"""Read-only handoff exporter built on top of the stable core API."""

from __future__ import annotations

import hashlib
from pathlib import Path

from extensions._support import exported_timestamp, read_snapshot, validation_basis_line, write_markdown_output


class HandoffExportError(Exception):
    """Raised when the handoff export cannot be generated."""


def export_handoff_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured handoff from the canonical state."""
    store, snapshot = read_snapshot(root, HandoffExportError)
    timestamp = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()

    return {
        "schema_version": "1",
        "export_kind": "handoff",
        "exported_at": timestamp,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "goal": snapshot.checkpoint.goal or "",
            "summary": snapshot.checkpoint.summary or "",
            "next_step": snapshot.checkpoint.next_step or "",
            "constraints": list(snapshot.checkpoint.constraints),
            "sources_count": len(snapshot.sources),
            "sources": [source.path for source in snapshot.sources],
            "updated_at": snapshot.checkpoint.updated_at,
            "validation": snapshot.last_validation.result,
            "validation_basis": "persisted canonical record only; exports do not rerun validate",
        },
    }


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
            validation_basis_line(),
        ]
    )

    return "\n".join(lines) + "\n"


def write_handoff_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the rendered handoff to an explicit output file."""
    markdown = export_handoff_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, HandoffExportError)
