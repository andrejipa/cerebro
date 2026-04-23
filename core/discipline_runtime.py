"""Operational discipline helpers for retries and redundant actions."""

from __future__ import annotations

import json
from pathlib import Path

from core.action_identity import compute_exec_command_signature, matches_action_retry_identity
from core.agent_runtime import build_command_registry_map
from core.digests import sha256_file, sha256_text
from core.runtime_event_window import events_since_latest_plan_update


def _resolve_workspace_path(root: Path, raw_path: str) -> Path:
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"path must be relative: {raw_path}")
    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"path cannot contain '..': {raw_path}")
    resolved = (root / candidate).resolve()
    try:
        resolved.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"path resolves outside workspace: {raw_path}") from exc
    return resolved


def _file_state_marker(path: Path) -> dict:
    if not path.exists():
        return {"exists": False, "sha256": ""}
    if not path.is_file():
        return {"exists": True, "sha256": "non-file"}
    return {"exists": True, "sha256": sha256_file(path)}


def build_action_evidence_token(root: Path, normalized_action: dict, agent_runtime: dict, task_id: str) -> str:
    """Return a deterministic token representing the current evidence relevant to one action."""
    verification = agent_runtime.get("verification", {})
    evidence = {
        "kind": normalized_action["kind"],
        "task_id": task_id,
        "verification_status": verification.get("status", ""),
        "pending_action_ids": sorted(
            item
            for item in verification.get("pending_action_ids", [])
            if isinstance(item, str)
        ),
    }

    kind = normalized_action["kind"]
    if kind in {"fs.create_file", "fs.write_patch", "fs.delete_soft"}:
        target = _resolve_workspace_path(root, normalized_action["path"])
        evidence["target_state"] = _file_state_marker(target)
    elif kind == "fs.move":
        source = _resolve_workspace_path(root, normalized_action["from"])
        target = _resolve_workspace_path(root, normalized_action["to"])
        evidence["source_state"] = _file_state_marker(source)
        evidence["target_state"] = _file_state_marker(target)
    elif kind == "exec.command":
        command_registry = build_command_registry_map(agent_runtime)
        evidence["command_id"] = normalized_action["command_id"]
        evidence["command_signature"] = compute_exec_command_signature(
            command_registry,
            normalized_action["command_id"],
        )
        evidence["last_run_at"] = verification.get("last_run_at", "")

    payload = json.dumps(evidence, sort_keys=True, ensure_ascii=True, separators=(",", ":"))
    return sha256_text(payload)


def _target_matches_last_outcome(root: Path, normalized_action: dict, actions: list[dict]) -> bool:
    if not actions:
        return False

    last_action = actions[-1]
    details = last_action.get("details", {})
    if not isinstance(details, dict):
        return False

    kind = normalized_action["kind"]
    if kind in {"fs.create_file", "fs.write_patch"}:
        target = _resolve_workspace_path(root, normalized_action["path"])
        current_state = _file_state_marker(target)
        return current_state["exists"] and current_state["sha256"] == details.get("post_sha256", "")

    if kind == "fs.move":
        source = _resolve_workspace_path(root, normalized_action["from"])
        target = _resolve_workspace_path(root, normalized_action["to"])
        source_state = _file_state_marker(source)
        target_state = _file_state_marker(target)
        return (
            not source_state["exists"]
            and target_state["exists"]
            and target_state["sha256"] == details.get("post_sha256", "")
        )

    if kind == "fs.delete_soft":
        target = _resolve_workspace_path(root, normalized_action["path"])
        current_state = _file_state_marker(target)
        return not current_state["exists"]

    return False


def evaluate_action_effectiveness(root: Path, normalized_action: dict) -> dict:
    """Reject typed actions that provably would not change effective workspace state."""
    kind = normalized_action["kind"]

    if kind == "fs.create_file":
        target = _resolve_workspace_path(root, normalized_action["path"])
        current_state = _file_state_marker(target)
        desired_sha256 = sha256_text(normalized_action["content"])
        if current_state["exists"] and current_state["sha256"] == desired_sha256:
            return {
                "allowed": False,
                "reason_code": "action_no_effect",
                "reason": "apply blocked because the action would not change the effective workspace state",
            }

    if kind == "fs.move":
        source = _resolve_workspace_path(root, normalized_action["from"])
        target = _resolve_workspace_path(root, normalized_action["to"])
        if source == target and source.exists():
            return {
                "allowed": False,
                "reason_code": "action_no_effect",
                "reason": "apply blocked because the action would not change the effective workspace state",
            }

    if kind == "fs.write_patch":
        target = _resolve_workspace_path(root, normalized_action["path"])
        if target.exists() and target.is_file():
            original = target.read_text(encoding="utf-8")
            original_sha256 = sha256_text(original)
            if original_sha256 == normalized_action["expected_sha256"]:
                updated = original
                can_simulate = True
                for replacement in normalized_action["replacements"]:
                    occurrences = updated.count(replacement["old"])
                    if occurrences < replacement["count"]:
                        can_simulate = False
                        break
                    updated = updated.replace(replacement["old"], replacement["new"], replacement["count"])
                if can_simulate and updated == original:
                    return {
                        "allowed": False,
                        "reason_code": "action_no_effect",
                        "reason": "apply blocked because the action would not change the effective workspace state",
                    }

    return {
        "allowed": True,
        "reason_code": "",
        "reason": "",
    }


def evaluate_retry_discipline(
    root: Path,
    normalized_action: dict,
    fingerprint: str,
    agent_runtime: dict,
    task_id: str,
    retry_justification: str,
) -> dict:
    """Decide whether one action retry is allowed under current evidence."""
    evidence_token = build_action_evidence_token(root, normalized_action, agent_runtime, task_id)
    actions = [
        action
        for action in agent_runtime.get("actions", [])
        if isinstance(action, dict) and matches_action_retry_identity(action, normalized_action, fingerprint)
    ]
    recent_history = [
        f"{action.get('id', '')}:{action.get('status', '')}:{action.get('updated_at', '')}"
        for action in actions[-3:]
    ]
    identical_evidence = [
        action
        for action in actions
        if isinstance(action.get("details"), dict) and action["details"].get("evidence_token") == evidence_token
    ]
    current_plan_events = events_since_latest_plan_update(agent_runtime.get("_recent_events", []))
    blocked_retry_count = len(
        [
            event
            for event in current_plan_events
            if isinstance(event, dict)
            and event.get("event") == "retry_blocked"
            and event.get("fingerprint") == fingerprint
        ]
    )

    if identical_evidence or _target_matches_last_outcome(root, normalized_action, actions):
        return {
            "allowed": False,
            "reason_code": "retry_blocked_no_new_evidence",
            "reason": "retry blocked because the same action was already attempted without new evidence",
            "evidence_token": evidence_token,
            "recent_history": recent_history,
            "redundant_attempts": len(actions),
            "blocked_retry_count": blocked_retry_count + 1,
        }

    if actions and (not isinstance(retry_justification, str) or not retry_justification.strip()):
        return {
            "allowed": False,
            "reason_code": "retry_requires_justification",
            "reason": "retry requires an explicit justification once the same action has already been attempted",
            "evidence_token": evidence_token,
            "recent_history": recent_history,
            "redundant_attempts": len(actions),
            "blocked_retry_count": blocked_retry_count + 1,
        }

    return {
        "allowed": True,
        "reason_code": "",
        "reason": "",
        "evidence_token": evidence_token,
        "recent_history": recent_history,
        "redundant_attempts": len(actions),
        "blocked_retry_count": blocked_retry_count,
    }
