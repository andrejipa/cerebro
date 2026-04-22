"""CLI wrapper for the read-only return map export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.return_map_export.exporter import (
    ReturnMapExportError,
    export_return_map_json,
    export_return_map_markdown,
    write_return_map_markdown,
)


def run_return_map_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_return_map_markdown,
        export_json=export_return_map_json,
        write_markdown=write_return_map_markdown,
        success_code="return_map_exported",
        success_message="return map written successfully",
        failure_code="return_map_export_failed",
        error_type=ReturnMapExportError,
    )
