"""Validation helpers for the minimal checkpoint state."""

from __future__ import annotations

from pathlib import Path

from core.agent_runtime import (
    ACTION_RECORD_KEYS,
    AGENT_RUNTIME_KEYS,
    APPROVAL_RECORD_KEYS,
    APPROVALS_KEYS,
    AUDIT_KEYS,
    BATCH_REGISTRY_KEYS,
    COMMAND_RECORD_KEYS,
    COMMAND_REGISTRY_KEYS,
    EXECUTION_POLICY_KEYS,
    MAX_ACTION_HISTORY,
    MAX_APPROVAL_ITEMS,
    MAX_APPROVAL_REQUIRED_KINDS,
    MAX_BLOCKED_COMMAND_PREFIXES,
    MAX_COMMAND_REGISTRY_COMMANDS,
    MAX_MEMORY_NOTES,
    MAX_MEMORY_TTL_DAYS,
    MAX_PLAN_TASKS,
    MAX_PROTECTED_PATHS,
    MAX_ROLLBACK_POINTS,
    MAX_TASK_ACCEPTANCE_CRITERIA,
    MAX_TASK_WORKING_SET,
    MAX_USED_BATCH_IDS,
    MAX_VERIFICATION_CHECKS,
    MEMORY_KEYS,
    MEMORY_NOTE_KEYS,
    PLAN_KEYS,
    PLAN_TASK_KEYS,
    ROLLBACK_POINT_KEYS,
    action_belongs_to_current_plan,
    VALID_ACTION_KINDS,
    VALID_ACTION_STATUSES,
    VALID_APPROVAL_STATUSES,
    VALID_AUTONOMY_LEVELS,
    VALID_COMMAND_DETERMINISM,
    VALID_COMMAND_RISKS,
    VALID_COMMAND_SIDE_EFFECTS,
    VALID_MEMORY_KINDS,
    VALID_PLAN_STATUSES,
    VALID_ROLLBACK_KINDS,
    VALID_TASK_STATUSES,
    VALID_TRACE_INTEGRITIES,
    VALID_TRACE_STATUSES,
    VALID_VERIFICATION_STATUSES,
    VERIFICATION_CHECK_KEYS,
    VERIFICATION_KEYS,
    VERIFICATION_STATE_CHECK_KEYS,
    canonicalize_state_data,
)
from core.execution_policy import required_action_approval_error
from core.schema import (
    CHECKPOINT_KEYS,
    DETAIL_KEYS,
    LAST_VALIDATION_KEYS,
    MAX_CONSTRAINT_LENGTH,
    MAX_CONSTRAINTS,
    MAX_GOAL_LENGTH,
    MAX_NEXT_STEP_LENGTH,
    MAX_SOURCES,
    MAX_SUMMARY_LENGTH,
    MAX_VALIDATION_DETAILS,
    ROOT_KEYS,
    SESSION_KEYS,
    SOURCE_KEYS,
    VALID_RESULTS,
    VALID_SOURCE_ROLES,
)
from core.schema_policy import CURRENT_SCHEMA_VERSION, is_supported_schema_version


def error(code: str, message: str) -> dict:
    """Create a structured validation error."""
    return {"code": code, "message": message}


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _require_exact_keys(container: dict, expected: set[str], code: str, label: str) -> list[dict]:
    errors = []
    actual = set(container.keys())
    missing = sorted(expected - actual)
    extra = sorted(actual - expected)

    for key in missing:
        errors.append(error(code, f"{label} missing required key: {key}"))
    for key in extra:
        errors.append(error(code, f"{label} contains unexpected key: {key}"))
    return errors


def _is_valid_sha256(value: str) -> bool:
    return len(value) == 64 and all(char in "0123456789abcdef" for char in value)


def _validate_non_empty_string(value: object, code: str, label: str) -> list[dict]:
    if not isinstance(value, str) or not value:
        return [error(code, f"{label} must be a non-empty string")]
    return []


def _validate_string(value: object, code: str, label: str) -> list[dict]:
    if not isinstance(value, str):
        return [error(code, f"{label} must be a string")]
    return []


def _validate_string_list(
    value: object,
    *,
    code: str,
    label: str,
    max_items: int | None = None,
    require_non_empty_items: bool = True,
) -> list[dict]:
    errors: list[dict] = []
    if not isinstance(value, list):
        return [error(code, f"{label} must be an array")]
    if max_items is not None and len(value) > max_items:
        errors.append(error(code, f"{label} cannot contain more than {max_items} items"))
    for index, item in enumerate(value):
        if not isinstance(item, str) or (require_non_empty_items and not item):
            qualifier = "a non-empty string" if require_non_empty_items else "a string"
            errors.append(error(code, f"{label}[{index}] must be {qualifier}"))
    return errors


def _validate_checkpoint_block(checkpoint: object, prefix: str = "checkpoint") -> list[dict]:
    errors: list[dict] = []

    if not isinstance(checkpoint, dict):
        return [error("invalid_checkpoint", f"{prefix} must be an object")]

    errors.extend(_require_exact_keys(checkpoint, CHECKPOINT_KEYS, "invalid_checkpoint_keys", prefix))

    for key, max_length in (
        ("goal", MAX_GOAL_LENGTH),
        ("summary", MAX_SUMMARY_LENGTH),
        ("next_step", MAX_NEXT_STEP_LENGTH),
        ("updated_at", None),
    ):
        value = checkpoint.get(key)
        if not isinstance(value, str):
            errors.append(error("invalid_checkpoint_field", f"{prefix}.{key} must be a string"))
            continue
        if max_length is not None and len(value) > max_length:
            errors.append(
                error(
                    "invalid_checkpoint_field",
                    f"{prefix}.{key} exceeds maximum length of {max_length}",
                )
            )

    constraints = checkpoint.get("constraints")
    if not isinstance(constraints, list):
        errors.append(error("invalid_checkpoint_constraints", f"{prefix}.constraints must be an array"))
    else:
        if len(constraints) > MAX_CONSTRAINTS:
            errors.append(
                error(
                    "invalid_checkpoint_constraints",
                    f"{prefix}.constraints cannot contain more than {MAX_CONSTRAINTS} items",
                )
            )
        for index, item in enumerate(constraints):
            if not isinstance(item, str):
                errors.append(
                    error(
                        "invalid_checkpoint_constraint_item",
                        f"{prefix}.constraints[{index}] must be a string",
                    )
                )
                continue
            if len(item) > MAX_CONSTRAINT_LENGTH:
                errors.append(
                    error(
                        "invalid_checkpoint_constraint_item",
                        f"{prefix}.constraints[{index}] exceeds maximum length of {MAX_CONSTRAINT_LENGTH}",
                    )
                )

    return errors


