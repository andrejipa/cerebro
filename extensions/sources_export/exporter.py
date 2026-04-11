"""Read-only sources export derived from the canonical state."""

from __future__ import annotations

from pathlib import Path

from extensions._support import exported_timestamp, read_snapshot, write_markdown_output


class SourcesExportError(Exception):
    """Raised when the sources export cannot be generated safely."""


def export_sources_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact inventory of canonical source paths."""
    store, snapshot = read_snapshot(root, SourcesExportError)

    exported_at_value = exported_timestamp(exported_at)
    session = "active" if store.has_active_session() else "inactive"
    primary_count = sum(1 for source in snapshot.sources if source.role == "primary")
    reference_count = sum(1 for source in snapshot.sources if source.role == "reference")

    lines = [
        "# Sources",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {snapshot.last_validation.result}",
        f"- Session: {session}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {snapshot.checkpoint.updated_at}",
        f"- Registered sources: {len(snapshot.sources)}",
        f"- Primary sources: {primary_count}",
        f"- Reference sources: {reference_count}",
        "",
        "## Registered Paths",
    ]

    if snapshot.sources:
        for source in snapshot.sources:
            lines.append(f"- {source.path} [{source.role}]")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def write_sources_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the sources inventory outside runtime-owned paths."""
    markdown = export_sources_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, SourcesExportError)
