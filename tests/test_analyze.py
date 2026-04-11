from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.analyze import run_analyze
from cli.commands.init import run_init
from core.state_store import StateStore


REPO_ROOT = Path(__file__).resolve().parents[1]


class AnalyzeCommandTests(unittest.TestCase):
    def test_analyze_with_valid_state_prints_stable_context_and_opens_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Resume work.",
                    "constraints": ["Do not change API"],
                }
            )
            before = store.read_snapshot()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            after = store.read_snapshot()
            self.assertEqual(exit_code, 0)
            self.assertEqual(
                output,
                "\n".join(
                    [
                        "OK",
                        "analysis_ready: continuity context loaded",
                        "goal: Ship",
                        "summary: Checkpoint is ready.",
                        "next_step: Resume work.",
                        "constraints: 1",
                        "- Do not change API",
                        "sources: 1",
                        "- tracked.txt",
                        f"revision: {before.revision}",
                        f"updated_at: {before.checkpoint.updated_at}",
                        "validation: ok",
                        "",
                    ]
                ),
            )
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.checkpoint, before.checkpoint)
            self.assertEqual(after.sources, before.sources)
            self.assertEqual(after.last_validation.result, "ok")
            self.assertTrue(store.session_path.exists())

    def test_analyze_blocks_when_validation_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            tracked.write_text("changed", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("analysis_blocked", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertFalse(store.session_path.exists())

    def test_analyze_does_not_change_revision_or_registered_context(self) -> None:
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
            before = store.read_snapshot()
            before_state = store.state_path.read_text(encoding="utf-8")

            exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            after = store.read_snapshot()
            after_state = store.state_path.read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertEqual(after.revision, before.revision)
            self.assertEqual(after.checkpoint, before.checkpoint)
            self.assertEqual(after.sources, before.sources)
            self.assertNotEqual(after_state, before_state)

    def test_analyze_subprocess_smoke(self) -> None:
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

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("analysis_ready", result.stdout)
            self.assertIn("goal: Goal", result.stdout)
