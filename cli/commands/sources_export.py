"""CLI wrapper for the read-only sources export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.sources_export.exporter import SourcesExportError, export_sources_markdown, write_sources_markdown


def run_sources_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_sources_markdown(root, args.out)
            print_ok(
                [
                    "sources_exported: sources written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_sources_markdown(root)
            print(markdown, end="")
    except SourcesExportError as exc:
        print_fail([user_error("sources_export_failed", str(exc))])
        return 1

    return 0