def _validate_memory_block(memory: object, prefix: str = "agent_runtime") -> list[dict]:
    errors: list[dict] = []

    if not isinstance(memory, dict):
        errors.append(error("invalid_agent_memory", f"{prefix}.memory must be an object"))
    else:
        errors.extend(_require_exact_keys(memory, MEMORY_KEYS, "invalid_agent_memory_keys", f"{prefix}.memory"))
        notes = memory.get("notes")
        if not isinstance(notes, list):
            errors.append(error("invalid_agent_memory_notes", f"{prefix}.memory.notes must be an array"))
        else:
            if len(notes) > MAX_MEMORY_NOTES:
                errors.append(error("invalid_agent_memory_notes", f"{prefix}.memory.notes cannot contain more than {MAX_MEMORY_NOTES} items"))
            for index, note in enumerate(notes):
                note_prefix = f"{prefix}.memory.notes[{index}]"
                if not isinstance(note, dict):
                    errors.append(error("invalid_agent_memory_note_item", f"{note_prefix} must be an object"))
                    continue
                errors.extend(_require_exact_keys(note, MEMORY_NOTE_KEYS, "invalid_agent_memory_note_keys", note_prefix))
                for field in ("id", "summary", "source", "updated_at"):
                    errors.extend(
                        _validate_non_empty_string(
                            note.get(field),
                            "invalid_agent_memory_note_field",
                            f"{note_prefix}.{field}",
                        )
                    )
                kind = note.get("kind")
                if not isinstance(kind, str) or kind not in VALID_MEMORY_KINDS:
                    errors.append(
                        error(
                            "invalid_agent_memory_note_kind",
                            f"{note_prefix}.kind must be one of: {', '.join(sorted(VALID_MEMORY_KINDS))}",
                        )
                    )
                ttl_days = note.get("ttl_days")
                if not _is_int(ttl_days) or ttl_days < 0 or ttl_days > MAX_MEMORY_TTL_DAYS:
                    errors.append(
                        error(
                            "invalid_agent_memory_note_ttl_days",
                            f"{note_prefix}.ttl_days must be an integer between 0 and {MAX_MEMORY_TTL_DAYS}",
                        )
                    )

    return errors


def _validate_execution_policy_block(
    execution_policy: object,
    prefix: str = "agent_runtime",
) -> tuple[list[dict], list[str]]:
    errors: list[dict] = []
    approval_required_kinds: list[str] = []

    if not isinstance(execution_policy, dict):
        errors.append(error("invalid_execution_policy", f"{prefix}.execution_policy must be an object"))
    else:
        errors.extend(
            _require_exact_keys(
                execution_policy,
                EXECUTION_POLICY_KEYS,
                "invalid_execution_policy_keys",
                f"{prefix}.execution_policy",
            )
        )
        autonomy_level = execution_policy.get("autonomy_level")
        if not isinstance(autonomy_level, str) or autonomy_level not in VALID_AUTONOMY_LEVELS:
            errors.append(
                error(
                    "invalid_execution_policy_autonomy_level",
                    f"{prefix}.execution_policy.autonomy_level must be one of: {', '.join(sorted(VALID_AUTONOMY_LEVELS))}",
                )
            )
        errors.extend(
            _validate_string_list(
                execution_policy.get("protected_paths"),
                code="invalid_execution_policy_protected_paths",
                label=f"{prefix}.execution_policy.protected_paths",
                max_items=MAX_PROTECTED_PATHS,
            )
        )
        errors.extend(
            _validate_string_list(
                execution_policy.get("blocked_command_prefixes"),
                code="invalid_execution_policy_blocked_command_prefixes",
                label=f"{prefix}.execution_policy.blocked_command_prefixes",
                max_items=MAX_BLOCKED_COMMAND_PREFIXES,
            )
        )
        errors.extend(
            _validate_string_list(
                execution_policy.get("approval_required_kinds"),
                code="invalid_execution_policy_approval_required_kinds",
                label=f"{prefix}.execution_policy.approval_required_kinds",
                max_items=MAX_APPROVAL_REQUIRED_KINDS,
            )
        )
        raw_approval_required_kinds = execution_policy.get("approval_required_kinds")
        if isinstance(raw_approval_required_kinds, list):
            approval_required_kinds = [
                item
                for item in raw_approval_required_kinds
                if isinstance(item, str) and item
            ]

    return errors, approval_required_kinds


def _validate_batch_registry_block(
    batch_registry: object,
    prefix: str = "agent_runtime",
) -> tuple[list[dict], set[str]]:
    errors: list[dict] = []
    batch_registry_used_ids: set[str] = set()

    if not isinstance(batch_registry, dict):
        errors.append(error("invalid_agent_batch_registry", f"{prefix}.batch_registry must be an object"))
    else:
        errors.extend(_require_exact_keys(batch_registry, BATCH_REGISTRY_KEYS, "invalid_agent_batch_registry_keys", f"{prefix}.batch_registry"))
        used_ids = batch_registry.get("used_ids")
        if not isinstance(used_ids, list):
            errors.append(error("invalid_agent_batch_registry_used_ids", f"{prefix}.batch_registry.used_ids must be an array"))
        else:
            if len(used_ids) > MAX_USED_BATCH_IDS:
                errors.append(
                    error(
                        "invalid_agent_batch_registry_used_ids",
                        f"{prefix}.batch_registry.used_ids cannot contain more than {MAX_USED_BATCH_IDS} items",
                    )
                )
            for index, batch_id in enumerate(used_ids):
                errors.extend(
                    _validate_non_empty_string(
                        batch_id,
                        "invalid_agent_batch_registry_used_ids",
                        f"{prefix}.batch_registry.used_ids[{index}]",
                    )
                )
                if isinstance(batch_id, str) and batch_id:
                    if batch_id in batch_registry_used_ids:
                        errors.append(error("invalid_agent_batch_registry_used_ids", f"duplicate batch_id in registry: {batch_id}"))
                    else:
                        batch_registry_used_ids.add(batch_id)

    return errors, batch_registry_used_ids


