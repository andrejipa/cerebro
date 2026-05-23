"""Operational memory helpers for the alpha runtime."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from core.agent_runtime import iter_command_checks
from core.success_memory import build_success_memory_source

MAX_MEMORY_NOTES = 64
DEFAULT_DECISION_TTL_DAYS = 30
DEFAULT_PITFALL_TTL_DAYS = 14
DEFAULT_WORKFLOW_TTL_DAYS = 21

VERIFICATION_FAILURE_NOTE_ID = "pitfall-verification-failed"


def _timestamp_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _parse_timestamp(value: object) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _prune_expired_notes(notes: list[dict], now: datetime) -> list[dict]:
    retained: list[dict] = []
    for note in notes:
        if not isinstance(note, dict):
            continue
        ttl_days = note.get("ttl_days")
        updated_at = _parse_timestamp(note.get("updated_at"))
        if not isinstance(ttl_days, int) or ttl_days <= 0 or updated_at is None:
            retained.append(note)
            continue
        if updated_at + timedelta(days=ttl_days) >= now:
            retained.append(note)
    return retained


def _trim_notes(notes: list[dict]) -> list[dict]:
    return notes[-MAX_MEMORY_NOTES:]


def _consolidated_success_note_id(pattern_signature: str) -> str:
    return f"workflow-success-{pattern_signature}"


def _extract_success_subject_signature(note: dict) -> str:
    source = note.get("source")
    if not isinstance(source, str) or not source.startswith("decision_success|"):
        return ""
    fields: dict[str, str] = {}
    for token in source.split("|")[1:]:
        key, separator, value = token.partition("=")
        if separator and key:
            fields[key] = value
    task_id = fields.get("task", "")
    working_set_bucket = fields.get("ws", "")
    acceptance = fields.get("acceptance", "")
    sensitive = fields.get("sensitive", "")
    actions = fields.get("actions", "")
    if not task_id or not working_set_bucket or acceptance not in {"0", "1"} or sensitive not in {"0", "1"}:
        return ""
    return (
        f"ws={working_set_bucket}"
        f"|acceptance={'defined' if acceptance == '1' else 'missing'}"
        f"|actions={actions or 'none'}"
        f"|sensitive={'yes' if sensitive == '1' else 'no'}"
    )


def sync_approval_memory_notes(notes: list[dict], approval_record: dict) -> list[dict]:
    """Upsert or remove decision notes derived from approval outcomes."""
    now = datetime.now(timezone.utc)
    retained = _prune_expired_notes([note for note in notes if isinstance(note, dict)], now)
    note_id = f"decision-approval-{approval_record['id']}"
    retained = [note for note in retained if note.get("id") != note_id]

    if approval_record["status"] == "rejected":
        retained.append(
            {
                "id": note_id,
                "kind": "decision",
                "summary": (
                    f"approval rejected for {approval_record['action_kind']} targeting "
                    f"{approval_record['target']}; sensitive action remains blocked"
                ),
                "source": f"approval:{approval_record['id']}",
                "ttl_days": DEFAULT_DECISION_TTL_DAYS,
                "updated_at": approval_record.get("resolved_at") or _timestamp_now(),
            }
        )

    return _trim_notes(retained)


def sync_verification_memory_notes(notes: list[dict], verification_record: dict) -> list[dict]:
    """Upsert pitfall notes derived from the latest verification result."""
    now = datetime.now(timezone.utc)
    retained = _prune_expired_notes([note for note in notes if isinstance(note, dict)], now)
    retained = [note for note in retained if note.get("id") != VERIFICATION_FAILURE_NOTE_ID]

    failing_command_ids = sorted(
        check["command_id"]
        for check in iter_command_checks(verification_record)
        if check.get("status") == "failed"
        and isinstance(check.get("command_id"), str)
    )
    pending_action_ids = [
        action_id
        for action_id in verification_record.get("pending_action_ids", [])
        if isinstance(action_id, str)
    ]

    if verification_record.get("status") == "failed":
        summary_parts: list[str] = []
        if failing_command_ids:
            summary_parts.append(f"verification failed for commands: {', '.join(failing_command_ids)}")
        if pending_action_ids:
            summary_parts.append(f"pending actions blocked by failed verification: {', '.join(pending_action_ids)}")
        if not summary_parts:
            summary_parts.append("verification failed and requires operator attention")
        retained.append(
            {
                "id": VERIFICATION_FAILURE_NOTE_ID,
                "kind": "pitfall",
                "summary": "; ".join(summary_parts),
                "source": "verification",
                "ttl_days": DEFAULT_PITFALL_TTL_DAYS,
                "updated_at": verification_record.get("last_run_at") or _timestamp_now(),
            }
        )

    return _trim_notes(retained)


def sync_success_memory_notes(notes: list[dict], success_records: list[dict]) -> list[dict]:
    """Persist one workflow note per success subject and ignore later repeats."""
    now = datetime.now(timezone.utc)
    retained = _prune_expired_notes([note for note in notes if isinstance(note, dict)], now)
    seen_subjects = {
        note_signature
        for note_signature in (
            _extract_success_subject_signature(note)
            for note in retained
        )
        if note_signature
    }
    pending_subjects: set[str] = set()

    for record in success_records:
        if not isinstance(record, dict):
            continue
        pattern_signature = record.get("pattern_signature")
        if not isinstance(pattern_signature, str) or not pattern_signature:
            continue
        if pattern_signature in seen_subjects or pattern_signature in pending_subjects:
            continue

        task_id = record.get("task_id")
        if not isinstance(task_id, str) or not task_id:
            continue
        action_kinds = [
            action_kind
            for action_kind in record.get("action_kinds", [])
            if isinstance(action_kind, str) and action_kind
        ]
        summary = (
            f"first verified success for subject {pattern_signature}: "
            f"context: {record.get('context', task_id)}; "
            f"action: {', '.join(action_kinds) or 'none'}; "
            f"result: {record.get('result', 'verified success')}; "
            f"cost: {record.get('cost', 0)}; "
            f"reason: {record.get('reason', 'verified workspace delta closed the task')}"
        )
        retained.append(
            {
                "id": _consolidated_success_note_id(pattern_signature),
                "kind": "workflow",
                "summary": summary,
                "source": build_success_memory_source(
                    task_id=task_id,
                    working_set_bucket=str(record.get("working_set_bucket", "unknown")),
                    acceptance_defined=bool(record.get("acceptance_defined")),
                    action_kinds=action_kinds,
                    has_sensitive_actions=bool(record.get("has_sensitive_actions")),
                    cost=int(record.get("cost", 0)),
                ),
                "ttl_days": DEFAULT_WORKFLOW_TTL_DAYS,
                "updated_at": record.get("recorded_at") or _timestamp_now(),
            }
        )
        pending_subjects.add(pattern_signature)
        seen_subjects.add(pattern_signature)

    return _trim_notes(retained)
