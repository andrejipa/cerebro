"""Implementation of the validate command."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok
from core.state_store import StateStore


def run_validate(root: Path, args=None) -> int:
    store = StateStore(root)
    result = store.validate_state()

    if result["ok"]:
        snapshot = store.read_snapshot()
        print_ok(
            [
                "validation_passed: context is structurally consistent",
                f"sources: {len(snapshot.sources)}",
                f"revision: {snapshot.revision}",
            ]
        )
        return 0

    print_fail(result["errors"])
    return 1
