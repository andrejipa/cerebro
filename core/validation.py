"""Validation helpers for the minimal checkpoint state."""

from __future__ import annotations

from pathlib import Path

from core.schema_policy import CURRENT_SCHEMA_VERSION, is_supported_schema_version
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
    SCHEMA_VERSION,
    SESSION_KEYS,
    SOURCE_KEYS,
    VALID_RESULTS,
    VALID_SOURCE_ROLES,
)


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


def _validate_checkpoint_block(checkpoint: object, prefix: str = "checkpoint") -> list[dict]:
    errors: list[dict] = []

    if not isinstance(checkpoint, dict):
        return [error("invalid_checkpoint", f"{prefix} must be an object")]

    errors.extend(_require_exact_keys(checkpoint, CHECKPOINT_KEYS, "invalid_checkpoint_keys", prefix))

    text_fields = (
        ("goal", MAX_GOAL_LENGTH),
        ("summary", MAX_SUMMARY_LENGTH),
        ("next_step", MAX_NEXT_STEP_LENGTH),
        ("updated_at", None),
    )
    for key, max_length in text_fields:
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


def validate_session_data(session: object) -> list[dict]:
    """Validate in-memory local session data."""
    errors: list[dict] = []

    if not isinstance(session, dict):
        return [error("invalid_session", "session must be a JSON object")]

    errors.extend(_require_exact_keys(session, SESSION_KEYS, "invalid_session_keys", "session"))

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

    return errors


def validate_state_data(state: object) -> list[dict]:
    """Validate in-memory state data against the minimal schema."""
    errors: list[dict] = []

    if not isinstance(state, dict):
        return [error("invalid_root", "state must be a JSON object")]

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

    checkpoint = state.get("checkpoint")
    errors.extend(_validate_checkpoint_block(checkpoint))

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
        validated_at = last_validation.get("validated_at")
        if not isinstance(validated_at, str):
            errors.append(error("invalid_validated_at", "last_validation.validated_at must be a string"))

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
                code = item.get("code")
                message = item.get("message")
                if not isinstance(code, str) or not code:
                    errors.append(error("invalid_validation_detail_code", f"{prefix}.code must be a non-empty string"))
                if not isinstance(message, str) or not message:
                    errors.append(
                        error("invalid_validation_detail_message", f"{prefix}.message must be a non-empty string")
                    )

    return errors
