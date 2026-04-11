"""Shared helpers for small read-only extensions.

Keep this module narrow. It exists only to remove repeated safe plumbing
across extension exporters without creating a new framework layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


def exported_timestamp(exported_at: str | None) -> str:
    """Return a stable export timestamp."""
    return exported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")


def read_snapshot(root: str | Path, error_type: type[Exception]) -> tuple[StateStore, object]:
    """Load the canonical snapshot through the public API or raise a typed extension error."""
    store = StateStore(root)
    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise error_type(f"failed to read state snapshot: {exc}") from exc
    return store, snapshot


def resolve_output_target(root: str | Path, output_path: str | Path) -> Path:
    """Resolve an explicit output path relative to the current project root."""
    root_path = Path(root).resolve()
    target = Path(output_path)
    if not target.is_absolute():
        target = root_path / target
    return target.resolve()


def reject_runtime_output_path(store: StateStore, target: Path, error_type: type[Exception]) -> None:
    """Reject writes to runtime-owned files and directories."""
    if store.is_runtime_path(target):
        raise error_type(f"output path is reserved for runtime files: {target}")
