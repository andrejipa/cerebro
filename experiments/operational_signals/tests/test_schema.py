from __future__ import annotations

import unittest

from experiments.operational_signals.schema import (
    SchemaError,
    append_record,
    compute_candidate_trigger,
    normalize_record,
    validate_registry_payload,
)


def _base_record(**overrides):
    payload = {
        "id": "uuc-fixed-001",
        "timestamp": "2026-04-20T18:00:00Z",
        "project_context": "demo-project",
        "task_description": "recover continuity for a task",
        "query_or_need": "where is the current approved path",
        "surface_used": ["analyze", "status-export"],
        "failure_mode": "EXCESSIVE_MANUAL_SEARCH",
        "manual_workaround": "opened README manually after exports",
        "operational_cost": {
            "minutes_spent": 12,
            "extra_files_opened": 6,
            "manual_search_rounds": 3,
        },
        "repeat_count": 2,
        "evidence": ["README.md", "docs/operations/SYSTEM_STATE.md"],
        "confidence": "medium",
        "notes": "synthetic record",
    }
    payload.update(overrides)
    return payload


class SchemaTests(unittest.TestCase):
    def test_normalize_record_computes_candidate_trigger_and_score(self) -> None:
        record = normalize_record(_base_record())
        self.assertTrue(record.candidate_trigger)
        self.assertGreaterEqual(record.trigger_score, 0.55)

    def test_invalid_failure_mode_fails_closed(self) -> None:
        with self.assertRaises(SchemaError):
            normalize_record(_base_record(failure_mode="UNKNOWN"))

    def test_invalid_confidence_fails_closed(self) -> None:
        with self.assertRaises(SchemaError):
            normalize_record(_base_record(confidence="certain"))

    def test_candidate_trigger_requires_repeat_and_non_low_confidence(self) -> None:
        self.assertFalse(compute_candidate_trigger(_base_record(repeat_count=1)))
        self.assertFalse(compute_candidate_trigger(_base_record(confidence="low")))
        self.assertTrue(compute_candidate_trigger(_base_record()))

    def test_duplicate_ids_are_rejected(self) -> None:
        payload = {"schema_version": "1", "unmet_use_case": [_base_record()]}
        with self.assertRaises(SchemaError):
            append_record(payload, _base_record())

    def test_registry_payload_validates_required_top_level_shape(self) -> None:
        validate_registry_payload({"schema_version": "1", "unmet_use_case": [_base_record()]})
        with self.assertRaises(SchemaError):
            validate_registry_payload({"schema_version": "2", "unmet_use_case": []})
