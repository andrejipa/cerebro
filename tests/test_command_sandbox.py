from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path

from core.command_sandbox import capture_tree_manifest, prepare_project_sandbox, summarize_manifest_diff


class CommandSandboxTests(unittest.TestCase):
    def test_prepare_project_sandbox_clones_workspace_without_mutating_original_tree(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            nested = root / "notes" / "draft.txt"
            nested.parent.mkdir(parents=True, exist_ok=True)
            tracked.write_text("hello\n", encoding="utf-8")
            nested.write_text("draft\n", encoding="utf-8")

            sandbox_dir, sandbox_root = prepare_project_sandbox(root)
            try:
                self.assertEqual((sandbox_root / "tracked.txt").read_text(encoding="utf-8"), "hello\n")
                self.assertEqual((sandbox_root / "notes" / "draft.txt").read_text(encoding="utf-8"), "draft\n")

                (sandbox_root / "tracked.txt").write_text("sandbox-only\n", encoding="utf-8")
                (sandbox_root / "notes" / "new.txt").write_text("created in sandbox\n", encoding="utf-8")

                self.assertEqual(tracked.read_text(encoding="utf-8"), "hello\n")
                self.assertFalse((root / "notes" / "new.txt").exists())
            finally:
                sandbox_dir.cleanup()

            self.assertFalse(sandbox_root.exists())

    def test_capture_tree_manifest_diff_ignores_directory_mtime_churn_but_reports_file_drift(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            directory = root / "notes"
            tracked = directory / "draft.txt"
            directory.mkdir(parents=True, exist_ok=True)
            tracked.write_text("before\n", encoding="utf-8")

            before = capture_tree_manifest(root)

            stat = directory.stat()
            os.utime(directory, ns=(stat.st_atime_ns, stat.st_mtime_ns + 1))
            after_dir_only = capture_tree_manifest(root)
            self.assertEqual(summarize_manifest_diff(before, after_dir_only), "")

            tracked.write_text("after\n", encoding="utf-8")
            after_file_change = capture_tree_manifest(root)
            summary = summarize_manifest_diff(before, after_file_change)

            self.assertIn("changed notes/draft.txt", summary)


if __name__ == "__main__":
    unittest.main()
