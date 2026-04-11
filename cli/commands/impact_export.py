"""CLI wrapper for the read-only impact export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.impact_export.exporter import ImpactExportError, export_impact_markdown, write_impact_markdown


def run_impact_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_impact_markdown(root, args.out)
            print_ok(
                [
                    "impact_exported: impact written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_impact_markdown(root)
            print(markdown, end="")
    except ImpactExportError as exc:
        print_fail([user_error("impact_export_failed", str(exc))])
        return 1

    return 0
