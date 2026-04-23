from __future__ import annotations

import unittest
import math
from copy import deepcopy

from core.replay_model import (
    ACCEPTED,
    DISCARD,
    ReplayModelError,
    build_snapshot_metadata,
    evaluate_snapshot,
    replay_digest_chain,
)
from core.schema import build_initial_state
from core.state_digest import canonical_state_digest
from core.transition_journal import TransitionJournal


def digest(state: dict, *, schema_version: int = 1) -> str:
    return canonical_state_digest(state, schema_version=schema_version)


def transition_payload(operation_id: str, pre_state: dict, post_state: dict, *, schema_version: int = 1) -> dict:
    return {
        "event_type": "state.transition",
        "event_version": 1,
        "schema_version": schema_version,
        "operation_id": operation_id,
        "pre_state_digest": digest(pre_state, schema_version=schema_version),
        "post_state_digest": digest(post_state, schema_version=schema_version),
        "deterministic_fields": {"operation_id": operation_id},
        "observational_fields": {},
    }


class ReplayModelTests(unittest.TestCase):
    def test_empty_replay_head_is_initial_state_digest(self) -> None:
        initial = build_initial_state()

        replay = replay_digest_chain(initial, (), schema_version=1)

        self.assertEqual(replay.sequence_number, 0)
        self.assertEqual(replay.event_id, "")
        self.assertEqual(replay.state_digest, digest(initial))

    def test_replay_digest_chain_accepts_contiguous_committed_events(self) -> None:
        initial = build_initial_state()
        first_state = deepcopy(initial)
        first_state["checkpoint"]["summary"] = "first"
        second_state = deepcopy(first_state)
        second_state["checkpoint"]["summary"] = "second"
        journal = TransitionJournal(self.create_temp_journal())
        first = journal.append_event(transition_payload("op-001", initial, first_state))
        second = journal.append_event(transition_payload("op-002", first_state, second_state))

        replay = replay_digest_chain(initial, journal.read_events(), schema_version=1)

        self.assertEqual(replay.sequence_number, 2)
        self.assertEqual(replay.event_id, second["event_id"])
        self.assertEqual(first["previous_event_id"], "")
        self.assertEqual(replay.state_digest, digest(second_state))

    def test_pre_state_digest_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = journal.append_event(transition_payload("op-001", post_state, post_state))

        with self.assertRaisesRegex(ReplayModelError, "pre_state_digest"):
            replay_digest_chain(initial, (event,), schema_version=1)

    def test_sequence_gap_fails_closed_even_without_filesystem_journal(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        first = journal.append_event(transition_payload("op-001", initial, post_state))
        second = journal.append_event(transition_payload("op-002", post_state, post_state))
        second = dict(second)
        second["sequence_number"] = 3

        with self.assertRaisesRegex(ReplayModelError, "sequence_number"):
            replay_digest_chain(initial, (first, second), schema_version=1)

    def test_previous_event_id_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        first = journal.append_event(transition_payload("op-001", initial, post_state))
        second = dict(journal.append_event(transition_payload("op-002", post_state, post_state)))
        second["previous_event_id"] = "sha256:wrong"

        with self.assertRaisesRegex(ReplayModelError, "previous_event_id"):
            replay_digest_chain(initial, (first, second), schema_version=1)

    def test_event_id_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = dict(journal.append_event(transition_payload("op-001", initial, post_state)))
        event["operation_id"] = "tampered"

        with self.assertRaisesRegex(ReplayModelError, "event_id mismatch"):
            replay_digest_chain(initial, (event,), schema_version=1)

    def test_event_schema_version_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = journal.append_event(transition_payload("op-001", initial, post_state, schema_version=2))

        with self.assertRaisesRegex(ReplayModelError, "schema_version"):
            replay_digest_chain(initial, (event,), schema_version=1)

    def test_snapshot_matching_replay_head_is_accepted(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)
        metadata = build_snapshot_metadata(initial, replay)

        decision = evaluate_snapshot(initial, metadata, replay)

        self.assertEqual(decision.status, ACCEPTED)

    def test_stale_snapshot_is_discarded_not_accepted(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = journal.append_event(transition_payload("op-001", initial, post_state))
        replay = replay_digest_chain(initial, (event,), schema_version=1)
        stale = replay_digest_chain(initial, (), schema_version=1)
        metadata = build_snapshot_metadata(initial, stale)

        decision = evaluate_snapshot(initial, metadata, replay)

        self.assertEqual(decision.status, DISCARD)

    def test_snapshot_ahead_of_replay_fails_closed(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)
        metadata = build_snapshot_metadata(initial, replay)
        metadata["sequence_number"] = 1
        metadata["event_id"] = "sha256:" + "a" * 64

        with self.assertRaisesRegex(ReplayModelError, "ahead"):
            evaluate_snapshot(initial, metadata, replay)

    def test_snapshot_metadata_digest_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)
        metadata = build_snapshot_metadata(initial, replay)
        metadata["state_digest"] = "sha256:" + "f" * 64

        with self.assertRaisesRegex(ReplayModelError, "state_digest"):
            evaluate_snapshot(initial, metadata, replay)

    def test_snapshot_state_digest_not_matching_replay_head_fails_closed(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)
        changed = deepcopy(initial)
        changed["checkpoint"]["summary"] = "changed"
        metadata = build_snapshot_metadata(changed, replay)

        with self.assertRaisesRegex(ReplayModelError, "replay head"):
            evaluate_snapshot(changed, metadata, replay)

    def test_snapshot_schema_version_mismatch_fails_closed(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)
        metadata = build_snapshot_metadata(initial, replay)
        metadata["schema_version"] = 2

        with self.assertRaisesRegex(ReplayModelError, "schema_version"):
            evaluate_snapshot(initial, metadata, replay)

    def test_malformed_snapshot_metadata_fails_closed(self) -> None:
        initial = build_initial_state()
        replay = replay_digest_chain(initial, (), schema_version=1)

        with self.assertRaisesRegex(ReplayModelError, "missing required fields"):
            evaluate_snapshot(initial, {"schema_version": 1}, replay)

    def test_non_sha_digest_fields_fail_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = dict(journal.append_event(transition_payload("op-001", initial, post_state)))
        event["post_state_digest"] = "sha256:not-a-real-digest"

        with self.assertRaisesRegex(ReplayModelError, "post_state_digest"):
            replay_digest_chain(initial, (event,), schema_version=1)

    def test_non_finite_event_payload_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = dict(journal.append_event(transition_payload("op-001", initial, post_state)))
        event["deterministic_fields"] = {"score": math.nan}

        with self.assertRaisesRegex(ReplayModelError, "floats must be finite"):
            replay_digest_chain(initial, (event,), schema_version=1)

    def test_non_string_event_payload_key_fails_closed(self) -> None:
        initial = build_initial_state()
        post_state = deepcopy(initial)
        post_state["checkpoint"]["summary"] = "post"
        journal = TransitionJournal(self.create_temp_journal())
        event = dict(journal.append_event(transition_payload("op-001", initial, post_state)))
        event["observational_fields"] = {1: "bad"}

        with self.assertRaisesRegex(ReplayModelError, "keys must be strings"):
            replay_digest_chain(initial, (event,), schema_version=1)

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
