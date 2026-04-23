from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.transition_journal import TransitionJournal, TransitionJournalError, compute_event_id


def make_event(operation_id: str = "op-001", *, event_type: str = "operation.prepared") -> dict:
    return {
        "event_type": event_type,
        "event_version": 1,
        "schema_version": 1,
        "operation_id": operation_id,
        "pre_state_digest": "sha256:" + "a" * 64,
        "post_state_digest": "sha256:" + "b" * 64,
        "deterministic_fields": {"intent": operation_id},
        "observational_fields": {"pid": 1},
    }


class TransitionJournalTests(unittest.TestCase):
    def test_append_assigns_monotonic_sequence_and_previous_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")

            first = journal.append_event(make_event("op-001"))
            second = journal.append_event(make_event("op-002"))

            self.assertEqual(first["sequence_number"], 1)
            self.assertEqual(first["previous_event_id"], "")
            self.assertEqual(second["sequence_number"], 2)
            self.assertEqual(second["previous_event_id"], first["event_id"])
            self.assertEqual(journal.read_events(), (first, second))
            self.assertEqual(journal.read_head(), {"sequence_number": 2, "event_id": second["event_id"]})

    def test_head_is_cache_not_authority(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            first = journal.append_event(make_event("op-001"))
            journal.head_path.write_text('{"sequence_number":999,"event_id":"sha256:stale"}\n', encoding="utf-8")

            second = journal.append_event(make_event("op-002"))

            self.assertEqual(second["sequence_number"], 2)
            self.assertEqual(second["previous_event_id"], first["event_id"])
            self.assertEqual(journal.read_head(), {"sequence_number": 2, "event_id": second["event_id"]})

    def test_sequence_gap_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            journal.append_event(make_event("op-001"))
            journal.append_event(make_event("op-002"))
            (Path(tmp_dir) / "journal" / "000000000000000001.json").unlink()

            with self.assertRaisesRegex(TransitionJournalError, "sequence gap"):
                journal.read_events()

    def test_corrupt_event_id_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            journal.append_event(make_event("op-001"))
            path = Path(tmp_dir) / "journal" / "000000000000000001.json"
            event = json.loads(path.read_text(encoding="utf-8"))
            event["operation_id"] = "op-tampered"
            path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(TransitionJournalError, "event_id mismatch"):
                journal.read_events()

    def test_previous_event_id_mismatch_fails_closed_even_with_recomputed_event_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            journal.append_event(make_event("op-001"))
            journal.append_event(make_event("op-002"))
            path = Path(tmp_dir) / "journal" / "000000000000000002.json"
            event = json.loads(path.read_text(encoding="utf-8"))
            event["previous_event_id"] = "sha256:wrong"
            event["event_id"] = compute_event_id(event)
            path.write_text(json.dumps(event, sort_keys=True, separators=(",", ":")) + "\n", encoding="utf-8")

            with self.assertRaisesRegex(TransitionJournalError, "previous_event_id mismatch"):
                journal.read_events()

    def test_abandoned_tmp_file_is_not_a_committed_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            first = journal.append_event(make_event("op-001"))
            tmp_path = Path(tmp_dir) / "journal" / "000000000000000002.json.tmp"
            tmp_path.write_text('{"sequence_number":2}\n', encoding="utf-8")

            second = journal.append_event(make_event("op-002"))

            self.assertEqual(journal.read_events(), (first, second))
            self.assertFalse(tmp_path.exists())

    def test_invalid_json_file_name_in_journal_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            journal.append_event(make_event("op-001"))
            invalid = Path(tmp_dir) / "journal" / "not-a-sequence.json"
            invalid.write_text("{}\n", encoding="utf-8")

            with self.assertRaisesRegex(TransitionJournalError, "invalid transition journal file name"):
                journal.read_events()

    def test_head_write_failure_does_not_reclassify_committed_event_as_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            original_write = journal._write_json_replace

            def write_or_fail_head(path: Path, payload: dict) -> None:
                if path.name == "HEAD":
                    raise TransitionJournalError("HEAD cache write failed")
                original_write(path, payload)

            with mock.patch.object(journal, "_write_json_replace", side_effect=write_or_fail_head):
                committed = journal.append_event(make_event("op-001"))

            self.assertEqual(journal.read_events(), (committed,))
            self.assertEqual(journal.read_head(), {"sequence_number": 1, "event_id": committed["event_id"]})

    def test_input_cannot_predeclare_ordering_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            event = make_event()
            event["sequence_number"] = 1

            with self.assertRaisesRegex(TransitionJournalError, "must not predeclare ordering fields"):
                journal.append_event(event)

    def test_malformed_state_digest_fields_fail_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            event = make_event()
            event["pre_state_digest"] = "sha256:pre"

            with self.assertRaisesRegex(TransitionJournalError, "pre_state_digest must be a sha256 digest"):
                journal.append_event(event)

    def test_concurrent_sequence_creation_cannot_be_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            original_write_once = journal._write_event_file_once
            concurrent_payload = b'{"concurrent":true}\n'

            def create_conflict_then_write(path: Path, payload: dict) -> None:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_bytes(concurrent_payload)
                original_write_once(path, payload)

            with mock.patch.object(journal, "_write_event_file_once", side_effect=create_conflict_then_write):
                with self.assertRaisesRegex(TransitionJournalError, "sequence already exists: 1"):
                    journal.append_event(make_event("op-001"))

            self.assertEqual((Path(tmp_dir) / "journal" / "000000000000000001.json").read_bytes(), concurrent_payload)

    def test_missing_required_transition_record_field_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            journal = TransitionJournal(Path(tmp_dir) / "journal")
            event = make_event()
            del event["deterministic_fields"]

            with self.assertRaisesRegex(TransitionJournalError, "missing required fields"):
                journal.append_event(event)


if __name__ == "__main__":
    unittest.main()
