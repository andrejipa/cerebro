"""CLI wrapper for the read-only handoff export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.handoff_export.exporter import (
    HandoffExportError,
    export_handoff_json,
    export_handoff_markdown,
    write_handoff_markdown,
)


def run_handoff_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_handoff_markdown,
        export_json=export_handoff_json,
        write_markdown=write_handoff_markdown,
        success_code="handoff_exported",
        success_message="handoff written successfully",
        failure_code="handoff_export_failed",
        error_type=HandoffExportError,
    )
