"""Canonical sha256 helpers shared by runtime modules.

Provides a single source of truth for the common digest idioms used across the
runtime. Higher-level fingerprinting semantics such as deterministic JSON
payload selection, command-registry signatures, and retry evidence rules remain
in the modules that own those contracts.
"""

from __future__ import annotations

import hashlib
from pathlib import Path


def sha256_text(content: str) -> str:
    """Return the hex sha256 digest of a UTF-8 encoded string."""
    return hashlib.sha256(content.encode("utf-8")).hexdigest()


def sha256_bytes(content: bytes) -> str:
    """Return the hex sha256 digest of a raw byte payload."""
    return hashlib.sha256(content).hexdigest()


def sha256_file(path: Path) -> str:
    """Return the hex sha256 digest of a file without loading it all at once."""
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()
