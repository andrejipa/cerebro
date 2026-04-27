"""Canonical runtime schema helpers for plans, actions, approvals, and verification."""

from __future__ import annotations

from copy import deepcopy

PLAN_KEYS = {
    "goal",
    "summary",
    "status",
    "current_task_id",
    "tasks",
    "generation_id",
    "updated_at",
}

PLAN_TASK_KEYS = {
    "id",
    "title",
    "status",
    "details",
    "depends_on",
    "working_set",
    "acceptance_criteria",
    "action_ids",
    "retry_blocked_count",
    "verify_blocked_count",
    "apply_blocked_count",
}

EXECUTION_POLICY_KEYS = {
    "autonomy_level",
    "protected_paths",
    "blocked_command_prefixes",
    "approval_required_kinds",
}

COMMAND_REGISTRY_KEYS = {
    "commands",
}

COMMAND_RECORD_KEYS = {
    "id",
    "argv",
    "cwd",
    "timeout_ms",
    "determinism",
    "side_effect",
    "risk",
    "allow_in_verify",
}

BATCH_REGISTRY_KEYS = {
    "used_ids",
}

APPROVALS_KEYS = {
    "items",
}

APPROVAL_RECORD_KEYS = {
    "id",
    "status",
    "fingerprint",
    "action_kind",
    "task_id",
    "target",
    "reason",
    "requested_at",
    "resolved_at",
}

ACTION_RECORD_KEYS = {
    "id",
    "kind",
    "status",
    "summary",
    "target",
    "task_id",
    "batch_id",
    "approval_id",
    "artifact_refs",
    "rollback_ref",
    "details",
    "updated_at",
}

# Optional keys that may appear in an action record but are not required.
ACTION_RECORD_OPTIONAL_KEYS: frozenset[str] = frozenset({"invariants"})

VERIFICATION_KEYS = {
    "required_command_ids",
    "pending_action_ids",
    "last_run_at",
    "status",
    "state_check",
    "checks",
    "failed_attempt_count",
}

VERIFICATION_STATE_CHECK_KEYS = {
    "status",
    "exit_code",
    "message",
}

VERIFICATION_CHECK_KEYS = {
    "id",
    "command_id",
    "status",
    "exit_code",
    "artifact_ref",
    "artifact_sha256",
    "covered_action_ids",
    "message",
}

MEMORY_KEYS = {
    "notes",
}

MEMORY_NOTE_KEYS = {
    "id",
    "kind",
    "summary",
    "source",
    "ttl_days",
    "updated_at",
}

AUDIT_KEYS = {
    "last_event_at",
    "last_event_type",
    "last_action_id",
    "active_session_id",
    "active_session_claim_id",
    "trace_thread_id",
    "next_event_id",
    "trace_status",
    "trace_integrity",
    "last_trace_error_at",
    "last_trace_error",
    "rollback_points",
}

ROLLBACK_POINT_KEYS = {
    "id",
    "kind",
    "artifact_ref",
    "created_at",
}

AGENT_RUNTIME_KEYS = {
    "plan",
    "execution_policy",
    "command_registry",
    "approvals",
    "actions",
    "batch_registry",
    "verification",
    "memory",
    "audit",
}

VALID_PLAN_STATUSES = {"idle", "ready", "blocked", "running", "completed"}
VALID_TASK_STATUSES = {"ready", "blocked", "running", "done", "failed"}
VALID_ACTION_KINDS = {
    "exec.command",
    "fs.create_file",
    "fs.delete_soft",
    "fs.move",
    "fs.write_patch",
    "read.checkpoint",
    "read.plan",
    "read.snapshot",
    "read.sources",
}
VALID_ACTION_STATUSES = {
    "planned",
    "pending_approval",
    "applied",
    "rolled_back",
    "blocked",
    "failed",
}
VALID_AUTONOMY_LEVELS = {"A0", "A1", "A2", "A3", "A4"}
VALID_VERIFICATION_STATUSES = {"idle", "passed", "failed"}
VALID_MEMORY_KINDS = {"context", "decision", "pitfall", "workflow"}
VALID_ROLLBACK_KINDS = {"preimage", "soft_delete", "batch"}
VALID_APPROVAL_STATUSES = {"pending", "approved", "rejected"}
VALID_COMMAND_DETERMINISM = {"high", "medium", "low"}
VALID_COMMAND_SIDE_EFFECTS = {"read_only", "workspace_write", "external_write"}
VALID_COMMAND_RISKS = {"low", "medium", "high"}
VALID_TRACE_STATUSES = {"healthy", "degraded"}
VALID_TRACE_INTEGRITIES = {"reliable", "partial"}

