"""Canonical state digest primitives."""

from __future__ import annotations

import hashlib
import json
import math
from typing import Any


class StateDigestError(Exception):
    """Raised when a state cannot be represented canonically."""


OBSERVATIONAL_FIELD_PATHS = frozenset(
    {
        ("checkpoint", "updated_at"),
        ("last_validation", "validated_at"),
        ("agent_runtime", "plan", "updated_at"),
        ("agent_runtime", "approvals", "items", "*", "requested_at"),
        ("agent_runtime", "approvals", "items", "*", "resolved_at"),
        ("agent_runtime", "actions", "*", "updated_at"),
        ("agent_runtime", "verification", "last_run_at"),
        ("agent_runtime", "memory", "notes", "*", "updated_at"),
        ("agent_runtime", "audit", "last_event_at"),
        ("agent_runtime", "audit", "last_trace_error"),
        ("agent_runtime", "audit", "last_trace_error_at"),
        ("agent_runtime", "audit", "next_event_id"),
        ("agent_runtime", "audit", "rollback_points", "*", "created_at"),
        ("agent_runtime", "audit", "trace_integrity"),
        ("agent_runtime", "audit", "trace_status"),
        ("agent_runtime", "audit", "trace_thread_id"),
    }
)


def canonical_state_payload(state: dict, *, schema_version: int) -> dict:
    """Return the canonical digest payload for an already validated state."""
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        raise StateDigestError("schema_version must be a positive integer")
    if not isinstance(state, dict):
        raise StateDigestError("state must be a JSON object")
    return {
        "schema_version": schema_version,
        "state": _normalize_value(state, ()),
    }


def canonical_state_bytes(state: dict, *, schema_version: int) -> bytes:
    """Return stable bytes for deterministic state comparison."""
    payload = canonical_state_payload(state, schema_version=schema_version)
    try:
        return json.dumps(
            payload,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=False,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise StateDigestError("state cannot be serialized canonically") from exc


def canonical_state_digest(state: dict, *, schema_version: int) -> str:
    """Return a sha256 digest over the canonical state payload."""
    return "sha256:" + hashlib.sha256(canonical_state_bytes(state, schema_version=schema_version)).hexdigest()


def _normalize_value(value: Any, path: tuple[str, ...]) -> Any:
    if isinstance(value, dict):
        normalized: dict[str, Any] = {}
        for key, child in value.items():
            if not isinstance(key, str):
                raise StateDigestError("state object keys must be strings")
            child_path = (*path, key)
            if _is_observational_path(child_path):
                continue
            normalized[key] = _normalize_value(child, child_path)
        return normalized
    if isinstance(value, list):
        return [_normalize_value(item, (*path, "*")) for item in value]
    if value is None or isinstance(value, (str, bool)):
        return value
    if isinstance(value, int) and not isinstance(value, bool):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise StateDigestError("state floats must be finite")
        return value
    raise StateDigestError(f"unsupported state value type at {'.'.join(path) or '<root>'}: {type(value).__name__}")


def _is_observational_path(path: tuple[str, ...]) -> bool:
    return any(_path_matches(path, pattern) for pattern in OBSERVATIONAL_FIELD_PATHS)


def _path_matches(path: tuple[str, ...], pattern: tuple[str, ...]) -> bool:
    if len(path) != len(pattern):
        return False
    return all(expected == "*" or actual == expected for actual, expected in zip(path, pattern))
