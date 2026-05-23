from __future__ import annotations

import unittest
from copy import deepcopy

from core.event_reducer import CHECKPOINT_REPLACED, EventReducerError, apply_event, replay_state
from core.schema import build_initial_state
from core.state_digest import canonical_state_digest
from core.transition_journal import TransitionJournal, compute_event_id


def digest(state: dict, *, schema_version: int = 1) -> str:
    return canonical_state_digest(state, schema_version=schema_version)


def checkpoint_event_payload(
    operation_id: str,
    pre_state: dict,
    post_state: dict,
    *,
    checkpoint: dict,
    updated_at: str = "2026-04-23T00:00:00Z",
    schema_version: int = 1,
    event_version: int = 1,
) -> dict:
    return {
        "event_type": CHECKPOINT_REPLACED,
        "event_version": event_version,
        "schema_version": schema_version,
        "operation_id": operation_id,
        "pre_state_digest": digest(pre_state, schema_version=schema_version),
        "post_state_digest": digest(post_state, schema_version=schema_version),
        "deterministic_fields": {"checkpoint": deepcopy(checkpoint)},
        "observational_fields": {"checkpoint": {"updated_at": updated_at}},
    }


def checkpoint_fields(**overrides) -> dict:
    fields = {
        "goal": "ship",
        "summary": "ready",
        "next_step": "test",
        "constraints": ["keep scope narrow"],
    }
    fields.update(overrides)
    return fields


def expected_state(pre_state: dict, checkpoint: dict, *, sequence_number: int, updated_at: str = "2026-04-23T00:00:00Z") -> dict:
    state = deepcopy(pre_state)
    state["revision"] = sequence_number
    state["checkpoint"] = {
        "goal": checkpoint["goal"],
        "summary": checkpoint["summary"],
        "next_step": checkpoint["next_step"],
        "constraints": deepcopy(checkpoint["constraints"]),
        "updated_at": updated_at,
    }
    return state


