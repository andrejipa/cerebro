from __future__ import annotations

import unittest

from core.schema import build_initial_state
from core.validation import validate_state_data


def _valid_state() -> dict:
    state = build_initial_state()
    state["sources"] = [
        {
            "path": "tracked.txt",
            "sha256": "a" * 64,
            "role": "primary",
        }
    ]
    state["last_validation"] = {
        "validated_at": "2026-04-16T00:00:00+00:00",
        "result": "ok",
        "details": [],
    }
    return state


class ValidationApprovalGuardTests(unittest.TestCase):
    def test_validate_state_rejects_failed_sensitive_action_without_approval_id(self) -> None:
        state = _valid_state()
        state["agent_runtime"]["actions"] = [
            {
                "id": "act-001",
                "kind": "fs.write_patch",
                "status": "failed",
                "summary": "Failed without approval.",
                "target": "tracked.txt",
                "task_id": "",
                "batch_id": "",
                "approval_id": "",
                "artifact_refs": [],
                "rollback_ref": "",
                "details": {"failure_message": "command exited with non-zero status"},
                "updated_at": "2026-04-16T00:02:00+00:00",
            }
        ]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_action_status", {item["code"] for item in errors})
        self.assertTrue(any("requires a non-empty approval_id" in item["message"] for item in errors))

    def test_validate_state_rejects_failed_destructive_create_without_approval_id(self) -> None:
        state = _valid_state()
        state["agent_runtime"]["actions"] = [
            {
                "id": "act-001",
                "kind": "fs.create_file",
                "status": "failed",
                "summary": "Failed overwrite without approval.",
                "target": "draft.txt",
                "task_id": "",
                "batch_id": "",
                "approval_id": "",
                "artifact_refs": ["artifacts/actions/act-001/preimage.txt"],
                "rollback_ref": "artifacts/actions/act-001/preimage.txt",
                "details": {"created_new": False, "path": "draft.txt"},
                "updated_at": "2026-04-16T00:02:00+00:00",
            }
        ]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_action_status", {item["code"] for item in errors})
        self.assertTrue(any("kind fs.create_file requires a non-empty approval_id" in item["message"] for item in errors))


if __name__ == "__main__":
    unittest.main()