DEFAULT_PROTECTED_PATHS = [
    ".cerebro/**",
    ".git/**",
]
DEFAULT_BLOCKED_COMMAND_PREFIXES = [
    "del",
    "format",
    "git",
    "move",
    "rd",
    "ren",
    "rename",
    "rm",
    "rmdir",
]
DEFAULT_APPROVAL_REQUIRED_KINDS = [
    "exec.command",
    "fs.delete_soft",
    "fs.move",
    "fs.write_patch",
]

MAX_PLAN_TASKS = 64
MAX_ACTION_HISTORY = 64
MAX_COMMAND_REGISTRY_COMMANDS = 32
MAX_VERIFICATION_CHECKS = 32
MAX_MEMORY_NOTES = 64
MAX_ROLLBACK_POINTS = 32
MAX_APPROVAL_ITEMS = 64
MAX_USED_BATCH_IDS = 256
MAX_TASK_WORKING_SET = 16
MAX_TASK_ACCEPTANCE_CRITERIA = 16
MAX_PROTECTED_PATHS = 32
MAX_BLOCKED_COMMAND_PREFIXES = 32
MAX_APPROVAL_REQUIRED_KINDS = 16
MAX_MEMORY_TTL_DAYS = 365


def _value_or_default(container: dict, key: str, default: object) -> object:
    if key in container:
        return deepcopy(container[key])
    return deepcopy(default)


def build_initial_command_registry() -> dict:
    """Return the initial command-registry block."""
    return {"commands": []}


def build_initial_approvals() -> dict:
    """Return the initial approvals block."""
    return {"items": []}


def build_initial_agent_runtime() -> dict:
    """Return the latest canonical runtime block."""
    return {
        "plan": {
            "goal": "",
            "summary": "",
            "status": "idle",
            "current_task_id": "",
            "tasks": [],
            "generation_id": "",
            "updated_at": "",
        },
        "execution_policy": {
            "autonomy_level": "A1",
            "protected_paths": list(DEFAULT_PROTECTED_PATHS),
            "blocked_command_prefixes": list(DEFAULT_BLOCKED_COMMAND_PREFIXES),
            "approval_required_kinds": list(DEFAULT_APPROVAL_REQUIRED_KINDS),
        },
        "command_registry": build_initial_command_registry(),
        "approvals": build_initial_approvals(),
        "actions": [],
        "batch_registry": {
            "used_ids": [],
        },
        "verification": {
            "required_command_ids": [],
            "pending_action_ids": [],
            "last_run_at": "",
            "status": "idle",
            "state_check": {
                "status": "idle",
                "exit_code": 0,
                "message": "",
            },
            "checks": [],
            "failed_attempt_count": 0,
        },
        "memory": {
            "notes": [],
        },
        "audit": {
            "last_event_at": "",
            "last_event_type": "",
            "last_action_id": "",
            "active_session_id": "",
            "active_session_claim_id": "",
            "trace_thread_id": "bootstrap",
            "next_event_id": 1,
            "trace_status": "healthy",
            "trace_integrity": "reliable",
            "last_trace_error_at": "",
            "last_trace_error": "",
            "rollback_points": [],
        },
    }


