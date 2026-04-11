"""Read-only handoff exporter built on top of the stable core API."""

from __future__ import annotations

from pathlib import Path

from core import StateStore
from extensions._support import exported_timestamp, read_snapshot, reject_runtime_output_path, resolve_output_target


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
    store = StateStore(root)
    markdown = export_handoff_markdown(root, exported_at=exported_at)
    target = resolve_output_target(root, output_path)
    reject_runtime_output_path(store, target, HandoffExportError)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target
