"""Implementation of the checkpoint command."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
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
        store.update_checkpoint(checkpoint_data)
        snapshot = store.read_snapshot()
        session_closed = store.close_session()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([user_error("operation_failed", str(exc))])
        return 1

    print_ok(
        [
            "checkpoint_updated: current checkpoint saved",
            f"revision: {snapshot.revision}",
            f"session_closed: {'yes' if session_closed else 'no'}",
        ]
    )
    return 0
