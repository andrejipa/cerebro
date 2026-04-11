from __future__ import annotations

import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.schema import build_initial_state
from core.state_store import StateStore, StateStoreError, StateValidationError


class StateStoreTests(unittest.TestCase):
    def test_save_and_load_initial_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            state = build_initial_state()

            store.save_state(state)

            loaded = store.load_state()
            self.assertEqual(loaded, state)

    def test_save_invalid_state_raises_validation_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            state = build_initial_state()
            del state["version"]

            with self.assertRaises(StateValidationError):
                store.save_state(state)

    def test_save_uses_atomic_replace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            state = build_initial_state()
            original_replace = os.replace

            with mock.patch("core.state_store.os.replace", wraps=original_replace) as replace_mock:
                store.save_state(state)

            self.assertEqual(replace_mock.call_count, 1)
            src, dst = replace_mock.call_args[0]
            self.assertTrue(str(src).endswith(".json.tmp"))
            self.assertEqual(Path(dst), store.state_path)
            self.assertTrue(store.state_path.exists())
            self.assertFalse(store.state_path.with_suffix(".json.tmp").exists())

    def test_register_sources_successfully(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["notes.txt"])

            self.assertEqual(updated["revision"], 1)
            self.assertEqual(
                updated["sources"],
                [
                    {
                        "path": "notes.txt",
                        "sha256": store.compute_sha256("notes.txt"),
                        "role": "primary",
                    }
                ],
            )

    def test_register_sources_rejects_absolute_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            with self.assertRaises(StateStoreError):
                store.register_sources([str(source_file.resolve())])

    def test_register_sources_rejects_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            source_file = root / "notes.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            with self.assertRaises(StateStoreError):
                store.register_sources(["../notes.txt"])

    def test_register_sources_rejects_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            outside_dir = Path(tempfile.mkdtemp())
            outside_file = outside_dir / "external.txt"
            outside_file.write_text("outside", encoding="utf-8")
            symlink_path = root / "external-link.txt"
            store = StateStore(root)
            store.save_state(build_initial_state())

            try:
                symlink_path.symlink_to(outside_file)
            except OSError as exc:
                self.skipTest(f"symlink creation not available: {exc}")

            try:
                with self.assertRaises(StateStoreError):
                    store.register_sources(["external-link.txt"])
            finally:
                if symlink_path.exists() or symlink_path.is_symlink():
                    symlink_path.unlink()
                if outside_file.exists():
                    outside_file.unlink()
                outside_dir.rmdir()

    def test_register_sources_deduplicates_and_orders_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "b.txt").write_text("b", encoding="utf-8")
            (root / "a.txt").write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["b.txt", "a.txt", "b.txt"])

            self.assertEqual([item["path"] for item in updated["sources"]], ["a.txt", "b.txt"])

    def test_register_sources_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "a.txt").write_text("a", encoding="utf-8")
            store = StateStore(root)
            store.save_state(build_initial_state())

            updated = store.register_sources(["a.txt"])

            self.assertEqual(updated["revision"], 1)

    def test_register_sources_has_no_partial_write_on_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            good_file = root / "a.txt"
            good_file.write_text("a", encoding="utf-8")
            store = StateStore(root)
            initial = build_initial_state()
            store.save_state(initial)

            with self.assertRaises(StateStoreError):
                store.register_sources(["a.txt", "../bad.txt"])

            loaded = store.load_state()
            self.assertEqual(loaded, initial)

    def test_update_checkpoint_updates_fields_correctly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())

            updated = store.update_checkpoint(
                {
                    "goal": "Ship the fix",
                    "summary": "The regression is isolated to the auth refresh path.",
                    "next_step": "Patch token refresh handling.",
                    "constraints": ["Keep API responses stable"],
                }
            )

            checkpoint = updated["checkpoint"]
            self.assertEqual(checkpoint["goal"], "Ship the fix")
            self.assertEqual(checkpoint["summary"], "The regression is isolated to the auth refresh path.")
            self.assertEqual(checkpoint["next_step"], "Patch token refresh handling.")
            self.assertEqual(checkpoint["constraints"], ["Keep API responses stable"])
            self.assertTrue(checkpoint["updated_at"])

    def test_update_checkpoint_increments_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())

            updated = store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )

            self.assertEqual(updated["revision"], 1)

    def test_update_checkpoint_rejects_field_above_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            initial = build_initial_state()
            store.save_state(initial)

            with self.assertRaises(StateValidationError):
                store.update_checkpoint(
                    {
                        "goal": "x" * 201,
                        "summary": "Summary",
                        "next_step": "Next",
                        "constraints": [],
                    }
                )

            loaded = store.load_state()
            self.assertEqual(loaded, initial)

    def test_open_session_writes_local_session_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())

            session = store.open_session("alice")

            self.assertEqual(session["actor"], "alice")
            self.assertEqual(session["based_on_revision"], 0)
            self.assertTrue(store.session_path.exists())

    def test_close_session_does_not_fail_without_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(tmp_dir)
            store.save_state(build_initial_state())

            store.close_session()

            self.assertFalse(store.session_path.exists())


if __name__ == "__main__":
    unittest.main()
