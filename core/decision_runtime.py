"""Derived task-prioritization helpers for the operational runtime."""

from __future__ import annotations

from copy import deepcopy
from collections import defaultdict

from core.runtime_event_window import events_since_latest_plan_update
from core.success_memory import parse_success_memory_note
from core.work_profile import derive_task_work_profile

MAX_EVIDENCE_EVENT_IDS = 6


def _valid_string_list(values: object) -> list[str]:
    if not isinstance(values, list):
        return []
    return [item for item in values if isinstance(item, str) and item]


def _task_working_set_bucket(working_set: list[str]) -> str:
    size = len([path for path in working_set if isinstance(path, str) and path])
    if size <= 0:
        return "undefined"
    if size == 1:
        return "single"
    if size <= 3:
        return "small"
    return "wide"


def _task_action_kinds(task_actions: list[dict]) -> list[str]:
    kinds: list[str] = []
    for action in task_actions:
        action_kind = action.get("kind")
        if isinstance(action_kind, str) and action_kind and action_kind not in kinds:
            kinds.append(action_kind)
    return kinds


def _append_unique_event_id(event_ids: list[str], candidate: object) -> None:
    if not isinstance(candidate, str):
        return
    cleaned = candidate.strip()
    if cleaned and cleaned not in event_ids:
        event_ids.append(cleaned)


def _build_task_event_provenance(recent_events: tuple[dict, ...] = ()) -> dict:
    events = events_since_latest_plan_update(recent_events)
    task_event_ids: dict[str, list[str]] = defaultdict(list)
    verification_event_ids: list[str] = []
    for event in events:
        if not isinstance(event, dict):
            continue
        event_id = event.get("event_id", "")
        if not isinstance(event_id, str) or not event_id.strip():
            continue
        event_type = event.get("event_type", event.get("event", ""))
        for task_id in _valid_string_list(event.get("tasks", [])):
            _append_unique_event_id(task_event_ids[task_id], event_id)
        task_id = event.get("task_id", "")
        if isinstance(task_id, str) and task_id.strip():
            _append_unique_event_id(task_event_ids[task_id.strip()], event_id)
        selected_task_id = event.get("selected_task_id", "")
        if isinstance(selected_task_id, str) and selected_task_id.strip():
            _append_unique_event_id(task_event_ids[selected_task_id.strip()], event_id)
        if event_type == "verification_completed":
            _append_unique_event_id(verification_event_ids, event_id)
    return {
        "task_event_ids": {
            task_id: event_ids[:MAX_EVIDENCE_EVENT_IDS]
            for task_id, event_ids in task_event_ids.items()
        },
        "verification_event_ids": verification_event_ids[:MAX_EVIDENCE_EVENT_IDS],
    }


def _load_success_patterns(agent_runtime: dict) -> list[dict]:
    notes = agent_runtime.get("memory", {}).get("notes", [])
    if not isinstance(notes, list):
        return []
    patterns_by_signature: dict[str, dict] = {}
    for note in notes:
        pattern = parse_success_memory_note(note)
        if pattern is not None:
            signature = pattern.get("pattern_signature", "")
            if not isinstance(signature, str) or not signature:
                continue
            patterns_by_signature[signature] = pattern
    return list(patterns_by_signature.values())


def _build_success_pattern_index(success_patterns: list[dict]) -> dict[tuple[str, bool, bool], list[dict]]:
    index: dict[tuple[str, bool, bool], list[dict]] = defaultdict(list)
    for pattern in success_patterns:
        index[
            (
                pattern["working_set_bucket"],
                pattern["acceptance_defined"],
                pattern["has_sensitive_actions"],
            )
        ].append(pattern)
    return index


def _matching_success_patterns(
    success_pattern_index: dict[tuple[str, bool, bool], list[dict]],
    *,
    working_set_bucket: str,
    acceptance_defined: bool,
    action_kinds: list[str],
    has_sensitive_actions: bool,
) -> list[dict]:
    success_patterns = success_pattern_index.get(
        (working_set_bucket, acceptance_defined, has_sensitive_actions),
        [],
    )
    matches: list[dict] = []
    for pattern in success_patterns:
        pattern_action_kinds = pattern["action_kinds"]
        if action_kinds:
            if pattern_action_kinds == action_kinds or pattern_action_kinds[: len(action_kinds)] == action_kinds:
                matches.append(pattern)
        elif pattern["cost"] <= 32:
            matches.append(pattern)
    return matches


