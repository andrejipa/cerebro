"""Replay digest-chain and snapshot-acceptance primitives."""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

from core.state_digest import StateDigestError, canonical_state_digest
from core.transition_journal import REQUIRED_EVENT_FIELDS, TransitionJournalError, compute_event_id


class ReplayModelError(Exception):
    """Raised when replay or snapshot acceptance cannot be proven."""


@dataclass(frozen=True)
class ReplayDigestResult:
    """Verified digest-chain head after replaying transition metadata."""

    schema_version: int
    sequence_number: int
    event_id: str
    state_digest: str


@dataclass(frozen=True)
class SnapshotDecision:
    """Snapshot acceptance outcome."""

    status: str
    reason: str


ACCEPTED = "accepted"
DISCARD = "discard"


SNAPSHOT_REQUIRED_FIELDS = {
    "schema_version",
    "sequence_number",
    "event_id",
    "state_digest",
}


def replay_digest_chain(initial_state: dict, events: Iterable[dict], *, schema_version: int) -> ReplayDigestResult:
    """Verify transition digest continuity without applying event reducers."""
    current_digest = _state_digest(initial_state, schema_version=schema_version)
    previous_event_id = ""
    sequence_number = 0

    for expected_sequence, event in enumerate(events, start=1):
        _validate_event(event, expected_sequence=expected_sequence, previous_event_id=previous_event_id)
        if event["schema_version"] != schema_version:
            raise ReplayModelError("transition event schema_version does not match replay schema_version")
        if event["pre_state_digest"] != current_digest:
            raise ReplayModelError("transition event pre_state_digest does not match replay head")
        current_digest = event["post_state_digest"]
        previous_event_id = event["event_id"]
        sequence_number = expected_sequence

    return ReplayDigestResult(
        schema_version=schema_version,
        sequence_number=sequence_number,
        event_id=previous_event_id,
        state_digest=current_digest,
    )


def build_snapshot_metadata(state: dict, replay: ReplayDigestResult) -> dict:
    """Build snapshot metadata that is acceptable for the supplied replay head."""
    state_digest = _state_digest(state, schema_version=replay.schema_version)
    return {
        "schema_version": replay.schema_version,
        "sequence_number": replay.sequence_number,
        "event_id": replay.event_id,
        "state_digest": state_digest,
    }


def evaluate_snapshot(state: dict, metadata: dict, replay: ReplayDigestResult) -> SnapshotDecision:
    """Decide whether a snapshot can be used for the verified replay head."""
    _validate_snapshot_metadata(metadata)
    if metadata["schema_version"] != replay.schema_version:
        raise ReplayModelError("snapshot schema_version does not match replay schema_version")

    state_digest = _state_digest(state, schema_version=metadata["schema_version"])
    if metadata["state_digest"] != state_digest:
        raise ReplayModelError("snapshot metadata state_digest does not match snapshot state")

    if metadata["sequence_number"] > replay.sequence_number:
        raise ReplayModelError("snapshot sequence_number is ahead of replay head")
    if metadata["sequence_number"] < replay.sequence_number:
        return SnapshotDecision(DISCARD, "snapshot is stale")
    if metadata["event_id"] != replay.event_id:
        raise ReplayModelError("snapshot event_id does not match replay head")
    if state_digest != replay.state_digest:
        raise ReplayModelError("snapshot state_digest does not match replay head")
    return SnapshotDecision(ACCEPTED, "snapshot matches replay head")


