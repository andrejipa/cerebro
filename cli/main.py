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
from cli.commands.iteration_commit import run_iteration_commit
from cli.commands.plan import run_plan
from cli.commands.residuals_view import run_residuals_view
from cli.commands.return_map_export import run_return_map_export
from cli.commands.resume import run_resume
from cli.commands.rollback import run_rollback
from cli.commands.runtime_manager import run_runtime_manager
from cli.commands.session_discard import run_session_discard
from cli.commands.sources_export import run_sources_export
from cli.commands.status_export import run_status_export
from cli.commands.validate import run_validate
from cli.commands.verify import run_verify
from cli.commands.validation_export import run_validation_export
from cli.commands.worktree import run_worktree
from cli.output import print_fail, user_error
from cli.project_root import find_project_root


def _read_interactive_input(prompt: str, *, code: str, message: str) -> str | None:
    try:
        return input(prompt).strip()
    except EOFError:
        print_fail([user_error(code, message)])
        return None


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

    choice = _read_interactive_input(
        "Selecione [1/2]: ",
        code="context_menu_input_closed",
        message="interactive context menu input closed before a selection was provided",
    )
    if choice is None:
        return None
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
        selection = _read_interactive_input(
            f"Selecione [1-{len(projects)}/N]: ",
            code="project_registry_selection_closed",
            message="interactive project selection input closed before a project was chosen",
        )
        if selection is None:
            return None
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
    raw_project_root = project_root
    if raw_project_root is None:
        raw_project_root = _read_interactive_input(
            "Project root: ",
            code="project_root_input_closed",
            message="interactive project root input closed before a project root was provided",
        )
        if raw_project_root is None:
            return None
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
        description=(
            "Bootstrap a project: state.json, runtime.db, AGENTS.md (universal, never CLAUDE.md), "
            "and docs/operations scaffold. Use --repair-scaffold to add only missing artefacts."
        ),
    )
    init_parser.add_argument(
        "--repair-scaffold",
        action="store_true",
        default=False,
        dest="repair_scaffold",
        help="create only missing scaffold artefacts without modifying existing files",
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

    iteration_commit_parser = add_command_parser(
        "iteration-commit",
        help="stage selected repo paths and create one generated iteration commit",
        description="Generate an iteration commit message from IMPLEMENTATION_STATUS, rerun the required repo test gates, stage only the selected repository paths, and create one git commit. This command is explicit automation for Cerebro engineering work; it does not mutate the managed project runtime state.",
    )
    iteration_commit_parser.add_argument(
        "--path",
        action="append",
        required=True,
        help="repository-relative path to stage for this iteration commit; may be repeated",
    )
    iteration_commit_parser.set_defaults(handler=run_iteration_commit)

    worktree_parser = add_command_parser(
        "worktree",
        help="manage isolated git worktrees for parallel Cerebro agents",
        description=(
            "Create and manage isolated git worktrees rooted under `.worktrees/`. "
            "Each worktree is a separate Cerebro project root with its own local `.cerebro/` runtime state."
        ),
    )
    worktree_subparsers = worktree_parser.add_subparsers(dest="worktree_command", required=True)
    worktree_create_parser = worktree_subparsers.add_parser(
        "create",
        help="create one isolated git worktree for parallel Cerebro work",
        description=(
            "Create a strict-slug git worktree under `.worktrees/<name>/`, create branch `worktree-<name>`, "
            "and register it in `.cerebro/worktrees.toml`."
        ),
    )
    worktree_create_parser.add_argument("name", help="strict worktree slug")
    worktree_create_parser.set_defaults(handler=run_worktree)
    worktree_list_parser = worktree_subparsers.add_parser(
        "list",
        help="list isolated git worktrees reconciled against the local registry",
        description=(
            "List git worktrees rooted under `.worktrees/` and reconcile them against `.cerebro/worktrees.toml` "
            "to surface active, missing, and unregistered entries."
        ),
    )
    worktree_list_parser.set_defaults(handler=run_worktree)
    worktree_clean_parser = worktree_subparsers.add_parser(
        "clean",
        help="remove one isolated git worktree and unregister it after a clean check",
        description=(
            "Remove one registered git worktree rooted under `.worktrees/<name>/`, delete branch "
            "`worktree-<name>`, and remove the registry entry only after Git confirms the cleanup."
        ),
    )
    worktree_clean_parser.add_argument("name", help="strict worktree slug")
    worktree_clean_parser.set_defaults(handler=run_worktree)

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
    handoff_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    handoff_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    handoff_parser.set_defaults(handler=run_handoff_export)

    context_index_parser = add_command_parser(
        "context-index-export",
        help="render a short navigation index from the current canonical context",
        description="Export a compact read-only navigation index derived from canonical state and organized around canonical registered sources and checkpoint text.",
    )
    context_index_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    context_index_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    context_index_parser.set_defaults(handler=run_context_index_export)

    impact_parser = add_command_parser(
        "impact-export",
        help="render a short operational impact view from the current state",
        description="Export a compact read-only impact view derived from the canonical state.",
    )
    impact_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    impact_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    impact_parser.set_defaults(handler=run_impact_export)

    sources_parser = add_command_parser(
        "sources-export",
        help="render a short inventory of registered sources from the current state",
        description="Export a compact read-only inventory of registered source paths from the canonical state.",
    )
    sources_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    sources_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    sources_parser.set_defaults(handler=run_sources_export)

    return_map_parser = add_command_parser(
        "return-map-export",
        help="render a short point-of-return view from the current checkpoint",
        description="Export a compact read-only return map derived from the canonical checkpoint.",
    )
    return_map_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    return_map_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    return_map_parser.set_defaults(handler=run_return_map_export)

    residuals_view_parser = add_command_parser(
        "residuals-view",
        help="render a structured view of accepted and blocked residuals",
        description="Export a compact read-only view derived from docs/operations/residuals.toml.",
    )
    residuals_view_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    residuals_view_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    residuals_view_parser.set_defaults(handler=run_residuals_view)

    runtime_manager_parser = add_command_parser(
        "runtime-manager",
        help="inspect the local runtime-manager read model",
        description=(
            "Synchronize or inspect the local runtime-manager SQLite read model. "
            "The CLI delegates to core.runtime_manager_store and does not parse TOML, SQLite, or Markdown directly."
        ),
    )
    runtime_manager_subparsers = runtime_manager_parser.add_subparsers(
        dest="runtime_manager_command",
        required=True,
    )
    runtime_manager_sync_parser = runtime_manager_subparsers.add_parser(
        "sync",
        help="import the observation center into runtime.db",
        description="Import docs/operations/observation_center.toml into the core-owned runtime.db read model.",
    )
    runtime_manager_sync_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_sync_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_status_parser = runtime_manager_subparsers.add_parser(
        "status",
        help="show read-only runtime-manager status",
        description="Show read-only status from runtime.db and fail closed when the imported source digest is stale.",
    )
    runtime_manager_status_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_status_parser.add_argument("--out", help="explicit projection output file; prints to stdout when omitted")
    runtime_manager_status_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_next_parser = runtime_manager_subparsers.add_parser(
        "next",
        help="show the selected eligible work item",
        description="Show the read-only next eligible runtime-manager item from the core-owned read model.",
    )
    runtime_manager_next_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_next_parser.add_argument("--out", help="explicit projection output file; prints to stdout when omitted")
    runtime_manager_next_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_center_parser = runtime_manager_subparsers.add_parser(
        "center",
        help="manage observation-center authority",
        description="Promote or export the observation center through the core-owned runtime.db boundary.",
    )
    runtime_manager_center_subparsers = runtime_manager_center_parser.add_subparsers(
        dest="center_command",
        required=True,
    )
    runtime_manager_center_promote_parser = runtime_manager_center_subparsers.add_parser(
        "promote",
        help="promote runtime.db as the primary observation-center authority",
        description="Import the current TOML center, then mark runtime.db as the primary local authority.",
    )
    runtime_manager_center_promote_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_center_promote_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_center_export_parser = runtime_manager_center_subparsers.add_parser(
        "export",
        help="export a deterministic TOML snapshot from runtime.db",
        description="Render TOML compatibility output from the SQLite observation-center authority.",
    )
    runtime_manager_center_export_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    runtime_manager_center_export_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_center_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_check_parser = runtime_manager_subparsers.add_parser(
        "check",
        help="check whether a registered command is eligible to run",
        description="Read-only enforcement gate: verify a command_id is registered, enabled, and all Phase 1 gates are satisfied.",
    )
    runtime_manager_check_parser.add_argument("command_id", help="command_id to check eligibility for")
    runtime_manager_check_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_check_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_run_parser = runtime_manager_subparsers.add_parser(
        "run",
        help="execute a registered command through the full enforcement chain",
        description=(
            "Constrained subprocess executor: eligibility gate, path scope, timeout, output budget, approval check. "
            "Executes exactly the argv_prefix registered for command_id — no extra arguments are accepted so that "
            "the approval fingerprint covers the full execution unit."
        ),
    )
    runtime_manager_run_parser.add_argument("command_id", help="command_id to execute")
    runtime_manager_run_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_run_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_trace_parser = runtime_manager_subparsers.add_parser(
        "trace",
        help="inspect sanitized Runtime Manager traces",
        description="Read or export runtime_traces and runtime_trace_events. Projection-only; trace output is not permission.",
    )
    runtime_manager_trace_subparsers = runtime_manager_trace_parser.add_subparsers(
        dest="trace_command",
        required=True,
    )
    trace_list_parser = runtime_manager_trace_subparsers.add_parser("list", help="list Runtime Manager traces")
    trace_list_parser.add_argument("--operation", default=None, help="filter by operation")
    trace_list_parser.add_argument("--subject-id", dest="subject_id", default=None, help="filter by subject id")
    trace_list_parser.add_argument("--limit", type=int, default=50, help="max rows (default 50; 0=all)")
    trace_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    trace_list_parser.set_defaults(handler=run_runtime_manager)
    trace_show_parser = runtime_manager_trace_subparsers.add_parser("show", help="show a Runtime Manager trace")
    trace_show_parser.add_argument("trace_id", help="trace_id to inspect")
    trace_show_parser.add_argument("--format", choices=("text", "json"), default="text")
    trace_show_parser.set_defaults(handler=run_runtime_manager)
    trace_export_parser = runtime_manager_trace_subparsers.add_parser("export", help="export a Runtime Manager trace")
    trace_export_parser.add_argument("trace_id", help="trace_id to export")
    trace_export_parser.add_argument("--format", dest="export_format", choices=("json", "jsonl", "otel-json"), default="json")
    trace_export_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_trace_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_metrics_parser = runtime_manager_subparsers.add_parser(
        "metrics",
        help="show local Runtime Manager health counters",
        description="Read local Runtime Manager metrics from runtime.db. Projection-only; metrics are not authority.",
    )
    runtime_manager_metrics_parser.add_argument("--format", choices=("text", "json"), default="text")
    runtime_manager_metrics_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_replay_parser = runtime_manager_subparsers.add_parser(
        "replay",
        help="run a deterministic Runtime Manager replay scenario",
        description="Evaluate a local replay scenario JSON file against runtime.db. Replay evidence is not permission.",
    )
    runtime_manager_replay_parser.add_argument("--scenario", required=True, help="path to replay scenario JSON")
    runtime_manager_replay_parser.add_argument("--format", choices=("text", "json"), default="text")
    runtime_manager_replay_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_evidence_parser = runtime_manager_subparsers.add_parser(
        "evidence",
        help="inspect execution evidence records",
        description="Read execution_evidence rows captured by run_command(). Read-only — does not execute anything.",
    )
    runtime_manager_evidence_subparsers = runtime_manager_evidence_parser.add_subparsers(
        dest="evidence_command",
        required=True,
    )
    runtime_manager_evidence_show_parser = runtime_manager_evidence_subparsers.add_parser(
        "show",
        help="show a single evidence record by id",
        description="Display all fields of a single execution_evidence row.",
    )
    runtime_manager_evidence_show_parser.add_argument("evidence_id", help="integer primary key of the evidence record")
    runtime_manager_evidence_show_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_evidence_show_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_evidence_list_parser = runtime_manager_evidence_subparsers.add_parser(
        "list",
        help="list recent evidence records, newest first",
        description="List execution_evidence rows, newest first. Optionally filter by observation_id.",
    )
    runtime_manager_evidence_list_parser.add_argument(
        "--observation-id",
        dest="observation_id",
        default=None,
        help="filter to a specific observation_id",
    )
    runtime_manager_evidence_list_parser.add_argument(
        "--limit",
        type=int,
        default=50,
        help="maximum rows to return (default 50; 0 = all)",
    )
    runtime_manager_evidence_list_parser.add_argument(
        "--format",
        choices=("text", "json"),
        default="text",
        help="output format; defaults to text",
    )
    runtime_manager_evidence_list_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_evidence_parser.set_defaults(handler=run_runtime_manager)

    # lease subcommand
    runtime_manager_lease_parser = runtime_manager_subparsers.add_parser(
        "lease",
        help="manage write-API leases (acquire, release, heartbeat, list)",
        description="Manage runtime-owned managed_leases: acquire single-flight ownership, renew, release, or list.",
    )
    runtime_manager_lease_subparsers = runtime_manager_lease_parser.add_subparsers(
        dest="lease_command", required=True
    )
    lease_acquire_parser = runtime_manager_lease_subparsers.add_parser("acquire", help="acquire a managed lease")
    lease_acquire_parser.add_argument("observation_id", help="observation id to lease")
    lease_acquire_parser.add_argument("--owner", default="cli", help="owner identifier (default: cli)")
    lease_acquire_parser.add_argument("--ttl-seconds", dest="ttl_seconds", type=int, default=300, help="lease TTL in seconds (default 300)")
    lease_acquire_parser.add_argument("--reason", default="", help="optional reason text")
    lease_acquire_parser.add_argument("--format", choices=("text", "json"), default="text")
    lease_acquire_parser.set_defaults(handler=run_runtime_manager)
    lease_release_parser = runtime_manager_lease_subparsers.add_parser("release", help="release an active managed lease")
    lease_release_parser.add_argument("lease_id", help="lease_id to release")
    lease_release_parser.add_argument("--owner", required=True, help="owner identifier (must match the acquiring owner)")
    lease_release_parser.add_argument("--format", choices=("text", "json"), default="text")
    lease_release_parser.set_defaults(handler=run_runtime_manager)
    lease_heartbeat_parser = runtime_manager_lease_subparsers.add_parser("heartbeat", help="renew an active managed lease")
    lease_heartbeat_parser.add_argument("lease_id", help="lease_id to renew")
    lease_heartbeat_parser.add_argument("--owner", required=True, help="owner identifier")
    lease_heartbeat_parser.add_argument("--ttl-seconds", dest="ttl_seconds", type=int, default=300, help="new TTL in seconds (default 300)")
    lease_heartbeat_parser.add_argument("--format", choices=("text", "json"), default="text")
    lease_heartbeat_parser.set_defaults(handler=run_runtime_manager)
    lease_list_parser = runtime_manager_lease_subparsers.add_parser("list", help="list managed leases")
    lease_list_parser.add_argument("--observation-id", dest="observation_id", default=None, help="filter by observation_id")
    lease_list_parser.add_argument("--limit", type=int, default=50, help="max rows (default 50; 0=all)")
    lease_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    lease_list_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_lease_parser.set_defaults(handler=run_runtime_manager)

    # stop subcommand
    runtime_manager_stop_parser = runtime_manager_subparsers.add_parser(
        "stop",
        help="manage write-API stop conditions (raise, resolve, list)",
        description="Manage runtime-owned stop conditions. A raised stop blocks observation selection until resolved.",
    )
    runtime_manager_stop_subparsers = runtime_manager_stop_parser.add_subparsers(
        dest="stop_command", required=True
    )
    stop_raise_parser = runtime_manager_stop_subparsers.add_parser("raise", help="raise a stop condition")
    stop_raise_parser.add_argument("subject_id", help="observation_id, 'runtime-manager', or '*' (global)")
    stop_raise_parser.add_argument("--reason", default="", help="human-readable reason")
    stop_raise_parser.add_argument("--severity", default="blocking", choices=("blocking", "informational"), help="severity (default blocking)")
    stop_raise_parser.add_argument("--format", choices=("text", "json"), default="text")
    stop_raise_parser.set_defaults(handler=run_runtime_manager)
    stop_resolve_parser = runtime_manager_stop_subparsers.add_parser("resolve", help="resolve a stop condition")
    stop_resolve_parser.add_argument("stop_condition_id", help="stop_condition_id to resolve")
    stop_resolve_parser.add_argument("--format", choices=("text", "json"), default="text")
    stop_resolve_parser.set_defaults(handler=run_runtime_manager)
    stop_list_parser = runtime_manager_stop_subparsers.add_parser("list", help="list managed stop conditions")
    stop_list_parser.add_argument("--subject-id", dest="subject_id", default=None, help="filter by subject_id")
    stop_list_parser.add_argument("--limit", type=int, default=50, help="max rows (default 50; 0=all)")
    stop_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    stop_list_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_stop_parser.set_defaults(handler=run_runtime_manager)

    # validation subcommand
    runtime_manager_validation_parser = runtime_manager_subparsers.add_parser(
        "validation",
        help="manage write-API validations (record, show)",
        description="Record or inspect runtime-owned validation records. A green record with valid fresh_until satisfies a validation gate.",
    )
    runtime_manager_validation_subparsers = runtime_manager_validation_parser.add_subparsers(
        dest="validation_command", required=True
    )
    validation_record_parser = runtime_manager_validation_subparsers.add_parser("record", help="record a validation result")
    validation_record_parser.add_argument("validation_id", help="validation gate id")
    validation_record_parser.add_argument("subject_id", help="observation_id this validation applies to")
    validation_record_parser.add_argument("--status", default="green", choices=("green", "red", "stale"), help="validation status (default green)")
    validation_record_parser.add_argument("--ttl-seconds", dest="ttl_seconds", type=int, default=0, help="freshness TTL; 0=no expiry")
    validation_record_parser.add_argument("--reason", default="", help="optional reason text")
    validation_record_parser.add_argument("--command-id", dest="command_id", default="", help="optional associated command_id")
    validation_record_parser.add_argument("--format", choices=("text", "json"), default="text")
    validation_record_parser.set_defaults(handler=run_runtime_manager)
    validation_show_parser = runtime_manager_validation_subparsers.add_parser("show", help="show a managed validation record")
    validation_show_parser.add_argument("validation_id", help="validation gate id to look up")
    validation_show_parser.add_argument("--format", choices=("text", "json"), default="text")
    validation_show_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_validation_parser.set_defaults(handler=run_runtime_manager)

    # approval subcommand
    runtime_manager_approval_parser = runtime_manager_subparsers.add_parser(
        "approval",
        help="manage write-API approvals (record, revoke, list)",
        description="Record or revoke runtime-owned approval records. Core computes the action fingerprint from the command registry.",
    )
    runtime_manager_approval_subparsers = runtime_manager_approval_parser.add_subparsers(
        dest="approval_command", required=True
    )
    approval_record_parser = runtime_manager_approval_subparsers.add_parser("record", help="record an approval")
    approval_record_parser.add_argument("command_id", help="registered command_id to approve")
    approval_record_parser.add_argument("subject_id", help="observation_id this approval applies to")
    approval_record_parser.add_argument("--actor", default="cli", help="actor granting the approval (default: cli)")
    approval_record_parser.add_argument("--scope", default="single-use", help="approval scope (default: single-use)")
    approval_record_parser.add_argument("--expires-at", dest="expires_at", default="", help="optional ISO-8601 expiry timestamp")
    approval_record_parser.add_argument("--format", choices=("text", "json"), default="text")
    approval_record_parser.set_defaults(handler=run_runtime_manager)
    approval_revoke_parser = runtime_manager_approval_subparsers.add_parser("revoke", help="revoke an approval")
    approval_revoke_parser.add_argument("approval_id", help="approval_id to revoke")
    approval_revoke_parser.add_argument("--format", choices=("text", "json"), default="text")
    approval_revoke_parser.set_defaults(handler=run_runtime_manager)
    approval_list_parser = runtime_manager_approval_subparsers.add_parser("list", help="list managed approvals")
    approval_list_parser.add_argument("--subject-id", dest="subject_id", default=None, help="filter by subject_id")
    approval_list_parser.add_argument("--command-id", dest="command_id", default=None, help="filter by command_id")
    approval_list_parser.add_argument("--limit", type=int, default=50, help="max rows (default 50; 0=all)")
    approval_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    approval_list_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_approval_parser.set_defaults(handler=run_runtime_manager)

    # rollback subcommand
    runtime_manager_rollback_parser = runtime_manager_subparsers.add_parser(
        "rollback",
        help="execute a registered rollback or list past rollback runs",
        description="Execute the registered rollback for a forward execution evidence_id, or list past rollback runs.",
    )
    runtime_manager_rollback_subparsers = runtime_manager_rollback_parser.add_subparsers(
        dest="rollback_subcommand", required=False
    )
    rollback_list_parser = runtime_manager_rollback_subparsers.add_parser("list", help="list rollback runs")
    rollback_list_parser.add_argument("--forward-command-id", dest="forward_command_id", default=None, help="filter by forward command_id")
    rollback_list_parser.add_argument("--limit", type=int, default=50, help="max rows (default 50; 0=all)")
    rollback_list_parser.add_argument("--format", choices=("text", "json"), default="text")
    rollback_list_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_rollback_parser.add_argument("--evidence-id", dest="evidence_id", default=None, help="evidence_id of the forward run to roll back")
    runtime_manager_rollback_parser.add_argument("--format", choices=("text", "json"), default="text")
    runtime_manager_rollback_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_mcp_stdio_parser = runtime_manager_subparsers.add_parser(
        "mcp-stdio",
        help="start MCP STDIO server (token from env CEREBRO_RUNTIME_MCP_TOKEN)",
        description=(
            "Start a FastMCP STDIO server backed by the local runtime-manager store. "
            "The server authenticates using the CEREBRO_RUNTIME_MCP_TOKEN env var. "
            "No HTTP, no OAuth server, no TLS."
        ),
    )
    runtime_manager_mcp_stdio_parser.set_defaults(handler=run_runtime_manager)

    # policy subcommand
    runtime_manager_policy_parser = runtime_manager_subparsers.add_parser(
        "policy",
        help="classify or explain autonomy-level policy for registered commands",
        description="Read-only policy projection: classify a command's autonomy level or explain all levels. Classification is not permission.",
    )
    runtime_manager_policy_subparsers = runtime_manager_policy_parser.add_subparsers(
        dest="policy_subcommand", required=True
    )
    policy_classify_parser = runtime_manager_policy_subparsers.add_parser(
        "classify",
        help="classify the autonomy level for a registered command_id",
        description="Look up a command_id in the registry and return its autonomy level, required controls, and friction budget. Classification is not permission.",
    )
    policy_classify_parser.add_argument("command_id", help="command_id to classify")
    policy_classify_parser.add_argument("--format", choices=("text", "json"), default="text")
    policy_classify_parser.set_defaults(handler=run_runtime_manager)
    policy_explain_parser = runtime_manager_policy_subparsers.add_parser(
        "explain-levels",
        help="explain all autonomy levels (L0–L4) with friction budgets and controls",
        description="Print a structured description of all five autonomy levels. Classification is not permission.",
    )
    policy_explain_parser.add_argument("--format", choices=("text", "json"), default="text")
    policy_explain_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_policy_parser.set_defaults(handler=run_runtime_manager)

    runtime_manager_integrity_parser = runtime_manager_subparsers.add_parser(
        "integrity",
        help="run local integrity checks on runtime.db (advisory only, not a gate)",
        description="Diagnostic checks: orphan events, stale leases/tokens, missing traces, counter plausibility. Not permission.",
    )
    runtime_manager_integrity_subparsers = runtime_manager_integrity_parser.add_subparsers(
        dest="integrity_subcommand", required=True
    )
    integrity_check_parser = runtime_manager_integrity_subparsers.add_parser(
        "check",
        help="run all integrity checks and report findings",
        description="Run all runtime.db integrity checks. Report is diagnostic only — not a runtime gate.",
    )
    integrity_check_parser.add_argument("--format", choices=("text", "json"), default="text")
    integrity_check_parser.set_defaults(handler=run_runtime_manager)
    runtime_manager_integrity_parser.set_defaults(handler=run_runtime_manager)

    status_parser = add_command_parser(
        "status-export",
        help="render a short operational status from the current state",
        description="Export a compact read-only operational status derived from the canonical state.",
    )
    status_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
    )
    status_parser.add_argument("--out", help="explicit output file; prints to stdout when omitted")
    status_parser.set_defaults(handler=run_status_export)

    validation_export_parser = add_command_parser(
        "validation-export",
        help="render a short view of the last persisted validation result",
        description="Export a compact read-only validation view derived from the persisted canonical validation record.",
    )
    validation_export_parser.add_argument(
        "--format",
        choices=("md", "json"),
        default="md",
        help="output format; defaults to md",
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
        _walk_up = getattr(args, "command", None) != "init"
        root = find_project_root(explicit=getattr(args, "project_root", None), walk_up=_walk_up).path
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
