from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import asdict, dataclass

from experiments.control_plane_trace import ControlPlaneTrace


class ControlPlaneEventLedgerError(ValueError):
    """Raised when a control-plane event ledger is malformed."""


_SCHEMA_VERSION = "1"
_ALLOWED_EVENT_TYPES = {
    "decision_opened",
    "evidence_read",
    "evidence_rejected",
    "approval_checked",
    "action_blocked",
    "verification_recorded",
    "rollback_recorded",
    "decision_closed",
}


@dataclass(frozen=True)
class ControlPlaneEventRecord:
    schema_version: str
    ledger_role: str
    trace_id: str
    sequence: int
    event_type: str
    subject: str
    detail: str
    replay_digest: str
    event_digest: str
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane event ledger only"
    ledger_is_not_permission: bool = True
    must_not_execute_automatically: bool = True
    replay_digest_is_not_truth: bool = True


@dataclass(frozen=True)
class ControlPlaneEventLedger:
    trace_id: str
    replay_digest: str
    records: tuple[ControlPlaneEventRecord, ...]
    replay_status: str
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane event ledger only"
    ledger_is_not_permission: bool = True
    must_not_execute_automatically: bool = True
    replay_digest_is_not_truth: bool = True


def _event_digest(
    *,
    ledger_role: str,
    trace_id: str,
    sequence: int,
    event_type: str,
    subject: str,
    detail: str,
    replay_digest: str,
) -> str:
    payload = {
        "schema_version": _SCHEMA_VERSION,
        "ledger_role": ledger_role,
        "trace_id": trace_id,
        "sequence": sequence,
        "event_type": event_type,
        "subject": subject,
        "detail": detail,
        "replay_digest": replay_digest,
        "state_change": "none",
        "authority": "non-authoritative; advisory control-plane event ledger only",
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return f"sha256:{sha256(encoded).hexdigest()}"


def _validate_trace(trace: ControlPlaneTrace) -> None:
    if trace.state_change != "none" or "non-authoritative" not in trace.authority:
        raise ControlPlaneEventLedgerError("trace input must be non-authoritative with state_change none")
    if not trace.trace_events:
        raise ControlPlaneEventLedgerError("trace must contain events")
    if trace.trace_events[0].event_type != "decision_opened":
        raise ControlPlaneEventLedgerError("trace must start with decision_opened")
    if trace.trace_events[-1].event_type != "decision_closed":
        raise ControlPlaneEventLedgerError("trace must end with decision_closed")
    if trace.replay_digest not in trace.trace_events[-1].detail:
        raise ControlPlaneEventLedgerError("decision_closed event must carry replay digest")


def _validate_records(records: tuple[ControlPlaneEventRecord, ...]) -> None:
    if not records:
        raise ControlPlaneEventLedgerError("ledger must contain at least one record")
    trace_ids = {record.trace_id for record in records}
    if len(trace_ids) != 1:
        raise ControlPlaneEventLedgerError("ledger records must use one trace_id")
    digests = {record.replay_digest for record in records}
    if len(digests) != 1:
        raise ControlPlaneEventLedgerError("ledger records must use one replay_digest")
    if records[0].event_type != "decision_opened":
        raise ControlPlaneEventLedgerError("ledger must start with decision_opened")
    if records[-1].event_type != "decision_closed":
        raise ControlPlaneEventLedgerError("ledger must end with decision_closed")
    for expected, record in enumerate(records):
        if record.schema_version != _SCHEMA_VERSION:
            raise ControlPlaneEventLedgerError("schema_version must be '1'")
        if record.ledger_role != "derived_control_plane_trace_event":
            raise ControlPlaneEventLedgerError("ledger_role must be derived_control_plane_trace_event")
        if record.sequence != expected:
            raise ControlPlaneEventLedgerError("ledger sequences must be contiguous from zero")
        if record.event_type not in _ALLOWED_EVENT_TYPES:
            raise ControlPlaneEventLedgerError(f"unknown event_type: {record.event_type}")
        if record.state_change != "none" or "non-authoritative" not in record.authority:
            raise ControlPlaneEventLedgerError("ledger records must be non-authoritative with state_change none")
        if (
            not record.ledger_is_not_permission
            or not record.must_not_execute_automatically
            or not record.replay_digest_is_not_truth
        ):
            raise ControlPlaneEventLedgerError("ledger guardrails must remain true")
        expected_digest = _event_digest(
            ledger_role=record.ledger_role,
            trace_id=record.trace_id,
            sequence=record.sequence,
            event_type=record.event_type,
            subject=record.subject,
            detail=record.detail,
            replay_digest=record.replay_digest,
        )
        if record.event_digest != expected_digest:
            raise ControlPlaneEventLedgerError("event_digest must match the record payload")
    if records[-1].replay_digest not in records[-1].detail:
        raise ControlPlaneEventLedgerError("decision_closed record must carry replay digest")


def _ledger_status(records: tuple[ControlPlaneEventRecord, ...]) -> str:
    if any(record.event_type == "action_blocked" for record in records):
        return "blocked_replay_verified"
    if any(record.event_type == "approval_checked" for record in records):
        return "human_review_replay_verified"
    return "advisory_replay_verified"


def build_control_plane_event_ledger(trace: ControlPlaneTrace) -> ControlPlaneEventLedger:
    """Build an in-memory advisory JSONL ledger from a ControlPlaneTrace."""

    _validate_trace(trace)
    records = tuple(
        ControlPlaneEventRecord(
            schema_version=_SCHEMA_VERSION,
            ledger_role="derived_control_plane_trace_event",
            trace_id=trace.trace_id,
            sequence=index,
            event_type=event.event_type,
            subject=event.subject,
            detail=event.detail,
            replay_digest=trace.replay_digest,
            event_digest=_event_digest(
                ledger_role="derived_control_plane_trace_event",
                trace_id=trace.trace_id,
                sequence=index,
                event_type=event.event_type,
                subject=event.subject,
                detail=event.detail,
                replay_digest=trace.replay_digest,
            ),
        )
        for index, event in enumerate(trace.trace_events)
    )
    _validate_records(records)
    return ControlPlaneEventLedger(
        trace_id=trace.trace_id,
        replay_digest=trace.replay_digest,
        records=records,
        replay_status=_ledger_status(records),
    )


def render_control_plane_event_ledger_jsonl(ledger: ControlPlaneEventLedger) -> str:
    _validate_records(ledger.records)
    lines = [json.dumps(asdict(record), sort_keys=True, separators=(",", ":")) for record in ledger.records]
    return "\n".join(lines) + "\n"


def parse_control_plane_event_ledger_jsonl(text: str) -> ControlPlaneEventLedger:
    if not text.strip():
        raise ControlPlaneEventLedgerError("ledger JSONL must not be empty")
    records = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ControlPlaneEventLedgerError(f"invalid JSONL at line {line_no}") from exc
        if not isinstance(raw, dict):
            raise ControlPlaneEventLedgerError(f"line {line_no} must be a JSON object")
        try:
            records.append(
                ControlPlaneEventRecord(
                    schema_version=str(raw["schema_version"]),
                    ledger_role=str(raw["ledger_role"]),
                    trace_id=str(raw["trace_id"]),
                    sequence=int(raw["sequence"]),
                    event_type=str(raw["event_type"]),
                    subject=str(raw["subject"]),
                    detail=str(raw["detail"]),
                    replay_digest=str(raw["replay_digest"]),
                    event_digest=str(raw["event_digest"]),
                    state_change=str(raw.get("state_change", "")),
                    authority=str(raw.get("authority", "")),
                    ledger_is_not_permission=bool(raw.get("ledger_is_not_permission", False)),
                    must_not_execute_automatically=bool(raw.get("must_not_execute_automatically", False)),
                    replay_digest_is_not_truth=bool(raw.get("replay_digest_is_not_truth", False)),
                )
            )
        except KeyError as exc:
            raise ControlPlaneEventLedgerError(f"line {line_no} is missing required field") from exc
    parsed = tuple(records)
    _validate_records(parsed)
    return ControlPlaneEventLedger(
        trace_id=parsed[0].trace_id,
        replay_digest=parsed[0].replay_digest,
        records=parsed,
        replay_status=_ledger_status(parsed),
    )
