"""Read-only handoff exporter built on top of the stable core API."""

from __future__ import annotations

from pathlib import Path

from extensions._support import exported_timestamp, read_snapshot, write_markdown_output


class HandoffExportError(Exception):
    """Raised when the handoff export cannot be generated."""


def export_handoff_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a short human-readable handoff from the canonical state."""
    _, snapshot = read_snapshot(root, HandoffExportError)
    timestamp = exported_timestamp(exported_at)
    lines = [
        "# Handoff",
        "",
        f"- Exported at: {timestamp}",
        "",
        "## Goal",
        snapshot.checkpoint.goal or "-",
        "",
        "## Summary",
        snapshot.checkpoint.summary or "-",
        "",
        "## Next Step",
        snapshot.checkpoint.next_step or "-",
        "",
        "## Constraints",
    ]

    if snapshot.checkpoint.constraints:
        for item in snapshot.checkpoint.constraints:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Sources",
            f"- Count: {len(snapshot.sources)}",
        ]
    )
    if snapshot.sources:
        for source in snapshot.sources:
            lines.append(f"- {source.path}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## State",
            f"- Revision: {snapshot.revision}",
            f"- Updated at: {snapshot.checkpoint.updated_at or '-'}",
            f"- Validation: {snapshot.last_validation.result}",
        ]
    )

    return "\n".join(lines) + "\n"


def write_handoff_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the rendered handoff to an explicit output file."""
    markdown = export_handoff_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, HandoffExportError)
