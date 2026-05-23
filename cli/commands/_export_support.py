"""Shared CLI runner for read-only export commands."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

from cli.output import print_fail, print_ok, user_error
from extensions._support import write_markdown_output


def run_markdown_export(
    root: Path,
    args,
    *,
    export_markdown: Callable[[Path], str],
    write_markdown: Callable[[Path, str], Path],
    success_code: str,
    success_message: str,
    failure_code: str,
    error_type: type[Exception],
) -> int:
    """Run one read-only markdown export command with consistent CLI behavior."""
    try:
        if args.out:
            target = write_markdown(root, args.out)
            print_ok(
                [
                    f"{success_code}: {success_message}",
                    f"output: {target}",
                ]
            )
        else:
            markdown = export_markdown(root)
            print(markdown, end="")
    except error_type as exc:
        print_fail([user_error(failure_code, str(exc))])
        return 1

    return 0


def run_formatted_export(
    root: Path,
    args,
    *,
    export_markdown: Callable[[Path], str],
    export_json: Callable[[Path], dict],
    write_markdown: Callable[[Path, str], Path],
    success_code: str,
    success_message: str,
    failure_code: str,
    error_type: type[Exception],
) -> int:
    """Run one read-only export command with markdown/json formatting."""
    output_format = getattr(args, "format", "md")
    try:
        if output_format == "json":
            payload = json.dumps(export_json(root), indent=2, sort_keys=True) + "\n"
            if args.out:
                target = write_markdown_output(root, args.out, payload, error_type)
                print_ok(
                    [
                        f"{success_code}: {success_message}",
                        f"output: {target}",
                    ]
                )
            else:
                print(payload, end="")
        else:
            if args.out:
                target = write_markdown(root, args.out)
                print_ok(
                    [
                        f"{success_code}: {success_message}",
                        f"output: {target}",
                    ]
                )
            else:
                markdown = export_markdown(root)
                print(markdown, end="")
    except error_type as exc:
        print_fail([user_error(failure_code, str(exc))])
        return 1

    return 0
