"""Execution policy helpers for the alpha runtime."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath, PureWindowsPath


class ExecutionPolicyError(Exception):
    """Raised when an action violates the configured execution policy."""


def _normalize_relative_path(root: Path, candidate: Path) -> str:
    try:
        return candidate.resolve().relative_to(root.resolve()).as_posix()
    except ValueError as exc:
        raise ExecutionPolicyError(f"path resolves outside root: {candidate}") from exc


def ensure_mutation_path_allowed(
    root: Path,
    candidate: Path,
    protected_paths: list[str],
    registered_paths: set[str],
) -> str:
    """Reject protected paths, registered sources, and paths outside the workspace."""
    normalized = _normalize_relative_path(root, candidate)
    pure = PurePosixPath(normalized)
    if any(pure.match(pattern) for pattern in protected_paths):
        raise ExecutionPolicyError(f"path is protected by execution policy: {normalized}")
    if normalized in registered_paths:
        raise ExecutionPolicyError(f"path is reserved as a registered context source: {normalized}")
    return normalized


def ensure_command_allowed(
    autonomy_level: str,
    argv: list[str],
    blocked_prefixes: list[str],
) -> None:
    """Reject command execution when the active policy level blocks it."""
    if autonomy_level in {"A0", "A1"}:
        raise ExecutionPolicyError(
            f"autonomy level {autonomy_level} does not allow command execution"
        )
    if not argv:
        raise ExecutionPolicyError("command argv must be non-empty")
    head = argv[0].strip()
    aliases = _command_head_aliases(head)
    if not aliases:
        raise ExecutionPolicyError("command argv[0] must be a non-empty string")
    normalized_blocklist = {
        item.strip().lower()
        for item in blocked_prefixes
        if isinstance(item, str) and item.strip()
    }
    blocked_aliases = sorted(aliases & normalized_blocklist)
    if blocked_aliases:
        raise ExecutionPolicyError(
            f"command prefix is blocked by execution policy: {blocked_aliases[0]}"
        )


def _command_head_aliases(head: str) -> set[str]:
    normalized = head.strip().lower()
    if not normalized:
        return set()

    aliases = {normalized}
    for candidate in (PurePosixPath(normalized).name, PureWindowsPath(normalized).name):
        if not candidate:
            continue
        aliases.add(candidate)
        stem = candidate
        while True:
            next_stem = PurePosixPath(stem).stem
            if not next_stem or next_stem == stem:
                break
            aliases.add(next_stem)
            stem = next_stem
    return aliases


def _normalize_required_kinds(approval_required_kinds: list[str]) -> set[str]:
    return {
        item
        for item in approval_required_kinds
        if isinstance(item, str) and item
    }


def _action_kind(action: object) -> str:
    if isinstance(action, str):
        return action
    if isinstance(action, Mapping):
        kind = action.get("kind")
        if isinstance(kind, str):
            return kind
    return ""


def _action_target(action: object) -> str:
    if not isinstance(action, Mapping):
        return ""
    details = action.get("details")
    if isinstance(details, Mapping):
        for field in ("path", "to_path", "command_id"):
            value = details.get(field)
            if isinstance(value, str) and value:
                return value
    for field in ("target", "path", "to", "command_id"):
        value = action.get(field)
        if isinstance(value, str) and value:
            return value
    return ""


def _action_fingerprint(action: object) -> str:
    if not isinstance(action, Mapping):
        return ""
    details = action.get("details")
    if not isinstance(details, Mapping):
        return ""
    fingerprint = details.get("fingerprint")
    return fingerprint if isinstance(fingerprint, str) else ""


def _approval_lookup(approval_items_or_statuses: object) -> dict[str, dict]:
    lookup: dict[str, dict] = {}
    if isinstance(approval_items_or_statuses, Mapping):
        for approval_id, value in approval_items_or_statuses.items():
            if not isinstance(approval_id, str) or not approval_id:
                continue
            if isinstance(value, Mapping):
                lookup[approval_id] = {"id": approval_id, **value}
                continue
            if isinstance(value, str):
                lookup[approval_id] = {"id": approval_id, "status": value}
        return lookup
    if isinstance(approval_items_or_statuses, list):
        for item in approval_items_or_statuses:
            if not isinstance(item, Mapping):
                continue
            approval_id = item.get("id")
            if not isinstance(approval_id, str) or not approval_id:
                continue
            lookup[approval_id] = dict(item)
    return lookup


def _effect_requires_approval(action: object, *, target_exists: bool | None = None) -> bool:
    if not isinstance(action, Mapping):
        return False
    kind = _action_kind(action)
    details = action.get("details")

    if kind == "fs.create_file":
        if isinstance(details, Mapping):
            created_new = details.get("created_new")
            if created_new is False:
                return True
            if created_new is True:
                return False
        return action.get("overwrite") is True and target_exists is True

    if kind == "fs.move":
        if isinstance(details, Mapping):
            overwrote_target = details.get("overwrote_target")
            if overwrote_target is True:
                return True
            if overwrote_target is False:
                return False
        return action.get("overwrite") is True and target_exists is True

    return False


def action_requires_approval(
    action: object,
    approval_required_kinds: list[str],
    *,
    target_exists: bool | None = None,
) -> bool:
    """Return whether the current policy requires an approval before execution."""
    action_kind = _action_kind(action)
    if not action_kind:
        return False
    normalized_required = _normalize_required_kinds(approval_required_kinds)
    if action_kind in normalized_required:
        return True
    return _effect_requires_approval(action, target_exists=target_exists)


def required_action_approval_error(
    action: object,
    approval_id: object,
    approval_items_or_statuses: object,
    approval_required_kinds: list[str],
    *,
    target_exists: bool | None = None,
    action_fingerprint: str = "",
    action_task_id: str | None = None,
    action_target: str = "",
) -> str:
    """Return one policy error when a sensitive action lacks an approved approval."""
    action_kind = _action_kind(action)
    if not action_kind or not action_requires_approval(
        action,
        approval_required_kinds,
        target_exists=target_exists,
    ):
        return ""
    if not isinstance(approval_id, str) or not approval_id:
        return f"kind {action_kind} requires a non-empty approval_id under execution policy"
    approval = _approval_lookup(approval_items_or_statuses).get(approval_id)
    approval_status = approval.get("status", "") if isinstance(approval, Mapping) else ""
    if approval_status != "approved":
        if approval_status:
            return f"kind {action_kind} requires approval {approval_id} to be approved, got {approval_status}"
        return f"kind {action_kind} requires approval {approval_id} to exist and be approved"
    approval_kind = approval.get("action_kind", "") if isinstance(approval, Mapping) else ""
    if isinstance(approval_kind, str) and approval_kind and approval_kind != action_kind:
        return f"approval {approval_id} does not match action kind {action_kind}"
    expected_fingerprint = action_fingerprint or _action_fingerprint(action)
    if expected_fingerprint:
        approval_fingerprint = approval.get("fingerprint", "") if isinstance(approval, Mapping) else ""
        if approval_fingerprint != expected_fingerprint:
            return f"approval {approval_id} does not match expected action fingerprint"
    expected_task_id = action_task_id
    if expected_task_id is None and isinstance(action, Mapping):
        task_id = action.get("task_id")
        if isinstance(task_id, str):
            expected_task_id = task_id
    if expected_task_id:
        approval_task_id = approval.get("task_id", "") if isinstance(approval, Mapping) else ""
        if approval_task_id != expected_task_id:
            return f"approval {approval_id} does not match task_id {expected_task_id}"
    expected_target = action_target or _action_target(action)
    if expected_target:
        approval_target = approval.get("target", "") if isinstance(approval, Mapping) else ""
        if approval_target != expected_target:
            return f"approval {approval_id} does not match target {expected_target}"
    return ""
