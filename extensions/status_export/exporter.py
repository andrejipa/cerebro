"""Read-only operational status export derived from the canonical state."""

from __future__ import annotations

from pathlib import Path

from core import StateStore
from extensions._support import (
    exported_timestamp,
    read_snapshot,
    reject_runtime_output_path,
    resolve_output_target,
    validation_risk_level,
)


class StatusExportError(Exception):
    """Raised when the status export cannot be generated safely."""


def export_status_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact operational status panel from the current snapshot."""
    store, snapshot = read_snapshot(root, StatusExportError)

    validation = snapshot.last_validation
    session = "active" if store.has_active_session() else "inactive"
    exported_at_value = exported_timestamp(exported_at)

    lines = [
        "# Status",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        f"- Risk: {validation_risk_level(validation.result, validation.details)}",
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
    target = resolve_output_target(root, output_path)
    reject_runtime_output_path(store, target, StatusExportError)

    markdown = export_status_markdown(root, exported_at=exported_at)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target