def _build_decision_surface(agent_runtime: dict, recent_events: tuple[dict, ...]) -> dict:
    verification = agent_runtime.get("verification", {})
    actions = agent_runtime.get("actions", [])
    approvals = agent_runtime.get("approvals", {}).get("items", [])

    action_by_id = {
        action["id"]: action
        for action in actions
        if isinstance(action, dict) and isinstance(action.get("id"), str)
    }
    pending_action_ids = set(_valid_string_list(verification.get("pending_action_ids", [])))
    pending_approvals = [
        approval
        for approval in approvals
        if isinstance(approval, dict) and approval.get("status") == "pending"
    ]
    pending_approval_tasks = {
        approval["task_id"]
        for approval in pending_approvals
        if isinstance(approval.get("task_id"), str) and approval["task_id"]
    }
    success_patterns = _load_success_patterns(agent_runtime)
    success_pattern_index = _build_success_pattern_index(success_patterns)
    failed_attempt_count = verification.get("failed_attempt_count", 0)
    if not isinstance(failed_attempt_count, int) or failed_attempt_count < 0:
        failed_attempt_count = 0

    return {
        "action_by_id": action_by_id,
        "pending_action_ids": pending_action_ids,
        "pending_approvals": pending_approvals,
        "pending_approval_tasks": pending_approval_tasks,
        "verification": verification,
        "repeated_failed_verifications": failed_attempt_count >= 2,
        "success_pattern_index": success_pattern_index,
    }


def _summarize_task_actions(task_actions: list[dict]) -> dict:
    failed_actions: list[dict] = []
    rolled_back_actions: list[dict] = []
    sensitive_actions: list[dict] = []
    action_signatures: list[tuple[str, str, str]] = []
    approval_count = 0

    for action in task_actions:
        status = action.get("status")
        if isinstance(status, str):
            if status in {"failed", "blocked"}:
                failed_actions.append(action)
            elif status == "rolled_back":
                rolled_back_actions.append(action)

        if action.get("kind") in {"fs.write_patch", "fs.move", "fs.delete_soft"}:
            sensitive_actions.append(action)

        details = action.get("details", {})
        if isinstance(details, dict):
            action_signatures.append(
                (
                    action.get("kind", ""),
                    action.get("target", ""),
                    details.get("fingerprint", ""),
                )
            )

        if action.get("approval_id"):
            approval_count += 1

    unique_signatures = {signature for signature in action_signatures if any(signature)}
    return {
        "failed_actions": failed_actions,
        "rolled_back_actions": rolled_back_actions,
        "sensitive_actions": sensitive_actions,
        "action_kinds": _task_action_kinds(task_actions),
        "approval_count": approval_count,
        "redundant_attempts": max(0, len(action_signatures) - len(unique_signatures)),
    }


