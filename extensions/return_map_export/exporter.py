"""Read-only return map export derived from the canonical checkpoint."""

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


class ReturnMapExportError(Exception):
    """Raised when the return map cannot be generated safely."""


def export_return_map_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured restart map from the canonical checkpoint."""
    store, snapshot = read_snapshot(root, ReturnMapExportError)

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()

    return {
        "schema_version": "1",
        "export_kind": "return_map",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": validation.result,
            "validation_basis": "persisted canonical record only; exports do not rerun validate",
            "session_file": session_file_presence(store),
            "updated_at": checkpoint.updated_at,
            "point_of_return": {
                "goal": checkpoint.goal,
                "summary": checkpoint.summary,
                "next_step": checkpoint.next_step,
            },
            "constraints": list(checkpoint.constraints),
            "sources_count": len(snapshot.sources),
            "sources": [source.path for source in snapshot.sources],
            "validation_details": [{"code": detail.code} for detail in validation.details],
        },
    }


def export_return_map_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a short restart map from the canonical checkpoint."""
    store, snapshot = read_snapshot(root, ReturnMapExportError)

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)

    lines = [
        "# Return Map",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        validation_basis_line(),
        f"- Session file: {session_file_presence(store)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {checkpoint.updated_at}",
        "",
        "## Point Of Return",
        f"- Goal: {checkpoint.goal}",
        f"- Summary: {checkpoint.summary}",
        f"- Next step: {checkpoint.next_step}",
        "",
        "## Constraints",
    ]

    if checkpoint.constraints:
        for item in checkpoint.constraints:
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
    for source in snapshot.sources:
        lines.append(f"- {source.path}")

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


def write_return_map_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the return map outside runtime-owned paths."""
    markdown = export_return_map_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, ReturnMapExportError)
