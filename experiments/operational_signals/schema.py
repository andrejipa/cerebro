from __future__ import annotations

from contextlib import suppress
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
import tempfile
import tomllib
from typing import Any
import uuid


SCHEMA_VERSION = "1"

FAILURE_MODES = {
    "CONTEXT_NOT_FOUND",
    "CONTEXT_AMBIGUOUS",
    "EXCESSIVE_MANUAL_SEARCH",
    "WRONG_SOURCE_SELECTED",
    "STALE_INFORMATION",
    "INSUFFICIENT_EXPORT_SURFACE",
    "DISCOVERY_COST_TOO_HIGH",
}

CONFIDENCE_LEVELS = {"low", "medium", "high"}

SEVERITY_BY_FAILURE_MODE = {
    "CONTEXT_NOT_FOUND": 0.75,
    "CONTEXT_AMBIGUOUS": 0.55,
    "EXCESSIVE_MANUAL_SEARCH": 0.50,
    "WRONG_SOURCE_SELECTED": 0.65,
    "STALE_INFORMATION": 0.80,
    "INSUFFICIENT_EXPORT_SURFACE": 0.90,
    "DISCOVERY_COST_TOO_HIGH": 0.60,
}

CONFIDENCE_SCORES = {
    "low": 0.30,
    "medium": 0.65,
    "high": 0.90,
}

REGISTRY_HEADER = """# Operational Insufficiency Signals
#
# This registry is experimental, derived, non-authoritative, opt-in,
# and observability-only. It is not canonical runtime state, must not
# be read or written by `core/`, and must never be treated as project
# truth or as a decision gate.

schema_version = "1"
"""


class SchemaError(ValueError):
    """Raised when a registry payload is invalid."""


@dataclass(frozen=True)
class OperationalCost:
    minutes_spent: int
    extra_files_opened: int
    manual_search_rounds: int


@dataclass(frozen=True)
class UnmetUseCaseRecord:
    id: str
    timestamp: str
    project_context: str
    task_description: str
    query_or_need: str
    surface_used: tuple[str, ...]
    failure_mode: str
    manual_workaround: str
    operational_cost: OperationalCost
    repeat_count: int
    evidence: tuple[str, ...]
    confidence: str
    candidate_trigger: bool
    trigger_score: float
    notes: str = ""


def utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def generate_record_id() -> str:
    return f"uuc-{datetime.now(timezone.utc):%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"


def is_forbidden_output_path(path: str | Path) -> bool:
    resolved = Path(path).resolve()
    return any(part.casefold() == ".cerebro" for part in resolved.parts)


