"""Session artifact and authority helpers extracted from ``StateStore``.

This service owns external session claim/live-proof storage, session-file
reading, holder binding helpers, and backend-specific encoding details. The
``StateStore`` facade continues to own revision ordering, pending-refresh
recovery, locking, and canonical state writes.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import zlib
from pathlib import Path
from typing import Callable

from core.validation import error, validate_session_data

if os.name == "nt":
    from core.windows_credential_store import (
        WindowsCredentialStoreError,
        delete_generic_credential,
        read_generic_credential,
        write_generic_credential,
    )
else:  # pragma: no cover - imported only on Windows-backed live-proof storage
    WindowsCredentialStoreError = RuntimeError
    delete_generic_credential = None
    read_generic_credential = None
    write_generic_credential = None


SESSION_CLAIMS_DIR_ENV_VAR = "CEREBRO_SESSION_CLAIMS_DIR"
SESSION_LIVE_PROOFS_DIR_ENV_VAR = "CEREBRO_SESSION_LIVE_PROOFS_DIR"
SESSION_CLAIM_BACKEND_FILE = "file"
SESSION_CLAIM_BACKEND_WINCRED = "wincred"
SESSION_LIVE_PROOF_BACKEND_FILE = "file"
SESSION_LIVE_PROOF_BACKEND_WINCRED = "wincred"
WINCRED_COMPRESSED_PAYLOAD_PREFIX = b"CZX1"
WINCRED_PACKED_SESSION_CLAIM_PREFIX = b"CZX2"
WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX = b"CZX3"
WINCRED_SESSION_CLAIM_FIELDS = (
    "claim_id",
    "session_id",
    "root_sha256",
    "session_token_sha256",
    "live_proof_id",
    "session_live_proof_sha256",
    "owner_binding_sha256",
)
WINCRED_SESSION_LIVE_PROOF_FIELDS = (
    "proof_id",
    "session_id",
    "root_sha256",
    "session_live_proof",
)


class StateSessionArtifactsService:
    """Provider-neutral helpers for local session authority artifacts."""

    def __init__(
        self,
        *,
        root: Path,
        session_path: Path,
        read_optional_file_bytes: Callable[[Path], bytes | None],
        write_bytes_atomic: Callable[[Path, bytes], None],
        error_cls: type[Exception],
        read_generic_credential_func: Callable[[str], bytes | None] | None = None,
        write_generic_credential_func: Callable[[str, bytes], None] | None = None,
        delete_generic_credential_func: Callable[[str], object] | None = None,
        windows_credential_store_error_cls: type[Exception] = WindowsCredentialStoreError,
    ) -> None:
        self.root = Path(root).resolve()
        self.session_path = Path(session_path)
        self._read_optional_file_bytes = read_optional_file_bytes
        self._write_bytes_atomic = write_bytes_atomic
        self._error_cls = error_cls
        self._read_generic_credential = read_generic_credential_func or read_generic_credential
        self._write_generic_credential = write_generic_credential_func or write_generic_credential
        self._delete_generic_credential = delete_generic_credential_func or delete_generic_credential
        self._windows_credential_store_error_cls = windows_credential_store_error_cls
        self.claims_dir = self.resolve_session_claims_dir()
        self.live_proofs_dir = self.resolve_session_live_proofs_dir()

    def hash_session_token(self, token: str) -> str:
        """Hash one session capability token before persistence or comparison."""
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def hash_session_live_proof(self, proof: str) -> str:
        """Hash one live session proof before persistence or comparison."""
        return hashlib.sha256(proof.encode("utf-8")).hexdigest()

    def resolve_session_claims_dir(self) -> Path:
        """Resolve the external per-user claim directory for live session authority."""
        override = os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip()
        if override:
            return Path(override).expanduser().resolve()

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return Path(local_app_data).resolve() / "Cerebro" / "session_claims"

        xdg_state_home = os.environ.get("XDG_STATE_HOME", "").strip()
        if xdg_state_home:
            return Path(xdg_state_home).expanduser().resolve() / "cerebro" / "session_claims"

        return Path.home().resolve() / ".local" / "state" / "cerebro" / "session_claims"

    def resolve_session_live_proofs_dir(self) -> Path:
        """Resolve the external per-user live-proof directory for active session freshness."""
        override = os.environ.get(SESSION_LIVE_PROOFS_DIR_ENV_VAR, "").strip()
        if override:
            return Path(override).expanduser().resolve()

        claims_override = os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip()
        if claims_override:
            return Path(claims_override).expanduser().resolve().parent / "session_live_proofs"

        if os.name == "nt":
            local_app_data = os.environ.get("LOCALAPPDATA", "").strip()
            if local_app_data:
                return Path(local_app_data).resolve() / "Cerebro" / "session_live_proofs"

        xdg_state_home = os.environ.get("XDG_STATE_HOME", "").strip()
        if xdg_state_home:
            return Path(xdg_state_home).expanduser().resolve() / "cerebro" / "session_live_proofs"

        return Path.home().resolve() / ".local" / "state" / "cerebro" / "session_live_proofs"

    def session_claim_path(self, claim_id: str) -> Path:
        """Return the external claim path for one claim id."""
        return self.claims_dir / f"{claim_id}.json"

    def session_live_proof_path(self, proof_id: str) -> Path:
        """Return the external live-proof path for one proof id."""
        return self.live_proofs_dir / f"{proof_id}.json"

    def session_claim_backend(self) -> str:
        """Return the active backend for session claim storage."""
        if os.environ.get(SESSION_CLAIMS_DIR_ENV_VAR, "").strip():
            return SESSION_CLAIM_BACKEND_FILE
        return SESSION_CLAIM_BACKEND_FILE

    def session_claim_target_name(self, claim_id: str) -> str:
        """Return one deterministic external target name for a session claim."""
        digest = hashlib.sha256(f"{self.hash_root_identity()}:claim:{claim_id}".encode("utf-8")).hexdigest()[:32]
        return f"Cerebro.SC.{digest}"

    def legacy_session_claim_target_name(self, claim_id: str) -> str:
        """Return the previous WinCred target name for compatibility reads and cleanup."""
        return f"Cerebro.SessionClaim.{self.hash_root_identity()}.{claim_id}"

    def session_claim_location(self, claim_id: str, *, backend: str | None = None) -> str:
        """Return one human-readable location descriptor for a claim."""
        resolved_backend = backend or self.session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            return self.session_claim_target_name(claim_id)
        return f"session_claims/{claim_id}.json"

    def session_live_proof_backend(self) -> str:
        """Return the active backend for session live-proof storage."""
        if os.environ.get(SESSION_LIVE_PROOFS_DIR_ENV_VAR, "").strip():
            return SESSION_LIVE_PROOF_BACKEND_FILE
        return SESSION_LIVE_PROOF_BACKEND_FILE

    def session_live_proof_target_name(self, proof_id: str) -> str:
        """Return one deterministic external target name for a live proof."""
        digest = hashlib.sha256(f"{self.hash_root_identity()}:proof:{proof_id}".encode("utf-8")).hexdigest()[:32]
        return f"Cerebro.SL.{digest}"

    def legacy_session_live_proof_target_name(self, proof_id: str) -> str:
        """Return the previous WinCred target name for compatibility reads and cleanup."""
        return f"Cerebro.SessionLiveProof.{self.hash_root_identity()}.{proof_id}"

    def session_live_proof_location(self, proof_id: str, *, backend: str | None = None) -> str:
        """Return one human-readable location descriptor for a live proof."""
        resolved_backend = backend or self.session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            return self.session_live_proof_target_name(proof_id)
        return f"session_live_proofs/{proof_id}.json"

    def hash_root_identity(self) -> str:
        """Hash the resolved project root for claim-to-root binding."""
        return hashlib.sha256(str(self.root).encode("utf-8")).hexdigest()

    def hash_session_owner_binding(self, binding: str) -> str:
        """Hash one local owner-context binding before persistence or comparison."""
        return hashlib.sha256(binding.encode("utf-8")).hexdigest()

    def current_session_owner_binding(self) -> str:
        """Return one best-effort fingerprint for the current live holder context."""
        parent_pid = os.getppid()
        if not isinstance(parent_pid, int) or parent_pid <= 0:
            return f"{os.name}:parent:0"

        parent_identity = self.process_binding_identity(parent_pid)
        return f"{os.name}:parent:{parent_pid}:{parent_identity}"

    def process_binding_identity(self, pid: int) -> str:
        """Return one stable-enough per-process identity marker for holder binding."""
        if os.name == "nt":
            identity = self.windows_process_binding_identity(pid)
            if identity:
                return identity
        else:
            identity = self.proc_process_binding_identity(pid)
            if identity:
                return identity
        return f"pid:{pid}"

    def proc_process_binding_identity(self, pid: int) -> str:
        """Return a Linux-style process identity when `/proc` is available."""
        proc_dir = Path("/proc") / str(pid)
        stat_path = proc_dir / "stat"
        if not stat_path.exists():
            return ""

        try:
            stat_text = stat_path.read_text(encoding="utf-8")
        except OSError:
            return ""

        right_paren = stat_text.rfind(")")
        if right_paren == -1:
            return ""
        fields = stat_text[right_paren + 2 :].split()
        if len(fields) <= 19:
            return ""

        start_ticks = fields[19]
        exe_path = ""
        exe_link = proc_dir / "exe"
        try:
            exe_path = os.readlink(exe_link)
        except OSError:
            exe_path = ""
        return f"start:{start_ticks};exe:{exe_path}"

    def windows_process_binding_identity(self, pid: int) -> str:
        """Return a Windows process identity from creation time plus executable path."""
        try:
            import ctypes
            from ctypes import wintypes
        except ImportError:
            return ""

        process_query_limited_information = 0x1000
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        kernel32.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
        kernel32.OpenProcess.restype = wintypes.HANDLE
        kernel32.GetProcessTimes.argtypes = [
            wintypes.HANDLE,
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
            ctypes.POINTER(wintypes.FILETIME),
        ]
        kernel32.GetProcessTimes.restype = wintypes.BOOL
        kernel32.QueryFullProcessImageNameW.argtypes = [
            wintypes.HANDLE,
            wintypes.DWORD,
            wintypes.LPWSTR,
            ctypes.POINTER(wintypes.DWORD),
        ]
        kernel32.QueryFullProcessImageNameW.restype = wintypes.BOOL
        kernel32.CloseHandle.argtypes = [wintypes.HANDLE]
        kernel32.CloseHandle.restype = wintypes.BOOL

        handle = kernel32.OpenProcess(process_query_limited_information, False, pid)
        if not handle:
            return ""

        try:
            created_at = wintypes.FILETIME()
            exited_at = wintypes.FILETIME()
            kernel_time = wintypes.FILETIME()
            user_time = wintypes.FILETIME()
            if not kernel32.GetProcessTimes(
                handle,
                ctypes.byref(created_at),
                ctypes.byref(exited_at),
                ctypes.byref(kernel_time),
                ctypes.byref(user_time),
            ):
                return ""

            created_ticks = (int(created_at.dwHighDateTime) << 32) | int(created_at.dwLowDateTime)
            buffer_length = wintypes.DWORD(32768)
            buffer = ctypes.create_unicode_buffer(buffer_length.value)
            if kernel32.QueryFullProcessImageNameW(handle, 0, buffer, ctypes.byref(buffer_length)):
                executable_path = buffer.value[: buffer_length.value]
            else:
                executable_path = ""
            return f"created:{created_ticks};exe:{executable_path}"
        finally:
            kernel32.CloseHandle(handle)

    def write_session_claim(self, claim_data: dict) -> None:
        """Persist one external session claim outside the project root."""
        backend = self.session_claim_backend()
        if backend == SESSION_CLAIM_BACKEND_WINCRED:
            payload = (json.dumps(claim_data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        else:
            payload = (json.dumps(claim_data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self.write_session_claim_bytes(claim_data["claim_id"], payload, backend=backend)

    def write_session_live_proof(self, proof_data: dict) -> None:
        """Persist one external live session proof outside the project root."""
        backend = self.session_live_proof_backend()
        if backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            payload = (json.dumps(proof_data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
        else:
            payload = (json.dumps(proof_data, indent=2, ensure_ascii=False) + "\n").encode("utf-8")
        self.write_session_live_proof_bytes(proof_data["proof_id"], payload, backend=backend)

    def _raise(self, message: str) -> Exception:
        return self._error_cls(message)

    def encode_wincred_payload(self, payload: bytes) -> bytes:
        """Compress WinCred payloads to stay below the host's effective blob limits."""
        return WINCRED_COMPRESSED_PAYLOAD_PREFIX + zlib.compress(payload, level=6)

    def decode_wincred_payload(self, payload: bytes, *, label: str) -> bytes:
        """Decode one WinCred payload while preserving compatibility with legacy plain JSON bytes."""
        if not payload.startswith(WINCRED_COMPRESSED_PAYLOAD_PREFIX):
            return payload
        try:
            return zlib.decompress(payload[len(WINCRED_COMPRESSED_PAYLOAD_PREFIX) :])
        except zlib.error as exc:
            raise self._raise(f"failed to decode {label} from WinCred storage") from exc

    def encode_wincred_structured_payload(
        self,
        payload: bytes,
        *,
        prefix: bytes,
        fields: tuple[str, ...],
    ) -> bytes:
        """Pack one known JSON object into a smaller WinCred-specific envelope."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.encode_wincred_payload(payload)
        if not isinstance(data, dict):
            return self.encode_wincred_payload(payload)
        if set(data.keys()) != set(fields):
            return self.encode_wincred_payload(payload)
        values: list[str] = []
        for field in fields:
            value = data.get(field)
            if not isinstance(value, str) or "\n" in value:
                return self.encode_wincred_payload(payload)
            values.append(value)
        packed = ("\n".join(values) + "\n").encode("utf-8")
        return prefix + zlib.compress(packed, level=6)

    def decode_wincred_structured_payload(
        self,
        payload: bytes,
        *,
        prefix: bytes,
        fields: tuple[str, ...],
        label: str,
    ) -> bytes:
        """Decode one smaller WinCred-specific envelope back into canonical compact JSON bytes."""
        if not payload.startswith(prefix):
            return self.decode_wincred_payload(payload, label=label)
        try:
            packed = zlib.decompress(payload[len(prefix) :])
        except zlib.error as exc:
            raise self._raise(f"failed to decode {label} from WinCred storage") from exc
        try:
            values = packed.decode("utf-8").splitlines()
        except UnicodeDecodeError as exc:
            raise self._raise(f"failed to decode {label} from WinCred storage") from exc
        if len(values) != len(fields):
            raise self._raise(f"failed to decode {label} from WinCred storage")
        data = {field: value for field, value in zip(fields, values)}
        return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")

    def encode_wincred_session_claim_payload(self, payload: bytes) -> bytes:
        """Encode one session claim into a compact WinCred envelope when the schema is known."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.encode_wincred_payload(payload)
        if not isinstance(data, dict) or set(data.keys()) != set(WINCRED_SESSION_CLAIM_FIELDS):
            return self.encode_wincred_payload(payload)
        try:
            packed = b"".join(
                (
                    self.pack_prefixed_hex_identifier(data["claim_id"], prefix="claim-", label="session claim claim_id"),
                    self.pack_prefixed_hex_identifier(data["session_id"], prefix="session-", label="session claim session_id"),
                    self.pack_sha256_hex(data["root_sha256"], label="session claim root_sha256"),
                    self.pack_sha256_hex(data["session_token_sha256"], label="session claim session_token_sha256"),
                    self.pack_prefixed_hex_identifier(data["live_proof_id"], prefix="proof-", label="session claim live_proof_id"),
                    self.pack_sha256_hex(
                        data["session_live_proof_sha256"],
                        label="session claim session_live_proof_sha256",
                    ),
                    self.pack_sha256_hex(data["owner_binding_sha256"], label="session claim owner_binding_sha256"),
                )
            )
        except ValueError:
            return self.encode_wincred_payload(payload)
        return WINCRED_PACKED_SESSION_CLAIM_PREFIX + packed

    def decode_wincred_session_claim_payload(self, payload: bytes) -> bytes:
        """Decode one WinCred session claim payload back into canonical compact JSON bytes."""
        if payload.startswith(WINCRED_PACKED_SESSION_CLAIM_PREFIX):
            packed = payload[len(WINCRED_PACKED_SESSION_CLAIM_PREFIX) :]
            if len(packed) == 176:
                data = {
                    "claim_id": self.unpack_prefixed_hex_identifier(packed[0:16], prefix="claim-"),
                    "session_id": self.unpack_prefixed_hex_identifier(packed[16:32], prefix="session-"),
                    "root_sha256": packed[32:64].hex(),
                    "session_token_sha256": packed[64:96].hex(),
                    "live_proof_id": self.unpack_prefixed_hex_identifier(packed[96:112], prefix="proof-"),
                    "session_live_proof_sha256": packed[112:144].hex(),
                    "owner_binding_sha256": packed[144:176].hex(),
                }
                return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            return self.decode_wincred_structured_payload(
                payload,
                prefix=WINCRED_PACKED_SESSION_CLAIM_PREFIX,
                fields=WINCRED_SESSION_CLAIM_FIELDS,
                label="external session claim",
            )
        return self.decode_wincred_payload(payload, label="external session claim")

    def encode_wincred_session_live_proof_payload(self, payload: bytes) -> bytes:
        """Encode one session live proof into a compact WinCred envelope when the schema is known."""
        try:
            data = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            return self.encode_wincred_payload(payload)
        if not isinstance(data, dict) or set(data.keys()) != set(WINCRED_SESSION_LIVE_PROOF_FIELDS):
            return self.encode_wincred_payload(payload)
        try:
            packed = b"".join(
                (
                    self.pack_prefixed_hex_identifier(data["proof_id"], prefix="proof-", label="session live proof proof_id"),
                    self.pack_prefixed_hex_identifier(
                        data["session_id"],
                        prefix="session-",
                        label="session live proof session_id",
                    ),
                    self.pack_sha256_hex(data["root_sha256"], label="session live proof root_sha256"),
                    self.pack_base64url_token(
                        data["session_live_proof"],
                        expected_bytes=32,
                        label="session live proof session_live_proof",
                    ),
                )
            )
        except ValueError:
            return self.encode_wincred_payload(payload)
        return WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX + packed

    def decode_wincred_session_live_proof_payload(self, payload: bytes) -> bytes:
        """Decode one WinCred session live proof payload back into canonical compact JSON bytes."""
        if payload.startswith(WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX):
            packed = payload[len(WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX) :]
            if len(packed) == 96:
                data = {
                    "proof_id": self.unpack_prefixed_hex_identifier(packed[0:16], prefix="proof-"),
                    "session_id": self.unpack_prefixed_hex_identifier(packed[16:32], prefix="session-"),
                    "root_sha256": packed[32:64].hex(),
                    "session_live_proof": self.unpack_base64url_token(packed[64:96]),
                }
                return (json.dumps(data, ensure_ascii=False, separators=(",", ":")) + "\n").encode("utf-8")
            return self.decode_wincred_structured_payload(
                payload,
                prefix=WINCRED_PACKED_SESSION_LIVE_PROOF_PREFIX,
                fields=WINCRED_SESSION_LIVE_PROOF_FIELDS,
                label="external session live proof",
            )
        return self.decode_wincred_payload(payload, label="external session live proof")

    def pack_prefixed_hex_identifier(self, value: object, *, prefix: str, label: str) -> bytes:
        """Pack one `prefix + 32hex` identifier into 16 raw bytes."""
        if not isinstance(value, str) or not value.startswith(prefix):
            raise ValueError(label)
        suffix = value[len(prefix) :]
        if len(suffix) != 32:
            raise ValueError(label)
        try:
            return bytes.fromhex(suffix)
        except ValueError as exc:
            raise ValueError(label) from exc

    def unpack_prefixed_hex_identifier(self, value: bytes, *, prefix: str) -> str:
        """Unpack one 16-byte identifier into its canonical prefixed hex form."""
        if len(value) != 16:
            raise self._raise("failed to decode WinCred identifier payload")
        return prefix + value.hex()

    def pack_sha256_hex(self, value: object, *, label: str) -> bytes:
        """Pack one sha256 hex string into 32 raw bytes."""
        if not isinstance(value, str) or len(value) != 64:
            raise ValueError(label)
        try:
            return bytes.fromhex(value)
        except ValueError as exc:
            raise ValueError(label) from exc

    def pack_base64url_token(self, value: object, *, expected_bytes: int, label: str) -> bytes:
        """Pack one URL-safe base64 token into its raw byte form."""
        if not isinstance(value, str) or not value:
            raise ValueError(label)
        padding = "=" * (-len(value) % 4)
        try:
            decoded = base64.urlsafe_b64decode((value + padding).encode("ascii"))
        except (ValueError, UnicodeEncodeError) as exc:
            raise ValueError(label) from exc
        if len(decoded) != expected_bytes or self.unpack_base64url_token(decoded) != value:
            raise ValueError(label)
        return decoded

    def unpack_base64url_token(self, value: bytes) -> str:
        """Unpack one raw token into URL-safe base64 without padding."""
        return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")

    def read_optional_session_claim_bytes(self, claim_id: object, *, backend: str | None = None) -> bytes | None:
        """Return raw claim bytes from the active backend when present."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self.session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            for target_name in (
                self.session_claim_target_name(normalized_claim_id),
                self.legacy_session_claim_target_name(normalized_claim_id),
            ):
                try:
                    payload = self._read_generic_credential(target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to read external session claim: {target_name}") from exc
                if payload is None:
                    continue
                return self.decode_wincred_session_claim_payload(payload)
            return None
        return self._read_optional_file_bytes(self.session_claim_path(normalized_claim_id))

    def write_session_claim_bytes(self, claim_id: object, payload: bytes, *, backend: str | None = None) -> None:
        """Persist raw claim bytes to the active backend."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            raise self._raise("external session claim id must be a non-empty string")
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self.session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            target_name = self.session_claim_target_name(normalized_claim_id)
            try:
                self._write_generic_credential(target_name, self.encode_wincred_session_claim_payload(payload))
            except self._windows_credential_store_error_cls as exc:
                raise self._raise(f"failed to write external session claim: {target_name}") from exc
            legacy_target_name = self.legacy_session_claim_target_name(normalized_claim_id)
            if legacy_target_name != target_name:
                try:
                    self._delete_generic_credential(legacy_target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to remove external session claim: {legacy_target_name}") from exc
            return
        self.claims_dir.mkdir(parents=True, exist_ok=True)
        self._write_bytes_atomic(self.session_claim_path(normalized_claim_id), payload)

    def read_optional_session_live_proof_bytes(self, proof_id: object, *, backend: str | None = None) -> bytes | None:
        """Return raw live-proof bytes from the active backend when present."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self.session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            for target_name in (
                self.session_live_proof_target_name(normalized_proof_id),
                self.legacy_session_live_proof_target_name(normalized_proof_id),
            ):
                try:
                    payload = self._read_generic_credential(target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to read external session live proof: {target_name}") from exc
                if payload is None:
                    continue
                return self.decode_wincred_session_live_proof_payload(payload)
            return None
        return self._read_optional_file_bytes(self.session_live_proof_path(normalized_proof_id))

    def write_session_live_proof_bytes(self, proof_id: object, payload: bytes, *, backend: str | None = None) -> None:
        """Persist raw live-proof bytes to the active backend."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            raise self._raise("external session live proof id must be a non-empty string")
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self.session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            target_name = self.session_live_proof_target_name(normalized_proof_id)
            try:
                self._write_generic_credential(target_name, self.encode_wincred_session_live_proof_payload(payload))
            except self._windows_credential_store_error_cls as exc:
                raise self._raise(f"failed to write external session live proof: {target_name}") from exc
            legacy_target_name = self.legacy_session_live_proof_target_name(normalized_proof_id)
            if legacy_target_name != target_name:
                try:
                    self._delete_generic_credential(legacy_target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to remove external session live proof: {legacy_target_name}") from exc
            return
        self.live_proofs_dir.mkdir(parents=True, exist_ok=True)
        self._write_bytes_atomic(self.session_live_proof_path(normalized_proof_id), payload)

    def read_session_claim_file(self, claim_id: object) -> tuple[dict | None, list[dict]]:
        """Return the raw external claim file when it is structurally valid."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None, [error("session_claim_invalid", "session.owner_claim_id must reference one external claim id")]
        normalized_claim_id = claim_id.strip()
        location = self.session_claim_location(normalized_claim_id)
        try:
            raw_claim = self.read_optional_session_claim_bytes(normalized_claim_id)
        except Exception:
            return None, [error("session_claim_unreadable", f"failed to read external session claim: {location}")]
        if raw_claim is None:
            return None, [error("session_claim_missing", f"external session claim not found: {location}")]
        try:
            claim_data = json.loads(raw_claim.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return None, [error("session_claim_invalid_json", f"invalid JSON in external session claim: {exc.msg}")]

        expected_keys = {
            "claim_id",
            "session_id",
            "root_sha256",
            "session_token_sha256",
            "live_proof_id",
            "session_live_proof_sha256",
            "owner_binding_sha256",
        }
        if not isinstance(claim_data, dict):
            return None, [error("session_claim_invalid_schema", "external session claim must be a JSON object")]
        actual_keys = set(claim_data.keys())
        if actual_keys != expected_keys:
            return None, [error("session_claim_invalid_schema", "external session claim does not match the required schema")]
        if not isinstance(claim_data.get("claim_id"), str) or not claim_data["claim_id"]:
            return None, [error("session_claim_invalid_schema", "external session claim claim_id must be a non-empty string")]
        if not isinstance(claim_data.get("session_id"), str) or not claim_data["session_id"]:
            return None, [error("session_claim_invalid_schema", "external session claim session_id must be a non-empty string")]
        root_sha256 = claim_data.get("root_sha256", "")
        if not isinstance(root_sha256, str) or not self.is_valid_sha256_string(root_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim root_sha256 must be a sha256 hex string")]
        session_token_sha256 = claim_data.get("session_token_sha256", "")
        if not isinstance(session_token_sha256, str) or not self.is_valid_sha256_string(session_token_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim session_token_sha256 must be a sha256 hex string")]
        live_proof_id = claim_data.get("live_proof_id", "")
        if not isinstance(live_proof_id, str) or not live_proof_id:
            return None, [error("session_claim_invalid_schema", "external session claim live_proof_id must be a non-empty string")]
        session_live_proof_sha256 = claim_data.get("session_live_proof_sha256", "")
        if not isinstance(session_live_proof_sha256, str) or not self.is_valid_sha256_string(session_live_proof_sha256):
            return None, [
                error(
                    "session_claim_invalid_schema",
                    "external session claim session_live_proof_sha256 must be a sha256 hex string",
                )
            ]
        owner_binding_sha256 = claim_data.get("owner_binding_sha256", "")
        if not isinstance(owner_binding_sha256, str) or not self.is_valid_sha256_string(owner_binding_sha256):
            return None, [error("session_claim_invalid_schema", "external session claim owner_binding_sha256 must be a sha256 hex string")]
        return claim_data, []

    def read_validated_session_claim(self, session_data: dict) -> tuple[dict | None, list[dict]]:
        """Return one validated external session claim for the current local session artifact."""
        claim_data, claim_errors = self.read_session_claim_file(session_data.get("owner_claim_id"))
        if claim_errors or claim_data is None:
            return claim_data, claim_errors
        if claim_data["session_id"] != session_data["session_id"]:
            return None, [error("session_claim_mismatch", "external session claim does not match the active local session id")]
        if claim_data["root_sha256"] != self.hash_root_identity():
            return None, [error("session_claim_mismatch", "external session claim does not belong to this project root")]
        return claim_data, []

    def remove_session_claim(self, claim_id: object, *, backend: str | None = None) -> None:
        """Remove one external session claim when present."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return
        normalized_claim_id = claim_id.strip()
        resolved_backend = backend or self.session_claim_backend()
        if resolved_backend == SESSION_CLAIM_BACKEND_WINCRED:
            for target_name in (
                self.session_claim_target_name(normalized_claim_id),
                self.legacy_session_claim_target_name(normalized_claim_id),
            ):
                try:
                    self._delete_generic_credential(target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to remove external session claim: {target_name}") from exc
            return
        claim_path = self.session_claim_path(normalized_claim_id)
        if not claim_path.exists():
            return
        try:
            claim_path.unlink()
        except OSError as exc:
            raise self._raise(f"failed to remove external session claim: {claim_path}") from exc

    def capture_session_claim_snapshot(self, claim_id: object, *, label: str) -> dict | None:
        """Capture one provider-neutral claim snapshot for later comparison or restore."""
        if not isinstance(claim_id, str) or not claim_id.strip():
            return None
        normalized_claim_id = claim_id.strip()
        return {
            "label": label,
            "claim_id": normalized_claim_id,
            "backend": self.session_claim_backend(),
            "bytes": self.read_optional_session_claim_bytes(normalized_claim_id),
        }

    def restore_session_claim_snapshot(self, snapshot: dict) -> None:
        """Restore one provider-neutral claim snapshot."""
        claim_id = snapshot.get("claim_id")
        if not isinstance(claim_id, str) or not claim_id:
            raise self._raise("session claim snapshot is missing claim_id")
        backend = snapshot.get("backend")
        if not isinstance(backend, str) or not backend:
            raise self._raise("session claim snapshot is missing backend")
        before_bytes = snapshot.get("bytes")
        if before_bytes is None:
            self.remove_session_claim(claim_id, backend=backend)
            return
        if not isinstance(before_bytes, bytes):
            raise self._raise("session claim snapshot must contain raw bytes or None")
        self.write_session_claim_bytes(claim_id, before_bytes, backend=backend)

    def read_session_live_proof_file(self, proof_id: object) -> tuple[dict | None, list[dict]]:
        """Return the raw external live proof when it is structurally valid."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None, [error("session_live_proof_invalid", "external session live proof id must be a non-empty string")]
        normalized_proof_id = proof_id.strip()
        location = self.session_live_proof_location(normalized_proof_id)
        try:
            raw_proof = self.read_optional_session_live_proof_bytes(normalized_proof_id)
        except Exception:
            return None, [error("session_live_proof_unreadable", f"failed to read external session live proof: {location}")]
        if raw_proof is None:
            return None, [error("session_live_proof_missing", f"external session live proof not found: {location}")]
        try:
            proof_data = json.loads(raw_proof.decode("utf-8"))
        except json.JSONDecodeError as exc:
            return None, [error("session_live_proof_invalid_json", f"invalid JSON in external session live proof: {exc.msg}")]

        expected_keys = {"proof_id", "session_id", "root_sha256", "session_live_proof"}
        if not isinstance(proof_data, dict):
            return None, [error("session_live_proof_invalid_schema", "external session live proof must be a JSON object")]
        actual_keys = set(proof_data.keys())
        if actual_keys != expected_keys:
            return None, [error("session_live_proof_invalid_schema", "external session live proof does not match the required schema")]
        if not isinstance(proof_data.get("proof_id"), str) or not proof_data["proof_id"]:
            return None, [error("session_live_proof_invalid_schema", "external session live proof proof_id must be a non-empty string")]
        if not isinstance(proof_data.get("session_id"), str) or not proof_data["session_id"]:
            return None, [error("session_live_proof_invalid_schema", "external session live proof session_id must be a non-empty string")]
        root_sha256 = proof_data.get("root_sha256", "")
        if not isinstance(root_sha256, str) or not self.is_valid_sha256_string(root_sha256):
            return None, [error("session_live_proof_invalid_schema", "external session live proof root_sha256 must be a sha256 hex string")]
        live_proof = proof_data.get("session_live_proof", "")
        if not isinstance(live_proof, str) or not live_proof:
            return None, [error("session_live_proof_invalid_schema", "external session live proof session_live_proof must be a non-empty string")]
        return proof_data, []

    def read_validated_session_live_proof(self, session_data: dict, claim_data: dict) -> tuple[dict | None, list[dict]]:
        """Return one validated external live proof for the current local session artifact."""
        proof_data, proof_errors = self.read_session_live_proof_file(claim_data.get("live_proof_id"))
        if proof_errors or proof_data is None:
            return proof_data, proof_errors
        if proof_data["proof_id"] != claim_data["live_proof_id"]:
            return None, [error("session_live_proof_mismatch", "external session live proof does not match the active live proof id")]
        if proof_data["session_id"] != session_data["session_id"]:
            return None, [error("session_live_proof_mismatch", "external session live proof does not match the active local session id")]
        if proof_data["root_sha256"] != self.hash_root_identity():
            return None, [error("session_live_proof_mismatch", "external session live proof does not belong to this project root")]
        if not hmac.compare_digest(
            claim_data["session_live_proof_sha256"],
            self.hash_session_live_proof(proof_data["session_live_proof"]),
        ):
            return None, [
                error(
                    "session_live_proof_mismatch",
                    "external session live proof does not match the active local session claim",
                )
            ]
        return proof_data, []

    def remove_session_live_proof(self, proof_id: object, *, backend: str | None = None) -> None:
        """Remove one external live proof when present."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return
        normalized_proof_id = proof_id.strip()
        resolved_backend = backend or self.session_live_proof_backend()
        if resolved_backend == SESSION_LIVE_PROOF_BACKEND_WINCRED:
            for target_name in (
                self.session_live_proof_target_name(normalized_proof_id),
                self.legacy_session_live_proof_target_name(normalized_proof_id),
            ):
                try:
                    self._delete_generic_credential(target_name)
                except self._windows_credential_store_error_cls as exc:
                    raise self._raise(f"failed to remove external session live proof: {target_name}") from exc
            return
        self.remove_session_live_proof_by_path(self.session_live_proof_path(normalized_proof_id))

    def remove_session_live_proof_by_path(self, proof_path: Path) -> None:
        """Remove one external live proof by path when present."""
        if not proof_path.exists():
            return
        try:
            proof_path.unlink()
        except OSError as exc:
            raise self._raise(f"failed to remove external session live proof: {proof_path}") from exc

    def is_valid_sha256_string(self, value: str) -> bool:
        """Return whether one string is a lowercase SHA-256 hex digest."""
        return len(value) == 64 and all(character in "0123456789abcdef" for character in value)

    def read_session_file(self) -> tuple[dict | None, list[dict]]:
        """Return the raw local session file when it is schema-valid independent of one state revision."""
        if not self.session_path.exists():
            return None, []

        try:
            with self.session_path.open(encoding="utf-8") as handle:
                session_data = json.load(handle)
        except json.JSONDecodeError as exc:
            return None, [error("session_invalid_json", f"invalid JSON in session file: {exc.msg}")]
        except OSError:
            return None, [error("session_unreadable", f"failed to read session file: {self.session_path}")]

        validation_errors = validate_session_data(session_data)
        if validation_errors:
            return None, [
                error("session_invalid_schema", "session file does not match the required schema"),
                *validation_errors,
            ]
        return session_data, []

    def active_session_live_proof_id(self, session_data: dict) -> str | None:
        """Return the current active live-proof id when the claim is readable enough to locate it."""
        claim_data, claim_errors = self.read_validated_session_claim(session_data)
        if claim_errors or claim_data is None:
            return None
        proof_id = claim_data.get("live_proof_id", "")
        if not isinstance(proof_id, str) or not proof_id:
            return None
        return proof_id

    def capture_session_live_proof_snapshot(self, proof_id: object, *, label: str) -> dict | None:
        """Capture one provider-neutral live-proof snapshot for later comparison or restore."""
        if not isinstance(proof_id, str) or not proof_id.strip():
            return None
        normalized_proof_id = proof_id.strip()
        return {
            "label": label,
            "proof_id": normalized_proof_id,
            "backend": self.session_live_proof_backend(),
            "bytes": self.read_optional_session_live_proof_bytes(normalized_proof_id),
        }

    def restore_session_live_proof_snapshot(self, snapshot: dict) -> None:
        """Restore one provider-neutral live-proof snapshot."""
        proof_id = snapshot.get("proof_id")
        if not isinstance(proof_id, str) or not proof_id:
            raise self._raise("session live-proof snapshot is missing proof_id")
        backend = snapshot.get("backend")
        if not isinstance(backend, str) or not backend:
            raise self._raise("session live-proof snapshot is missing backend")
        before_bytes = snapshot.get("bytes")
        if before_bytes is None:
            self.remove_session_live_proof(proof_id, backend=backend)
            return
        if not isinstance(before_bytes, bytes):
            raise self._raise("session live-proof snapshot must contain raw bytes or None")
        self.write_session_live_proof_bytes(proof_id, before_bytes, backend=backend)
