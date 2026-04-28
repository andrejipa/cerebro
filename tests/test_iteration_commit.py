from __future__ import annotations

import io
import subprocess
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.commands.iteration_commit as iteration_commit_module


class IterationCommitCommandTests(unittest.TestCase):
    def _write_status(self, repo_root: Path, *, current_state: str = "concluída") -> Path:
        operations_dir = repo_root / "docs" / "operations"
        operations_dir.mkdir(parents=True, exist_ok=True)
        status_path = operations_dir / "IMPLEMENTATION_STATUS.md"
        status_path.write_text(
            "\n".join(
                [
                    "# Implementation Status — External Cerebro Model",
                    "",
                    "## Fatias concluídas",
                    "",
                    "- Fatia 6: `Commit automático por iteração`",
                    "  - Implementada em: `2026-04-18`",
                    "  - Arquivos alterados:",
                    "    - `cli/commands/iteration_commit.py`",
                    "  - Testes adicionados:",
                    "    - `tests.test_iteration_commit.IterationCommitCommandTests.test_run_iteration_commit_generates_commit_with_documented_message`",
                    "  - Critério de pronto: `sim`",
                    "",
                    "## Fatia atual",
                    "",
                    "- Qual é: `FATIA 6 — Commit automático por iteração`",
                    f"- Estado: `{current_state}`",
                ]
            ),
            encoding="utf-8",
        )
        return status_path

    def test_run_iteration_commit_generates_commit_with_documented_message(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                calls.append(command_tuple)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 626 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md", "cli/main.py"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == (
                    "git",
                    "diff",
                    "--cached",
                    "--name-only",
                    "--",
                    "docs/operations/IMPLEMENTATION_STATUS.md",
                    "cli/main.py",
                ):
                    return subprocess.CompletedProcess(
                        command,
                        0,
                        stdout="docs/operations/IMPLEMENTATION_STATUS.md\ncli/main.py\n",
                        stderr="",
                    )
                if command_tuple == ("git", "commit", "-m", "iter-6: Commit automático por iteração — 626 testes"):
                    return subprocess.CompletedProcess(command, 0, stdout="[main abc123] ok\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md", "cli/main.py"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertTrue(output.startswith("OK"))
            self.assertIn("mode: explicit automation", output)
            self.assertIn("message: iter-6: Commit automático por iteração — 626 testes", output)
            self.assertIn("paths: docs/operations/IMPLEMENTATION_STATUS.md, cli/main.py", output)
            self.assertEqual(calls[-1], ("git", "commit", "-m", "iter-6: Commit automático por iteração — 626 testes"))
            self.assertIn(("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md", "cli/main.py"), calls)
            self.assertEqual(status_path.read_text(encoding="utf-8").count("FATIA 6"), 1)

    def test_run_iteration_commit_fails_closed_when_index_is_not_clean(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            self._write_status(repo_root)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                calls.append(command_tuple)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 626 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="README.md\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", repo_root / "docs" / "operations" / "IMPLEMENTATION_STATUS.md"):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("iteration-commit requires a clean index before staging the selected paths", output)
            self.assertNotIn(("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md"), calls)

    def test_build_iteration_commit_rejects_paths_outside_repo(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            with self.assertRaises(iteration_commit_module.IterationCommitError) as ctx:
                iteration_commit_module.build_iteration_commit(
                    ["../outside.txt"],
                    repo_root=repo_root,
                    status_path=status_path,
                )

            self.assertIn("outside the Cerebro repository", str(ctx.exception))

    def test_run_iteration_commit_unstages_selection_when_commit_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                calls.append(command_tuple)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 626 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == (
                    "git",
                    "diff",
                    "--cached",
                    "--name-only",
                    "--",
                    "docs/operations/IMPLEMENTATION_STATUS.md",
                ):
                    return subprocess.CompletedProcess(command, 0, stdout="docs/operations/IMPLEMENTATION_STATUS.md\n", stderr="")
                if command_tuple == ("git", "commit", "-m", "iter-6: Commit automático por iteração — 626 testes"):
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="commit blocked")
                if command_tuple == ("git", "reset", "HEAD", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("commit blocked", output)
            self.assertIn(("git", "reset", "HEAD", "--", "docs/operations/IMPLEMENTATION_STATUS.md"), calls)

    def test_build_commit_message_falls_back_to_last_completed_fatia(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root, current_state="em progresso")

            message = iteration_commit_module._build_commit_message(status_path, 626)

            self.assertEqual(message, "iter-6: Commit automático por iteração — 626 testes")

    def test_run_iteration_commit_fails_closed_when_full_suite_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 1, stdout="Ran 634 tests in 1.000s\nFAILED (failures=1)\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("full test suite is not green", output)

    def test_run_iteration_commit_fails_closed_when_suite_count_is_unavailable(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="OK\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("test count could not be determined", output)

    def test_run_iteration_commit_fails_closed_when_architecture_suite_is_red(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 634 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 1, stdout="Ran 51 tests in 0.500s\nFAILED (failures=1)\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("architecture test suite is not green", output)

    def test_run_iteration_commit_fails_closed_when_selected_paths_stage_nothing(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)
            calls: list[tuple[str, ...]] = []

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                calls.append(command_tuple)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 634 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "reset", "HEAD", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("selected paths produced no staged changes", output)
            self.assertIn(("git", "reset", "HEAD", "--", "docs/operations/IMPLEMENTATION_STATUS.md"), calls)

    def test_run_iteration_commit_fails_closed_when_git_repo_root_mismatches(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as other_repo_dir:
            repo_root = Path(repo_dir).resolve()
            other_repo_root = Path(other_repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{other_repo_root}\n", stderr="")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("must run from the Cerebro repository root", output)

    def test_run_iteration_commit_fails_closed_when_git_add_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 643 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git add failed")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("git add failed", output)

    def test_build_commit_message_fails_closed_without_any_concluded_fatia(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            status_path = operations_dir / "IMPLEMENTATION_STATUS.md"
            status_path.write_text(
                "\n".join(
                    [
                        "# Implementation Status — External Cerebro Model",
                        "",
                        "## Fatias concluídas",
                        "",
                        "## Fatia atual",
                        "",
                        "- Qual é: `FATIA 6 — Commit automático por iteração`",
                        "- Estado: `em progresso`",
                    ]
                ),
                encoding="utf-8",
            )

            with self.assertRaises(iteration_commit_module.IterationCommitError) as ctx:
                iteration_commit_module._build_commit_message(status_path, 643)

            self.assertIn("does not expose a concluded fatia", str(ctx.exception))

    def test_run_iteration_commit_surfaces_cleanup_failure_when_unstage_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            status_path = self._write_status(repo_root)

            def fake_run(command: list[str], *, cwd: Path) -> subprocess.CompletedProcess[str]:
                self.assertEqual(cwd, repo_root)
                command_tuple = tuple(command)
                if command_tuple == ("git", "rev-parse", "--show-toplevel"):
                    return subprocess.CompletedProcess(command, 0, stdout=f"{repo_root}\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 643 tests in 1.000s\nOK\n", stderr="")
                if command_tuple == (iteration_commit_module.sys.executable, "-m", "unittest", "tests.test_architecture", "-v"):
                    return subprocess.CompletedProcess(command, 0, stdout="Ran 51 tests in 0.500s\nOK\n", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "add", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="", stderr="")
                if command_tuple == ("git", "diff", "--cached", "--name-only", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 0, stdout="docs/operations/IMPLEMENTATION_STATUS.md\n", stderr="")
                if command_tuple == ("git", "commit", "-m", "iter-6: Commit automático por iteração — 643 testes"):
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="commit blocked")
                if command_tuple == ("git", "reset", "HEAD", "--", "docs/operations/IMPLEMENTATION_STATUS.md"):
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git reset failed during cleanup")
                raise AssertionError(f"unexpected command: {command_tuple}")

            args = mock.Mock(path=["docs/operations/IMPLEMENTATION_STATUS.md"])
            stream = io.StringIO()
            with mock.patch.object(iteration_commit_module, "REPO_ROOT", repo_root):
                with mock.patch.object(iteration_commit_module, "IMPLEMENTATION_STATUS_PATH", status_path):
                    with mock.patch.object(iteration_commit_module, "_run_command", side_effect=fake_run):
                        with redirect_stdout(stream):
                            exit_code = iteration_commit_module.run_iteration_commit(repo_root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertTrue(output.startswith("FAIL"))
            self.assertIn("git reset failed during cleanup", output)
