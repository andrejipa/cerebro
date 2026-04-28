"""Tests for experiments/drift_detection.

Covers: hasher, scanner, detector, baseline, report, schema, and the
non-mutation boundary (scan and detect must never write to .cerebro/ or
modify canonical state).
"""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.drift_detection.baseline import load_baseline, save_baseline
from experiments.drift_detection.detector import detect
from experiments.drift_detection.hasher import ast_hash
from experiments.drift_detection.report import to_markdown, write_report
from experiments.drift_detection.scanner import scan
from experiments.drift_detection.schema import DriftEntry, DriftReport, FileHashEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _py(root: Path, rel: str, source: str) -> Path:
    """Write a Python source file and return its path."""
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(source, encoding="utf-8")
    return path


def _fake_entry(path: str, h: str = "abc123", lc: int = 5) -> FileHashEntry:
    return FileHashEntry(path=path, ast_hash=h, line_count=lc)


# ---------------------------------------------------------------------------
# hasher
# ---------------------------------------------------------------------------

class AstHashTests(unittest.TestCase):

    def test_valid_python_returns_hex_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = _py(Path(tmp), "a.py", "x = 1\n")
            result = ast_hash(f)
            self.assertIsNotNone(result)
            assert result is not None
            self.assertEqual(len(result), 64)  # SHA-256 hex
            self.assertRegex(result, r'^[0-9a-f]{64}$')

    def test_same_source_different_whitespace_produces_same_hash(self) -> None:
        """AST hash is whitespace-independent."""
        with tempfile.TemporaryDirectory() as tmp:
            f1 = _py(Path(tmp), "a.py", "x = 1\ny = 2\n")
            f2 = _py(Path(tmp), "b.py", "x=1\ny=2\n")
            self.assertEqual(ast_hash(f1), ast_hash(f2))

    def test_comment_only_change_produces_same_hash(self) -> None:
        """Comments do not affect the AST hash."""
        with tempfile.TemporaryDirectory() as tmp:
            f1 = _py(Path(tmp), "a.py", "x = 1\n")
            f2 = _py(Path(tmp), "b.py", "# comment\nx = 1\n")
            self.assertEqual(ast_hash(f1), ast_hash(f2))

    def test_structural_change_produces_different_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f1 = _py(Path(tmp), "a.py", "x = 1\n")
            f2 = _py(Path(tmp), "b.py", "x = 2\n")
            self.assertNotEqual(ast_hash(f1), ast_hash(f2))

    def test_syntax_error_returns_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            f = _py(Path(tmp), "bad.py", "def (:\n")
            self.assertIsNone(ast_hash(f))

    def test_missing_file_returns_none(self) -> None:
        self.assertIsNone(ast_hash(Path("/definitely/does/not/exist.py")))


# ---------------------------------------------------------------------------
# scanner
# ---------------------------------------------------------------------------

