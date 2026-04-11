"""Minimal CLI entrypoint for the checkpoint system."""

from __future__ import annotations

import argparse
from pathlib import Path

from cli.commands.analyze import run_analyze
from cli.commands.bootstrap_scan import run_bootstrap_scan
from cli.commands.checkpoint import run_checkpoint
from cli.commands.handoff_export import run_handoff_export
from cli.commands.impact_export import run_impact_export
from cli.commands.import_context import run_import_context
from cli.commands.init import run_init
from cli.commands.return_map_export import run_return_map_export
from cli.commands.resume import run_resume
from cli.commands.sources_export import run_sources_export
from cli.commands.status_export import run_status_export
from cli.commands.validate import run_validate
from cli.commands.validation_export import run_validation_export
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

    bootstrap_scan_parser = subparsers.add_parser(
        "bootstrap-scan",
        help="suggest likely bootstrap entry files without changing runtime state",
        description="Assistive-only scan that suggests candidate entry files from path and filename signals only; it does not create or modify runtime state. `--root` affects this scan only; later commands still use the current working directory unless you change into the target project first.",
    )
    bootstrap_scan_parser.add_argument(
        "--root",
        help="explicit project root to scan; defaults to the current directory and does not change where later commands run",
    )
    bootstrap_scan_parser.add_argument(
        "--limit",
        type=int,
        default=6,
        help="maximum number of suggested candidates to print; must be greater than zero",
    )
    bootstrap_scan_parser.set_defaults(handler=run_bootstrap_scan)

    import_parser = subparsers.add_parser(
        "import-context",
        help="replace the registered context source files",
        description="Register an explicit set of source files used as context anchors. File paths and runtime state are resolved from the current working directory.",
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

    impact_parser = subparsers.add_parser(
        "impact-export",
        help="render a short operational impact view from the current state",
        description="Export a compact read-only impact view derived from the canonical state.",
    )
    impact_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    impact_parser.set_defaults(handler=run_impact_export)

    sources_parser = subparsers.add_parser(
        "sources-export",
        help="render a short inventory of registered sources from the current state",
        description="Export a compact read-only inventory of registered source paths from the canonical state.",
    )
    sources_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    sources_parser.set_defaults(handler=run_sources_export)

    return_map_parser = subparsers.add_parser(
        "return-map-export",
        help="render a short point-of-return view from the current checkpoint",
        description="Export a compact read-only return map derived from the canonical checkpoint.",
    )
    return_map_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    return_map_parser.set_defaults(handler=run_return_map_export)

    status_parser = subparsers.add_parser(
        "status-export",
        help="render a short operational status from the current state",
        description="Export a compact read-only operational status derived from the canonical state.",
    )
    status_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    status_parser.set_defaults(handler=run_status_export)

    validation_export_parser = subparsers.add_parser(
        "validation-export",
        help="render a short view of the last persisted validation result",
        description="Export a compact read-only validation view derived from the persisted canonical validation record.",
    )
    validation_export_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    validation_export_parser.set_defaults(handler=run_validation_export)

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