def _canonicalize_plan(plan: object) -> dict:
    runtime_plan = deepcopy(build_initial_agent_runtime()["plan"])
    if not isinstance(plan, dict):
        return runtime_plan

    for key in ("goal", "summary", "status", "current_task_id", "generation_id", "updated_at"):
        runtime_plan[key] = _value_or_default(plan, key, runtime_plan[key])

    raw_tasks = plan.get("tasks", [])
    if not isinstance(raw_tasks, list):
        runtime_plan["tasks"] = deepcopy(raw_tasks)
        return runtime_plan

    tasks: list[object] = []
    for task in raw_tasks:
        if not isinstance(task, dict):
            tasks.append(deepcopy(task))
            continue
        tasks.append(
            {
                "id": _value_or_default(task, "id", ""),
                "title": _value_or_default(task, "title", ""),
                "status": _value_or_default(task, "status", "ready"),
                "details": _value_or_default(task, "details", ""),
                "depends_on": _value_or_default(task, "depends_on", []),
                "working_set": _value_or_default(task, "working_set", []),
                "acceptance_criteria": _value_or_default(task, "acceptance_criteria", []),
                "action_ids": _value_or_default(task, "action_ids", []),
                "retry_blocked_count": _value_or_default(task, "retry_blocked_count", 0),
                "verify_blocked_count": _value_or_default(task, "verify_blocked_count", 0),
                "apply_blocked_count": _value_or_default(task, "apply_blocked_count", 0),
            }
        )
    runtime_plan["tasks"] = tasks
    return runtime_plan


def _canonicalize_execution_policy(policy: object) -> dict:
    runtime_policy = deepcopy(build_initial_agent_runtime()["execution_policy"])
    if not isinstance(policy, dict):
        return runtime_policy

    for key in (
        "autonomy_level",
        "protected_paths",
        "blocked_command_prefixes",
        "approval_required_kinds",
    ):
        runtime_policy[key] = _value_or_default(policy, key, runtime_policy[key])
    return runtime_policy


def _canonicalize_command_registry(agent_runtime: dict) -> dict:
    registry = agent_runtime.get("command_registry")
    verification = agent_runtime.get("verification")
    runtime_registry = build_initial_command_registry()

    raw_commands: object = []
    if isinstance(registry, dict) and "commands" in registry:
        raw_commands = deepcopy(registry["commands"])
    elif isinstance(verification, dict) and "commands" in verification:
        raw_commands = deepcopy(verification["commands"])

    if not isinstance(raw_commands, list):
        runtime_registry["commands"] = raw_commands
        return runtime_registry

    commands: list[object] = []
    for index, command in enumerate(raw_commands, start=1):
        if not isinstance(command, dict):
            commands.append(deepcopy(command))
            continue
        commands.append(
            {
                "id": _value_or_default(command, "id", f"cmd-{index:03d}"),
                "argv": _value_or_default(command, "argv", []),
                "cwd": _value_or_default(command, "cwd", "."),
                "timeout_ms": _value_or_default(command, "timeout_ms", 120000),
                "determinism": _value_or_default(command, "determinism", "high"),
                "side_effect": _value_or_default(command, "side_effect", "read_only"),
                "risk": _value_or_default(command, "risk", "low"),
                "allow_in_verify": _value_or_default(command, "allow_in_verify", True),
            }
        )
    runtime_registry["commands"] = commands
    return runtime_registry


def _canonicalize_approvals(approvals: object) -> dict:
    runtime_approvals = build_initial_approvals()
    if not isinstance(approvals, dict):
        return runtime_approvals

    raw_items = approvals.get("items", [])
    if not isinstance(raw_items, list):
        runtime_approvals["items"] = deepcopy(raw_items)
        return runtime_approvals

    items: list[object] = []
    for approval in raw_items:
        if not isinstance(approval, dict):
            items.append(deepcopy(approval))
            continue
        items.append(
            {
                "id": _value_or_default(approval, "id", ""),
                "status": _value_or_default(approval, "status", "pending"),
                "fingerprint": _value_or_default(approval, "fingerprint", ""),
                "action_kind": _value_or_default(approval, "action_kind", ""),
                "task_id": _value_or_default(approval, "task_id", ""),
                "target": _value_or_default(approval, "target", ""),
                "reason": _value_or_default(approval, "reason", ""),
                "requested_at": _value_or_default(approval, "requested_at", ""),
                "resolved_at": _value_or_default(approval, "resolved_at", ""),
            }
        )
    runtime_approvals["items"] = items
    return runtime_approvals


