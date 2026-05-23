"""Implementation of the alpha-runtime approve command."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.state_store import StateStore, StateStoreError, StateValidationError


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def run_approve(root: Path, args) -> int:
    """Resolve one pending approval as approved or rejected."""
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
                user_error("approve_blocked", "approve blocked because validation failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    try:
        agent_runtime = store.read_agent_runtime()
        approval = next(
            (
                item
                for item in agent_runtime["approvals"]["items"]
                if isinstance(item, dict) and item.get("id") == args.approval_id
            ),
            None,
        )
        if approval is None:
            raise StateStoreError(f"unknown approval id: {args.approval_id}")
        if approval["status"] != "pending":
            raise StateStoreError(f"approval is already resolved: {approval['id']} ({approval['status']})")
        approval = dict(approval)
        approval["status"] = args.decision
        approval["resolved_at"] = _timestamp_now()
        updated = store.update_agent_approval(
            approval,
            validated_revision=result["revision"],
            expected_session_token=resolve_session_token(args),
        )
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    print_ok(
        [
            f"approval_{approval['status']}: {approval['id']}",
            f"target: {approval['target']}",
            f"revision: {updated['revision']}",
        ]
    )
    return 0
