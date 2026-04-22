"""Derived universal work-unit classification for multi-domain runtime tasks."""

from __future__ import annotations


GOVERNED_ACTION_KINDS = {
    "exec.command",
    "fs.create_file",
    "fs.delete_soft",
    "fs.move",
    "fs.write_patch",
}

VALID_WORK_UNIT_KINDS = {
    "state_only",
    "structured_state",
    "governed_execution",
}

VALID_WORKLOAD_MODES = {
    "light",
    "moderate",
    "heavy",
}


def _string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str) and item]


def derive_task_work_profile(
    agent_runtime: dict,
    task: dict,
    *,
    task_actions: list[dict] | None = None,
    pending_task_actions: list[str] | None = None,
    task_has_pending_approval: bool = False,
) -> dict:
    """Classify one task by operational weight without changing canonical state."""
    actions = task_actions if isinstance(task_actions, list) else []
    pending_actions = pending_task_actions if isinstance(pending_task_actions, list) else []
    plan = agent_runtime.get("plan", {})
    command_registry = agent_runtime.get("command_registry", {}).get("commands", [])

    working_set = _string_list(task.get("working_set", []))
    depends_on = _string_list(task.get("depends_on", []))
    acceptance_criteria = _string_list(task.get("acceptance_criteria", []))
    action_ids = _string_list(task.get("action_ids", []))
    action_kinds = [
        action.get("kind")
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("kind"), str) and action.get("kind")
    ]

    governed_signals = []
    task_has_governed_surface = bool(
        working_set
        or acceptance_criteria
        or action_ids
        or actions
        or pending_actions
        or task_has_pending_approval
    )
    if isinstance(command_registry, list) and command_registry and task_has_governed_surface:
        governed_signals.append("verification commands are registered for the task's governed surface")
    if working_set:
        governed_signals.append("task defines a bounded execution surface")
    if action_ids or actions:
        governed_signals.append("task owns recorded runtime actions")
    if pending_actions:
        governed_signals.append("task has actions pending verification")
    if task_has_pending_approval:
        governed_signals.append("task is gated by approval")
    if any(kind in GOVERNED_ACTION_KINDS for kind in action_kinds):
        governed_signals.append("task carries governed action kinds")

    if governed_signals:
        return {
            "work_unit_kind": "governed_execution",
            "workload_mode": "heavy",
            "requires_working_set": True,
            "requires_acceptance_criteria": True,
            "rationale": governed_signals,
        }

    structured_signals = []
    if depends_on:
        structured_signals.append("task is ordered by explicit dependencies")
    if acceptance_criteria:
        structured_signals.append("task defines state-level completion criteria")
    if isinstance(plan.get("tasks"), list) and len(plan["tasks"]) > 1 and (depends_on or acceptance_criteria):
        structured_signals.append("task participates in a multi-step structured plan")

    if structured_signals:
        return {
            "work_unit_kind": "structured_state",
            "workload_mode": "moderate",
            "requires_working_set": False,
            "requires_acceptance_criteria": False,
            "rationale": structured_signals,
        }

    return {
        "work_unit_kind": "state_only",
        "workload_mode": "light",
        "requires_working_set": False,
        "requires_acceptance_criteria": False,
        "rationale": [
            "task can be completed by an explicit state transition without governed execution"
        ],
    }


def derive_task_work_profiles(agent_runtime: dict) -> list[dict]:
    """Return one derived work profile per canonical task."""
    tasks = agent_runtime.get("plan", {}).get("tasks", [])
    actions = agent_runtime.get("actions", [])
    approvals = agent_runtime.get("approvals", {}).get("items", [])
    verification = agent_runtime.get("verification", {})

    action_by_id = {
        action["id"]: action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str) and action.get("id")
    }
    pending_action_ids = set(_string_list(verification.get("pending_action_ids", [])))
    pending_approval_tasks = {
        approval["task_id"]
        for approval in approvals
        if isinstance(approval, dict)
        and approval.get("status") == "pending"
        and isinstance(approval.get("task_id"), str)
        and approval["task_id"]
    }

    profiles: list[dict] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        action_ids = _string_list(task.get("action_ids", []))
        task_actions = [action_by_id[action_id] for action_id in action_ids if action_id in action_by_id]
        pending_task_actions = [action_id for action_id in action_ids if action_id in pending_action_ids]
        profile = derive_task_work_profile(
            agent_runtime,
            task,
            task_actions=task_actions,
            pending_task_actions=pending_task_actions,
            task_has_pending_approval=task_id in pending_approval_tasks,
        )
        profiles.append(
            {
                "id": task_id,
                "title": task.get("title", ""),
                **profile,
            }
        )
    return profiles


def summarize_workload_modes(task_profiles: list[dict]) -> dict[str, int]:
    """Return workload-mode counts for one runtime snapshot."""
    counts = {"light": 0, "moderate": 0, "heavy": 0}
    for profile in task_profiles:
        if not isinstance(profile, dict):
            continue
        mode = profile.get("workload_mode")
        if mode in counts:
            counts[mode] += 1
    return counts
