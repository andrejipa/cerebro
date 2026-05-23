"""Implementation of the checkpoint command."""

from __future__ import annotations

import getpass
from pathlib import Path

from cli.commands._session_ownership import resolve_session_token
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.state_store import StateStore, StateStoreError, StateValidationError


def run_checkpoint(root: Path, args) -> int:
    store = StateStore(root)
    checkpoint_data = {
        "goal": args.goal,
        "summary": args.summary,
        "next_step": args.next_step,
        "constraints": args.constraint or [],
    }

    try:
        result = store.validate_state()
        if not result["ok"]:
            print_fail(
                [
                    user_error("checkpoint_blocked", "checkpoint blocked because validation failed"),
                    *state_store_user_errors(root, result["errors"]),
                ]
            )
            return 1

        snapshot = result["snapshot"]
        session = result.get("session")
        actor = getattr(args, "actor", None) or getpass.getuser()
        if snapshot.checkpoint.updated_at and session is None:
            print_fail(
                [
                    user_error(
                        "checkpoint_requires_active_session",
                        "checkpoint blocked because no active session is open for this round",
                    )
                ]
            )
            return 1
        if snapshot.checkpoint.updated_at and session["actor"] != actor:
            print_fail(
                [
                    user_error(
                        "checkpoint_actor_mismatch",
                        "checkpoint blocked because the active session belongs to a different actor",
                    ),
                    user_error("requested_actor", f"requested actor: {actor}"),
                    user_error("active_session_actor", f"active session actor: {session['actor']}"),
                ]
            )
            return 1

        session_closed = session is not None
        store.update_checkpoint(
            checkpoint_data,
            validated_revision=result["revision"],
            close_session_on_success=True,
            expected_session_id=session["session_id"] if session is not None else None,
            expected_session_token=resolve_session_token(args),
        )
        snapshot = store.read_snapshot()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    print_ok(
        [
            "checkpoint_updated: current checkpoint saved",
            f"revision: {snapshot.revision}",
            f"session_closed: {'yes' if session_closed else 'no'}",
        ]
    )
    return 0
