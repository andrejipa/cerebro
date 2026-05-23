"""Read-only operational status export derived from the canonical state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from core import StateStoreError, StateValidationError, iter_command_checks
from extensions._support import (
    exported_timestamp,
    read_snapshot_and_runtime,
    session_file_presence,
    validation_basis_line,
    validation_risk_level,
    write_markdown_output,
)


class StatusExportError(Exception):
    """Raised when the status export cannot be generated safely."""


def _events_since_latest_plan_update(events: tuple[dict, ...] | list[dict]) -> tuple[dict, ...]:
    """Keep extension diagnostics aligned to the latest plan generation without importing internal core helpers."""
    if not isinstance(events, (tuple, list)):
        return ()

    normalized = tuple(event for event in events if isinstance(event, dict))
    for index in range(len(normalized) - 1, -1, -1):
        if normalized[index].get("event") == "plan_updated":
            return normalized[index:]
    return normalized


def _load_recent_events(store, limit: int = 20) -> tuple[dict, ...]:
    try:
        return store.read_recent_events(limit=limit)
    except StateStoreError as exc:
        raise StatusExportError(f"failed to read runtime event log: {exc}") from exc


def _load_task_assessments(store, agent_runtime: dict, recent_events: tuple[dict, ...]) -> tuple[dict, ...]:
    try:
        return store.read_task_assessments(
            agent_runtime=agent_runtime,
            recent_events=recent_events,
        )
    except Exception as exc:
        raise StatusExportError(f"failed to derive runtime task assessments: {exc}") from exc


def _load_task_selection_consistency(
    store,
    agent_runtime: dict,
    recent_events: tuple[dict, ...],
    task_assessments: tuple[dict, ...],
) -> dict:
    try:
        return store.read_task_selection_consistency(
            agent_runtime=agent_runtime,
            recent_events=recent_events,
            task_assessments=task_assessments,
        )
    except Exception as exc:
        raise StatusExportError(f"failed to replay task selection consistency: {exc}") from exc


def _load_task_work_profiles(store, agent_runtime: dict) -> tuple[dict, ...]:
    try:
        return store.read_task_work_profiles(agent_runtime=agent_runtime)
    except Exception as exc:
        raise StatusExportError(f"failed to derive runtime task work profiles: {exc}") from exc


def _load_recent_consolidations(store, limit: int = 3) -> tuple[dict, ...]:
    try:
        return store.read_recent_consolidations(limit=limit)
    except StateStoreError as exc:
        raise StatusExportError(f"failed to derive parallel approach consolidations: {exc}") from exc


def _load_parallel_consolidation_view(
    store,
    recent_events: tuple[dict, ...],
    limit: int = 3,
) -> tuple[tuple[dict, ...], dict[tuple[str, str], dict]]:
    subjects: list[tuple[str, str]] = []
    for event in recent_events:
        if not isinstance(event, dict) or event.get("event") != "parallel_approach_consolidated":
            continue
        parsed = store.parse_parallel_approach_consolidation_event(event)
        if parsed is not None:
            subjects.append((parsed["subject_kind"], parsed["subject_id"]))
    try:
        return store.read_parallel_approach_consolidation_view(limit=limit, subjects=subjects)
    except StateStoreError as exc:
        raise StatusExportError(f"failed to derive parallel approach consolidations: {exc}") from exc


def _task_counts(tasks: list[dict]) -> dict[str, int]:
    counts = {
        "ready": 0,
        "blocked": 0,
        "running": 0,
        "done": 0,
        "failed": 0,
    }
    for task in tasks:
        if not isinstance(task, dict):
            continue
        status = task.get("status")
        if status in counts:
            counts[status] += 1
    return counts


def _workload_counts(task_profiles: tuple[dict, ...]) -> dict[str, int]:
    counts = {"light": 0, "moderate": 0, "heavy": 0}
    for profile in task_profiles:
        if not isinstance(profile, dict):
            continue
        mode = profile.get("workload_mode")
        if mode in counts:
            counts[mode] += 1
    return counts


def _runtime_diagnostics(
    agent_runtime: dict,
    recent_events: tuple[dict, ...],
    task_profiles: dict[str, dict],
) -> tuple[list[str], list[str]]:
    plan = agent_runtime["plan"]
    tasks = plan["tasks"]
    approvals = [
        approval
        for approval in agent_runtime["approvals"]["items"]
        if isinstance(approval, dict)
    ]
    pending_approvals = [approval for approval in approvals if approval["status"] == "pending"]
    verification = agent_runtime["verification"]
    commands = agent_runtime["command_registry"]["commands"]
    diagnostics: list[str] = []
    next_actions: list[str] = []
    heavy_task_ids = {
        task_id
        for task_id, profile in task_profiles.items()
        if profile.get("workload_mode") == "heavy"
    }
    heavy_tasks_missing_acceptance = [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("id") in heavy_task_ids
        and not task["acceptance_criteria"]
    ]
    heavy_tasks_missing_working_set = [
        task
        for task in tasks
        if isinstance(task, dict)
        and task.get("id") in heavy_task_ids
        and not task["working_set"]
    ]

    if heavy_task_ids and not commands:
        diagnostics.append("plan_has_no_registered_verification_commands")
        next_actions.append("update the active plan with at least one registered verification command")

    if heavy_tasks_missing_acceptance:
        diagnostics.append("tasks_missing_acceptance_criteria")
        next_actions.append("refine tasks with explicit acceptance criteria before widening execution scope")

    if heavy_tasks_missing_working_set:
        diagnostics.append("tasks_missing_working_set")
        next_actions.append("define working_set per task to keep execution bounded and reviewable")

    if pending_approvals:
        diagnostics.append("pending_approvals_present")
        next_actions.append("resolve pending approvals before retrying sensitive actions")

    required_command_ids = {
        command_id
        for command_id in verification.get("required_command_ids", [])
        if isinstance(command_id, str) and command_id
    }
    executed_command_ids = {
        check["command_id"]
        for check in iter_command_checks(verification)
        if check.get("status") == "passed"
        and isinstance(check.get("command_id"), str)
        and check["command_id"]
    }
    if verification["pending_action_ids"]:
        diagnostics.append("actions_pending_verification")
        next_actions.append("run `cerebro verify` before applying additional workspace mutations")
        if required_command_ids and not required_command_ids.issubset(executed_command_ids):
            diagnostics.append("verification_required_coverage_incomplete")
            next_actions.append("run the remaining required verification commands before treating the current delta as closed")

    if verification["status"] == "failed":
        diagnostics.append("verification_failed")
        next_actions.append("fix the failing verification command or rollback the pending action set")

    recent_failed_verifications = [
        event
        for event in recent_events
        if isinstance(event, dict)
        and event.get("event") == "verification_completed"
        and event.get("status") == "failed"
    ]
    if len(recent_failed_verifications) >= 2:
        diagnostics.append("repeated_verification_failures")
        next_actions.append("stop retrying the same verification path; replan, fix the command, or rollback the pending action set")

    if plan["status"] == "blocked":
        diagnostics.append("plan_blocked")
        next_actions.append("unblock dependencies or reduce the task graph before continuing")

    if any(
        isinstance(command, dict)
        and (command.get("risk") == "high" or command.get("side_effect") == "external_write")
        for command in commands
    ):
        diagnostics.append("high_risk_commands_registered")
        next_actions.append("review high-risk commands and keep them behind explicit approvals only")

    unique_actions: list[str] = []
    for action in next_actions:
        if action not in unique_actions:
            unique_actions.append(action)

    return diagnostics, unique_actions


def _cycle_cost_summary(agent_runtime: dict, recent_events: tuple[dict, ...], task_counts: dict[str, int]) -> dict[str, object]:
    actions = [
        action
        for action in agent_runtime["actions"]
        if isinstance(action, dict)
    ]
    applied_count = sum(1 for action in actions if action.get("status") == "applied")
    failed_count = sum(1 for action in actions if action.get("status") == "failed")
    blocked_count = sum(1 for action in actions if action.get("status") == "blocked")
    rolled_back_count = sum(1 for action in actions if action.get("status") == "rolled_back")
    recent_verification_failures = sum(
        1
        for event in recent_events
        if isinstance(event, dict)
        and event.get("event") == "verification_completed"
        and event.get("status") == "failed"
    )
    recent_retry_blocked = sum(
        1
        for event in recent_events
        if isinstance(event, dict) and event.get("event") == "retry_blocked"
    )
    recent_apply_blocked = sum(
        1
        for event in recent_events
        if isinstance(event, dict) and event.get("event") == "apply_blocked"
    )
    recent_verify_blocked = sum(
        1
        for event in recent_events
        if isinstance(event, dict) and event.get("event") == "verify_blocked"
    )
    completed_tasks = task_counts.get("done", 0)
    terminal_tasks = completed_tasks + task_counts.get("failed", 0)
    active_tasks = task_counts.get("ready", 0) + task_counts.get("blocked", 0) + task_counts.get("running", 0)
    ratio = applied_count / completed_tasks if completed_tasks else None
    rising_without_closure = (
        completed_tasks == 0
        and applied_count >= 1
        and (
            recent_verification_failures >= 2
            or recent_retry_blocked >= 2
            or recent_apply_blocked >= 2
            or recent_verify_blocked >= 2
            or failed_count >= 1
            or rolled_back_count >= 1
        )
    )
    return {
        "actions_total": len(actions),
        "actions_applied": applied_count,
        "actions_failed": failed_count,
        "actions_blocked": blocked_count,
        "actions_rolled_back": rolled_back_count,
        "tasks_completed": completed_tasks,
        "tasks_terminal": terminal_tasks,
        "tasks_active": active_tasks,
        "actions_per_completed_task": ratio,
        "recent_verification_failures": recent_verification_failures,
        "recent_retry_blocked": recent_retry_blocked,
        "recent_apply_blocked": recent_apply_blocked,
        "recent_verify_blocked": recent_verify_blocked,
        "rising_without_closure": rising_without_closure,
    }


def _format_event_line(event: dict) -> str:
    recorded_at = event.get("recorded_at") or "unknown"
    event_type = event.get("event") or "unknown_event"
    action_id = event.get("action_id")
    approval_id = event.get("approval_id")
    subject_kind = event.get("subject_kind")
    subject_id = event.get("subject_id")
    consolidation_id = event.get("consolidation_id")
    winner_id = event.get("winner_id")
    status = event.get("status")
    target = event.get("target")
    task_id = event.get("task_id")
    cost = event.get("cost")
    parts = [f"{recorded_at} :: {event_type}"]
    if action_id:
        parts.append(f"action={action_id}")
    if approval_id:
        parts.append(f"approval={approval_id}")
    if isinstance(subject_kind, str) and isinstance(subject_id, str) and subject_kind and subject_id:
        parts.append(f"subject={subject_kind}:{subject_id}")
    if isinstance(consolidation_id, str) and consolidation_id:
        parts.append(f"consolidation={consolidation_id}")
    if isinstance(winner_id, str) and winner_id:
        parts.append(f"winner={winner_id}")
    if status:
        parts.append(f"status={status}")
    if target:
        parts.append(f"target={target}")
    if task_id:
        parts.append(f"task={task_id}")
    if isinstance(cost, int):
        parts.append(f"cost={cost}")
    return " | ".join(parts)


def _format_consolidation_line(consolidation: dict) -> list[str]:
    lines = [
        f"- {consolidation['subject_kind']} {consolidation['subject_id']}: id={consolidation['consolidation_id']}; winner={consolidation['winner_id']}",
    ]
    if consolidation.get("winner_label"):
        lines[0] += f" ({consolidation['winner_label']})"
    lines[0] += f"; supersedes={consolidation.get('supersedes_consolidation_id') or 'root'}"
    if consolidation.get("compared_approach_ids"):
        lines[0] += f"; compared={', '.join(consolidation['compared_approach_ids'])}"
    if consolidation.get("rejected_approach_ids"):
        lines[0] += f"; rejected={', '.join(consolidation['rejected_approach_ids'])}"
    if consolidation.get("comparison_basis"):
        lines.append(f"  basis: {'; '.join(consolidation['comparison_basis'])}")
    if consolidation.get("decision"):
        lines.append(f"  decision: {consolidation['decision']}")
    if consolidation.get("comparison_event_ids"):
        lines.append(f"  compared events: {', '.join(consolidation['comparison_event_ids'])}")
    return lines


def _sanitize_recent_event_for_display(store, event: dict) -> dict:
    if not isinstance(event, dict):
        return {
            "recorded_at": "",
            "event": "unreadable_event_log_record",
        }
    if event.get("event") != "parallel_approach_consolidated":
        return event
    parsed = store.parse_parallel_approach_consolidation_event(event)
    if parsed is None:
        sanitized = {
            "recorded_at": event.get("recorded_at", ""),
            "event": "invalid_parallel_approach_consolidation_record",
        }
        subject_kind = event.get("subject_kind")
        subject_id = event.get("subject_id")
        consolidation_id = event.get("consolidation_id")
        if isinstance(subject_kind, str) and isinstance(subject_id, str) and subject_kind and subject_id:
            sanitized["subject_kind"] = subject_kind
            sanitized["subject_id"] = subject_id
        if isinstance(consolidation_id, str) and consolidation_id:
            sanitized["consolidation_id"] = consolidation_id
        return sanitized
    current_head = store.read_parallel_approach_consolidation_head(
        parsed["subject_kind"],
        parsed["subject_id"],
    )
    if current_head is not None and current_head["consolidation_id"] == parsed["consolidation_id"]:
        return event
    sanitized = {
        "recorded_at": parsed.get("recorded_at", event.get("recorded_at", "")),
        "event": "stale_parallel_approach_consolidation_record",
        "subject_kind": parsed["subject_kind"],
        "subject_id": parsed["subject_id"],
        "consolidation_id": parsed["consolidation_id"],
    }
    if current_head is None:
        sanitized["target"] = "current=none"
    else:
        sanitized["target"] = f"current={current_head['consolidation_id']}"
    return sanitized


def _sanitize_recent_events_for_display(
    store,
    events: tuple[dict, ...],
    head_map: dict[tuple[str, str], dict],
) -> tuple[dict, ...]:
    parsed_consolidations: list[dict | None] = []
    for event in events:
        parsed = None
        if isinstance(event, dict) and event.get("event") == "parallel_approach_consolidated":
            parsed = store.parse_parallel_approach_consolidation_event(event)
        parsed_consolidations.append(parsed)
    sanitized: list[dict] = []
    for event, parsed in zip(events, parsed_consolidations, strict=False):
        if not isinstance(event, dict):
            sanitized.append(
                {
                    "recorded_at": "",
                    "event": "unreadable_event_log_record",
                }
            )
            continue
        if event.get("event") != "parallel_approach_consolidated":
            sanitized.append(event)
            continue
        if parsed is None:
            sanitized.append(_sanitize_recent_event_for_display(store, event))
            continue
        current_head = head_map.get((parsed["subject_kind"], parsed["subject_id"]))
        if current_head is not None and current_head["consolidation_id"] == parsed["consolidation_id"]:
            sanitized.append(event)
            continue
        degraded = {
            "recorded_at": parsed.get("recorded_at", event.get("recorded_at", "")),
            "event": "stale_parallel_approach_consolidation_record",
            "subject_kind": parsed["subject_kind"],
            "subject_id": parsed["subject_id"],
            "consolidation_id": parsed["consolidation_id"],
        }
        if current_head is None:
            degraded["target"] = "current=none"
        else:
            degraded["target"] = f"current={current_head['consolidation_id']}"
        sanitized.append(degraded)
    return tuple(sanitized)


def _recent_flow_control(agent_runtime: dict) -> tuple[list[str], list[str]]:
    approvals = [
        approval
        for approval in agent_runtime["approvals"]["items"]
        if isinstance(approval, dict)
    ]
    actions = [
        action
        for action in agent_runtime["actions"]
        if isinstance(action, dict)
    ]
    approval_lines: list[str] = []
    batch_lines: list[str] = []

    pending_approvals = sorted(
        [approval for approval in approvals if approval["status"] == "pending"],
        key=lambda approval: approval.get("requested_at", ""),
        reverse=True,
    )[:3]
    for approval in pending_approvals:
        approval_lines.append(
            f"pending approval {approval['id']}: {approval['action_kind']} -> {approval['target']}"
        )

    recent_resolutions = sorted(
        [approval for approval in approvals if approval["status"] in {"approved", "rejected"}],
        key=lambda approval: approval.get("resolved_at") or approval.get("requested_at", ""),
        reverse=True,
    )[:3]
    for approval in recent_resolutions:
        approval_lines.append(
            f"recent approval {approval['status']} {approval['id']}: {approval['action_kind']} -> {approval['target']}"
        )

    batches: dict[str, dict] = {}
    for action in actions:
        batch_id = action.get("batch_id")
        if not isinstance(batch_id, str) or not batch_id:
            continue
        batch = batches.setdefault(
            batch_id,
            {
                "action_count": 0,
                "latest_status": "",
                "latest_updated_at": "",
            },
        )
        batch["action_count"] += 1
        updated_at = action.get("updated_at", "")
        if updated_at >= batch["latest_updated_at"]:
            batch["latest_updated_at"] = updated_at
            batch["latest_status"] = action.get("status", "")

    recent_batches = sorted(
        batches.items(),
        key=lambda item: item[1]["latest_updated_at"],
        reverse=True,
    )[:3]
    for batch_id, batch in recent_batches:
        batch_lines.append(
            f"recent batch {batch_id}: actions={batch['action_count']}, latest_status={batch['latest_status'] or 'unknown'}"
        )

    return approval_lines, batch_lines


def export_status_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured operational status panel from the current snapshot."""
    store, snapshot, agent_runtime = read_snapshot_and_runtime(root, StatusExportError)
    recent_events_error = ""
    task_assessments_error = ""
    selection_consistency_error = ""
    consolidation_error = ""
    task_profiles_error = ""
    recent_events: tuple[dict, ...] = ()
    recent_events_for_display: tuple[dict, ...] = ()
    current_plan_recent_events: tuple[dict, ...] = ()
    trace_observability = store.read_trace_observability(agent_runtime=agent_runtime)
    trace_status_degraded = trace_observability["trace_status"] != "healthy"
    trace_integrity_partial = trace_observability["trace_integrity"] != "reliable"
    trace_partial = trace_status_degraded or trace_integrity_partial

    try:
        recent_events = _load_recent_events(store)
        recent_events_for_display = recent_events[-5:]
        current_plan_recent_events = _events_since_latest_plan_update(recent_events)
    except StatusExportError as exc:
        recent_events = ()
        recent_events_for_display = ()
        current_plan_recent_events = ()
        recent_events_error = str(exc)
    sanitized_recent_events: tuple[dict, ...] = ()

    try:
        consolidations, consolidation_head_map = _load_parallel_consolidation_view(store, recent_events_for_display)
    except StatusExportError as exc:
        consolidations = ()
        consolidation_head_map = {}
        consolidation_error = str(exc)

    try:
        task_assessments = _load_task_assessments(
            store,
            agent_runtime,
            current_plan_recent_events if not recent_events_error else (),
        )
    except StatusExportError as exc:
        task_assessments = ()
        task_assessments_error = str(exc)

    if task_assessments_error:
        selection_consistency = {}
        selection_consistency_error = "task assessment surface unavailable"
    else:
        try:
            selection_consistency = _load_task_selection_consistency(
                store,
                agent_runtime,
                current_plan_recent_events if not recent_events_error else (),
                task_assessments,
            )
        except StatusExportError as exc:
            selection_consistency = {}
            selection_consistency_error = str(exc)

    try:
        task_profiles = _load_task_work_profiles(store, agent_runtime)
    except StatusExportError as exc:
        task_profiles = ()
        task_profiles_error = str(exc)

    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()

    tasks = [
        task
        for task in agent_runtime["plan"]["tasks"]
        if isinstance(task, dict)
    ]
    task_counts = _task_counts(tasks)
    approvals = [
        approval
        for approval in agent_runtime["approvals"]["items"]
        if isinstance(approval, dict)
    ]
    notes = [
        note
        for note in agent_runtime["memory"]["notes"]
        if isinstance(note, dict)
    ]
    task_profiles_by_id = {
        profile["id"]: profile
        for profile in task_profiles
        if isinstance(profile, dict) and isinstance(profile.get("id"), str) and profile.get("id")
    }
    workload_counts = _workload_counts(task_profiles)
    diagnostics, next_actions = _runtime_diagnostics(
        agent_runtime,
        current_plan_recent_events if not trace_partial else (),
        task_profiles_by_id,
    )
    approval_lines, batch_lines = _recent_flow_control(agent_runtime)
    cycle_cost_summary = _cycle_cost_summary(
        agent_runtime,
        current_plan_recent_events if not trace_partial else (),
        task_counts,
    )
    current_task_id = agent_runtime["plan"]["current_task_id"] or "none"
    plan_status = agent_runtime["plan"]["status"]
    command_count = len(agent_runtime["command_registry"]["commands"])
    action_count = len(agent_runtime["actions"])
    pending_approval_count = len([approval for approval in approvals if approval["status"] == "pending"])
    pending_verification_count = len(agent_runtime["verification"]["pending_action_ids"])
    memory_note_count = len(notes)
    consolidation_count = len(consolidations)

    if trace_status_degraded:
        diagnostics.append("trace_degraded")
        next_actions.append("restore trace append health before relying on event-derived diagnostics or cycle pressure")

    if trace_integrity_partial:
        diagnostics.append("trace_integrity_partial")
        next_actions.append("treat event-derived diagnostics as partial until a fresh trace thread restores analytical confidence")

    if trace_partial:
        diagnostics.append("runtime_diagnostics_partial")

    if recent_events_error:
        diagnostics.append("runtime_event_log_unavailable")
        next_actions.append("inspect the runtime event log path and restore recent-event reads")

    if task_assessments_error:
        diagnostics.append("task_assessment_surface_unavailable")
        next_actions.append("restore task assessment derivation before relying on prioritized execution guidance")

    if selection_consistency_error:
        diagnostics.append("task_selection_replay_unavailable")
        next_actions.append("restore task-selection replay before relying on decision-consistency diagnostics")
    elif selection_consistency.get("status") == "mismatch":
        diagnostics.append("task_selection_replay_mismatch")
        next_actions.append("refresh current_task_id from the current decision surface before relying on execution guidance")

    if task_profiles_error:
        diagnostics.append("task_profile_surface_unavailable")
        next_actions.append("restore derived work-profile reads before relying on lightweight versus governed diagnostics")

    if consolidation_error:
        diagnostics.append("parallel_consolidation_surface_unavailable")
        next_actions.append("restore parallel consolidation reads before relying on consolidation audit output")

    if cycle_cost_summary["rising_without_closure"]:
        diagnostics.append("cycle_cost_rising_without_closure")
        next_actions.append("reduce scope or replan before adding more actions to a cycle that is not closing")

    if recent_events_for_display and not recent_events_error:
        if consolidation_error:
            sanitized_recent_events = recent_events_for_display
        else:
            try:
                sanitized_recent_events = _sanitize_recent_events_for_display(
                    store,
                    recent_events_for_display,
                    consolidation_head_map,
                )
            except StateStoreError as exc:
                sanitized_recent_events = ()
                recent_events_error = f"failed to sanitize runtime event log: {exc}"
                diagnostics.append("runtime_event_log_unavailable")
                next_actions.append("inspect the runtime event log path and restore recent-event reads")
    else:
        sanitized_recent_events = recent_events_for_display

    selected = None
    if agent_runtime["plan"]["current_task_id"]:
        selected = next(
            (
                item
                for item in task_assessments
                if item["id"] == agent_runtime["plan"]["current_task_id"]
            ),
            None,
        )

    if selection_consistency:
        decision_replay = {
            "status": selection_consistency["status"],
            "current_task_id": selection_consistency["current_task_id"],
            "derived_task_id": selection_consistency["derived_task_id"],
            "reason": selection_consistency["reason"],
            "priority_gap": selection_consistency["priority_gap"],
        }
    elif selection_consistency_error:
        decision_replay = {
            "status": "unavailable",
            "current_task_id": None,
            "derived_task_id": None,
            "reason": selection_consistency_error,
            "priority_gap": None,
        }
    else:
        decision_replay = {
            "status": "not_available",
            "current_task_id": None,
            "derived_task_id": None,
            "reason": "selection replay not available",
            "priority_gap": None,
        }

    if selected is not None:
        task_decision = {
            "selected_task_id": selected["id"],
            "workload_mode": selected["workload_mode"],
            "work_unit_kind": selected["work_unit_kind"],
            "decision_basis": {
                "impact": selected["impact"],
                "cost": selected["cost"],
                "risk": selected["risk"],
                "priority": selected["priority"],
            },
            "evidence": list(selected["evidence"][:3]),
            "evidence_event_ids": list(selected.get("evidence_event_ids", [])[:5]),
        }
    else:
        task_decision = {
            "selected_task_id": None,
            "workload_mode": None,
            "work_unit_kind": None,
            "decision_basis": None,
            "evidence": [],
            "evidence_event_ids": [],
            "reason": "no executable task is available from the current runtime state",
        }

    recent_notes = sorted(notes, key=lambda note: note["updated_at"], reverse=True)[:5]

    return {
        "schema_version": "1",
        "export_kind": "status",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": {
                "result": validation.result,
                "basis": "persisted canonical record only; exports do not rerun validate",
                "risk": validation_risk_level(validation.result, validation.details),
                "validated_at": validation.validated_at,
                "details": [{"code": detail.code} for detail in validation.details],
            },
            "session_file": session_file_presence(store),
            "sources_count": len(snapshot.sources),
            "updated_at": snapshot.checkpoint.updated_at,
            "runtime": {
                "plan_status": plan_status,
                "current_task_id": current_task_id,
                "tasks_total": len(tasks),
                "task_counts": task_counts,
                "registered_commands": command_count,
                "actions_recorded": action_count,
                "pending_approvals": pending_approval_count,
                "pending_verification_actions": pending_verification_count,
                "memory_notes": memory_note_count,
                "parallel_consolidations": consolidation_count,
                "workload_modes": workload_counts,
            },
            "trace": dict(trace_observability),
            "runtime_diagnostics": diagnostics,
            "recommended_next_actions": next_actions,
            "cycle_cost": dict(cycle_cost_summary),
            "prioritized_tasks": list(task_assessments[:5]),
            "task_decision": task_decision,
            "decision_replay": decision_replay,
            "flow_control": {
                "approval_lines": approval_lines,
                "batch_lines": batch_lines,
            },
            "recent_memory_notes": [
                {
                    "kind": note["kind"],
                    "summary": note["summary"],
                    "source": note["source"],
                    "updated_at": note["updated_at"],
                }
                for note in recent_notes
            ],
            "parallel_consolidations": list(consolidations),
            "recent_runtime_events": list(sanitized_recent_events),
            "surface_errors": {
                "recent_events_error": recent_events_error or None,
                "task_assessments_error": task_assessments_error or None,
                "selection_consistency_error": selection_consistency_error or None,
                "consolidation_error": consolidation_error or None,
                "task_profiles_error": task_profiles_error or None,
            },
        },
    }


