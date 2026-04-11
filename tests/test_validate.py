from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from cli.commands.checkpoint import run_checkpoint
from cli.commands.init import run_init
from cli.commands.import_context import run_import_context
from cli.commands.resume import run_resume
from core.schema import build_initial_state
from core.state_store import StateStore


class ValidateCommandTests(unittest.TestCase):
    def test_init_creates_expected_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            exit_code = run_init(root)

            self.assertEqual(exit_code, 0)
            self.assertTrue((root / ".cerebro" / "state.json").exists())
            self.assertTrue((root / ".cerebro" / "logs" / "events.jsonl").exists())
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())

    def test_validate_accepts_valid_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.save_state(build_initial_state())

            result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])

    def test_validate_reports_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            (cerebro_dir / "state.json").write_text("{invalid", encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_json")

    def test_validate_reports_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid_state = build_initial_state()
            invalid_state["revision"] = "1"
            (cerebro_dir / "state.json").write_text(
                json.dumps(invalid_state, indent=2),
                encoding="utf-8",
            )

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_schema")

    def test_validate_ok_with_intact_registered_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])

            result = store.validate_state()

            self.assertTrue(result["ok"])
            self.assertEqual(result["errors"], [])
            updated = store.load_state()
            self.assertEqual(updated["last_validation"]["result"], "ok")

    def test_validate_fail_when_registered_file_is_removed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])
            source_file.unlink()

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "source_missing")

    def test_validate_fail_when_registered_file_hash_changes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "source_hash_mismatch")

    def test_import_context_command_replaces_sources_after_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            first = root / "a.txt"
            second = root / "b.txt"
            first.write_text("a", encoding="utf-8")
            second.write_text("b", encoding="utf-8")
            run_init(root, None)

            args = type("Args", (), {"files": ["b.txt", "a.txt", "b.txt"]})
            with mock.patch("builtins.input", return_value="y"):
                exit_code = run_import_context(root, args)

            self.assertEqual(exit_code, 0)
            state = StateStore(root).load_state()
            self.assertEqual([item["path"] for item in state["sources"]], ["a.txt", "b.txt"])
            self.assertEqual(state["revision"], 1)

    def test_import_context_command_does_not_save_without_confirmation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "a.txt"
            source_file.write_text("a", encoding="utf-8")
            run_init(root, None)

            args = type("Args", (), {"files": ["a.txt"]})
            with mock.patch("builtins.input", return_value="n"):
                exit_code = run_import_context(root, args)

            self.assertEqual(exit_code, 0)
            state = StateStore(root).load_state()
            self.assertEqual(state["sources"], [])
            self.assertEqual(state["revision"], 0)

    def test_validate_fails_with_session_invalid_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text("{invalid", encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_invalid_json")

    def test_validate_fails_with_session_invalid_schema(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text(
                json.dumps(
                    {
                        "opened_at": "2026-04-10T00:00:00+00:00",
                        "based_on_revision": 0,
                    }
                ),
                encoding="utf-8",
            )

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_invalid_schema")

    def test_validate_fails_with_session_revision_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text(
                json.dumps(
                    {
                        "opened_at": "2026-04-10T00:00:00+00:00",
                        "actor": "alice",
                        "based_on_revision": 1,
                    }
                ),
                encoding="utf-8",
            )

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "session_revision_invalid")

    def test_resume_with_valid_state_creates_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready to continue.",
                    "next_step": "Open the target file.",
                    "constraints": ["Do not change public API"],
                }
            )

            args = type("Args", (), {"actor": "alice"})
            exit_code = run_resume(root, args)

            self.assertEqual(exit_code, 0)
            session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "alice")
            self.assertEqual(session["based_on_revision"], 1)

    def test_resume_blocks_when_validate_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")

            args = type("Args", (), {"actor": "alice"})
            exit_code = run_resume(root, args)

            self.assertEqual(exit_code, 1)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())

    def test_resume_overwrites_existing_session(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.update_checkpoint(
                {
                    "goal": "Ship",
                    "summary": "Ready.",
                    "next_step": "Continue.",
                    "constraints": [],
                }
            )
            store.open_session("old")

            args = type("Args", (), {"actor": "new"})
            exit_code = run_resume(root, args)

            self.assertEqual(exit_code, 0)
            session = json.loads((root / ".cerebro" / "session.local.json").read_text(encoding="utf-8"))
            self.assertEqual(session["actor"], "new")
            self.assertEqual(session["based_on_revision"], 1)

    def test_checkpoint_command_removes_session_after_success(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.open_session("alice")

            args = type(
                "Args",
                (),
                {
                    "goal": "Ship",
                    "summary": "Checkpoint updated.",
                    "next_step": "Run tests.",
                    "constraint": ["Keep behavior stable"],
                },
            )
            exit_code = run_checkpoint(root, args)

            self.assertEqual(exit_code, 0)
            self.assertFalse((root / ".cerebro" / "session.local.json").exists())
            state = store.load_state()
            self.assertEqual(state["checkpoint"]["goal"], "Ship")
            self.assertEqual(state["revision"], 1)


if __name__ == "__main__":
    unittest.main()