def _canonicalize_actions(actions: object) -> list[object]:
    if not isinstance(actions, list):
        return deepcopy(actions)

    normalized: list[object] = []
    for action in actions:
        if not isinstance(action, dict):
            normalized.append(deepcopy(action))
            continue
        canonical_action: dict = {
                "id": _value_or_default(action, "id", ""),
                "kind": _value_or_default(action, "kind", ""),
                "status": _value_or_default(action, "status", "planned"),
                "summary": _value_or_default(action, "summary", ""),
                "target": _value_or_default(action, "target", ""),
                "task_id": _value_or_default(action, "task_id", ""),
                "batch_id": _value_or_default(action, "batch_id", ""),
                "approval_id": _value_or_default(action, "approval_id", ""),
                "artifact_refs": _value_or_default(action, "artifact_refs", []),
                "rollback_ref": _value_or_default(action, "rollback_ref", ""),
                "details": _value_or_default(action, "details", {}),
                "updated_at": _value_or_default(action, "updated_at", ""),
            }
        if "invariants" in action:
            canonical_action["invariants"] = deepcopy(action["invariants"])
        normalized.append(canonical_action)
    return normalized


def _canonicalize_verification(agent_runtime: dict, command_registry: dict) -> dict:
    runtime_verification = deepcopy(build_initial_agent_runtime()["verification"])
    verification = agent_runtime.get("verification")
    if not isinstance(verification, dict):
        runtime_verification["required_command_ids"] = [
            command["id"]
            for command in command_registry["commands"]
            if isinstance(command, dict) and command.get("allow_in_verify", True)
        ]
        return runtime_verification

    default_required_command_ids = [
        command["id"]
        for command in command_registry["commands"]
        if isinstance(command, dict) and command.get("allow_in_verify", True)
    ]
    runtime_verification["required_command_ids"] = _value_or_default(
        verification,
        "required_command_ids",
        default_required_command_ids,
    )
    runtime_verification["pending_action_ids"] = _value_or_default(
        verification,
        "pending_action_ids",
        [],
    )
    runtime_verification["last_run_at"] = _value_or_default(verification, "last_run_at", "")
    runtime_verification["status"] = _value_or_default(verification, "status", "idle")
    state_check = verification.get("state_check")
    if isinstance(state_check, dict):
        runtime_verification["state_check"] = {
            "status": _value_or_default(state_check, "status", "idle"),
            "exit_code": _value_or_default(state_check, "exit_code", 0),
            "message": _value_or_default(state_check, "message", ""),
        }
    failed_attempt_count = verification.get("failed_attempt_count", 0)
    if isinstance(failed_attempt_count, int) and failed_attempt_count >= 0:
        runtime_verification["failed_attempt_count"] = failed_attempt_count

    raw_checks = verification.get("checks", [])
    if not isinstance(raw_checks, list):
        runtime_verification["checks"] = deepcopy(raw_checks)
        return runtime_verification

    checks: list[object] = []
    for check in raw_checks:
        if not isinstance(check, dict):
            checks.append(deepcopy(check))
            continue
        if check.get("gate") == "state":
            runtime_verification["state_check"] = {
                "status": _value_or_default(check, "status", "failed"),
                "exit_code": _value_or_default(check, "exit_code", 1),
                "message": _value_or_default(check, "message", ""),
            }
            continue
        checks.append(
            {
                "id": _value_or_default(check, "id", ""),
                "command_id": _value_or_default(check, "command_id", ""),
                "status": _value_or_default(check, "status", "failed"),
                "exit_code": _value_or_default(check, "exit_code", 1),
                "artifact_ref": _value_or_default(check, "artifact_ref", ""),
                "artifact_sha256": _value_or_default(check, "artifact_sha256", ""),
                "covered_action_ids": _value_or_default(check, "covered_action_ids", []),
                "message": _value_or_default(check, "message", ""),
            }
        )
    runtime_verification["checks"] = checks
    return runtime_verification


