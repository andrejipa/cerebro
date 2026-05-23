"""Shared encoding and parsing helpers for workflow success memory notes."""

from __future__ import annotations

SUCCESS_SOURCE_PREFIX = "decision_success"


def build_success_memory_source(
    *,
    task_id: str,
    working_set_bucket: str,
    acceptance_defined: bool,
    action_kinds: list[str],
    has_sensitive_actions: bool,
    cost: int,
) -> str:
    normalized_actions = [
        action_kind
        for action_kind in action_kinds
        if isinstance(action_kind, str) and action_kind
    ]
    return (
        f"{SUCCESS_SOURCE_PREFIX}"
        f"|task={task_id}"
        f"|ws={working_set_bucket or 'unknown'}"
        f"|acceptance={1 if acceptance_defined else 0}"
        f"|actions={'+'.join(normalized_actions) or 'none'}"
        f"|sensitive={1 if has_sensitive_actions else 0}"
        f"|cost={max(0, int(cost))}"
    )


def parse_success_memory_note(note: object) -> dict | None:
    if not isinstance(note, dict):
        return None
    if note.get("kind") != "workflow":
        return None
    source = note.get("source")
    if not isinstance(source, str) or not source.startswith(f"{SUCCESS_SOURCE_PREFIX}|"):
        return None

    fields: dict[str, str] = {}
    for token in source.split("|")[1:]:
        key, separator, value = token.partition("=")
        if separator and key:
            fields[key] = value

    task_id = fields.get("task", "")
    working_set_bucket = fields.get("ws", "")
    acceptance = fields.get("acceptance", "")
    sensitive = fields.get("sensitive", "")
    if not task_id or not working_set_bucket or acceptance not in {"0", "1"} or sensitive not in {"0", "1"}:
        return None

    raw_actions = fields.get("actions", "none")
    action_kinds = [item for item in raw_actions.split("+") if item and item != "none"]
    try:
        cost = int(fields.get("cost", "0"))
    except ValueError:
        return None

    return {
        "task_id": task_id,
        "working_set_bucket": working_set_bucket,
        "acceptance_defined": acceptance == "1",
        "action_kinds": action_kinds,
        "has_sensitive_actions": sensitive == "1",
        "cost": max(0, cost),
        "pattern_signature": (
            f"ws={working_set_bucket}"
            f"|acceptance={'defined' if acceptance == '1' else 'missing'}"
            f"|actions={'+'.join(action_kinds) or 'none'}"
            f"|sensitive={'yes' if sensitive == '1' else 'no'}"
        ),
        "reason": note.get("summary", ""),
        "updated_at": note.get("updated_at", ""),
    }
