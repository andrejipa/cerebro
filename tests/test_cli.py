from __future__ import annotations

import io
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.init import run_init
from cli.commands.resume import run_resume
from cli.commands.validate import run_validate
from core.state_store import StateStore


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
        self.assertIn("Local context checkpoint CLI", result.stdout)
        self.assertIn("import-context", result.stdout)
        self.assertIn("handoff-export", result.stdout)

    def test_subcommand_help_pages(self) -> None:
        for command in ("init", "import-context", "checkpoint", "resume", "handoff-export", "validate"):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn(command, result.stdout)

    def test_cli_usage_error_returns_exit_code_2(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "checkpoint"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)


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

    def test_validate_ok_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("validation_passed:", output)

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
