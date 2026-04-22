"""Shared helpers for small read-only extensions.

Keep this module narrow. It exists only to remove repeated safe plumbing
across extension exporters without creating a new framework layer.
"""

from __future__ import annotations

from datetime import datetime, timezone
import os
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


def exported_timestamp(exported_at: str | None) -> str:
    """Return a stable export timestamp."""
    return exported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")


def session_file_presence(store: StateStore) -> str:
    """Return a compact label for local session-file presence only."""
    return "present" if store.has_active_session() else "absent"


def read_snapshot(root: str | Path, error_type: type[Exception]) -> tuple[StateStore, object]:
    """Load the canonical snapshot through the public API or raise a typed extension error."""
    store = StateStore(root)
    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise error_type(f"failed to read state snapshot: {exc}") from exc
    return store, snapshot


def read_snapshot_and_runtime(root: str | Path, error_type: type[Exception]) -> tuple[StateStore, object, dict]:
    """Load one coherent snapshot plus runtime block through the public API."""
    store = StateStore(root)
    try:
        snapshot, agent_runtime = store.read_snapshot_and_runtime()
    except (StateStoreError, StateValidationError) as exc:
        raise error_type(f"failed to read state snapshot: {exc}") from exc
    return store, snapshot, agent_runtime


def resolve_output_target(root: str | Path, output_path: str | Path) -> Path:
    """Resolve an explicit output path relative to the current project root."""
    root_path = Path(root).resolve()
    target = Path(output_path)
    if not target.is_absolute():
        target = root_path / target
    return target.resolve()


def reject_runtime_output_path(store: StateStore, target: Path, error_type: type[Exception]) -> None:
    """Reject writes to runtime-owned files, directories, and canonical source files."""
    if store.is_runtime_path(target):
        raise error_type(f"output path is reserved for runtime files: {target}")

    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise error_type(f"failed to read state snapshot: {exc}") from exc

    registered_source_paths = {(store.root / source.path).resolve() for source in snapshot.sources}
    if target in registered_source_paths:
        raise error_type(f"output path is reserved for registered source files: {target}")


def write_markdown_output(
    root: str | Path,
    output_path: str | Path,
    markdown: str,
    error_type: type[Exception],
) -> Path:
    """Write derived Markdown outside runtime-owned paths."""
    store = StateStore(root)
    target = resolve_output_target(root, output_path)
    reject_runtime_output_path(store, target, error_type)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        _write_text_atomic(target, markdown)
    except OSError as exc:
        raise error_type(f"failed to write output file: {target}") from exc
    return target


def _write_text_atomic(path: Path, text: str) -> None:
    """Persist derived text via write-then-replace to avoid partial outputs."""
    tmp_path = path.with_suffix(f"{path.suffix}.tmp")
    try:
        tmp_path.write_text(text, encoding="utf-8", newline="\n")
        os.replace(tmp_path, path)
    finally:
        try:
            if tmp_path.exists():
                tmp_path.unlink()
        except OSError:
            pass


def validation_risk_level(result: str, details: tuple[object, ...]) -> str:
    """Map canonical validation metadata to a compact operational risk label."""
    if result == "ok":
        return "low"

    blocking_source_codes = {
        "source_hash_mismatch",
        "source_missing",
        "source_outside_root",
    }
    detail_codes = {detail.code for detail in details}
    if detail_codes & blocking_source_codes:
        return "high"
    return "elevated"


def validation_basis_line() -> str:
    """Return the standard note that exports use persisted validation only."""
    return "- Validation basis: persisted canonical record only; exports do not rerun validate"
