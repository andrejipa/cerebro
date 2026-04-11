from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.handoff_export import run_handoff_export
from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.handoff_export.exporter import HandoffExportError, export_handoff_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]


class HandoffExportTests(unittest.TestCase):
    def test_export_contains_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("secret-content", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship fix",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Open tracked.txt and continue.",
                    "constraints": ["Do not change API"],
                }
            )
            store.validate_state()

            output = export_handoff_markdown(root, exported_at="2026-04-10T12:00:00+00:00")

            self.assertIn("# Handoff", output)
            self.assertIn("Ship fix", output)
            self.assertIn("Checkpoint is ready.", output)
            self.assertIn("Open tracked.txt and continue.", output)
            self.assertIn("Do not change API", output)
            self.assertIn("tracked.txt", output)
            self.assertIn("Last validation: ok", output)
            self.assertIn("Revision: 2", output)

    def test_export_does_not_include_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("TOP SECRET BODY", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            output = export_handoff_markdown(root, exported_at="2026-04-10T12:00:00+00:00")

            self.assertNotIn("TOP SECRET BODY", output)

    def test_export_fails_explicitly_when_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaises(HandoffExportError):
                export_handoff_markdown(root)

    def test_export_does_not_change_revision_or_state_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            before_state = store.state_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            export_handoff_markdown(root, exported_at="2026-04-10T12:00:00+00:00")

            after_state = store.state_path.read_text(encoding="utf-8")
            after_revision = store.read_snapshot().revision
            self.assertEqual(before_revision, after_revision)
            self.assertEqual(before_state, after_state)

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_handoff_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Handoff", output)
            self.assertIn("## Objetivo", output)

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            args = type("Args", (), {"out": "handoff.md"})

            exit_code = run_handoff_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "handoff.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Handoff", content)

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "handoff-export"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("# Handoff", result.stdout)
            self.assertIn("## Objetivo", result.stdout)
