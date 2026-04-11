"""Implementation of the init command."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core.state_store import StateStore, StateStoreError


def run_init(root: Path, args=None) -> int:
    store = StateStore(root)

    try:
        store.initialize()
    except StateStoreError as exc:
        code = "state_exists" if "already exists" in str(exc) else "operation_failed"
        print_fail([user_error(code, str(exc))])
        return 1

    print_ok(
        [
            f"instance_created: {store.cerebro_dir}",
            f"state_path: {store.state_path}",
        ]
    )
    return 0