def iter_command_checks(verification: object) -> tuple[dict, ...]:
    """Return only canonical command checks from one verification block."""
    if not isinstance(verification, dict):
        return ()
    raw_checks = verification.get("checks", [])
    if not isinstance(raw_checks, list):
        return ()
    checks: list[dict] = []
    for check in raw_checks:
        if not isinstance(check, dict):
            continue
        command_id = check.get("command_id")
        if not isinstance(command_id, str) or not command_id:
            continue
        checks.append(check)
    return tuple(checks)


def _canonicalize_memory(memory: object) -> dict:
    runtime_memory = deepcopy(build_initial_agent_runtime()["memory"])
    if not isinstance(memory, dict):
        return runtime_memory

    raw_notes = memory.get("notes", [])
    if not isinstance(raw_notes, list):
        runtime_memory["notes"] = deepcopy(raw_notes)
        return runtime_memory

    notes: list[object] = []
    for note in raw_notes:
        if not isinstance(note, dict):
            notes.append(deepcopy(note))
            continue
        notes.append(
            {
                "id": _value_or_default(note, "id", ""),
                "kind": _value_or_default(note, "kind", "context"),
                "summary": _value_or_default(note, "summary", ""),
                "source": _value_or_default(note, "source", ""),
                "ttl_days": _value_or_default(note, "ttl_days", 0),
                "updated_at": _value_or_default(note, "updated_at", ""),
            }
        )
    runtime_memory["notes"] = notes
    return runtime_memory


def _canonicalize_audit(audit: object) -> dict:
    runtime_audit = deepcopy(build_initial_agent_runtime()["audit"])
    if not isinstance(audit, dict):
        return runtime_audit

    for key in (
        "last_event_at",
        "last_event_type",
        "last_action_id",
        "active_session_id",
        "active_session_claim_id",
        "trace_thread_id",
        "trace_status",
        "trace_integrity",
        "last_trace_error_at",
        "last_trace_error",
    ):
        runtime_audit[key] = _value_or_default(audit, key, runtime_audit[key])

    next_event_id = audit.get("next_event_id", runtime_audit["next_event_id"])
    if isinstance(next_event_id, int) and next_event_id >= 1:
        runtime_audit["next_event_id"] = next_event_id

    raw_rollback_points = audit.get("rollback_points", [])
    if not isinstance(raw_rollback_points, list):
        runtime_audit["rollback_points"] = deepcopy(raw_rollback_points)
    else:
        rollback_points: list[object] = []
        for rollback_point in raw_rollback_points:
            if not isinstance(rollback_point, dict):
                rollback_points.append(deepcopy(rollback_point))
                continue
            rollback_points.append(
                {
                    "id": _value_or_default(rollback_point, "id", ""),
                    "kind": _value_or_default(rollback_point, "kind", "preimage"),
                    "artifact_ref": _value_or_default(rollback_point, "artifact_ref", ""),
                    "created_at": _value_or_default(rollback_point, "created_at", ""),
                }
            )
        runtime_audit["rollback_points"] = rollback_points

    return runtime_audit


