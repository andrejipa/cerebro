"""Execution policy helpers for the alpha runtime."""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path, PurePosixPath


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
    head = argv[0].strip().lower()
    if not head:
        raise ExecutionPolicyError("command argv[0] must be a non-empty string")
    if head in {item.lower() for item in blocked_prefixes}:
        raise ExecutionPolicyError(f"command prefix is blocked by execution policy: {head}")


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
    approval_statuses: dict[str, str],
    approval_required_kinds: list[str],
    *,
    target_exists: bool | None = None,
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
    approval_status = approval_statuses.get(approval_id, "")
    if approval_status != "approved":
        if approval_status:
            return f"kind {action_kind} requires approval {approval_id} to be approved, got {approval_status}"
        return f"kind {action_kind} requires approval {approval_id} to exist and be approved"
    return ""