def ensure_allowed_registry_path(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if is_forbidden_output_path(resolved):
        raise SchemaError(f"registry path must stay outside .cerebro: {resolved}")
    return resolved


def ensure_allowed_output_path(path: str | Path) -> Path:
    resolved = Path(path).resolve()
    if is_forbidden_output_path(resolved):
        raise SchemaError(f"derived output path must stay outside .cerebro: {resolved}")
    return resolved


def _require_non_empty_string(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise SchemaError(f"{field_name} must be a non-empty string")
    return value.strip()


def _require_non_negative_int(value: Any, field_name: str) -> int:
    if not isinstance(value, int) or value < 0:
        raise SchemaError(f"{field_name} must be a non-negative integer")
    return value


def _normalize_string_list(value: Any, field_name: str) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        raise SchemaError(f"{field_name} must be a non-empty list")
    normalized: list[str] = []
    for item in value:
        normalized.append(_require_non_empty_string(item, field_name))
    return tuple(normalized)


def _validate_timestamp(value: Any) -> str:
    timestamp = _require_non_empty_string(value, "timestamp")
    try:
        datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
    except ValueError as exc:
        raise SchemaError("timestamp must be an ISO-8601 datetime") from exc
    return timestamp


def _validate_operational_cost(value: Any) -> OperationalCost:
    if not isinstance(value, dict):
        raise SchemaError("operational_cost must be a table")
    return OperationalCost(
        minutes_spent=_require_non_negative_int(value.get("minutes_spent"), "operational_cost.minutes_spent"),
        extra_files_opened=_require_non_negative_int(
            value.get("extra_files_opened"),
            "operational_cost.extra_files_opened",
        ),
        manual_search_rounds=_require_non_negative_int(
            value.get("manual_search_rounds"),
            "operational_cost.manual_search_rounds",
        ),
    )


def compute_trigger_score(record_like: dict[str, Any]) -> float:
    failure_mode = _require_non_empty_string(record_like.get("failure_mode"), "failure_mode")
    if failure_mode not in FAILURE_MODES:
        raise SchemaError(f"unsupported failure_mode: {failure_mode}")
    confidence = _require_non_empty_string(record_like.get("confidence"), "confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise SchemaError(f"unsupported confidence: {confidence}")
    repeat_count = _require_non_negative_int(record_like.get("repeat_count"), "repeat_count")
    operational_cost = _validate_operational_cost(record_like.get("operational_cost"))

    severity_score = SEVERITY_BY_FAILURE_MODE[failure_mode]
    cost_score = (
        min(1.0, operational_cost.minutes_spent / 30.0)
        + min(1.0, operational_cost.extra_files_opened / 8.0)
        + min(1.0, operational_cost.manual_search_rounds / 4.0)
    ) / 3.0
    repeat_signal = min(1.0, repeat_count / 4.0)
    confidence_signal = CONFIDENCE_SCORES[confidence]
    score = (
        0.40 * severity_score
        + 0.25 * cost_score
        + 0.20 * repeat_signal
        + 0.15 * confidence_signal
    )
    return round(score, 4)


def compute_candidate_trigger(record_like: dict[str, Any], *, threshold: float = 0.55) -> bool:
    repeat_count = _require_non_negative_int(record_like.get("repeat_count"), "repeat_count")
    confidence = _require_non_empty_string(record_like.get("confidence"), "confidence")
    if confidence not in CONFIDENCE_LEVELS:
        raise SchemaError(f"unsupported confidence: {confidence}")
    trigger_score = compute_trigger_score(record_like)
    return repeat_count >= 2 and confidence != "low" and trigger_score >= threshold


def normalize_record(raw: dict[str, Any]) -> UnmetUseCaseRecord:
    record = {
        "id": raw.get("id") or generate_record_id(),
        "timestamp": raw.get("timestamp") or utc_now_iso(),
        "project_context": raw.get("project_context"),
        "task_description": raw.get("task_description"),
        "query_or_need": raw.get("query_or_need"),
        "surface_used": raw.get("surface_used"),
        "failure_mode": raw.get("failure_mode"),
        "manual_workaround": raw.get("manual_workaround"),
        "operational_cost": raw.get("operational_cost"),
        "repeat_count": raw.get("repeat_count"),
        "evidence": raw.get("evidence"),
        "confidence": raw.get("confidence"),
        "notes": raw.get("notes", ""),
    }
    validated = UnmetUseCaseRecord(
        id=_require_non_empty_string(record["id"], "id"),
        timestamp=_validate_timestamp(record["timestamp"]),
        project_context=_require_non_empty_string(record["project_context"], "project_context"),
        task_description=_require_non_empty_string(record["task_description"], "task_description"),
        query_or_need=_require_non_empty_string(record["query_or_need"], "query_or_need"),
        surface_used=_normalize_string_list(record["surface_used"], "surface_used"),
        failure_mode=_require_non_empty_string(record["failure_mode"], "failure_mode"),
        manual_workaround=_require_non_empty_string(record["manual_workaround"], "manual_workaround"),
        operational_cost=_validate_operational_cost(record["operational_cost"]),
        repeat_count=_require_non_negative_int(record["repeat_count"], "repeat_count"),
        evidence=_normalize_string_list(record["evidence"], "evidence"),
        confidence=_require_non_empty_string(record["confidence"], "confidence"),
        candidate_trigger=False,
        trigger_score=0.0,
        notes=str(record["notes"]).strip(),
    )
    if validated.failure_mode not in FAILURE_MODES:
        raise SchemaError(f"unsupported failure_mode: {validated.failure_mode}")
    if validated.confidence not in CONFIDENCE_LEVELS:
        raise SchemaError(f"unsupported confidence: {validated.confidence}")

    candidate_trigger = compute_candidate_trigger(as_record_dict(validated))
    trigger_score = compute_trigger_score(as_record_dict(validated))
    return UnmetUseCaseRecord(
        **{**asdict(validated), "candidate_trigger": candidate_trigger, "trigger_score": trigger_score}
    )


def as_record_dict(record: UnmetUseCaseRecord) -> dict[str, Any]:
    payload = asdict(record)
    payload["surface_used"] = list(record.surface_used)
    payload["evidence"] = list(record.evidence)
    return payload


def load_registry_text(path: str | Path) -> dict[str, Any]:
    resolved = ensure_allowed_registry_path(path)
    if not resolved.exists():
        return {"schema_version": SCHEMA_VERSION, "unmet_use_case": []}
    payload = tomllib.loads(resolved.read_text(encoding="utf-8"))
    return normalize_registry(payload)


def validate_registry_payload(payload: dict[str, Any]) -> None:
    if payload.get("schema_version") != SCHEMA_VERSION:
        raise SchemaError(f"unsupported schema_version: {payload.get('schema_version')!r}")
    entries = payload.get("unmet_use_case", [])
    if not isinstance(entries, list):
        raise SchemaError("unmet_use_case must be a list")
    seen_ids: set[str] = set()
    for entry in entries:
        normalized = normalize_record(entry)
        if normalized.id in seen_ids:
            raise SchemaError(f"duplicate record id: {normalized.id}")
        seen_ids.add(normalized.id)


def normalize_registry(payload: dict[str, Any]) -> dict[str, Any]:
    validate_registry_payload(payload)
    entries = [as_record_dict(normalize_record(entry)) for entry in payload.get("unmet_use_case", [])]
    return {"schema_version": SCHEMA_VERSION, "unmet_use_case": entries}


def append_record(payload: dict[str, Any], record: dict[str, Any]) -> dict[str, Any]:
    normalized_registry = normalize_registry(payload)
    normalized_record = as_record_dict(normalize_record(record))
    if any(item["id"] == normalized_record["id"] for item in normalized_registry["unmet_use_case"]):
        raise SchemaError(f"duplicate record id: {normalized_record['id']}")
    normalized_registry["unmet_use_case"].append(normalized_record)
    return normalized_registry


def _quote_string(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"')
    return f'"{escaped}"'


def serialize_registry(payload: dict[str, Any]) -> str:
    normalized_registry = normalize_registry(payload)
    lines = [REGISTRY_HEADER.rstrip(), ""]
    for entry in normalized_registry["unmet_use_case"]:
        lines.append("[[unmet_use_case]]")
        lines.append(f'id = {_quote_string(entry["id"])}')
        lines.append(f'timestamp = {_quote_string(entry["timestamp"])}')
        lines.append(f'project_context = {_quote_string(entry["project_context"])}')
        lines.append(f'task_description = {_quote_string(entry["task_description"])}')
        lines.append(f'query_or_need = {_quote_string(entry["query_or_need"])}')
        surface_list = ", ".join(_quote_string(item) for item in entry["surface_used"])
        lines.append(f"surface_used = [{surface_list}]")
        lines.append(f'failure_mode = {_quote_string(entry["failure_mode"])}')
        lines.append(f'manual_workaround = {_quote_string(entry["manual_workaround"])}')
        lines.append(f"repeat_count = {entry['repeat_count']}")
        evidence_list = ", ".join(_quote_string(item) for item in entry["evidence"])
        lines.append(f"evidence = [{evidence_list}]")
        lines.append(f'confidence = {_quote_string(entry["confidence"])}')
        lines.append(f"candidate_trigger = {'true' if entry['candidate_trigger'] else 'false'}")
        lines.append(f"trigger_score = {entry['trigger_score']:.4f}")
        lines.append(f'notes = {_quote_string(entry["notes"])}')
        lines.append("[unmet_use_case.operational_cost]")
        lines.append(f"minutes_spent = {entry['operational_cost']['minutes_spent']}")
        lines.append(f"extra_files_opened = {entry['operational_cost']['extra_files_opened']}")
        lines.append(f"manual_search_rounds = {entry['operational_cost']['manual_search_rounds']}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"


def atomic_write_registry(path: str | Path, payload: dict[str, Any]) -> Path:
    resolved = ensure_allowed_registry_path(path)
    resolved.parent.mkdir(parents=True, exist_ok=True)
    rendered = serialize_registry(payload)
    with tempfile.NamedTemporaryFile("w", encoding="utf-8", delete=False, dir=resolved.parent, suffix=".tmp") as handle:
        temp_path = Path(handle.name)
        try:
            handle.write(rendered)
        except Exception:
            with suppress(Exception):
                handle.close()
            with suppress(FileNotFoundError, PermissionError):
                temp_path.unlink()
            raise
    try:
        temp_path.replace(resolved)
    finally:
        with suppress(FileNotFoundError):
            temp_path.unlink()
    return resolved