def _canonicalize_batch_registry(agent_runtime: object) -> dict:
    runtime_batch_registry = deepcopy(build_initial_agent_runtime()["batch_registry"])
    registry_source = {}
    if isinstance(agent_runtime, dict):
        batch_registry = agent_runtime.get("batch_registry")
        if isinstance(batch_registry, dict):
            registry_source = batch_registry
        else:
            legacy_audit = agent_runtime.get("audit")
            if isinstance(legacy_audit, dict):
                registry_source = {"used_ids": legacy_audit.get("used_batch_ids", [])}
    used_ids = registry_source.get("used_ids", [])
    if isinstance(used_ids, list):
        runtime_batch_registry["used_ids"] = [
            batch_id
            for batch_id in used_ids
            if isinstance(batch_id, str) and batch_id
        ]
    else:
        runtime_batch_registry["used_ids"] = deepcopy(used_ids)
    return runtime_batch_registry


def canonicalize_agent_runtime(agent_runtime: object) -> dict:
    """Upgrade persisted runtime data into the latest in-memory shape."""
    runtime = deepcopy(build_initial_agent_runtime())
    if not isinstance(agent_runtime, dict):
        return runtime

    runtime["plan"] = _canonicalize_plan(agent_runtime.get("plan"))
    runtime["execution_policy"] = _canonicalize_execution_policy(agent_runtime.get("execution_policy"))
    runtime["command_registry"] = _canonicalize_command_registry(agent_runtime)
    runtime["approvals"] = _canonicalize_approvals(agent_runtime.get("approvals"))
    runtime["actions"] = _canonicalize_actions(agent_runtime.get("actions", []))
    runtime["batch_registry"] = _canonicalize_batch_registry(agent_runtime)
    runtime["verification"] = _canonicalize_verification(agent_runtime, runtime["command_registry"])
    runtime["memory"] = _canonicalize_memory(agent_runtime.get("memory"))
    runtime["audit"] = _canonicalize_audit(agent_runtime.get("audit"))
    return runtime


def canonicalize_state_data(state: object) -> object:
    """Canonicalize the runtime block for persisted state dictionaries."""
    if not isinstance(state, dict):
        return state
    if "agent_runtime" not in state:
        return deepcopy(state)
    runtime = canonicalize_agent_runtime(state["agent_runtime"])
    normalized = deepcopy(state)
    normalized["agent_runtime"] = runtime
    return normalized


def build_command_registry_map(agent_runtime: dict) -> dict[str, dict]:
    """Return commands keyed by id from the canonical command registry."""
    registry = agent_runtime.get("command_registry", {})
    commands = registry.get("commands", [])
    if not isinstance(commands, list):
        return {}
    return {
        command["id"]: command
        for command in commands
        if isinstance(command, dict) and isinstance(command.get("id"), str)
    }


def current_plan_generation_id(agent_runtime: dict) -> str:
    """Return the canonical generation marker for the current plan."""
    plan = agent_runtime.get("plan", {})
    if not isinstance(plan, dict):
        return ""
    generation_id = plan.get("generation_id", "")
    return generation_id if isinstance(generation_id, str) else ""


def action_belongs_to_current_plan(agent_runtime: dict, action: object) -> bool:
    """Return whether one retained action still belongs to the current plan generation."""
    if not isinstance(action, dict):
        return False

    details = action.get("details", {})
    action_plan_generation_id = ""
    if isinstance(details, dict):
        raw_plan_generation_id = details.get("plan_generation_id", "")
        if isinstance(raw_plan_generation_id, str):
            action_plan_generation_id = raw_plan_generation_id

    plan_generation_id = current_plan_generation_id(agent_runtime)
    if action_plan_generation_id:
        return bool(plan_generation_id) and action_plan_generation_id == plan_generation_id

    action_id = action.get("id", "")
    task_id = action.get("task_id", "")
    if not isinstance(action_id, str) or not action_id or not isinstance(task_id, str) or not task_id:
        return False

    plan = agent_runtime.get("plan", {})
    tasks = plan.get("tasks", []) if isinstance(plan, dict) else []
    if not isinstance(tasks, list):
        return False
    for task in tasks:
        if not isinstance(task, dict) or task.get("id") != task_id:
            continue
        action_ids = task.get("action_ids", [])
        return isinstance(action_ids, list) and action_id in action_ids
    return False
