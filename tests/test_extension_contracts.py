from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.handoff_export.exporter import HandoffExportError, export_handoff_markdown, write_handoff_markdown
from extensions.return_map_export.exporter import (
    ReturnMapExportError,
    export_return_map_markdown,
    write_return_map_markdown,
)
from extensions.status_export.exporter import StatusExportError, export_status_markdown, write_status_markdown


class ReadOnlyExtensionContractTests(unittest.TestCase):
    def test_exports_run_in_sequence_without_modifying_runtime(self) -> None:
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
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            handoff = export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            status = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            return_map = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Handoff", handoff)
            self.assertIn("# Status", status)
            self.assertIn("# Return Map", return_map)
            self.assertEqual(before_revision, store.read_snapshot().revision)
            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_all_read_only_extensions_reject_runtime_output_paths(self) -> None:
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
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(HandoffExportError):
                write_handoff_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(ReturnMapExportError):
                write_return_map_markdown(root, ".cerebro/blocked.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_exports_do_not_leak_source_body_in_shared_fixture(self) -> None:
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

            for output in (
                export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
            ):
                self.assertNotIn("TOP SECRET BODY", output)
