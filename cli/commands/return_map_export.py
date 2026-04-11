"""CLI wrapper for the read-only return map export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.return_map_export.exporter import (
    ReturnMapExportError,
    export_return_map_markdown,
    write_return_map_markdown,
)


def run_return_map_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_return_map_markdown(root, args.out)
            print_ok(
                [
                    "return_map_exported: return map written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_return_map_markdown(root)
            print(markdown, end="")
    except ReturnMapExportError as exc:
        print_fail([user_error("return_map_export_failed", str(exc))])
        return 1

    return 0
