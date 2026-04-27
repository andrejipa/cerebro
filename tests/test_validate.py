from __future__ import annotations

import hashlib
import io
import json
import os
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import mock

from cli.commands.analyze import run_analyze
from cli.commands.checkpoint import run_checkpoint
from cli.commands.init import run_init
from cli.commands.import_context import run_import_context
from cli.commands.resume import run_resume
from cli.commands.session_discard import run_session_discard
from cli.commands.validate import run_validate
from core.schema import build_initial_state
from core.validation import validate_session_data, validate_state_data
from core.state_store import (
    RETENTION_ACTION_GROUP_LIMIT,
    RETENTION_NON_CONSOLIDATION_EVENT_LIMIT,
    RETENTION_VERIFICATION_GROUP_LIMIT,
    SESSION_CLAIMS_DIR_ENV_VAR,
    SESSION_LIVE_PROOFS_DIR_ENV_VAR,
    StateStore,
    StateStoreError,
)


def seed_valid_runtime(root: Path, filename: str = "tracked.txt", contents: str = "hello") -> tuple[StateStore, Path]:
    tracked = root / filename
    tracked.write_text(contents, encoding="utf-8")
    store = StateStore(root)
    if not store.state_path.exists():
        store.save_state(build_initial_state())
    store.register_sources([filename])
    return store, tracked


def make_args(**kwargs):
    return SimpleNamespace(**kwargs)


def session_token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def owner_binding_hash(binding: str = "holder-context") -> str:
    return hashlib.sha256(binding.encode("utf-8")).hexdigest()


def read_session_claim(store: StateStore, claim_id: str) -> dict:
    claim_data, claim_errors = store._read_session_claim_file(claim_id)
    if claim_errors or claim_data is None:
        raise AssertionError(f"expected valid session claim for {claim_id}, got {claim_errors}")
    return claim_data


def read_session_claim_bytes(store: StateStore, claim_id: str, *, backend: str | None = None) -> bytes | None:
    return store._read_optional_session_claim_bytes(claim_id, backend=backend)


def read_session_live_proof_bytes(store: StateStore, proof_id: str, *, backend: str | None = None) -> bytes | None:
    return store._read_optional_session_live_proof_bytes(proof_id, backend=backend)


def fail_unlink_for_path(target_path: Path):
    original_unlink = Path.unlink

    def side_effect(path_obj: Path, *args, **kwargs):
        if path_obj == target_path:
            raise OSError("synthetic unlink failure")
        return original_unlink(path_obj, *args, **kwargs)

    return mock.patch.object(Path, "unlink", autospec=True, side_effect=side_effect)


def fail_state_replace_for_payload(target_path: Path, *, marker: str):
    original_replace = os.replace

    def side_effect(source, destination):
        if Path(destination) == target_path:
            payload = Path(source).read_text(encoding="utf-8")
            if marker in payload:
                raise OSError("synthetic replace failure")
        return original_replace(source, destination)

    return mock.patch("core.state_store.os.replace", side_effect=side_effect)