def _validate_command_registry_block(
    command_registry: object,
    prefix: str = "agent_runtime",
) -> tuple[list[dict], set[str], set[str]]:
    errors: list[dict] = []
    command_ids: set[str] = set()
    allow_in_verify_command_ids: set[str] = set()

    if not isinstance(command_registry, dict):
        errors.append(error("invalid_command_registry", f"{prefix}.command_registry must be an object"))
    else:
        errors.extend(
            _require_exact_keys(
                command_registry,
                COMMAND_REGISTRY_KEYS,
                "invalid_command_registry_keys",
                f"{prefix}.command_registry",
            )
        )
        commands = command_registry.get("commands")
        if not isinstance(commands, list):
            errors.append(error("invalid_command_registry_commands", f"{prefix}.command_registry.commands must be an array"))
        else:
            if len(commands) > MAX_COMMAND_REGISTRY_COMMANDS:
                errors.append(
                    error(
                        "invalid_command_registry_commands",
                        f"{prefix}.command_registry.commands cannot contain more than {MAX_COMMAND_REGISTRY_COMMANDS} items",
                    )
                )
            for index, command in enumerate(commands):
                command_prefix = f"{prefix}.command_registry.commands[{index}]"
                if not isinstance(command, dict):
                    errors.append(error("invalid_command_registry_command_item", f"{command_prefix} must be an object"))
                    continue
                errors.extend(
                    _require_exact_keys(
                        command,
                        COMMAND_RECORD_KEYS,
                        "invalid_command_registry_command_keys",
                        command_prefix,
                    )
                )
                command_id = command.get("id")
                if not isinstance(command_id, str) or not command_id:
                    errors.append(error("invalid_command_registry_command_id", f"{command_prefix}.id must be a non-empty string"))
                elif command_id in command_ids:
                    errors.append(error("invalid_command_registry_commands", f"duplicate command id: {command_id}"))
                else:
                    command_ids.add(command_id)
                if isinstance(command_id, str) and command.get("allow_in_verify") is True:
                    allow_in_verify_command_ids.add(command_id)

                argv = command.get("argv")
                if not isinstance(argv, list) or not argv:
                    errors.append(error("invalid_command_registry_command_argv", f"{command_prefix}.argv must be a non-empty array"))
                else:
                    for arg_index, item in enumerate(argv):
                        if not isinstance(item, str) or not item:
                            errors.append(
                                error(
                                    "invalid_command_registry_command_argv_item",
                                    f"{command_prefix}.argv[{arg_index}] must be a non-empty string",
                                )
                            )
                errors.extend(
                    _validate_non_empty_string(
                        command.get("cwd"),
                        "invalid_command_registry_command_cwd",
                        f"{command_prefix}.cwd",
                    )
                )
                timeout_ms = command.get("timeout_ms")
                if not _is_int(timeout_ms) or timeout_ms <= 0:
                    errors.append(
                        error(
                            "invalid_command_registry_command_timeout_ms",
                            f"{command_prefix}.timeout_ms must be a positive integer",
                        )
                    )
                determinism = command.get("determinism")
                if not isinstance(determinism, str) or determinism not in VALID_COMMAND_DETERMINISM:
                    errors.append(
                        error(
                            "invalid_command_registry_command_determinism",
                            f"{command_prefix}.determinism must be one of: {', '.join(sorted(VALID_COMMAND_DETERMINISM))}",
                        )
                    )
                side_effect = command.get("side_effect")
                if not isinstance(side_effect, str) or side_effect not in VALID_COMMAND_SIDE_EFFECTS:
                    errors.append(
                        error(
                            "invalid_command_registry_command_side_effect",
                            f"{command_prefix}.side_effect must be one of: {', '.join(sorted(VALID_COMMAND_SIDE_EFFECTS))}",
                        )
                    )
                risk = command.get("risk")
                if not isinstance(risk, str) or risk not in VALID_COMMAND_RISKS:
                    errors.append(
                        error(
                            "invalid_command_registry_command_risk",
                            f"{command_prefix}.risk must be one of: {', '.join(sorted(VALID_COMMAND_RISKS))}",
                        )
                    )
                if not isinstance(command.get("allow_in_verify"), bool):
                    errors.append(
                        error(
                            "invalid_command_registry_command_allow_in_verify",
                            f"{command_prefix}.allow_in_verify must be a boolean",
                        )
                    )
                elif command.get("allow_in_verify") is True and side_effect != "read_only":
                    errors.append(
                        error(
                            "invalid_command_registry_command_verify_side_effect",
                            f"{command_prefix}.allow_in_verify requires {command_prefix}.side_effect to be read_only",
                        )
                    )

    return errors, command_ids, allow_in_verify_command_ids


