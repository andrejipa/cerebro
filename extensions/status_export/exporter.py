"""Read-only operational status export derived from the canonical state."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


class StatusExportError(Exception):
    """Raised when the status export cannot be generated safely."""


def export_status_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact operational status panel from the current snapshot."""
    store = StateStore(root)

    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise StatusExportError(f"failed to read state snapshot: {exc}") from exc

    validation = snapshot.last_validation
    session = "active" if store.has_active_session() else "inactive"
    exported_at_value = exported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

    lines = [
        "# Status",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        f"- Risk: {_risk_level(validation.result, validation.details)}",
        f"- Session: {session}",
        f"- Sources: {len(snapshot.sources)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {snapshot.checkpoint.updated_at}",
    ]

    if validation.validated_at:
        lines.append(f"- Validated at: {validation.validated_at}")

    if validation.details:
        lines.append("- Validation details:")
        for detail in validation.details:
            lines.append(f"  - {detail.code}")

    return "\n".join(lines) + "\n"


def write_status_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the operational status to a non-runtime file."""
    store = StateStore(root)
    root_path = Path(root).resolve()
    target = Path(output_path)
    if not target.is_absolute():
        target = root_path / target
    target = target.resolve()

    if store.is_runtime_path(target):
        raise StatusExportError("refusing to write status output inside the runtime directory")

    markdown = export_status_markdown(root_path, exported_at=exported_at)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target


def _risk_level(result: str, details: tuple[object, ...]) -> str:
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