class EventReducerTests(unittest.TestCase):
    def test_replay_state_applies_checkpoint_replaced_event_and_matches_digest(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="first")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        journal = TransitionJournal(self.create_temp_journal())
        event = journal.append_event(checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint))

        result = replay_state(initial, (event,), schema_version=1)

        self.assertEqual(result.sequence_number, 1)
        self.assertEqual(result.event_id, event["event_id"])
        self.assertEqual(result.state, post_state)
        self.assertEqual(result.state_digest, digest(post_state))

    def test_replay_state_applies_multiple_events_in_order(self) -> None:
        initial = build_initial_state()
        first_checkpoint = checkpoint_fields(summary="first")
        first_state = expected_state(initial, first_checkpoint, sequence_number=1)
        second_checkpoint = checkpoint_fields(summary="second", next_step="verify")
        second_state = expected_state(first_state, second_checkpoint, sequence_number=2)
        journal = TransitionJournal(self.create_temp_journal())
        first = journal.append_event(checkpoint_event_payload("op-001", initial, first_state, checkpoint=first_checkpoint))
        second = journal.append_event(checkpoint_event_payload("op-002", first_state, second_state, checkpoint=second_checkpoint))

        result = replay_state(initial, (first, second), schema_version=1)

        self.assertEqual(result.sequence_number, 2)
        self.assertEqual(result.state, second_state)

    def test_apply_event_does_not_mutate_input_state(self) -> None:
        initial = build_initial_state()
        original = deepcopy(initial)
        checkpoint = checkpoint_fields(summary="changed")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )

        reduced = apply_event(initial, event, schema_version=1)

        self.assertEqual(initial, original)
        self.assertNotEqual(reduced, original)

    def test_apply_event_rejects_uncommitted_event_without_sequence(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="changed")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)

        with self.assertRaisesRegex(EventReducerError, "missing required fields"):
            apply_event(initial, event, schema_version=1)

    def test_apply_event_rejects_tampered_event_id(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="changed")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )
        event = dict(event)
        event["operation_id"] = "tampered"

        with self.assertRaisesRegex(EventReducerError, "event_id mismatch"):
            apply_event(initial, event, schema_version=1)

    def test_event_sequence_must_advance_current_revision(self) -> None:
        initial = build_initial_state()
        initial["revision"] = 5
        checkpoint = checkpoint_fields(summary="changed")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )

        with self.assertRaisesRegex(EventReducerError, "advance current state revision"):
            replay_state(initial, (event,), schema_version=1)

    def test_unknown_event_type_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields()
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )
        event = dict(event)
        event["event_type"] = "state.replace"
        event["event_id"] = compute_event_id(event)

        with self.assertRaisesRegex(EventReducerError, "unsupported event type or version"):
            replay_state(initial, (event,), schema_version=1)

    def test_unsupported_event_version_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields()
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint, event_version=2)
        )

        with self.assertRaisesRegex(EventReducerError, "unsupported event type or version"):
            replay_state(initial, (event,), schema_version=1)

    def test_unknown_deterministic_field_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields()
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )
        event = dict(event)
        event["deterministic_fields"] = dict(event["deterministic_fields"])
        event["deterministic_fields"]["unexpected"] = True
        event["event_id"] = compute_event_id(event)

        with self.assertRaisesRegex(EventReducerError, "deterministic_fields"):
            replay_state(initial, (event,), schema_version=1)

    def test_unknown_observational_field_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields()
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )
        event = dict(event)
        event["observational_fields"] = {"checkpoint": {"updated_at": "now", "host": "local"}}
        event["event_id"] = compute_event_id(event)

        with self.assertRaisesRegex(EventReducerError, "observational checkpoint"):
            replay_state(initial, (event,), schema_version=1)

    def test_post_digest_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="intended")
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event_checkpoint = checkpoint_fields(summary="actual")
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=event_checkpoint)
        )

        with self.assertRaisesRegex(EventReducerError, "post_state_digest"):
            replay_state(initial, (event,), schema_version=1)

    def test_invalid_reduced_state_fails_closed(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="x" * 1001)
        post_state = expected_state(initial, checkpoint, sequence_number=1)
        event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, post_state, checkpoint=checkpoint)
        )

        with self.assertRaisesRegex(EventReducerError, "failed validation"):
            replay_state(initial, (event,), schema_version=1)

    def test_observational_timestamp_does_not_change_canonical_digest(self) -> None:
        initial = build_initial_state()
        checkpoint = checkpoint_fields(summary="same")
        first_state = expected_state(initial, checkpoint, sequence_number=1, updated_at="first")
        second_state = expected_state(initial, checkpoint, sequence_number=1, updated_at="second")
        first_event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, first_state, checkpoint=checkpoint, updated_at="first")
        )
        second_event = TransitionJournal(self.create_temp_journal()).append_event(
            checkpoint_event_payload("op-001", initial, second_state, checkpoint=checkpoint, updated_at="second")
        )

        first = replay_state(initial, (first_event,), schema_version=1)
        second = replay_state(initial, (second_event,), schema_version=1)

        self.assertNotEqual(first.state["checkpoint"]["updated_at"], second.state["checkpoint"]["updated_at"])
        self.assertEqual(first.state_digest, second.state_digest)

    def create_temp_journal(self):
        self.addCleanup(self._cleanup_temp_dirs)
        if not hasattr(self, "_temp_dirs"):
            self._temp_dirs = []
        import tempfile

        tmp_dir = tempfile.TemporaryDirectory()
        self._temp_dirs.append(tmp_dir)
        return tmp_dir.name

    def _cleanup_temp_dirs(self) -> None:
        for tmp_dir in getattr(self, "_temp_dirs", []):
            tmp_dir.cleanup()
        self._temp_dirs = []


if __name__ == "__main__":
    unittest.main()
