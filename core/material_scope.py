"""Material scope preimage primitives."""

from __future__ import annotations

import hashlib
import string
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable


class MaterialScopeError(Exception):
    """Raised when material filesystem scope cannot be proven safely."""


@dataclass(frozen=True)
class FilePreimage:
    """Canonical preimage for one declared material file path."""

    path: str
    exists: bool
    sha256: str
    size: int | None
    file_type: str


@dataclass(frozen=True)
class MaterialScopeManifest:
    """Preimages for the complete declared material scope under one root."""

    root: str
    files: tuple[FilePreimage, ...]

    @property
    def scoped_paths(self) -> frozenset[str]:
        return frozenset(file.path for file in self.files)


def snapshot_material_scope(root: str | Path, paths: Iterable[str]) -> MaterialScopeManifest:
    """Capture canonical preimages for the declared material file scope."""
    resolved_root = _require_existing_root(root)
    normalized_paths = _normalize_unique_paths(paths)
    return MaterialScopeManifest(
        root=str(resolved_root),
        files=tuple(_capture_preimage(resolved_root, path) for path in normalized_paths),
    )


def verify_material_scope(manifest: MaterialScopeManifest) -> None:
    """Fail closed if any captured preimage changed since snapshot time."""
    _validate_manifest_shape(manifest)
    root = _require_existing_root(manifest.root)
    for expected in manifest.files:
        current = _capture_preimage(root, expected.path)
        if current != expected:
            raise MaterialScopeError(f"material preimage changed: {expected.path}")


def assert_effects_within_scope(manifest: MaterialScopeManifest, touched_paths: Iterable[str]) -> tuple[str, ...]:
    """Return normalized touched paths only when all are inside the manifest."""
    _validate_manifest_shape(manifest)
    normalized_touches = _normalize_paths(touched_paths)
    scoped_paths = manifest.scoped_paths
    outside = sorted(path for path in normalized_touches if path not in scoped_paths)
    if outside:
        raise MaterialScopeError("material effects outside declared scope: " + ", ".join(outside))
    return normalized_touches


def verify_commit_scope(manifest: MaterialScopeManifest, touched_paths: Iterable[str]) -> tuple[str, ...]:
    """Verify declared effects and preimages before a caller commits mutations."""
    normalized_touches = assert_effects_within_scope(manifest, touched_paths)
    verify_material_scope(manifest)
    return normalized_touches


def _require_existing_root(root: str | Path) -> Path:
    if not isinstance(root, (str, Path)):
        raise MaterialScopeError("material scope root must be a path")
    try:
        resolved = Path(root).resolve(strict=True)
    except OSError as exc:
        raise MaterialScopeError("material scope root must exist") from exc
    if not resolved.is_dir():
        raise MaterialScopeError("material scope root must be a directory")
    return resolved


def _normalize_unique_paths(paths: Iterable[str]) -> tuple[str, ...]:
    normalized = _normalize_paths(paths)
    seen: set[str] = set()
    duplicates: list[str] = []
    for path in normalized:
        if path in seen:
            duplicates.append(path)
        seen.add(path)
    if duplicates:
        raise MaterialScopeError("duplicate material scope paths: " + ", ".join(sorted(set(duplicates))))
    return normalized


def _normalize_paths(paths: Iterable[str]) -> tuple[str, ...]:
    if isinstance(paths, (str, bytes)) or paths is None:
        raise MaterialScopeError("material paths must be an iterable of strings")
    normalized: list[str] = []
    for raw_path in paths:
        normalized.append(_normalize_relative_path(raw_path))
    return tuple(normalized)


def _normalize_relative_path(raw_path: str) -> str:
    if not isinstance(raw_path, str):
        raise MaterialScopeError("material path must be a string")
    path = raw_path.replace("\\", "/")
    if not path:
        raise MaterialScopeError("material path must not be empty")
    if path.startswith("/") or path.startswith("//") or ":" in path:
        raise MaterialScopeError(f"material path must be relative: {raw_path}")
    parts = path.split("/")
    if any(part in {"", ".", ".."} for part in parts):
        raise MaterialScopeError(f"material path must be normalized and traversal-free: {raw_path}")
    return "/".join(parts)


def _capture_preimage(root: Path, normalized_path: str) -> FilePreimage:
    target = _resolve_scoped_path(root, normalized_path)
    if not target.exists():
        return FilePreimage(
            path=normalized_path,
            exists=False,
            sha256="",
            size=None,
            file_type="missing",
        )
    if not target.is_file():
        raise MaterialScopeError(f"material path is not a file: {normalized_path}")

    digest, size = _hash_file_stably(target, normalized_path)
    return FilePreimage(
        path=normalized_path,
        exists=True,
        sha256=f"sha256:{digest}",
        size=size,
        file_type="file",
    )


def _resolve_scoped_path(root: Path, normalized_path: str) -> Path:
    current = root
    for part in normalized_path.split("/"):
        current = current / part
        if current.is_symlink():
            raise MaterialScopeError(f"material path uses a symlink: {normalized_path}")
    try:
        resolved = current.resolve(strict=False)
        resolved.relative_to(root)
    except (OSError, ValueError) as exc:
        raise MaterialScopeError(f"material path escapes root: {normalized_path}") from exc
    return current


def _hash_file_stably(path: Path, normalized_path: str) -> tuple[str, int]:
    try:
        before = path.stat()
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        after = path.stat()
    except OSError as exc:
        raise MaterialScopeError(f"failed to read material path: {normalized_path}") from exc
    if before.st_size != after.st_size or before.st_mtime_ns != after.st_mtime_ns:
        raise MaterialScopeError(f"material path changed while hashing: {normalized_path}")
    return digest.hexdigest(), after.st_size


def _validate_manifest_shape(manifest: MaterialScopeManifest) -> None:
    if not isinstance(manifest, MaterialScopeManifest):
        raise MaterialScopeError("material manifest has invalid type")
    _require_existing_root(manifest.root)
    if not isinstance(manifest.files, tuple):
        raise MaterialScopeError("material manifest files must be a tuple")
    seen: set[str] = set()
    for preimage in manifest.files:
        _validate_preimage_shape(preimage)
        if preimage.path in seen:
            raise MaterialScopeError(f"duplicate material manifest path: {preimage.path}")
        seen.add(preimage.path)


def _validate_preimage_shape(preimage: FilePreimage) -> None:
    if not isinstance(preimage, FilePreimage):
        raise MaterialScopeError("material preimage has invalid type")
    normalized = _normalize_relative_path(preimage.path)
    if normalized != preimage.path:
        raise MaterialScopeError("material preimage path is not canonical")
    if preimage.exists is True:
        if preimage.file_type != "file":
            raise MaterialScopeError("existing material preimage must have file type")
        if not isinstance(preimage.size, int) or isinstance(preimage.size, bool) or preimage.size < 0:
            raise MaterialScopeError("existing material preimage size must be non-negative")
        if not _is_sha256_digest(preimage.sha256):
            raise MaterialScopeError("existing material preimage must have a sha256 digest")
    elif preimage.exists is False:
        if preimage.file_type != "missing" or preimage.size is not None or preimage.sha256 != "":
            raise MaterialScopeError("missing material preimage must use the missing sentinel")
    else:
        raise MaterialScopeError("material preimage exists must be boolean")


def _is_sha256_digest(value: object) -> bool:
    if not isinstance(value, str):
        return False
    prefix = "sha256:"
    if not value.startswith(prefix):
        return False
    digest = value[len(prefix) :]
    return len(digest) == 64 and all(character in string.hexdigits for character in digest)