def _validate_agent_runtime_block(agent_runtime: object, prefix: str = "agent_runtime") -> list[dict]:
    errors: list[dict] = []

    if not isinstance(agent_runtime, dict):
        return [error("invalid_agent_runtime", f"{prefix} must be an object")]

    errors.extend(_require_exact_keys(agent_runtime, AGENT_RUNTIME_KEYS, "invalid_agent_runtime_keys", prefix))

    task_ids: set[str] = set()
    task_statuses: dict[str, str] = {}
    task_dependencies: dict[str, list[str]] = {}
    action_ids_seen: set[str] = set()
    action_ids_by_task: dict[str, set[str]] = {}
    action_statuses: dict[str, str] = {}
    approval_ids: set[str] = set()
    approval_statuses: dict[str, str] = {}
    approval_items: list[dict] = []
    command_ids: set[str] = set()
    allow_in_verify_command_ids: set[str] = set()

    plan = agent_runtime.get("plan")
    if not isinstance(plan, dict):
        errors.append(error("invalid_agent_plan", f"{prefix}.plan must be an object"))
    else:
        errors.extend(_require_exact_keys(plan, PLAN_KEYS, "invalid_agent_plan_keys", f"{prefix}.plan"))
        for key in ("goal", "summary", "updated_at", "current_task_id", "generation_id"):
            errors.extend(_validate_string(plan.get(key), "invalid_agent_plan_field", f"{prefix}.plan.{key}"))

        plan_status = plan.get("status")
        if not isinstance(plan_status, str) or plan_status not in VALID_PLAN_STATUSES:
            errors.append(
                error(
                    "invalid_agent_plan_status",
                    f"{prefix}.plan.status must be one of: {', '.join(sorted(VALID_PLAN_STATUSES))}",
                )
            )

        tasks = plan.get("tasks")
        if not isinstance(tasks, list):
            errors.append(error("invalid_agent_plan_tasks", f"{prefix}.plan.tasks must be an array"))
        else:
            if len(tasks) > MAX_PLAN_TASKS:
                errors.append(
                    error(
                        "invalid_agent_plan_tasks",
                        f"{prefix}.plan.tasks cannot contain more than {MAX_PLAN_TASKS} items",
                    )
                )
            for index, task in enumerate(tasks):
                task_prefix = f"{prefix}.plan.tasks[{index}]"
                if not isinstance(task, dict):
                    errors.append(error("invalid_agent_plan_task_item", f"{task_prefix} must be an object"))
                    continue
                errors.extend(_require_exact_keys(task, PLAN_TASK_KEYS, "invalid_agent_plan_task_keys", task_prefix))
                for field in ("id", "title", "details"):
                    errors.extend(
                        _validate_non_empty_string(
                            task.get(field),
                            "invalid_agent_plan_task_field",
                            f"{task_prefix}.{field}",
                        )
                    )
                task_id = task.get("id")
                if isinstance(task_id, str) and task_id:
                    if task_id in task_ids:
                        errors.append(error("invalid_agent_plan_tasks", f"duplicate task id: {task_id}"))
                    task_ids.add(task_id)
                    task_statuses[task_id] = task.get("status", "")
                task_status = task.get("status")
                if not isinstance(task_status, str) or task_status not in VALID_TASK_STATUSES:
                    errors.append(
                        error(
                            "invalid_agent_plan_task_status",
                            f"{task_prefix}.status must be one of: {', '.join(sorted(VALID_TASK_STATUSES))}",
                        )
                    )

                depends_on = task.get("depends_on")
                errors.extend(
                    _validate_string_list(
                        depends_on,
                        code="invalid_agent_plan_task_depends_on",
                        label=f"{task_prefix}.depends_on",
                    )
                )
                if isinstance(task_id, str) and task_id and isinstance(depends_on, list):
                    task_dependencies[task_id] = depends_on

                errors.extend(
                    _validate_string_list(
                        task.get("working_set"),
                        code="invalid_agent_plan_task_working_set",
                        label=f"{task_prefix}.working_set",
                        max_items=MAX_TASK_WORKING_SET,
                    )
                )
                errors.extend(
                    _validate_string_list(
                        task.get("acceptance_criteria"),
                        code="invalid_agent_plan_task_acceptance_criteria",
                        label=f"{task_prefix}.acceptance_criteria",
                        max_items=MAX_TASK_ACCEPTANCE_CRITERIA,
                    )
                )
                errors.extend(
                    _validate_string_list(
                        task.get("action_ids"),
                        code="invalid_agent_plan_task_action_ids",
                        label=f"{task_prefix}.action_ids",
                    )
                )
                for field in ("retry_blocked_count", "verify_blocked_count", "apply_blocked_count"):
                    value = task.get(field)
                    if not _is_int(value) or value < 0:
                        errors.append(
                            error(
                                "invalid_agent_plan_task_field",
                                f"{task_prefix}.{field} must be a non-negative integer",
                            )
                        )
                if isinstance(task_id, str) and task_id and isinstance(task.get("action_ids"), list):
                    action_ids_by_task[task_id] = set(task["action_ids"])

        current_task_id = plan.get("current_task_id")
        if isinstance(current_task_id, str) and current_task_id and current_task_id not in task_ids:
            errors.append(
                error(
                    "invalid_agent_plan_current_task_id",
                    f"{prefix}.plan.current_task_id must reference an existing task id",
                )
            )

        if isinstance(tasks, list):
            if tasks and plan_status == "idle":
                errors.append(error("invalid_agent_plan_status", f"{prefix}.plan.status cannot be idle when tasks exist"))
            if not tasks and plan_status != "idle":
                errors.append(error("invalid_agent_plan_status", f"{prefix}.plan.status must be idle when no tasks exist"))
            if tasks and task_ids and all(task_statuses.get(task_id) == "done" for task_id in task_ids) and plan_status != "completed":
                errors.append(error("invalid_agent_plan_status", f"{prefix}.plan.status must be completed when all tasks are done"))

    execution_policy = agent_runtime.get("execution_policy")
    execution_policy_errors, approval_required_kinds = _validate_execution_policy_block(execution_policy, prefix)
    errors.extend(execution_policy_errors)

    command_registry = agent_runtime.get("command_registry")
    command_registry_errors, command_ids, allow_in_verify_command_ids = _validate_command_registry_block(
        command_registry,
        prefix,
    )
    errors.extend(command_registry_errors)

    approvals = agent_runtime.get("approvals")
    if not isinstance(approvals, dict):
        errors.append(error("invalid_agent_approvals", f"{prefix}.approvals must be an object"))
    else:
        errors.extend(_require_exact_keys(approvals, APPROVALS_KEYS, "invalid_agent_approvals_keys", f"{prefix}.approvals"))
        items = approvals.get("items")
        if not isinstance(items, list):
            errors.append(error("invalid_agent_approvals_items", f"{prefix}.approvals.items must be an array"))
        else:
            if len(items) > MAX_APPROVAL_ITEMS:
                errors.append(
                    error(
                        "invalid_agent_approvals_items",
                        f"{prefix}.approvals.items cannot contain more than {MAX_APPROVAL_ITEMS} items",
                    )
                )
            for index, approval in enumerate(items):
                approval_prefix = f"{prefix}.approvals.items[{index}]"
                if not isinstance(approval, dict):
                    errors.append(error("invalid_agent_approval_item", f"{approval_prefix} must be an object"))
                    continue
                errors.extend(
                    _require_exact_keys(
                        approval,
                        APPROVAL_RECORD_KEYS,
                        "invalid_agent_approval_keys",
                        approval_prefix,
                    )
                )
                for field in ("id", "fingerprint", "action_kind", "target", "reason", "requested_at"):
                    errors.extend(
                        _validate_non_empty_string(
                            approval.get(field),
                            "invalid_agent_approval_field",
                            f"{approval_prefix}.{field}",
                        )
                    )
                errors.extend(
                    _validate_string(
                        approval.get("task_id"),
                        "invalid_agent_approval_field",
                        f"{approval_prefix}.task_id",
                    )
                )
                errors.extend(
                    _validate_string(
                        approval.get("resolved_at"),
                        "invalid_agent_approval_field",
                        f"{approval_prefix}.resolved_at",
                    )
                )
                approval_id = approval.get("id")
                if isinstance(approval_id, str) and approval_id:
                    if approval_id in approval_ids:
                        errors.append(error("invalid_agent_approvals_items", f"duplicate approval id: {approval_id}"))
                    approval_ids.add(approval_id)
                    approval_statuses[approval_id] = approval.get("status", "")
                    approval_items.append(approval)
                status = approval.get("status")
                if not isinstance(status, str) or status not in VALID_APPROVAL_STATUSES:
                    errors.append(
                        error(
                            "invalid_agent_approval_status",
                            f"{approval_prefix}.status must be one of: {', '.join(sorted(VALID_APPROVAL_STATUSES))}",
                        )
                    )
                elif status == "pending" and approval.get("resolved_at"):
                    errors.append(error("invalid_agent_approval_status", f"{approval_prefix}.resolved_at must be empty for pending approvals"))
                elif status in {"approved", "rejected"} and not approval.get("resolved_at"):
                    errors.append(error("invalid_agent_approval_status", f"{approval_prefix}.resolved_at must be set once approval is resolved"))
                approval_task_id = approval.get("task_id")
                if isinstance(approval_task_id, str) and approval_task_id and approval_task_id not in task_ids:
                    errors.append(error("invalid_agent_approval_field", f"{approval_prefix}.task_id references unknown task id: {approval_task_id}"))

    actions = agent_runtime.get("actions")
    if not isinstance(actions, list):
        errors.append(error("invalid_agent_actions", f"{prefix}.actions must be an array"))
    else:
        if len(actions) > MAX_ACTION_HISTORY:
            errors.append(
                error(
                    "invalid_agent_actions",
                    f"{prefix}.actions cannot contain more than {MAX_ACTION_HISTORY} items",
                )
            )
        for index, action in enumerate(actions):
            action_prefix = f"{prefix}.actions[{index}]"
            if not isinstance(action, dict):
                errors.append(error("invalid_agent_action_item", f"{action_prefix} must be an object"))
                continue
            errors.extend(_require_exact_keys(action, ACTION_RECORD_KEYS, "invalid_agent_action_keys", action_prefix))
            action_id = action.get("id")
            if not isinstance(action_id, str) or not action_id:
                errors.append(error("invalid_agent_action_id", f"{action_prefix}.id must be a non-empty string"))
            elif action_id in action_ids_seen:
                errors.append(error("invalid_agent_actions", f"duplicate action id: {action_id}"))
            else:
                action_ids_seen.add(action_id)
                action_statuses[action_id] = action.get("status", "")
            kind = action.get("kind")
            if not isinstance(kind, str) or kind not in VALID_ACTION_KINDS:
                errors.append(
                    error(
                        "invalid_agent_action_kind",
                        f"{action_prefix}.kind must be one of: {', '.join(sorted(VALID_ACTION_KINDS))}",
                    )
                )
            status = action.get("status")
            if not isinstance(status, str) or status not in VALID_ACTION_STATUSES:
                errors.append(
                    error(
                        "invalid_agent_action_status",
                        f"{action_prefix}.status must be one of: {', '.join(sorted(VALID_ACTION_STATUSES))}",
                    )
                )
            for field in ("summary", "target", "task_id", "batch_id", "approval_id", "rollback_ref", "updated_at"):
                errors.extend(_validate_string(action.get(field), "invalid_agent_action_field", f"{action_prefix}.{field}"))
            if not isinstance(action.get("details"), dict):
                errors.append(error("invalid_agent_action_details", f"{action_prefix}.details must be an object"))
            errors.extend(
                _validate_string_list(
                    action.get("artifact_refs"),
                    code="invalid_agent_action_artifact_refs",
                    label=f"{action_prefix}.artifact_refs",
                )
            )

    batch_registry = agent_runtime.get("batch_registry")
    batch_registry_errors, batch_registry_used_ids = _validate_batch_registry_block(batch_registry, prefix)
    errors.extend(batch_registry_errors)

    verification = agent_runtime.get("verification")
    if not isinstance(verification, dict):
        errors.append(error("invalid_agent_verification", f"{prefix}.verification must be an object"))
    else:
        errors.extend(
            _require_exact_keys(
                verification,
                VERIFICATION_KEYS,
                "invalid_agent_verification_keys",
                f"{prefix}.verification",
            )
        )
        errors.extend(_validate_string(verification.get("last_run_at"), "invalid_agent_verification_field", f"{prefix}.verification.last_run_at"))
        verification_status = verification.get("status")
        if not isinstance(verification_status, str) or verification_status not in VALID_VERIFICATION_STATUSES:
            errors.append(
                error(
                    "invalid_agent_verification_status",
                    f"{prefix}.verification.status must be one of: {', '.join(sorted(VALID_VERIFICATION_STATUSES))}",
                )
            )
        errors.extend(
            _validate_string_list(
                verification.get("required_command_ids"),
                code="invalid_agent_verification_required_command_ids",
                label=f"{prefix}.verification.required_command_ids",
            )
        )
        errors.extend(
            _validate_string_list(
                verification.get("pending_action_ids"),
                code="invalid_agent_verification_pending_action_ids",
                label=f"{prefix}.verification.pending_action_ids",
            )
        )
        failed_attempt_count = verification.get("failed_attempt_count")
        if not _is_int(failed_attempt_count) or failed_attempt_count < 0:
            errors.append(
                error(
                    "invalid_agent_verification_failed_attempt_count",
                    f"{prefix}.verification.failed_attempt_count must be a non-negative integer",
                )
            )
        state_check = verification.get("state_check")
        if not isinstance(state_check, dict):
            errors.append(error("invalid_agent_verification_state_check", f"{prefix}.verification.state_check must be an object"))
        else:
            errors.extend(
                _require_exact_keys(
                    state_check,
                    VERIFICATION_STATE_CHECK_KEYS,
                    "invalid_agent_verification_state_check_keys",
                    f"{prefix}.verification.state_check",
                )
            )
            state_check_status = state_check.get("status")
            if not isinstance(state_check_status, str) or state_check_status not in VALID_VERIFICATION_STATUSES:
                errors.append(
                    error(
                        "invalid_agent_verification_state_check_status",
                        f"{prefix}.verification.state_check.status must be one of: {', '.join(sorted(VALID_VERIFICATION_STATUSES))}",
                    )
                )
            state_check_exit_code = state_check.get("exit_code")
            if not _is_int(state_check_exit_code):
                errors.append(
                    error(
                        "invalid_agent_verification_state_check_exit_code",
                        f"{prefix}.verification.state_check.exit_code must be an integer",
                    )
                )
            errors.extend(
                _validate_string(
                    state_check.get("message"),
                    "invalid_agent_verification_state_check_field",
                    f"{prefix}.verification.state_check.message",
                )
            )
        checks = verification.get("checks")
        if not isinstance(checks, list):
            errors.append(error("invalid_agent_verification_checks", f"{prefix}.verification.checks must be an array"))
        else:
            if len(checks) > MAX_VERIFICATION_CHECKS:
                errors.append(
                    error(
                        "invalid_agent_verification_checks",
                        f"{prefix}.verification.checks cannot contain more than {MAX_VERIFICATION_CHECKS} items",
                    )
                )
            for index, check in enumerate(checks):
                check_prefix = f"{prefix}.verification.checks[{index}]"
                if not isinstance(check, dict):
                    errors.append(error("invalid_agent_verification_check_item", f"{check_prefix} must be an object"))
                    continue
                errors.extend(
                    _require_exact_keys(
                        check,
                        VERIFICATION_CHECK_KEYS,
                        "invalid_agent_verification_check_keys",
                        check_prefix,
                    )
                )
                for field in ("id", "command_id", "artifact_ref", "artifact_sha256", "message"):
                    errors.extend(_validate_string(check.get(field), "invalid_agent_verification_check_field", f"{check_prefix}.{field}"))
                artifact_sha256 = check.get("artifact_sha256")
                if isinstance(artifact_sha256, str) and artifact_sha256 and not _is_valid_sha256(artifact_sha256):
                    errors.append(
                        error(
                            "invalid_agent_verification_check_field",
                            f"{check_prefix}.artifact_sha256 must be a 64-character lowercase hex string",
                        )
                    )
                errors.extend(
                    _validate_string_list(
                        check.get("covered_action_ids"),
                        code="invalid_agent_verification_check_covered_action_ids",
                        label=f"{check_prefix}.covered_action_ids",
                    )
                )
                status = check.get("status")
                if not isinstance(status, str) or status not in {"passed", "failed"}:
                    errors.append(error("invalid_agent_verification_check_status", f"{check_prefix}.status must be one of: failed, passed"))
                exit_code = check.get("exit_code")
                if not _is_int(exit_code):
                    errors.append(error("invalid_agent_verification_check_exit_code", f"{check_prefix}.exit_code must be an integer"))

    memory = agent_runtime.get("memory")
    errors.extend(_validate_memory_block(memory, prefix))

    audit = agent_runtime.get("audit")
    if not isinstance(audit, dict):
        errors.append(error("invalid_agent_audit", f"{prefix}.audit must be an object"))
    else:
        errors.extend(_require_exact_keys(audit, AUDIT_KEYS, "invalid_agent_audit_keys", f"{prefix}.audit"))
        for field in (
            "last_event_at",
            "last_event_type",
            "last_action_id",
            "active_session_id",
            "active_session_claim_id",
            "trace_thread_id",
            "last_trace_error_at",
            "last_trace_error",
        ):
            errors.extend(_validate_string(audit.get(field), "invalid_agent_audit_field", f"{prefix}.audit.{field}"))
        active_session_id = audit.get("active_session_id", "")
        active_session_claim_id = audit.get("active_session_claim_id", "")
        if bool(active_session_id) != bool(active_session_claim_id):
            errors.append(
                error(
                    "invalid_agent_audit_field",
                    f"{prefix}.audit.active_session_id and {prefix}.audit.active_session_claim_id must both be empty or both be non-empty",
                )
            )
        next_event_id = audit.get("next_event_id")
        if not _is_int(next_event_id) or next_event_id < 1:
            errors.append(error("invalid_agent_audit_field", f"{prefix}.audit.next_event_id must be an integer greater than or equal to 1"))
        trace_status = audit.get("trace_status")
        if not isinstance(trace_status, str) or trace_status not in VALID_TRACE_STATUSES:
            errors.append(
                error(
                    "invalid_agent_audit_field",
                    f"{prefix}.audit.trace_status must be one of: {', '.join(sorted(VALID_TRACE_STATUSES))}",
                )
            )
        trace_integrity = audit.get("trace_integrity")
        if not isinstance(trace_integrity, str) or trace_integrity not in VALID_TRACE_INTEGRITIES:
            errors.append(
                error(
                    "invalid_agent_audit_field",
                    f"{prefix}.audit.trace_integrity must be one of: {', '.join(sorted(VALID_TRACE_INTEGRITIES))}",
                )
            )
        rollback_points = audit.get("rollback_points")
        if not isinstance(rollback_points, list):
            errors.append(error("invalid_agent_audit_rollback_points", f"{prefix}.audit.rollback_points must be an array"))
        else:
            if len(rollback_points) > MAX_ROLLBACK_POINTS:
                errors.append(
                    error(
                        "invalid_agent_audit_rollback_points",
                        f"{prefix}.audit.rollback_points cannot contain more than {MAX_ROLLBACK_POINTS} items",
                    )
                )
            for index, rollback_point in enumerate(rollback_points):
                rollback_prefix = f"{prefix}.audit.rollback_points[{index}]"
                if not isinstance(rollback_point, dict):
                    errors.append(error("invalid_agent_audit_rollback_point_item", f"{rollback_prefix} must be an object"))
                    continue
                errors.extend(
                    _require_exact_keys(
                        rollback_point,
                        ROLLBACK_POINT_KEYS,
                        "invalid_agent_audit_rollback_point_keys",
                        rollback_prefix,
                    )
                )
                for field in ("id", "artifact_ref", "created_at"):
                    errors.extend(
                        _validate_non_empty_string(
                            rollback_point.get(field),
                            "invalid_agent_audit_rollback_point_field",
                            f"{rollback_prefix}.{field}",
                        )
                    )
                kind = rollback_point.get("kind")
                if not isinstance(kind, str) or kind not in VALID_ROLLBACK_KINDS:
                    errors.append(
                        error(
                            "invalid_agent_audit_rollback_point_kind",
                            f"{rollback_prefix}.kind must be one of: {', '.join(sorted(VALID_ROLLBACK_KINDS))}",
                        )
                    )
    for task_id, depends_on in task_dependencies.items():
        for dep in depends_on:
            if dep == task_id:
                errors.append(error("invalid_agent_plan_task_depends_on", f"task {task_id} cannot depend on itself"))
            elif dep not in task_ids:
                errors.append(error("invalid_agent_plan_task_depends_on", f"task {task_id} depends on unknown task id: {dep}"))
        if task_statuses.get(task_id) in {"ready", "running", "done"} and any(
            task_statuses.get(dep) != "done" for dep in depends_on if dep in task_statuses
        ):
            errors.append(
                error(
                    "invalid_agent_plan_task_status",
                    f"task {task_id} cannot be {task_statuses[task_id]!r} while dependencies are incomplete",
                )
            )

    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(task_id: str) -> None:
        if task_id in visited:
            return
        if task_id in visiting:
            errors.append(error("invalid_agent_plan_tasks", f"plan dependencies must form a DAG; cycle detected at {task_id}"))
            return
        visiting.add(task_id)
        for dep in task_dependencies.get(task_id, []):
            if dep in task_dependencies:
                visit(dep)
        visiting.remove(task_id)
        visited.add(task_id)

    for task_id in task_dependencies:
        visit(task_id)

    executable_task_ids = {
        task_id
        for task_id, status in task_statuses.items()
        if status in {"ready", "running"}
    }

    if isinstance(audit, dict):
        last_action_id = audit.get("last_action_id", "")
        if isinstance(last_action_id, str) and last_action_id and last_action_id not in action_ids_seen:
            errors.append(error("invalid_agent_audit_field", f"{prefix}.audit.last_action_id must reference an existing action id"))

    for task_id, task_action_ids in action_ids_by_task.items():
        for action_id in task_action_ids:
            if action_id not in action_ids_seen:
                errors.append(error("invalid_agent_plan_task_action_ids", f"task {task_id} references unknown action id: {action_id}"))

    for action in actions if isinstance(actions, list) else []:
        if not isinstance(action, dict):
            continue
        action_id = action.get("id")
        task_id = action.get("task_id")
        batch_id = action.get("batch_id")
        current_plan_action = action_belongs_to_current_plan(agent_runtime, action)
        if current_plan_action and isinstance(task_id, str) and task_id:
            if task_id not in task_ids:
                errors.append(error("invalid_agent_action_field", f"action {action_id} references unknown task id: {task_id}"))
            elif isinstance(action_id, str) and action_id and action_id not in action_ids_by_task.get(task_id, set()):
                errors.append(error("invalid_agent_action_field", f"task {task_id} must include action {action_id} in action_ids"))
        approval_id = action.get("approval_id")
        if isinstance(approval_id, str) and approval_id:
            if approval_id not in approval_ids:
                errors.append(error("invalid_agent_action_field", f"action {action_id} references unknown approval id: {approval_id}"))
            else:
                approval_status = approval_statuses.get(approval_id)
                action_status = action.get("status")
                if action_status == "pending_approval" and approval_status != "pending":
                    errors.append(error("invalid_agent_action_status", f"action {action_id} cannot be pending_approval with resolved approval {approval_id}"))
                if action_status == "applied" and approval_status == "rejected":
                    errors.append(error("invalid_agent_action_status", f"action {action_id} cannot be applied with rejected approval {approval_id}"))
        action_status = action.get("status")
        if action_status in {"applied", "failed", "rolled_back"}:
            approval = next(
                (
                    item
                    for item in approval_items
                    if isinstance(item, dict) and item.get("id") == approval_id
                ),
                None,
            )
            legacy_single_task_fallback = (
                isinstance(approval, dict)
                and not approval.get("task_id")
                and isinstance(task_id, str)
                and task_id
                and executable_task_ids == {task_id}
            )
            approval_error = required_action_approval_error(
                action,
                approval_id,
                approval_items,
                approval_required_kinds,
                action_task_id="" if legacy_single_task_fallback else None,
            )
            if approval_error:
                if isinstance(approval_id, str) and approval_id and approval_id not in approval_ids:
                    pass
                else:
                    errors.append(error("invalid_agent_action_status", f"action {action_id} {approval_error}"))
        if current_plan_action and isinstance(batch_id, str) and batch_id and batch_id not in batch_registry_used_ids:
            errors.append(error("invalid_agent_action_field", f"action {action_id} references unknown batch_id registry entry: {batch_id}"))

    if isinstance(verification, dict):
        required_command_ids = verification.get("required_command_ids", [])
        if isinstance(required_command_ids, list):
            for command_id in required_command_ids:
                if command_id not in command_ids:
                    errors.append(error("invalid_agent_verification_required_command_ids", f"unknown verification command id: {command_id}"))
                elif command_id not in allow_in_verify_command_ids:
                    errors.append(error("invalid_agent_verification_required_command_ids", f"command id is not allowed in verify: {command_id}"))

        pending_action_ids = verification.get("pending_action_ids", [])
        if isinstance(pending_action_ids, list):
            for action_id in pending_action_ids:
                if action_id not in action_ids_seen:
                    errors.append(error("invalid_agent_verification_pending_action_ids", f"unknown pending action id: {action_id}"))
                elif action_statuses.get(action_id) == "rolled_back":
                    errors.append(error("invalid_agent_verification_pending_action_ids", f"rolled back action cannot remain pending verification: {action_id}"))

        checks = verification.get("checks", [])
        has_failed_check = False
        if isinstance(checks, list):
            for check in checks:
                if not isinstance(check, dict):
                    continue
                gate = check.get("gate")
                command_id = check.get("command_id")
                if command_id not in command_ids:
                    errors.append(error("invalid_agent_verification_check_field", f"verification command_id must exist in command_registry: {command_id}"))
                covered_action_ids = check.get("covered_action_ids", [])
                if isinstance(covered_action_ids, list):
                    for action_id in covered_action_ids:
                        if action_id not in action_ids_seen:
                            errors.append(error("invalid_agent_verification_check_covered_action_ids", f"verification check references unknown action id: {action_id}"))
                if check.get("status") == "failed":
                    has_failed_check = True

        verification_status = verification.get("status")
        state_check_failed = isinstance(state_check, dict) and state_check.get("status") == "failed"
        if verification_status == "passed" and has_failed_check:
            errors.append(error("invalid_agent_verification_status", f"{prefix}.verification.status cannot be passed when checks failed"))
        if verification_status == "passed" and isinstance(pending_action_ids, list) and pending_action_ids:
            errors.append(error("invalid_agent_verification_status", f"{prefix}.verification.status cannot be passed while actions are pending verification"))
        if verification_status == "failed" and not has_failed_check and not state_check_failed and isinstance(pending_action_ids, list) and not pending_action_ids:
            errors.append(error("invalid_agent_verification_status", f"{prefix}.verification.status cannot be failed without a failing check or pending action"))

    return errors


