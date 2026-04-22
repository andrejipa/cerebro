"""Read-only validation export derived from the persisted canonical validation record."""

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


class ValidationExportError(Exception):
    """Raised when the validation export cannot be generated safely."""


def export_validation_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured view of the persisted canonical validation record."""
    store, snapshot = read_snapshot(root, ValidationExportError)
    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()

    return {
        "schema_version": "1",
        "export_kind": "validation",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": validation.result,
            "validation_basis": "persisted canonical record only; exports do not rerun validate",
            "risk": validation_risk_level(validation.result, validation.details),
            "session_file": session_file_presence(store),
            "updated_at": snapshot.checkpoint.updated_at,
            "registered_sources": len(snapshot.sources),
            "validated_at": validation.validated_at,
            "details_count": len(validation.details),
            "details": [
                {
                    "code": detail.code,
                }
                for detail in validation.details
            ],
        },
    }


def export_validation_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact view of the persisted canonical validation record."""
    store, snapshot = read_snapshot(root, ValidationExportError)

    validation = snapshot.last_validation
    exported_at_value = exported_timestamp(exported_at)
    lines = [
        "# Validation",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        validation_basis_line(),
        f"- Risk: {validation_risk_level(validation.result, validation.details)}",
        f"- Session file: {session_file_presence(store)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {snapshot.checkpoint.updated_at}",
        f"- Registered sources: {len(snapshot.sources)}",
    ]

    if validation.validated_at:
        lines.append(f"- Validated at: {validation.validated_at}")

    lines.extend(
        [
            f"- Validation details: {len(validation.details)}",
            "",
            "## Validation Details",
        ]
    )

    if validation.details:
        for detail in validation.details:
            lines.append(f"- {detail.code}")
    else:
        lines.append("- none")

    return "\n".join(lines) + "\n"


def write_validation_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the validation view outside runtime-owned paths."""
    markdown = export_validation_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, ValidationExportError)
