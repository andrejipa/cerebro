"""Shared contract tests for every tracked read-only export."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.handoff_export.exporter import HandoffExportError, export_handoff_markdown, write_handoff_markdown
from extensions.impact_export.exporter import ImpactExportError, export_impact_markdown, write_impact_markdown
from extensions.return_map_export.exporter import (
    ReturnMapExportError,
    export_return_map_markdown,
    write_return_map_markdown,
)
from extensions.sources_export.exporter import SourcesExportError, export_sources_markdown, write_sources_markdown
from extensions.status_export.exporter import StatusExportError, export_status_markdown, write_status_markdown
from extensions.validation_export.exporter import (
    ValidationExportError,
    export_validation_markdown,
    write_validation_markdown,
)

REPO_ROOT = Path(__file__).resolve().parents[1]


class ReadOnlyExtensionContractTests(unittest.TestCase):
    def test_export_commands_write_files_by_subprocess_without_modifying_runtime(self) -> None:
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

            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            for command, filename, success_code in (
                ("handoff-export", "handoff.md", "handoff_exported"),
                ("impact-export", "impact.md", "impact_exported"),
                ("sources-export", "sources.md", "sources_exported"),
                ("status-export", "status.md", "status_exported"),
                ("validation-export", "validation.md", "validation_exported"),
                ("return-map-export", "return-map.md", "return_map_exported"),
            ):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, "-m", "cli.main", command, "--out", filename],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0)
                    self.assertTrue((root / filename).exists())
                    self.assertIn(success_code, result.stdout)

            self.assertEqual(before_revision, store.read_snapshot().revision)
            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_export_commands_reflect_failed_validation_after_real_analyze_block(self) -> None:
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
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            first_analyze = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first_analyze.returncode, 0)

            tracked.write_text("changed", encoding="utf-8")
            second_analyze = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second_analyze.returncode, 1)
            self.assertIn("analysis_blocked", second_analyze.stdout)
            self.assertIn("source_hash_mismatch", second_analyze.stdout)

            for command in (
                "handoff-export",
                "impact-export",
                "sources-export",
                "status-export",
                "validation-export",
                "return-map-export",
            ):
                with self.subTest(command=command):
                    result = subprocess.run(
                        [sys.executable, "-m", "cli.main", command],
                        cwd=root,
                        env=env,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 0)
                    self.assertIn("Validation: fail", result.stdout)

    def test_exports_report_session_file_presence_when_local_session_file_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()
            store.open_session("alice")

            impact = export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            status = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            sources = export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            return_map = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            validation = export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- Session file: present", impact)
            self.assertIn("- Session file: present", status)
            self.assertIn("- Session file: present", sources)
            self.assertIn("- Session file: present", return_map)
            self.assertIn("- Session file: present", validation)

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
            impact = export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            status = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            sources = export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            return_map = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            validation = export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Handoff", handoff)
            self.assertIn("# Impact", impact)
            self.assertIn("# Status", status)
            self.assertIn("# Sources", sources)
            self.assertIn("# Return Map", return_map)
            self.assertIn("# Validation", validation)
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

            with self.assertRaises(ImpactExportError):
                write_impact_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(SourcesExportError):
                write_sources_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(ReturnMapExportError):
                write_return_map_markdown(root, ".cerebro/blocked.md")

            with self.assertRaises(ValidationExportError):
                write_validation_markdown(root, ".cerebro/blocked.md")

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
                export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
            ):
                self.assertNotIn("TOP SECRET BODY", output)

    def test_exports_reflect_failed_validation_after_real_analyze_block_in_process(self) -> None:
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
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            first_analyze = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(first_analyze.returncode, 0)

            tracked.write_text("changed", encoding="utf-8")
            second_analyze = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(second_analyze.returncode, 1)
            self.assertIn("analysis_blocked", second_analyze.stdout)
            self.assertIn("source_hash_mismatch", second_analyze.stdout)

            handoff = export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            impact = export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            status = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            sources = export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            return_map = export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            validation = export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("Validation: fail", handoff)
            self.assertIn("- Validation: fail", impact)
            self.assertIn("- Validation: fail", status)
            self.assertIn("- Validation: fail", sources)
            self.assertIn("- Validation: fail", return_map)
            self.assertIn("- Validation: fail", validation)
            self.assertIn("## Validation Details", impact)
            self.assertIn("## Validation Details", status)
            self.assertIn("## Validation Details", return_map)
            self.assertIn("## Validation Details", validation)

    def test_exports_fail_explicitly_when_state_becomes_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.state_path.write_text("{invalid", encoding="utf-8")

            with self.assertRaises(HandoffExportError):
                export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ImpactExportError):
                export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(StatusExportError):
                export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(SourcesExportError):
                export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ReturnMapExportError):
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ValidationExportError):
                export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

    def test_exports_fail_explicitly_when_state_schema_becomes_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            invalid_state = store.load_state()
            invalid_state["revision"] = True
            store.state_path.write_text(json.dumps(invalid_state, indent=2), encoding="utf-8")

            with self.assertRaises(HandoffExportError):
                export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ImpactExportError):
                export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(StatusExportError):
                export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(SourcesExportError):
                export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ReturnMapExportError):
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            with self.assertRaises(ValidationExportError):
                export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
