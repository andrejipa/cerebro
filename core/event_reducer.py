"""Versioned in-memory reducers for transition events."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
from typing import Iterable

from core.replay_model import ReplayModelError, replay_digest_chain
from core.state_digest import StateDigestError, canonical_state_digest
from core.transition_journal import TransitionJournalError, compute_event_id
from core.validation import validate_state_data


class EventReducerError(Exception):
    """Raised when an event cannot be reduced safely."""


@dataclass(frozen=True)
class ReplayStateResult:
    """State reconstructed by applying supported reducers in memory."""

    schema_version: int
    sequence_number: int
    event_id: str
    state_digest: str
    state: dict


CHECKPOINT_REPLACED = "checkpoint.replaced"
CHECKPOINT_REPLACED_VERSION = 1

SUPPORTED_EVENT_VERSIONS = frozenset({(CHECKPOINT_REPLACED, CHECKPOINT_REPLACED_VERSION)})
CHECKPOINT_DETERMINISTIC_FIELDS = frozenset({"goal", "summary", "next_step", "constraints"})
CHECKPOINT_OBSERVATIONAL_FIELDS = frozenset({"updated_at"})


def replay_state(initial_state: dict, events: Iterable[dict], *, schema_version: int) -> ReplayStateResult:
    """Replay supported events into a deterministic in-memory state."""
    committed_events = tuple(events)
    digest_head = _replay_digest_chain(initial_state, committed_events, schema_version=schema_version)
    current_state = deepcopy(initial_state)

    for event in committed_events:
        current_state = apply_event(current_state, event, schema_version=schema_version)

    state_digest = _state_digest(current_state, schema_version=schema_version)
    if state_digest != digest_head.state_digest:
        raise EventReducerError("reduced state digest does not match replay digest head")
    return ReplayStateResult(
        schema_version=schema_version,
        sequence_number=digest_head.sequence_number,
        event_id=digest_head.event_id,
        state_digest=state_digest,
        state=current_state,
    )


def apply_event(state: dict, event: dict, *, schema_version: int) -> dict:
    """Apply one supported event to a copy of state and verify its digest contract."""
    _validate_supported_event(event, schema_version=schema_version)
    current_revision = state.get("revision") if isinstance(state, dict) else None
    if (
        not isinstance(current_revision, int)
        or isinstance(current_revision, bool)
        or current_revision != event["sequence_number"] - 1
    ):
        raise EventReducerError("event sequence_number must advance current state revision by one")
    pre_state_digest = _state_digest(state, schema_version=schema_version)
    if event["pre_state_digest"] != pre_state_digest:
        raise EventReducerError("event pre_state_digest does not match current state")

    reduced = _apply_checkpoint_replaced(state, event)
    _validate_reduced_state(reduced)

    post_state_digest = _state_digest(reduced, schema_version=schema_version)
    if event["post_state_digest"] != post_state_digest:
        raise EventReducerError("event post_state_digest does not match reduced state")
    return reduced


def _apply_checkpoint_replaced(state: dict, event: dict) -> dict:
    deterministic_fields = event["deterministic_fields"]
    checkpoint = deterministic_fields["checkpoint"]
    observational_checkpoint = event["observational_fields"].get("checkpoint", {})

    reduced = deepcopy(state)
    reduced["revision"] = event["sequence_number"]
    reduced["checkpoint"] = {
        "goal": checkpoint["goal"],
        "summary": checkpoint["summary"],
        "next_step": checkpoint["next_step"],
        "constraints": deepcopy(checkpoint["constraints"]),
        "updated_at": observational_checkpoint.get("updated_at", reduced["checkpoint"]["updated_at"]),
    }
    return reduced


def _validate_supported_event(event: dict, *, schema_version: int) -> None:
    if not isinstance(event, dict):
        raise EventReducerError("event must be an object")
    required = {
        "event_type",
        "event_version",
        "schema_version",
        "sequence_number",
        "previous_event_id",
        "event_id",
        "pre_state_digest",
        "post_state_digest",
        "deterministic_fields",
        "observational_fields",
    }
    missing = sorted(required - set(event))
    if missing:
        raise EventReducerError("event missing required fields: " + ", ".join(missing))
    if not isinstance(schema_version, int) or isinstance(schema_version, bool) or schema_version < 1:
        raise EventReducerError("reducer schema_version must be a positive integer")
    if event.get("schema_version") != schema_version:
        raise EventReducerError("event schema_version does not match reducer schema_version")
    if not isinstance(event.get("schema_version"), int) or isinstance(event.get("schema_version"), bool):
        raise EventReducerError("event schema_version must be a positive integer")
    if not isinstance(event.get("sequence_number"), int) or isinstance(event.get("sequence_number"), bool) or event["sequence_number"] < 1:
        raise EventReducerError("event sequence_number must be a positive integer")
    for field in ("previous_event_id", "event_id", "pre_state_digest", "post_state_digest"):
        if not isinstance(event.get(field), str):
            raise EventReducerError(f"event {field} must be a string")
    try:
        expected_event_id = compute_event_id(event)
    except TransitionJournalError as exc:
        raise EventReducerError("event_id cannot be recomputed") from exc
    if event["event_id"] != expected_event_id:
        raise EventReducerError("event_id mismatch")
    event_key = (event.get("event_type"), event.get("event_version"))
    if event_key not in SUPPORTED_EVENT_VERSIONS:
        raise EventReducerError("unsupported event type or version")
    _validate_checkpoint_replaced_fields(event)


def _validate_checkpoint_replaced_fields(event: dict) -> None:
    deterministic_fields = event.get("deterministic_fields")
    if not isinstance(deterministic_fields, dict):
        raise EventReducerError("event deterministic_fields must be an object")
    if set(deterministic_fields) != {"checkpoint"}:
        raise EventReducerError("checkpoint.replaced deterministic_fields must contain only checkpoint")

    checkpoint = deterministic_fields["checkpoint"]
    if not isinstance(checkpoint, dict):
        raise EventReducerError("checkpoint.replaced checkpoint must be an object")
    if set(checkpoint) != CHECKPOINT_DETERMINISTIC_FIELDS:
        raise EventReducerError("checkpoint.replaced checkpoint fields are not exact")
    for field in ("goal", "summary", "next_step"):
        if not isinstance(checkpoint[field], str):
            raise EventReducerError(f"checkpoint.replaced checkpoint.{field} must be a string")
    constraints = checkpoint["constraints"]
    if not isinstance(constraints, list) or any(not isinstance(item, str) for item in constraints):
        raise EventReducerError("checkpoint.replaced checkpoint.constraints must be an array of strings")

    observational_fields = event.get("observational_fields")
    if not isinstance(observational_fields, dict):
        raise EventReducerError("event observational_fields must be an object")
    if set(observational_fields) - {"checkpoint"}:
        raise EventReducerError("checkpoint.replaced observational_fields contains unsupported fields")
    observational_checkpoint = observational_fields.get("checkpoint", {})
    if not isinstance(observational_checkpoint, dict):
        raise EventReducerError("checkpoint.replaced observational checkpoint must be an object")
    if set(observational_checkpoint) - CHECKPOINT_OBSERVATIONAL_FIELDS:
        raise EventReducerError("checkpoint.replaced observational checkpoint contains unsupported fields")
    if "updated_at" in observational_checkpoint and not isinstance(observational_checkpoint["updated_at"], str):
        raise EventReducerError("checkpoint.replaced observational checkpoint.updated_at must be a string")


def _validate_reduced_state(state: dict) -> None:
    errors = validate_state_data(state)
    if errors:
        first = errors[0]
        code = first.get("code", "invalid_state") if isinstance(first, dict) else "invalid_state"
        message = first.get("message", "state validation failed") if isinstance(first, dict) else "state validation failed"
        raise EventReducerError(f"reduced state failed validation: {code}: {message}")


def _state_digest(state: dict, *, schema_version: int) -> str:
    try:
        return canonical_state_digest(state, schema_version=schema_version)
    except StateDigestError as exc:
        raise EventReducerError("state cannot be digested for reducer") from exc


def _replay_digest_chain(initial_state: dict, events: tuple[dict, ...], *, schema_version: int):
    try:
        return replay_digest_chain(initial_state, events, schema_version=schema_version)
    except ReplayModelError as exc:
        raise EventReducerError("event digest chain is invalid") from exc
