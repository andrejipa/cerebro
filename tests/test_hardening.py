from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core.schema import MAX_SOURCES, build_initial_state
from core.state_store import StateStore, StateStoreError, StateValidationError
from tests.runtime_fixtures import seed_registered_source


class HardeningTests(unittest.TestCase):
    def test_validate_does_not_change_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["tracked.txt"])

            before = store.load_state()["revision"]
            result = store.validate_state()
            after = store.load_state()["revision"]

            self.assertTrue(result["ok"])
            self.assertEqual(before, after)

    def test_checkpoint_does_not_change_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["tracked.txt"])
            before_sources = store.load_state()["sources"]

            updated = store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )

            self.assertEqual(updated["sources"], before_sources)

    def test_open_session_does_not_change_revision(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.initialize()
            seed_registered_source(root)
            before = store.load_state()["revision"]

            store.open_session("alice")

            after = store.load_state()["revision"]
            self.assertEqual(before, after)

    def test_validate_fails_for_duplicate_and_unsorted_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid = build_initial_state()
            invalid["sources"] = [
                {"path": "b.txt", "sha256": "a" * 64, "role": "primary"},
                {"path": "a.txt", "sha256": "b" * 64, "role": "primary"},
                {"path": "a.txt", "sha256": "c" * 64, "role": "primary"},
            ]
            (cerebro_dir / "state.json").write_text(json.dumps(invalid, indent=2), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            codes = [item["code"] for item in result["errors"]]
            self.assertIn("state_invalid_schema", codes)
            messages = [item["message"] for item in result["errors"]]
            self.assertTrue(any("duplicate source path" in message for message in messages))
            self.assertTrue(any("ordered lexically" in message for message in messages))

    def test_validate_fails_for_invalid_sha256_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid = build_initial_state()
            invalid["sources"] = [{"path": "a.txt", "sha256": "123", "role": "primary"}]
            (cerebro_dir / "state.json").write_text(json.dumps(invalid, indent=2), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "state_invalid_schema")
            self.assertTrue(any(item["code"] == "invalid_source_sha256" for item in result["errors"][1:]))

    def test_validate_fails_when_sources_exceed_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir(parents=True, exist_ok=True)
            invalid = build_initial_state()
            invalid["sources"] = [
                {"path": f"file-{index}.txt", "sha256": "a" * 64, "role": "primary"}
                for index in range(MAX_SOURCES + 1)
            ]
            (cerebro_dir / "state.json").write_text(json.dumps(invalid, indent=2), encoding="utf-8")

            result = StateStore(root).validate_state()

            self.assertFalse(result["ok"])
            self.assertTrue(any("cannot contain more than" in item["message"] for item in result["errors"]))

    def test_validate_fails_when_registered_file_becomes_symlink_outside_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.initialize()
            store.register_sources(["tracked.txt"])

            outside_dir = Path(tempfile.mkdtemp())
            outside_file = outside_dir / "external.txt"
            outside_file.write_text("outside", encoding="utf-8")

            try:
                tracked.unlink()
                tracked.symlink_to(outside_file)
            except OSError as exc:
                if tracked.exists() or tracked.is_symlink():
                    tracked.unlink()
                outside_file.unlink()
                outside_dir.rmdir()
                self.skipTest(f"symlink creation not available: {exc}")

            try:
                result = store.validate_state()
                self.assertFalse(result["ok"])
                self.assertEqual(result["errors"][0]["code"], "source_outside_root")
            finally:
                if tracked.exists() or tracked.is_symlink():
                    tracked.unlink()
                if outside_file.exists():
                    outside_file.unlink()
                outside_dir.rmdir()

    def test_save_state_preserves_original_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            original = build_initial_state()
            store.save_state(original)
            updated = build_initial_state()
            updated["revision"] = 1

            with mock.patch("core.state_store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(StateStoreError):
                    store.save_state(updated)

            loaded = store.load_state()
            self.assertEqual(loaded, original)
            self.assertFalse(store.state_path.with_suffix(".json.tmp").exists())

    def test_open_session_leaves_no_partial_file_when_replace_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = StateStore(root)
            store.initialize()
            seed_registered_source(root)

            with mock.patch("core.state_store.os.replace", side_effect=OSError("replace failed")):
                with self.assertRaises(StateStoreError):
                    store.open_session("alice")

            self.assertFalse(store.session_path.exists())
