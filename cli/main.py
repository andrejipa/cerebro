"""Minimal CLI entrypoint for the checkpoint system."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands.analyze import run_analyze
from cli.commands.checkpoint import run_checkpoint
from cli.commands.handoff_export import run_handoff_export
from cli.commands.import_context import run_import_context
from cli.commands.init import run_init
from cli.commands.resume import run_resume
from cli.commands.validate import run_validate
from cli.output import print_fail, user_error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="cerebro",
        description="Deterministic context runtime. Use `cerebro analyze` as the standard entrypoint.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    analyze_parser = subparsers.add_parser(
        "analyze",
        help="standard entrypoint for continuity context",
        description="Official runtime entrypoint: validate state, present context, and open a local session.",
    )
    analyze_parser.add_argument("--actor", help="explicit local actor name")
    analyze_parser.set_defaults(handler=run_analyze)

    init_parser = subparsers.add_parser(
        "init",
        help="create a new local checkpoint instance",
        description="Create the local checkpoint directory and initial state.",
    )
    init_parser.set_defaults(handler=run_init)

    import_parser = subparsers.add_parser(
        "import-context",
        help="replace the registered context source files",
        description="Register an explicit set of source files used as context anchors.",
    )
    import_parser.add_argument("--files", nargs="+", required=True, help="explicit relative file paths")
    import_parser.set_defaults(handler=run_import_context)

    checkpoint_parser = subparsers.add_parser(
        "checkpoint",
        help="update the current operational checkpoint",
        description="Save a short operational checkpoint without changing registered sources.",
    )
    checkpoint_parser.add_argument("--goal", required=True, help="short current goal")
    checkpoint_parser.add_argument("--summary", required=True, help="short operational summary")
    checkpoint_parser.add_argument("--next-step", required=True, dest="next_step", help="next executable step")
    checkpoint_parser.add_argument(
        "--constraint",
        action="append",
        default=[],
        help="short operational constraint; may be repeated",
    )
    checkpoint_parser.set_defaults(handler=run_checkpoint)

    resume_parser = subparsers.add_parser(
        "resume",
        help="compatibility command for the legacy resume flow",
        description="Compatibility command that runs the legacy resume flow on top of the same core state.",
    )
    resume_parser.add_argument("--actor", help="explicit local actor name")
    resume_parser.set_defaults(handler=run_resume)

    handoff_parser = subparsers.add_parser(
        "handoff-export",
        help="render a short human-readable handoff from the current state",
        description="Export a short Markdown handoff derived from the canonical state.",
    )
    handoff_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    handoff_parser.set_defaults(handler=run_handoff_export)

    validate_parser = subparsers.add_parser(
        "validate",
        help="validate state, sources, and local session",
        description="Validate registered state, sources, and the local session file when present.",
    )
    validate_parser.set_defaults(handler=run_validate)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    try:
        return args.handler(Path.cwd(), args)
    except KeyboardInterrupt:
        print_fail([user_error("interrupted", "command interrupted by user")])
        return 1
    except Exception:
        print_fail([user_error("internal_error", "unexpected internal error")])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
