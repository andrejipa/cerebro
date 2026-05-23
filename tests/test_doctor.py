from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.commands.doctor as doctor_module
from cli.commands.init import run_init
from core.state_store import StateStore, StateStoreError, StateValidationError
from tests.runtime_fixtures import seed_registered_source


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

    def _patch_healthy_installation(self):
        return mock.patch.object(
            doctor_module,
            "_installation_check",
            return_value={
                "name": "installation",
                "status": doctor_module.STATUS_HEALTHY,
                "message": "isolated Python import and cerebro executable are available",
            },
        )

    def test_run_doctor_reports_initialized_project_without_mutating_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            self._seed_repo_docs(repo_root)
            run_init(project_root)
            store, _tracked = seed_registered_source(project_root)
            state = store.load_state()
            state["last_validation"] = {
                "validated_at": "2026-05-08T00:00:00+00:00",
                "result": "ok",
                "details": [],
            }
            store.save_state(state, expected_revision=state["revision"])
            before_bytes = store.state_path.read_bytes()

            stream = io.StringIO()
            with mock.patch.object(doctor_module, "REPO_ROOT", repo_root):
                with self._patch_healthy_installation():
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
            self.assertIn("- installation: SAUDAVEL", output)
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
                with self._patch_healthy_installation():
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
                with self._patch_healthy_installation():
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
                with self._patch_healthy_installation():
                    with redirect_stdout(stream):
                        exit_code = doctor_module.run_doctor(project_root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("- suite: CRITICO - test suite not available under", output)

    def test_suite_check_uses_base_gate_runner_with_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            (repo_root / "tests").mkdir()
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Ran 454 tests in 77.000s\n\nOK (skipped=3)\nSUMMARY profile=base ran=454 failures=0 errors=0 skipped=3\n",
                stderr="",
            )

            with mock.patch.object(doctor_module.subprocess, "run", return_value=completed) as fake_run:
                result = doctor_module._suite_check(repo_root)

            fake_run.assert_called_once_with(
                [sys.executable, "-m", "tests.gate_runner", "--profile", "base"],
                cwd=repo_root,
                capture_output=True,
                text=True,
                check=False,
                timeout=doctor_module.SUITE_TIMEOUT_SECONDS,
            )
            self.assertEqual(result["status"], doctor_module.STATUS_HEALTHY)
            self.assertIn("SUMMARY profile=base", result["message"])

    def test_suite_check_reports_base_gate_timeout(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            (repo_root / "tests").mkdir()

            with mock.patch.object(
                doctor_module.subprocess,
                "run",
                side_effect=subprocess.TimeoutExpired(cmd=["python"], timeout=doctor_module.SUITE_TIMEOUT_SECONDS),
            ):
                result = doctor_module._suite_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("base gate timed out after 240s", result["message"])

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
                with self._patch_healthy_installation():
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

    def test_installation_check_fails_when_repo_root_is_missing_packages(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()

            result = doctor_module._installation_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("repo root is missing import packages", result["message"])

    def test_installation_check_fails_when_isolated_import_is_broken(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            (repo_root / "cli").mkdir()
            (repo_root / "cli" / "main.py").write_text("", encoding="utf-8")
            (repo_root / "core").mkdir()
            (repo_root / "core" / "__init__.py").write_text("", encoding="utf-8")
            (repo_root / "extensions").mkdir()
            (repo_root / "extensions" / "__init__.py").write_text("", encoding="utf-8")

            with mock.patch.object(
                doctor_module,
                "_run_isolated_import_check",
                return_value={
                    "name": "installation",
                    "status": doctor_module.STATUS_CRITICAL,
                    "message": "isolated installed import failed: No module named 'cli'",
                },
            ):
                result = doctor_module._installation_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("isolated installed import failed", result["message"])

    def test_installation_check_warns_when_cerebro_executable_is_not_on_path(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            (repo_root / "cli").mkdir()
            (repo_root / "cli" / "main.py").write_text("", encoding="utf-8")
            (repo_root / "core").mkdir()
            (repo_root / "core" / "__init__.py").write_text("", encoding="utf-8")
            (repo_root / "extensions").mkdir()
            (repo_root / "extensions" / "__init__.py").write_text("", encoding="utf-8")

            with mock.patch.object(
                doctor_module,
                "_run_isolated_import_check",
                return_value={
                    "name": "installation",
                    "status": doctor_module.STATUS_HEALTHY,
                    "message": "isolated installed import succeeded",
                },
            ), mock.patch.object(
                doctor_module,
                "_run_cerebro_executable_check",
                return_value={
                    "name": "installation",
                    "status": doctor_module.STATUS_WARNING,
                    "message": "cerebro executable was not found on PATH",
                },
            ):
                result = doctor_module._installation_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
            self.assertIn("not found on PATH", result["message"])

    def test_isolated_import_check_fails_when_install_points_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as foreign_dir:
            repo_root = Path(repo_dir).resolve()
            foreign_root = Path(foreign_dir).resolve()
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=(
                    "{"
                    f"\"cli.main\": \"{(foreign_root / 'cli' / 'main.py').as_posix()}\", "
                    f"\"core\": \"{(foreign_root / 'core' / '__init__.py').as_posix()}\", "
                    f"\"extensions\": \"{(foreign_root / 'extensions' / '__init__.py').as_posix()}\""
                    "}"
                ),
                stderr="",
            )

            with mock.patch.object(doctor_module.subprocess, "run", return_value=completed):
                result = doctor_module._run_isolated_import_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("points outside this repo", result["message"])

    def test_isolated_import_check_rejects_json_without_required_module_keys(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout='{"cli.main": "D:/repo/cli/main.py"}\n',
                stderr="",
            )

            with mock.patch.object(doctor_module.subprocess, "run", return_value=completed):
                result = doctor_module._run_isolated_import_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("invalid output", result["message"])

    def test_isolated_import_check_reports_execution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()

            with mock.patch.object(doctor_module.subprocess, "run", side_effect=OSError("python blocked")):
                result = doctor_module._run_isolated_import_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("could not be executed", result["message"])

    def test_isolated_import_check_accepts_json_after_stdout_noise(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            for relative_path in (
                Path("cli") / "main.py",
                Path("core") / "__init__.py",
                Path("extensions") / "__init__.py",
            ):
                target = repo_root / relative_path
                target.parent.mkdir(parents=True, exist_ok=True)
                target.write_text("", encoding="utf-8")
            completed = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout=(
                    "runtime warning\n"
                    "{"
                    f"\"cli.main\": \"{(repo_root / 'cli' / 'main.py').as_posix()}\", "
                    f"\"core\": \"{(repo_root / 'core' / '__init__.py').as_posix()}\", "
                    f"\"extensions\": \"{(repo_root / 'extensions' / '__init__.py').as_posix()}\""
                    "}\n"
                ),
                stderr="",
            )

            with mock.patch.object(doctor_module.subprocess, "run", return_value=completed):
                result = doctor_module._run_isolated_import_check(repo_root)

            self.assertEqual(result["status"], doctor_module.STATUS_HEALTHY)
            self.assertIn("points at this repo", result["message"])

    def test_cerebro_executable_check_reports_stale_path_execution_failure(self) -> None:
        stale_executable = r"C:\stale\cerebro.exe"

        with mock.patch.object(doctor_module.shutil, "which", return_value=stale_executable):
            with mock.patch.object(
                doctor_module,
                "_scripts_dir_for_current_interpreter",
                return_value=Path(r"C:\stale"),
            ), mock.patch.object(doctor_module.subprocess, "run", side_effect=OSError("not runnable")):
                result = doctor_module._run_cerebro_executable_check()

        self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
        self.assertIn("could not be started from PATH", result["message"])

    def test_cerebro_executable_check_warns_when_path_points_to_other_python_environment(self) -> None:
        foreign_executable = r"C:\other-python\Scripts\cerebro.exe"

        with mock.patch.object(doctor_module.shutil, "which", return_value=foreign_executable):
            with mock.patch.object(
                doctor_module,
                "_scripts_dir_for_current_interpreter",
                return_value=Path(r"C:\current-python\Scripts"),
            ):
                result = doctor_module._run_cerebro_executable_check()

        self.assertEqual(result["status"], doctor_module.STATUS_WARNING)
        self.assertIn("different Python environment", result["message"])

    def test_cerebro_executable_check_reports_nonzero_help_exit(self) -> None:
        executable = r"C:\current-python\Scripts\cerebro.exe"
        completed = subprocess.CompletedProcess(
            args=[executable, "--help"],
            returncode=1,
            stdout="",
            stderr="broken entrypoint",
        )

        with mock.patch.object(doctor_module.shutil, "which", return_value=executable):
            with mock.patch.object(
                doctor_module,
                "_scripts_dir_for_current_interpreter",
                return_value=Path(r"C:\current-python\Scripts"),
            ), mock.patch.object(doctor_module.subprocess, "run", return_value=completed):
                result = doctor_module._run_cerebro_executable_check()

        self.assertEqual(result["status"], doctor_module.STATUS_CRITICAL)
        self.assertIn("broken entrypoint", result["message"])

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

    def test_state_check_reports_validation_failure_as_critical(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            run_init(project_root)
            store = StateStore(project_root)
            state = store.load_state()
            state["last_validation"] = {
                "validated_at": "2026-05-08T00:00:00+00:00",
                "result": "fail",
                "details": [{"code": "source_hash_mismatch", "message": "changed"}],
            }
            store.save_state(state, expected_revision=state["revision"])

            state_check, runtime = doctor_module._state_check(store)

            self.assertIsNotNone(runtime)
            self.assertEqual(state_check["status"], doctor_module.STATUS_CRITICAL)
            self.assertIn("validation fail", state_check["message"])

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
