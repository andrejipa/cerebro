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

from cli.commands.init import run_init
from cli.commands.return_map_export import run_return_map_export
from core.state_store import StateStore
from extensions.return_map_export.exporter import (
    ReturnMapExportError,
    export_return_map_json,
    export_return_map_markdown,
    write_return_map_markdown,
)
from tests.runtime_fixtures import seed_checkpointed_runtime, seed_registered_source

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReturnMapExportTests(unittest.TestCase):
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

            output = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Return Map", output)
            self.assertIn("- Exported at: 2026-04-11T12:00:00+00:00", output)
            self.assertIn("- Validation: ok", output)
            self.assertIn("- Session file: present", output)
            self.assertIn("- Revision: 2", output)
            self.assertIn("- Goal: Ship fix", output)
            self.assertIn("- Summary: Checkpoint is ready.", output)
            self.assertIn("- Next step: Open tracked.txt and continue.", output)
            self.assertIn("- Do not change API", output)
            self.assertIn("- tracked.txt", output)

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
            store.open_session("alice")

            payload = export_return_map_json(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["export_kind"], "return_map")
            self.assertEqual(payload["exported_at"], "2026-04-11T12:00:00+00:00")
            self.assertEqual(payload["revision"], 2)
            self.assertEqual(len(payload["root_sha256"]), 64)
            self.assertEqual(payload["payload"]["validation"], "ok")
            self.assertEqual(
                payload["payload"]["validation_basis"],
                "persisted canonical record only; exports do not rerun validate",
            )
            self.assertEqual(payload["payload"]["session_file"], "present")
            self.assertEqual(
                payload["payload"]["point_of_return"],
                {
                    "goal": "Ship fix",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Open tracked.txt and continue.",
                },
            )
            self.assertEqual(payload["payload"]["constraints"], ["Do not change API"])
            self.assertEqual(payload["payload"]["sources_count"], 1)
            self.assertEqual(payload["payload"]["sources"], ["tracked.txt"])
            self.assertEqual(payload["payload"]["validation_details"], [])

    def test_export_does_not_include_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("TOP SECRET BODY", encoding="utf-8")
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

            output = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertNotIn("TOP SECRET BODY", output)

    def test_export_is_stable_for_same_state(self) -> None:
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

            first = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            second = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(first, second)

    def test_export_fails_explicitly_when_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaises(ReturnMapExportError):
                export_return_map_markdown(root)

            with self.assertRaises(ReturnMapExportError):
                export_return_map_json(root)

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

            export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

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
            store, _ = seed_registered_source(root)
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(ReturnMapExportError):
                write_return_map_markdown(root, ".cerebro/state.json")

            with self.assertRaises(ReturnMapExportError):
                write_return_map_markdown(root, ".cerebro/session.local.json")

            with self.assertRaises(ReturnMapExportError):
                write_return_map_markdown(root, ".cerebro/return-map.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_return_map_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Return Map", output)
            self.assertIn("## Point Of Return", output)

    def test_cli_exports_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_return_map_export(root, type("Args", (), {"out": None, "format": "json"}))

            payload = json.loads(stream.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["export_kind"], "return_map")

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            args = type("Args", (), {"out": "return-map.md"})

            exit_code = run_return_map_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "return-map.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Return Map", content)

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "return-map-export"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("# Return Map", result.stdout)
            self.assertIn("## Point Of Return", result.stdout)