class ScannerTests(unittest.TestCase):

    def test_finds_py_files_under_given_roots(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/module.py", "x = 1\n")
            _py(root, "cli/cmd.py", "y = 2\n")
            entries = scan(root, roots=["core", "cli"])
            paths = {e.path for e in entries}
            self.assertIn("core/module.py", paths)
            self.assertIn("cli/cmd.py", paths)

    def test_skips_pycache_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/mod.py", "x = 1\n")
            _py(root, "core/__pycache__/mod.cpython-310.py", "x = 1\n")
            entries = scan(root, roots=["core"])
            paths = {e.path for e in entries}
            self.assertNotIn("core/__pycache__/mod.cpython-310.py", paths)
            self.assertIn("core/mod.py", paths)

    def test_missing_root_is_silently_skipped(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/mod.py", "x = 1\n")
            entries = scan(root, roots=["core", "nonexistent_dir"])
            self.assertEqual(len(entries), 1)

    def test_each_entry_has_path_hash_and_line_count(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/mod.py", "x = 1\ny = 2\n")
            entries = scan(root, roots=["core"])
            self.assertEqual(len(entries), 1)
            e = entries[0]
            self.assertEqual(e.path, "core/mod.py")
            self.assertIsNotNone(e.ast_hash)
            self.assertEqual(e.line_count, 2)

    def test_empty_root_returns_empty_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "core").mkdir()
            entries = scan(root, roots=["core"])
            self.assertEqual(entries, [])

    def test_scan_never_writes_to_cerebro(self) -> None:
        """Non-mutation boundary: scan must not create .cerebro/ in the target."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/mod.py", "x = 1\n")
            scan(root, roots=["core"])
            self.assertFalse((root / ".cerebro").exists())


# ---------------------------------------------------------------------------
# detector
# ---------------------------------------------------------------------------

class DetectorTests(unittest.TestCase):

    def test_no_drift_when_baseline_equals_current(self) -> None:
        baseline = [_fake_entry("core/a.py", "hash1")]
        current = [_fake_entry("core/a.py", "hash1")]
        report = detect(baseline, current)
        self.assertFalse(report.has_drift)
        self.assertEqual(report.drift_entries, [])

    def test_detects_added_file(self) -> None:
        baseline = [_fake_entry("core/a.py", "hash1")]
        current = [_fake_entry("core/a.py", "hash1"), _fake_entry("core/b.py", "hash2")]
        report = detect(baseline, current)
        self.assertTrue(report.has_drift)
        added = [e for e in report.drift_entries if e.kind == "added"]
        self.assertEqual(len(added), 1)
        self.assertEqual(added[0].path, "core/b.py")
        self.assertIsNone(added[0].baseline_hash)

    def test_detects_removed_file(self) -> None:
        baseline = [_fake_entry("core/a.py", "hash1"), _fake_entry("core/b.py", "hash2")]
        current = [_fake_entry("core/a.py", "hash1")]
        report = detect(baseline, current)
        removed = [e for e in report.drift_entries if e.kind == "removed"]
        self.assertEqual(len(removed), 1)
        self.assertEqual(removed[0].path, "core/b.py")
        self.assertIsNone(removed[0].current_hash)

    def test_detects_modified_file(self) -> None:
        baseline = [_fake_entry("core/a.py", "oldhash")]
        current = [_fake_entry("core/a.py", "newhash")]
        report = detect(baseline, current)
        modified = [e for e in report.drift_entries if e.kind == "modified"]
        self.assertEqual(len(modified), 1)
        self.assertEqual(modified[0].baseline_hash, "oldhash")
        self.assertEqual(modified[0].current_hash, "newhash")

    def test_drift_entries_sorted_by_path(self) -> None:
        baseline = [_fake_entry("core/z.py", "h1")]
        current = [_fake_entry("core/a.py", "h2"), _fake_entry("core/m.py", "h3")]
        report = detect(baseline, current)
        paths = [e.path for e in report.drift_entries]
        self.assertEqual(paths, sorted(paths))

    def test_scanned_files_count_reflects_current(self) -> None:
        baseline: list[FileHashEntry] = []
        current = [_fake_entry("core/a.py"), _fake_entry("core/b.py")]
        report = detect(baseline, current)
        self.assertEqual(report.scanned_files, 2)


# ---------------------------------------------------------------------------
# DriftReport properties
# ---------------------------------------------------------------------------

class DriftReportPropertiesTests(unittest.TestCase):

    def _report(self, entries: list[DriftEntry]) -> DriftReport:
        return DriftReport(
            generated_at="2026-01-01T00:00:00+00:00",
            baseline_snapshot="snap.json",
            scanned_files=5,
            drift_entries=entries,
        )

    def test_has_drift_false_when_no_entries(self) -> None:
        self.assertFalse(self._report([]).has_drift)

    def test_has_drift_true_when_entries_present(self) -> None:
        e = DriftEntry(path="x.py", kind="modified", baseline_hash="a", current_hash="b")
        self.assertTrue(self._report([e]).has_drift)

    def test_summary_no_drift(self) -> None:
        self.assertIn("No drift", self._report([]).summary)

    def test_summary_counts_kinds(self) -> None:
        entries = [
            DriftEntry(path="a.py", kind="modified", baseline_hash="x", current_hash="y"),
            DriftEntry(path="b.py", kind="added", baseline_hash=None, current_hash="z"),
        ]
        summary = self._report(entries).summary
        self.assertIn("1 added", summary)
        self.assertIn("1 modified", summary)


# ---------------------------------------------------------------------------
# baseline
# ---------------------------------------------------------------------------

class BaselineTests(unittest.TestCase):

    def test_roundtrip_save_and_load(self) -> None:
        entries = [
            FileHashEntry(path="core/a.py", ast_hash="abc", line_count=10),
            FileHashEntry(path="cli/b.py", ast_hash="def", line_count=5),
        ]
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "snap.json"
            save_baseline(entries, snap)
            loaded = load_baseline(snap)
            self.assertIsNotNone(loaded)
            assert loaded is not None
            self.assertEqual(len(loaded), 2)
            self.assertEqual(loaded[0].path, "core/a.py")
            self.assertEqual(loaded[0].ast_hash, "abc")
            self.assertEqual(loaded[1].line_count, 5)

    def test_load_missing_file_returns_none(self) -> None:
        self.assertIsNone(load_baseline(Path("/does/not/exist.json")))

    def test_saved_baseline_is_valid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "snap.json"
            save_baseline([_fake_entry("core/a.py")], snap)
            data = json.loads(snap.read_text(encoding="utf-8"))
            # v2 format: object with captured_at + entries list
            self.assertIsInstance(data, dict)
            self.assertIn("captured_at", data)
            self.assertIsInstance(data["entries"], list)
            self.assertEqual(data["entries"][0]["path"], "core/a.py")


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

class ReportTests(unittest.TestCase):

    def _no_drift_report(self) -> DriftReport:
        return DriftReport(
            generated_at="2026-01-01T00:00:00+00:00",
            baseline_snapshot="snap.json",
            scanned_files=3,
            drift_entries=[],
        )

    def _drift_report(self) -> DriftReport:
        return DriftReport(
            generated_at="2026-01-01T00:00:00+00:00",
            baseline_snapshot="snap.json",
            scanned_files=3,
            drift_entries=[
                DriftEntry("core/a.py", "modified", "oldhash1234567890", "newhash1234567890"),
                DriftEntry("core/b.py", "added", None, "addedhash123456"),
                DriftEntry("core/c.py", "removed", "removedhash12345", None),
            ],
        )

    def test_markdown_no_drift_contains_no_drift_message(self) -> None:
        md = to_markdown(self._no_drift_report())
        self.assertIn("No structural drift", md)
        self.assertIn("Non-authoritative", md)

    def test_markdown_drift_lists_all_entries(self) -> None:
        md = to_markdown(self._drift_report())
        self.assertIn("core/a.py", md)
        self.assertIn("core/b.py", md)
        self.assertIn("core/c.py", md)
        self.assertIn("modified", md)
        self.assertIn("added", md)
        self.assertIn("removed", md)

    def test_markdown_is_non_authoritative(self) -> None:
        md = to_markdown(self._no_drift_report())
        self.assertIn("Non-authoritative", md)

    def test_write_report_creates_md_and_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp)
            md_path, json_path = write_report(self._drift_report(), out)
            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("drift_entries", data)
            self.assertEqual(len(data["drift_entries"]), 3)

    def test_json_report_has_summary_and_has_drift_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, json_path = write_report(self._drift_report(), Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertIn("has_drift", data)
            self.assertIn("summary", data)
            self.assertTrue(data["has_drift"])

    def test_write_report_never_writes_to_cerebro(self) -> None:
        """Non-mutation boundary: write_report output must not go into .cerebro/."""
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reports"
            write_report(self._no_drift_report(), out)
            self.assertFalse((Path(tmp) / ".cerebro").exists())


# ---------------------------------------------------------------------------
# end-to-end: scan → detect pipeline
# ---------------------------------------------------------------------------

class EndToEndPipelineTests(unittest.TestCase):

    def test_scan_detect_pipeline_catches_real_modification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = _py(root, "core/mod.py", "x = 1\n")
            baseline = scan(root, roots=["core"])
            # Structural change
            f.write_text("x = 99\n", encoding="utf-8")
            current = scan(root, roots=["core"])
            report = detect(baseline, current)
            self.assertTrue(report.has_drift)
            self.assertEqual(report.drift_entries[0].kind, "modified")

    def test_scan_detect_pipeline_ignores_comment_only_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            f = _py(root, "core/mod.py", "x = 1\n")
            baseline = scan(root, roots=["core"])
            f.write_text("# new comment\nx = 1\n", encoding="utf-8")
            current = scan(root, roots=["core"])
            report = detect(baseline, current)
            self.assertFalse(report.has_drift)

    def test_pipeline_does_not_mutate_canonical_state(self) -> None:
        """Full scan→detect→report pipeline must not touch .cerebro/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            _py(root, "core/mod.py", "x = 1\n")
            baseline = scan(root, roots=["core"])
            current = scan(root, roots=["core"])
            report = detect(baseline, current)
            write_report(report, root / "reports")
            self.assertFalse((root / ".cerebro").exists())



# ---------------------------------------------------------------------------
# staleness integration in detect()
# ---------------------------------------------------------------------------

class DetectorStalenessIntegrationTests(unittest.TestCase):

    def test_detect_without_captured_at_has_no_staleness(self) -> None:
        baseline = [_fake_entry("core/a.py", "h1")]
        current  = [_fake_entry("core/a.py", "h1")]
        report = detect(baseline, current)
        self.assertIsNone(report.staleness_score)
        self.assertIsNone(report.staleness_classification)

    def test_detect_with_captured_at_sets_staleness_fields(self) -> None:
        from datetime import datetime, timezone, timedelta
        captured = (datetime.now(timezone.utc) - timedelta(days=10)).isoformat()
        baseline = [_fake_entry("core/a.py", "h1")]
        current  = [_fake_entry("core/a.py", "h1")]
        report = detect(baseline, current, baseline_captured_at=captured)
        self.assertIsNotNone(report.staleness_score)
        self.assertIsNotNone(report.staleness_classification)
        self.assertIsInstance(report.staleness_score, float)
        self.assertIn(report.staleness_classification,
                      ("fresh", "aging", "stale", "critical"))

    def test_detect_fresh_baseline_no_drift_scores_fresh(self) -> None:
        from datetime import datetime, timezone
        captured = datetime.now(timezone.utc).isoformat()
        baseline = [_fake_entry("core/a.py", "h1")]
        current  = [_fake_entry("core/a.py", "h1")]
        report = detect(baseline, current, baseline_captured_at=captured)
        self.assertEqual(report.staleness_classification, "fresh")
        self.assertLess(report.staleness_score, 0.3)

    def test_detect_old_baseline_with_many_changes_scores_critical(self) -> None:
        from datetime import datetime, timezone, timedelta
        captured = (datetime.now(timezone.utc) - timedelta(days=100)).isoformat()
        baseline = [_fake_entry(f"core/{i}.py", f"old{i}") for i in range(10)]
        current  = [_fake_entry(f"core/{i}.py", f"new{i}") for i in range(10)]
        report = detect(baseline, current, baseline_captured_at=captured)
        self.assertEqual(report.staleness_classification, "critical")
        self.assertGreaterEqual(report.staleness_score, 0.8)

    def test_detect_staleness_included_in_json_report(self) -> None:
        from datetime import datetime, timezone
        import json
        captured = datetime.now(timezone.utc).isoformat()
        baseline = [_fake_entry("core/a.py", "h1")]
        current  = [_fake_entry("core/a.py", "h1")]
        report = detect(baseline, current, baseline_captured_at=captured)
        with tempfile.TemporaryDirectory() as tmp:
            _, json_path = write_report(report, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIn("staleness_score", data)
        self.assertIn("staleness_classification", data)

    def test_detect_no_captured_at_json_report_staleness_null(self) -> None:
        import json
        baseline = [_fake_entry("core/a.py", "h1")]
        current  = [_fake_entry("core/a.py", "h1")]
        report = detect(baseline, current)
        with tempfile.TemporaryDirectory() as tmp:
            _, json_path = write_report(report, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertIsNone(data["staleness_score"])
        self.assertIsNone(data["staleness_classification"])

    def test_load_baseline_with_meta_returns_captured_at(self) -> None:
        from experiments.drift_detection.baseline import load_baseline_with_meta
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "snap.json"
            entries = [_fake_entry("core/a.py")]
            save_baseline(entries, snap)
            result = load_baseline_with_meta(snap)
            self.assertIsNotNone(result)
            loaded_entries, captured_at = result
            self.assertEqual(len(loaded_entries), 1)
            self.assertIsNotNone(captured_at)
            # Must be parseable as ISO-8601
            from datetime import datetime
            datetime.fromisoformat(captured_at)

    def test_load_baseline_with_meta_legacy_v1_no_captured_at(self) -> None:
        """Legacy v1 snapshot (bare array) loads without captured_at."""
        import json
        from experiments.drift_detection.baseline import load_baseline_with_meta
        with tempfile.TemporaryDirectory() as tmp:
            snap = Path(tmp) / "snap.json"
            snap.write_text(json.dumps([
                {"path": "core/a.py", "ast_hash": "abc", "line_count": 1}
            ]), encoding="utf-8")
            result = load_baseline_with_meta(snap)
            self.assertIsNotNone(result)
            entries, captured_at = result
            self.assertEqual(len(entries), 1)
            self.assertIsNone(captured_at)

    def test_load_baseline_with_meta_absent_returns_none(self) -> None:
        from experiments.drift_detection.baseline import load_baseline_with_meta
        result = load_baseline_with_meta(Path("/does/not/exist/snap.json"))
        self.assertIsNone(result)



if __name__ == "__main__":
    unittest.main()
