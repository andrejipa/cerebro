"""Implementation of the resume command."""

from __future__ import annotations

import getpass
from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core.state_store import StateStore, StateStoreError, StateValidationError


def run_resume(root: Path, args) -> int:
    store = StateStore(root)
    result = store.validate_state()

    if not result["ok"]:
        print_fail(
            [
                user_error("resume_blocked", "resume blocked because validation failed"),
                *result["errors"],
            ]
        )
        return 1

    actor = args.actor or getpass.getuser()

    try:
        snapshot = store.read_snapshot()
        store.open_session(actor)
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([user_error("operation_failed", str(exc))])
        return 1

    checkpoint = snapshot.checkpoint
    lines = [
        "resume_ready: checkpoint loaded and local session opened",
        f"actor: {actor}",
        f"goal: {checkpoint.goal}",
        f"summary: {checkpoint.summary}",
        f"next_step: {checkpoint.next_step}",
        f"constraints: {len(checkpoint.constraints)}",
    ]
    for item in checkpoint.constraints:
        lines.append(f"- {item}")
    lines.extend(
        [
            f"updated_at: {checkpoint.updated_at}",
            f"sources: {len(snapshot.sources)}",
        ]
    )
    print_ok(lines)
    return 0
