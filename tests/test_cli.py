from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.main as cli_main_module
from cli.commands.init import run_init
from cli.commands.resume import run_resume
from cli.commands.validate import run_validate
from core.state_store import StateStore
from tests.runtime_fixtures import seed_registered_source


REPO_ROOT = Path(__file__).resolve().parents[1]


class CliHelpAndExitCodeTests(unittest.TestCase):
    def test_main_help_via_module_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.replace("\n", " ")
        self.assertIn("Deterministic context runtime.", result.stdout)
        self.assertIn("Install Cerebro once from the Cerebro repository root.", result.stdout)
        self.assertIn("Use Cerebro from the target project root.", result.stdout)
        self.assertIn("First successful run:", result.stdout)
        self.assertIn("cerebro init", result.stdout)
        self.assertIn("cerebro import-context --files ...", result.stdout)
        self.assertIn("cerebro checkpoint --goal ... --summary ... --next-step ...", result.stdout)
        self.assertIn("cerebro validate", result.stdout)
        self.assertIn("--project-root", result.stdout)
        self.assertIn("target project root", help_text)
        self.assertIn("After bootstrap, `cerebro analyze` is the standard entrypoint.", help_text)
        self.assertIn("Ignore exports and advanced commands until this succeeds once.", help_text)
        self.assertIn("analyze", result.stdout)
        self.assertIn("approve", result.stdout)
        self.assertIn("apply", result.stdout)
        self.assertIn("bootstrap-scan", result.stdout)
        self.assertIn("context-index-export", result.stdout)
        self.assertIn("import-context", result.stdout)
        self.assertIn("handoff-export", result.stdout)
        self.assertIn("impact-export", result.stdout)
        self.assertIn("plan", result.stdout)
        self.assertIn("rollback", result.stdout)
        self.assertIn("session-discard", result.stdout)
        self.assertIn("return-map-export", result.stdout)
        self.assertIn("sources-export", result.stdout)
        self.assertIn("status-export", result.stdout)
        self.assertIn("validation-export", result.stdout)
        self.assertIn("verify", result.stdout)

    def test_subcommand_help_pages(self) -> None:
        for command in (
            "analyze",
            "approve",
            "apply",
            "bootstrap-scan",
            "context-index-export",
            "init",
            "import-context",
            "checkpoint",
            "plan",
            "resume",
            "rollback",
            "session-discard",
            "handoff-export",
            "context-index-export",
            "impact-export",
            "return-map-export",
            "sources-export",
            "status-export",
            "validation-export",
            "validate",
            "verify",
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn(command, result.stdout)

    def test_cli_rejects_unapproved_human_aliases(self) -> None:
        for alias in (
            "gerente",
            "marcar",
            "conferir",
            "faxineiro",
            "memoria",
            "caminho",
            "impacto",
            "entrega",
        ):
            with self.subTest(alias=alias):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", alias],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid choice", result.stderr)

    def test_analyze_help_declares_standard_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "analyze", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Official runtime entrypoint", result.stdout)

    def test_resume_help_declares_compatibility_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "resume", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Compatibility command", result.stdout)

    def test_session_discard_help_declares_explicit_reopen_boundary(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "session-discard", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("stale-session", result.stdout)
        self.assertIn("does not make continuity uninterrupted again", result.stdout)

    def test_validation_export_help_declares_persisted_validation_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "validation-export", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("read-only validation view", result.stdout)

    def test_import_context_help_declares_diff_and_confirmation(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "import-context", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.replace("\n", " ")
        self.assertIn("sources diff", help_text)
        self.assertIn("requires confirmation", help_text)

    def test_plan_help_declares_domain_input_adapter_options(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "plan", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--input-text", result.stdout)
        self.assertIn("--input-file", result.stdout)
        self.assertIn("--input-kind", result.stdout)

    def test_export_help_pages_declare_read_only_derived_role(self) -> None:
        expected_fragments = {
            "handoff-export": ("Markdown handoff", "canonical", "state"),
            "context-index-export": ("read-only navigation index", "canonical", "sources", "checkpoint"),
            "impact-export": ("read-only impact view", "canonical", "state"),
            "sources-export": ("read-only inventory", "canonical", "state"),
            "return-map-export": ("read-only return map", "canonical", "checkpoint"),
            "status-export": ("read-only operational status", "canonical", "state"),
            "validation-export": ("read-only validation view", "persisted", "canonical validation record"),
        }

        for command, fragments in expected_fragments.items():
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                for fragment in fragments:
                    self.assertIn(fragment, result.stdout)

    def test_cli_usage_error_returns_exit_code_2(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "checkpoint"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_main_dispatches_current_working_directory_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["validate"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["--project-root", str(project_root), "validate"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_accepts_explicit_project_root_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["validate", "--project-root", str(project_root)])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_plan_uses_explicit_project_root_for_relative_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            run_init(project_root, None)
            store, _tracked = seed_registered_source(project_root)
            (project_root / "plan.txt").write_text("comprar arroz, leite, pao", encoding="utf-8")
            (other_root / "plan.txt").write_text("this must not be read", encoding="utf-8")

            stream = io.StringIO()
            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with redirect_stdout(stream):
                    exit_code = cli_main_module.main(
                        [
                            "--project-root",
                            str(project_root),
                            "plan",
                            "--input-file",
                            "plan.txt",
                            "--input-kind",
                            "list",
                        ]
                    )
            finally:
                os.chdir(previous_cwd)

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 0)
            self.assertEqual(runtime["plan"]["goal"], "Complete listed items")
            self.assertEqual([task["title"] for task in runtime["plan"]["tasks"]], ["comprar arroz", "leite", "pao"])

    def test_bootstrap_scan_root_argument_overrides_global_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as scan_dir:
            project_root = Path(project_dir).resolve()
            scan_root = Path(scan_dir).resolve()
            (project_root / "README.md").write_text("project readme", encoding="utf-8")
            (scan_root / "README.md").write_text("scan readme", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(
                    [
                        "--project-root",
                        str(project_root),
                        "bootstrap-scan",
                        "--root",
                        str(scan_root),
                        "--limit",
                        "1",
                    ]
                )

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn(f"scan_root: {scan_root}", output)
            self.assertIn(f'next_workdir: cd "{scan_root}"', output)
            self.assertNotIn(f"scan_root: {project_root}", output)


class CliOutputTests(unittest.TestCase):
    def test_init_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_init(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("instance_created:", output)
            self.assertIn("state_path:", output)
            self.assertIn("next_step: run `cerebro import-context --files ...`", output)

    def test_validate_ok_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_registered_source(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("validation_passed:", output)

    def test_validate_ok_output_does_not_reopen_snapshot_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_registered_source(root)
            stream = io.StringIO()

            with mock.patch("cli.commands.validate.StateStore.read_snapshot", side_effect=AssertionError("unexpected")):
                with redirect_stdout(stream):
                    exit_code = run_validate(root)

            self.assertEqual(exit_code, 0)

    def test_validate_fail_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.unlink()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("source_missing", output)

    def test_resume_blocked_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"actor": "alice"})

            with redirect_stdout(stream):
                exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("resume_blocked", output)
            self.assertIn("source_hash_mismatch", output)
