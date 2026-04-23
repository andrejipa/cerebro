from __future__ import annotations

import json
import os
import threading
import tempfile
import time
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from core.agent_runtime import MAX_ACTION_HISTORY, MAX_USED_BATCH_IDS
from core.schema import build_initial_state
from core.state_store import (
    SESSION_CLAIMS_DIR_ENV_VAR,
    SESSION_LIVE_PROOFS_DIR_ENV_VAR,
    StateStore,
    StateStoreError,
    StateValidationError,
)


class StateStoreTests(unittest.TestCase):
    def _seed_valid_runtime(self, root: Path) -> tuple[StateStore, Path]:
        tracked = root / "tracked.txt"
        tracked.write_text("hello", encoding="utf-8")
        store = StateStore(root)
        store.save_state(build_initial_state())
        store.register_sources(["tracked.txt"])
        return store, tracked

    def _seed_trace_plan(self, store: StateStore) -> dict:
        validation = store.validate_state()
        return store.update_agent_plan(
            {
                "goal": "Observe trace behavior",
                "summary": "Seed one runtime task for trace tests.",
                "tasks": [
                    {
                        "id": "task-001",
                        "title": "Trace task",
                        "status": "ready",
                        "details": "Trace task",
                        "depends_on": [],
                        "working_set": ["tracked.txt"],
                        "acceptance_criteria": ["event log remains coherent"],
                        "action_ids": [],
                    }
                ],
                "command_registry": [],
                "required_command_ids": [],
                "autonomy_level": "A2",
                "protected_paths": [".cerebro/**", ".git/**"],
                "blocked_command_prefixes": ["rm"],
                "approval_required_kinds": ["fs.write_patch"],
            },
            validated_revision=validation["revision"],
        )

    def _read_session_claim(self, store: StateStore, claim_id: str) -> dict:
        claim_data, claim_errors = store._read_session_claim_file(claim_id)
        self.assertEqual(claim_errors, [])
        self.assertIsNotNone(claim_data)
        return claim_data

    def _read_session_claim_bytes(self, store: StateStore, claim_id: str, *, backend: str | None = None) -> bytes | None:
        return store._read_optional_session_claim_bytes(claim_id, backend=backend)

    def test_wincred_claim_storage_round_trips_large_payload_via_compression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = (
                json.dumps(
                    {
                        "claim_id": "claim-1234567890abcdef1234567890abcdef",
                        "session_id": "session-1234567890abcdef1234567890abcdef",
                        "root_sha256": "a" * 64,
                        "session_token_sha256": "b" * 64,
                        "live_proof_id": "proof-1234567890abcdef1234567890abcdef",
                        "session_live_proof_sha256": "c" * 64,
                        "owner_binding_sha256": "d" * 64,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            captured: dict[str, bytes] = {}

            def fake_write(target_name: str, raw_payload: bytes, *, username: str = "") -> None:
                captured[target_name] = raw_payload

            def fake_read(target_name: str) -> bytes | None:
                return captured.get(target_name)

            with mock.patch("core.state_store.write_generic_credential", side_effect=fake_write), mock.patch(
                "core.state_store.read_generic_credential",
                side_effect=fake_read,
            ):
                store._write_session_claim_bytes("claim-1", payload, backend="wincred")
                stored_payload = next(iter(captured.values()))
                self.assertLess(len(stored_payload), len(payload))
                self.assertEqual(
                    store._read_optional_session_claim_bytes("claim-1", backend="wincred"),
                    payload,
                )

    def test_wincred_live_proof_storage_round_trips_large_payload_via_compression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = (
                json.dumps(
                    {
                        "proof_id": "proof-1234567890abcdef1234567890abcdef",
                        "session_id": "session-1234567890abcdef1234567890abcdef",
                        "root_sha256": "a" * 64,
                        "session_live_proof": "x" * 96,
                    },
                    ensure_ascii=False,
                    separators=(",", ":"),
                )
                + "\n"
            ).encode("utf-8")
            captured: dict[str, bytes] = {}

            def fake_write(target_name: str, raw_payload: bytes, *, username: str = "") -> None:
                captured[target_name] = raw_payload

            def fake_read(target_name: str) -> bytes | None:
                return captured.get(target_name)

            with mock.patch("core.state_store.write_generic_credential", side_effect=fake_write), mock.patch(
                "core.state_store.read_generic_credential",
                side_effect=fake_read,
            ):
                store._write_session_live_proof_bytes("proof-1", payload, backend="wincred")
                stored_payload = next(iter(captured.values()))
                self.assertLess(len(stored_payload), len(payload))
                self.assertEqual(
                    store._read_optional_session_live_proof_bytes("proof-1", backend="wincred"),
                    payload,
                )

    def test_wincred_claim_storage_reads_legacy_plain_payload_without_compression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = b'{"claim_id":"legacy"}\n'

            with mock.patch("core.state_store.read_generic_credential", return_value=payload):
                self.assertEqual(
                    store._read_optional_session_claim_bytes("claim-legacy", backend="wincred"),
                    payload,
                )

    def test_wincred_claim_storage_rejects_corrupted_compressed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = b"CZX1not-a-valid-zlib-stream"

            with mock.patch("core.state_store.read_generic_credential", return_value=payload):
                with self.assertRaises(StateStoreError) as exc_info:
                    store._read_optional_session_claim_bytes("claim-corrupted", backend="wincred")

            self.assertIn("failed to decode external session claim from WinCred storage", str(exc_info.exception))

    def test_wincred_live_proof_storage_reads_legacy_plain_payload_without_compression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = b'{"proof_id":"legacy"}\n'

            with mock.patch("core.state_store.read_generic_credential", return_value=payload):
                self.assertEqual(
                    store._read_optional_session_live_proof_bytes("proof-legacy", backend="wincred"),
                    payload,
                )

    def test_wincred_live_proof_storage_rejects_corrupted_compressed_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            payload = b"CZX1not-a-valid-zlib-stream"

            with mock.patch("core.state_store.read_generic_credential", return_value=payload):
                with self.assertRaises(StateStoreError) as exc_info:
                    store._read_optional_session_live_proof_bytes("proof-corrupted", backend="wincred")

            self.assertIn("failed to decode external session live proof from WinCred storage", str(exc_info.exception))

    def test_save_and_load_initial_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            state = build_initial_state()

            store.save_state(state)

            loaded = store.load_state()
            self.assertEqual(loaded, state)

    def test_save_invalid_state_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            state = build_initial_state()
            del state["version"]

            with self.assertRaises(StateValidationError):
                store.save_state(state)

    def test_validate_ignores_missing_artifacts_for_rolled_back_actions(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.update_agent_approval(
                {
                    "id": "apr-001",
                    "status": "approved",
                    "fingerprint": "fp-rolled-back-delete",
                    "action_kind": "fs.delete_soft",
                    "task_id": "",
                    "target": "draft.txt",
                    "reason": "approved for delete",
                    "requested_at": "2026-04-15T00:00:00+00:00",
                    "resolved_at": "2026-04-15T00:00:05+00:00",
                }
            )
            store.record_agent_action(
                {
                    "id": "act-rolled-back",
                    "kind": "fs.delete_soft",
                    "status": "rolled_back",
                    "summary": "restore deleted file",
                    "target": "draft.txt",
                    "task_id": "",
                    "batch_id": "",
                    "approval_id": "apr-001",
                    "artifact_refs": ["trash/act-rolled-back/draft.txt"],
                    "rollback_ref": "trash/act-rolled-back/draft.txt",
                    "details": {"trash_ref": "trash/act-rolled-back/draft.txt"},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                }
            )

            result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])

    def test_record_agent_actions_batch_commits_in_one_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)
            validation = store.validate_state()

            updated = store.record_agent_actions(
                [
                    {
                        "id": "act-001",
                        "kind": "fs.create_file",
                        "status": "applied",
                        "summary": "create one",
                        "target": "draft-a.txt",
                        "task_id": "task-001",
                        "batch_id": "batch-001",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {},
                        "updated_at": "2026-04-15T00:00:00+00:00",
                    },
                    {
                        "id": "act-002",
                        "kind": "fs.create_file",
                        "status": "applied",
                        "summary": "create two",
                        "target": "draft-b.txt",
                        "task_id": "task-001",
                        "batch_id": "batch-001",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {},
                        "updated_at": "2026-04-15T00:00:01+00:00",
                    },
                ],
                validated_revision=validation["revision"],
            )

            self.assertEqual(updated["revision"], validation["revision"] + 1)
            self.assertEqual(
                [action["id"] for action in updated["agent_runtime"]["actions"]],
                ["act-001", "act-002"],
            )
            events = store.read_recent_events(limit=10)
            action_ids = [
                event.get("action_id")
                for event in events
                if event.get("event") == "action_recorded"
            ]
            self.assertEqual(action_ids[-2:], ["act-001", "act-002"])

    def test_record_agent_actions_prunes_task_and_pending_refs_when_history_trims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            updated = self._seed_trace_plan(store)

            def action_record(action_id: str) -> dict:
                return {
                    "id": action_id,
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": f"create {action_id}",
                    "target": f"{action_id}.txt",
                    "task_id": "task-001",
                    "batch_id": "",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                }

            updated = store.record_agent_action(action_record("act-old"), validated_revision=updated["revision"])
            for index in range(1, MAX_ACTION_HISTORY + 1):
                updated = store.record_agent_action(
                    action_record(f"act-{index:03d}"),
                    validated_revision=updated["revision"],
                )

            validation = store.validate_state()

            self.assertTrue(validation["ok"], validation["errors"])
            runtime = updated["agent_runtime"]
            retained_action_ids = [action["id"] for action in runtime["actions"]]
            self.assertEqual(len(retained_action_ids), MAX_ACTION_HISTORY)
            self.assertNotIn("act-old", retained_action_ids)
            self.assertEqual(retained_action_ids[0], "act-001")
            self.assertEqual(retained_action_ids[-1], f"act-{MAX_ACTION_HISTORY:03d}")
            task_action_ids = runtime["plan"]["tasks"][0]["action_ids"]
            self.assertNotIn("act-old", task_action_ids)
            self.assertEqual(task_action_ids, retained_action_ids)
            self.assertNotIn("act-old", runtime["verification"]["pending_action_ids"])
            self.assertEqual(runtime["verification"]["pending_action_ids"], retained_action_ids)
            self.assertEqual(runtime["audit"]["last_action_id"], f"act-{MAX_ACTION_HISTORY:03d}")

    def test_record_agent_actions_prunes_verification_check_coverage_when_history_trims(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            updated = self._seed_trace_plan(store)
            updated = store.update_agent_plan(
                {
                    "goal": "Observe trace behavior",
                    "summary": "Seed one runtime task for trace tests.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Trace task",
                            "status": "ready",
                            "details": "Trace task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["event log remains coherent"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=updated["revision"],
            )

            updated = store.record_agent_action(
                {
                    "id": "act-old",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "create old",
                    "target": "act-old.txt",
                    "task_id": "task-001",
                    "batch_id": "",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=updated["revision"],
            )
            updated = store.update_agent_verification(
                {
                    "required_command_ids": ["cmd-001"],
                    "pending_action_ids": ["act-old"],
                    "last_run_at": "2026-04-15T00:00:10+00:00",
                    "status": "passed",
                    "state_check": {
                        "status": "passed",
                        "exit_code": 0,
                        "message": "old action verified",
                    },
                    "checks": [
                        {
                            "id": "check-cmd-001",
                            "command_id": "cmd-001",
                            "status": "passed",
                            "exit_code": 0,
                            "artifact_ref": "",
                            "artifact_sha256": "",
                            "covered_action_ids": ["act-old"],
                            "message": "old action verified",
                        }
                    ],
                },
                validated_revision=updated["revision"],
            )

            for index in range(1, MAX_ACTION_HISTORY + 1):
                updated = store.record_agent_action(
                    {
                        "id": f"act-{index:03d}",
                        "kind": "exec.command",
                        "status": "applied",
                        "summary": f"observe {index:03d}",
                        "target": f"echo {index:03d}",
                        "task_id": "task-001",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {"side_effect": "read_only"},
                        "updated_at": "2026-04-15T00:00:20+00:00",
                    },
                    validated_revision=updated["revision"],
                )

            validation = store.validate_state()

            self.assertTrue(validation["ok"], validation["errors"])
            runtime = updated["agent_runtime"]
            self.assertEqual(len(runtime["verification"]["checks"]), 1)
            self.assertEqual(runtime["verification"]["checks"][0]["command_id"], "cmd-001")
            self.assertEqual(runtime["verification"]["checks"][0]["covered_action_ids"], [])
            self.assertEqual(runtime["verification"]["state_check"]["status"], "passed")
            self.assertEqual(runtime["verification"]["state_check"]["message"], "old action verified")
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertNotIn("act-old", runtime["plan"]["tasks"][0]["action_ids"])

    def test_record_agent_actions_retains_batch_registry_beyond_action_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            updated = self._seed_trace_plan(store)

            updated = store.record_agent_action(
                {
                    "id": "act-old",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "create old batch file",
                    "target": "old-batch.txt",
                    "task_id": "task-001",
                    "batch_id": "batch-old",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=updated["revision"],
            )
            for index in range(1, MAX_ACTION_HISTORY + 1):
                updated = store.record_agent_action(
                    {
                        "id": f"act-{index:03d}",
                        "kind": "exec.command",
                        "status": "applied",
                        "summary": f"observe {index:03d}",
                        "target": f"python -c print({index})",
                        "task_id": "",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {"side_effect": "read_only"},
                        "updated_at": "2026-04-15T00:00:20+00:00",
                    },
                    validated_revision=updated["revision"],
                )

            validation = store.validate_state()

            self.assertTrue(validation["ok"], validation["errors"])
            runtime = updated["agent_runtime"]
            self.assertNotIn("act-old", [action["id"] for action in runtime["actions"]])
            self.assertIn("batch-old", runtime["batch_registry"]["used_ids"])

    def test_update_agent_plan_keeps_historical_actions_valid_even_when_task_ids_are_reused(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            updated = self._seed_trace_plan(store)
            plan_generation_id = updated["agent_runtime"]["plan"]["generation_id"]

            updated = store.record_agent_action(
                {
                    "id": "act-old",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "create draft",
                    "target": "draft.txt",
                    "task_id": "task-001",
                    "batch_id": "batch-old",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {"plan_generation_id": plan_generation_id},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=updated["revision"],
            )

            updated = store.update_agent_plan(
                {
                    "goal": "Second plan",
                    "summary": "Replan after historical action.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "New task with reused id",
                            "status": "ready",
                            "details": "Fresh current task",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=updated["revision"],
            )

            validation = store.validate_state()

            self.assertTrue(validation["ok"], validation["errors"])
            runtime = updated["agent_runtime"]
            self.assertEqual(runtime["plan"]["tasks"][0]["action_ids"], [])
            self.assertEqual(runtime["batch_registry"]["used_ids"], [])
            self.assertEqual(runtime["actions"][0]["id"], "act-old")

    def test_update_agent_plan_rejects_verify_command_not_declared_read_only(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            validation = store.validate_state()

            with self.assertRaises(StateValidationError) as exc_info:
                store.update_agent_plan(
                    {
                        "goal": "Unsafe verify metadata",
                        "summary": "Verify commands must stay read-only.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Inspect tracked file",
                                "status": "ready",
                                "details": "Inspect tracked file",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["verify succeeds"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [
                            {
                                "id": "cmd-001",
                                "argv": ["python", "-c", "print('unsafe')"],
                                "cwd": ".",
                                "timeout_ms": 1000,
                                "determinism": "high",
                                "side_effect": "workspace_write",
                                "risk": "low",
                                "allow_in_verify": True,
                            }
                        ],
                        "required_command_ids": ["cmd-001"],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                )

            self.assertTrue(
                any(
                    error["code"] == "invalid_command_registry_command_verify_side_effect"
                    for error in exc_info.exception.errors
                ),
                exc_info.exception.errors,
            )

    def test_record_agent_actions_caps_batch_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            updated = self._seed_trace_plan(store)

            action_records = [
                {
                    "id": f"act-{index:03d}",
                    "kind": "exec.command",
                    "status": "applied",
                    "summary": f"observe {index:03d}",
                    "target": f"python -c print({index})",
                    "task_id": "",
                    "batch_id": f"batch-{index:03d}",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {"side_effect": "read_only"},
                    "updated_at": f"2026-04-15T00:00:{index % 60:02d}+00:00",
                }
                for index in range(MAX_USED_BATCH_IDS + 1)
            ]

            updated = store.record_agent_actions(action_records, validated_revision=updated["revision"])

            validation = store.validate_state()

            self.assertTrue(validation["ok"], validation["errors"])
            used_batch_ids = updated["agent_runtime"]["batch_registry"]["used_ids"]
            self.assertEqual(len(used_batch_ids), MAX_USED_BATCH_IDS)
            self.assertNotIn("batch-000", used_batch_ids)
            self.assertEqual(used_batch_ids[0], "batch-001")
            self.assertEqual(used_batch_ids[-1], f"batch-{MAX_USED_BATCH_IDS:03d}")

    def test_read_recent_events_returns_last_non_empty_records_and_tolerates_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.logs_dir.mkdir(parents=True, exist_ok=True)
            with store.events_path.open("w", encoding="utf-8", newline="\n") as handle:
                for index in range(12):
                    handle.write(
                        json.dumps(
                            {
                                "recorded_at": f"2026-04-13T00:00:{index:02d}+00:00",
                                "event": "runtime_event",
                                "index": index,
                            }
                        )
                    )
                    handle.write("\n")
                handle.write("\n")
                handle.write("{not-json}\n")
                handle.write(
                    json.dumps(
                        {
                            "recorded_at": "2026-04-13T00:01:00+00:00",
                            "event": "runtime_event",
                            "index": 99,
                        }
                    )
                )
                handle.write("\n")

            events = store.read_recent_events(limit=3)

            self.assertEqual([event["event"] for event in events], ["runtime_event", "unreadable_event_log_record", "runtime_event"])
            self.assertEqual(events[0]["index"], 11)
            self.assertEqual(events[-1]["index"], 99)

    def test_trace_append_failure_marks_degraded_without_losing_persisted_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)

            with mock.patch.object(store, "_write_trace_event_line", side_effect=OSError("disk full")):
                updated = store.record_agent_action(
                    {
                        "id": "act-001",
                        "kind": "fs.create_file",
                        "status": "applied",
                        "summary": "create artifact",
                        "target": "artifact.txt",
                        "task_id": "task-001",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {},
                        "updated_at": "2026-04-13T00:00:00+00:00",
                    }
                )

            self.assertEqual([action["id"] for action in updated["agent_runtime"]["actions"]], ["act-001"])
            reloaded = store.load_state()
            self.assertEqual([action["id"] for action in reloaded["agent_runtime"]["actions"]], ["act-001"])
            self.assertEqual(reloaded["agent_runtime"]["audit"]["trace_status"], "degraded")
            self.assertEqual(reloaded["agent_runtime"]["audit"]["trace_integrity"], "partial")
            self.assertIn("disk full", reloaded["agent_runtime"]["audit"]["last_trace_error"])
            self.assertFalse(any(event.get("action_id") == "act-001" for event in store.read_recent_events(limit=10)))

    def test_trace_event_ids_are_monotonic_within_trace_thread(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)

            store.record_runtime_event(
                {
                    "event_type": "runtime_probe",
                    "phase": "observe",
                    "step": "runtime_probe",
                    "note": "first",
                }
            )
            store.record_runtime_event(
                {
                    "event_type": "runtime_probe",
                    "phase": "observe",
                    "step": "runtime_probe",
                    "note": "second",
                }
            )

            trace_thread_id = store.load_state()["agent_runtime"]["audit"]["trace_thread_id"]
            events = [
                event
                for event in store.read_recent_events(limit=10)
                if event.get("trace_thread_id") == trace_thread_id
            ]

            self.assertGreaterEqual(len(events), 4)
            event_ids = [event["event_id"] for event in events]
            self.assertTrue(all(event_id.startswith(f"{trace_thread_id}:") for event_id in event_ids))
            self.assertEqual(
                event_ids,
                [f"{trace_thread_id}:{index:06d}" for index in range(1, len(event_ids) + 1)],
            )

    def test_trace_status_recovers_to_healthy_after_successful_append(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)

            with mock.patch.object(store, "_write_trace_event_line", side_effect=OSError("disk full")):
                store.record_runtime_event(
                    {
                        "event_type": "runtime_probe",
                        "phase": "observe",
                        "step": "runtime_probe",
                        "note": "will fail",
                    }
                )

            degraded = store.load_state()["agent_runtime"]["audit"]
            self.assertEqual(degraded["trace_status"], "degraded")
            self.assertEqual(degraded["trace_integrity"], "partial")

            store.record_runtime_event(
                {
                    "event_type": "runtime_probe",
                    "phase": "observe",
                    "step": "runtime_probe",
                    "note": "recovered",
                }
            )

            recovered = store.load_state()["agent_runtime"]["audit"]
            self.assertEqual(recovered["trace_status"], "healthy")
            self.assertEqual(recovered["trace_integrity"], "partial")
            self.assertEqual(recovered["last_trace_error"], "")
            self.assertEqual(recovered["last_trace_error_at"], "")

    def test_runtime_signal_persists_when_trace_append_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)

            with mock.patch.object(store, "_write_trace_event_line", side_effect=OSError("disk full")):
                store.record_runtime_event(
                    {
                        "event_type": "apply_blocked",
                        "phase": "apply",
                        "step": "apply_blocked",
                        "task_id": "task-001",
                        "reason_code": "action_no_effect",
                        "reason": "apply blocked because the action would not change the effective workspace state",
                    }
                )

            state = store.load_state()
            self.assertEqual(state["revision"], 3)
            self.assertEqual(state["agent_runtime"]["audit"]["trace_status"], "degraded")
            self.assertEqual(state["agent_runtime"]["plan"]["tasks"][0]["apply_blocked_count"], 1)
            assessments = {item["id"]: item for item in store.read_task_assessments()}
            self.assertIn("task has 1 blocked apply attempt(s)", assessments["task-001"]["evidence"])

    def test_trace_observability_reports_state_event_divergence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            planned = self._seed_trace_plan(store)
            state = store.load_state()
            state["agent_runtime"]["audit"]["next_event_id"] = planned["agent_runtime"]["audit"]["next_event_id"] + 3
            store.save_state(state, expected_revision=state["revision"])

            trace = store.read_trace_observability()

            self.assertEqual(trace["trace_status"], "healthy")
            self.assertEqual(trace["trace_integrity"], "partial")
            self.assertIn("state_event_gap", trace["diagnostics"])
            self.assertLess(trace["latest_event_number"], trace["expected_last_event_number"])

    def test_read_task_selection_consistency_detects_stale_current_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            validation = store.validate_state()
            updated = store.update_agent_plan(
                {
                    "goal": "Priority",
                    "summary": "Detect stale selection.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Underspecified task",
                            "status": "ready",
                            "details": "Underspecified task",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Scoped task",
                            "status": "ready",
                            "details": "Scoped task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )
            state = store.load_state()
            state["agent_runtime"]["plan"]["current_task_id"] = "task-001"
            store.save_state(state, expected_revision=updated["revision"])

            replay = store.read_task_selection_consistency()

            self.assertEqual(replay["status"], "mismatch")
            self.assertEqual(replay["current_task_id"], "task-001")
            self.assertEqual(replay["derived_task_id"], "task-002")
            self.assertGreater(replay["priority_gap"], 0)

    def test_read_task_assessments_delegates_to_read_model_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            agent_runtime = {"plan": {"tasks": []}}
            recent_events = ({"event": "runtime_probe"},)
            expected = ({"id": "task-001"},)

            with mock.patch.object(
                store._read_models,
                "read_task_assessments",
                return_value=expected,
            ) as delegated:
                result = store.read_task_assessments(
                    event_limit=7,
                    agent_runtime=agent_runtime,
                    recent_events=recent_events,
                )

            self.assertIs(result, expected)
            delegated.assert_called_once_with(
                event_limit=7,
                agent_runtime=agent_runtime,
                recent_events=recent_events,
            )

    def test_read_task_selection_consistency_delegates_to_read_model_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            agent_runtime = {"plan": {"current_task_id": "task-001"}}
            recent_events = ({"event": "plan_updated"},)
            task_assessments = ({"id": "task-001"},)
            expected = {"status": "consistent"}

            with mock.patch.object(
                store._read_models,
                "read_task_selection_consistency",
                return_value=expected,
            ) as delegated:
                result = store.read_task_selection_consistency(
                    agent_runtime=agent_runtime,
                    recent_events=recent_events,
                    task_assessments=task_assessments,
                )

            self.assertIs(result, expected)
            delegated.assert_called_once_with(
                agent_runtime=agent_runtime,
                recent_events=recent_events,
                task_assessments=task_assessments,
            )

    def test_read_task_work_profiles_delegates_to_read_model_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            agent_runtime = {"plan": {"tasks": []}}
            expected = ({"id": "task-001", "workload_mode": "light"},)

            with mock.patch.object(
                store._read_models,
                "read_task_work_profiles",
                return_value=expected,
            ) as delegated:
                result = store.read_task_work_profiles(agent_runtime=agent_runtime)

            self.assertIs(result, expected)
            delegated.assert_called_once_with(agent_runtime=agent_runtime)

    def test_write_session_claim_delegates_to_session_artifacts_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            claim_data = {"claim_id": "claim-1"}

            with mock.patch.object(
                store._session_artifacts,
                "write_session_claim",
                return_value=None,
            ) as delegated:
                store._write_session_claim(claim_data)

            delegated.assert_called_once_with(claim_data)

    def test_read_session_file_delegates_to_session_artifacts_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            expected = ({"session_id": "session-1"}, [])

            with mock.patch.object(
                store._session_artifacts,
                "read_session_file",
                return_value=expected,
            ) as delegated:
                result = store._read_session_file()

            delegated.assert_called_once_with()
            self.assertEqual(result, expected)

    def test_capture_session_live_proof_snapshot_delegates_to_session_artifacts_service(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            expected = {
                "label": "external session live proof",
                "proof_id": "proof-1",
                "backend": "file",
                "bytes": b"payload",
            }

            with mock.patch.object(
                store._session_artifacts,
                "capture_session_live_proof_snapshot",
                return_value=expected,
            ) as delegated:
                snapshot = store._capture_session_live_proof_snapshot(
                    "proof-1",
                    label="external session live proof",
                )

            delegated.assert_called_once_with("proof-1", label="external session live proof")
            self.assertEqual(snapshot, expected)

    def test_trace_events_remain_single_writer_under_concurrent_runtime_event_appends(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            self._seed_trace_plan(store)

            barrier = threading.Barrier(4)
            errors: list[Exception] = []

            def append_event(index: int) -> None:
                local_store = StateStore(root)
                try:
                    barrier.wait(timeout=2)
                    local_store.record_runtime_event(
                        {
                            "event_type": "runtime_probe",
                            "phase": "observe",
                            "step": f"worker_{index}",
                            "worker_index": index,
                        }
                    )
                except Exception as exc:  # pragma: no cover - should keep the list empty
                    errors.append(exc)

            threads = [threading.Thread(target=append_event, args=(index,)) for index in range(4)]
            for thread in threads:
                thread.start()
            for thread in threads:
                thread.join(timeout=2)

            self.assertEqual(errors, [])
            self.assertTrue(all(not thread.is_alive() for thread in threads))
            trace_thread_id = store.load_state()["agent_runtime"]["audit"]["trace_thread_id"]
            events = [
                event
                for event in store.read_recent_events(limit=16)
                if event.get("trace_thread_id") == trace_thread_id
            ]
            event_ids = [event["event_id"] for event in events]
            self.assertEqual(
                event_ids,
                [f"{trace_thread_id}:{index:06d}" for index in range(1, len(event_ids) + 1)],
            )
            self.assertEqual(len(event_ids), len(set(event_ids)))
            self.assertFalse(store.lock_path.exists())

    def test_read_snapshot_and_runtime_returns_coherent_detached_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            state = build_initial_state()
            state["revision"] = 7
            state["agent_runtime"]["plan"] = {
                "goal": "Goal",
                "summary": "Summary",
                "status": "ready",
                "current_task_id": "task-001",
                "updated_at": "2026-04-13T00:00:00+00:00",
                "tasks": [
                    {
                        "id": "task-001",
                        "title": "Task 1",
                        "status": "ready",
                        "details": "Details",
                        "depends_on": [],
                        "working_set": ["tracked.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    }
                ],
            }
            store.save_state(state)

            snapshot, runtime = store.read_snapshot_and_runtime()

            self.assertEqual(snapshot.revision, 7)
            self.assertEqual(runtime["plan"]["current_task_id"], "task-001")

            runtime["plan"]["current_task_id"] = "mutated"
            runtime["plan"]["tasks"][0]["title"] = "Changed"

            persisted_runtime = store.read_agent_runtime()
            self.assertEqual(persisted_runtime["plan"]["current_task_id"], "task-001")
            self.assertEqual(persisted_runtime["plan"]["tasks"][0]["title"], "Task 1")

    def test_record_parallel_approach_consolidation_is_append_only_and_read_derived(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a", "approach-c"],
                    "comparison_basis": ["lower rollback cost", "stronger verify coverage"],
                    "decision": "selected approach B after comparing reversibility and verification cost",
                    "comparison_event_ids": ["evt-001", "evt-002"],
                }
            )

            loaded = store.load_state()
            self.assertEqual(loaded["revision"], 0)

            events = store.read_recent_events(limit=1)
            self.assertEqual(len(events), 1)
            self.assertEqual(events[0]["event"], "parallel_approach_consolidated")
            self.assertEqual(events[0]["winner_id"], "approach-b")
            self.assertIn("consolidation_id", events[0])
            self.assertEqual(events[0]["supersedes_consolidation_id"], "")

            consolidations = store.read_recent_consolidations(limit=1)
            self.assertEqual(len(consolidations), 1)
            consolidation = consolidations[0]
            self.assertEqual(consolidation["subject_kind"], "task")
            self.assertEqual(consolidation["subject_id"], "task-019")
            self.assertEqual(consolidation["consolidation_id"], events[0]["consolidation_id"])
            self.assertEqual(consolidation["supersedes_consolidation_id"], "")
            self.assertEqual(consolidation["compared_approach_ids"], ("approach-a", "approach-b", "approach-c"))
            self.assertEqual(consolidation["winner_id"], "approach-b")
            self.assertEqual(consolidation["rejected_approach_ids"], ("approach-a", "approach-c"))
            self.assertEqual(consolidation["comparison_basis"], ("lower rollback cost", "stronger verify coverage"))
            self.assertEqual(consolidation["decision"], "selected approach B after comparing reversibility and verification cost")

            first_consolidation_id = consolidation["consolidation_id"]

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                    "winner_id": "approach-c",
                    "winner_label": "approach C",
                    "rejected_approach_ids": ["approach-a", "approach-b"],
                    "comparison_basis": ["stronger rollback posture"],
                    "decision": "replaced approach B after rollback review",
                    "comparison_event_ids": ["evt-003"],
                }
            )

            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["supersedes_consolidation_id"], first_consolidation_id)
            self.assertNotEqual(latest_event["consolidation_id"], first_consolidation_id)

    def test_record_parallel_approach_consolidation_rejects_non_exhaustive_or_unresolved_sets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            with self.assertRaisesRegex(StateStoreError, "cover the full compared set"):
                store.record_parallel_approach_consolidation(
                    {
                        "subject_kind": "task",
                        "subject_id": "task-019",
                        "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                        "winner_id": "approach-b",
                        "winner_label": "approach B",
                        "rejected_approach_ids": ["approach-a"],
                        "comparison_basis": ["lower rollback cost"],
                        "decision": "picked approach B",
                        "comparison_event_ids": ["evt-001"],
                    }
                )

            with self.assertRaisesRegex(StateStoreError, "at least one comparison_event_id"):
                store.record_parallel_approach_consolidation(
                    {
                        "subject_kind": "task",
                        "subject_id": "task-019",
                        "compared_approach_ids": ["approach-a", "approach-b"],
                        "winner_id": "approach-b",
                        "winner_label": "approach B",
                        "rejected_approach_ids": ["approach-a"],
                        "comparison_basis": ["lower rollback cost"],
                        "decision": "picked approach B",
                        "comparison_event_ids": [],
                    }
                )

    def test_read_recent_consolidations_returns_latest_valid_record_per_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["lower execution cost"],
                    "decision": "picked approach A first",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]
            first_consolidation_id = first_event["consolidation_id"]
            self.assertEqual(first_event["supersedes_consolidation_id"], "")
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-020",
                    "compared_approach_ids": ["approach-c", "approach-d"],
                    "winner_id": "approach-d",
                    "winner_label": "approach D",
                    "rejected_approach_ids": ["approach-c"],
                    "comparison_basis": ["better verify coverage"],
                    "decision": "picked approach D",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            second_event = store.read_recent_events(limit=1)[0]
            second_consolidation_id = second_event["consolidation_id"]
            self.assertEqual(second_event["supersedes_consolidation_id"], "")
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["stronger rollback posture"],
                    "decision": "replaced approach A after stronger rollback evidence",
                    "comparison_event_ids": ["evt-003"],
                }
            )
            third_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(third_event["supersedes_consolidation_id"], first_consolidation_id)
            self.assertNotEqual(third_event["consolidation_id"], first_consolidation_id)
            self.assertNotEqual(third_event["consolidation_id"], second_consolidation_id)

            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(
                        {
                            "recorded_at": "2026-04-13T10:00:00+00:00",
                            "event": "parallel_approach_consolidated",
                            "subject_kind": "task",
                            "subject_id": "task-019",
                            "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                            "winner_id": "approach-c",
                            "winner_label": "spoofed",
                            "rejected_approach_ids": ["approach-a"],
                            "comparison_basis": ["corrupted"],
                            "decision": "invalid event should be ignored",
                            "comparison_event_ids": ["evt-004"],
                        }
                    )
                )
                handle.write("\n")

            consolidations = store.read_recent_consolidations(limit=3)
            self.assertEqual(len(consolidations), 2)
            self.assertEqual(consolidations[0]["subject_id"], "task-020")
            self.assertEqual(consolidations[1]["subject_id"], "task-019")
            self.assertEqual(consolidations[1]["consolidation_id"], third_event["consolidation_id"])
            self.assertEqual(consolidations[1]["supersedes_consolidation_id"], first_consolidation_id)
            self.assertEqual(consolidations[1]["winner_id"], "approach-b")
            self.assertEqual(consolidations[1]["rejected_approach_ids"], ("approach-a",))

    def test_record_parallel_approach_consolidation_rejects_stale_supersedes_and_replayed_old_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-021",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["first comparison"],
                    "decision": "picked approach A first",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-021",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["rollback posture improved"],
                    "decision": "picked approach B after new evidence",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            latest_event = store.read_recent_events(limit=1)[0]

            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                replayed = dict(first_event)
                replayed["recorded_at"] = "2026-04-13T11:11:11+00:00"
                handle.write(json.dumps(replayed))
                handle.write("\n")

            head = store.read_parallel_approach_consolidation_head("task", "task-021")
            self.assertIsNotNone(head)
            self.assertEqual(head["consolidation_id"], latest_event["consolidation_id"])
            self.assertEqual(head["supersedes_consolidation_id"], first_event["consolidation_id"])
            self.assertEqual(store.read_recent_consolidations(limit=1)[0]["winner_id"], "approach-b")

            with self.assertRaisesRegex(StateStoreError, "must supersede the current head"):
                store.record_parallel_approach_consolidation(
                    {
                        "subject_kind": "task",
                        "subject_id": "task-021",
                        "consolidation_id": "cons-manual",
                        "supersedes_consolidation_id": first_event["consolidation_id"],
                        "compared_approach_ids": ["approach-a", "approach-b"],
                        "winner_id": "approach-a",
                        "winner_label": "approach A",
                        "rejected_approach_ids": ["approach-b"],
                        "comparison_basis": ["stale supersedes"],
                        "decision": "should be rejected",
                        "comparison_event_ids": ["evt-003"],
                    }
                )

    def test_read_parallel_approach_consolidation_heads_batches_subject_head_lookup(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-031",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["first"],
                    "decision": "root",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-031",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["second"],
                    "decision": "head",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            latest_event = store.read_recent_events(limit=1)[0]
            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                replayed = dict(first_event)
                replayed["recorded_at"] = "2026-04-13T10:10:10+00:00"
                handle.write(json.dumps(replayed))
                handle.write("\n")

            heads = store.read_parallel_approach_consolidation_heads(
                [("task", "task-031"), ("task", "missing-task"), ("task", "task-031")]
            )

            self.assertEqual(set(heads.keys()), {("task", "task-031")})
            self.assertEqual(heads[("task", "task-031")]["consolidation_id"], latest_event["consolidation_id"])
            self.assertEqual(heads[("task", "task-031")]["winner_id"], "approach-b")

    def test_read_parallel_approach_consolidation_view_returns_recent_and_requested_heads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-041",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["first"],
                    "decision": "task-041 root",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-042",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["first"],
                    "decision": "task-042 root",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-041",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["second"],
                    "decision": "task-041 head",
                    "comparison_event_ids": ["evt-003"],
                }
            )

            recent, head_map = store.read_parallel_approach_consolidation_view(
                limit=2,
                subjects=[("task", "task-041"), ("task", "missing-task")],
            )

            self.assertEqual([item["subject_id"] for item in recent], ["task-042", "task-041"])
            self.assertEqual(recent[-1]["winner_id"], "approach-b")
            self.assertEqual(set(head_map.keys()), {("task", "task-041")})
            self.assertEqual(head_map[("task", "task-041")]["winner_id"], "approach-b")

    def test_read_recent_consolidations_finds_sparse_subjects_in_large_logs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.logs_dir.mkdir(parents=True, exist_ok=True)

            with store.events_path.open("w", encoding="utf-8", newline="\n") as handle:
                for index in range(25_000):
                    handle.write(
                        json.dumps(
                            {
                                "recorded_at": f"2026-04-13T00:00:{index % 60:02d}+00:00",
                                "event": "runtime_event",
                                "index": index,
                            }
                        )
                    )
                    handle.write("\n")

                for subject_index in range(6):
                    handle.write(
                        json.dumps(
                            {
                                "recorded_at": f"2026-04-13T01:00:{subject_index:02d}+00:00",
                                "event": "parallel_approach_consolidated",
                                "consolidation_id": f"cons-task-{subject_index:02d}",
                                "supersedes_consolidation_id": "",
                                "subject_kind": "task",
                                "subject_id": f"task-{subject_index}",
                                "compared_approach_ids": ["approach-a", "approach-b"],
                                "winner_id": "approach-b",
                                "winner_label": "approach B",
                                "rejected_approach_ids": ["approach-a"],
                                "comparison_basis": ["verify burden"],
                                "decision": "picked approach B",
                                "comparison_event_ids": [f"evt-{subject_index:03d}"],
                            }
                        )
                    )
                    handle.write("\n")
                    for noise_index in range(3_500):
                        handle.write(
                            json.dumps(
                                {
                                    "recorded_at": f"2026-04-13T02:00:{noise_index % 60:02d}+00:00",
                                    "event": "runtime_event",
                                    "noise": f"{subject_index}-{noise_index}",
                                }
                            )
                        )
                        handle.write("\n")

            consolidations = store.read_recent_consolidations(limit=3)

            self.assertEqual([item["subject_id"] for item in consolidations], ["task-3", "task-4", "task-5"])
            self.assertTrue(all(item["winner_id"] == "approach-b" for item in consolidations))

    def test_save_uses_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            state = build_initial_state()
            original_replace = os.replace

            with mock.patch("core.state_store.os.replace", wraps=original_replace) as replace_mock:
                store.save_state(state)

            self.assertEqual(replace_mock.call_count, 1)
            src, dst = replace_mock.call_args[0]
            self.assertTrue(str(src).endswith(".json.tmp"))
            self.assertEqual(Path(dst), store.state_path)
            self.assertTrue(store.state_path.exists())
            self.assertFalse(store.state_path.with_suffix(".json.tmp").exists())

    def test_save_state_rejects_revision_regression_even_with_matching_expected_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            advanced = store.load_state()
            advanced["revision"] = 1
            store.save_state(advanced, expected_revision=0)

            downgraded = store.load_state()
            downgraded["revision"] = 0

            with self.assertRaises(StateStoreError) as exc_info:
                store.save_state(downgraded, expected_revision=1)

            self.assertIn("state revision must not go backwards", str(exc_info.exception))
            self.assertEqual(store.load_state()["revision"], 1)

    def test_save_state_recovers_from_late_runtime_lock_cleanup_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            state = build_initial_state()
            original_unlink = Path.unlink
            cleanup_failures = {"remaining": 3}

            def flaky_unlink(path: Path, *args, **kwargs):
                if Path(path) == store.lock_path and cleanup_failures["remaining"] > 0:
                    cleanup_failures["remaining"] -= 1
                    raise OSError("lock cleanup failed")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.unlink", autospec=True, side_effect=flaky_unlink):
                store.save_state(state)
                self.assertTrue(store.state_path.exists())
                self.assertTrue(store.lock_path.exists())

                store.save_state(state)

            self.assertEqual(store.load_state(), state)
            self.assertFalse(store.lock_path.exists())

    def test_save_state_cleans_partial_runtime_lock_when_owner_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            state = build_initial_state()
            original_open = os.open
            original_write = os.write
            runtime_lock_fd: int | None = None

            def tracking_open(path, flags, mode=0o777):
                nonlocal runtime_lock_fd
                fd = original_open(path, flags, mode)
                if Path(path) == store.lock_path:
                    runtime_lock_fd = fd
                return fd

            def fail_runtime_lock_owner_write(fd: int, payload: bytes) -> int:
                if fd == runtime_lock_fd:
                    original_write(fd, payload[:1])
                    raise OSError("synthetic runtime-lock owner write failure")
                return original_write(fd, payload)

            with mock.patch("core.state_runtime_lock_service.os.open", side_effect=tracking_open):
                with mock.patch(
                    "core.state_runtime_lock_service.os.write",
                    side_effect=fail_runtime_lock_owner_write,
                ):
                    with self.assertRaises(OSError) as exc_info:
                        store.save_state(state)

            self.assertIn("synthetic runtime-lock owner write failure", str(exc_info.exception))
            self.assertIsNotNone(runtime_lock_fd)
            with self.assertRaises(OSError):
                os.fstat(runtime_lock_fd)
            self.assertFalse(store.lock_path.exists())
            self.assertFalse(store._process_runtime_lock_is_held())

            store.save_state(state)

            self.assertEqual(store.load_state(), state)

    def test_register_sources_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["notes.txt"])

            self.assertEqual(updated["revision"], 1)
            self.assertEqual(
                updated["sources"],
                [
                    {
                        "path": "notes.txt",
                        "sha256": store.compute_sha256("notes.txt"),
                        "role": "primary",
                    }
                ],
            )

    def test_register_sources_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            with self.assertRaises(StateStoreError):
                store.register_sources([str(source_file.resolve())])

    def test_register_sources_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            with self.assertRaises(StateStoreError):
                store.register_sources(["../notes.txt"])

    def test_register_sources_rejects_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            outside_dir = Path(tempfile.mkdtemp())
            outside_file = outside_dir / "external.txt"
            outside_file.write_text("outside", encoding="utf-8")
            symlink_path = root / "external-link.txt"
            store = StateStore(root)
            store.save_state(build_initial_state())

            try:
                symlink_path.symlink_to(outside_file)
            except OSError as exc:
                self.skipTest(f"symlink creation not available: {exc}")

            try:
                with self.assertRaises(StateStoreError):
                    store.register_sources(["external-link.txt"])
            finally:
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                if outside_file.exists():
                    outside_file.unlink()
                outside_dir.rmdir()

    def test_register_sources_deduplicates_and_orders_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["b.txt", "a.txt", "b.txt"])

            self.assertEqual([item["path"] for item in updated["sources"]], ["a.txt", "b.txt"])

    def test_register_sources_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "a.txt").write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["a.txt"])

            self.assertEqual(updated["revision"], 1)

    def test_register_sources_has_no_partial_write_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            good_file = root / "a.txt"
            good_file.write_text("a", encoding="utf-8")
            store = StateStore(root)
            initial = build_initial_state()
            store.save_state(initial)

            with self.assertRaises(StateStoreError):
                store.register_sources(["a.txt", "../bad.txt"])

            loaded = store.load_state()
            self.assertEqual(loaded, initial)

    def test_register_sources_does_not_change_state_when_session_close_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["a.txt"])
            before = store.load_state()

            with mock.patch.object(
                store,
                "close_session",
                side_effect=StateStoreError("failed to remove session file: session.local.json"),
            ):
                with self.assertRaises(StateStoreError):
                    store.register_sources(["a.txt"])

            after = store.load_state()
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["sources"], before["sources"])
            self.assertEqual(after["last_validation"], before["last_validation"])

    def test_register_sources_restores_session_when_state_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["a.txt"])
            session = store.open_session("alice")
            before = store.load_state()
            before_session = store.session_path.read_text(encoding="utf-8")
            before_claim = self._read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(before_claim)

            with mock.patch.object(store, "save_state", side_effect=StateStoreError("failed to write file: state.json")):
                with self.assertRaises(StateStoreError) as exc_info:
                    store.register_sources(["a.txt"], expected_session_token=session["session_token"])

            after = store.load_state()
            self.assertIn("failed to write file", str(exc_info.exception))
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["sources"], before["sources"])
            self.assertEqual(after["last_validation"], before["last_validation"])
            self.assertTrue(store.session_path.exists())
            self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
            self.assertEqual(self._read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
            self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
            self.assertEqual(after["agent_runtime"]["audit"]["active_session_claim_id"], before["agent_runtime"]["audit"]["active_session_claim_id"])

    def test_update_checkpoint_updates_fields_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)

            updated = store.update_checkpoint(
                {
                    "goal": "Ship the fix",
                    "summary": "The regression is isolated to the auth refresh path.",
                    "next_step": "Patch token refresh handling.",
                    "constraints": ["Keep API responses stable"],
                }
            )

            checkpoint = updated["checkpoint"]
            self.assertEqual(checkpoint["goal"], "Ship the fix")
            self.assertEqual(checkpoint["summary"], "The regression is isolated to the auth refresh path.")
            self.assertEqual(checkpoint["next_step"], "Patch token refresh handling.")
            self.assertEqual(checkpoint["constraints"], ["Keep API responses stable"])
            self.assertTrue(checkpoint["updated_at"])

    def test_update_checkpoint_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)

            updated = store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )

            self.assertEqual(updated["revision"], 2)

    def test_update_checkpoint_rejects_field_above_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            initial = store.load_state()

            with self.assertRaises(StateValidationError):
                store.update_checkpoint(
                    {
                        "goal": "x" * 201,
                        "summary": "Summary",
                        "next_step": "Next",
                        "constraints": [],
                    }
                )

            loaded = store.load_state()
            self.assertEqual(loaded["revision"], initial["revision"])
            self.assertEqual(loaded["checkpoint"], initial["checkpoint"])

    def test_update_checkpoint_blocks_when_registered_context_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            tracked.write_text("changed", encoding="utf-8")

            with self.assertRaises(StateValidationError) as exc_info:
                store.update_checkpoint(
                    {
                        "goal": "Blocked",
                        "summary": "Should not save.",
                        "next_step": "Stop.",
                        "constraints": [],
                    }
                )

            self.assertEqual(exc_info.exception.errors[0]["code"], "source_hash_mismatch")
            after = store.load_state()
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["checkpoint"], before["checkpoint"])

    def test_update_checkpoint_rejects_stale_validated_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            validation = store.validate_state()
            store.update_checkpoint(
                {
                    "goal": "First",
                    "summary": "Move revision.",
                    "next_step": "Continue.",
                    "constraints": [],
                },
                validated_revision=validation["revision"],
            )

            with self.assertRaises(StateStoreError):
                store.update_checkpoint(
                    {
                        "goal": "Second",
                        "summary": "Should fail.",
                        "next_step": "Stop.",
                        "constraints": [],
                    },
                    validated_revision=validation["revision"],
                )

    def test_open_session_writes_local_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)

            session = store.open_session("alice")
            persisted = json.loads(store.session_path.read_text(encoding="utf-8"))
            state = store.load_state()

            self.assertTrue(session["session_id"])
            self.assertEqual(session["actor"], "alice")
            self.assertEqual(session["based_on_revision"], 1)
            self.assertTrue(session["session_token"])
            self.assertNotIn("session_token", persisted)
            self.assertTrue(persisted["owner_claim_id"].startswith("claim-"))
            claim = self._read_session_claim(store, persisted["owner_claim_id"])
            live_proof, live_proof_errors = store._read_session_live_proof_file(claim["live_proof_id"])
            self.assertEqual(live_proof_errors, [])
            self.assertIsNotNone(live_proof)
            self.assertEqual(claim["session_id"], session["session_id"])
            self.assertEqual(claim["session_token_sha256"], store._hash_session_token(session["session_token"]))
            self.assertTrue(claim["live_proof_id"].startswith("proof-"))
            self.assertEqual(
                claim["session_live_proof_sha256"],
                store._hash_session_live_proof(live_proof["session_live_proof"]),
            )
            self.assertNotIn("session_token", claim)
            self.assertNotIn("session_live_proof", claim)
            self.assertEqual(claim["owner_binding_sha256"], store._hash_session_owner_binding(store._current_session_owner_binding()))
            self.assertEqual(live_proof["session_id"], session["session_id"])
            self.assertTrue(store.session_path.exists())
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_id"], session["session_id"])
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_claim_id"], session["owner_claim_id"])

    def test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                store, _ = self._seed_valid_runtime(root)
                before = deepcopy(store.load_state())
                before_claim_paths = sorted(path.name for path in store.claims_dir.glob("*.json"))
                before_live_proof_paths = sorted(path.name for path in store.live_proofs_dir.glob("*.json"))
                original_write = store._write_json_atomic

                def fail_final_session_write(path: Path, data: dict) -> None:
                    if path == store.session_path:
                        raise OSError("session file write failed")
                    original_write(path, data)

                with mock.patch.object(store, "_write_json_atomic", side_effect=fail_final_session_write):
                    with self.assertRaises(OSError) as exc_info:
                        store.open_session("alice")

                self.assertIn("session file write failed", str(exc_info.exception))
                self.assertFalse(store.session_path.exists())
                self.assertEqual(sorted(path.name for path in store.claims_dir.glob("*.json")), before_claim_paths)
                self.assertEqual(sorted(path.name for path in store.live_proofs_dir.glob("*.json")), before_live_proof_paths)

                after = store.load_state()
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.validate_state()["ok"])

    def test_open_session_discards_registry_residue_when_state_restore_after_session_file_failure_also_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                store, _ = self._seed_valid_runtime(root)
                before = deepcopy(store.load_state())
                before_claim_paths = sorted(path.name for path in store.claims_dir.glob("*.json"))
                before_live_proof_paths = sorted(path.name for path in store.live_proofs_dir.glob("*.json"))
                original_write = store._write_json_atomic
                original_save_state = StateStore.save_state
                save_state_calls = {"count": 0}

                def fail_final_session_write(path: Path, data: dict) -> None:
                    if path == store.session_path:
                        raise OSError("session file write failed")
                    original_write(path, data)

                def fail_first_restore_only(
                    runtime: StateStore,
                    state: dict,
                    expected_revision: int | None = None,
                ) -> None:
                    save_state_calls["count"] += 1
                    if save_state_calls["count"] == 2:
                        raise OSError("state restore failed")
                    original_save_state(runtime, state, expected_revision=expected_revision)

                with mock.patch.object(store, "_write_json_atomic", side_effect=fail_final_session_write):
                    with mock.patch.object(StateStore, "save_state", autospec=True, side_effect=fail_first_restore_only):
                        with self.assertRaises(OSError) as exc_info:
                            store.open_session("alice")

                self.assertEqual(save_state_calls["count"], 2)
                self.assertIn("state restore failed", str(exc_info.exception))
                self.assertFalse(store.session_path.exists())
                self.assertEqual(sorted(path.name for path in store.claims_dir.glob("*.json")), before_claim_paths)
                self.assertEqual(sorted(path.name for path in store.live_proofs_dir.glob("*.json")), before_live_proof_paths)

                after = store.load_state()
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.validate_state()["ok"])

    def test_update_agent_plan_requires_caller_supplied_session_capability(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            validation = store.validate_state()
            before_state = deepcopy(store.load_state())
            before_session_bytes = store.session_path.read_bytes()
            before_claim_bytes = self._read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(before_claim_bytes)

            with self.assertRaises(StateValidationError) as exc_info:
                store.update_agent_plan(
                    {
                        "goal": "Observe continuity",
                        "summary": "Session ownership must stay external to the persisted claim.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Plan task",
                                "status": "ready",
                                "details": "Plan task",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["explicit token required"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [],
                        "required_command_ids": [],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                )

            after_state = store.load_state()
            self.assertEqual(exc_info.exception.errors[0]["code"], "session_token_required")
            self.assertEqual(after_state["revision"], before_state["revision"])
            self.assertEqual(after_state["agent_runtime"], before_state["agent_runtime"])
            self.assertEqual(store.session_path.read_bytes(), before_session_bytes)
            self.assertEqual(self._read_session_claim_bytes(store, session["owner_claim_id"]), before_claim_bytes)

    def test_update_agent_plan_keeps_owned_session_valid_after_revision_bump(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            validation = store.validate_state()

            updated = store.update_agent_plan(
                {
                    "goal": "Observe continuity",
                    "summary": "Keep the same owner session alive after plan changes.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Plan task",
                            "status": "ready",
                            "details": "Plan task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["session stays valid"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
                expected_session_token=session["session_token"],
            )

            after_validation = store.validate_state()
            refreshed_session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(updated["revision"], validation["revision"] + 1)
            self.assertTrue(after_validation["ok"], after_validation["errors"])
            self.assertEqual(refreshed_session["based_on_revision"], updated["revision"])

    def test_validate_state_recovers_pending_session_refresh_after_crash_before_state_save(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            validation = store.validate_state()
            before_revision = validation["revision"]
            before_state_bytes = store.state_path.read_bytes()
            before_session_bytes = store.session_path.read_bytes()
            before_claim_bytes = self._read_session_claim_bytes(store, session["owner_claim_id"])
            live_proof_id = self._read_session_claim(store, session["owner_claim_id"])["live_proof_id"]
            before_live_proof_bytes = store._read_optional_session_live_proof_bytes(live_proof_id)

            with mock.patch.object(store, "save_state", side_effect=SystemExit("crash after session refresh")):
                with self.assertRaises(SystemExit):
                    store.update_agent_plan(
                        {
                            "goal": "Observe continuity",
                            "summary": "Crash between session refresh and state commit.",
                            "tasks": [
                                {
                                    "id": "task-001",
                                    "title": "Plan task",
                                    "status": "ready",
                                    "details": "Plan task",
                                    "depends_on": [],
                                    "working_set": ["tracked.txt"],
                                    "acceptance_criteria": ["session refresh is recovered"],
                                    "action_ids": [],
                                }
                            ],
                            "command_registry": [],
                            "required_command_ids": [],
                            "autonomy_level": "A2",
                            "protected_paths": [".cerebro/**", ".git/**"],
                            "blocked_command_prefixes": ["rm"],
                            "approval_required_kinds": ["fs.write_patch"],
                        },
                        validated_revision=before_revision,
                        expected_session_token=session["session_token"],
                    )

            split_session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(store.load_state()["revision"], before_revision)
            self.assertEqual(split_session["based_on_revision"], before_revision + 1)
            self.assertTrue(store.session_refresh_pending_path.exists())

            restarted = StateStore(root)
            after_validation = restarted.validate_state()

            self.assertTrue(after_validation["ok"], after_validation["errors"])
            self.assertFalse(restarted.session_refresh_pending_path.exists())
            self.assertEqual(restarted.state_path.read_bytes(), before_state_bytes)
            self.assertEqual(restarted.session_path.read_bytes(), before_session_bytes)
            self.assertEqual(self._read_session_claim_bytes(restarted, session["owner_claim_id"]), before_claim_bytes)
            self.assertEqual(
                restarted._read_optional_session_live_proof_bytes(live_proof_id),
                before_live_proof_bytes,
            )

    def test_validate_state_finalizes_stale_pending_session_refresh_after_successful_commit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            validation = store.validate_state()

            with mock.patch.object(store, "_clear_pending_session_refresh", side_effect=lambda: None):
                updated = store.update_agent_plan(
                    {
                        "goal": "Observe continuity",
                        "summary": "Pending refresh should finalize on the next validation.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Plan task",
                                "status": "ready",
                                "details": "Plan task",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["stale pending refresh is finalized"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [],
                        "required_command_ids": [],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                    expected_session_token=session["session_token"],
                )

            self.assertTrue(store.session_refresh_pending_path.exists())
            persisted_session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(store.load_state()["revision"], updated["revision"])
            self.assertEqual(persisted_session["based_on_revision"], updated["revision"])

            restarted = StateStore(root)
            after_validation = restarted.validate_state()

            self.assertTrue(after_validation["ok"], after_validation["errors"])
            self.assertFalse(restarted.session_refresh_pending_path.exists())
            refreshed_session = json.loads(restarted.session_path.read_text(encoding="utf-8"))
            self.assertEqual(refreshed_session["based_on_revision"], updated["revision"])

    def test_update_agent_plan_rejects_replayed_session_from_different_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
            validation = store.validate_state()

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-b"):
                with self.assertRaises(StateValidationError) as exc_info:
                    store.update_agent_plan(
                        {
                            "goal": "Observe continuity",
                            "summary": "Cross-terminal replay must fail closed.",
                            "tasks": [
                                {
                                    "id": "task-001",
                                    "title": "Plan task",
                                    "status": "ready",
                                    "details": "Plan task",
                                    "depends_on": [],
                                    "working_set": ["tracked.txt"],
                                    "acceptance_criteria": ["binding mismatch blocks"],
                                    "action_ids": [],
                                }
                            ],
                            "command_registry": [],
                            "required_command_ids": [],
                            "autonomy_level": "A2",
                            "protected_paths": [".cerebro/**", ".git/**"],
                            "blocked_command_prefixes": ["rm"],
                            "approval_required_kinds": ["fs.write_patch"],
                        },
                        validated_revision=validation["revision"],
                        expected_session_token=session["session_token"],
                    )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_owner_binding_mismatch")
            self.assertTrue(store.session_path.exists())

    def test_update_agent_plan_rejects_forged_session_without_external_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            store._remove_session_claim(session["owner_claim_id"])
            validation = store.validate_state()

            with self.assertRaises(StateValidationError) as exc_info:
                store.update_agent_plan(
                    {
                        "goal": "Observe continuity",
                        "summary": "Forged repo-local session must not gain authority.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Plan task",
                                "status": "ready",
                                "details": "Plan task",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["missing claim blocks"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [],
                        "required_command_ids": [],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                    expected_session_token=session["session_token"],
                )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_claim_missing")

    def test_file_backed_session_missing_errors_redact_external_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            with tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
                with mock.patch.dict(
                    os.environ,
                    {
                        SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                        SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                    },
                    clear=False,
                ):
                    store, _ = self._seed_valid_runtime(root)
                    session = store.open_session("alice")
                    claim = self._read_session_claim(store, session["owner_claim_id"])
                    self.assertIsNotNone(claim)
                    claim_id = session["owner_claim_id"]
                    proof_id = claim["live_proof_id"]
                    store._remove_session_claim(claim_id)
                    store._remove_session_live_proof(proof_id)

                    claim_data, claim_errors = store._read_session_claim_file(claim_id)
                    proof_data, proof_errors = store._read_session_live_proof_file(proof_id)

            self.assertIsNone(claim_data)
            self.assertEqual(claim_errors[0]["code"], "session_claim_missing")
            self.assertIn(f"session_claims/{claim_id}.json", claim_errors[0]["message"])
            self.assertNotIn(str(Path(claims_override).resolve()), claim_errors[0]["message"])

            self.assertIsNone(proof_data)
            self.assertEqual(proof_errors[0]["code"], "session_live_proof_missing")
            self.assertIn(f"session_live_proofs/{proof_id}.json", proof_errors[0]["message"])
            self.assertNotIn(str(Path(proofs_override).resolve()), proof_errors[0]["message"])

    def test_open_session_blocks_when_registered_context_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "notes.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["notes.txt"])
            tracked.write_text("changed", encoding="utf-8")

            with self.assertRaises(StateValidationError) as exc_info:
                store.open_session("alice")

            self.assertEqual(exc_info.exception.errors[0]["code"], "source_hash_mismatch")
            self.assertFalse(store.session_path.exists())

    def test_open_session_rejects_stale_validated_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            validation = store.validate_state()
            store.update_checkpoint(
                {
                    "goal": "First",
                    "summary": "Move revision.",
                    "next_step": "Continue.",
                    "constraints": [],
                },
                validated_revision=validation["revision"],
            )

            with self.assertRaises(StateStoreError):
                store.open_session("alice", validated_revision=validation["revision"])

    def test_open_session_rejects_existing_active_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.open_session("alice")

            with self.assertRaises(StateValidationError) as exc_info:
                store.open_session("bob")

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_open_conflict")
            session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "alice")

    def test_open_session_rejects_second_actor_after_split_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._seed_valid_runtime(root)
            first = StateStore(root)
            second = StateStore(root)
            first_validation = first.validate_state()
            second_validation = second.validate_state()

            first.open_session("alice", validated_revision=first_validation["revision"])

            with self.assertRaises(StateValidationError) as exc_info:
                second.open_session("bob", validated_revision=second_validation["revision"])

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_open_conflict")
            session = json.loads(first.session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "alice")

    def test_update_checkpoint_rejects_replaced_session_when_expected_session_id_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Before",
                    "summary": "Stable.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            alice_session = store.open_session("alice")
            validation = store.validate_state()
            alice_session_id = validation["session"]["session_id"]
            store.discard_session(expected_session_token=alice_session["session_token"])
            bob_session = store.open_session("bob")
            before = store.load_state()

            with self.assertRaises(StateValidationError) as exc_info:
                store.update_checkpoint(
                    {
                        "goal": "After",
                        "summary": "Should fail.",
                        "next_step": "Stop.",
                        "constraints": [],
                    },
                    validated_revision=validation["revision"],
                    close_session_on_success=True,
                    expected_session_id=alice_session_id,
                    expected_session_token=bob_session["session_token"],
                )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_changed_during_operation")
            after = store.load_state()
            session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["checkpoint"], before["checkpoint"])
            self.assertEqual(session["actor"], "bob")

    def test_register_sources_closes_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["notes.txt"])
            session = store.open_session("alice")

            store.register_sources(["notes.txt"], expected_session_token=session["session_token"])

            self.assertFalse(store.session_path.exists())
            self.assertIsNone(self._read_session_claim_bytes(store, session["owner_claim_id"]))
            state = store.load_state()
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_id"], "")
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_claim_id"], "")

    def test_register_sources_rechecks_hash_before_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            with mock.patch.object(store, "compute_sha256", side_effect=["a" * 64, "b" * 64]):
                with self.assertRaises(StateStoreError) as exc_info:
                    store.register_sources(["tracked.txt"])

            self.assertIn("source changed during registration", str(exc_info.exception))
            self.assertEqual(store.load_state()["sources"], [])

    def test_validate_does_not_overwrite_newer_checkpoint_when_parallel_update_waits(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "G1",
                    "summary": "Initial checkpoint.",
                    "next_step": "Validate.",
                    "constraints": [],
                }
            )
            validator = StateStore(root)
            updater = StateStore(root)
            pause_reached = threading.Event()
            resume_validate = threading.Event()
            original_write = validator._write_json_atomic

            def delayed_write(path: Path, data: dict) -> None:
                if path == validator.state_path and data["last_validation"]["validated_at"]:
                    pause_reached.set()
                    self.assertTrue(resume_validate.wait(timeout=2))
                original_write(path, data)

            update_errors: list[Exception] = []

            def run_validate() -> None:
                validator.validate_state()

            def run_update() -> None:
                try:
                    updater.update_checkpoint(
                        {
                            "goal": "G2",
                            "summary": "New checkpoint.",
                            "next_step": "Keep the latest value.",
                            "constraints": [],
                        }
                    )
                except Exception as exc:  # pragma: no cover - test should keep the list empty
                    update_errors.append(exc)

            with mock.patch.object(validator, "_write_json_atomic", side_effect=delayed_write):
                validate_thread = threading.Thread(target=run_validate)
                update_thread = threading.Thread(target=run_update)
                validate_thread.start()
                self.assertTrue(pause_reached.wait(timeout=2))
                update_thread.start()
                resume_validate.set()
                validate_thread.join(timeout=2)
                update_thread.join(timeout=2)

            self.assertEqual(update_errors, [])
            self.assertFalse(validate_thread.is_alive())
            self.assertFalse(update_thread.is_alive())
            final_state = StateStore(root).load_state()
            self.assertEqual(final_state["revision"], 3)
            self.assertEqual(final_state["checkpoint"]["goal"], "G2")

    def test_runtime_lock_recovers_stale_lock_when_pid_probe_is_invalid_parameter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.lock_path.write_text("999999", encoding="utf-8")
            probe_error = OSError(22, "invalid parameter")
            probe_error.winerror = 87

            with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 0):
                with mock.patch("core.state_store.os.kill", side_effect=probe_error):
                    result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertFalse(store.lock_path.exists())

    def test_runtime_lock_recovers_stale_empty_or_garbled_lock_after_grace_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)

            for payload in ("", "garbled-owner"):
                with self.subTest(payload=payload if payload else "<empty>"):
                    store.lock_path.write_text(payload, encoding="ascii")
                    stale_at = time.time() - 2
                    os.utime(store.lock_path, (stale_at, stale_at))

                    with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 1):
                        result = store.validate_state()

                    self.assertTrue(result["ok"])
                    self.assertFalse(store.lock_path.exists())

    def test_runtime_lock_fresh_garbled_lock_still_times_out_without_staleness_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.lock_path.write_text("garbled-owner", encoding="ascii")

            with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 0):
                with mock.patch("core.state_store.RUNTIME_LOCK_POLL_SECONDS", 1):
                    with self.assertRaises(StateStoreError) as exc_info:
                        store.validate_state()

            message = str(exc_info.exception)
            self.assertIn("runtime.lock", message)
            self.assertIn("stale lock", message)
            self.assertEqual(store.lock_path.read_text(encoding="ascii"), "garbled-owner")

    def test_runtime_lock_timeout_reports_stale_lock_guidance_when_owner_still_looks_alive(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.lock_path.write_text("999999", encoding="utf-8")

            with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 0):
                with mock.patch("core.state_store.os.kill", return_value=None):
                    with self.assertRaises(StateStoreError) as exc_info:
                        store.validate_state()

            message = str(exc_info.exception)
            self.assertIn("runtime.lock", message)
            self.assertIn("stale lock", message)
            self.assertEqual(store.lock_path.read_text(encoding="utf-8"), "999999")

    def test_runtime_lock_serializes_two_store_instances_after_extraction(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            peer = StateStore(root)
            holder_entered = threading.Event()
            release_holder = threading.Event()
            contender_acquired = threading.Event()
            holder_errors: list[Exception] = []
            contender_errors: list[Exception] = []

            def holder() -> None:
                try:
                    with store.runtime_lock():
                        holder_entered.set()
                        release_holder.wait(timeout=2)
                except Exception as exc:  # pragma: no cover - failure collected below
                    holder_errors.append(exc)

            def contender() -> None:
                holder_entered.wait(timeout=2)
                try:
                    with peer.runtime_lock():
                        contender_acquired.set()
                except Exception as exc:  # pragma: no cover - failure collected below
                    contender_errors.append(exc)

            holder_thread = threading.Thread(target=holder)
            contender_thread = threading.Thread(target=contender)
            holder_thread.start()
            self.assertTrue(holder_entered.wait(timeout=2))
            contender_thread.start()
            self.assertFalse(contender_acquired.wait(timeout=0.1))
            release_holder.set()
            holder_thread.join(timeout=2)
            contender_thread.join(timeout=2)

            self.assertEqual(holder_errors, [])
            self.assertEqual(contender_errors, [])
            self.assertTrue(contender_acquired.is_set())
            self.assertFalse(store.lock_path.exists())

    def test_close_session_does_not_fail_without_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())

            store.close_session()

            self.assertFalse(store.session_path.exists())

    def test_close_session_fails_closed_and_records_trace_when_session_file_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                store, _ = self._seed_valid_runtime(root)
                session = store.open_session("alice")
                claim = self._read_session_claim(store, session["owner_claim_id"])
                before = store.load_state()
                before_claim = self._read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = store._read_optional_session_live_proof_bytes(claim["live_proof_id"])
                store.session_path.write_text("{invalid json", encoding="utf-8")

                with self.assertRaises(StateStoreError) as exc_info:
                    store.close_session()

                after = store.load_state()
                self.assertIn("failed to read session file before closing session", str(exc_info.exception))
                self.assertIn("session_invalid_json", str(exc_info.exception))
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), "{invalid json")
                self.assertEqual(self._read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(store._read_optional_session_live_proof_bytes(claim["live_proof_id"]), before_live_proof)
                latest_event = store.read_recent_events(limit=1)[0]
                self.assertEqual(latest_event["event"], "session_close_failed")
                self.assertEqual(latest_event["reason_code"], "session_invalid_json")

    def test_discard_session_clears_stale_session_records_trace_without_bumping_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Revision moved.",
                    "next_step": "Re-open continuity.",
                    "constraints": [],
                },
                expected_session_token=session["session_token"],
            )
            stale_session = json.loads(store.session_path.read_text(encoding="utf-8"))
            stale_session["based_on_revision"] -= 1
            store.session_path.write_text(json.dumps(stale_session), encoding="utf-8")
            before_revision = store.load_state()["revision"]

            result = store.discard_session(expected_session_token=session["session_token"])

            after_state = store.load_state()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "discarded")
            self.assertTrue(result["recovered_stale_session"])
            self.assertEqual(result["revision"], before_revision)
            self.assertEqual(after_state["revision"], before_revision)
            self.assertEqual(after_state["last_validation"]["result"], "ok")
            self.assertFalse(store.session_path.exists())
            self.assertIsNone(self._read_session_claim_bytes(store, session["owner_claim_id"]))
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_id"], "")
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_claim_id"], "")
            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["event"], "session_discarded")
            self.assertEqual(latest_event["mode"], "stale_session_recovery")

    def test_discard_session_clears_registry_only_session_residue_without_bumping_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            claim = self._read_session_claim(store, session["owner_claim_id"])
            before_revision = store.load_state()["revision"]
            store.session_path.unlink()

            validation = store.validate_state()
            self.assertFalse(validation["ok"])
            self.assertEqual(validation["errors"][0]["code"], "session_registry_mismatch")

            result = store.discard_session()

            after_state = store.load_state()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "discarded")
            self.assertTrue(result["recovered_stale_session"])
            self.assertEqual(result["revision"], before_revision)
            self.assertEqual(after_state["revision"], before_revision)
            self.assertEqual(after_state["last_validation"]["result"], "ok")
            self.assertFalse(store.session_path.exists())
            self.assertIsNone(self._read_session_claim_bytes(store, session["owner_claim_id"]))
            self.assertIsNone(store._read_optional_session_live_proof_bytes(claim["live_proof_id"]))
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_id"], "")
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_claim_id"], "")
            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["event"], "session_discarded")
            self.assertEqual(latest_event["mode"], "stale_session_recovery")

    def test_discard_session_clears_orphan_session_local_residue_after_close_session_crash_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            claim = self._read_session_claim(store, session["owner_claim_id"])
            state = store.load_state()
            before_revision = state["revision"]
            store._clear_active_session_registry(state)
            store.save_state(state, expected_revision=state["revision"])
            store._remove_session_live_proof(claim["live_proof_id"])
            store._remove_session_claim(session["owner_claim_id"])

            validation = store.validate_state()
            self.assertFalse(validation["ok"])
            self.assertEqual(validation["errors"][0]["code"], "session_not_registered")

            result = store.discard_session()

            after_state = store.load_state()
            self.assertTrue(result["ok"])
            self.assertEqual(result["status"], "discarded")
            self.assertTrue(result["recovered_stale_session"])
            self.assertEqual(result["revision"], before_revision)
            self.assertEqual(after_state["revision"], before_revision)
            self.assertFalse(store.session_path.exists())
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_id"], "")
            self.assertEqual(after_state["agent_runtime"]["audit"]["active_session_claim_id"], "")
            self.assertTrue(store.validate_state()["ok"])
            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["event"], "session_discarded")
            self.assertEqual(latest_event["mode"], "stale_session_recovery")

    def test_discard_session_blocks_session_not_registered_without_token_when_claim_still_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            session = store.open_session("alice")
            state = store.load_state()
            before_revision = state["revision"]
            store._clear_active_session_registry(state)
            store.save_state(state, expected_revision=state["revision"])

            validation = store.validate_state()
            self.assertFalse(validation["ok"])
            self.assertEqual(validation["errors"][0]["code"], "session_not_registered")

            result = store.discard_session()

            after_state = store.load_state()
            self.assertFalse(result["ok"])
            self.assertEqual(result["status"], "blocked")
            self.assertEqual(result["reason"], "session_token")
            self.assertEqual(result["errors"][0]["code"], "session_token_required")
            self.assertEqual(after_state["revision"], before_revision)
            self.assertTrue(store.session_path.exists())
            self.assertIsNotNone(self._read_session_claim_bytes(store, session["owner_claim_id"]))

    def test_discard_session_invalidates_restored_session_backup_in_same_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")

            session_bytes = store.session_path.read_bytes()
            claim_bytes = self._read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(claim_bytes)

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                result = store.discard_session(expected_session_token=session["session_token"])

            self.assertTrue(result["ok"])
            store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
            store._write_bytes_atomic(store.session_path, session_bytes)

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                validation = store.validate_state()

            self.assertFalse(validation["ok"])
            self.assertEqual(validation["errors"][0]["code"], "session_not_registered")
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                with self.assertRaises(StateValidationError) as exc_info:
                    store.update_agent_plan(
                        {
                            "goal": "Observe continuity",
                            "summary": "Restored discarded session must not regain authority.",
                            "tasks": [
                                {
                                    "id": "task-001",
                                    "title": "Plan task",
                                    "status": "ready",
                                    "details": "Plan task",
                                    "depends_on": [],
                                    "working_set": ["tracked.txt"],
                                    "acceptance_criteria": ["discarded session stays dead"],
                                    "action_ids": [],
                                }
                            ],
                            "command_registry": [],
                            "required_command_ids": [],
                            "autonomy_level": "A2",
                            "protected_paths": [".cerebro/**", ".git/**"],
                            "blocked_command_prefixes": ["rm"],
                            "approval_required_kinds": ["fs.write_patch"],
                        },
                        validated_revision=store.load_state()["revision"],
                        expected_session_token=session["session_token"],
                    )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_not_registered")

    def test_update_checkpoint_rejects_full_snapshot_restore_without_live_proof(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = store.state_path.read_bytes()
                session_bytes = store.session_path.read_bytes()
                claim_bytes = self._read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(store.state_path, state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                store._write_bytes_atomic(store.session_path, session_bytes)

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                validation = store.validate_state()
                self.assertFalse(validation["ok"])
                self.assertEqual(validation["errors"][0]["code"], "session_live_proof_missing")
                with self.assertRaises(StateValidationError) as exc_info:
                    store.update_checkpoint(
                        {
                            "goal": "Ship",
                            "summary": "Restored snapshot should fail closed.",
                            "next_step": "Stop.",
                            "constraints": [],
                        },
                        validated_revision=store.load_state()["revision"],
                        expected_session_token=session["session_token"],
                    )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_live_proof_missing")
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_update_checkpoint_rejects_file_snapshot_restore_of_live_proof_when_backend_is_wincred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            if store._session_live_proof_backend() != "wincred":
                self.skipTest("requires Windows credential-backed live-proof storage")
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                claim_data = self._read_session_claim(store, session["owner_claim_id"])
                state_bytes = store.state_path.read_bytes()
                session_bytes = store.session_path.read_bytes()
                claim_bytes = self._read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                proof_bytes = store._read_optional_session_live_proof_bytes(claim_data["live_proof_id"])
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(store.state_path, state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                self.assertIsNotNone(proof_bytes)
                store._write_bytes_atomic(
                    store._session_live_proof_path(claim_data["live_proof_id"]),
                    proof_bytes,
                )
                store._write_bytes_atomic(store.session_path, session_bytes)

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                validation = store.validate_state()
                self.assertFalse(validation["ok"])
                self.assertEqual(validation["errors"][0]["code"], "session_live_proof_missing")
                with self.assertRaises(StateValidationError) as exc_info:
                    store.update_checkpoint(
                    {
                        "goal": "Ship",
                        "summary": "File snapshot restore must not revive a wincred-backed live proof.",
                        "next_step": "Continue.",
                        "constraints": [],
                    },
                    validated_revision=store.load_state()["revision"],
                    expected_session_token=session["session_token"],
                )

            self.assertEqual(exc_info.exception.errors[0]["code"], "session_live_proof_missing")
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_live_proof_snapshot_restores_to_captured_backend_even_if_env_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as override_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            if store._session_live_proof_backend() != "wincred":
                self.skipTest("requires Windows credential-backed live-proof storage")
            session = store.open_session("alice")
            claim_data = self._read_session_claim(store, session["owner_claim_id"])
            proof_id = claim_data["live_proof_id"]
            snapshot = store._capture_session_live_proof_snapshot(
                proof_id,
                label="external session live proof",
            )

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["backend"], "wincred")
            store._remove_session_live_proof(proof_id, backend="wincred")
            self.assertIsNone(store._read_optional_session_live_proof_bytes(proof_id, backend="wincred"))

            with mock.patch.dict(os.environ, {SESSION_LIVE_PROOFS_DIR_ENV_VAR: override_dir}, clear=False):
                store._restore_session_live_proof_snapshot(snapshot)
                self.assertIsNone(store._read_optional_session_live_proof_bytes(proof_id, backend="file"))

            self.assertEqual(
                store._read_optional_session_live_proof_bytes(proof_id, backend="wincred"),
                snapshot["bytes"],
            )

    def test_session_claim_snapshot_restores_to_captured_backend_even_if_env_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as override_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            if store._session_claim_backend() != "wincred":
                self.skipTest("requires Windows credential-backed session claim storage")
            session = store.open_session("alice")
            claim_id = session["owner_claim_id"]
            snapshot = store._capture_session_claim_snapshot(
                claim_id,
                label="external session claim",
            )

            self.assertIsNotNone(snapshot)
            self.assertEqual(snapshot["backend"], "wincred")
            store._remove_session_claim(claim_id, backend="wincred")
            self.assertIsNone(self._read_session_claim_bytes(store, claim_id, backend="wincred"))

            with mock.patch.dict(os.environ, {SESSION_CLAIMS_DIR_ENV_VAR: override_dir}, clear=False):
                store._restore_session_claim_snapshot(snapshot)
                self.assertIsNone(self._read_session_claim_bytes(store, claim_id, backend="file"))

            self.assertEqual(
                self._read_session_claim_bytes(store, claim_id, backend="wincred"),
                snapshot["bytes"],
            )

    def test_discard_session_rejects_replayed_session_from_different_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")

            with mock.patch.object(store, "_current_session_owner_binding", return_value="terminal-b"):
                result = store.discard_session(expected_session_token=session["session_token"])

            self.assertFalse(result["ok"])
            self.assertEqual(result["reason"], "session_token")
            self.assertEqual(result["errors"][0]["code"], "session_owner_binding_mismatch")
            self.assertTrue(store.session_path.exists())

    def test_discard_session_holds_runtime_lock_until_post_discard_validation_finishes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = self._seed_valid_runtime(root)
            peer = StateStore(root)
            test_case = self
            session = store.open_session("alice")
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Revision moved.",
                    "next_step": "Re-open continuity.",
                    "constraints": [],
                },
                expected_session_token=session["session_token"],
            )
            stale_session = json.loads(store.session_path.read_text(encoding="utf-8"))
            stale_session["based_on_revision"] -= 1
            store.session_path.write_text(json.dumps(stale_session), encoding="utf-8")
            entered_close = threading.Event()
            allow_close = threading.Event()
            opener_finished = threading.Event()
            discard_result: dict[str, dict] = {}
            open_result: dict[str, dict] = {}
            original_close_session = StateStore.close_session

            def delayed_close(self) -> bool:
                if self is store:
                    entered_close.set()
                    test_case.assertTrue(allow_close.wait(timeout=5))
                return original_close_session(self)

            def run_discard() -> None:
                discard_result["result"] = store.discard_session(expected_session_token=session["session_token"])

            def run_open() -> None:
                open_result["session"] = peer.open_session("bob")
                opener_finished.set()

            with mock.patch.object(StateStore, "close_session", new=delayed_close):
                discard_thread = threading.Thread(target=run_discard)
                discard_thread.start()
                self.assertTrue(entered_close.wait(timeout=5))
                open_thread = threading.Thread(target=run_open)
                open_thread.start()
                self.assertFalse(opener_finished.wait(timeout=0.2))
                allow_close.set()
                discard_thread.join(timeout=5)
                open_thread.join(timeout=5)

            self.assertFalse(discard_thread.is_alive())
            self.assertFalse(open_thread.is_alive())
            self.assertEqual(discard_result["result"]["status"], "discarded")
            self.assertEqual(open_result["session"]["actor"], "bob")
            session = json.loads(store.session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "bob")

    def test_close_session_wraps_unremovable_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())
            store.session_path.mkdir()

            with self.assertRaises(StateStoreError) as exc_info:
                store.close_session()

            self.assertIn("failed to remove session file", str(exc_info.exception))


if __name__ == "__main__":
    unittest.main()