def derive_task_assessments(agent_runtime: dict, recent_events: tuple[dict, ...] = ()) -> list[dict]:
    """Return evidence-backed task assessments derived from runtime state."""
    plan = agent_runtime.get("plan", {})
    tasks = plan.get("tasks", [])
    surface = _build_decision_surface(agent_runtime, recent_events)
    provenance = _build_task_event_provenance(recent_events)
    action_by_id = surface["action_by_id"]
    pending_action_ids = surface["pending_action_ids"]
    pending_approvals = surface["pending_approvals"]
    pending_approval_tasks = surface["pending_approval_tasks"]
    verification = surface["verification"]
    repeated_failed_verifications = surface["repeated_failed_verifications"]
    success_pattern_index = surface["success_pattern_index"]
    task_event_ids = provenance["task_event_ids"]
    verification_event_ids = provenance["verification_event_ids"]

    assessments: list[dict] = []
    for task in tasks:
        if not isinstance(task, dict):
            continue

        task_id = task.get("id", "")
        action_ids = _valid_string_list(task.get("action_ids", []))
        task_actions = [action_by_id[action_id] for action_id in action_ids if action_id in action_by_id]
        retry_blocked_count = task.get("retry_blocked_count", 0)
        if not isinstance(retry_blocked_count, int) or retry_blocked_count < 0:
            retry_blocked_count = 0
        verify_blocked_count = task.get("verify_blocked_count", 0)
        if not isinstance(verify_blocked_count, int) or verify_blocked_count < 0:
            verify_blocked_count = 0
        apply_blocked_count = task.get("apply_blocked_count", 0)
        if not isinstance(apply_blocked_count, int) or apply_blocked_count < 0:
            apply_blocked_count = 0

        evidence: list[str] = []
        evidence_event_ids = list(task_event_ids.get(task_id, ()))
        recent_history: list[str] = []
        impact = 10
        estimated_cost = 10
        risk = 5
        status = task.get("status", "")

        if status == "running":
            impact += 45
            evidence.append("task is already in progress")
        elif status == "ready":
            impact += 30
            evidence.append("task is executable now")
        elif status == "blocked":
            impact += 12
            estimated_cost += 12
            evidence.append("task is blocked by unfinished dependencies")
        elif status == "failed":
            impact += 40
            risk += 20
            evidence.append("task is in failed state")
        elif status == "done":
            evidence.append("task is already completed")

        depends_on = _valid_string_list(task.get("depends_on", []))
        if depends_on:
            estimated_cost += len(depends_on) * 8
            evidence.append(f"task depends on {len(depends_on)} prerequisite(s)")

        working_set = _valid_string_list(task.get("working_set", []))
        acceptance = _valid_string_list(task.get("acceptance_criteria", []))

        if action_ids:
            estimated_cost += len(action_ids) * 6
            evidence.append(f"task already owns {len(action_ids)} recorded action(s)")
            recent_history.append(f"actions={len(action_ids)}")

        pending_task_actions = [action_id for action_id in action_ids if action_id in pending_action_ids]
        task_has_pending_approval = task_id in pending_approval_tasks
        task_profile = derive_task_work_profile(
            agent_runtime,
            task,
            task_actions=task_actions,
            pending_task_actions=pending_task_actions,
            task_has_pending_approval=task_has_pending_approval,
        )

        if working_set:
            impact += 8
            estimated_cost += max(0, len(working_set) - 1) * 4
            evidence.append("task defines an explicit execution surface")
            evidence.append(f"working set is bounded to {len(working_set)} path(s)")
        elif task_profile["requires_working_set"]:
            estimated_cost += 12
            risk += 8
            evidence.append("working set is undefined")
        else:
            evidence.append("task does not require a workspace-bound working set")
        working_set_bucket = _task_working_set_bucket(working_set)

        if acceptance:
            impact += 8
            evidence.append("task defines explicit completion criteria")
            evidence.append(f"acceptance criteria defined: {len(acceptance)}")
        elif task_profile["requires_acceptance_criteria"]:
            estimated_cost += 12
            risk += 8
            evidence.append("acceptance criteria are missing")
        else:
            evidence.append("task can close by explicit state transition without verify-style acceptance criteria")
        acceptance_defined = bool(acceptance)

        evidence.append(
            f"task is classified as {task_profile['workload_mode']} {task_profile['work_unit_kind']}"
        )

        if pending_task_actions:
            impact += 35
            risk += 20
            evidence.append(f"task owns {len(pending_task_actions)} action(s) pending verification")

        if len(pending_task_actions) >= 3:
            unresolved_action_burden = len(pending_task_actions) - 2
            estimated_cost += unresolved_action_burden * 8
            risk += min(12, unresolved_action_burden * 4)
            evidence.append(
                f"task has high pending action burden without verified closure ({len(pending_task_actions)} pending actions)"
            )
            recent_history.append(f"pending_action_burden={len(pending_task_actions)}")

        if verification.get("status") == "failed" and pending_task_actions:
            impact += 25
            evidence.append("pending task actions are blocked by failed verification")

        if repeated_failed_verifications and pending_task_actions:
            impact += 15
            risk += 10
            evidence.append("repeated verification failures are affecting this task")

        if pending_task_actions:
            for event_id in verification_event_ids:
                _append_unique_event_id(evidence_event_ids, event_id)

        action_summary = _summarize_task_actions(task_actions)
        failed_actions = action_summary["failed_actions"]
        if failed_actions:
            impact += 18
            risk += 18
            evidence.append(f"task has {len(failed_actions)} failed or blocked action(s)")
            recent_history.append(f"failed_actions={len(failed_actions)}")

        rolled_back_actions = action_summary["rolled_back_actions"]
        if rolled_back_actions:
            risk += 12
            evidence.append(f"task has {len(rolled_back_actions)} rolled back action(s)")
            recent_history.append(f"rolled_back_actions={len(rolled_back_actions)}")

        redundant_attempts = action_summary["redundant_attempts"]
        if redundant_attempts:
            evidence.append(f"task has {redundant_attempts} redundant action attempt(s)")
            recent_history.append(f"redundant_attempts={redundant_attempts}")

        if retry_blocked_count:
            impact += 15
            risk += 10
            evidence.append(f"task has {retry_blocked_count} blocked retry attempt(s)")
            recent_history.append(f"retry_blocked={retry_blocked_count}")

        if verify_blocked_count:
            estimated_cost += verify_blocked_count * 6
            evidence.append(f"task has {verify_blocked_count} blocked verify attempt(s)")
            recent_history.append(f"verify_blocked={verify_blocked_count}")

        if apply_blocked_count:
            estimated_cost += apply_blocked_count * 6
            risk += 4
            evidence.append(f"task has {apply_blocked_count} blocked apply attempt(s)")
            recent_history.append(f"apply_blocked={apply_blocked_count}")

        sensitive_actions = action_summary["sensitive_actions"]
        if sensitive_actions:
            risk += min(24, 8 * len(sensitive_actions))
            evidence.append("task contains sensitive filesystem mutations")

        if action_summary["approval_count"]:
            risk += 10
            evidence.append("task has approval-governed actions")

        if task_has_pending_approval:
            impact += 18
            risk += 10
            estimated_cost += 8
            evidence.append("task is waiting on a pending approval")
            recent_history.append("pending_approval=1")
        elif pending_approvals and status == "ready":
            evidence.append("other runtime tasks are waiting on approval")

        action_kinds = action_summary["action_kinds"]
        has_sensitive_actions = bool(sensitive_actions)
        success_matches: list[dict] = []
        success_boost = 0
        success_cost_reduction = 0
        if status in {"ready", "running"}:
            success_matches = _matching_success_patterns(
                success_pattern_index,
                working_set_bucket=working_set_bucket,
                acceptance_defined=acceptance_defined,
                action_kinds=action_kinds,
                has_sensitive_actions=has_sensitive_actions,
            )
            if success_matches:
                support_weight = len(success_matches)
                success_boost = min(18, support_weight * 6)
                if action_kinds and any(match["action_kinds"] == action_kinds for match in success_matches):
                    success_boost += 4
                    evidence.append("current action mix matches a previously successful pattern")
                impact += success_boost
                success_cost_reduction = min(12, support_weight * 4)
                estimated_cost = max(0, estimated_cost - success_cost_reduction)
                evidence.append(f"task matches {support_weight} verified success pattern(s)")
                recent_history.append(f"success_matches={support_weight}")

        if success_matches and (
            retry_blocked_count
            or apply_blocked_count
            or verify_blocked_count
            or failed_actions
            or rolled_back_actions
        ):
            confidence_penalty = min(success_boost, 10)
            impact = max(0, impact - confidence_penalty)
            estimated_cost += success_cost_reduction
            evidence.append("recent blocked or failed attempts reduced confidence in the learned success pattern")
            recent_history.append("success_pattern_confidence_reduced")

        real_cost = (
            len(task_actions) * 10
            + len(failed_actions) * 12
            + len(rolled_back_actions) * 10
            + redundant_attempts * 18
            + retry_blocked_count * 20
            + verify_blocked_count * 16
            + apply_blocked_count * 12
        )
        cost = estimated_cost + real_cost

        executable = status in {"ready", "running"}
        if status in {"ready", "running"} and verification.get("status") == "failed":
            executable = False
            risk += 18
            evidence.append("task is blocked until verification is rerun successfully")
        if task_has_pending_approval:
            executable = False
            evidence.append("task is blocked until approval is resolved")

        if status == "done":
            priority = 0
        else:
            raw_priority = (impact * 2) - cost - risk
            if not executable:
                raw_priority -= 20
            priority = max(0, min(100, raw_priority))

        assessments.append(
            {
                "id": task_id,
                "title": task.get("title", ""),
                "status": status,
                "executable": executable,
                "impact": impact,
                "estimated_cost": estimated_cost,
                "real_cost": real_cost,
                "cost": cost,
                "risk": risk,
                "priority": priority,
                "evidence": evidence,
                "evidence_event_ids": evidence_event_ids[:MAX_EVIDENCE_EVENT_IDS],
                "recent_history": recent_history,
                "work_unit_kind": task_profile["work_unit_kind"],
                "workload_mode": task_profile["workload_mode"],
            }
        )

    assessments.sort(
        key=lambda item: (
            0 if item["status"] == "running" else 1 if item["status"] == "ready" else 2,
            -item["priority"],
            item["cost"],
            item["id"],
        )
    )
    return assessments


