from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.commands.doctor as doctor_module
from cli.commands.init import run_init
from core.state_store import StateStore, StateStoreError, StateValidationError


class DoctorCommandTests(unittest.TestCase):
    def _seed_repo_docs(self, repo_root: Path) -> None:
        operations_dir = repo_root / "docs" / "operations"
        operations_dir.mkdir(parents=True, exist_ok=True)
        (operations_dir / "WEAKNESS_REPORT.md").write_text(
            "\n".join(
                [
                    "### CRÍTICO",
                    "- Nenhum item `CRÍTICO` aberto.",
                    "",
                    "### ALTO",
                    "- item alfa",
                    "  Status atual: Grupo 6",
                ]
            ),
            encoding="utf-8",
        )
        (operations_dir / "FREEZE_POLICY.md").write_text(
            "This freeze applies to growth, not to corrective maintenance.\n",
            encoding="utf-8",
        )

    def test_run_doctor_reports_initialized_project_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)
            run_init(project_root)
            store = StateStore(project_root)
            before_bytes = store.state_path.read_bytes()

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with mock.patch.object(
                    doctor_module,
                    "_suite_check",
                    return_value={
                        "name": "suite",
                        "status": doctor_module.STATUS_HEALTHY,
                        "message": "Ran 617 tests in 1.000s; OK (skipped=6)",
                    },
                ):
                    with redirect_stdout(stream):
                        exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("DOCTOR", output)
            self.assertIn("mode: read-only", output)
            self.assertIn("- python: SAUDAVEL", output)
            self.assertIn("- suite: SAUDAVEL", output)
            self.assertIn("- state: SAUDAVEL", output)
            self.assertIn("- session: ATENCAO - no active local session", output)
            self.assertIn("- weakness_report: ATENCAO - CRITICO abertos: 0; ALTO abertos: 1", output)
            self.assertIn("- freeze: SAUDAVEL", output)
            self.assertEqual(store.state_path.read_bytes(), before_bytes)
            self.assertFalse(store.session_path.exists())

    def test_run_doctor_reports_missing_state_without_creating_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with mock.patch.object(
                    doctor_module,
                    "_suite_check",
                    return_value={
                        "name": "suite",
                        "status": doctor_module.STATUS_HEALTHY,
                        "message": "Ran 617 tests in 1.000s; OK (skipped=6)",
                    },
                ):
                    with redirect_stdout(stream):
                        exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("- state: ATENCAO - runtime state not initialized", output)
            self.assertIn("- session: ATENCAO - no active local session", output)
            self.assertFalse((project_root / ".cerebro").exists())

    def test_run_doctor_returns_non_zero_when_a_critical_check_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with mock.patch.object(
                    doctor_module,
                    "_suite_check",
                    return_value={
                        "name": "suite",
                        "status": doctor_module.STATUS_CRITICAL,
                        "message": "Ran 617 tests in 1.000s; FAILED (failures=1)",
                    },
                ):
                    with redirect_stdout(stream):
                        exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("- suite: CRITICO - Ran 617 tests in 1.000s; FAILED (failures=1)", output)

    def test_run_doctor_fails_closed_when_repo_suite_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)
            run_init(project_root)

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with redirect_stdout(stream):
                    exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("- suite: CRITICO - test suite not available under", output)

    def test_run_doctor_reports_inconsistent_session_registry_without_local_sidecar(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)
            run_init(project_root)
            store = StateStore(project_root)
            state = store.load_state()
            state["agent_runtime"]["audit"]["active_session_id"] = "session-123"
            state["agent_runtime"]["audit"]["active_session_claim_id"] = "claim-123"
            store.save_state(state, expected_revision=state["revision"])
            self.assertFalse(store.session_path.exists())

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with mock.patch.object(
                    doctor_module,
                    "_suite_check",
                    return_value={
                        "name": "suite",
                        "status": doctor_module.STATUS_HEALTHY,
                        "message": "Ran 634 tests in 1.000s; OK (skipped=6)",
                    },
                ):
                    with redirect_stdout(stream):
                        exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("- session: CRITICO - session registry and local sidecar are inconsistent", output)

    def test_state_check_reports_invalid_canonical_state(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            run_init(project_root)
            store = StateStore(project_root)

            with mock.patch.object(
                StateStore,
                "read_snapshot_and_runtime",
                side_effect=StateValidationError([{"code": "state_invalid"}]),
            ):
                state_check, runtime = doctor_module._state_check(store)

            self.assertIsNone(runtime)
            self.assertEqual(state_check["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("canonical state is invalid (state_invalid)", state_check["message"])

    def test_state_check_reports_state_store_read_failure(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            run_init(project_root)
            store = StateStore(project_root)

            with mock.patch.object(
                StateStore,
                "read_snapshot_and_runtime",
                side_effect=StateStoreError("failed to read canonical state"),
            ):
                state_check, runtime = doctor_module._state_check(store)

            self.assertIsNone(runtime)
            self.assertEqual(state_check["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("failed to read canonical state", state_check["message"])

    def test_session_check_reports_sidecar_present_when_state_cannot_be_inspected(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            run_init(project_root)
            store = StateStore(project_root)
            store.session_path.write_text("{}", encoding="utf-8")

            result = doctor_module._session_check(store, None)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("local session sidecar exists but state could not be inspected", result["message"])

    def test_session_check_reports_healthy_when_registry_and_sidecar_are_present(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            run_init(project_root)
            store = StateStore(project_root)
            store.session_path.write_text("{}", encoding="utf-8")

            result = doctor_module._session_check(
                store,
                {"audit": {"active_session_id": "session-123", "active_session_claim_id": "claim-123"}},
            )

            self.assertEqual(result["status"], doctor_module.STATUS_HEALTHY)
            self.assertIn("active session registered (session-123)", result["message"])

    def test_weakness_check_warns_when_report_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()

            with mock.patch("pathlib.Path.read_text", side_effect=OSError("read failed")):
                result = doctor_module._weakness_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
            self.assertIn("unable to read weakness report", result["message"])

    def test_weakness_check_warns_when_open_items_cannot_be_classified(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_text("no structured headings here", encoding="utf-8")

            result = doctor_module._weakness_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
            self.assertIn("unable to classify open CRITICO/ALTO items", result["message"])

    def test_freeze_check_warns_when_policy_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()

            with mock.patch("pathlib.Path.read_text", side_effect=OSError("read failed")):
                result = doctor_module._freeze_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
            self.assertIn("unable to read freeze policy", result["message"])

    def test_freeze_check_warns_when_carve_out_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "FREEZE_POLICY.md").write_text("growth is frozen\n", encoding="utf-8")

            result = doctor_module._freeze_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
            self.assertIn("corrective-maintenance carve-out was not confirmed", result["message"])
