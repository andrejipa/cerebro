from __future__ import annotations

import math
import unittest
from copy import deepcopy

from core.schema import build_initial_state
from core.state_digest import StateDigestError, canonical_state_digest, canonical_state_payload


def digest(state: dict, *, schema_version: int = 1) -> str:
    return canonical_state_digest(state, schema_version=schema_version)


class StateDigestTests(unittest.TestCase):
    def test_mapping_insertion_order_does_not_change_digest(self) -> None:
        first = {"version": 1, "revision": 0, "checkpoint": {"goal": "Ship", "summary": "Ready"}}
        second = {"checkpoint": {"summary": "Ready", "goal": "Ship"}, "revision": 0, "version": 1}

        self.assertEqual(digest(first), digest(second))

    def test_decision_field_change_changes_digest(self) -> None:
        state = build_initial_state()
        changed = deepcopy(state)
        changed["checkpoint"]["summary"] = "different"

        self.assertNotEqual(digest(state), digest(changed))

    def test_observational_fields_are_excluded_explicitly(self) -> None:
        state = build_initial_state()
        changed = deepcopy(state)
        changed["checkpoint"]["updated_at"] = "2026-04-23T00:00:00Z"
        changed["last_validation"]["validated_at"] = "2026-04-23T00:00:01Z"
        changed["agent_runtime"]["plan"]["updated_at"] = "2026-04-23T00:00:02Z"
        changed["agent_runtime"]["approvals"]["items"] = [
            {
                "id": "approval-1",
                "status": "approved",
                "fingerprint": "f" * 64,
                "action_kind": "exec.command",
                "task_id": "task-1",
                "target": "python -m unittest",
                "reason": "test",
                "requested_at": "2026-04-23T00:00:03Z",
                "resolved_at": "2026-04-23T00:00:04Z",
            }
        ]
        baseline = deepcopy(changed)
        baseline["agent_runtime"]["approvals"]["items"][0]["requested_at"] = "baseline"
        baseline["agent_runtime"]["approvals"]["items"][0]["resolved_at"] = "baseline"
        changed["agent_runtime"]["actions"] = [
            {
                "id": "action-1",
                "kind": "exec.command",
                "status": "applied",
                "summary": "run tests",
                "target": "python -m unittest",
                "task_id": "task-1",
                "batch_id": "",
                "approval_id": "approval-1",
                "artifact_refs": [],
                "rollback_ref": "",
                "details": {},
                "updated_at": "2026-04-23T00:00:05Z",
            }
        ]
        baseline["agent_runtime"]["actions"] = deepcopy(changed["agent_runtime"]["actions"])
        baseline["agent_runtime"]["actions"][0]["updated_at"] = "baseline"
        changed["agent_runtime"]["verification"]["last_run_at"] = "2026-04-23T00:00:06Z"
        baseline["agent_runtime"]["verification"]["last_run_at"] = "baseline"
        changed["agent_runtime"]["memory"]["notes"] = [
            {"id": "note-1", "kind": "fact", "summary": "summary", "source": "test", "ttl_days": 1, "updated_at": "2026-04-23T00:00:07Z"}
        ]
        baseline["agent_runtime"]["memory"]["notes"] = deepcopy(changed["agent_runtime"]["memory"]["notes"])
        baseline["agent_runtime"]["memory"]["notes"][0]["updated_at"] = "baseline"
        changed["agent_runtime"]["audit"]["last_event_at"] = "2026-04-23T00:00:08Z"
        baseline["agent_runtime"]["audit"]["last_event_at"] = "baseline"
        changed["agent_runtime"]["audit"]["trace_thread_id"] = "trace-other"
        changed["agent_runtime"]["audit"]["trace_status"] = "degraded"
        changed["agent_runtime"]["audit"]["trace_integrity"] = "partial"
        changed["agent_runtime"]["audit"]["next_event_id"] = 999
        changed["agent_runtime"]["audit"]["last_trace_error"] = "observational"
        changed["agent_runtime"]["audit"]["last_trace_error_at"] = "2026-04-23T00:00:09Z"
        changed["agent_runtime"]["audit"]["rollback_points"] = [
            {"id": "rollback-1", "kind": "state", "artifact_ref": "state.json", "created_at": "2026-04-23T00:00:10Z"}
        ]
        baseline["agent_runtime"]["audit"]["rollback_points"] = deepcopy(changed["agent_runtime"]["audit"]["rollback_points"])
        baseline["agent_runtime"]["audit"]["rollback_points"][0]["created_at"] = "baseline"

        self.assertEqual(digest(baseline), digest(changed))

    def test_observational_exclusions_are_path_specific(self) -> None:
        state = build_initial_state()
        changed = deepcopy(state)
        state["checkpoint"]["host"] = "host-a"
        changed["checkpoint"]["host"] = "host-b"

        self.assertNotEqual(digest(state), digest(changed))

    def test_absent_optional_field_and_explicit_null_are_different(self) -> None:
        state = build_initial_state()
        changed = deepcopy(state)
        changed["checkpoint"]["operator_note"] = None

        self.assertNotEqual(digest(state), digest(changed))

    def test_list_order_is_semantic_and_preserved(self) -> None:
        state = build_initial_state()
        first = deepcopy(state)
        second = deepcopy(state)
        first["sources"] = [
            {"path": "a.txt", "sha256": "a" * 64, "role": "primary"},
            {"path": "b.txt", "sha256": "b" * 64, "role": "reference"},
        ]
        second["sources"] = list(reversed(first["sources"]))

        self.assertNotEqual(digest(first), digest(second))

    def test_schema_version_is_part_of_digest(self) -> None:
        state = build_initial_state()

        self.assertNotEqual(digest(state, schema_version=1), digest(state, schema_version=2))

    def test_payload_omits_observational_fields(self) -> None:
        state = build_initial_state()
        payload = canonical_state_payload(state, schema_version=1)

        self.assertNotIn("updated_at", payload["state"]["checkpoint"])
        self.assertNotIn("validated_at", payload["state"]["last_validation"])
        self.assertNotIn("trace_thread_id", payload["state"]["agent_runtime"]["audit"])

    def test_non_string_object_key_fails_closed(self) -> None:
        with self.assertRaisesRegex(StateDigestError, "keys must be strings"):
            digest({1: "bad"})

    def test_non_finite_float_fails_closed(self) -> None:
        with self.assertRaisesRegex(StateDigestError, "floats must be finite"):
            digest({"value": math.nan})

    def test_unsupported_object_type_fails_closed(self) -> None:
        with self.assertRaisesRegex(StateDigestError, "unsupported state value type"):
            digest({"value": object()})

    def test_schema_version_must_be_positive_integer(self) -> None:
        with self.assertRaisesRegex(StateDigestError, "schema_version must be a positive integer"):
            digest(build_initial_state(), schema_version=0)


if __name__ == "__main__":
    unittest.main()
