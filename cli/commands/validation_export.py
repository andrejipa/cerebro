"""CLI wrapper for the read-only validation export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.validation_export.exporter import (
    ValidationExportError,
    export_validation_json,
    export_validation_markdown,
    write_validation_markdown,
)


def run_validation_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_validation_markdown,
        export_json=export_validation_json,
        write_markdown=write_validation_markdown,
        success_code="validation_exported",
        success_message="validation written successfully",
        failure_code="validation_export_failed",
        error_type=ValidationExportError,
    )
