"""Read-only operational impact export derived from the canonical state."""

from __future__ import annotations

from pathlib import Path

from extensions._support import (
    exported_timestamp,
    read_snapshot,
    session_file_presence,
    validation_risk_level,
    write_markdown_output,
)


class ImpactExportError(Exception):
    """Raised when the impact export cannot be generated safely."""


def export_impact_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact operational impact view from the current snapshot."""
    store, snapshot = read_snapshot(root, ImpactExportError)

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)

    lines = [
        "# Impact",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        f"- Risk: {validation_risk_level(validation.result, validation.details)}",
        f"- Session file: {session_file_presence(store)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {checkpoint.updated_at}",
        "",
        "## Scope",
        f"- Goal: {checkpoint.goal}",
        f"- Next step: {checkpoint.next_step}",
        f"- Constraint count: {len(checkpoint.constraints)}",
        f"- Registered sources: {len(snapshot.sources)}",
        "",
        "## Registered Paths",
    ]

    if snapshot.sources:
        for source in snapshot.sources:
            lines.append(f"- {source.path}")
    else:
        lines.append("- none")

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


def write_impact_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the operational impact view outside runtime-owned paths."""
    markdown = export_impact_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, ImpactExportError)
