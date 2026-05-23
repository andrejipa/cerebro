from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore

from experiments.context_discovery import (
    MAX_CONTENT_BYTES,
    MAX_CONTENT_LINES,
    discover_context,
    read_content_head,
    render_markdown,
)
from experiments.context_discovery.content import content_role_signals
from experiments.context_discovery.discovery import ContextDiscoveryError


def _initialize_with_sources(root: Path, paths: list[str]) -> StateStore:
    run_init(root, None)
    store = StateStore(root)
    store.register_sources(paths)
    store.update_checkpoint(
        {
            "goal": "Goal",
            "summary": "Summary",
            "next_step": "Next",
            "constraints": [],
        }
    )
    store.validate_state()
    return store


class ContextDiscoveryReportTests(unittest.TestCase):
    def test_candidate_not_registered_is_lifted_by_content_scope_heading(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# demo\n\nReadme body.\n", encoding="utf-8")
            (root / "NOTES.md").write_text(
                "# Project Scope\n\nThis document defines the active product scope.\n",
                encoding="utf-8",
            )
            _initialize_with_sources(root, ["README.md"])

            report = discover_context(root)

            candidate_paths = {candidate.relative_path for candidate in report.candidates_not_registered}
            self.assertIn("NOTES.md", candidate_paths)
            self.assertNotIn("README.md", candidate_paths)

            notes_candidate = next(
                candidate
                for candidate in report.candidates_not_registered
                if candidate.relative_path == "NOTES.md"
            )
            self.assertEqual(notes_candidate.role, "project-scope")
            self.assertTrue(
                any(reason.startswith("content:") for reason in notes_candidate.reasons),
                msg=notes_candidate.reasons,
            )

    def test_drift_record_flags_registered_source_whose_sha_no_longer_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "CONTEXT.md").write_text("# Context\n\nOriginal content.\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md", "CONTEXT.md"])

            (root / "CONTEXT.md").write_text(
                "# Daily journal\n\nUnrelated content now.\n", encoding="utf-8"
            )

            report = discover_context(root)

            drift_paths = {record.relative_path for record in report.drift_on_registered_sources}
            self.assertIn("CONTEXT.md", drift_paths)
            drift = next(
                record
                for record in report.drift_on_registered_sources
                if record.relative_path == "CONTEXT.md"
            )
            self.assertNotEqual(drift.registered_sha256, drift.current_sha256)
            self.assertIn("Daily journal", drift.current_heading)

    def test_missing_record_flags_registered_source_deleted_from_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            ghost = root / "GHOST.md"
            ghost.write_text("ghost content", encoding="utf-8")
            _initialize_with_sources(root, ["README.md", "GHOST.md"])
            ghost.unlink()

            report = discover_context(root)

            missing_paths = {record.relative_path for record in report.missing_registered_sources}
            self.assertEqual(missing_paths, {"GHOST.md"})

    def test_discovery_does_not_mutate_runtime_or_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            (root / "NOTES.md").write_text("# Project Scope\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md"])

            before_runtime = {
                path.relative_to(root / ".cerebro").as_posix(): path.read_bytes()
                for path in sorted((root / ".cerebro").rglob("*"))
                if path.is_file()
            }
            before_project = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file() and ".cerebro" not in path.parts
            }

            discover_context(root)

            after_runtime = {
                path.relative_to(root / ".cerebro").as_posix(): path.read_bytes()
                for path in sorted((root / ".cerebro").rglob("*"))
                if path.is_file()
            }
            after_project = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file() and ".cerebro" not in path.parts
            }
            self.assertEqual(before_runtime, after_runtime)
            self.assertEqual(before_project, after_project)

    def test_discovery_without_registered_state_records_note_and_still_emits_candidates(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "NOTES.md").write_text(
                "# Project Scope\n\nThis defines the project.\n",
                encoding="utf-8",
            )

            report = discover_context(root)

            self.assertEqual(report.registered_source_count, 0)
            self.assertTrue(any("no registered sources" in note for note in report.notes), msg=report.notes)
            self.assertIn(
                "NOTES.md",
                {candidate.relative_path for candidate in report.candidates_not_registered},
            )

    def test_discovery_rejects_missing_root(self) -> None:
        with self.assertRaises(ContextDiscoveryError):
            discover_context("/definitely/does/not/exist/at/all")

    def test_discovery_rejects_non_positive_candidate_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                discover_context(tmp_dir, candidate_limit=0)


class ContentHeadSafetyTests(unittest.TestCase):
    def test_binary_files_are_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            binary_path = root / "blob.txt"
            binary_path.write_bytes(b"\x00\x01\x02\x03\x04" + b"garbage" * 200)
            self.assertIsNone(read_content_head(binary_path))

    def test_non_textual_suffix_is_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            binary_path = root / "image.png"
            binary_path.write_bytes(b"\x89PNG\r\n\x1a\n" + b"data" * 200)
            self.assertIsNone(read_content_head(binary_path))

    def test_oversized_file_respects_caps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            big_path = root / "big.md"
            filler_line = "filler " * 20
            body = ("padding\n" * 5) + (filler_line + "\n") * 200
            trailing_marker = "PROJECT_SCOPE_MARKER_AT_END"
            body += trailing_marker + "\n"
            big_path.write_text(body, encoding="utf-8")

            head = read_content_head(big_path)
            self.assertIsNotNone(head)
            assert head is not None
            self.assertLessEqual(len(head.splitlines()), MAX_CONTENT_LINES)
            self.assertLessEqual(len(head.encode("utf-8")), MAX_CONTENT_BYTES)
            self.assertNotIn(trailing_marker, head)

    def test_content_role_signals_detects_each_role_family(self) -> None:
        cases = {
            "# Project Scope\n": "project-scope",
            "# Architecture Decision\n": "architecture-decision",
            "# Handoff summary\n": "continuity",
            "# Estado atual\n": "current-state",
        }
        for head, expected_role in cases.items():
            with self.subTest(head=head):
                roles = {role for role, _, _ in content_role_signals(".md", head)}
                self.assertIn(expected_role, roles)


class ReportRenderingTests(unittest.TestCase):
    def test_markdown_shape_is_stable_with_empty_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# demo\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md"])
            markdown = render_markdown(discover_context(root))

            self.assertIn("# Context Discovery Report", markdown)
            self.assertIn("## candidates_not_registered", markdown)
            self.assertIn("## drift_on_registered_sources", markdown)
            self.assertIn("## missing_registered_sources", markdown)
            self.assertIn("state_change: none", markdown)
            self.assertIn("advisory only", markdown)


if __name__ == "__main__":
    unittest.main()
