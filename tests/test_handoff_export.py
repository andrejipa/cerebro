from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

from cli.commands.handoff_export import run_handoff_export
from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.handoff_export.exporter import (
    HandoffExportError,
    export_handoff_json,
    export_handoff_markdown,
    write_handoff_markdown,
)
from tests.runtime_fixtures import seed_checkpointed_runtime

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
            self.assertIn("Validation: ok", output)
            self.assertIn("Revision: 2", output)

    def test_export_json_contains_expected_fields(self) -> None:
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

            payload = export_handoff_json(root, exported_at="2026-04-10T12:00:00+00:00")

            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["export_kind"], "handoff")
            self.assertEqual(payload["exported_at"], "2026-04-10T12:00:00+00:00")
            self.assertEqual(payload["revision"], 2)
            self.assertEqual(len(payload["root_sha256"]), 64)
            self.assertEqual(payload["payload"]["goal"], "Ship fix")
            self.assertEqual(payload["payload"]["summary"], "Checkpoint is ready.")
            self.assertEqual(payload["payload"]["next_step"], "Open tracked.txt and continue.")
            self.assertEqual(payload["payload"]["constraints"], ["Do not change API"])
            self.assertEqual(payload["payload"]["sources_count"], 1)
            self.assertEqual(payload["payload"]["sources"], ["tracked.txt"])
            self.assertEqual(payload["payload"]["validation"], "ok")
            self.assertEqual(
                payload["payload"]["validation_basis"],
                "persisted canonical record only; exports do not rerun validate",
            )

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

            with self.assertRaises(HandoffExportError):
                export_handoff_json(root)

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
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            export_handoff_markdown(root, exported_at="2026-04-10T12:00:00+00:00")

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
            store, _ = seed_checkpointed_runtime(root)
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(HandoffExportError):
                write_handoff_markdown(root, ".cerebro/state.json")

            with self.assertRaises(HandoffExportError):
                write_handoff_markdown(root, ".cerebro/session.local.json")

            with self.assertRaises(HandoffExportError):
                write_handoff_markdown(root, ".cerebro/handoff.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_handoff_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Handoff", output)
            self.assertIn("## Goal", output)

    def test_cli_exports_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_handoff_export(root, type("Args", (), {"out": None, "format": "json"}))

            payload = json.loads(stream.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["export_kind"], "handoff")

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            args = type("Args", (), {"out": "handoff.md"})

            exit_code = run_handoff_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "handoff.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Handoff", content)

    def test_cli_export_failure_does_not_leave_partial_output_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            args = type("Args", (), {"out": "handoff.md"})
            output_path = root / "handoff.md"
            output_path.write_text("existing handoff", encoding="utf-8")
            original_replace = os.replace
            stream = io.StringIO()

            def flaky_replace(src, dst):
                if Path(dst) == output_path:
                    raise OSError("replace failed")
                return original_replace(src, dst)

            with mock.patch("extensions._support.os.replace", side_effect=flaky_replace):
                with redirect_stdout(stream):
                    exit_code = run_handoff_export(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("handoff_export_failed", output)
            self.assertEqual(output_path.read_text(encoding="utf-8"), "existing handoff")
            self.assertFalse(output_path.with_suffix(".md.tmp").exists())

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
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
            self.assertIn("## Goal", result.stdout)