def validate_session_data(session: object) -> list[dict]:
    """Validate in-memory local session data."""
    errors: list[dict] = []

    if not isinstance(session, dict):
        return [error("invalid_session", "session must be a JSON object")]

    errors.extend(_require_exact_keys(session, SESSION_KEYS, "invalid_session_keys", "session"))

    session_id = session.get("session_id")
    if not isinstance(session_id, str) or not session_id:
        errors.append(error("invalid_session_id", "session.session_id must be a non-empty string"))

    opened_at = session.get("opened_at")
    if not isinstance(opened_at, str) or not opened_at:
        errors.append(error("invalid_session_opened_at", "session.opened_at must be a non-empty string"))

    actor = session.get("actor")
    if not isinstance(actor, str) or not actor:
        errors.append(error("invalid_session_actor", "session.actor must be a non-empty string"))

    based_on_revision = session.get("based_on_revision")
    if not _is_int(based_on_revision) or based_on_revision < 0:
        errors.append(
            error(
                "invalid_session_based_on_revision",
                "session.based_on_revision must be a non-negative integer",
            )
        )

    owner_claim_id = session.get("owner_claim_id")
    if not isinstance(owner_claim_id, str) or not owner_claim_id:
        errors.append(
            error(
                "invalid_session_owner_claim_id",
                "session.owner_claim_id must be a non-empty string",
            )
        )

    return errors


