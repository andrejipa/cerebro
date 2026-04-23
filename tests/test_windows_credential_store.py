from __future__ import annotations

import ctypes
import os
import unittest
from unittest import mock


@unittest.skipUnless(os.name == "nt", "WinCred helpers only run on Windows hosts")
class WindowsCredentialStoreTests(unittest.TestCase):
    def _module(self):
        import core.windows_credential_store as wincred

        return wincred

    def _build_credential(self, *, target_name: str, payload: bytes, username: str = ""):
        wincred = self._module()
        blob_buffer = None
        blob_pointer = None
        if payload:
            blob_buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
            blob_pointer = ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_ubyte))

        credential = wincred.CREDENTIALW()
        credential.Type = wincred.CRED_TYPE_GENERIC
        credential.TargetName = target_name
        credential.CredentialBlobSize = len(payload)
        credential.CredentialBlob = blob_pointer
        credential.Persist = wincred.CRED_PERSIST_LOCAL_MACHINE
        credential.AttributeCount = 0
        credential.Attributes = None
        credential.UserName = username
        return credential, blob_buffer

    def test_write_passes_payload_to_credwrite(self) -> None:
        wincred = self._module()
        seen: dict[str, object] = {}

        def fake_write(credential_ptr, flags):
            credential = ctypes.cast(credential_ptr, ctypes.POINTER(wincred.CREDENTIALW)).contents
            seen["target_name"] = credential.TargetName
            seen["persist"] = credential.Persist
            seen["flags"] = flags
            seen["username"] = credential.UserName
            if credential.CredentialBlobSize == 0:
                seen["payload"] = b""
            else:
                seen["payload"] = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            return True

        with mock.patch.object(wincred._ADVAPI32, "CredWriteW", side_effect=fake_write):
            wincred.write_generic_credential("cred-target", b"\x00hello-\xffpayload", username="alice")

        self.assertEqual(seen["target_name"], "cred-target")
        self.assertEqual(seen["payload"], b"\x00hello-\xffpayload")
        self.assertEqual(seen["username"], "alice")
        self.assertEqual(seen["persist"], wincred.CRED_PERSIST_LOCAL_MACHINE)
        self.assertEqual(seen["flags"], 0)

    def test_write_handles_empty_payload(self) -> None:
        wincred = self._module()
        seen: dict[str, object] = {}

        def fake_write(credential_ptr, flags):
            credential = ctypes.cast(credential_ptr, ctypes.POINTER(wincred.CREDENTIALW)).contents
            seen["payload_size"] = credential.CredentialBlobSize
            seen["payload_ptr"] = credential.CredentialBlob
            return True

        with mock.patch.object(wincred._ADVAPI32, "CredWriteW", side_effect=fake_write):
            wincred.write_generic_credential("cred-target", b"")

        self.assertEqual(seen["payload_size"], 0)
        self.assertFalse(seen["payload_ptr"])

    def test_write_raises_when_credwrite_fails(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredWriteW", return_value=False):
            with mock.patch("core.windows_credential_store.ctypes.get_last_error", return_value=5):
                with self.assertRaises(wincred.WindowsCredentialStoreError) as exc_info:
                    wincred.write_generic_credential("cred-target", b"payload")

        self.assertIn("CredWriteW failed: 5", str(exc_info.exception))

    def test_read_returns_none_when_target_not_found(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredReadW", return_value=False):
            with mock.patch("core.windows_credential_store.ctypes.get_last_error", return_value=wincred.ERROR_NOT_FOUND):
                self.assertIsNone(wincred.read_generic_credential("missing-target"))

    def test_read_returns_payload_and_frees_credential(self) -> None:
        wincred = self._module()
        credential, blob_buffer = self._build_credential(target_name="cred-target", payload=b"payload")
        credential_ptr = ctypes.pointer(credential)
        keeper = {"credential": credential, "blob_buffer": blob_buffer, "credential_ptr": credential_ptr}

        def fake_read(_target_name, _cred_type, _flags, output_ptr):
            cast_output = ctypes.cast(output_ptr, ctypes.POINTER(ctypes.POINTER(wincred.CREDENTIALW)))
            cast_output[0] = keeper["credential_ptr"]
            return True

        with mock.patch.object(wincred._ADVAPI32, "CredReadW", side_effect=fake_read):
            with mock.patch.object(wincred._ADVAPI32, "CredFree", return_value=None) as free_mock:
                payload = wincred.read_generic_credential("cred-target")

        self.assertEqual(payload, b"payload")
        free_mock.assert_called_once()

    def test_read_returns_empty_bytes_when_blob_is_empty(self) -> None:
        wincred = self._module()
        credential, blob_buffer = self._build_credential(target_name="cred-target", payload=b"")
        credential_ptr = ctypes.pointer(credential)
        keeper = {"credential": credential, "blob_buffer": blob_buffer, "credential_ptr": credential_ptr}

        def fake_read(_target_name, _cred_type, _flags, output_ptr):
            cast_output = ctypes.cast(output_ptr, ctypes.POINTER(ctypes.POINTER(wincred.CREDENTIALW)))
            cast_output[0] = keeper["credential_ptr"]
            return True

        with mock.patch.object(wincred._ADVAPI32, "CredReadW", side_effect=fake_read):
            with mock.patch.object(wincred._ADVAPI32, "CredFree", return_value=None):
                payload = wincred.read_generic_credential("cred-target")

        self.assertEqual(payload, b"")

    def test_read_raises_when_credread_fails_for_other_reason(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredReadW", return_value=False):
            with mock.patch("core.windows_credential_store.ctypes.get_last_error", return_value=13):
                with self.assertRaises(wincred.WindowsCredentialStoreError) as exc_info:
                    wincred.read_generic_credential("cred-target")

        self.assertIn("CredReadW failed: 13", str(exc_info.exception))

    def test_delete_returns_false_when_target_not_found(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredDeleteW", return_value=False):
            with mock.patch("core.windows_credential_store.ctypes.get_last_error", return_value=wincred.ERROR_NOT_FOUND):
                self.assertFalse(wincred.delete_generic_credential("missing-target"))

    def test_delete_returns_true_on_success(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredDeleteW", return_value=True) as delete_mock:
            self.assertTrue(wincred.delete_generic_credential("cred-target"))

        delete_mock.assert_called_once_with("cred-target", wincred.CRED_TYPE_GENERIC, 0)

    def test_delete_raises_when_creddelete_fails_for_other_reason(self) -> None:
        wincred = self._module()

        with mock.patch.object(wincred._ADVAPI32, "CredDeleteW", return_value=False):
            with mock.patch("core.windows_credential_store.ctypes.get_last_error", return_value=22):
                with self.assertRaises(wincred.WindowsCredentialStoreError) as exc_info:
                    wincred.delete_generic_credential("cred-target")

        self.assertIn("CredDeleteW failed: 22", str(exc_info.exception))

    def test_write_rejects_empty_target_name(self) -> None:
        wincred = self._module()

        with self.assertRaises(wincred.WindowsCredentialStoreError):
            wincred.write_generic_credential("", b"payload")

    def test_write_rejects_non_bytes_payload(self) -> None:
        wincred = self._module()

        with self.assertRaises(wincred.WindowsCredentialStoreError):
            wincred.write_generic_credential("cred-target", "not-bytes")  # type: ignore[arg-type]

    def test_read_rejects_empty_target_name(self) -> None:
        wincred = self._module()

        with self.assertRaises(wincred.WindowsCredentialStoreError):
            wincred.read_generic_credential("")

    def test_delete_rejects_empty_target_name(self) -> None:
        wincred = self._module()

        with self.assertRaises(wincred.WindowsCredentialStoreError):
            wincred.delete_generic_credential("")


class WindowsCredentialStoreFallbackTests(unittest.TestCase):
    """Validate the non-Windows fallback shape exposed via state_store."""

    def test_state_store_fallback_exports_none_on_non_nt(self) -> None:
        from core import state_store

        if os.name == "nt":
            from core.windows_credential_store import WindowsCredentialStoreError as real_error

            self.assertIs(state_store.WindowsCredentialStoreError, real_error)
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
