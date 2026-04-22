from __future__ import annotations

import os
import unittest
import uuid


@unittest.skipUnless(os.name == "nt", "WinCred helpers only run on Windows hosts")
class WindowsCredentialStoreTests(unittest.TestCase):
    def setUp(self) -> None:
        from core.windows_credential_store import delete_generic_credential

        self._created_targets: list[str] = []
        self._delete = delete_generic_credential

    def tearDown(self) -> None:
        for target in self._created_targets:
            try:
                self._delete(target)
            except Exception:
                pass

    def _unique_target(self) -> str:
        target = f"cerebro-test-{uuid.uuid4().hex}"
        self._created_targets.append(target)
        return target

    def test_write_then_read_round_trips_payload(self) -> None:
        from core.windows_credential_store import (
            read_generic_credential,
            write_generic_credential,
        )

        target = self._unique_target()
        payload = b"\x00hello-\xffpayload"

        write_generic_credential(target, payload)
        self.assertEqual(read_generic_credential(target), payload)

    def test_read_returns_none_when_target_not_found(self) -> None:
        from core.windows_credential_store import read_generic_credential

        missing = self._unique_target()
        self._created_targets.remove(missing)

        self.assertIsNone(read_generic_credential(missing))

    def test_delete_returns_false_when_target_not_found(self) -> None:
        from core.windows_credential_store import delete_generic_credential

        missing = self._unique_target()
        self._created_targets.remove(missing)

        self.assertFalse(delete_generic_credential(missing))

    def test_delete_returns_true_after_write(self) -> None:
        from core.windows_credential_store import (
            delete_generic_credential,
            read_generic_credential,
            write_generic_credential,
        )

        target = self._unique_target()
        write_generic_credential(target, b"payload")

        self.assertTrue(delete_generic_credential(target))
        self._created_targets.remove(target)
        self.assertIsNone(read_generic_credential(target))

    def test_write_rejects_empty_target_name(self) -> None:
        from core.windows_credential_store import (
            WindowsCredentialStoreError,
            write_generic_credential,
        )

        with self.assertRaises(WindowsCredentialStoreError):
            write_generic_credential("", b"payload")

    def test_write_rejects_non_bytes_payload(self) -> None:
        from core.windows_credential_store import (
            WindowsCredentialStoreError,
            write_generic_credential,
        )

        with self.assertRaises(WindowsCredentialStoreError):
            write_generic_credential(self._unique_target(), "not-bytes")  # type: ignore[arg-type]

    def test_read_rejects_empty_target_name(self) -> None:
        from core.windows_credential_store import (
            WindowsCredentialStoreError,
            read_generic_credential,
        )

        with self.assertRaises(WindowsCredentialStoreError):
            read_generic_credential("")

    def test_delete_rejects_empty_target_name(self) -> None:
        from core.windows_credential_store import (
            WindowsCredentialStoreError,
            delete_generic_credential,
        )

        with self.assertRaises(WindowsCredentialStoreError):
            delete_generic_credential("")

    def test_empty_payload_round_trips_as_empty_bytes(self) -> None:
        from core.windows_credential_store import (
            read_generic_credential,
            write_generic_credential,
        )

        target = self._unique_target()
        write_generic_credential(target, b"")
        self.assertEqual(read_generic_credential(target), b"")

    def test_overwrite_replaces_payload(self) -> None:
        from core.windows_credential_store import (
            read_generic_credential,
            write_generic_credential,
        )

        target = self._unique_target()
        write_generic_credential(target, b"first")
        write_generic_credential(target, b"second")
        self.assertEqual(read_generic_credential(target), b"second")


class WindowsCredentialStoreFallbackTests(unittest.TestCase):
    """Validate the non-Windows fallback shape exposed via state_store."""

    def test_state_store_fallback_exports_none_on_non_nt(self) -> None:
        from core import state_store

        if os.name == "nt":
            from core.windows_credential_store import (
                WindowsCredentialStoreError as RealError,
            )

            self.assertIs(state_store.WindowsCredentialStoreError, RealError)
            self.assertIsNotNone(state_store.write_generic_credential)
            self.assertIsNotNone(state_store.read_generic_credential)
            self.assertIsNotNone(state_store.delete_generic_credential)
        else:
            self.assertIs(state_store.WindowsCredentialStoreError, RuntimeError)
            self.assertIsNone(state_store.write_generic_credential)
            self.assertIsNone(state_store.read_generic_credential)
            self.assertIsNone(state_store.delete_generic_credential)


if __name__ == "__main__":
    unittest.main()
