from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from cli.commands.resume import run_resume
from core.schema import build_initial_state
from core.read_models import CheckpointRecord, SourceRecord, StateSnapshot
from core.state_store import StateStore


class CompatibilitySuiteTests(unittest.TestCase):
    def test_legacy_agent_runtime_shape_is_canonicalized_on_load(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            legacy_state = build_initial_state()
            legacy_state["agent_runtime"] = {
                "plan": {
                    "goal": "Legacy",
                    "summary": "v2 layout",
                    "status": "ready",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Legacy task",
                            "status": "ready",
                            "details": "Legacy task",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                        }
                    ],
                    "updated_at": "",
                },
                "execution_policy": {
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                },
                "actions": [],
                "verification": {
                    "commands": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                        }
                    ],
                    "last_run_at": "",
                    "status": "idle",
                    "checks": [],
                },
                "memory": {"notes": []},
                "audit": {
                    "last_event_at": "",
                    "last_event_type": "",
                    "last_action_id": "",
                    "trace_thread_id": "bootstrap",
                    "next_event_id": 1,
                    "trace_status": "healthy",
                    "trace_integrity": "reliable",
                    "last_trace_error_at": "",
                    "last_trace_error": "",
                    "rollback_points": [],
                    "used_batch_ids": [],
                },
            }
            (cerebro_dir / "state.json").write_text(json.dumps(legacy_state, indent=2), encoding="utf-8")

            loaded = StateStore(root).load_state()

            self.assertEqual(loaded["agent_runtime"]["plan"]["current_task_id"], "")
            self.assertEqual(loaded["agent_runtime"]["plan"]["tasks"][0]["action_ids"], [])
            self.assertEqual(loaded["agent_runtime"]["command_registry"]["commands"][0]["id"], "cmd-001")
            self.assertEqual(loaded["agent_runtime"]["verification"]["required_command_ids"], ["cmd-001"])
            self.assertEqual(loaded["agent_runtime"]["approvals"]["items"], [])
            self.assertEqual(loaded["agent_runtime"]["batch_registry"]["used_ids"], [])

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
            invalid_state = build_initial_state()
            invalid_state["version"] = "3"
            (cerebro_dir / "state.json").write_text(json.dumps(invalid_state, indent=2), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_schema")
            self.assertTrue(any(item["code"] == "unsupported_schema_version" for item in result["errors"][1:]))
