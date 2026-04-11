"""Read-only operational status export derived from the canonical state."""

from __future__ import annotations

from pathlib import Path

from extensions._support import (
    exported_timestamp,
    read_snapshot,
    session_file_presence,
    validation_risk_level,
    write_markdown_output,
)


class StatusExportError(Exception):
    """Raised when the status export cannot be generated safely."""


def export_status_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact operational status panel from the current snapshot."""
    store, snapshot = read_snapshot(root, StatusExportError)

    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)

    lines = [
        "# Status",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        f"- Risk: {validation_risk_level(validation.result, validation.details)}",
        f"- Session file: {session_file_presence(store)}",
        f"- Sources: {len(snapshot.sources)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {snapshot.checkpoint.updated_at}",
    ]

    if validation.validated_at:
        lines.append(f"- Validated at: {validation.validated_at}")

    if validation.details:
        lines.extend(
            [
                "",
                "## Validation Details",
            ]
        )
        for detail in validation.details:
            lines.append(f"- {detail.code}")

    return "\n".join(lines) + "\n"


def write_status_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the operational status to a non-runtime file."""
    markdown = export_status_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, StatusExportError)
