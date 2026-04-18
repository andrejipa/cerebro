"""Minimal CLI entrypoint for the checkpoint system."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from cli.project_dashboard import render_open_dashboard
from cli.project_registry import ProjectRegistryError, load_projects, register_or_update_project
from cli.commands.analyze import run_analyze
from cli.commands.approve import run_approve
from cli.commands.apply import run_apply
from cli.commands.bootstrap_scan import run_bootstrap_scan
from cli.commands.checkpoint import run_checkpoint
from cli.commands.context_index_export import run_context_index_export
from cli.commands.doctor import run_doctor
from cli.commands.handoff_export import run_handoff_export
from cli.commands.impact_export import run_impact_export
from cli.commands.import_context import run_import_context
from cli.commands.init import run_init
from cli.commands.plan import run_plan
from cli.commands.return_map_export import run_return_map_export
from cli.commands.resume import run_resume
from cli.commands.rollback import run_rollback
from cli.commands.session_discard import run_session_discard
from cli.commands.sources_export import run_sources_export
from cli.commands.status_export import run_status_export
from cli.commands.validate import run_validate
from cli.commands.verify import run_verify
from cli.commands.validation_export import run_validation_export
from cli.output import print_fail, user_error


def _dispatch_context_menu(argv: list[str]) -> list[str] | None:
    if argv:
        return argv
    if not sys.stdin.isatty():
        print_fail([user_error("context_menu_unavailable", "interactive context menu requires a terminal; pass a subcommand explicitly")])
        return None

    print("CEREBRO")
    print("---------------------")
    print("(1) Desenvolvimento")
    print("(2) Gerenciar projeto")

    choice = input("Selecione [1/2]: ").strip()
    if choice == "1":
        return ["analyze"]
    if choice == "2":
        return _dispatch_managed_project_mode()

    print_fail([user_error("context_menu_invalid", f"invalid context menu selection: {choice or '<empty>'}")])
    return None


def _dispatch_managed_project_mode() -> list[str] | None:
    try:
        projects = load_projects()
    except ProjectRegistryError as exc:
        print_fail([user_error("project_registry_invalid", str(exc))])
        return None

    if projects:
        print("Projetos registrados")
        for index, project in enumerate(projects, start=1):
            print(f"({index}) {project['name']} — {project['path']}")
        print("(N) Novo projeto")
        selection = input(f"Selecione [1-{len(projects)}/N]: ").strip()
        if selection.lower() == "n":
            return _register_and_dispatch_project()
        if selection.isdigit():
            project_index = int(selection) - 1
            if 0 <= project_index < len(projects):
                return _register_and_dispatch_project(projects[project_index]["path"])
        print_fail([user_error("project_registry_selection_invalid", f"invalid project selection: {selection or '<empty>'}")])
        return None

    return _register_and_dispatch_project()


def _register_and_dispatch_project(project_root: str | None = None) -> list[str] | None:
    raw_project_root = project_root if project_root is not None else input("Project root: ").strip()
    if not raw_project_root:
        print_fail([user_error("project_root_missing", "project root is required for managed-project mode")])
        return None

    resolved_root = Path(raw_project_root).expanduser().resolve()
    if not resolved_root.exists():
        print_fail([user_error("project_root_not_found", f"project root does not exist: {resolved_root}")])
        return None
    if not resolved_root.is_dir():
        print_fail([user_error("project_root_invalid", f"project root is not a directory: {resolved_root}")])
        return None

    try:
        register_or_update_project(resolved_root)
    except ProjectRegistryError as exc:
        print_fail([user_error("project_registry_invalid", str(exc))])
        return None
    return ["--project-root", str(resolved_root), "analyze"]


def build_parser() -> argparse.ArgumentParser:
    project_root_parent = argparse.ArgumentParser(add_help=False)
    project_root_parent.add_argument(
        "--project-root",
        default=argparse.SUPPRESS,
        help="explicit project root; defaults to the current working directory",
    )
    parser = argparse.ArgumentParser(
        prog="cerebro",
        parents=[project_root_parent],
        formatter_class=argparse.RawDescriptionHelpFormatter,
        description=(
            "Deterministic context runtime.\n\n"
            "Install Cerebro once from the Cerebro repository root.\n"
            "Use Cerebro from the target project root.\n\n"
            "First successful run:\n"
            "  1. cerebro init\n"
            "  2. cerebro import-context --files ...\n"
            "  3. cerebro checkpoint --goal ... --summary ... --next-step ...\n"
            "  4. cerebro validate\n"
            "  5. cerebro analyze\n\n"
            "After bootstrap, `cerebro analyze` is the standard entrypoint.\n"
            "Ignore exports and advanced commands until this succeeds once."
        ),
    )
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_command_parser = lambda *args, **kwargs: subparsers.add_parser(*args, parents=[project_root_parent], **kwargs)

    init_parser = add_command_parser(
        "init",
        help="create a new local checkpoint instance",
        description="Create the local checkpoint directory and initial state.",
    )
    init_parser.set_defaults(handler=run_init)

    import_parser = add_command_parser(
        "import-context",
        help="replace the registered context source files",
        description="Register an explicit set of source files used as context anchors. The command previews a sources diff and requires confirmation before replacing the current set. File paths and runtime state are resolved from the current working directory.",
    )
    import_parser.add_argument("--files", nargs="+", required=True, help="explicit relative file paths")
    import_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    import_parser.set_defaults(handler=run_import_context)

    checkpoint_parser = add_command_parser(
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
    checkpoint_parser.add_argument("--actor", help="explicit local actor expected to own the active session")
    checkpoint_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    checkpoint_parser.set_defaults(handler=run_checkpoint)

    plan_parser = add_command_parser(
        "plan",
        help="persist an alpha-runtime execution plan and verification registry",
        description="Persist the alpha-runtime plan, typed task list, execution policy, and registered verification commands. Accepts either repeated --task flags or one domain-adapted text input.",
    )
    plan_parser.add_argument("--goal", help="alpha-runtime goal; required unless derived from domain input")
    plan_parser.add_argument("--summary", help="alpha-runtime summary; required unless derived from domain input")
    plan_parser.add_argument("--task", action="append", default=[], help="task title; may be repeated")
    plan_parser.add_argument("--input-text", help="domain input text to adapt into canonical tasks")
    plan_parser.add_argument("--input-file", help="UTF-8 text file to adapt into canonical tasks")
    plan_parser.add_argument(
        "--input-kind",
        choices=("auto", "list", "task", "structured"),
        default="auto",
        help="adapter mode for --input-text/--input-file; auto detects ambiguity and requires explicit selection",
    )
    plan_parser.add_argument(
        "--verify-command",
        action="append",
        default=[],
        help="verification command string to register; may be repeated",
    )
    plan_parser.add_argument(
        "--autonomy-level",
        default="A1",
        help="execution autonomy level (A0-A4); defaults to A1",
    )
    plan_parser.add_argument(
        "--protect-path",
        action="append",
        default=[],
        help="extra protected path glob; may be repeated",
    )
    plan_parser.add_argument(
        "--blocked-command",
        action="append",
        default=[],
        help="extra blocked command prefix; may be repeated",
    )
    plan_parser.add_argument(
        "--approval-required-kind",
        action="append",
        default=[],
        help="extra action kind requiring approval; may be repeated",
    )
    plan_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    plan_parser.set_defaults(handler=run_plan)

    validate_parser = add_command_parser(
        "validate",
        help="validate state, sources, and local session",
        description="Validate registered state, sources, and the local session file when present.",
    )
    validate_parser.add_argument(
        "--retention-report",
        action="store_true",
        help="print a dry-run retention report for runtime artifacts and events.jsonl",
    )
    validate_parser.add_argument(
        "--retention-apply",
        action="store_true",
        help="apply the governed retention policy after validate passes",
    )
    validate_parser.set_defaults(handler=run_validate)

    apply_parser = add_command_parser(
        "apply",
        help="execute one or more typed action payloads against the current project",
        description="Load one or more JSON action payloads, validate them against policy, execute them, and persist the action records.",
    )
    apply_parser.add_argument("--action-file", action="append", required=True, help="path to one JSON action payload; may be repeated")
    apply_parser.add_argument("--task-id", help="explicit task id to bind the action to; defaults to current_task_id")
    apply_parser.add_argument("--batch-id", help="explicit batch id shared across multiple actions")
    apply_parser.add_argument("--retry-justification", help="explicit reason required when retrying a previously attempted action after new evidence")
    apply_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    apply_parser.set_defaults(handler=run_apply)

    approve_parser = add_command_parser(
        "approve",
        help="resolve one pending alpha-runtime approval",
        description="Approve or reject one pending action approval request and persist the decision.",
    )
    approve_parser.add_argument("--approval-id", required=True, help="pending approval id")
    approve_parser.add_argument(
        "--decision",
        required=True,
        choices=("approved", "rejected"),
        help="approval decision",
    )
    approve_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    approve_parser.set_defaults(handler=run_approve)

    verify_parser = add_command_parser(
        "verify",
        help="run the registered alpha-runtime verification commands",
        description="Run the registered verification commands and persist the resulting checks.",
    )
    verify_parser.add_argument(
        "--command-id",
        action="append",
        default=[],
        help="specific registered command id to run; may be repeated",
    )
    verify_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    verify_parser.set_defaults(handler=run_verify)

    rollback_parser = add_command_parser(
        "rollback",
        help="rollback one applied action or one applied batch",
        description="Rollback one applied reversible action or one reversible batch in reverse order.",
    )
    rollback_parser.add_argument("--action-id", help="one applied action id to rollback")
    rollback_parser.add_argument("--batch-id", help="one batch id to rollback")
    rollback_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    rollback_parser.set_defaults(handler=run_rollback)

    analyze_parser = add_command_parser(
        "analyze",
        help="standard entrypoint for continuity context",
        description="Official runtime entrypoint: validate state, present context, and open a local session only when no active local session is already present.",
    )
    analyze_parser.add_argument("--actor", help="explicit local actor name")
    analyze_parser.add_argument(
        "--emit-session-token",
        action="store_true",
        help="emit the one live session capability token in command output for external capture; omitted by default to avoid accidental leakage",
    )
    analyze_parser.set_defaults(handler=run_analyze)

    doctor_parser = add_command_parser(
        "doctor",
        help="run a read-only diagnostic report for the current project and runtime",
        description="Render a read-only diagnostic report for Python, the repo test suite, canonical state, session presence, weakness backlog, and freeze posture. This command does not open continuity and does not mutate runtime state.",
    )
    doctor_parser.set_defaults(handler=run_doctor)

    resume_parser = add_command_parser(
        "resume",
        help="compatibility command for the legacy resume flow",
        description="Compatibility command that runs the legacy resume flow on top of the same core state, opening a local session only when no active local session is already present.",
    )
    resume_parser.add_argument("--actor", help="explicit local actor name")
    resume_parser.add_argument(
        "--emit-session-token",
        action="store_true",
        help="emit the one live session capability token in command output for external capture; omitted by default to avoid accidental leakage",
    )
    resume_parser.set_defaults(handler=run_resume)

    session_discard_parser = add_command_parser(
        "session-discard",
        help="discard the local session file explicitly",
        description="Discard the local session file explicitly. This can clear a stale-session block, but it does not make continuity uninterrupted again; reopen continuity later through analyze or resume.",
    )
    session_discard_parser.add_argument("--session-token", help="active session capability token; use `-` to read one line from stdin, or fall back to CEREBRO_SESSION_TOKEN")
    session_discard_parser.set_defaults(handler=run_session_discard)

    bootstrap_scan_parser = add_command_parser(
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

    handoff_parser = add_command_parser(
        "handoff-export",
        help="render a short human-readable handoff from the current state",
        description="Export a short Markdown handoff derived from the canonical state.",
    )
    handoff_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    handoff_parser.set_defaults(handler=run_handoff_export)

    context_index_parser = add_command_parser(
        "context-index-export",
        help="render a short navigation index from the current canonical context",
        description="Export a compact read-only navigation index derived from canonical state and organized around canonical registered sources and checkpoint text.",
    )
    context_index_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    context_index_parser.set_defaults(handler=run_context_index_export)

    impact_parser = add_command_parser(
        "impact-export",
        help="render a short operational impact view from the current state",
        description="Export a compact read-only impact view derived from the canonical state.",
    )
    impact_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    impact_parser.set_defaults(handler=run_impact_export)

    sources_parser = add_command_parser(
        "sources-export",
        help="render a short inventory of registered sources from the current state",
        description="Export a compact read-only inventory of registered source paths from the canonical state.",
    )
    sources_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    sources_parser.set_defaults(handler=run_sources_export)

    return_map_parser = add_command_parser(
        "return-map-export",
        help="render a short point-of-return view from the current checkpoint",
        description="Export a compact read-only return map derived from the canonical checkpoint.",
    )
    return_map_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    return_map_parser.set_defaults(handler=run_return_map_export)

    status_parser = add_command_parser(
        "status-export",
        help="render a short operational status from the current state",
        description="Export a compact read-only operational status derived from the canonical state.",
    )
    status_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    status_parser.set_defaults(handler=run_status_export)

    validation_export_parser = add_command_parser(
        "validation-export",
        help="render a short view of the last persisted validation result",
        description="Export a compact read-only validation view derived from the persisted canonical validation record.",
    )
    validation_export_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    validation_export_parser.set_defaults(handler=run_validation_export)

    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        effective_argv = list(sys.argv[1:] if argv is None else argv)
        opened_without_args = not effective_argv
        dispatched_argv = _dispatch_context_menu(effective_argv)
        if dispatched_argv is None:
            return 1
        parser = build_parser()
        args = parser.parse_args(dispatched_argv)
        root = Path(args.project_root).resolve() if getattr(args, "project_root", None) else Path.cwd()
        if opened_without_args and args.command == "analyze":
            print(render_open_dashboard(root))
        return args.handler(root, args)
    except KeyboardInterrupt:
        print_fail([user_error("interrupted", "command interrupted by user")])
        return 1
    except Exception:
        print_fail([user_error("internal_error", "unexpected internal error")])
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
