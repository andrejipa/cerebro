"""Implementation of the alpha-runtime rollback command."""

from __future__ import annotations

from pathlib import Path

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.action_runtime import ActionRuntimeError, guarded_rollback_batch, rollback_action
from core.agent_runtime import action_belongs_to_current_plan
from core.execution_policy import ExecutionPolicyError, required_action_approval_error
from core.state_store import StateStore, StateStoreError, StateValidationError


def _select_actions(agent_runtime: dict, action_id: str, batch_id: str) -> list[dict]:
    actions = [
        action
        for action in agent_runtime["actions"]
        if isinstance(action, dict) and action.get("status") == "applied"
    ]
    if action_id:
        return [action for action in actions if action.get("id") == action_id]
    return [
        action
        for action in actions
        if action.get("batch_id") == batch_id and action_belongs_to_current_plan(agent_runtime, action)
    ]


def _missing_target_message(agent_runtime: dict, action_id: str, batch_id: str) -> str:
    """Explain retained-history misses without elevating audit rollback points into runtime authority."""
    audit = agent_runtime.get("audit", {})
    batch_registry = agent_runtime.get("batch_registry", {})
    used_batch_ids = batch_registry.get("used_ids", []) if isinstance(batch_registry, dict) else []
    if action_id:
        actions = agent_runtime.get("actions", [])
        if isinstance(actions, list):
            for action in actions:
                if not isinstance(action, dict) or action.get("id") != action_id:
                    continue
                status = action.get("status")
                if status == "rolled_back":
                    return "requested action is already rolled_back and cannot be rolled back again"
                if isinstance(status, str) and status:
                    return f"requested action is not currently applied and cannot be rolled back from status={status}"
        rollback_points = audit.get("rollback_points", []) if isinstance(audit, dict) else []
        if isinstance(rollback_points, list) and any(
            isinstance(rollback_point, dict) and rollback_point.get("id") == action_id
            for rollback_point in rollback_points
        ):
            return (
                "requested action is no longer in retained canonical action history; "
                "audit rollback_points are historical evidence only"
            )
    if batch_id and isinstance(used_batch_ids, list) and batch_id in used_batch_ids:
        return "requested batch_id is already closed in canonical batch history and no applied actions remain under it"
    return "no applied actions matched the requested rollback target"


def _ensure_selected_actions_have_required_approval(agent_runtime: dict, selected: list[dict]) -> None:
    approvals = agent_runtime.get("approvals", {})
    approval_items = approvals.get("items", []) if isinstance(approvals, dict) else []
    approval_statuses = {
        item.get("id"): item.get("status", "")
        for item in approval_items
        if isinstance(item, dict) and isinstance(item.get("id"), str) and item.get("id")
    }
    execution_policy = agent_runtime.get("execution_policy", {})
    approval_required_kinds = (
        execution_policy.get("approval_required_kinds", [])
        if isinstance(execution_policy, dict)
        else []
    )
    for action in selected:
        if not isinstance(action, dict):
            continue
        approval_error = required_action_approval_error(
            action,
            action.get("approval_id"),
            approval_statuses,
            approval_required_kinds if isinstance(approval_required_kinds, list) else [],
        )
        if approval_error:
            raise ExecutionPolicyError(
                f"rollback requires the original action approval to remain valid: action {action.get('id', '')} {approval_error}"
            )


def run_rollback(root: Path, args) -> int:
    """Rollback one applied action or one applied batch in reverse order."""
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
                user_error("rollback_blocked", "rollback blocked because validation failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    try:
        if bool(args.action_id) == bool(args.batch_id):
            raise ActionRuntimeError("provide exactly one of --action-id or --batch-id")

        agent_runtime = store.read_agent_runtime()
        selected = _select_actions(agent_runtime, args.action_id or "", args.batch_id or "")
        if not selected:
            raise ActionRuntimeError(_missing_target_message(agent_runtime, args.action_id or "", args.batch_id or ""))
        _ensure_selected_actions_have_required_approval(agent_runtime, selected)

        registered_paths = {item.path for item in store.read_sources()}
        validated_revision = result["revision"]
        with guarded_rollback_batch(root, store, agent_runtime, selected, registered_paths) as ordered_actions:
            rolled_back = [
                rollback_action(root, store, agent_runtime, action_record, registered_paths)
                for action_record in ordered_actions
            ]
            updated = store.record_agent_actions(
                rolled_back,
                validated_revision=validated_revision,
                expected_session_token=resolve_session_token(args),
            )
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except (ActionRuntimeError, ExecutionPolicyError) as exc:
        print_fail([user_error("rollback_rejected", str(exc))])
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    print_ok(
        [
            f"actions_rolled_back: {len(rolled_back)}",
            f"revision: {updated['revision']}",
            *[f"- {action['id']}: {action['target']}" for action in rolled_back],
        ]
    )
    return 0
