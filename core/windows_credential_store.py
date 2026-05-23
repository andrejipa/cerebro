"""Minimal WinCred helpers for session live-proof storage on Windows."""

from __future__ import annotations

import ctypes
from ctypes import wintypes


CRED_TYPE_GENERIC = 1
CRED_PERSIST_LOCAL_MACHINE = 2
ERROR_NOT_FOUND = 1168


class WindowsCredentialStoreError(Exception):
    """Raised when WinCred operations fail."""


class FILETIME(ctypes.Structure):
    _fields_ = [
        ("dwLowDateTime", wintypes.DWORD),
        ("dwHighDateTime", wintypes.DWORD),
    ]


class CREDENTIAL_ATTRIBUTEW(ctypes.Structure):
    _fields_ = [
        ("Keyword", wintypes.LPWSTR),
        ("Flags", wintypes.DWORD),
        ("ValueSize", wintypes.DWORD),
        ("Value", ctypes.POINTER(ctypes.c_ubyte)),
    ]


class CREDENTIALW(ctypes.Structure):
    _fields_ = [
        ("Flags", wintypes.DWORD),
        ("Type", wintypes.DWORD),
        ("TargetName", wintypes.LPWSTR),
        ("Comment", wintypes.LPWSTR),
        ("LastWritten", FILETIME),
        ("CredentialBlobSize", wintypes.DWORD),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", wintypes.DWORD),
        ("AttributeCount", wintypes.DWORD),
        ("Attributes", ctypes.POINTER(CREDENTIAL_ATTRIBUTEW)),
        ("TargetAlias", wintypes.LPWSTR),
        ("UserName", wintypes.LPWSTR),
    ]


_ADVAPI32 = ctypes.WinDLL("Advapi32", use_last_error=True)
_ADVAPI32.CredWriteW.argtypes = [ctypes.POINTER(CREDENTIALW), wintypes.DWORD]
_ADVAPI32.CredWriteW.restype = wintypes.BOOL
_ADVAPI32.CredReadW.argtypes = [
    wintypes.LPCWSTR,
    wintypes.DWORD,
    wintypes.DWORD,
    ctypes.POINTER(ctypes.POINTER(CREDENTIALW)),
]
_ADVAPI32.CredReadW.restype = wintypes.BOOL
_ADVAPI32.CredDeleteW.argtypes = [wintypes.LPCWSTR, wintypes.DWORD, wintypes.DWORD]
_ADVAPI32.CredDeleteW.restype = wintypes.BOOL
_ADVAPI32.CredFree.argtypes = [ctypes.c_void_p]
_ADVAPI32.CredFree.restype = None


def write_generic_credential(target_name: str, payload: bytes, *, username: str = "") -> None:
    """Write one generic credential payload to the current user's credential set."""
    if not isinstance(target_name, str) or not target_name:
        raise WindowsCredentialStoreError("credential target_name must be a non-empty string")
    if not isinstance(payload, bytes):
        raise WindowsCredentialStoreError("credential payload must be raw bytes")

    blob_buffer = None
    blob_pointer = None
    if payload:
        blob_buffer = (ctypes.c_ubyte * len(payload)).from_buffer_copy(payload)
        blob_pointer = ctypes.cast(blob_buffer, ctypes.POINTER(ctypes.c_ubyte))

    credential = CREDENTIALW()
    credential.Type = CRED_TYPE_GENERIC
    credential.TargetName = target_name
    credential.CredentialBlobSize = len(payload)
    credential.CredentialBlob = blob_pointer
    credential.Persist = CRED_PERSIST_LOCAL_MACHINE
    credential.AttributeCount = 0
    credential.Attributes = None
    credential.UserName = username or ""

    if not _ADVAPI32.CredWriteW(ctypes.byref(credential), 0):
        raise WindowsCredentialStoreError(f"CredWriteW failed: {ctypes.get_last_error()}")


def read_generic_credential(target_name: str) -> bytes | None:
    """Read one generic credential payload from the current user's credential set."""
    if not isinstance(target_name, str) or not target_name:
        raise WindowsCredentialStoreError("credential target_name must be a non-empty string")

    credential_ptr = ctypes.POINTER(CREDENTIALW)()
    if not _ADVAPI32.CredReadW(target_name, CRED_TYPE_GENERIC, 0, ctypes.byref(credential_ptr)):
        error_code = ctypes.get_last_error()
        if error_code == ERROR_NOT_FOUND:
            return None
        raise WindowsCredentialStoreError(f"CredReadW failed: {error_code}")

    try:
        credential = credential_ptr.contents
        if not credential.CredentialBlob or credential.CredentialBlobSize == 0:
            return b""
        return ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
    finally:
        _ADVAPI32.CredFree(credential_ptr)


def delete_generic_credential(target_name: str) -> bool:
    """Delete one generic credential payload from the current user's credential set."""
    if not isinstance(target_name, str) or not target_name:
        raise WindowsCredentialStoreError("credential target_name must be a non-empty string")

    if not _ADVAPI32.CredDeleteW(target_name, CRED_TYPE_GENERIC, 0):
        error_code = ctypes.get_last_error()
        if error_code == ERROR_NOT_FOUND:
            return False
        raise WindowsCredentialStoreError(f"CredDeleteW failed: {error_code}")
    return True
