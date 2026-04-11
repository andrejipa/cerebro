"""CLI wrapper for the read-only validation export extension."""

from __future__ import annotations

from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions.validation_export.exporter import (
    ValidationExportError,
    export_validation_markdown,
    write_validation_markdown,
)


def run_validation_export(root: Path, args) -> int:
    try:
        if args.out:
            target = write_validation_markdown(root, args.out)
            print_ok(
                [
                    "validation_exported: validation written successfully",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_validation_markdown(root)
            print(markdown, end="")
    except ValidationExportError as exc:
        print_fail([user_error("validation_export_failed", str(exc))])
        return 1

    return 0
