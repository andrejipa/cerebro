"""CLI wrapper for the read-only context index export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.context_index_export.exporter import (
    ContextIndexExportError,
    export_context_index_json,
    export_context_index_markdown,
    write_context_index_markdown,
)


def run_context_index_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_context_index_markdown,
        export_json=export_context_index_json,
        write_markdown=write_context_index_markdown,
        success_code="context_index_exported",
        success_message="context index written successfully",
        failure_code="context_index_export_failed",
        error_type=ContextIndexExportError,
    )
