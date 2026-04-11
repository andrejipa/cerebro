"""Implementation of the import-context command."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core.state_store import StateStore, StateStoreError, StateValidationError


def run_import_context(root: Path, args) -> int:
    store = StateStore(root)

    try:
        current_sources = store.read_sources()
        new_sources = store.prepare_sources(args.files)
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([user_error("operation_failed", str(exc))])
        return 1

    current_paths = {item.path for item in current_sources}
    new_paths = {item["path"] for item in new_sources}

    added = sorted(new_paths - current_paths)
    removed = sorted(current_paths - new_paths)
    kept = sorted(current_paths & new_paths)

    print("Sources diff")
    print(f"  added: {len(added)}")
    for path in added:
        print(f"    + {path}")
    print(f"  removed: {len(removed)}")
    for path in removed:
        print(f"    - {path}")
    print(f"  kept: {len(kept)}")
    for path in kept:
        print(f"    = {path}")

    answer = input("continue? [y/N] ").strip().lower()
    if answer != "y":
        print("Cancelled")
        return 0

    try:
        store.register_sources(args.files)
        snapshot = store.read_snapshot()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([user_error("operation_failed", str(exc))])
        return 1

    print_ok(
        [
            f"sources_registered: {len(snapshot.sources)}",
            f"revision: {snapshot.revision}",
        ]
    )
    return 0
