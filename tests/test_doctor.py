from __future__ import annotations

import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.commands.doctor as doctor_module
from cli.commands.init import run_init
from core.state_store import StateStore


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
