"""CLI wrapper for the read-only sources export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.sources_export.exporter import (
    SourcesExportError,
    export_sources_json,
    export_sources_markdown,
    write_sources_markdown,
)


def run_sources_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_sources_markdown,
        export_json=export_sources_json,
        write_markdown=write_sources_markdown,
        success_code="sources_exported",
        success_message="sources written successfully",
        failure_code="sources_export_failed",
        error_type=SourcesExportError,
    )
