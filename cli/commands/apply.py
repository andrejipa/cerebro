"""Implementation of the alpha-runtime apply command."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.action_runtime import (
    ActionRuntimeError,
    TRANSACTIONAL_BATCH_ACTION_KINDS,
    apply_action,
    compute_action_fingerprint,
    compute_exec_command_signature,
    execute_apply_cycle,
    guarded_apply_batch,
    load_action_payload,
    normalize_action_payload,
    preflight_apply_batch,
)
from core.agent_runtime import action_belongs_to_current_plan, build_command_registry_map
from core.decision_runtime import derive_task_assessments
from core.discipline_runtime import evaluate_action_effectiveness, evaluate_retry_discipline
from core.execution_policy import ExecutionPolicyError, action_requires_approval, ensure_mutation_path_allowed
from core.state_store import StateStore, StateStoreError, StateValidationError


def _iter_action_files(raw_action_file: object) -> list[str]:
    if isinstance(raw_action_file, str):
        return [raw_action_file]
    if isinstance(raw_action_file, list):
        return [item for item in raw_action_file if isinstance(item, str) and item]
    return []


def _resolve_action_file(root: Path, store: StateStore, raw_action_file: str) -> Path:
    action_file = Path(raw_action_file)
    if not action_file.is_absolute():
        action_file = (root / action_file).resolve()
    if store.is_runtime_path(action_file):
        raise ActionRuntimeError(f"action file cannot be loaded from runtime-owned paths: {action_file}")
    return action_file


def _select_task(agent_runtime: dict, requested_task_id: str) -> str:
    tasks = agent_runtime["plan"]["tasks"]
    if not tasks:
        return ""
    selected_task_id = requested_task_id or agent_runtime["plan"]["current_task_id"]
    if not selected_task_id:
        raise ActionRuntimeError("plan has tasks but no current_task_id is available for apply")
    for task in tasks:
        if not isinstance(task, dict) or task.get("id") != selected_task_id:
            continue
        if task["status"] not in {"ready", "running"}:
            raise ActionRuntimeError(f"task is not executable in its current status: {selected_task_id} ({task['status']})")
        return selected_task_id
    raise ActionRuntimeError(f"unknown task id: {selected_task_id}")


def _task_assessment_by_id(agent_runtime: dict) -> dict[str, dict]:
    return {
        item["id"]: item
        for item in derive_task_assessments(agent_runtime)
        if isinstance(item, dict) and isinstance(item.get("id"), str)
    }


def _executable_task_ids(agent_runtime: dict) -> tuple[str, ...]:
    task_ids: list[str] = []
    for task in agent_runtime["plan"]["tasks"]:
        if not isinstance(task, dict):
            continue
        task_id = task.get("id")
        if not isinstance(task_id, str) or not task_id:
            continue
        if task.get("status") in {"ready", "running"}:
            task_ids.append(task_id)
    return tuple(task_ids)


def _find_matching_approval(agent_runtime: dict, fingerprint: str, task_id: str) -> dict | None:
    executable_task_ids = _executable_task_ids(agent_runtime)
    for approval in reversed(agent_runtime["approvals"]["items"]):
        if not isinstance(approval, dict):
            continue
        if approval.get("fingerprint") != fingerprint:
            continue
        approval_task_id = approval.get("task_id")
        if isinstance(approval_task_id, str) and approval_task_id == task_id:
            return approval
        if (
            (not isinstance(approval_task_id, str) or not approval_task_id)
            and len(executable_task_ids) == 1
            and executable_task_ids[0] == task_id
        ):
            return approval
    return None


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _build_pending_approval(agent_runtime: dict, fingerprint: str, normalized_action: dict, target: str, task_id: str) -> dict:
    existing_ids = {
        approval["id"]
        for approval in agent_runtime["approvals"]["items"]
        if isinstance(approval, dict) and isinstance(approval.get("id"), str)
    }
    counter = 1
    approval_id = f"apr-{counter:03d}"
    while approval_id in existing_ids:
        counter += 1
        approval_id = f"apr-{counter:03d}"
    return {
        "id": approval_id,
        "status": "pending",
        "fingerprint": fingerprint,
        "action_kind": normalized_action["kind"],
        "task_id": task_id,
        "target": target,
        "reason": "policy requires approval before executing this action",
        "requested_at": _timestamp_now(),
        "resolved_at": "",
    }


def _approval_target(normalized_action: dict) -> str:
    for field in ("path", "to", "command_id"):
        value = normalized_action.get(field)
        if isinstance(value, str) and value:
            return value
    return normalized_action["kind"]


def _resolve_projected_workspace_path(root: Path, raw_path: str) -> Path:
    return (root / raw_path).resolve()


def _precheck_action_policy_boundaries(root: Path, agent_runtime: dict, normalized_action: dict, registered_paths: set[str]) -> None:
    """Reject impossible workspace mutations before approval prompts are considered."""
    policy = agent_runtime["execution_policy"]
    protected_paths = policy["protected_paths"]

    if normalized_action["kind"] == "fs.create_file":
        ensure_mutation_path_allowed(
            root,
            _resolve_projected_workspace_path(root, normalized_action["path"]),
            protected_paths,
            registered_paths,
        )
        return
    if normalized_action["kind"] == "fs.move":
        ensure_mutation_path_allowed(
            root,
            _resolve_projected_workspace_path(root, normalized_action["from"]),
            protected_paths,
            registered_paths,
        )
        ensure_mutation_path_allowed(
            root,
            _resolve_projected_workspace_path(root, normalized_action["to"]),
            protected_paths,
            registered_paths,
        )
        return
    if normalized_action["kind"] in {"fs.delete_soft", "fs.write_patch"}:
        ensure_mutation_path_allowed(
            root,
            _resolve_projected_workspace_path(root, normalized_action["path"]),
            protected_paths,
            registered_paths,
        )


def _projected_target_exists(root: Path, normalized_action: dict, projected_exists: dict[Path, bool]) -> bool | None:
    kind = normalized_action["kind"]
    if kind == "fs.create_file":
        target = _resolve_projected_workspace_path(root, normalized_action["path"])
    elif kind == "fs.move":
        target = _resolve_projected_workspace_path(root, normalized_action["to"])
    else:
        return None
    return projected_exists.get(target, target.exists())


def _update_projected_workspace_state(root: Path, normalized_action: dict, projected_exists: dict[Path, bool]) -> None:
    kind = normalized_action["kind"]
    if kind == "fs.create_file":
        projected_exists[_resolve_projected_workspace_path(root, normalized_action["path"])] = True
        return
    if kind == "fs.move":
        projected_exists[_resolve_projected_workspace_path(root, normalized_action["from"])] = False
        projected_exists[_resolve_projected_workspace_path(root, normalized_action["to"])] = True
        return
    if kind == "fs.delete_soft":
        projected_exists[_resolve_projected_workspace_path(root, normalized_action["path"])] = False


def _resolve_action_approval(
    store: StateStore,
    agent_runtime: dict,
    fingerprint: str,
    normalized_action: dict,
    task_id: str,
    validated_revision: int,
    expected_session_token: str | None,
    *,
    target_exists: bool | None,
) -> tuple[str, int, list[str] | None]:
    """Return approval metadata or user-facing block lines when execution cannot proceed."""
    if not action_requires_approval(
        normalized_action,
        agent_runtime["execution_policy"]["approval_required_kinds"],
        target_exists=target_exists,
    ):
        return "", validated_revision, None

    approval = _find_matching_approval(agent_runtime, fingerprint, task_id)
    if approval is None:
        approval = _build_pending_approval(
            agent_runtime,
            fingerprint,
            normalized_action,
            _approval_target(normalized_action),
            task_id,
        )
        updated = store.update_agent_approval(
            approval,
            validated_revision=validated_revision,
            expected_session_token=expected_session_token,
        )
        return (
            "",
            updated["revision"],
            [
                user_error("approval_required", f"approval requested before executing action: {approval['id']}"),
                user_error("approval_target", approval["target"]),
                user_error("approval_reason", approval["reason"]),
                user_error("next_step", f"run `cerebro approve --approval-id {approval['id']} --decision approved`"),
            ],
        )
    if approval["status"] == "pending":
        return (
            "",
            validated_revision,
            [
                user_error("approval_required", f"action is waiting for approval: {approval['id']}"),
                user_error("approval_target", approval["target"]),
            ],
        )
    if approval["status"] == "rejected":
        return "", validated_revision, [user_error("approval_rejected", f"approval rejected for action: {approval['id']}")]
    return approval["id"], validated_revision, None


def _sync_ephemeral_runtime_after_apply(agent_runtime: dict, action_record: dict) -> None:
    """Mirror enough runtime state locally so later actions in the same CLI batch see prior effects."""
    actions = [
        item
        for item in agent_runtime.get("actions", [])
        if isinstance(item, dict) and item.get("id") != action_record["id"]
    ]
    actions.append(action_record)
    agent_runtime["actions"] = actions

    verification = agent_runtime.get("verification", {})
    pending_action_ids = verification.get("pending_action_ids", [])
    if not isinstance(pending_action_ids, list):
        pending_action_ids = []
    pending_action_ids = [item for item in pending_action_ids if item != action_record["id"]]
    if action_record["status"] == "applied" and action_record["kind"].startswith("fs."):
        pending_action_ids.append(action_record["id"])
        verification["status"] = "idle"
        verification["checks"] = []
        verification["last_run_at"] = ""
    verification["pending_action_ids"] = pending_action_ids


def _ensure_batch_id_is_fresh(agent_runtime: dict, batch_id: str) -> None:
    """Reject attempts to extend one existing canonical batch across later apply invocations."""
    if not isinstance(batch_id, str) or not batch_id:
        return
    batch_registry = agent_runtime.get("batch_registry", {})
    used_batch_ids = batch_registry.get("used_ids", []) if isinstance(batch_registry, dict) else []
    if isinstance(used_batch_ids, list) and batch_id in used_batch_ids:
        raise ActionRuntimeError(f"batch_id is already bound to a previous apply invocation: {batch_id}")
    for action in agent_runtime.get("actions", []):
        if not isinstance(action, dict):
            continue
        if not action_belongs_to_current_plan(agent_runtime, action):
            continue
        if action.get("batch_id") != batch_id:
            continue
        raise ActionRuntimeError(f"batch_id is already bound to a previous apply invocation: {batch_id}")


def run_apply(root: Path, args) -> int:
    """Load and execute one or more typed action payloads."""
    store = StateStore(root)
    try:
        result = store.validate_state()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    if not result["ok"]:
        print_fail(
            [
                user_error("apply_blocked", "apply blocked because validation failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    try:
        action_files = _iter_action_files(getattr(args, "action_file", ""))
        if not action_files:
            raise ActionRuntimeError("at least one --action-file must be provided")

        batch_id = getattr(args, "batch_id", "") or (f"batch-{uuid4().hex[:8]}" if len(action_files) > 1 else "")
        multi_file_batch = len(action_files) > 1
        requested_task_id = getattr(args, "task_id", "") or ""
        retry_justification = getattr(args, "retry_justification", "") or ""
        completed_actions: list[dict] = []
        validated_revision = result["revision"]
        expected_session_token = resolve_session_token(args)
        updated: dict | None = None
        planning_snapshot, planning_runtime = store.read_snapshot_and_runtime()
        registered_paths = {item.path for item in planning_snapshot.sources}
        _ensure_batch_id_is_fresh(planning_runtime, batch_id)
        planned_actions: list[dict] = []
        projected_exists: dict[Path, bool] = {}

        for raw_action_file in action_files:
            action_file = _resolve_action_file(root, store, raw_action_file)
            payload = load_action_payload(action_file)
            normalized_action = normalize_action_payload(payload)
            if multi_file_batch and normalized_action["kind"] not in TRANSACTIONAL_BATCH_ACTION_KINDS:
                raise ActionRuntimeError(
                    f"multi-file apply batches currently support only filesystem action kinds: {normalized_action['kind']}"
                )
            agent_runtime = planning_runtime
            if agent_runtime["verification"]["status"] == "failed":
                raise ActionRuntimeError("verification is failed; rerun verify successfully before applying more changes")
            command_registry = build_command_registry_map(agent_runtime)
            if (
                normalized_action["kind"] == "exec.command"
                and normalized_action["command_id"] not in command_registry
            ):
                raise ActionRuntimeError(f"unknown command_id: {normalized_action['command_id']}")
            task_id = _select_task(agent_runtime, requested_task_id)
            assessments = _task_assessment_by_id(agent_runtime)
            task_assessment = assessments.get(task_id, {})
            if (
                isinstance(task_assessment, dict)
                and task_assessment.get("status") in {"ready", "running"}
                and not task_assessment.get("executable", True)
            ):
                raise ActionRuntimeError(f"task is blocked by current runtime discipline: {task_id}")
            _precheck_action_policy_boundaries(root, agent_runtime, normalized_action, registered_paths)
            fingerprint = compute_action_fingerprint(payload, command_registry=command_registry)
            effectiveness = evaluate_action_effectiveness(root, normalized_action)
            if not effectiveness["allowed"]:
                store.record_runtime_event(
                    {
                        "event": "apply_blocked",
                        "phase": "apply",
                        "step": "apply_blocked",
                        "task_id": task_id,
                        "action_kind": normalized_action["kind"],
                        "fingerprint": fingerprint,
                        "reason_code": effectiveness["reason_code"],
                        "reason": effectiveness["reason"],
                        "wasted_cost": 5,
                    }
                )
                raise ActionRuntimeError(effectiveness["reason"])
            discipline = evaluate_retry_discipline(
                root,
                normalized_action,
                fingerprint,
                agent_runtime,
                task_id,
                retry_justification,
            )
            if not discipline["allowed"]:
                store.record_runtime_event(
                    {
                        "event": "retry_blocked",
                        "phase": "apply",
                        "step": "retry_blocked",
                        "task_id": task_id,
                        "action_kind": normalized_action["kind"],
                        "fingerprint": fingerprint,
                        "reason_code": discipline["reason_code"],
                        "reason": discipline["reason"],
                        "recent_history": discipline["recent_history"],
                        "blocked_retry_count": discipline["blocked_retry_count"],
                        "wasted_cost": max(1, discipline["redundant_attempts"]) * 10,
                    }
                )
                raise ActionRuntimeError(discipline["reason"])
            target_exists = _projected_target_exists(root, normalized_action, projected_exists)
            approval_id, validated_revision, blocked_lines = _resolve_action_approval(
                store,
                agent_runtime,
                fingerprint,
                normalized_action,
                task_id,
                validated_revision,
                expected_session_token,
                target_exists=target_exists,
            )
            if blocked_lines is not None:
                print_fail(blocked_lines)
                return 1
            _update_projected_workspace_state(root, normalized_action, projected_exists)

            plan_entry = {
                "payload": payload,
                "normalized_action": normalized_action,
                "task_id": task_id,
                "approval_id": approval_id,
                "fingerprint": fingerprint,
                "discipline": discipline,
                "command_registry": command_registry,
            }
            if multi_file_batch:
                planned_actions.append(plan_entry)
                continue

            detail_updates: dict[str, object] = {
                "fingerprint": fingerprint,
                "evidence_token": discipline["evidence_token"],
                "retry_justification": retry_justification.strip(),
                "redundant_attempts_before_apply": discipline["redundant_attempts"],
                "recent_history": discipline["recent_history"],
            }
            if normalized_action["kind"] == "exec.command":
                detail_updates["command_signature"] = compute_exec_command_signature(
                    command_registry,
                    normalized_action["command_id"],
                )
            action_record, updated = execute_apply_cycle(
                root,
                store,
                payload,
                command_registry,
                registered_paths,
                task_id=task_id,
                batch_id=batch_id,
                approval_id=approval_id,
                expected_session_token=expected_session_token,
                detail_updates=detail_updates,
            )
            validated_revision = updated["revision"]
            completed_actions.append(action_record)

        if multi_file_batch:
            preflight_apply_batch(
                root,
                store,
                planning_runtime,
                [
                    {
                        **item,
                        "batch_id": batch_id,
                    }
                    for item in planned_actions
                ],
                planned_actions[0]["command_registry"] if planned_actions else {},
                registered_paths,
            )
            working_runtime = planning_runtime
            with guarded_apply_batch(
                root,
                store,
                [item["normalized_action"] for item in planned_actions],
            ):
                for plan_entry in planned_actions:
                    action_record = apply_action(
                        root,
                        store,
                        working_runtime,
                        plan_entry["payload"],
                        plan_entry["command_registry"],
                        registered_paths,
                        task_id=plan_entry["task_id"],
                        batch_id=batch_id,
                        approval_id=plan_entry["approval_id"],
                    )
                    action_record["details"]["fingerprint"] = plan_entry["fingerprint"]
                    action_record["details"]["evidence_token"] = plan_entry["discipline"]["evidence_token"]
                    action_record["details"]["retry_justification"] = retry_justification.strip()
                    action_record["details"]["redundant_attempts_before_apply"] = plan_entry["discipline"][
                        "redundant_attempts"
                    ]
                    action_record["details"]["recent_history"] = plan_entry["discipline"]["recent_history"]
                    completed_actions.append(action_record)
                    _sync_ephemeral_runtime_after_apply(working_runtime, action_record)
                updated = store.record_agent_actions(
                    completed_actions,
                    validated_revision=validated_revision,
                    expected_session_token=expected_session_token,
                )
                validated_revision = updated["revision"]
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except (ActionRuntimeError, ExecutionPolicyError) as exc:
        print_fail([user_error("action_rejected", str(exc))])
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    lines = [
        f"actions_applied: {len(completed_actions)}",
        f"revision: {updated['revision']}",
    ]
    if batch_id:
        lines.append(f"batch_id: {batch_id}")
    for action_record in completed_actions:
        lines.append(f"- {action_record['id']}: {action_record['kind']} -> {action_record['status']}")
    if any(action_record["status"] == "failed" for action_record in completed_actions):
        print_fail(
            [
                user_error("action_failed", "one or more actions finished with failure status"),
                *[user_error(action["id"], action["target"]) for action in completed_actions if action["status"] == "failed"],
            ]
        )
        return 1
    print_ok(lines)
    return 0
