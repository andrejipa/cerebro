"""Read-only operational impact export derived from the canonical state."""

from __future__ import annotations

import hashlib
from pathlib import Path

from extensions._support import (
    exported_timestamp,
    read_snapshot,
    session_file_presence,
    validation_basis_line,
    validation_risk_level,
    write_markdown_output,
)


class ImpactExportError(Exception):
    """Raised when the impact export cannot be generated safely."""


def export_impact_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured operational impact view from the current snapshot."""
    store, snapshot = read_snapshot(root, ImpactExportError)

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()

    return {
        "schema_version": "1",
        "export_kind": "impact",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": validation.result,
            "validation_basis": "persisted canonical record only; exports do not rerun validate",
            "risk": validation_risk_level(validation.result, validation.details),
            "session_file": session_file_presence(store),
            "updated_at": checkpoint.updated_at,
            "scope": {
                "goal": checkpoint.goal,
                "next_step": checkpoint.next_step,
                "constraint_count": len(checkpoint.constraints),
                "registered_sources": len(snapshot.sources),
            },
            "registered_paths": [source.path for source in snapshot.sources],
            "validation_details": [{"code": detail.code} for detail in validation.details],
        },
    }


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
        validation_basis_line(),
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
