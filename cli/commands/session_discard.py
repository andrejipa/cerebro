"""Implementation of the explicit local session-discard command."""

from __future__ import annotations

from pathlib import Path

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core import StateStore, StateStoreError, StateValidationError


def run_session_discard(root: Path, args) -> int:
    """Discard the local session file without claiming uninterrupted continuity."""
    store = StateStore(root)
    try:
        result = store.discard_session(expected_session_token=resolve_session_token(args))
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    if not result["ok"] and result["status"] == "blocked":
        if result.get("reason") == "session_absent":
            message = "session discard blocked because no local session file exists"
        elif result.get("reason") == "session_token":
            message = "session discard blocked because active local session ownership was not proven"
        elif result.get("reason") == "session_validation":
            message = "session discard blocked because the local session file is not valid enough to recover safely"
        else:
            message = "session discard blocked because validation failed for reasons beyond the local session"
        print_fail(
            [
                user_error("session_discard_blocked", message),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    if not result["ok"] and result["status"] == "incomplete":
        print_fail(
            [
                user_error("session_discard_incomplete", "local session removed but validation still failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    if not result["ok"]:
        print_fail(state_store_user_errors(root, result["errors"]))
        return 1

    if result["status"] == "absent":
        print_ok(
            [
                "session_absent: no local session file found",
                "next_step: run `cerebro analyze` if you need to open continuity",
                f"revision: {result['revision']}",
            ]
        )
        return 0

    lines = [
        "session_discarded: local session file removed",
        "next_step: run `cerebro analyze` to reopen continuity explicitly",
        f"revision: {result['revision']}",
    ]
    if result.get("recovered_stale_session"):
        lines.append("continuity: stale-session block cleared; the previous continuity break remains explicit")
    else:
        lines.append("continuity: local continuity closed explicitly")
    print_ok(lines)
    return 0
