"""CLI wrapper for the read-only status export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.status_export.exporter import StatusExportError, export_status_markdown, write_status_markdown


def run_status_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_status_markdown(root, args.out)
            print_ok(
                [
                    "status_exported: status written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_status_markdown(root)
            print(markdown, end="")
    except StatusExportError as exc:
        print_fail([user_error("status_export_failed", str(exc))])
        return 1

    return 0
