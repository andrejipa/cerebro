"""Abstractions for external session claim and live proof storage."""

import json
from typing import Protocol
from pathlib import Path
import os
import tempfile

if os.name == "nt":
    from core.windows_credential_store import (
        WindowsCredentialStoreError,
        delete_generic_credential,
        read_generic_credential,
        write_generic_credential,
    )
else:
    WindowsCredentialStoreError = RuntimeError

class SessionBackendError(Exception):
    """Base exception for backend storage failures."""

class ISessionBackend(Protocol):
    """Strategy for reading and writing session claims securely."""
    
    def read_claim(self, target_name: str) -> bytes | None:
        """Read a raw claim payload."""
        ...
        
    def write_claim(self, target_name: str, payload: bytes) -> None:
        """Write a raw claim payload."""
        ...
        
    def delete_claim(self, target_name: str) -> None:
        """Remove a claim payload."""
        ...

class FileSessionBackend:
    """Fallback file-backed storage for session claims."""
    
    def __init__(self, base_dir: Path):
        self.base_dir = base_dir
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
    def _secure_path(self, target_name: str) -> Path:
        """Sanitiza o nome do alvo para prevenir Path Traversal."""
        if not target_name or "/" in target_name or "\\" in target_name or ".." in target_name:
            raise SessionBackendError(f"Invalid or unsafe target name: {target_name}")
        return self.base_dir / f"{target_name}.json"

    def read_claim(self, target_name: str) -> bytes | None:
        path = self._secure_path(target_name)
        return path.read_bytes() if path.exists() else None
        
    def write_claim(self, target_name: str, payload: bytes) -> None:
        """Escreve atómicamente via arquivo temporário para evitar corrupção em crashes."""
        path = self._secure_path(target_name)
        tmp_path = path.with_suffix(".tmp")
        try:
            tmp_path.write_bytes(payload)
            os.replace(tmp_path, path)
        except OSError as exc:
            raise SessionBackendError(f"Failed to write claim atomically: {exc}") from exc
        
    def delete_claim(self, target_name: str) -> None:
        self._secure_path(target_name).unlink(missing_ok=True)