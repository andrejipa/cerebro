"""Canonical action identity helpers shared across runtime modules."""

from __future__ import annotations

import json

from core.digests import sha256_text


def _exec_command_binding_payload(command: dict | None, command_id: str) -> dict:
    """Return the approval/retry-relevant snapshot for one exec.command entry."""
    if not isinstance(command, dict):
        return {"command_id": command_id, "missing": True}

    argv = command.get("argv", [])
    if not isinstance(argv, list):
        argv = []

    return {
        "command_id": command_id,
        "argv": list(argv),
        "cwd": command.get("cwd", "") if isinstance(command.get("cwd"), str) else "",
        "timeout_ms": command.get("timeout_ms"),
        "determinism": command.get("determinism", "") if isinstance(command.get("determinism"), str) else "",
        "side_effect": command.get("side_effect", "") if isinstance(command.get("side_effect"), str) else "",
        "risk": command.get("risk", "") if isinstance(command.get("risk"), str) else "",
        "allow_in_verify": bool(command.get("allow_in_verify", False)),
    }


def compute_exec_command_signature(command_registry: dict[str, dict], command_id: str) -> str:
    """Return a stable digest for the resolved exec.command registry snapshot."""
    payload = _exec_command_binding_payload(command_registry.get(command_id), command_id)
    serialized = json.dumps(payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256_text(serialized)


def compute_normalized_action_fingerprint(normalized_action: dict, *, command_signature: str | None = None) -> str:
    """Return the canonical fingerprint for one already-normalized action payload."""
    fingerprint_payload = {
        key: value
        for key, value in normalized_action.items()
        if key not in {"id", "summary"}
    }
    if normalized_action.get("kind") == "exec.command" and command_signature is not None:
        fingerprint_payload["command_signature"] = command_signature
    serialized = json.dumps(fingerprint_payload, ensure_ascii=True, sort_keys=True, separators=(",", ":"))
    return sha256_text(serialized)


def action_runtime_signature(action: dict) -> tuple[str, str, str]:
    """Extract the `(kind, target, fingerprint)` tuple used by runtime summaries."""
    details = action.get("details", {})
    fingerprint = ""
    if isinstance(details, dict):
        raw_fingerprint = details.get("fingerprint")
        if isinstance(raw_fingerprint, str):
            fingerprint = raw_fingerprint
    return (
        action.get("kind", ""),
        action.get("target", ""),
        fingerprint,
    )


def matches_action_retry_identity(action: dict, normalized_action: dict, fingerprint: str) -> bool:
    """Return whether one prior action should count as the same retry identity."""
    _, _, stored_fingerprint = action_runtime_signature(action)
    if stored_fingerprint:
        return stored_fingerprint == fingerprint

    if action.get("kind") != normalized_action.get("kind"):
        return False

    kind = normalized_action["kind"]
    if kind in {"fs.create_file", "fs.write_patch", "fs.delete_soft"}:
        return action.get("target") == normalized_action.get("path", "")
    if kind == "fs.move":
        return action.get("target") == f"{normalized_action.get('from', '')} -> {normalized_action.get('to', '')}"
    return False
