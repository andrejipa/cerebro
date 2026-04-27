from __future__ import annotations

import io
import os
import signal
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cli.commands.init import run_init
from cli.commands.verify import run_verify
from core.digests import sha256_text
from core.state_store import StateStore, StateStoreError
from core.verification_runtime import (
    MAX_VERIFY_ARTIFACT_TEXT_BYTES,
    VERIFY_ARTIFACT_TRUNCATION_MARKER,
    VerificationRuntimeError,
    build_verification_artifact_retention_report,
    execute_verification_cycle,
    run_verification_commands,
    _run_verify_subprocess,
    _terminate_verify_process_boundary,
)


class VerificationRuntimeTests(unittest.TestCase):
    def _store_with_verify_command(
        self,
        root: Path,
        argv: list[str],
        *,
        command_id: str = "cmd-001",
        timeout_ms: int = 120000,
    ) -> StateStore:
        tracked = root / "tracked.txt"
        tracked.write_text("hello", encoding="utf-8")
        run_init(root, None)
        store = StateStore(root)
        store.register_sources(["tracked.txt"])
        validation = store.validate_state()
        store.update_agent_plan(
            {
                "goal": "Run verification command",
                "summary": "Run one verification command.",
                "tasks": [
                    {
                        "id": "task-001",
                        "title": "Run verify",
                        "status": "ready",
                        "details": "Run verify",
                        "depends_on": [],
                        "working_set": ["tracked.txt"],
                        "acceptance_criteria": ["verify records command evidence"],
                        "action_ids": [],
                    }
                ],
                "command_registry": [
                    {
                        "id": command_id,
                        "argv": argv,
                        "cwd": ".",
                        "timeout_ms": timeout_ms,
                        "determinism": "high",
                        "side_effect": "read_only",
                        "risk": "low",
                        "allow_in_verify": True,
                    }
                ],
                "required_command_ids": [command_id],
                "autonomy_level": "A2",
                "protected_paths": [".cerebro/**", ".git/**"],
                "blocked_command_prefixes": ["rm"],
                "approval_required_kinds": ["fs.write_patch"],
            },
            validated_revision=validation["revision"],
        )
        return store

    def test_run_verify_rejects_command_cwd_that_resolves_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Reject escaped verify cwd",
                    "summary": "verify must fail closed when a command cwd escapes the project root.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["escaped cwd is rejected before subprocess spawn"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": "../escape",
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

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output.getvalue())
            self.assertIn("command cwd resolves outside root: ../escape", output.getvalue())
            self.assertEqual(store.read_agent_runtime()["verification"]["status"], "idle")

    def test_run_verify_allows_full_command_check_budget_without_synthetic_gate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            command_registry = []
            required_command_ids = []
            for index in range(32):
                command_id = f"cmd-{index:03d}"
                command_registry.append(
                    {
                        "id": command_id,
                        "argv": ["python", "-c", "print('ok')"],
                        "cwd": ".",
                        "timeout_ms": 120000,
                        "determinism": "high",
                        "side_effect": "read_only",
                        "risk": "low",
                        "allow_in_verify": True,
                    }
                )
                required_command_ids.append(command_id)
            store.update_agent_plan(
                {
                    "goal": "Verify check ceiling",
                    "summary": "verify must allow the full command budget when checks are command-only",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify accepts 32 command checks without synthetic overflow"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": command_registry,
                    "required_command_ids": required_command_ids,
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 0)
            rendered = output.getvalue()
            self.assertIn("verification_passed", rendered)
            self.assertIn("checks: 32", rendered)
            self.assertNotIn("invalid_agent_verification_checks", rendered)
            self.assertEqual(store.read_agent_runtime()["verification"]["status"], "passed")

    def test_run_verify_uses_core_transaction_without_read_agent_runtime_reload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify core transaction",
                    "summary": "verify should not reload runtime through the CLI boundary",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
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

            output = io.StringIO()
            with patch.object(StateStore, "read_agent_runtime", side_effect=AssertionError("unexpected runtime reload")):
                with redirect_stdout(output):
                    exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 0)
            self.assertIn("verification_passed", output.getvalue())

    def test_verify_policy_deny_is_typed_as_verification_runtime_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify policy denial",
                    "summary": "A1 must fail through the typed verify boundary.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["policy denial is typed"],
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
                    "autonomy_level": "A1",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            with self.assertRaises(VerificationRuntimeError) as ctx:
                run_verification_commands(root, store, store.read_agent_runtime())

            self.assertIn("verification command cmd-001 is blocked by execution policy", str(ctx.exception))
            self.assertIn("autonomy level A1 does not allow command execution", str(ctx.exception))

    def test_verify_blocks_path_qualified_blocked_command_prefix(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify blocked path-qualified shell",
                    "summary": "verify must normalize blocked command prefixes before subprocess spawn",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["path-qualified blocked shell is rejected"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [r"C:\Windows\System32\WindowsPowerShell\v1.0\powershell.exe", "-c", "echo ok"],
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
                    "blocked_command_prefixes": ["powershell"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            with self.assertRaises(VerificationRuntimeError) as ctx:
                run_verification_commands(root, store, store.read_agent_runtime())

            self.assertIn("verification command cmd-001 is blocked by execution policy", str(ctx.exception))
            self.assertIn("command prefix is blocked by execution policy: powershell", str(ctx.exception))

    def test_verify_artifact_write_failure_records_failed_verification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify artifact persistence failure",
                    "summary": "Artifact write failures must stay canonical in verify.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify artifact persistence failure is recorded canonically"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                "import sys; print('stdout ok'); sys.stderr.write('stderr ok\\n')",
                            ],
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

            original_write_text = Path.write_text

            def flaky_write_text(path: Path, text: str, *args, **kwargs) -> int:
                if (
                    path.name == "cmd-001.stderr.txt"
                    and path.parent.parent.name == "verification"
                ):
                    raise OSError("forced verification artifact write failure")
                return original_write_text(path, text, *args, **kwargs)

            output = io.StringIO()
            with patch("pathlib.Path.write_text", new=flaky_write_text):
                with redirect_stdout(output):
                    exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output.getvalue())
            self.assertIn("failed to persist verification artifacts", output.getvalue())
            self.assertNotIn("internal_error", output.getvalue())

            verification = store.read_agent_runtime()["verification"]
            self.assertEqual(verification["status"], "failed")
            self.assertEqual(verification["state_check"]["status"], "passed")
            self.assertEqual(len(verification["checks"]), 1)
            command_check = verification["checks"][0]
            self.assertEqual(command_check["command_id"], "cmd-001")
            self.assertEqual(command_check["status"], "failed")
            self.assertEqual(command_check["artifact_ref"], "")
            self.assertEqual(command_check["artifact_sha256"], "")
            self.assertEqual(command_check["exit_code"], 0)
            self.assertIn("failed to persist verification artifacts", command_check["message"])

            recent_events = store.read_recent_events(limit=8)
            matching = [event for event in recent_events if event.get("event") == "verify_failed" and event.get("command_id") == "cmd-001"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["reason_code"], "command_artifact_persistence_exception")

    def test_verify_artifacts_are_bounded_for_large_stdout_and_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._store_with_verify_command(
                root,
                [
                    "python",
                    "-c",
                    "import sys; sys.stdout.write('x' * 70000); sys.stderr.write('y' * 70000)",
                ],
            )

            verification = run_verification_commands(root, store, store.read_agent_runtime())

            self.assertEqual(verification["status"], "passed")
            check = verification["checks"][0]
            stdout_text = (store.cerebro_dir / check["artifact_ref"]).read_text(encoding="utf-8")
            stderr_text = (store.cerebro_dir / check["artifact_ref"].replace(".stdout.txt", ".stderr.txt")).read_text(
                encoding="utf-8"
            )
            self.assertLessEqual(len(stdout_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)
            self.assertLessEqual(len(stderr_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)
            self.assertTrue(stdout_text.endswith(VERIFY_ARTIFACT_TRUNCATION_MARKER))
            self.assertTrue(stderr_text.endswith(VERIFY_ARTIFACT_TRUNCATION_MARKER))
            self.assertEqual(check["artifact_sha256"], sha256_text(stdout_text))

    def test_verify_artifacts_preserve_small_stdout_and_stderr(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._store_with_verify_command(
                root,
                ["python", "-c", "import sys; print('stdout ok'); sys.stderr.write('stderr ok\\n')"],
            )

            verification = run_verification_commands(root, store, store.read_agent_runtime())

            self.assertEqual(verification["status"], "passed")
            check = verification["checks"][0]
            stdout_text = (store.cerebro_dir / check["artifact_ref"]).read_text(encoding="utf-8")
            stderr_text = (store.cerebro_dir / check["artifact_ref"].replace(".stdout.txt", ".stderr.txt")).read_text(
                encoding="utf-8"
            )
            self.assertEqual(stdout_text, "stdout ok\n")
            self.assertEqual(stderr_text, "stderr ok\n")
            self.assertNotIn(VERIFY_ARTIFACT_TRUNCATION_MARKER, stdout_text)
            self.assertNotIn(VERIFY_ARTIFACT_TRUNCATION_MARKER, stderr_text)
            self.assertEqual(check["artifact_sha256"], sha256_text(stdout_text))

    def test_verify_failed_command_with_large_output_remains_failed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._store_with_verify_command(
                root,
                [
                    "python",
                    "-c",
                    "import sys; sys.stdout.write('x' * 70000); sys.stderr.write('y' * 70000); raise SystemExit(7)",
                ],
            )

            verification = run_verification_commands(root, store, store.read_agent_runtime())

            self.assertEqual(verification["status"], "failed")
            check = verification["checks"][0]
            self.assertEqual(check["status"], "failed")
            self.assertEqual(check["exit_code"], 7)
            self.assertIn("command exited with non-zero status", check["message"])
            stdout_text = (store.cerebro_dir / check["artifact_ref"]).read_text(encoding="utf-8")
            stderr_text = (store.cerebro_dir / check["artifact_ref"].replace(".stdout.txt", ".stderr.txt")).read_text(
                encoding="utf-8"
            )
            self.assertLessEqual(len(stdout_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)
            self.assertLessEqual(len(stderr_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)
            self.assertTrue(stdout_text.endswith(VERIFY_ARTIFACT_TRUNCATION_MARKER))
            self.assertTrue(stderr_text.endswith(VERIFY_ARTIFACT_TRUNCATION_MARKER))

    def test_verify_timeout_records_failed_check_with_bounded_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = self._store_with_verify_command(
                root,
                [
                    "python",
                    "-c",
                    "import sys, time; print('before timeout'); sys.stdout.flush(); time.sleep(2)",
                ],
                timeout_ms=100,
            )

            verification = run_verification_commands(root, store, store.read_agent_runtime())

            self.assertEqual(verification["status"], "failed")
            check = verification["checks"][0]
            self.assertEqual(check["status"], "failed")
            self.assertIn("command timed out", check["message"])
            stdout_text = (store.cerebro_dir / check["artifact_ref"]).read_text(encoding="utf-8")
            stderr_text = (store.cerebro_dir / check["artifact_ref"].replace(".stdout.txt", ".stderr.txt")).read_text(
                encoding="utf-8"
            )
            self.assertLessEqual(len(stdout_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)
            self.assertLessEqual(len(stderr_text.encode("utf-8")), MAX_VERIFY_ARTIFACT_TEXT_BYTES)

    def test_run_verify_subprocess_preserves_success_output(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            result = _run_verify_subprocess(
                ["python", "-c", "import sys; print('ok'); sys.stderr.write('warn\\n')"],
                cwd=Path(tmp_dir),
                timeout_seconds=5,
                env={},
            )

            self.assertFalse(result.timed_out)
            self.assertEqual(result.returncode, 0)
            self.assertEqual(result.stdout, "ok\n")
            self.assertEqual(result.stderr, "warn\n")

    def test_windows_timeout_uses_taskkill_boundary(self) -> None:
        class FakeProcess:
            pid = 1234

            def __init__(self) -> None:
                self.killed = False

            def poll(self):
                return None

            def kill(self) -> None:
                self.killed = True

        process = FakeProcess()

        with patch("core.verification_runtime.os.name", "nt"):
            with patch("core.verification_runtime.subprocess.run") as run_mock:
                messages = _terminate_verify_process_boundary(process)  # type: ignore[arg-type]

        self.assertEqual(messages, ())
        run_mock.assert_called_once()
        self.assertEqual(run_mock.call_args.args[0], ["taskkill", "/T", "/F", "/PID", "1234"])
        self.assertTrue(process.killed)

    def test_posix_timeout_uses_process_group_boundary(self) -> None:
        class FakeProcess:
            pid = 1234

            def poll(self):
                return None

        with patch("core.verification_runtime.os.name", "posix"):
            with patch("core.verification_runtime.os.killpg", create=True) as killpg_mock:
                messages = _terminate_verify_process_boundary(FakeProcess())  # type: ignore[arg-type]

        self.assertEqual(messages, ())
        killpg_mock.assert_called_once_with(1234, getattr(signal, "SIGKILL", signal.SIGTERM))

    def test_process_boundary_termination_failure_is_visible(self) -> None:
        class FakeProcess:
            pid = 1234

            def poll(self):
                return None

            def kill(self) -> None:
                raise OSError("still alive")

        with patch("core.verification_runtime.os.name", "posix"):
            with patch("core.verification_runtime.os.killpg", side_effect=OSError("denied"), create=True):
                messages = _terminate_verify_process_boundary(FakeProcess())  # type: ignore[arg-type]

        rendered = "; ".join(messages)
        self.assertIn("process group termination failed", rendered)
        self.assertIn("process termination failed", rendered)

    def test_verification_artifact_retention_report_classifies_without_mutating(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            verification_root = store.artifacts_dir / "verification"
            verification_root.mkdir(parents=True, exist_ok=True)
            timestamps = {
                "verify-live": 1_700_000_003,
                "verify-recent": 1_700_000_002,
                "verify-old": 1_700_000_001,
            }
            for run_id in ("verify-live", "verify-recent", "verify-old"):
                run_dir = verification_root / run_id
                run_dir.mkdir()
                artifact = run_dir / "cmd-001.stdout.txt"
                artifact.write_text(f"run {run_id}", encoding="utf-8")
                (run_dir / "cmd-001.stderr.txt").write_text("", encoding="utf-8")
                timestamp = timestamps[run_id]
                os.utime(run_dir, (timestamp, timestamp))
            ambiguous = verification_root / "loose.txt"
            ambiguous.write_text("not a run dir", encoding="utf-8")
            before = {path.relative_to(verification_root).as_posix(): path.read_bytes() for path in verification_root.rglob("*") if path.is_file()}

            report = build_verification_artifact_retention_report(
                verification_root,
                {
                    "verification": {
                        "checks": [
                            {
                                "artifact_ref": "artifacts/verification/verify-live/cmd-001.stdout.txt",
                                "artifact_sha256": "abc",
                            }
                        ]
                    }
                },
                retained_recent_limit=1,
            )

            classifications = {entry.run_id: entry.classification for entry in report.entries}
            self.assertEqual(report.status, "ok")
            self.assertEqual(classifications["verify-live"], "live_referenced")
            self.assertEqual(classifications["verify-recent"], "recent_unreferenced")
            self.assertEqual(classifications["verify-old"], "cleanup_eligible")
            self.assertEqual(classifications["loose.txt"], "ambiguous_do_not_touch")
            self.assertEqual(report.live_referenced_count, 1)
            self.assertEqual(report.recent_unreferenced_count, 1)
            self.assertEqual(report.cleanup_eligible_count, 1)
            self.assertEqual(report.ambiguous_count, 1)
            self.assertGreater(report.cleanup_eligible_bytes, 0)
            self.assertEqual(report.state_change, "none")
            after = {path.relative_to(verification_root).as_posix(): path.read_bytes() for path in verification_root.rglob("*") if path.is_file()}
            self.assertEqual(after, before)

    def test_verification_artifact_retention_report_missing_root_is_empty(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            verification_root = Path(tmp_dir) / "missing-verification-root"

            report = build_verification_artifact_retention_report(verification_root, {"verification": {}})

            self.assertEqual(report.status, "missing_artifact_root")
            self.assertEqual(report.total_entries, 0)
            self.assertEqual(report.cleanup_eligible_count, 0)
            self.assertEqual(report.cleanup_eligible_bytes, 0)

    def test_verification_artifact_retention_report_invalid_root_is_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            verification_root = Path(tmp_dir) / "verification"
            verification_root.write_text("not a directory", encoding="utf-8")
            before = verification_root.read_text(encoding="utf-8")

            report = build_verification_artifact_retention_report(verification_root, {"verification": {}})

            self.assertEqual(report.status, "invalid_artifact_root")
            self.assertEqual(report.total_entries, 1)
            self.assertEqual(report.cleanup_eligible_count, 0)
            self.assertEqual(report.cleanup_eligible_bytes, 0)
            self.assertEqual(report.ambiguous_count, 1)
            self.assertEqual(report.entries[0].classification, "ambiguous_do_not_touch")
            self.assertIn("not a readable directory", report.entries[0].reason)
            self.assertEqual(verification_root.read_text(encoding="utf-8"), before)

    def test_verification_artifact_retention_report_rejects_negative_recent_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(VerificationRuntimeError):
                build_verification_artifact_retention_report(Path(tmp_dir), {}, retained_recent_limit=-1)

    def test_verification_artifact_retention_report_marks_racy_entries_ambiguous(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            verification_root = Path(tmp_dir) / "verification"
            verification_root.mkdir()
            stable = verification_root / "verify-stable"
            stable.mkdir()
            (stable / "cmd-001.stdout.txt").write_text("ok", encoding="utf-8")
            vanished = verification_root / "verify-vanished"
            vanished.mkdir()
            (vanished / "cmd-001.stdout.txt").write_text("gone", encoding="utf-8")
            original_stat = Path.stat

            def racy_stat(path: Path, *args, **kwargs):
                if path.name == "verify-vanished":
                    raise FileNotFoundError(path)
                return original_stat(path, *args, **kwargs)

            with patch.object(Path, "stat", racy_stat):
                report = build_verification_artifact_retention_report(
                    verification_root,
                    {"verification": {}},
                    retained_recent_limit=0,
                )

            classifications = {entry.run_id: entry.classification for entry in report.entries}
            reasons = {entry.run_id: entry.reason for entry in report.entries}
            self.assertEqual(report.status, "ok")
            self.assertEqual(classifications["verify-stable"], "cleanup_eligible")
            self.assertEqual(classifications["verify-vanished"], "ambiguous_do_not_touch")
            self.assertIn("metadata could not be read", reasons["verify-vanished"])
            self.assertEqual(report.ambiguous_count, 1)

    def test_execute_verification_cycle_returns_without_commands_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Blocked verify",
                    "summary": "validation failure must short-circuit verify before commands run",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify blocks before command execution"],
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
            runtime_before = store.read_agent_runtime()
            tracked.unlink()

            with patch(
                "core.verification_runtime.run_verification_commands",
                side_effect=AssertionError("commands must not run after validation failure"),
            ):
                result, verification_record, updated = execute_verification_cycle(root, store)

            self.assertFalse(result["ok"])
            self.assertIsNone(verification_record)
            self.assertIsNone(updated)
            self.assertEqual(store.read_agent_runtime(), runtime_before)

    def test_execute_verification_cycle_rejects_store_root_mismatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)

            with tempfile.TemporaryDirectory() as other_tmp:
                other_root = Path(other_tmp)
                with self.assertRaises(StateStoreError) as ctx:
                    execute_verification_cycle(other_root, store)

            self.assertIn("verification cycle root must match state store root", str(ctx.exception))

    def test_run_verify_requires_session_token_before_running_commands(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            session = store.open_session("alice", validated_revision=validation["revision"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify session ownership",
                    "summary": "verify must fail before running commands when session token is absent",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify blocks before command execution without a token"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('should-not-run')"],
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
                expected_session_token=session["session_token"],
            )

            output = io.StringIO()
            with patch(
                "core.verification_runtime.run_verification_commands",
                side_effect=AssertionError("commands must not run without a valid session token"),
            ):
                with redirect_stdout(output):
                    exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 1)
            self.assertIn("session_token_required", output.getvalue())
            self.assertEqual(store.read_agent_runtime()["verification"]["status"], "idle")

    def test_run_verify_records_failed_verification_when_sandbox_prepare_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify sandbox preparation failure",
                    "summary": "verify must stay canonical when sandbox bootstrap fails",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["sandbox failure is recorded canonically"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('should-not-run')"],
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

            output = io.StringIO()
            with patch(
                "core.verification_runtime.prepare_project_sandbox",
                side_effect=OSError("forced sandbox failure"),
            ):
                with redirect_stdout(output):
                    exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output.getvalue())
            self.assertIn("failed to prepare verification sandbox", output.getvalue())

            verification = store.read_agent_runtime()["verification"]
            self.assertEqual(verification["status"], "failed")
            self.assertEqual(len(verification["checks"]), 0)
            self.assertEqual(verification["state_check"]["status"], "failed")
            self.assertEqual(verification["state_check"]["exit_code"], 1)
            self.assertIn("failed to prepare verification sandbox", verification["state_check"]["message"])

            recent_events = store.read_recent_events(limit=8)
            matching = [event for event in recent_events if event.get("event") == "verify_failed" and event.get("reason_code") == "sandbox_prepare_failed"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["command_id"], "state")


if __name__ == "__main__":
    unittest.main()
