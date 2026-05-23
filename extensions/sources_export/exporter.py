"""Read-only sources export derived from the canonical state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from extensions._support import (
    exported_timestamp,
    read_snapshot,
    session_file_presence,
    validation_basis_line,
    write_markdown_output,
)


class SourcesExportError(Exception):
    """Raised when the sources export cannot be generated safely."""


def export_sources_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured inventory of canonical source paths."""
    store, snapshot = read_snapshot(root, SourcesExportError)
    exported_at_value = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()
    primary_count = sum(1 for source in snapshot.sources if source.role == "primary")
    reference_count = sum(1 for source in snapshot.sources if source.role == "reference")

    sources: list[dict[str, object]] = []
    for source in snapshot.sources:
        source_path = (store.root / source.path).resolve()
        try:
            size_bytes: int | None = source_path.stat().st_size
        except OSError:
            size_bytes = None
        sources.append(
            {
                "path": source.path,
                "sha256": source.sha256,
                "role": source.role,
                "size_bytes": size_bytes,
            }
        )

    return {
        "schema_version": "1",
        "export_kind": "sources",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": snapshot.last_validation.result,
            "session_file": session_file_presence(store),
            "updated_at": snapshot.checkpoint.updated_at,
            "count": len(snapshot.sources),
            "primary_count": primary_count,
            "reference_count": reference_count,
            "sources": sources,
        },
    }


def export_sources_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact inventory of canonical source paths."""
    store, snapshot = read_snapshot(root, SourcesExportError)

    exported_at_value = exported_timestamp(exported_at)
    primary_count = sum(1 for source in snapshot.sources if source.role == "primary")
    reference_count = sum(1 for source in snapshot.sources if source.role == "reference")

    lines = [
        "# Sources",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {snapshot.last_validation.result}",
        validation_basis_line(),
        f"- Session file: {session_file_presence(store)}",
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
