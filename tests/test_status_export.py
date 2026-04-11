from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.init import run_init
from cli.commands.status_export import run_status_export
from core.state_store import StateStore
from extensions.status_export.exporter import StatusExportError, export_status_markdown, write_status_markdown

REPO_ROOT = Path(__file__).resolve().parents[1]


class StatusExportTests(unittest.TestCase):
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
            store.open_session("alice")

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Status", output)
            self.assertIn("- Exported at: 2026-04-11T12:00:00+00:00", output)
            self.assertIn("- Validation: ok", output)
            self.assertIn("- Risk: low", output)
            self.assertIn("- Session file: present", output)
            self.assertIn("- Sources: 1", output)
            self.assertIn("- Revision: 2", output)
            self.assertIn("- Updated at:", output)
            self.assertIn("- Validated at:", output)

    def test_export_reports_fail_and_high_risk_for_inconsistent_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()
            tracked.write_text("changed", encoding="utf-8")
            store.validate_state()

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- Validation: fail", output)
            self.assertIn("- Risk: high", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertIn("- Session file: absent", output)

    def test_export_does_not_include_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("TOP SECRET BODY", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertNotIn("TOP SECRET BODY", output)
            self.assertNotIn("Ship fix", output)
            self.assertNotIn("Checkpoint is ready.", output)

    def test_export_is_stable_for_same_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()

            first = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            second = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(first, second)

    def test_export_fails_explicitly_when_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaises(StatusExportError):
                export_status_markdown(root)

    def test_export_does_not_change_revision_or_runtime_files(self) -> None:
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
            store.validate_state()
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            after_state = store.state_path.read_text(encoding="utf-8")
            after_session = store.session_path.read_text(encoding="utf-8")
            after_revision = store.read_snapshot().revision
            self.assertEqual(before_revision, after_revision)
            self.assertEqual(before_state, after_state)
            self.assertEqual(before_session, after_session)

    def test_export_rejects_runtime_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/state.json")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/session.local.json")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/status.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_status_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Status", output)
            self.assertIn("- Validation:", output)

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            args = type("Args", (), {"out": "status.md"})

            exit_code = run_status_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "status.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Status", content)

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "status-export"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("# Status", result.stdout)
            self.assertIn("- Validation:", result.stdout)