def _validate_event(event: dict, *, expected_sequence: int, previous_event_id: str) -> None:
    if not isinstance(event, dict):
        raise ReplayModelError("transition event must be an object")

    missing = sorted(field for field in REQUIRED_EVENT_FIELDS if field not in event)
    missing.extend(field for field in ("sequence_number", "previous_event_id", "event_id") if field not in event)
    if missing:
        raise ReplayModelError("transition event missing required fields: " + ", ".join(sorted(missing)))

    if event.get("sequence_number") != expected_sequence:
        raise ReplayModelError("transition event sequence_number is not contiguous")
    if event.get("previous_event_id") != previous_event_id:
        raise ReplayModelError("transition event previous_event_id mismatch")

    for field in ("event_type", "operation_id", "pre_state_digest", "post_state_digest", "previous_event_id", "event_id"):
        if not isinstance(event.get(field), str):
            raise ReplayModelError(f"transition event {field} must be a string")
    for field in ("event_type", "operation_id", "pre_state_digest", "post_state_digest", "event_id"):
        if not event[field]:
            raise ReplayModelError(f"transition event {field} must be non-empty")
    for field in ("pre_state_digest", "post_state_digest", "event_id"):
        _validate_digest(event[field], f"transition event {field}")
    for field in ("event_version", "schema_version", "sequence_number"):
        if not isinstance(event.get(field), int) or isinstance(event.get(field), bool) or event[field] < 1:
            raise ReplayModelError(f"transition event {field} must be a positive integer")
    for field in ("deterministic_fields", "observational_fields"):
        if not isinstance(event.get(field), dict):
            raise ReplayModelError(f"transition event {field} must be an object")
        _validate_json_value(event[field], field)

    try:
        expected_event_id = compute_event_id(event)
    except TransitionJournalError as exc:
        raise ReplayModelError("transition event_id cannot be recomputed") from exc
    if event["event_id"] != expected_event_id:
        raise ReplayModelError("transition event_id mismatch")


def _validate_snapshot_metadata(metadata: dict) -> None:
    if not isinstance(metadata, dict):
        raise ReplayModelError("snapshot metadata must be an object")
    missing = sorted(field for field in SNAPSHOT_REQUIRED_FIELDS if field not in metadata)
    if missing:
        raise ReplayModelError("snapshot metadata missing required fields: " + ", ".join(missing))
    if not isinstance(metadata.get("schema_version"), int) or isinstance(metadata.get("schema_version"), bool) or metadata["schema_version"] < 1:
        raise ReplayModelError("snapshot schema_version must be a positive integer")
    if not isinstance(metadata.get("sequence_number"), int) or isinstance(metadata.get("sequence_number"), bool) or metadata["sequence_number"] < 0:
        raise ReplayModelError("snapshot sequence_number must be a non-negative integer")
    for field in ("event_id", "state_digest"):
        if not isinstance(metadata.get(field), str):
            raise ReplayModelError(f"snapshot {field} must be a string")
    _validate_digest(metadata["state_digest"], "snapshot state_digest")
    if metadata["sequence_number"] == 0 and metadata["event_id"] != "":
        raise ReplayModelError("empty snapshot sequence must use an empty event_id")
    if metadata["sequence_number"] > 0 and not metadata["event_id"]:
        raise ReplayModelError("non-empty snapshot sequence must include event_id")
    if metadata["event_id"]:
        _validate_digest(metadata["event_id"], "snapshot event_id")


def _state_digest(state: dict, *, schema_version: int) -> str:
    try:
        return canonical_state_digest(state, schema_version=schema_version)
    except StateDigestError as exc:
        raise ReplayModelError("state cannot be digested for replay") from exc


def _validate_digest(value: str, label: str) -> None:
    if not value.startswith("sha256:") or len(value) != 71:
        raise ReplayModelError(f"{label} must be a sha256 digest")
    suffix = value.removeprefix("sha256:")
    if any(character not in "0123456789abcdef" for character in suffix):
        raise ReplayModelError(f"{label} must be a lowercase hex sha256 digest")


def _validate_json_value(value: object, path: str) -> None:
    if isinstance(value, dict):
        for key, child in value.items():
            if not isinstance(key, str):
                raise ReplayModelError(f"{path} keys must be strings")
            _validate_json_value(child, f"{path}.{key}")
        return
    if isinstance(value, list):
        for index, child in enumerate(value):
            _validate_json_value(child, f"{path}[{index}]")
        return
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int) and not isinstance(value, bool):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ReplayModelError(f"{path} floats must be finite")
        return
    raise ReplayModelError(f"{path} contains unsupported value type: {type(value).__name__}")
