"""CLI wrapper for the read-only status export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.status_export.exporter import (
    StatusExportError,
    export_status_json,
    export_status_markdown,
    write_status_markdown,
)


def run_status_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_status_markdown,
        export_json=export_status_json,
        write_markdown=write_status_markdown,
        success_code="status_exported",
        success_message="status written successfully",
        failure_code="status_export_failed",
        error_type=StatusExportError,
    )