def validate_state_data(state: object) -> list[dict]:
    """Validate in-memory state data against the minimal schema."""
    errors: list[dict] = []

    if not isinstance(state, dict):
        return [error("invalid_root", "state must be a JSON object")]

    normalized_state = canonicalize_state_data(state)
    if not isinstance(normalized_state, dict):
        return [error("invalid_root", "state must be a JSON object")]
    state = normalized_state

    errors.extend(_require_exact_keys(state, ROOT_KEYS, "invalid_root_keys", "state"))

    version = state.get("version")
    if not isinstance(version, str) or not version:
        errors.append(error("invalid_version", "version must be a non-empty string"))
    elif not is_supported_schema_version(version):
        errors.append(
            error(
                "unsupported_schema_version",
                f"version {version!r} is not supported by this runtime; expected {CURRENT_SCHEMA_VERSION!r}",
            )
        )

    revision = state.get("revision")
    if not _is_int(revision) or revision < 0:
        errors.append(error("invalid_revision", "revision must be a non-negative integer"))

    sources = state.get("sources")
    if not isinstance(sources, list):
        errors.append(error("invalid_sources", "sources must be an array"))
    else:
        if len(sources) > MAX_SOURCES:
            errors.append(error("invalid_sources", f"sources cannot contain more than {MAX_SOURCES} items"))

        seen_paths: set[str] = set()
        sorted_paths: list[str] = []
        for index, item in enumerate(sources):
            prefix = f"sources[{index}]"
            if not isinstance(item, dict):
                errors.append(error("invalid_source_item", f"{prefix} must be an object"))
                continue
            errors.extend(_require_exact_keys(item, SOURCE_KEYS, "invalid_source_keys", prefix))

            path = item.get("path")
            if not isinstance(path, str) or not path:
                errors.append(error("invalid_source_path", f"{prefix}.path must be a non-empty string"))
            else:
                candidate = Path(path)
                if candidate.is_absolute():
                    errors.append(error("invalid_source_path", f"{prefix}.path must be relative"))
                elif any(part == ".." for part in candidate.parts):
                    errors.append(error("invalid_source_path", f"{prefix}.path cannot contain '..'"))
                elif "\\" in path:
                    errors.append(error("invalid_source_path", f"{prefix}.path must use forward slashes"))
                if path in seen_paths:
                    errors.append(error("invalid_sources", f"duplicate source path: {path}"))
                seen_paths.add(path)
                sorted_paths.append(path)

            sha256 = item.get("sha256")
            if not isinstance(sha256, str) or not sha256:
                errors.append(error("invalid_source_sha256", f"{prefix}.sha256 must be a non-empty string"))
            elif not _is_valid_sha256(sha256):
                errors.append(error("invalid_source_sha256", f"{prefix}.sha256 must be a 64-character lowercase hex string"))

            role = item.get("role")
            if not isinstance(role, str) or role not in VALID_SOURCE_ROLES:
                errors.append(
                    error(
                        "invalid_source_role",
                        f"{prefix}.role must be one of: {', '.join(sorted(VALID_SOURCE_ROLES))}",
                    )
                )

        if sorted_paths != sorted(sorted_paths):
            errors.append(error("invalid_sources", "sources must be ordered lexically by path"))

    errors.extend(_validate_checkpoint_block(state.get("checkpoint")))

    last_validation = state.get("last_validation")
    if not isinstance(last_validation, dict):
        errors.append(error("invalid_last_validation", "last_validation must be an object"))
    else:
        errors.extend(
            _require_exact_keys(
                last_validation,
                LAST_VALIDATION_KEYS,
                "invalid_last_validation_keys",
                "last_validation",
            )
        )
        errors.extend(_validate_string(last_validation.get("validated_at"), "invalid_validated_at", "last_validation.validated_at"))

        result = last_validation.get("result")
        if not isinstance(result, str) or result not in VALID_RESULTS:
            errors.append(
                error(
                    "invalid_validation_result",
                    f"last_validation.result must be one of: {', '.join(sorted(VALID_RESULTS))}",
                )
            )

        details = last_validation.get("details")
        if not isinstance(details, list):
            errors.append(error("invalid_validation_details", "last_validation.details must be an array"))
        else:
            if len(details) > MAX_VALIDATION_DETAILS:
                errors.append(
                    error(
                        "invalid_validation_details",
                        f"last_validation.details cannot contain more than {MAX_VALIDATION_DETAILS} items",
                    )
                )
            for index, item in enumerate(details):
                prefix = f"last_validation.details[{index}]"
                if not isinstance(item, dict):
                    errors.append(error("invalid_validation_detail_item", f"{prefix} must be an object"))
                    continue
                errors.extend(_require_exact_keys(item, DETAIL_KEYS, "invalid_validation_detail_keys", prefix))
                errors.extend(_validate_non_empty_string(item.get("code"), "invalid_validation_detail_code", f"{prefix}.code"))
                errors.extend(_validate_non_empty_string(item.get("message"), "invalid_validation_detail_message", f"{prefix}.message"))

    errors.extend(_validate_agent_runtime_block(state.get("agent_runtime")))

    return errors
