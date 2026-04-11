"""Implementation of the standard runtime continuity protocol."""

from __future__ import annotations

import getpass
from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core import StateStore, StateStoreError, StateValidationError


def run_analyze(root: Path, args) -> int:
    """Run the canonical continuity flow for the current project state."""
    store = StateStore(root)

    try:
        result = store.validate_state()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([user_error("operation_failed", str(exc))])
        return 1

    if not result["ok"]:
        print_fail(
            [
                user_error("analysis_blocked", "analysis blocked because validation failed"),
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
        "analysis_ready: continuity context loaded",
        f"goal: {checkpoint.goal}",
        f"summary: {checkpoint.summary}",
        f"next_step: {checkpoint.next_step}",
        f"constraints: {len(checkpoint.constraints)}",
    ]
    for item in checkpoint.constraints:
        lines.append(f"- {item}")

    lines.append(f"sources: {len(snapshot.sources)}")
    for source in snapshot.sources:
        lines.append(f"- {source.path}")

    lines.extend(
        [
            f"revision: {snapshot.revision}",
            f"updated_at: {checkpoint.updated_at}",
            f"validation: {snapshot.last_validation.result}",
        ]
    )
    print_ok(lines)
    return 0
