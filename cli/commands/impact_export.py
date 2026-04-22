"""CLI wrapper for the read-only impact export extension."""

from __future__ import annotations

from pathlib import Path

from cli.commands._export_support import run_formatted_export
from extensions.impact_export.exporter import (
    ImpactExportError,
    export_impact_json,
    export_impact_markdown,
    write_impact_markdown,
)


def run_impact_export(root: Path, args) -> int:
    return run_formatted_export(
        root,
        args,
        export_markdown=export_impact_markdown,
        export_json=export_impact_json,
        write_markdown=write_impact_markdown,
        success_code="impact_exported",
        success_message="impact written successfully",
        failure_code="impact_export_failed",
        error_type=ImpactExportError,
    )
