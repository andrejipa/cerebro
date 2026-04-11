from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from cli.commands.resume import run_resume
from core.read_models import CheckpointRecord, SourceRecord, StateSnapshot
from core.state_store import StateStore


class CompatibilitySuiteTests(unittest.TestCase):
    def test_read_snapshot_returns_stable_read_models(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": ["Constraint"],
                }
            )

            snapshot = store.read_snapshot()

            self.assertIsInstance(snapshot, StateSnapshot)
            self.assertIsInstance(snapshot.checkpoint, CheckpointRecord)
            self.assertEqual(len(snapshot.sources), 1)
            self.assertIsInstance(snapshot.sources[0], SourceRecord)
            self.assertEqual(snapshot.sources[0].path, "tracked.txt")
            self.assertEqual(snapshot.checkpoint.goal, "Goal")

    def test_full_flow_remains_compatible(self) -> None:
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
                    "constraints": [],
                }
            )

            exit_code = run_resume(root, type("Args", (), {"actor": "alice"}))

            self.assertEqual(exit_code, 0)
            self.assertTrue(store.session_path.exists())
            result = store.validate_state()
            self.assertTrue(result["ok"])

    def test_unsupported_schema_version_fails_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid_state = {
                "version": "2",
                "revision": 0,
                "sources": [],
                "checkpoint": {
                    "goal": "",
                    "summary": "",
                    "next_step": "",
                    "constraints": [],
                    "updated_at": "",
                },
                "last_validation": {
                    "validated_at": "",
                    "result": "fail",
                    "details": [],
                },
            }
            (cerebro_dir / "state.json").write_text(json.dumps(invalid_state, indent=2), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_schema")
            self.assertTrue(any(item["code"] == "unsupported_schema_version" for item in result["errors"][1:]))
