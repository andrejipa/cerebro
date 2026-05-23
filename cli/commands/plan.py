"""Implementation of the alpha-runtime plan command."""

from __future__ import annotations

from pathlib import Path
import shlex

from cli.commands._session_ownership import resolve_session_token
from cli.commands._plan_input import load_plan_input
from cli.output import print_ambiguity, print_fail, print_ok, state_store_user_error, state_store_user_errors, user_error
from core.agent_runtime import (
    DEFAULT_APPROVAL_REQUIRED_KINDS,
    DEFAULT_BLOCKED_COMMAND_PREFIXES,
    DEFAULT_PROTECTED_PATHS,
)
from core.domain_input_adapter import DomainInputAdapterError, DomainInputAmbiguityError
from core.state_store import StateStore, StateStoreError, StateValidationError


def _build_plan_tasks(raw_tasks: list[str]) -> list[dict]:
    tasks: list[dict] = []
    for index, title in enumerate(raw_tasks, start=1):
        normalized_title = title.strip()
        if not normalized_title:
            raise StateStoreError("task titles must be non-empty strings")
        tasks.append(
            {
                "id": f"task-{index:03d}",
                "title": normalized_title,
                "status": "ready",
                "details": normalized_title,
                "depends_on": [],
                "working_set": [],
                "acceptance_criteria": [],
                "action_ids": [],
            }
        )
    return tasks


def _build_command_registry(raw_commands: list[str]) -> list[dict]:
    commands: list[dict] = []
    for index, raw_command in enumerate(raw_commands, start=1):
        normalized = raw_command.strip()
        if not normalized:
            raise StateStoreError("verification commands must be non-empty strings")
        argv = shlex.split(normalized, posix=False)
        if not argv:
            raise StateStoreError("verification commands must expand to a non-empty argv")
        commands.append(
            {
                "id": f"cmd-{index:03d}",
                "argv": argv,
                "cwd": ".",
                "timeout_ms": 120000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        )
    return commands


def _format_ambiguity_lines(ambiguity: DomainInputAmbiguityError) -> list[str]:
    lines = [
        f"ambiguity_type: {ambiguity.ambiguity_type}",
        f"ambiguity_level: {ambiguity.ambiguity_level}",
        "Possible interpretations:",
    ]
    for index, interpretation in enumerate(ambiguity.interpretations, start=1):
        lines.append(
            f"{index}. {interpretation['kind']} [{interpretation['confidence']}]: {interpretation['description']}"
        )
        lines.append(f"   difference: {interpretation['difference']}")
        lines.append(f"   impact: {interpretation['impact']}")
        lines.append(f"   reason: {interpretation['reason']}")
        lines.append(f"   select with: {interpretation['resolution']}")
    lines.append("Selection required: rerun `cerebro plan` with one explicit resolution path or rewrite the input to be more explicit.")
    return lines


def run_plan(root: Path, args) -> int:
    """Persist the alpha-runtime plan and verification registry."""
    store = StateStore(root)
    try:
        result = store.validate_state()
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    if not result["ok"]:
        print_fail(
            [
                user_error("plan_blocked", "plan blocked because validation failed"),
                *state_store_user_errors(root, result["errors"]),
            ]
        )
        return 1

    try:
        plan_input = load_plan_input(root, args)
        tasks = plan_input["tasks"] if plan_input["tasks"] is not None else _build_plan_tasks(args.task or [])
        command_registry = _build_command_registry(plan_input["verify_commands"])
        updated = store.update_agent_plan(
            {
                "goal": plan_input["goal"],
                "summary": plan_input["summary"],
                "tasks": tasks,
                "command_registry": command_registry,
                "required_command_ids": [command["id"] for command in command_registry],
                "autonomy_level": args.autonomy_level,
                "protected_paths": [*DEFAULT_PROTECTED_PATHS, *(args.protect_path or [])],
                "blocked_command_prefixes": [*DEFAULT_BLOCKED_COMMAND_PREFIXES, *(args.blocked_command or [])],
                "approval_required_kinds": [
                    *DEFAULT_APPROVAL_REQUIRED_KINDS,
                    *(getattr(args, "approval_required_kind", []) or []),
                ],
            },
            validated_revision=result["revision"],
            expected_session_token=resolve_session_token(args),
        )
    except DomainInputAmbiguityError as exc:
        print_ambiguity(_format_ambiguity_lines(exc))
        return 1
    except DomainInputAdapterError as exc:
        print_fail([user_error("domain_input_invalid", str(exc))])
        return 1
    except StateValidationError as exc:
        print_fail(exc.errors)
        return 1
    except StateStoreError as exc:
        print_fail([state_store_user_error(root, "operation_failed", str(exc))])
        return 1

    runtime = updated["agent_runtime"]
    print_ok(
        [
            "plan_saved: alpha runtime plan persisted",
            f"revision: {updated['revision']}",
            f"plan_status: {runtime['plan']['status']}",
            f"tasks: {len(runtime['plan']['tasks'])}",
            f"command_registry: {len(runtime['command_registry']['commands'])}",
            f"autonomy_level: {runtime['execution_policy']['autonomy_level']}",
        ]
    )
    return 0
