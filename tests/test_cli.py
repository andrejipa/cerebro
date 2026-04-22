from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.main as cli_main_module
import cli.project_dashboard as project_dashboard_module
import cli.project_registry as project_registry_module
import cli.commands.worktree as worktree_command_module
import cli.worktree_registry as worktree_registry_module
from cli.commands.init import run_init
from cli.commands.resume import run_resume
from cli.commands.validate import run_validate
from core.state_store import StateStore
from tests.runtime_fixtures import seed_registered_source


REPO_ROOT = Path(__file__).resolve().parents[1]


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_git_repo(root: Path) -> None:
    init_result = subprocess.run(
        ["git", "init", "-b", "main", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if init_result.returncode != 0:
        raise AssertionError(init_result.stderr or init_result.stdout)
    for command in (
        ("config", "user.email", "codex@example.com"),
        ("config", "user.name", "Codex"),
    ):
        result = _run_git(root, *command)
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
    (root / "README.md").write_text("demo\n", encoding="utf-8")
    add_result = _run_git(root, "add", "README.md")
    if add_result.returncode != 0:
        raise AssertionError(add_result.stderr or add_result.stdout)
    commit_result = _run_git(root, "commit", "-m", "init")
    if commit_result.returncode != 0:
        raise AssertionError(commit_result.stderr or commit_result.stdout)


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
        self.assertIn("doctor", result.stdout)
        self.assertIn("iteration-commit", result.stdout)
        self.assertIn("import-context", result.stdout)
        self.assertIn("handoff-export", result.stdout)
        self.assertIn("impact-export", result.stdout)
        self.assertIn("plan", result.stdout)
        self.assertIn("residuals-view", result.stdout)
        self.assertIn("rollback", result.stdout)
        self.assertIn("session-discard", result.stdout)
        self.assertIn("return-map-export", result.stdout)
        self.assertIn("sources-export", result.stdout)
        self.assertIn("status-export", result.stdout)
        self.assertIn("validation-export", result.stdout)
        self.assertIn("verify", result.stdout)
        self.assertIn("worktree", result.stdout)

    def test_subcommand_help_pages(self) -> None:
        for command in (
            "analyze",
            "approve",
            "apply",
            "bootstrap-scan",
            "context-index-export",
            "doctor",
            "iteration-commit",
            "init",
            "import-context",
            "checkpoint",
            "plan",
            "residuals-view",
            "resume",
            "rollback",
            "session-discard",
            "worktree",
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

    def test_doctor_help_declares_read_only_diagnostic_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "doctor", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("read-only diagnostic report", result.stdout)
        self.assertIn("does not open continuity", result.stdout)
        self.assertIn("does not mutate runtime state", result.stdout)

    def test_iteration_commit_help_declares_generated_commit_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "iteration-commit", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Generate an iteration commit message", result.stdout)
        self.assertIn("selected repository paths", result.stdout)

    def test_worktree_help_declares_isolated_git_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "worktree", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("isolated git worktrees", result.stdout)
        self.assertIn(".worktrees/", result.stdout)

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

    def test_export_subcommands_declare_json_format_option(self) -> None:
        for command in (
            "handoff-export",
            "context-index-export",
            "impact-export",
            "sources-export",
            "return-map-export",
            "status-export",
            "validation-export",
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 0)
                self.assertIn("--format", result.stdout)
                self.assertIn("json", result.stdout)
                self.assertIn("md", result.stdout)

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
            "residuals-view": ("read-only view", "docs/operations/residuals.toml"),
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

    def test_main_dispatches_current_working_directory_to_doctor_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_doctor(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_doctor", side_effect=fake_doctor):
                    exit_code = cli_main_module.main(["doctor"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_doctor_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_doctor(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_doctor", side_effect=fake_doctor):
                    exit_code = cli_main_module.main(["doctor", "--project-root", str(project_root)])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_dispatches_current_working_directory_to_iteration_commit_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_iteration_commit(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_iteration_commit", side_effect=fake_iteration_commit):
                    exit_code = cli_main_module.main(["iteration-commit", "--path", "docs/operations/IMPLEMENTATION_STATUS.md"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_iteration_commit_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_iteration_commit(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_iteration_commit", side_effect=fake_iteration_commit):
                    exit_code = cli_main_module.main(
                        ["iteration-commit", "--project-root", str(project_root), "--path", "docs/operations/IMPLEMENTATION_STATUS.md"]
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_dispatches_current_working_directory_to_worktree_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_worktree(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_worktree", side_effect=fake_worktree):
                    exit_code = cli_main_module.main(["worktree", "create", "demo"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_worktree_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_worktree(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_worktree", side_effect=fake_worktree):
                    exit_code = cli_main_module.main(["--project-root", str(project_root), "worktree", "create", "demo"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_without_argv_opens_context_menu_and_dispatches_development_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as fake_home:
            root = Path(tmp_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                print("ANALYZE_CALLED")
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["1"]):
                            with mock.patch.object(cli_main_module, "render_open_dashboard", return_value="DASHBOARD\nestado_projeto: state_absent"):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])
            self.assertIn("CEREBRO", output)
            self.assertIn("(1) Desenvolvimento", output)
            self.assertIn("(2) Gerenciar projeto", output)
            self.assertIn("DASHBOARD", output)
            self.assertLess(output.index("DASHBOARD"), output.index("ANALYZE_CALLED"))
            self.assertFalse((fake_home_root / ".cerebro" / "projects.toml").exists())

    def test_main_none_uses_process_argv_for_context_menu_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(sys, "argv", ["cerebro"]):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["1"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                exit_code = cli_main_module.main()
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_without_argv_opens_context_menu_and_dispatches_managed_project_mode(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                print("ANALYZE_CALLED")
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(project_root)]):
                            with mock.patch.object(cli_main_module, "render_open_dashboard", return_value="DASHBOARD\nestado_projeto: state_absent"):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])
            self.assertIn("DASHBOARD", output)
            self.assertLess(output.index("DASHBOARD"), output.index("ANALYZE_CALLED"))
            self.assertTrue(registry_path.exists())
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(registry["projects"][0]["name"], project_root.name)
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)
            self.assertTrue(registry["projects"][0]["last_used"])

    def test_main_without_argv_fails_closed_for_invalid_context_menu_selection(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch("builtins.input", side_effect=["9"]):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_invalid", output)

    def test_main_without_argv_fails_closed_when_context_menu_input_is_closed(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch("builtins.input", side_effect=EOFError()):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_input_closed", output)
        self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_for_blank_project_root(self) -> None:
        stream = io.StringIO()

        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2", "   "]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_root_missing", output)

    def test_main_without_argv_fails_closed_when_project_root_input_is_closed(self) -> None:
        stream = io.StringIO()

        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2", EOFError()]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_root_input_closed", output)
        self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_when_registry_lock_cleanup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            other_root = Path(other_dir).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            stream = io.StringIO()
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                        with mock.patch("sys.stdin.isatty", return_value=True):
                            with mock.patch("builtins.input", side_effect=["2", str(project_root)]):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_invalid", output)
            self.assertNotIn("internal_error", output)
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_main_without_argv_fails_closed_when_registered_project_selection_input_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", EOFError()]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_selection_closed", output)
            self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_when_terminal_is_unavailable(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=False):
            with mock.patch("builtins.input", side_effect=AssertionError("input should not be called")):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_unavailable", output)

    def test_main_without_argv_lists_registered_projects_and_dispatches_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as second_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            second_root = Path(second_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            registry_path = registry_dir / "projects.toml"
            registry_path.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                        "[[projects]]",
                        'name = "beta"',
                        f'path = "{_toml_escape(str(second_root))}"',
                        'last_used = "2026-04-16T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", "1"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])
            self.assertIn("Projetos registrados", output)
            self.assertEqual(registry["projects"][0]["path"], str(project_root))
            self.assertNotEqual(registry["projects"][0]["last_used"], "2026-04-17T10:00:00+00:00")

    def test_main_without_argv_fails_closed_when_project_registry_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text("not = [valid", encoding="utf-8")
            stream = io.StringIO()

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2"]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_registry_invalid", output)

    def test_main_without_argv_fails_closed_for_invalid_registered_project_selection(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", "9"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_selection_invalid", output)

    def test_main_without_argv_fails_closed_when_managed_project_root_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            missing_root = other_root / "missing-project"
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(missing_root)]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_root_not_found", output)

    def test_main_without_argv_fails_closed_when_managed_project_root_is_not_directory(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            invalid_root = other_root / "not-a-directory.txt"
            invalid_root.write_text("content", encoding="utf-8")
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(invalid_root)]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_root_invalid", output)

    def test_project_registry_serializes_concurrent_updates(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_a_dir, tempfile.TemporaryDirectory() as project_b_dir:
            fake_home_root = Path(fake_home).resolve()
            project_a = Path(project_a_dir).resolve()
            project_b = Path(project_b_dir).resolve()
            entered = threading.Event()
            release = threading.Event()
            second_done = threading.Event()
            errors: list[Exception] = []
            original_load = project_registry_module._load_projects_unlocked
            load_calls = {"count": 0}

            def blocking_load(path: Path) -> list[dict[str, str]]:
                load_calls["count"] += 1
                if load_calls["count"] == 1:
                    entered.set()
                    release.wait(timeout=5)
                return original_load(path)

            def register_project(root: Path, *, done: threading.Event | None = None) -> None:
                try:
                    project_registry_module.register_or_update_project(root)
                except Exception as exc:  # pragma: no cover - test helper
                    errors.append(exc)
                finally:
                    if done is not None:
                        done.set()

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch.object(project_registry_module, "_load_projects_unlocked", side_effect=blocking_load):
                    first = threading.Thread(target=register_project, args=(project_a,))
                    second = threading.Thread(target=register_project, args=(project_b,), kwargs={"done": second_done})
                    first.start()
                    self.assertTrue(entered.wait(timeout=5))
                    second.start()
                    self.assertFalse(second_done.wait(timeout=0.2))
                    release.set()
                    first.join(timeout=5)
                    second.join(timeout=5)

            registry = tomllib.loads((fake_home_root / ".cerebro" / "projects.toml").read_text(encoding="utf-8"))
            paths = {Path(item["path"]) for item in registry["projects"]}
            self.assertEqual(errors, [])
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(paths, {project_a, project_b})

    def test_project_registry_register_or_update_project_rejects_missing_root_outside_menu(self) -> None:
        with (
            tempfile.TemporaryDirectory() as fake_home,
            tempfile.TemporaryDirectory() as existing_project_dir,
            tempfile.TemporaryDirectory() as missing_parent_dir,
        ):
            fake_home_root = Path(fake_home).resolve()
            existing_project = Path(existing_project_dir).resolve()
            missing_root = (Path(missing_parent_dir).resolve() / "missing-project").resolve()
            registry_file = fake_home_root / ".cerebro" / "projects.toml"
            registry_file.parent.mkdir(parents=True, exist_ok=True)
            registry_file.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "existing"',
                        f'path = "{_toml_escape(str(existing_project))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            before = registry_file.read_text(encoding="utf-8")

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "project root is invalid"):
                    project_registry_module.register_or_update_project(missing_root)

            self.assertEqual(registry_file.read_text(encoding="utf-8"), before)

    def test_project_registry_save_projects_rejects_missing_root_outside_menu(self) -> None:
        with (
            tempfile.TemporaryDirectory() as fake_home,
            tempfile.TemporaryDirectory() as existing_project_dir,
            tempfile.TemporaryDirectory() as missing_parent_dir,
        ):
            fake_home_root = Path(fake_home).resolve()
            existing_project = Path(existing_project_dir).resolve()
            missing_root = (Path(missing_parent_dir).resolve() / "missing-project").resolve()
            registry_file = fake_home_root / ".cerebro" / "projects.toml"
            registry_file.parent.mkdir(parents=True, exist_ok=True)
            registry_file.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "existing"',
                        f'path = "{_toml_escape(str(existing_project))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            before = registry_file.read_text(encoding="utf-8")

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "project root is invalid"):
                    project_registry_module.save_projects(
                        [
                            {
                                "name": "existing",
                                "path": str(existing_project),
                                "last_used": "2026-04-17T10:00:00+00:00",
                            },
                            {
                                "name": "missing",
                                "path": str(missing_root),
                                "last_used": "2026-04-17T11:00:00+00:00",
                            },
                        ]
                    )

            self.assertEqual(registry_file.read_text(encoding="utf-8"), before)

    def test_project_registry_register_or_update_project_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "failed to release project registry lock"):
                        project_registry_module.register_or_update_project(project_root)

            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_project_registry_save_projects_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "failed to release project registry lock"):
                        project_registry_module.save_projects(
                            [
                                {
                                    "name": "alpha",
                                    "path": str(project_root),
                                    "last_used": "2026-04-17T10:00:00+00:00",
                                }
                            ]
                        )

            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_project_registry_register_or_update_project_reports_write_and_lock_release_failure(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with mock.patch.object(
                        project_registry_module,
                        "_save_projects_unlocked",
                        side_effect=project_registry_module.ProjectRegistryError(
                            f"failed to write project registry: {registry_path}"
                        ),
                    ):
                        with self.assertRaisesRegex(
                            project_registry_module.ProjectRegistryError,
                            "failed to write project registry: .*failed to release project registry lock",
                        ):
                            project_registry_module.register_or_update_project(project_root)

            self.assertTrue(registry_path.with_suffix(".toml.lock").exists())

    def test_project_registry_save_projects_reports_write_and_lock_release_failure(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with mock.patch.object(
                        project_registry_module,
                        "_save_projects_unlocked",
                        side_effect=project_registry_module.ProjectRegistryError(
                            f"failed to write project registry: {registry_path}"
                        ),
                    ):
                        with self.assertRaisesRegex(
                            project_registry_module.ProjectRegistryError,
                            "failed to write project registry: .*failed to release project registry lock",
                        ):
                            project_registry_module.save_projects(
                                [
                                    {
                                        "name": "alpha",
                                        "path": str(project_root),
                                        "last_used": "2026-04-17T10:00:00+00:00",
                                    }
                                ]
                            )

            self.assertTrue(registry_path.with_suffix(".toml.lock").exists())

    def test_explicit_analyze_does_not_render_open_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "render_open_dashboard", side_effect=AssertionError("dashboard should not render")):
                    with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                        exit_code = cli_main_module.main(["analyze"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_explicit_doctor_does_not_dispatch_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with mock.patch.object(cli_main_module, "run_doctor", return_value=0) as fake_doctor:
                        exit_code = cli_main_module.main(["doctor"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            fake_doctor.assert_called_once()

    def test_worktree_create_creates_git_worktree_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("worktree: demo", output)
            self.assertTrue((repo_root / ".worktrees" / "demo").exists())

            registry = tomllib.loads((repo_root / ".cerebro" / "worktrees.toml").read_text(encoding="utf-8"))
            self.assertEqual(len(registry["worktrees"]), 1)
            self.assertEqual(registry["worktrees"][0]["name"], "demo")
            self.assertEqual(registry["worktrees"][0]["branch"], "worktree-demo")
            self.assertEqual(Path(registry["worktrees"][0]["path"]), repo_root / ".worktrees" / "demo")

            branch_result = _run_git(repo_root, "branch", "--list", "worktree-demo")
            self.assertEqual(branch_result.returncode, 0)
            self.assertIn("worktree-demo", branch_result.stdout)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_create_rejects_invalid_name(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            invalid_name = str((repo_root / "escape").resolve())
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", invalid_name])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("invalid_worktree_name", output)
            self.assertFalse((repo_root / ".worktrees").exists())
            self.assertFalse((repo_root / ".cerebro" / "worktrees.toml").exists())

    def test_worktree_create_fails_closed_when_name_is_already_registered(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                first_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                second_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 1)
            self.assertIn("worktree_already_registered", output)

            registry_entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(registry_entries), 1)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_reports_active_registered_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                list_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 0)
            self.assertEqual(list_exit, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"demo | worktree-demo | active | {repo_root / '.worktrees' / 'demo'}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_reports_missing_registered_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_registry_module.save_worktrees(
                repo_root,
                [
                    {
                        "name": "demo",
                        "path": str(repo_root / ".worktrees" / "demo"),
                        "branch": "worktree-demo",
                        "created_at": "2026-04-18T00:00:00+00:00",
                        "status": "active",
                    }
                ],
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"demo | worktree-demo | missing | {repo_root / '.worktrees' / 'demo'}", output)

    def test_worktree_list_reports_unregistered_detached_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "detached-demo"

            add_result = _run_git(repo_root, "worktree", "add", "-b", "worktree-detached-demo", str(worktree_path))
            self.assertEqual(add_result.returncode, 0, add_result.stderr or add_result.stdout)
            detach_result = _run_git(worktree_path, "checkout", "--detach", "HEAD")
            self.assertEqual(detach_result.returncode, 0, detach_result.stderr or detach_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"detached-demo | - | unregistered | {worktree_path}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-detached-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_fails_closed_when_git_listing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "rev-parse", "--show-toplevel"]:
                    return subprocess.CompletedProcess(command, 0, stdout=str(repo_root) + "\n", stderr="")
                if command == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
                    return subprocess.CompletedProcess(command, 0, stdout=str(repo_root / ".git") + "\n", stderr="")
                if command == ["git", "worktree", "list", "--porcelain"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git list failed")
                raise AssertionError(f"unexpected git command: {command}")

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("worktree_list_failed", output)
            self.assertIn("git list failed", output)

    def test_worktree_list_fails_closed_when_registry_name_does_not_match_path(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            registry_path = repo_root / ".cerebro" / "worktrees.toml"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                "\n".join(
                    [
                        "[[worktrees]]",
                        'name = "fake-name"',
                        f'path = "{_toml_escape(str(repo_root / ".worktrees" / "real-name"))}"',
                        'branch = "worktree-real-name"',
                        'created_at = "2026-04-18T00:00:00+00:00"',
                        'status = "active"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertIn("name does not match path basename", output)

    def test_worktree_list_uses_admin_root_when_invoked_from_child_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            create_stream = io.StringIO()
            child_path = repo_root / ".worktrees" / "demo"

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            self.assertEqual(create_exit, 0)

            list_stream = io.StringIO()
            with redirect_stdout(list_stream):
                list_exit = cli_main_module.main(["--project-root", str(child_path), "worktree", "list"])

            output = list_stream.getvalue()
            self.assertEqual(list_exit, 0)
            self.assertIn(f"repo_root: {repo_root}", output)
            self.assertIn(f"demo | worktree-demo | active | {child_path}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(child_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_removes_worktree_branch_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 0)
            self.assertEqual(clean_exit, 0)
            self.assertIn("worktree: demo", output)
            self.assertFalse((repo_root / ".worktrees" / "demo").exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_registered_active_does_not_use_force_remove(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()
            observed_remove_commands: list[list[str]] = []
            real_run_git = worktree_command_module._run_git_command

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command[:3] == ["git", "worktree", "remove"]:
                    observed_remove_commands.append(command)
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            stream = io.StringIO()
            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertEqual(observed_remove_commands, [["git", "worktree", "remove", str(worktree_path)]])
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_blocks_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            (worktree_path / "dirty.txt").write_text("dirty\n", encoding="utf-8")

            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_dirty", output)
            self.assertTrue(worktree_path.exists())
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_keeps_registry_when_branch_delete_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            real_run_git = worktree_command_module._run_git_command
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_failed", output)
            self.assertIn("branch delete failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_create_cleans_up_when_registry_persist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_create_reports_cleanup_failure_when_registry_persist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            real_run_git = worktree_command_module._run_git_command
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="cleanup branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                    with redirect_stdout(stream):
                        create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("cleanup failed", output)
            self.assertIn("cleanup branch delete failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_create_fails_closed_when_git_worktree_add_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()
            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "worktree", "add", "-b", "worktree-demo", str(worktree_path)]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git worktree add failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_create_failed", output)
            self.assertIn("git worktree add failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_create_serializes_concurrent_registry_updates(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            entered = threading.Event()
            release = threading.Event()
            second_done = threading.Event()
            errors: list[Exception] = []
            results: dict[str, dict[str, str]] = {}
            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                alpha_command = [
                    "git",
                    "worktree",
                    "add",
                    "-b",
                    "worktree-alpha",
                    str(repo_root / ".worktrees" / "alpha"),
                ]
                if command == alpha_command:
                    entered.set()
                    release.wait(timeout=5)
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            def create_worktree(name: str, *, done: threading.Event | None = None) -> None:
                try:
                    results[name] = worktree_command_module.create_worktree(repo_root, name)
                except Exception as exc:  # pragma: no cover - test helper
                    errors.append(exc)
                finally:
                    if done is not None:
                        done.set()

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                first = threading.Thread(target=create_worktree, args=("alpha",))
                second = threading.Thread(target=create_worktree, args=("beta",), kwargs={"done": second_done})
                first.start()
                self.assertTrue(entered.wait(timeout=5))
                second.start()
                self.assertFalse(second_done.wait(timeout=0.2))
                release.set()
                first.join(timeout=5)
                second.join(timeout=5)

            registry_entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(errors, [])
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual({item["name"] for item in registry_entries}, {"alpha", "beta"})
            self.assertEqual({item["name"] for item in results.values()}, {"alpha", "beta"})
            self.assertTrue((repo_root / ".worktrees" / "alpha").exists())
            self.assertTrue((repo_root / ".worktrees" / "beta").exists())

    def test_worktree_create_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            registry_path = repo_root / ".cerebro" / "worktrees.toml"
            lock_path = registry_path.with_suffix(".toml.lock")
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()
            real_unlink = Path.unlink

            def fake_unlink(path: Path, *args, **kwargs):
                if path == lock_path:
                    raise OSError("lock release failed")
                return real_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.unlink", autospec=True, side_effect=fake_unlink):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertTrue(worktree_path.exists())
            self.assertTrue(lock_path.exists())
            self.assertEqual(registry["worktrees"][0]["name"], "demo")
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            lock_path.unlink(missing_ok=True)
            cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_clean_removes_unregistered_active_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            add_result = _run_git(repo_root, "worktree", "add", "-b", "worktree-demo", str(worktree_path))
            self.assertEqual(add_result.returncode, 0, add_result.stderr or add_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_recovers_unregistered_branch_after_failed_create_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            real_run_git = worktree_command_module._run_git_command
            create_stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="cleanup branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                    with redirect_stdout(create_stream):
                        create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            self.assertEqual(create_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            clean_stream = io.StringIO()
            with redirect_stdout(clean_stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_recovers_when_checkout_was_removed_before_branch_delete(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            first_stream = io.StringIO()
            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(first_stream):
                    first_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(first_clean_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            second_stream = io.StringIO()
            with redirect_stdout(second_stream):
                second_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(second_clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_recovers_when_registry_persist_fails_after_physical_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            first_stream = io.StringIO()
            with mock.patch.object(
                worktree_command_module,
                "update_worktrees",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with redirect_stdout(first_stream):
                    first_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(first_clean_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

            second_stream = io.StringIO()
            with redirect_stdout(second_stream):
                second_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(second_clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_fails_closed_when_removed_checkout_has_tampered_branch(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            create_branch_result = _run_git(repo_root, "branch", "keep-me")
            self.assertEqual(create_branch_result.returncode, 0, create_branch_result.stderr or create_branch_result.stdout)
            remove_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(remove_result.returncode, 0, remove_result.stderr or remove_result.stdout)

            entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(entries), 1)
            tampered_entry = dict(entries[0])
            tampered_entry["branch"] = "keep-me"
            worktree_registry_module.save_worktrees(repo_root, [tampered_entry])

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertIn("keep-me", _run_git(repo_root, "branch", "--list", "keep-me").stdout)

    def test_worktree_clean_fails_closed_when_active_worktree_has_tampered_branch(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            create_branch_result = _run_git(repo_root, "branch", "keep-me")
            self.assertEqual(create_branch_result.returncode, 0, create_branch_result.stderr or create_branch_result.stdout)
            checkout_result = _run_git(worktree_path, "checkout", "keep-me")
            self.assertEqual(checkout_result.returncode, 0, checkout_result.stderr or checkout_result.stdout)

            entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(entries), 1)
            tampered_entry = dict(entries[0])
            tampered_entry["branch"] = "keep-me"
            worktree_registry_module.save_worktrees(repo_root, [tampered_entry])

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertTrue(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertIn("keep-me", _run_git(repo_root, "branch", "--list", "keep-me").stdout)

            cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
            delete_demo_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_demo_result.returncode, 0, delete_demo_result.stderr or delete_demo_result.stdout)
            delete_keep_result = _run_git(repo_root, "branch", "-D", "keep-me")
            self.assertEqual(delete_keep_result.returncode, 0, delete_keep_result.stderr or delete_keep_result.stdout)

    def test_worktree_clean_fails_closed_when_registry_entry_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            detach_result = _run_git(worktree_path, "checkout", "--detach", "HEAD")
            self.assertEqual(detach_result.returncode, 0, detach_result.stderr or detach_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertTrue(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_uses_admin_root_when_invoked_from_child_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            child_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(child_path), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 0)
            self.assertIn(f"repo_root: {repo_root}", output)
            self.assertFalse(child_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_render_open_dashboard_reads_operational_summary_and_initialized_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
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
                        "- item beta",
                        "  Status atual: Grupo 6",
                    ]
                ),
                encoding="utf-8",
            )
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `FATIA 4 — Dashboard de estado ao abrir`",
                    ]
                ),
                encoding="utf-8",
            )

            run_init(project_root)

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("impl-fatia-4: dashboard de estado - 617 testes", "617"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("DASHBOARD", output)
            self.assertIn(f"project_root: {project_root}", output)
            self.assertIn("testes: 617", output)
            self.assertIn("criticos_abertos: 0", output)
            self.assertIn("altos_abertos: 2", output)
            self.assertIn("ultima_iteracao: impl-fatia-4: dashboard de estado - 617 testes", output)
            self.assertIn("proximo_item: FATIA 4 — Dashboard de estado ao abrir", output)
            self.assertIn("estado_projeto: initialized", output)
            self.assertIn("revisao: 0", output)
            self.assertIn("validacao:", output)

    def test_render_open_dashboard_reports_not_initialized_when_project_has_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
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
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `FATIA 4 — Dashboard de estado ao abrir`",
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("impl-fatia-4: dashboard de estado - 617 testes", "617"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("estado_projeto: state_absent", output)
            self.assertNotIn("revisao:", output)

    def test_render_open_dashboard_reports_state_unavailable_when_state_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
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
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `nenhuma — prova de parada e encerramento formal`",
                    ]
                ),
                encoding="utf-8",
            )
            state_dir = project_root / ".cerebro"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "state.json").write_text("{invalid", encoding="utf-8")

            output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("estado_projeto: state_unavailable", output)

    def test_render_open_dashboard_treats_invalid_doc_encoding_as_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_bytes(b"\xff\xfe\xfd")
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_bytes(b"\xff\xfe\xfd")

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("unknown", "unknown"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("testes: unknown", output)
            self.assertIn("criticos_abertos: unknown", output)
            self.assertIn("altos_abertos: unknown", output)
            self.assertIn("proximo_item: unknown", output)
            self.assertIn("estado_projeto: state_absent", output)

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
