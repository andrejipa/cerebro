"""Implementation of the standard runtime continuity protocol."""

from __future__ import annotations

import getpass
from pathlib import Path

from cli.commands._session_ownership import session_token_output_lines
from cli.output import print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
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
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    if not result["ok"]:
        print_fail(
            [
                user_error("analysis_blocked", "analysis blocked because validation failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    actor = args.actor or getpass.getuser()
    snapshot = result["snapshot"]

    try:
        session = store.open_session(actor, validated_revision=result["revision"])
    except StateValidationError as exc:
        print_fail(
            [
                user_error("analysis_blocked", "analysis blocked because continuity could not be opened"),
                *state_store_user_errors(root, exc.errors),
            ]
        )
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
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
            *session_token_output_lines(session, emit_token=bool(getattr(args, "emit_session_token", False))),
        ]
    )
    print_ok(lines)
    return 0