def _select_from_assessments(assessments: list[dict]) -> dict:
    """Choose the best executable task from an already-derived assessment surface."""
    candidates = [item for item in assessments if item["executable"]]
    if not candidates:
        return {
            "task_id": "",
            "priority": 0,
            "impact": 0,
            "cost": 0,
            "risk": 0,
            "evidence": [],
            "evidence_event_ids": [],
            "reason": "no executable task is available from the current runtime state",
        }

    selected = deepcopy(candidates[0])
    selected["task_id"] = selected["id"]
    selected["rejected_alternatives"] = [
        {
            "task_id": item["id"],
            "reason": (
                "not selected because it is not executable"
                if not item["executable"]
                else f"lower priority than selected task ({item['priority']} < {selected['priority']})"
            ),
            "priority": item["priority"],
        }
        for item in assessments
        if item["id"] != selected["id"]
    ][:3]
    selected["reason"] = (
        f"selected for highest executable priority based on impact={selected['impact']}, "
        f"cost={selected['cost']}, risk={selected['risk']}, real_cost={selected['real_cost']}"
    )
    return selected


def evaluate_task_selection_consistency(
    agent_runtime: dict,
    recent_events: tuple[dict, ...] = (),
    *,
    assessments: tuple[dict, ...] | list[dict] | None = None,
) -> dict:
    """Replay task selection from the current runtime state without mutating it."""
    if assessments is None:
        derived_assessments = derive_task_assessments(agent_runtime, recent_events)
    else:
        derived_assessments = [deepcopy(item) for item in assessments if isinstance(item, dict)]
    selection = _select_from_assessments(derived_assessments)
    current_task_id = agent_runtime.get("plan", {}).get("current_task_id", "")
    if not isinstance(current_task_id, str):
        current_task_id = ""
    plan_status = agent_runtime.get("plan", {}).get("status", "")
    if not isinstance(plan_status, str):
        plan_status = ""
    current_assessment = next(
        (item for item in derived_assessments if item.get("id") == current_task_id),
        None,
    )
    derived_task_id = selection["task_id"]
    current_priority = current_assessment.get("priority", 0) if isinstance(current_assessment, dict) else 0
    derived_priority = selection.get("priority", 0) if derived_task_id else 0

    if plan_status not in {"ready", "running"}:
        if current_task_id:
            status = "mismatch"
            reason = f"current_task_id should be empty while plan status is {plan_status or 'unknown'}"
        else:
            status = "not_applicable"
            reason = f"selection replay is not applicable while plan status is {plan_status or 'unknown'}"
    elif current_task_id == derived_task_id:
        status = "consistent"
        reason = "current_task_id matches the best executable task from the current assessment surface"
    elif not current_task_id and derived_task_id:
        status = "mismatch"
        reason = "current_task_id is empty while an executable task is available"
    elif current_task_id and current_assessment is None:
        status = "mismatch"
        reason = "current_task_id does not resolve to a current assessment"
    elif current_task_id and isinstance(current_assessment, dict) and not current_assessment.get("executable", False):
        status = "mismatch"
        reason = "current_task_id points to a task that is not currently executable"
    else:
        status = "mismatch"
        reason = "current_task_id does not match the best executable task from the current assessment surface"

    return {
        "status": status,
        "plan_status": plan_status,
        "current_task_id": current_task_id,
        "derived_task_id": derived_task_id,
        "current_priority": current_priority,
        "derived_priority": derived_priority,
        "priority_gap": max(0, derived_priority - current_priority),
        "current_executable": bool(current_assessment.get("executable", False)) if isinstance(current_assessment, dict) else False,
        "derived_executable": bool(derived_task_id),
        "reason": reason,
    }


def choose_next_task(agent_runtime: dict, recent_events: tuple[dict, ...] = ()) -> dict:
    """Return the best current-task selection plus its evidence-backed justification."""
    assessments = derive_task_assessments(agent_runtime, recent_events)
    selected = _select_from_assessments(assessments)
    selected["assessments"] = assessments
    return selected
