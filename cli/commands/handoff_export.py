"""CLI wrapper for the read-only handoff export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.handoff_export.exporter import HandoffExportError, export_handoff_markdown, write_handoff_markdown


def run_handoff_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_handoff_markdown(root, args.out)
            print_ok(
                [
                    "handoff_exported: handoff written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_handoff_markdown(root)
            print(markdown, end="")
    except HandoffExportError as exc:
        print_fail([user_error("handoff_export_failed", str(exc))])
        return 1

    return 0
