from __future__ import annotations

import tempfile
import unittest
from copy import deepcopy
from pathlib import Path
from unittest import mock

from core.schema import build_initial_state
from core.state_store import StateStore


class StateStoreDigestTests(unittest.TestCase):
    def test_get_state_digest_returns_non_empty_sha256_string(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            store.save_state(build_initial_state())

            digest = store.get_state_digest()

            self.assertRegex(digest, r"^sha256:[0-9a-f]{64}$")

    def test_get_state_digest_is_deterministic_for_same_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            state = build_initial_state()
            store.save_state(state)

            self.assertEqual(store.get_state_digest(), store.get_state_digest())

    def test_get_state_digest_accepts_explicit_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            state = build_initial_state()

            explicit_digest = store.get_state_digest(state)

            self.assertRegex(explicit_digest, r"^sha256:[0-9a-f]{64}$")

    def test_load_state_does_not_propagate_internal_digest_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            state = build_initial_state()
            store.save_state(state)

            with mock.patch("core.state_store.canonical_state_digest", side_effect=RuntimeError("digest failed")):
                loaded = store.load_state()

            self.assertEqual(loaded, state)

    def test_load_state_returns_same_result_with_and_without_digest_active(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = StateStore(Path(tmp_dir))
            state = build_initial_state()
            store.save_state(state)

            loaded_with_digest = store.load_state()
            with mock.patch("core.state_store.canonical_state_digest", return_value="sha256:" + "0" * 64):
                loaded_with_mocked_digest = store.load_state()

            self.assertEqual(loaded_with_digest, loaded_with_mocked_digest)
            self.assertEqual(loaded_with_digest, deepcopy(state))


if __name__ == "__main__":
    unittest.main()
