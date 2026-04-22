from __future__ import annotations

import io
import json
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cli.commands.apply import run_apply
from cli.commands.init import run_init
from core.action_runtime import ActionRuntimeError, apply_action
from core.agent_runtime import build_initial_agent_runtime
from core.state_store import StateStore


class ActionRuntimeCommandTests(unittest.TestCase):
    def test_exec_command_rejects_command_cwd_that_resolves_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Reject escaped cwd",
                    "summary": "apply must fail closed when command cwd escapes the workspace root.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["escaped cwd is rejected"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": "../escape",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "workspace_write",
                            "risk": "medium",
                            "allow_in_verify": False,
                        }
                    ],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run escaped cwd command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("action_rejected", output.getvalue())
            self.assertIn("command cwd resolves outside root: ../escape", output.getvalue())
            self.assertEqual(store.read_agent_runtime()["actions"], [])

    def test_exec_command_launch_failure_is_structured_and_audited(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Launch failure",
                    "summary": "Missing executables must fail cleanly.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["launch failure is explicit"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["__definitely_missing_executable__"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "workspace_write",
                            "risk": "medium",
                            "allow_in_verify": False,
                        }
                    ],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run missing command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("action_rejected", output.getvalue())
            self.assertIn("failed to execute command_id cmd-001", output.getvalue())
            self.assertNotIn("internal_error", output.getvalue())
            self.assertEqual(store.read_agent_runtime()["actions"], [])

            recent_events = store.read_recent_events(limit=8)
            matching = [event for event in recent_events if event.get("event") == "apply_failed" and event.get("action_id") == "act-command"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["reason_code"], "command_execution_exception")

    def test_exec_command_artifact_write_failure_records_failed_action(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("seed\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Artifact persistence failure",
                    "summary": "Artifact write failures must keep a canonical failed action record.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run mutating command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["artifact persistence failure is recorded canonically"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                sys.executable,
                                "-c",
                                (
                                    "from pathlib import Path; "
                                    "path = Path('mutated.txt'); "
                                    "existing = path.read_text(encoding='utf-8') if path.exists() else ''; "
                                    "path.write_text(existing + 'ran\\n', encoding='utf-8'); "
                                    "print('stdout ok'); "
                                    "import sys; "
                                    "sys.stderr.write('stderr ok\\n')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "workspace_write",
                            "risk": "medium",
                            "allow_in_verify": False,
                        }
                    ],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run mutating command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            original_write_text = Path.write_text

            def flaky_write_text(path: Path, text: str, *args, **kwargs) -> int:
                if (
                    path.name == "stderr.txt"
                    and path.parent.name == "act-command"
                    and path.parent.parent.name == "actions"
                ):
                    raise OSError("forced stderr artifact write failure")
                return original_write_text(path, text, *args, **kwargs)

            output = io.StringIO()
            with patch("pathlib.Path.write_text", new=flaky_write_text):
                with redirect_stdout(output):
                    exit_code = run_apply(
                        root,
                        type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                    )

            self.assertEqual(exit_code, 1)
            self.assertIn("action_failed", output.getvalue())
            self.assertNotIn("internal_error", output.getvalue())
            self.assertEqual(tracked.read_text(encoding="utf-8"), "seed\n")
            self.assertEqual((root / "mutated.txt").read_text(encoding="utf-8"), "ran\n")

            runtime = store.read_agent_runtime()
            self.assertEqual(len(runtime["actions"]), 1)
            action_record = runtime["actions"][0]
            self.assertEqual(action_record["id"], "act-command")
            self.assertEqual(action_record["status"], "failed")
            self.assertEqual(action_record["artifact_refs"], [])
            self.assertEqual(action_record["details"]["exit_code"], 0)
            self.assertIn("failed to persist command artifacts", action_record["details"]["failure_message"])

            recent_events = store.read_recent_events(limit=8)
            matching = [
                event
                for event in recent_events
                if event.get("event") == "action_recorded" and event.get("action_id") == "act-command"
            ]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["status"], "failed")


class ActionRuntimePolicyBoundaryTests(unittest.TestCase):
    def _build_agent_runtime(self) -> dict:
        runtime = build_initial_agent_runtime()
        runtime["execution_policy"]["autonomy_level"] = "A2"
        runtime["execution_policy"]["approval_required_kinds"] = ["fs.write_patch"]
        return runtime

    def test_apply_action_blocks_destructive_create_file_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            draft = root / "draft.txt"
            draft.write_text("before\n", encoding="utf-8")

            with self.assertRaises(ActionRuntimeError) as ctx:
                apply_action(
                    root,
                    store,
                    self._build_agent_runtime(),
                    {
                        "id": "act-overwrite-direct",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft directly",
                        "path": "draft.txt",
                        "content": "after\n",
                        "overwrite": True,
                    },
                    {},
                    set(),
                )

            self.assertIn("requires a non-empty approval_id", str(ctx.exception))
            self.assertEqual(draft.read_text(encoding="utf-8"), "before\n")
            self.assertFalse((store.artifacts_dir / "actions" / "act-overwrite-direct").exists())

    def test_apply_action_blocks_destructive_move_without_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            source = root / "source.txt"
            target = root / "target.txt"
            source.write_text("source\n", encoding="utf-8")
            target.write_text("target\n", encoding="utf-8")

            with self.assertRaises(ActionRuntimeError) as ctx:
                apply_action(
                    root,
                    store,
                    self._build_agent_runtime(),
                    {
                        "id": "act-move-direct",
                        "kind": "fs.move",
                        "summary": "move over existing target directly",
                        "from": "source.txt",
                        "to": "target.txt",
                        "overwrite": True,
                    },
                    {},
                    set(),
                )

            self.assertIn("requires a non-empty approval_id", str(ctx.exception))
            self.assertEqual(source.read_text(encoding="utf-8"), "source\n")
            self.assertEqual(target.read_text(encoding="utf-8"), "target\n")
            self.assertFalse((store.artifacts_dir / "actions" / "act-move-direct").exists())


if __name__ == "__main__":
    unittest.main()