def export_status_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact operational status panel from the current snapshot."""
    store, snapshot, agent_runtime = read_snapshot_and_runtime(root, StatusExportError)
    recent_events_error = ""
    task_assessments_error = ""
    selection_consistency_error = ""
    consolidation_error = ""
    task_profiles_error = ""
    recent_events: tuple[dict, ...] = ()
    recent_events_for_display: tuple[dict, ...] = ()
    current_plan_recent_events: tuple[dict, ...] = ()
    trace_observability = store.read_trace_observability(agent_runtime=agent_runtime)
    trace_status_degraded = trace_observability["trace_status"] != "healthy"
    trace_integrity_partial = trace_observability["trace_integrity"] != "reliable"
    trace_partial = trace_status_degraded or trace_integrity_partial

    try:
        recent_events = _load_recent_events(store)
        recent_events_for_display = recent_events[-5:]
        current_plan_recent_events = _events_since_latest_plan_update(recent_events)
    except StatusExportError as exc:
        recent_events = ()
        recent_events_for_display = ()
        current_plan_recent_events = ()
        recent_events_error = str(exc)
    sanitized_recent_events = ()

    try:
        consolidations, consolidation_head_map = _load_parallel_consolidation_view(store, recent_events_for_display)
    except StatusExportError as exc:
        consolidations = ()
        consolidation_head_map = {}
        consolidation_error = str(exc)

    try:
        task_assessments = _load_task_assessments(
            store,
            agent_runtime,
            current_plan_recent_events if not recent_events_error else (),
        )
    except StatusExportError as exc:
        task_assessments = ()
        task_assessments_error = str(exc)

    if task_assessments_error:
        selection_consistency = {}
        selection_consistency_error = "task assessment surface unavailable"
    else:
        try:
            selection_consistency = _load_task_selection_consistency(
                store,
                agent_runtime,
                current_plan_recent_events if not recent_events_error else (),
                task_assessments,
            )
        except StatusExportError as exc:
            selection_consistency = {}
            selection_consistency_error = str(exc)

    try:
        task_profiles = _load_task_work_profiles(store, agent_runtime)
    except StatusExportError as exc:
        task_profiles = ()
        task_profiles_error = str(exc)

    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    tasks = []
    task_counts = {
        "ready": 0,
        "blocked": 0,
        "running": 0,
        "done": 0,
        "failed": 0,
    }
    approvals = []
    notes = []
    diagnostics: list[str] = []
    next_actions: list[str] = []
    workload_counts = {"light": 0, "moderate": 0, "heavy": 0}
    approval_lines: list[str] = []
    batch_lines: list[str] = []
    cycle_cost_summary = {
        "actions_total": 0,
        "actions_applied": 0,
        "actions_failed": 0,
        "actions_blocked": 0,
        "actions_rolled_back": 0,
        "tasks_completed": 0,
        "tasks_terminal": 0,
        "tasks_active": 0,
        "actions_per_completed_task": None,
        "recent_verification_failures": 0,
        "recent_retry_blocked": 0,
        "recent_apply_blocked": 0,
        "recent_verify_blocked": 0,
        "rising_without_closure": False,
    }
    current_task_id = "none"
    plan_status = "unavailable"
    command_count = "unavailable"
    action_count = "unavailable"
    pending_approval_count = "unavailable"
    pending_verification_count = "unavailable"
    memory_note_count = "unavailable"
    consolidation_count = "unavailable"

    tasks = [
        task
        for task in agent_runtime["plan"]["tasks"]
        if isinstance(task, dict)
    ]
    task_counts = _task_counts(tasks)
    approvals = [
        approval
        for approval in agent_runtime["approvals"]["items"]
        if isinstance(approval, dict)
    ]
    notes = [
        note
        for note in agent_runtime["memory"]["notes"]
        if isinstance(note, dict)
    ]
    task_profiles_by_id = {
        profile["id"]: profile
        for profile in task_profiles
        if isinstance(profile, dict) and isinstance(profile.get("id"), str) and profile.get("id")
    }
    workload_counts = _workload_counts(task_profiles)
    diagnostics, next_actions = _runtime_diagnostics(agent_runtime, current_plan_recent_events if not trace_partial else (), task_profiles_by_id)
    approval_lines, batch_lines = _recent_flow_control(agent_runtime)
    cycle_cost_summary = _cycle_cost_summary(agent_runtime, current_plan_recent_events if not trace_partial else (), task_counts)
    current_task_id = agent_runtime["plan"]["current_task_id"] or "none"
    plan_status = agent_runtime["plan"]["status"]
    command_count = len(agent_runtime["command_registry"]["commands"])
    action_count = len(agent_runtime["actions"])
    pending_approval_count = len([approval for approval in approvals if approval["status"] == "pending"])
    pending_verification_count = len(agent_runtime["verification"]["pending_action_ids"])
    memory_note_count = len(notes)
    consolidation_count = len(consolidations)

    if trace_status_degraded:
        diagnostics.append("trace_degraded")
        next_actions.append("restore trace append health before relying on event-derived diagnostics or cycle pressure")

    if trace_integrity_partial:
        diagnostics.append("trace_integrity_partial")
        next_actions.append("treat event-derived diagnostics as partial until a fresh trace thread restores analytical confidence")

    if trace_partial:
        diagnostics.append("runtime_diagnostics_partial")

    if recent_events_error:
        diagnostics.append("runtime_event_log_unavailable")
        next_actions.append("inspect the runtime event log path and restore recent-event reads")

    if task_assessments_error:
        diagnostics.append("task_assessment_surface_unavailable")
        next_actions.append("restore task assessment derivation before relying on prioritized execution guidance")

    if selection_consistency_error:
        diagnostics.append("task_selection_replay_unavailable")
        next_actions.append("restore task-selection replay before relying on decision-consistency diagnostics")
    elif selection_consistency.get("status") == "mismatch":
        diagnostics.append("task_selection_replay_mismatch")
        next_actions.append("refresh current_task_id from the current decision surface before relying on execution guidance")

    if task_profiles_error:
        diagnostics.append("task_profile_surface_unavailable")
        next_actions.append("restore derived work-profile reads before relying on lightweight versus governed diagnostics")

    if consolidation_error:
        diagnostics.append("parallel_consolidation_surface_unavailable")
        next_actions.append("restore parallel consolidation reads before relying on consolidation audit output")

    if cycle_cost_summary["rising_without_closure"]:
        diagnostics.append("cycle_cost_rising_without_closure")
        next_actions.append("reduce scope or replan before adding more actions to a cycle that is not closing")

    if recent_events_for_display and not recent_events_error:
        if consolidation_error:
            sanitized_recent_events = recent_events_for_display
        else:
            try:
                sanitized_recent_events = _sanitize_recent_events_for_display(
                    store,
                    recent_events_for_display,
                    consolidation_head_map,
                )
            except StateStoreError as exc:
                sanitized_recent_events = ()
                recent_events_error = f"failed to sanitize runtime event log: {exc}"
                diagnostics.append("runtime_event_log_unavailable")
                next_actions.append("inspect the runtime event log path and restore recent-event reads")
    else:
        sanitized_recent_events = recent_events_for_display

    lines = [
        "# Status",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        validation_basis_line(),
        f"- Risk: {validation_risk_level(validation.result, validation.details)}",
        f"- Session file: {session_file_presence(store)}",
        f"- Sources: {len(snapshot.sources)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {snapshot.checkpoint.updated_at}",
    ]

    if validation.validated_at:
        lines.append(f"- Validated at: {validation.validated_at}")

    lines.extend(
        [
            "",
            "## Runtime",
            f"- Plan status: {plan_status}",
            f"- Current task id: {current_task_id}",
            f"- Tasks: {len(tasks)}",
            f"- Task counts: ready={task_counts['ready']}, blocked={task_counts['blocked']}, running={task_counts['running']}, done={task_counts['done']}, failed={task_counts['failed']}",
            f"- Registered commands: {command_count}",
            f"- Actions recorded: {action_count}",
            f"- Pending approvals: {pending_approval_count}",
            f"- Pending verification actions: {pending_verification_count}",
            f"- Memory notes: {memory_note_count}",
            f"- Parallel consolidations: {consolidation_count}",
            f"- Workload modes: light={workload_counts['light']}, moderate={workload_counts['moderate']}, heavy={workload_counts['heavy']}",
            f"- Trace status: {trace_observability['trace_status']}",
            f"- Trace integrity: {trace_observability['trace_integrity']}",
            f"- Trace durability: {trace_observability['durability_mode']}",
        ]
    )
    lines.extend(["", "## Runtime Diagnostics"])
    if diagnostics:
        for diagnostic in diagnostics:
            lines.append(f"- {diagnostic}")
    else:
        lines.append("- runtime_consistent")

    lines.extend(["", "## Recommended Next Actions"])
    if next_actions:
        for action in next_actions:
            lines.append(f"- {action}")
    else:
        lines.append("- no_runtime_adjustment_needed")

    ratio = cycle_cost_summary["actions_per_completed_task"]
    ratio_text = "n/a (no completed tasks yet)" if ratio is None else f"{ratio:.2f}"
    recent_failure_pressure = (
        "n/a (trace partial)"
        if trace_partial
        else (
            "verification_failed="
            f"{cycle_cost_summary['recent_verification_failures']}, "
            f"retry_blocked={cycle_cost_summary['recent_retry_blocked']}, "
            f"apply_blocked={cycle_cost_summary['recent_apply_blocked']}, "
            f"verify_blocked={cycle_cost_summary['recent_verify_blocked']}"
        )
    )
    lines.extend(
        [
            "",
            "## Cycle Cost",
            (
                "- Actions: "
                f"total={cycle_cost_summary['actions_total']}, "
                f"applied={cycle_cost_summary['actions_applied']}, "
                f"failed={cycle_cost_summary['actions_failed']}, "
                f"blocked={cycle_cost_summary['actions_blocked']}, "
                f"rolled_back={cycle_cost_summary['actions_rolled_back']}"
            ),
            (
                "- Task closures: "
                f"completed={cycle_cost_summary['tasks_completed']}, "
                f"terminal={cycle_cost_summary['tasks_terminal']}, "
                f"active={cycle_cost_summary['tasks_active']}"
            ),
            f"- Actions per completed task: {ratio_text}",
            (
                "- Recent failure pressure: "
                f"{recent_failure_pressure}"
            ),
        ]
    )

    lines.extend(["", "## Prioritized Tasks"])
    if task_assessments:
        for assessment in task_assessments[:5]:
            lines.append(
                f"- {assessment['id']}: status={assessment['status']}, mode={assessment['workload_mode']}, unit={assessment['work_unit_kind']}, priority={assessment['priority']}, impact={assessment['impact']}, cost={assessment['cost']}, risk={assessment['risk']}"
            )
            if assessment["evidence"]:
                lines.append(f"  evidence: {assessment['evidence'][0]}")
            if assessment.get("evidence_event_ids"):
                lines.append(f"  evidence events: {', '.join(assessment['evidence_event_ids'][:3])}")
    elif task_assessments_error:
        lines.append("- task_assessments_unavailable")
    else:
        lines.append("- no_task_assessments_available")

    selected = None
    if agent_runtime is not None and agent_runtime["plan"]["current_task_id"]:
        selected = next(
            (
                item
                for item in task_assessments
                if item["id"] == agent_runtime["plan"]["current_task_id"]
            ),
            None,
        )

    lines.extend(["", "## Task Decision"])
    if selected is not None:
        lines.extend(
            [
                f"- Selected task: {selected['id']}",
                f"- Work profile: mode={selected['workload_mode']}, unit={selected['work_unit_kind']}",
                f"- Decision basis: impact={selected['impact']}, cost={selected['cost']}, risk={selected['risk']}, priority={selected['priority']}",
            ]
        )
        for evidence in selected["evidence"][:3]:
            lines.append(f"- Evidence: {evidence}")
        if selected.get("evidence_event_ids"):
            lines.append(f"- Evidence events: {', '.join(selected['evidence_event_ids'][:5])}")
    else:
        lines.extend(
            [
                "- Selected task: none",
                "- Decision basis: no executable task is available from the current runtime state",
            ]
        )

    lines.extend(["", "## Decision Replay"])
    if selection_consistency:
        lines.extend(
            [
                f"- Replay status: {selection_consistency['status']}",
                f"- Current task id: {selection_consistency['current_task_id'] or 'none'}",
                f"- Derived task id: {selection_consistency['derived_task_id'] or 'none'}",
                f"- Reason: {selection_consistency['reason']}",
            ]
        )
        if selection_consistency["priority_gap"]:
            lines.append(f"- Priority gap: {selection_consistency['priority_gap']}")
    elif selection_consistency_error:
        lines.append("- selection_replay_unavailable")
    else:
        lines.append("- selection_replay_not_available")

    lines.extend(["", "## Flow Control"])
    if approval_lines or batch_lines:
        for line in approval_lines:
            lines.append(f"- {line}")
        for line in batch_lines:
            lines.append(f"- {line}")
    else:
        lines.append("- no_active_flow_controls")

    if notes:
        lines.extend(["", "## Recent Memory Notes"])
        recent_notes = sorted(notes, key=lambda note: note["updated_at"], reverse=True)[:5]
        for note in recent_notes:
            lines.append(f"- [{note['kind']}] {note['summary']} (source={note['source']}, updated_at={note['updated_at']})")

    if consolidations:
        lines.extend(["", "## Parallel Approach Consolidations"])
        for consolidation in consolidations:
            lines.extend(_format_consolidation_line(consolidation))

    lines.extend(["", "## Recent Runtime Events"])
    if sanitized_recent_events:
        for event in sanitized_recent_events:
            lines.append(f"- {_format_event_line(event)}")
    elif recent_events_error:
        lines.append("- runtime_event_log_unavailable")
    else:
        lines.append("- no_runtime_events_recorded")

    if validation.details:
        lines.extend(
            [
                "",
                "## Validation Details",
            ]
        )
        for detail in validation.details:
            lines.append(f"- {detail.code}")

    return "\n".join(lines) + "\n"


def write_status_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the operational status to a non-runtime file."""
    markdown = export_status_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, StatusExportError)