def append_noise_events(store: StateStore, count: int) -> None:
    with store.events_path.open("ab") as handle:
        for index in range(count):
            payload = {
                "event_id": f"noise:{index:06d}",
                "trace_thread_id": "noise",
                "recorded_at": "2026-04-15T00:00:00+00:00",
                "revision": 0,
                "event": "runtime_event",
                "event_type": "runtime_event",
                "phase": "act",
                "step": "noise",
                "parent_event_id": "",
                "target": f"noise-{index:06d}",
            }
            handle.write((json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8"))


def seed_approved_action(store: StateStore, *, approval_id: str, action_kind: str, target: str) -> int:
    validation = store.validate_state()
    updated = store.update_agent_approval(
        {
            "id": approval_id,
            "status": "approved",
            "fingerprint": f"fp-{approval_id}",
            "action_kind": action_kind,
            "task_id": "",
            "target": target,
            "reason": "approval required",
            "requested_at": "2026-04-15T00:00:00+00:00",
            "resolved_at": "2026-04-15T00:00:01+00:00",
        },
        validated_revision=validation["revision"],
    )
    return updated["revision"]


def seed_retention_fixture(root: Path) -> StateStore:
    store, _ = seed_valid_runtime(root)
    validation = store.validate_state()
    store.update_agent_plan(
        {
            "goal": "Retention fixture",
            "summary": "Seed one verification command for retention coverage.",
            "tasks": [
                {
                    "id": "task-001",
                    "title": "Retention task",
                    "status": "ready",
                    "details": "Retention task",
                    "depends_on": [],
                    "working_set": ["tracked.txt"],
                    "acceptance_criteria": ["retention keeps live verification refs"],
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
        validated_revision=validation["revision"],
    )
    store.record_parallel_approach_consolidation(
        {
            "subject_kind": "task",
            "subject_id": "task-001",
            "compared_approach_ids": ["approach-a", "approach-b"],
            "winner_id": "approach-b",
            "winner_label": "approach B",
            "rejected_approach_ids": ["approach-a"],
            "comparison_basis": ["lower rollback cost"],
            "decision": "picked approach-b",
            "comparison_event_ids": ["evt-001"],
        }
    )

    validation_revision = seed_approved_action(
        store,
        approval_id="apr-live",
        action_kind="fs.create_file",
        target="draft.txt",
    )
    live_action_path = store.artifacts_dir / "actions" / "act-live" / "preimage.txt"
    live_action_path.parent.mkdir(parents=True, exist_ok=True)
    live_action_path.write_text("before", encoding="utf-8")
    live_action_ref = live_action_path.relative_to(store.cerebro_dir).as_posix()
    updated = store.record_agent_action(
        {
            "id": "act-live",
            "kind": "fs.create_file",
            "status": "applied",
            "summary": "retain live rollback artifact",
            "target": "draft.txt",
            "task_id": "",
            "batch_id": "",
            "approval_id": "apr-live",
            "artifact_refs": [live_action_ref],
            "rollback_ref": live_action_ref,
            "details": {
                "created_new": False,
                "path": "draft.txt",
                "rollback_artifact_sha256": hashlib.sha256(b"before").hexdigest(),
            },
            "updated_at": "2026-04-15T00:00:00+00:00",
        },
        validated_revision=validation_revision,
    )

    live_verification_dir = store.artifacts_dir / "verification" / "verify-live"
    live_verification_dir.mkdir(parents=True, exist_ok=True)
    live_stdout = live_verification_dir / "cmd-001.stdout.txt"
    live_stderr = live_verification_dir / "cmd-001.stderr.txt"
    live_stdout.write_text("passed", encoding="utf-8")
    live_stderr.write_text("", encoding="utf-8")
    live_stdout_ref = live_stdout.relative_to(store.cerebro_dir).as_posix()
    store.update_agent_verification(
        {
            "required_command_ids": ["cmd-001"],
            "pending_action_ids": [],
            "last_run_at": "2026-04-15T00:00:10+00:00",
            "status": "passed",
            "state_check": {
                "status": "passed",
                "exit_code": 0,
                "message": "",
            },
            "checks": [
                {
                    "id": "check-cmd-001",
                    "command_id": "cmd-001",
                    "status": "passed",
                    "exit_code": 0,
                    "artifact_ref": live_stdout_ref,
                    "artifact_sha256": hashlib.sha256(b"passed").hexdigest(),
                    "covered_action_ids": ["act-live"],
                    "message": "",
                }
            ],
        },
        validated_revision=updated["revision"],
    )

    for index in range(RETENTION_VERIFICATION_GROUP_LIMIT + 1):
        run_dir = store.artifacts_dir / "verification" / f"verify-old-{index:02d}"
        run_dir.mkdir(parents=True, exist_ok=True)
        artifact = run_dir / "cmd-001.stdout.txt"
        artifact.write_text(f"old verification {index}", encoding="utf-8")
        timestamp = 100 + index
        os.utime(artifact, (timestamp, timestamp))

    for index in range(RETENTION_ACTION_GROUP_LIMIT + 1):
        action_dir = store.artifacts_dir / "actions" / f"act-old-{index:03d}"
        action_dir.mkdir(parents=True, exist_ok=True)
        artifact = action_dir / "preimage.txt"
        artifact.write_text(f"old action {index}", encoding="utf-8")
        timestamp = 100 + index
        os.utime(artifact, (timestamp, timestamp))

    append_noise_events(store, RETENTION_NON_CONSOLIDATION_EVENT_LIMIT + 5)
    return store


class ValidationFunctionTests(unittest.TestCase):
    def _valid_state(self) -> dict:
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

    def _valid_task(self, task_id: str, *, status: str = "ready", depends_on: list[str] | None = None) -> dict:
        return {
            "id": task_id,
            "title": f"Task {task_id}",
            "status": status,
            "details": "Validation fixture task.",
            "depends_on": list(depends_on or []),
            "working_set": ["tracked.txt"],
            "acceptance_criteria": ["stays valid"],
            "action_ids": [],
            "retry_blocked_count": 0,
            "verify_blocked_count": 0,
            "apply_blocked_count": 0,
        }

    def _valid_command(
        self,
        command_id: str,
        *,
        allow_in_verify: bool,
        side_effect: str = "read_only",
    ) -> dict:
        return {
            "id": command_id,
            "argv": ["python", "--version"],
            "cwd": ".",
            "timeout_ms": 1000,
            "determinism": "high",
            "side_effect": side_effect,
            "risk": "low",
            "allow_in_verify": allow_in_verify,
        }

    def test_validate_state_rejects_orphan_current_task_id(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["plan"] = {
            **state["agent_runtime"]["plan"],
            "status": "ready",
            "current_task_id": "task-missing",
            "tasks": [self._valid_task("task-001")],
        }

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_plan_current_task_id", {item["code"] for item in errors})

    def test_validate_state_rejects_plan_task_cycles(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["plan"] = {
            **state["agent_runtime"]["plan"],
            "status": "blocked",
            "tasks": [
                self._valid_task("task-a", status="blocked", depends_on=["task-b"]),
                self._valid_task("task-b", status="blocked", depends_on=["task-a"]),
            ],
        }

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_plan_tasks", {item["code"] for item in errors})
        self.assertTrue(any("cycle detected" in item["message"] for item in errors))

    def test_validate_state_rejects_applied_action_with_rejected_approval(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["approvals"]["items"] = [
            {
                "id": "apr-001",
                "status": "rejected",
                "fingerprint": "fp-001",
                "action_kind": "fs.write_patch",
                "task_id": "",
                "target": "tracked.txt",
                "reason": "Unsafe",
                "requested_at": "2026-04-16T00:00:00+00:00",
                "resolved_at": "2026-04-16T00:01:00+00:00",
            }
        ]
        state["agent_runtime"]["actions"] = [
            {
                "id": "act-001",
                "kind": "fs.write_patch",
                "status": "applied",
                "summary": "Applied with rejected approval.",
                "target": "tracked.txt",
                "task_id": "",
                "batch_id": "",
                "approval_id": "apr-001",
                "artifact_refs": [],
                "rollback_ref": "",
                "details": {},
                "updated_at": "2026-04-16T00:02:00+00:00",
            }
        ]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_action_status", {item["code"] for item in errors})
        self.assertTrue(any("rejected approval" in item["message"] for item in errors))

    def test_validate_state_rejects_applied_sensitive_action_without_approval_id(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["actions"] = [
            {
                "id": "act-001",
                "kind": "fs.write_patch",
                "status": "applied",
                "summary": "Applied without approval.",
                "target": "tracked.txt",
                "task_id": "",
                "batch_id": "",
                "approval_id": "",
                "artifact_refs": [],
                "rollback_ref": "",
                "details": {},
                "updated_at": "2026-04-16T00:02:00+00:00",
            }
        ]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_action_status", {item["code"] for item in errors})
        self.assertTrue(any("requires a non-empty approval_id" in item["message"] for item in errors))

    def test_validate_state_rejects_applied_destructive_create_without_approval_id(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["actions"] = [
            {
                "id": "act-001",
                "kind": "fs.create_file",
                "status": "applied",
                "summary": "Overwrite without approval.",
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

    def test_validate_state_rejects_unknown_required_verification_command_id(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["verification"]["required_command_ids"] = ["cmd-missing"]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_verification_required_command_ids", {item["code"] for item in errors})
        self.assertTrue(any("unknown verification command id" in item["message"] for item in errors))

    def test_validate_state_rejects_empty_command_registry_cwd(self) -> None:
        state = self._valid_state()
        command = self._valid_command("cmd-001", allow_in_verify=True)
        command["cwd"] = ""
        state["agent_runtime"]["command_registry"]["commands"] = [command]

        errors = validate_state_data(state)

        self.assertIn("invalid_command_registry_command_cwd", {item["code"] for item in errors})

    def test_validate_state_rejects_command_registry_id_path_segment_escape(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["command_registry"]["commands"] = [
            self._valid_command("../escape", allow_in_verify=True)
        ]

        errors = validate_state_data(state)

        self.assertIn("invalid_command_registry_command_id", {item["code"] for item in errors})
        self.assertTrue(any("safe as a runtime path segment" in item["message"] for item in errors))

    def test_validate_state_accepts_safe_command_registry_path_segment_ids(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["command_registry"]["commands"] = [
            self._valid_command("cmd.fast_01", allow_in_verify=True)
        ]
        state["agent_runtime"]["verification"]["required_command_ids"] = ["cmd.fast_01"]

        errors = validate_state_data(state)

        self.assertNotIn("invalid_command_registry_command_id", {item["code"] for item in errors})

    def test_validate_state_accepts_command_registry_cwd_boundary_that_runtime_rejects_later(self) -> None:
        state = self._valid_state()
        command = self._valid_command("cmd-001", allow_in_verify=True)
        command["cwd"] = "../escape"
        state["agent_runtime"]["command_registry"]["commands"] = [command]

        errors = validate_state_data(state)

        self.assertNotIn("invalid_command_registry_command_cwd", {item["code"] for item in errors})

    def test_validate_state_rejects_required_verification_command_not_allowed_in_verify(self) -> None:
        state = self._valid_state()
        state["agent_runtime"]["command_registry"]["commands"] = [
            self._valid_command("cmd-001", allow_in_verify=False)
        ]
        state["agent_runtime"]["verification"]["required_command_ids"] = ["cmd-001"]

        errors = validate_state_data(state)

        self.assertIn("invalid_agent_verification_required_command_ids", {item["code"] for item in errors})
        self.assertTrue(any("not allowed in verify" in item["message"] for item in errors))

    def test_validate_session_rejects_empty_owner_claim_id(self) -> None:
        session = {
            "session_id": "session-001",
            "opened_at": "2026-04-16T00:00:00+00:00",
            "actor": "alice",
            "based_on_revision": 1,
            "owner_claim_id": "",
        }

        errors = validate_session_data(session)

        self.assertEqual(["invalid_session_owner_claim_id"], [item["code"] for item in errors])

    def test_validate_state_rejects_invalid_source_path_boundaries(self) -> None:
        for path in ("C:/tmp/a.txt", "../a.txt", "dir\\a.txt"):
            with self.subTest(path=path):
                state = self._valid_state()
                state["sources"] = [
                    {
                        "path": path,
                        "sha256": "a" * 64,
                        "role": "primary",
                    }
                ]

                errors = validate_state_data(state)

                self.assertIn("invalid_source_path", {item["code"] for item in errors})


class ValidateCommandTests(unittest.TestCase):
    def test_init_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            exit_code = run_init(root)

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / ".cerebro" / "state.json").exists())
            self.assertTrue((root / ".cerebro" / "artifacts").exists())
            self.assertTrue((root / ".cerebro" / "logs" / "events.jsonl").exists())
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())
            self.assertTrue((root / ".cerebro" / "trash").exists())

    def test_validate_accepts_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = seed_valid_runtime(root)

            result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])

    def test_validate_fails_without_registered_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "sources_unregistered")

    def test_validate_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            (cerebro_dir / "state.json").write_text("{invalid", encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_json")

    def test_validate_reports_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid_state = build_initial_state()
            invalid_state["revision"] = "1"
            (cerebro_dir / "state.json").write_text(
                json.dumps(invalid_state, indent=2),
                encoding="utf-8",
            )

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_schema")

    def test_validate_ok_with_intact_registered_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])

            result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])
            updated = store.load_state()
            self.assertEqual(updated["last_validation"]["result"], "ok")

    def test_validate_fail_when_registered_file_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])
            source_file.unlink()

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "source_missing")

    def test_validate_fail_when_registered_file_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "source_hash_mismatch")

    def test_validate_retention_report_is_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            expected = store.inspect_retention(expected_revision=store.validate_state()["revision"])
            before_events = store.events_path.read_bytes()

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_validate(root, make_args(retention_report=True, retention_apply=False))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn(
                f"retention_event_candidates: {expected['events']['archived_line_count']} lines / {expected['events']['archived_bytes']} bytes",
                output,
            )
            self.assertIn(
                f"retention_artifact_candidates: {expected['artifacts']['archive_group_count']} groups / {expected['artifacts']['archive_file_count']} files / {expected['artifacts']['archive_bytes']} bytes",
                output,
            )
            self.assertEqual(store.events_path.read_bytes(), before_events)
            self.assertTrue((store.artifacts_dir / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertTrue((store.artifacts_dir / "actions" / "act-old-000" / "preimage.txt").exists())
            self.assertFalse((store.trash_dir / "retention").exists())

    def test_inspect_retention_rejects_stale_expected_revision_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            current_revision = store.validate_state()["revision"]
            before_events = store.events_path.read_bytes()

            with self.assertRaisesRegex(StateStoreError, "state revision changed during operation"):
                store.inspect_retention(expected_revision=current_revision + 1)

            self.assertEqual(store.events_path.read_bytes(), before_events)
            self.assertFalse((store.trash_dir / "retention").exists())

    def test_inspect_retention_blocks_unknown_artifact_surfaces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            unknown_artifact = store.artifacts_dir / "misc" / "odd.txt"
            unknown_artifact.parent.mkdir(parents=True, exist_ok=True)
            unknown_artifact.write_text("unknown", encoding="utf-8")

            report = store.inspect_retention(expected_revision=store.validate_state()["revision"])

            self.assertEqual(report["artifacts"]["blocked_unknown_group_count"], 1)
            self.assertEqual(report["artifacts"]["blocked_unknown_examples"], ("misc/odd.txt",))

    def test_apply_retention_rejects_stale_expected_revision_without_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            current_revision = store.validate_state()["revision"]
            before_events = store.events_path.read_bytes()
            live_artifact = store.artifacts_dir / "verification" / "verify-old-00" / "cmd-001.stdout.txt"

            with self.assertRaisesRegex(StateStoreError, "state revision changed during operation"):
                store.apply_retention(expected_revision=current_revision + 1)

            self.assertEqual(store.events_path.read_bytes(), before_events)
            self.assertFalse((store.trash_dir / "retention").exists())
            self.assertTrue(live_artifact.exists())

    def test_validate_retention_apply_archives_eligible_surfaces_and_preserves_live_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            expected = store.inspect_retention(expected_revision=store.validate_state()["revision"])

            with mock.patch.object(StateStore, "_timestamp_now", return_value="2026-04-15T00:00:20+00:00"):
                stream = io.StringIO()
                with redirect_stdout(stream):
                    exit_code = run_validate(root, make_args(retention_report=False, retention_apply=True))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("retention_applied: governed runtime cleanup archived only eligible surfaces", output)

            archives = sorted((store.trash_dir / "retention").glob("retention-*"))
            self.assertEqual(len(archives), 1)
            archive_root = archives[0]
            manifest = json.loads((archive_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["events"]["archived_line_count"], expected["events"]["archived_line_count"])
            self.assertEqual(manifest["artifacts"]["archived_group_count"], expected["artifacts"]["archive_group_count"])
            self.assertTrue((archive_root / "artifacts" / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertTrue((archive_root / "artifacts" / "actions" / "act-old-000" / "preimage.txt").exists())
            self.assertTrue((archive_root / "logs" / "events.archived.jsonl").exists())

            self.assertFalse((store.artifacts_dir / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertFalse((store.artifacts_dir / "actions" / "act-old-000" / "preimage.txt").exists())
            self.assertTrue((store.artifacts_dir / "verification" / "verify-live" / "cmd-001.stdout.txt").exists())
            self.assertTrue((store.artifacts_dir / "verification" / "verify-live" / "cmd-001.stderr.txt").exists())
            self.assertTrue((store.artifacts_dir / "actions" / "act-live" / "preimage.txt").exists())

            active_events = [line for line in store.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(any("parallel_approach_consolidated" in line for line in active_events))
            self.assertTrue(any("retention_applied" in line for line in active_events))
            self.assertEqual(
                sum(1 for line in active_events if '"event":"runtime_event"' in line),
                RETENTION_NON_CONSOLIDATION_EVENT_LIMIT,
            )

            second_stream = io.StringIO()
            with mock.patch.object(StateStore, "_timestamp_now", return_value="2026-04-15T00:00:20+00:00"):
                with redirect_stdout(second_stream):
                    second_exit = run_validate(root, make_args(retention_report=False, retention_apply=True))
            self.assertEqual(second_exit, 0)
            self.assertIn("retention_applied: no eligible cleanup candidates", second_stream.getvalue())
            self.assertEqual(len(sorted((store.trash_dir / "retention").glob("retention-*"))), 1)

    def test_validate_retention_apply_rerun_is_safe_after_manifest_write_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            original_write_json_atomic = StateStore._write_json_atomic
            manifest_failure = {"triggered": False}

            def flaky_write_json_atomic(store_self: StateStore, path: Path, data: object) -> None:
                target = Path(path)
                if (
                    not manifest_failure["triggered"]
                    and target.name == "manifest.json"
                    and "/trash/retention/retention-" in target.as_posix()
                ):
                    manifest_failure["triggered"] = True
                    raise StateStoreError("simulated retention manifest write failure")
                original_write_json_atomic(store_self, target, data)

            failed_stream = io.StringIO()
            with mock.patch.object(
                StateStore,
                "_write_json_atomic",
                autospec=True,
                side_effect=flaky_write_json_atomic,
            ):
                with redirect_stdout(failed_stream):
                    failed_exit = run_validate(root, make_args(retention_report=False, retention_apply=True))

            failed_output = failed_stream.getvalue()
            self.assertEqual(failed_exit, 1)
            self.assertTrue(manifest_failure["triggered"])
            self.assertIn("simulated retention manifest write failure", failed_output)

            archives = sorted((store.trash_dir / "retention").glob("retention-*"))
            self.assertEqual(len(archives), 1)
            archive_root = archives[0]
            self.assertFalse((archive_root / "manifest.json").exists())
            pending_manifest = json.loads((archive_root / "manifest.pending.json").read_text(encoding="utf-8"))
            self.assertIn("retention_event", pending_manifest)
            self.assertTrue((archive_root / "artifacts" / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertTrue((archive_root / "artifacts" / "actions" / "act-old-000" / "preimage.txt").exists())
            self.assertTrue((archive_root / "logs" / "events.archived.jsonl").exists())
            self.assertFalse((store.artifacts_dir / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertFalse((store.artifacts_dir / "actions" / "act-old-000" / "preimage.txt").exists())

            active_events = [line for line in store.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertTrue(any("parallel_approach_consolidated" in line for line in active_events))
            self.assertEqual(sum(1 for line in active_events if "retention_applied" in line), 1)
            self.assertEqual(
                sum(1 for line in active_events if '"event":"runtime_event"' in line),
                RETENTION_NON_CONSOLIDATION_EVENT_LIMIT,
            )

            rerun_stream = io.StringIO()
            with redirect_stdout(rerun_stream):
                rerun_exit = run_validate(root, make_args(retention_report=False, retention_apply=True))

            self.assertEqual(rerun_exit, 0)
            rerun_output = rerun_stream.getvalue()
            self.assertIn("retention_applied: governed runtime cleanup archived only eligible surfaces", rerun_output)
            manifest = json.loads((archive_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["retention_event_id"], pending_manifest["retention_event"]["event_id"])
            self.assertFalse((archive_root / "manifest.pending.json").exists())
            self.assertEqual(len(sorted((store.trash_dir / "retention").glob("retention-*"))), 1)
            rerun_events = [line for line in store.events_path.read_text(encoding="utf-8").splitlines() if line.strip()]
            self.assertEqual(sum(1 for line in rerun_events if "retention_applied" in line), 1)

    def test_validate_retention_apply_fails_when_retention_trace_append_degrades_and_rerun_is_safe(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = seed_retention_fixture(root)
            original_write_trace_event_line = StateStore._write_trace_event_line
            append_failure = {"triggered": False}

            def truncated_retention_append(store_self: StateStore, event: dict) -> None:
                if not append_failure["triggered"] and event.get("event_type") == "retention_applied":
                    append_failure["triggered"] = True
                    store_self.logs_dir.mkdir(parents=True, exist_ok=True)
                    with store_self.events_path.open("ab") as handle:
                        partial = (
                            json.dumps(
                                {"event_type": event["event_type"], "event_id": event["event_id"]},
                                separators=(",", ":"),
                            ).encode("utf-8")[:24]
                        )
                        handle.write(partial + b"\n")
                    raise OSError("simulated truncated retention_applied append")
                original_write_trace_event_line(store_self, event)

            failed_stream = io.StringIO()
            with mock.patch.object(
                StateStore,
                "_write_trace_event_line",
                autospec=True,
                side_effect=truncated_retention_append,
            ):
                with mock.patch.object(StateStore, "_timestamp_now", return_value="2026-04-15T00:00:20+00:00"):
                    with redirect_stdout(failed_stream):
                        failed_exit = run_validate(root, make_args(retention_report=False, retention_apply=True))

            failed_output = failed_stream.getvalue()
            self.assertEqual(failed_exit, 1)
            self.assertTrue(append_failure["triggered"])
            self.assertIn("simulated truncated retention_applied append", failed_output)
            self.assertNotIn("validation_passed: context is valid for runtime use", failed_output)
            self.assertNotIn("retention_applied: governed runtime cleanup archived only eligible surfaces", failed_output)

            archives = sorted((store.trash_dir / "retention").glob("retention-*"))
            self.assertEqual(len(archives), 1)
            archive_root = archives[0]
            self.assertFalse((archive_root / "manifest.json").exists())
            pending_manifest = json.loads((archive_root / "manifest.pending.json").read_text(encoding="utf-8"))
            self.assertEqual(pending_manifest["retention_event"]["event_type"], "retention_applied")
            self.assertTrue((archive_root / "artifacts" / "verification" / "verify-old-00" / "cmd-001.stdout.txt").exists())
            self.assertTrue((archive_root / "artifacts" / "actions" / "act-old-000" / "preimage.txt").exists())
            self.assertTrue((archive_root / "logs" / "events.archived.jsonl").exists())

            active_raw_lines = [line for line in store.events_path.read_bytes().splitlines() if line.strip()]
            self.assertTrue(any(store._parse_parallel_approach_consolidation_line(line) is not None for line in active_raw_lines))
            self.assertFalse(any(store._parse_event_log_event_type(line) == "retention_applied" for line in active_raw_lines))
            self.assertEqual(
                sum(1 for line in active_raw_lines if b'"event":"runtime_event"' in line),
                RETENTION_NON_CONSOLIDATION_EVENT_LIMIT,
            )

            audit = store.load_state()["agent_runtime"]["audit"]
            self.assertEqual(audit["trace_status"], "degraded")
            self.assertEqual(audit["trace_integrity"], "partial")
            self.assertIn("simulated truncated retention_applied append", audit["last_trace_error"])

            rerun_stream = io.StringIO()
            with redirect_stdout(rerun_stream):
                rerun_exit = run_validate(root, make_args(retention_report=False, retention_apply=True))

            rerun_output = rerun_stream.getvalue()
            self.assertEqual(rerun_exit, 0)
            self.assertIn("retention_applied: governed runtime cleanup archived only eligible surfaces", rerun_output)
            final_manifest = json.loads((archive_root / "manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(final_manifest["retention_event_id"], pending_manifest["retention_event"]["event_id"])
            self.assertFalse((archive_root / "manifest.pending.json").exists())
            rerun_raw_lines = [line for line in store.events_path.read_bytes().splitlines() if line.strip()]
            self.assertLessEqual(
                sum(1 for line in rerun_raw_lines if store._parse_event_log_event_type(line) == "retention_applied"),
                1,
            )
            self.assertEqual(len(sorted((store.trash_dir / "retention").glob("retention-*"))), 1)

    def test_validate_fails_when_live_runtime_rollback_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = seed_valid_runtime(root)
            artifact_path = store.cerebro_dir / "artifacts" / "actions" / "act-001" / "preimage.txt"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text("before", encoding="utf-8")
            artifact_ref = artifact_path.relative_to(store.cerebro_dir).as_posix()
            validation_revision = seed_approved_action(
                store,
                approval_id="apr-001",
                action_kind="fs.create_file",
                target="draft.txt",
            )

            store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "overwrite draft",
                    "target": "draft.txt",
                    "task_id": "",
                    "batch_id": "",
                    "approval_id": "apr-001",
                    "artifact_refs": [artifact_ref],
                    "rollback_ref": artifact_ref,
                    "details": {"created_new": False, "path": "draft.txt"},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=validation_revision,
            )
            artifact_path.unlink()

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("runtime_artifact_missing", output)
            self.assertIn("agent_runtime.actions[0].rollback_ref", output)
            self.assertEqual(store.load_state()["last_validation"]["result"], "fail")

    def test_validate_fails_when_live_runtime_rollback_artifact_content_diverges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = seed_valid_runtime(root)
            artifact_path = store.cerebro_dir / "artifacts" / "actions" / "act-001" / "preimage.txt"
            artifact_path.parent.mkdir(parents=True, exist_ok=True)
            artifact_path.write_text("before", encoding="utf-8")
            artifact_ref = artifact_path.relative_to(store.cerebro_dir).as_posix()
            validation_revision = seed_approved_action(
                store,
                approval_id="apr-001",
                action_kind="fs.create_file",
                target="draft.txt",
            )

            store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "overwrite draft",
                    "target": "draft.txt",
                    "task_id": "",
                    "batch_id": "",
                    "approval_id": "apr-001",
                    "artifact_refs": [artifact_ref],
                    "rollback_ref": artifact_ref,
                    "details": {
                        "created_new": False,
                        "path": "draft.txt",
                        "rollback_artifact_sha256": hashlib.sha256(b"before").hexdigest(),
                    },
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=validation_revision,
            )
            artifact_path.write_text("tampered", encoding="utf-8")

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("runtime_artifact_hash_mismatch", output)
            self.assertIn("agent_runtime.actions[0].rollback_ref", output)

    def test_validate_fails_when_live_runtime_artifact_ref_resolves_outside_cerebro(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = seed_valid_runtime(root)
            validation_revision = seed_approved_action(
                store,
                approval_id="apr-001",
                action_kind="fs.create_file",
                target="draft.txt",
            )
            store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "overwrite draft",
                    "target": "draft.txt",
                    "task_id": "",
                    "batch_id": "",
                    "approval_id": "apr-001",
                    "artifact_refs": ["../outside.txt"],
                    "rollback_ref": "../outside.txt",
                    "details": {"created_new": False, "path": "draft.txt"},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=validation_revision,
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("runtime_artifact_invalid", output)
            self.assertIn("resolves outside .cerebro", output)

    def test_validate_fails_when_live_runtime_artifact_ref_points_to_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store, _ = seed_valid_runtime(root)
            artifact_dir = store.cerebro_dir / "artifacts" / "actions" / "act-001"
            artifact_dir.mkdir(parents=True, exist_ok=True)
            artifact_ref = artifact_dir.relative_to(store.cerebro_dir).as_posix()
            validation_revision = seed_approved_action(
                store,
                approval_id="apr-001",
                action_kind="fs.create_file",
                target="draft.txt",
            )
            store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "overwrite draft",
                    "target": "draft.txt",
                    "task_id": "",
                    "batch_id": "",
                    "approval_id": "apr-001",
                    "artifact_refs": [artifact_ref],
                    "rollback_ref": artifact_ref,
                    "details": {"created_new": False, "path": "draft.txt"},
                    "updated_at": "2026-04-15T00:00:00+00:00",
                },
                validated_revision=validation_revision,
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("runtime_artifact_invalid", output)
            self.assertIn("must resolve to a file inside .cerebro", output)

    def test_validate_command_reports_runtime_lock_timeout_as_operation_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.lock_path.write_text("999999", encoding="utf-8")
            stream = io.StringIO()

            with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 0):
                with mock.patch("core.state_store.os.kill", return_value=None):
                    with redirect_stdout(stream):
                        exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("operation_failed", output)
            self.assertIn("runtime lock", output)
            self.assertNotIn("internal_error", output)

    def test_validate_reports_wrong_directory_guidance_when_project_root_is_an_ancestor(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            nested = root / "subdir" / "deeper"
            nested.mkdir(parents=True)
            run_init(root, None)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(nested)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("state_missing", output)
            self.assertIn("no Cerebro state found in current directory", output)
            self.assertIn("outside the project directory", output)
            self.assertIn(f'cd "{root}"', output)

    def test_validate_reports_import_context_as_next_step_when_sources_are_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("sources_unregistered", output)
            self.assertIn("Next step: run `cerebro import-context --files ...`", output)
            self.assertIn("README.md", output)

    def test_validate_reports_state_missing_after_initialized_state_file_is_deleted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            state_path = root / ".cerebro" / "state.json"
            state_path.unlink()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("state_missing", output)
            self.assertIn("no Cerebro state found in current directory", output)
            self.assertIn("run `cerebro init` first", output)
            self.assertNotIn("internal_error", output)

    def test_resume_command_reports_runtime_lock_timeout_as_operation_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.lock_path.write_text("999999", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"actor": "alice"})

            with mock.patch("core.state_store.RUNTIME_LOCK_TIMEOUT_SECONDS", 0):
                with mock.patch("core.state_store.os.kill", return_value=None):
                    with redirect_stdout(stream):
                        exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("operation_failed", output)
            self.assertIn("runtime lock", output)
            self.assertNotIn("internal_error", output)

    def test_import_context_command_replaces_sources_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")
            run_init(root, None)

            args = type("Args", (), {"files": ["b.txt", "a.txt", "b.txt"]})
            with mock.patch("builtins.input", return_value="y"):
                exit_code = run_import_context(root, args)

            self.assertEqual(exit_code, 0)
            state = StateStore(root).load_state()
            self.assertEqual([item["path"] for item in state["sources"]], ["a.txt", "b.txt"])
            self.assertEqual(state["revision"], 1)

    def test_import_context_command_closes_existing_session_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["a.txt"])
            session = store.open_session("alice")

            args = make_args(files=["a.txt"], session_token=session["session_token"])
            with mock.patch("builtins.input", return_value="y"):
                exit_code = run_import_context(root, args)

            self.assertEqual(exit_code, 0)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())

    def test_import_context_reports_operation_failed_without_mutating_state_when_session_close_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["a.txt"])
                session = store.open_session("alice")
                before = store.load_state()
                before_session = store.session_path.read_text(encoding="utf-8")
                claim = read_session_claim(store, session["owner_claim_id"])
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(files=["a.txt"], session_token=session["session_token"])
                stream = io.StringIO()
                with fail_unlink_for_path(store.session_path):
                    with mock.patch("builtins.input", return_value="y"):
                        with redirect_stdout(stream):
                            exit_code = run_import_context(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to remove session file", output)
                self.assertIn("session.local.json", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["sources"], before["sources"])
                self.assertEqual(after["last_validation"], before["last_validation"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)

    def test_import_context_reports_operation_failed_without_mutating_state_when_session_file_read_raises_during_close(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            replacement_file = root / "b.txt"
            source_file.write_text("a", encoding="utf-8")
            replacement_file.write_text("b", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["a.txt"])
                session = store.open_session("alice")
                before = store.load_state()
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                claim = read_session_claim(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(files=["b.txt"], session_token=session["session_token"])
                stream = io.StringIO()
                original_close_session = StateStore.close_session

                def fail_during_close_session(self):
                    with mock.patch.object(self, "_read_session_file", side_effect=RuntimeError("synthetic session read failure")):
                        return original_close_session(self)

                with mock.patch.object(StateStore, "close_session", autospec=True, side_effect=fail_during_close_session):
                    with mock.patch("builtins.input", return_value="y"):
                        with redirect_stdout(stream):
                            exit_code = run_import_context(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to read session file before closing session", output)
                self.assertIn("session_unreadable", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["sources"], before["sources"])
                self.assertEqual(after["last_validation"], before["last_validation"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.session_path.exists())
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)

    def test_import_context_reports_operation_failed_without_losing_session_when_state_write_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_override, tempfile.TemporaryDirectory() as proofs_override:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            with mock.patch.dict(
                os.environ,
                {
                    SESSION_CLAIMS_DIR_ENV_VAR: claims_override,
                    SESSION_LIVE_PROOFS_DIR_ENV_VAR: proofs_override,
                },
                clear=False,
            ):
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["a.txt"])
                session = store.open_session("alice")
                before = store.load_state()
                before_session = store.session_path.read_text(encoding="utf-8")
                claim = read_session_claim(store, session["owner_claim_id"])
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(files=["a.txt"], session_token=session["session_token"])
                stream = io.StringIO()
                with fail_state_replace_for_payload(store.state_path, marker="sources_not_validated"):
                    with mock.patch("builtins.input", return_value="y"):
                        with redirect_stdout(stream):
                            exit_code = run_import_context(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to write file", output)
                self.assertIn("state.json", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["sources"], before["sources"])
                self.assertEqual(after["last_validation"], before["last_validation"])
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)
            self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
            self.assertEqual(
                after["agent_runtime"]["audit"]["active_session_claim_id"],
                before["agent_runtime"]["audit"]["active_session_claim_id"],
            )

    def test_import_context_command_does_not_save_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            run_init(root, None)

            args = type("Args", (), {"files": ["a.txt"]})
            with mock.patch("builtins.input", return_value="n"):
                exit_code = run_import_context(root, args)

            self.assertEqual(exit_code, 0)
            state = StateStore(root).load_state()
            self.assertEqual(state["sources"], [])
            self.assertEqual(state["revision"], 0)

    def test_validate_fails_with_session_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text("{invalid", encoding="utf-8")

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_invalid_json")

    def test_validate_fails_with_session_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text(
                json.dumps(
                    {
                        "session_id": "session-test",
                        "opened_at": "2026-04-10T00:00:00+00:00",
                        "based_on_revision": 0,
                        "owner_claim_id": "claim-test",
                    }
                ),
                encoding="utf-8",
            )

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_invalid_schema")

    def test_validate_fails_with_session_revision_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session_path = root / ".cerebro" / "session.local.json"
            store.open_session("alice")
            session_data = json.loads(session_path.read_text(encoding="utf-8"))
            session_data["based_on_revision"] = 2
            session_path.write_text(json.dumps(session_data), encoding="utf-8")

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_revision_invalid")

    def test_validate_fails_with_stale_session_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            session_path = root / ".cerebro" / "session.local.json"
            store.open_session("alice")
            session_data = json.loads(session_path.read_text(encoding="utf-8"))
            session_data["based_on_revision"] = 0
            session_path.write_text(json.dumps(session_data), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_revision_invalid")

    def test_validate_fails_when_session_claim_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")
            store._remove_session_claim(session["owner_claim_id"])

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_claim_missing")

    def test_session_discard_clears_stale_session_and_requires_explicit_reopen(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
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
            session_path = root / ".cerebro" / "session.local.json"
            stale_session = json.loads(session_path.read_text(encoding="utf-8"))
            stale_session["based_on_revision"] -= 1
            session_path.write_text(json.dumps(stale_session), encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, make_args(session_token=session["session_token"]))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_discarded", output)
            self.assertIn("stale-session block cleared", output)
            self.assertIn("run `cerebro analyze` to reopen continuity explicitly", output)
            self.assertFalse(session_path.exists())
            self.assertTrue(store.validate_state()["ok"])
            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["event"], "session_discarded")
            self.assertEqual(latest_event["mode"], "stale_session_recovery")

            analyze_args = type("Args", (), {"actor": "bob"})
            analyze_stream = io.StringIO()
            with redirect_stdout(analyze_stream):
                analyze_exit = run_analyze(root, analyze_args)

            self.assertEqual(analyze_exit, 0)
            session = json.loads(session_path.read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "bob")

    def test_session_discard_clears_registry_only_session_residue_after_open_session_split(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")
            session_path = root / ".cerebro" / "session.local.json"
            session_path.unlink()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_discarded", output)
            self.assertIn("stale-session block cleared", output)
            self.assertIn("run `cerebro analyze` to reopen continuity explicitly", output)
            self.assertFalse(session_path.exists())
            self.assertTrue(store.validate_state()["ok"])
            state = store.load_state()
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_id"], "")
            self.assertEqual(state["agent_runtime"]["audit"]["active_session_claim_id"], "")
            self.assertIsNone(read_session_claim_bytes(store, session["owner_claim_id"]))

    def test_session_discard_clears_orphan_session_local_residue_after_close_session_crash_window(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")
            claim = read_session_claim(store, session["owner_claim_id"])
            state = store.load_state()
            store._clear_active_session_registry(state)
            store.save_state(state, expected_revision=state["revision"])
            store._remove_session_live_proof(claim["live_proof_id"])
            store._remove_session_claim(session["owner_claim_id"])
            session_path = root / ".cerebro" / "session.local.json"
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_discarded", output)
            self.assertIn("stale-session block cleared", output)
            self.assertIn("run `cerebro analyze` to reopen continuity explicitly", output)
            self.assertFalse(session_path.exists())
            self.assertIsNone(read_session_claim_bytes(store, session["owner_claim_id"]))
            self.assertTrue(store.validate_state()["ok"])

    def test_session_discard_reports_absent_when_no_local_session_or_registry_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_valid_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_absent", output)
            self.assertIn("run `cerebro analyze` if you need to open continuity", output)
            self.assertNotIn("stale-session block cleared", output)

    def test_session_discard_closes_valid_session_without_claiming_stale_recovery(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, make_args(session_token=session["session_token"]))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_discarded", output)
            self.assertIn("local continuity closed explicitly", output)
            self.assertNotIn("stale-session block cleared", output)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())
            latest_event = store.read_recent_events(limit=1)[0]
            self.assertEqual(latest_event["event"], "session_discarded")
            self.assertEqual(latest_event["mode"], "explicit_close")

    def test_session_discard_blocks_when_validation_has_non_session_errors(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, tracked = seed_valid_runtime(root)
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
            stale_session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            stale_session["based_on_revision"] -= 1
            (root / ".cerebro" / "session.local.json").write_text(json.dumps(stale_session), encoding="utf-8")
            tracked.write_text("changed", encoding="utf-8")
            session_path = root / ".cerebro" / "session.local.json"
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, make_args(session_token=session["session_token"]))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_discard_blocked", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertTrue(session_path.exists())

    def test_session_discard_blocks_without_explicit_session_token_when_claim_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")
            session_path = root / ".cerebro" / "session.local.json"
            stale_session = json.loads(session_path.read_text(encoding="utf-8"))
            stale_session["based_on_revision"] -= 1
            session_path.write_text(json.dumps(stale_session), encoding="utf-8")
            before_state = store.load_state()
            before_claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
            self.assertIsNotNone(before_claim_bytes)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            after_state = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_discard_blocked", output)
            self.assertIn("session_token_required", output)
            self.assertTrue(session_path.exists())
            self.assertEqual(after_state["revision"], before_state["revision"])
            self.assertEqual(after_state["agent_runtime"]["audit"], before_state["agent_runtime"]["audit"])
            self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim_bytes)

    def test_session_discard_blocks_replayed_session_token_from_different_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
            stream = io.StringIO()

            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-b"):
                with redirect_stdout(stream):
                    exit_code = run_session_discard(root, make_args(session_token=session["session_token"]))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_discard_blocked", output)
            self.assertIn("session_owner_binding_mismatch", output)
            self.assertTrue((root / ".cerebro" / "session.local.json").exists())

    def test_session_discard_reports_operation_failed_when_core_discard_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_valid_runtime(root)
            stream = io.StringIO()

            with mock.patch.object(
                StateStore,
                "discard_session",
                side_effect=StateStoreError("failed to remove session file: session.local.json"),
            ):
                with redirect_stdout(stream):
                    exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("operation_failed", output)
            self.assertIn("failed to remove session file", output)

    def test_resume_with_valid_state_creates_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready to continue.",
                    "next_step": "Open the target file.",
                    "constraints": ["Do not change public API"],
                }
            )

            args = type("Args", (), {"actor": "alice"})
            exit_code = run_resume(root, args)

            self.assertEqual(exit_code, 0)
            session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertTrue(session["session_id"])
            self.assertEqual(session["actor"], "alice")
            self.assertEqual(session["based_on_revision"], 2)

    def test_resume_blocks_when_validate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")

            args = type("Args", (), {"actor": "alice"})
            exit_code = run_resume(root, args)

            self.assertEqual(exit_code, 1)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())

    def test_resume_blocks_when_local_session_is_already_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            store.open_session("old")

            stream = io.StringIO()
            args = type("Args", (), {"actor": "new"})
            with redirect_stdout(stream):
                exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("resume_blocked", output)
            self.assertIn("session_open_conflict", output)
            self.assertIn("session-discard", output)
            session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "old")
            self.assertEqual(session["based_on_revision"], 2)

    def test_resume_blocks_file_snapshot_replay_when_live_proof_backend_is_wincred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            if store._session_live_proof_backend() != "wincred":
                self.skipTest("requires Windows credential-backed live-proof storage")
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                claim_data = read_session_claim(store, session["owner_claim_id"])
                proof_bytes = store._read_optional_session_live_proof_bytes(claim_data["live_proof_id"])
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                self.assertIsNotNone(proof_bytes)
                store._write_bytes_atomic(
                    store._session_live_proof_path(claim_data["live_proof_id"]),
                    proof_bytes,
                )
                store._write_bytes_atomic(session_path, session_bytes)

            stream = io.StringIO()
            args = type("Args", (), {"actor": "bob"})
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("resume_blocked", output)
            self.assertIn("session_live_proof_missing", output)
            session_data = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertEqual(session_data["actor"], "alice")

    def test_resume_blocks_file_snapshot_replay_when_claim_backend_is_wincred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            if store._session_claim_backend() != "wincred":
                self.skipTest("requires Windows credential-backed session claim storage")
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_bytes_atomic(store._session_claim_path(session["owner_claim_id"]), claim_bytes)
                store._write_bytes_atomic(session_path, session_bytes)

            stream = io.StringIO()
            args = type("Args", (), {"actor": "bob"})
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("resume_blocked", output)
            self.assertIn("session_claim_missing", output)
            session_data = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertEqual(session_data["actor"], "alice")

    def test_checkpoint_blocks_when_session_changes_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Before",
                    "summary": "Stable round.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )

            alice_session = store.open_session("alice")
            self.assertEqual(
                run_session_discard(root, make_args(session_token=alice_session["session_token"])),
                0,
            )
            bob_session = store.open_session("bob")

            args = make_args(
                goal="After",
                summary="Alice stale write.",
                next_step="Do not save.",
                constraint=[],
                actor="alice",
                session_token=bob_session["session_token"],
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            state = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("checkpoint_actor_mismatch", output)
            self.assertEqual(session["actor"], "bob")
            self.assertEqual(state["checkpoint"]["summary"], "Stable round.")

    def test_checkpoint_blocks_replayed_session_token_from_different_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")

            args = make_args(
                goal="Ship",
                summary="Replay should fail.",
                next_step="Stop.",
                constraint=[],
                actor="alice",
                session_token=session["session_token"],
            )
            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-b"):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_owner_binding_mismatch", output)
            self.assertTrue((root / ".cerebro" / "session.local.json").exists())

    def test_checkpoint_blocks_restored_discarded_session_in_same_holder(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                store._write_bytes_atomic(session_path, session_bytes)

            args = make_args(
                goal="Hijacked",
                summary="Restored session should fail.",
                next_step="Stop.",
                constraint=[],
                actor="alice",
                session_token=session["session_token"],
            )
            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_not_registered", output)
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_checkpoint_blocks_full_snapshot_replay_without_explicit_session_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                store._write_bytes_atomic(session_path, session_bytes)

            args = make_args(
                goal="Hijacked",
                summary="Restored snapshot should not regain ownership.",
                next_step="Stop.",
                constraint=[],
                actor="alice",
            )
            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_live_proof_missing", output)
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_checkpoint_blocks_full_snapshot_replay_without_live_proof_even_with_explicit_session_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                store._write_bytes_atomic(session_path, session_bytes)

            args = make_args(
                goal="Hijacked",
                summary="Restored snapshot should still fail without live proof.",
                next_step="Stop.",
                constraint=[],
                actor="alice",
                session_token=session["session_token"],
            )
            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_live_proof_missing", output)
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_checkpoint_blocks_file_snapshot_replay_when_live_proof_backend_is_wincred(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
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
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                claim_data = read_session_claim(store, session["owner_claim_id"])
                proof_bytes = store._read_optional_session_live_proof_bytes(claim_data["live_proof_id"])
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                self.assertIsNotNone(proof_bytes)
                store._write_bytes_atomic(
                    store._session_live_proof_path(claim_data["live_proof_id"]),
                    proof_bytes,
                )
                store._write_bytes_atomic(session_path, session_bytes)

            args = make_args(
                goal="Hijacked",
                summary="File restore must not revive a wincred-backed live proof.",
                next_step="Stop.",
                constraint=[],
                actor="alice",
                session_token=session["session_token"],
            )
            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_live_proof_missing", output)
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Ready.")

    def test_session_discard_clears_full_snapshot_restore_without_live_proof_and_no_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
                state_bytes = (root / ".cerebro" / "state.json").read_bytes()
                session_path = root / ".cerebro" / "session.local.json"
                session_bytes = session_path.read_bytes()
                claim_bytes = read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(claim_bytes)
                store.discard_session(expected_session_token=session["session_token"])
                store._write_bytes_atomic(root / ".cerebro" / "state.json", state_bytes)
                store._write_session_claim_bytes(session["owner_claim_id"], claim_bytes)
                store._write_bytes_atomic(session_path, session_bytes)

            stream = io.StringIO()
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                with redirect_stdout(stream):
                    exit_code = run_session_discard(root, None)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("session_discarded", output)
            self.assertIn("stale-session block cleared", output)
            self.assertFalse(session_path.exists())
            self.assertIsNone(read_session_claim_bytes(store, session["owner_claim_id"]))
            self.assertTrue(store.validate_state()["ok"])

    def test_checkpoint_accepts_session_token_from_stdin(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            session = store.open_session("alice")
            args = make_args(
                goal="Ship",
                summary="Updated through stdin capability.",
                next_step="Continue.",
                constraint=[],
                actor="alice",
                session_token="-",
            )
            stream = io.StringIO()
            with mock.patch("sys.stdin", io.StringIO(f"{session['session_token']}\n")):
                with redirect_stdout(stream):
                    exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("checkpoint_updated", output)
            self.assertEqual(store.load_state()["checkpoint"]["summary"], "Updated through stdin capability.")

    def test_import_context_blocks_replayed_session_token_from_different_owner_binding(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, tracked = seed_valid_runtime(root)
            extra = root / "extra.txt"
            extra.write_text("extra", encoding="utf-8")
            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-a"):
                session = store.open_session("alice")
            stream = io.StringIO()

            with mock.patch.object(StateStore, "_current_session_owner_binding", return_value="terminal-b"):
                with mock.patch("builtins.input", return_value="y"):
                    with redirect_stdout(stream):
                        exit_code = run_import_context(
                            root,
                            make_args(files=["tracked.txt", "extra.txt"], session_token=session["session_token"]),
                        )

            output = stream.getvalue()
            snapshot = store.read_snapshot()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_owner_binding_mismatch", output)
            self.assertEqual([item.path for item in snapshot.sources], ["tracked.txt"])
            self.assertTrue((root / ".cerebro" / "session.local.json").exists())

    def test_checkpoint_blocks_forged_session_without_external_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            session = store.open_session("bob")
            store._remove_session_claim(session["owner_claim_id"])
            args = make_args(
                goal="Hijacked",
                summary="Forged session should fail.",
                next_step="Stop.",
                constraint=[],
                actor="bob",
                session_token=session["session_token"],
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("session_claim_missing", output)

    def test_checkpoint_command_removes_session_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            session = store.open_session("alice")

            args = make_args(
                goal="Ship",
                summary="Checkpoint updated.",
                next_step="Run tests.",
                constraint=["Keep behavior stable"],
                actor="alice",
                session_token=session["session_token"],
            )
            exit_code = run_checkpoint(root, args)

            self.assertEqual(exit_code, 0)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())
            state = store.load_state()
            self.assertEqual(state["checkpoint"]["goal"], "Ship")
            self.assertEqual(state["revision"], 2)

    def test_checkpoint_command_reports_operation_failed_without_mutating_state_when_session_close_fails(self) -> None:
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
                run_init(root, None)
                store, _ = seed_valid_runtime(root)
                session = store.open_session("alice")
                before = store.load_state()
                before_session = store.session_path.read_text(encoding="utf-8")
                claim = read_session_claim(store, session["owner_claim_id"])
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(
                    goal="Ship",
                    summary="Checkpoint updated.",
                    next_step="Run tests.",
                    constraint=["Keep behavior stable"],
                    actor="alice",
                    session_token=session["session_token"],
                )
                stream = io.StringIO()
                with fail_unlink_for_path(store.session_path):
                    with redirect_stdout(stream):
                        exit_code = run_checkpoint(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to remove session file", output)
                self.assertIn("session.local.json", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["checkpoint"], before["checkpoint"])
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )

    def test_checkpoint_command_reports_operation_failed_without_mutating_state_when_session_file_read_raises_during_close(
        self,
    ) -> None:
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
                run_init(root, None)
                store, _ = seed_valid_runtime(root)
                session = store.open_session("alice")
                before = store.load_state()
                before_session = store.session_path.read_text(encoding="utf-8")
                claim = read_session_claim(store, session["owner_claim_id"])
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(
                    goal="Ship",
                    summary="Checkpoint updated.",
                    next_step="Run tests.",
                    constraint=["Keep behavior stable"],
                    actor="alice",
                    session_token=session["session_token"],
                )
                stream = io.StringIO()
                original_close_session = StateStore.close_session

                def fail_during_close_session(self):
                    with mock.patch.object(self, "_read_session_file", side_effect=RuntimeError("synthetic session read failure")):
                        return original_close_session(self)

                with mock.patch.object(StateStore, "close_session", autospec=True, side_effect=fail_during_close_session):
                    with redirect_stdout(stream):
                        exit_code = run_checkpoint(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to read session file before closing session", output)
                self.assertIn("session_unreadable", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["checkpoint"], before["checkpoint"])
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )

    def test_checkpoint_command_reports_operation_failed_without_losing_session_when_state_write_fails(self) -> None:
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
                run_init(root, None)
                store, _ = seed_valid_runtime(root)
                session = store.open_session("alice")
                before = store.load_state()
                before_session = store.session_path.read_text(encoding="utf-8")
                claim = read_session_claim(store, session["owner_claim_id"])
                before_claim = read_session_claim_bytes(store, session["owner_claim_id"])
                before_live_proof = read_session_live_proof_bytes(store, claim["live_proof_id"])
                self.assertIsNotNone(before_claim)
                self.assertIsNotNone(before_live_proof)

                args = make_args(
                    goal="Ship",
                    summary="Checkpoint updated.",
                    next_step="Run tests.",
                    constraint=["Keep behavior stable"],
                    actor="alice",
                    session_token=session["session_token"],
                )
                stream = io.StringIO()
                with fail_state_replace_for_payload(store.state_path, marker='"summary": "Checkpoint updated."'):
                    with redirect_stdout(stream):
                        exit_code = run_checkpoint(root, args)

                output = stream.getvalue()
                after = store.load_state()
                self.assertEqual(exit_code, 1)
                self.assertIn("operation_failed", output)
                self.assertIn("failed to write file", output)
                self.assertIn("state.json", output)
                self.assertNotIn("internal_error", output)
                self.assertEqual(after["revision"], before["revision"])
                self.assertEqual(after["checkpoint"], before["checkpoint"])
                self.assertTrue(store.session_path.exists())
                self.assertEqual(store.session_path.read_text(encoding="utf-8"), before_session)
                self.assertEqual(read_session_claim_bytes(store, session["owner_claim_id"]), before_claim)
                self.assertEqual(read_session_live_proof_bytes(store, claim["live_proof_id"]), before_live_proof)
                self.assertEqual(after["agent_runtime"]["audit"]["active_session_id"], before["agent_runtime"]["audit"]["active_session_id"])
                self.assertEqual(
                    after["agent_runtime"]["audit"]["active_session_claim_id"],
                    before["agent_runtime"]["audit"]["active_session_claim_id"],
                )

    def test_checkpoint_command_blocks_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Before",
                    "summary": "Stable.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            store.open_session("alice")
            tracked.write_text("changed", encoding="utf-8")

            args = type(
                "Args",
                (),
                {
                    "goal": "After",
                    "summary": "Should block.",
                    "next_step": "Do not save.",
                    "constraint": [],
                    "actor": "alice",
                },
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            state = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("checkpoint_blocked", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertEqual(state["checkpoint"]["goal"], "Before")
            self.assertTrue((root / ".cerebro" / "session.local.json").exists())

    def test_checkpoint_command_blocks_without_active_session_after_seed_checkpoint(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_valid_runtime(root)
            store.update_checkpoint(
                {
                    "goal": "Before",
                    "summary": "Seed checkpoint.",
                    "next_step": "Open analyze next time.",
                    "constraints": [],
                }
            )
            before = store.load_state()

            args = type(
                "Args",
                (),
                {
                    "goal": "After",
                    "summary": "Should block.",
                    "next_step": "Do not save.",
                    "constraint": [],
                    "actor": "alice",
                },
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_checkpoint(root, args)

            output = stream.getvalue()
            after = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("checkpoint_requires_active_session", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["checkpoint"], before["checkpoint"])


if __name__ == "__main__":
    unittest.main()
