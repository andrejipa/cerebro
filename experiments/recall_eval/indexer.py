from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from collections import Counter, defaultdict
from functools import lru_cache
from hashlib import sha256
import json
import math
import os
import tempfile
import unicodedata
import uuid

from .chunker import (
    PATH_ONLY_EXTENSIONS,
    TEXT_EXTENSIONS,
    TextChunk,
    chunk_text,
    is_path_only_extension,
    is_textual_extension,
)
from .semantic_vectors import embed_sparse
from .scope_classifier import classify_scope


SKIP_DIRS = {
    ".git",
    "node_modules",
    "venv",
    ".venv",
    "__pycache__",
    ".obsidian",
    ".tmp",
    ".cerebro",
    "dist",
    "build",
    ".next",
    ".cache",
    "jre",
    "bin",
    "obj",
}

INDEX_CACHE_FORMAT_VERSION = 3
DERIVED_TEMP_BASE = (
    Path(__file__).resolve().parents[2] / ".tmp_recall_eval"
    if __import__("platform").system() == "Windows"
    else Path("/tmp") / "cerebro_recall_eval"
)


@dataclass(frozen=True)
class IndexedChunk:
    project_name: str
    root: str
    path: str
    chunk_id: int
    text: str
    source_kind: str
    scope: str
    scope_flags: tuple[str, ...]
    token_counts: dict[str, int]
    weighted_tokens: dict[str, float]
    vector_norm: float
    semantic_vector: tuple[dict[int, float], float] | None = None


@dataclass(frozen=True)
class ProjectIndex:
    project_name: str
    root: str
    temp_root: str
    chunks: tuple[IndexedChunk, ...]
    idf: dict[str, float]


@dataclass(frozen=True)
class SourceArtifact:
    project_name: str
    root: str
    path: str
    text: str
    source_kind: str


@dataclass(frozen=True)
class SourceInventoryEntry:
    path: str
    source_kind: str
    size: int
    mtime_ns: int
    ctime_ns: int


@dataclass(frozen=True)
class DirectoryInventoryEntry:
    path: str
    mtime_ns: int
    ctime_ns: int


def ensure_outside_roots(candidate: str | Path, roots: list[str | Path]) -> None:
    candidate_path = Path(candidate).resolve()
    for root in roots:
        root_path = Path(root).resolve()
        try:
            candidate_path.relative_to(root_path)
        except ValueError:
            continue
        raise ValueError(f"Experimental artifact path must stay outside project roots: {candidate_path}")


def _resolve_usable_temp_base(project_roots: list[str | Path], *, leaf_name: str) -> Path:
    candidates: list[Path] = [DERIVED_TEMP_BASE / leaf_name]
    for env_name in ("TEMP", "TMP"):
        value = os.environ.get(env_name)
        if value:
            candidates.append(Path(value) / leaf_name)
    candidates.append(Path(tempfile.gettempdir()) / leaf_name)

    seen: set[str] = set()
    for candidate in candidates:
        try:
            resolved = candidate.resolve()
        except OSError:
            continue
        key = str(resolved)
        if key in seen:
            continue
        seen.add(key)
        try:
            ensure_outside_roots(resolved, project_roots)
        except ValueError:
            continue
        try:
            resolved.mkdir(parents=True, exist_ok=True)
        except OSError:
            continue
        return resolved

    fallback = (Path(tempfile.gettempdir()) / leaf_name).resolve()
    ensure_outside_roots(fallback, project_roots)
    fallback.mkdir(parents=True, exist_ok=True)
    return fallback


def _create_derived_temp_dir(base_dir: Path, *, prefix: str) -> Path:
    base_dir.mkdir(parents=True, exist_ok=True)
    for _ in range(128):
        candidate = base_dir / f"{prefix}{uuid.uuid4().hex}"
        try:
            candidate.mkdir(mode=0o777)
        except FileExistsError:
            continue
        except PermissionError:
            if os.name == "nt" and base_dir.is_dir() and os.access(base_dir, os.W_OK):
                continue
            raise
        return candidate.resolve()
    raise FileExistsError(f"unable to allocate derived temp dir under {base_dir}")


def build_experiment_temp_root(project_roots: list[str | Path], prefix: str = "cerebro_recall_eval_") -> str:
    temp_base = _resolve_usable_temp_base(project_roots, leaf_name="runtime")
    temp_root = _create_derived_temp_dir(temp_base, prefix=prefix)
    ensure_outside_roots(temp_root, project_roots)
    return str(temp_root)


def build_reusable_index_cache_root(
    project_roots: list[str | Path],
    prefix: str = "cerebro_recall_eval_index_cache",
) -> str:
    cache_root = _resolve_usable_temp_base(project_roots, leaf_name="cache") / prefix
    ensure_outside_roots(cache_root, project_roots)
    cache_root.mkdir(parents=True, exist_ok=True)
    return str(cache_root)


def _tokenize(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized.lower():
        if char.isalnum() or char == "_":
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tokens


def _read_text_file(path: Path, limit: int = 160_000) -> str:
    for encoding in ("utf-8", "utf-8-sig", "latin-1"):
        try:
            return path.read_text(encoding=encoding)[:limit]
        except (OSError, UnicodeDecodeError):
            continue
    try:
        return path.read_bytes()[:limit].decode("utf-8", errors="ignore")
    except OSError:
        return ""


def _iter_candidate_files(root: Path) -> list[Path]:
    paths: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
        for filename in filenames:
            paths.append(Path(dirpath) / filename)
    return sorted(paths)


def _iter_candidate_directories(root: Path) -> list[Path]:
    directories = [root]
    for dirpath, dirnames, _ in os.walk(root):
        current_path = Path(dirpath)
        if current_path != root:
            directories.append(current_path)
        dirnames[:] = [name for name in dirnames if name not in SKIP_DIRS]
    return sorted(set(directories))


def build_project_index(
    project_name: str,
    root: str | Path,
    temp_root: str | Path,
    *,
    cache_root: str | Path | None = None,
) -> ProjectIndex:
    root_path = Path(root).resolve()
    temp_root_path = Path(temp_root).resolve()
    ensure_outside_roots(temp_root_path, [root_path])
    cache_status = "disabled"
    cache_signature: str | None = None
    cache_path: Path | None = None

    if cache_root is not None:
        cache_root_path = Path(cache_root).resolve()
        cache_root_path.mkdir(parents=True, exist_ok=True)
        ensure_outside_roots(cache_root_path, [root_path])
        cache_path = cache_root_path / _cache_file_name(project_name, root_path)
        cached_index = _load_cached_project_index(
            cache_path,
            project_name=project_name,
            root_path=root_path,
            temp_root_path=temp_root_path,
        )
        if cached_index is not None:
            _write_index_manifest(
                project_name=project_name,
                root_path=root_path,
                temp_root_path=temp_root_path,
                chunk_count=len(cached_index.index.chunks),
                cache_status="hit",
                cache_path=cache_path,
                cache_signature=cached_index.signature,
            )
            return cached_index.index
        cache_status = "miss"

    candidate_files = _iter_candidate_files(root_path)
    candidate_directories = _iter_candidate_directories(root_path)
    source_inventory = _build_source_inventory(root_path, candidate_files)
    directory_inventory = _build_directory_inventory(root_path, candidate_directories)
    cache_signature = _build_cache_signature(project_name, root_path, source_inventory)

    source_artifacts = _collect_source_artifacts(project_name, root_path, source_inventory)
    indexed_chunks, idf = _build_fresh_project_index(source_artifacts)
    index = ProjectIndex(
        project_name=project_name,
        root=str(root_path),
        temp_root=str(temp_root_path),
        chunks=tuple(indexed_chunks),
        idf=idf,
    )

    if cache_path is not None:
        try:
            _write_cached_project_index(
                cache_path,
                index,
                cache_signature,
                source_inventory,
                directory_inventory,
            )
        except OSError:
            cache_status = "write-failed"

    _write_index_manifest(
        project_name=project_name,
        root_path=root_path,
        temp_root_path=temp_root_path,
        chunk_count=len(index.chunks),
        cache_status=cache_status,
        cache_path=cache_path,
        cache_signature=cache_signature,
    )
    return index


def _build_fresh_project_index(
    source_artifacts: list[SourceArtifact],
) -> tuple[list[IndexedChunk], dict[str, float]]:
    raw_chunks: list[TextChunk] = []
    for artifact in source_artifacts:
        chunk_kwargs = {}
        if artifact.source_kind == "path-metadata":
            chunk_kwargs = {"max_chars": 400, "overlap_chars": 0}
        raw_chunks.extend(
            chunk_text(
                project_name=artifact.project_name,
                root=artifact.root,
                path=artifact.path,
                text=artifact.text,
                source_kind=artifact.source_kind,
                **chunk_kwargs,
            )
        )

    document_frequency: defaultdict[str, int] = defaultdict(int)
    chunk_token_counts: list[Counter[str]] = []
    for chunk in raw_chunks:
        token_counts = Counter(_tokenize(chunk.text))
        chunk_token_counts.append(token_counts)
        for token in token_counts:
            document_frequency[token] += 1

    total_chunks = max(1, len(raw_chunks))
    idf = {
        token: math.log(1.0 + total_chunks / (1.0 + frequency))
        for token, frequency in document_frequency.items()
    }

    indexed_chunks: list[IndexedChunk] = []
    for chunk, token_counts in zip(raw_chunks, chunk_token_counts):
        weighted_tokens: dict[str, float] = {}
        norm_sq = 0.0
        for token, count in token_counts.items():
            weight = (1.0 + math.log(count)) * idf[token]
            weighted_tokens[token] = weight
            norm_sq += weight * weight
        scope, scope_flags = classify_scope(chunk.path)
        indexed_chunks.append(
            IndexedChunk(
                project_name=chunk.project_name,
                root=chunk.root,
                path=chunk.path,
                chunk_id=chunk.chunk_id,
                text=chunk.text,
                source_kind=chunk.source_kind,
                scope=scope,
                scope_flags=tuple(scope_flags),
                token_counts=dict(token_counts),
                weighted_tokens=weighted_tokens,
                vector_norm=math.sqrt(norm_sq),
                semantic_vector=embed_sparse(f"{chunk.path}\n{chunk.text}"),
            )
        )

    return indexed_chunks, idf


def _collect_source_artifacts(
    project_name: str,
    root_path: Path,
    source_inventory: list[SourceInventoryEntry],
) -> list[SourceArtifact]:
    artifacts: list[SourceArtifact] = []
    for source in source_inventory:
        if source.source_kind == "text":
            file_path = root_path / Path(source.path)
            text = _read_text_file(file_path)
            if text.strip():
                artifacts.append(
                    SourceArtifact(
                        project_name=project_name,
                        root=str(root_path),
                        path=source.path,
                        text=text,
                        source_kind="text",
                    )
                )
            continue
        if source.source_kind == "path-metadata":
            artifacts.append(
                SourceArtifact(
                    project_name=project_name,
                    root=str(root_path),
                    path=source.path,
                    text=source.path,
                    source_kind="path-metadata",
                )
            )
    return artifacts


def _build_cache_signature(
    project_name: str,
    root_path: Path,
    source_inventory: list[SourceInventoryEntry],
) -> str:
    signature_input = {
        "format_version": INDEX_CACHE_FORMAT_VERSION,
        "project_name": project_name,
        "root_fingerprint": _fingerprint_text(str(root_path)),
        "builder_fingerprint": _builder_fingerprint(),
        "inventory": [_serialize_source_inventory_entry(entry) for entry in source_inventory],
    }
    encoded = json.dumps(signature_input, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return sha256(encoded).hexdigest()


@dataclass(frozen=True)
class CachedProjectIndex:
    index: ProjectIndex
    signature: str | None


def _load_cached_project_index(
    cache_path: Path,
    *,
    project_name: str,
    root_path: Path,
    temp_root_path: Path,
) -> CachedProjectIndex | None:
    try:
        payload = json.loads(cache_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError, json.JSONDecodeError):
        return None
    if payload.get("format_version") != INDEX_CACHE_FORMAT_VERSION:
        return None
    if payload.get("root_fingerprint") != _fingerprint_text(str(root_path)):
        return None
    source_inventory = _deserialize_source_inventory(payload.get("inventory"))
    directory_inventory = _deserialize_directory_inventory(payload.get("directories"))
    if source_inventory is None or directory_inventory is None:
        return None
    if payload.get("signature") != _build_cache_signature(project_name, root_path, source_inventory):
        return None
    if not _cached_tree_state_matches(root_path, source_inventory, directory_inventory):
        return None
    return CachedProjectIndex(
        index=_deserialize_project_index(payload, root_path=root_path, temp_root_path=temp_root_path),
        signature=payload.get("signature"),
    )


def _write_cached_project_index(
    cache_path: Path,
    index: ProjectIndex,
    cache_signature: str,
    source_inventory: list[SourceInventoryEntry],
    directory_inventory: list[DirectoryInventoryEntry],
) -> None:
    payload = {
        "format_version": INDEX_CACHE_FORMAT_VERSION,
        "signature": cache_signature,
        "root_fingerprint": _fingerprint_text(index.root),
        "inventory": [_serialize_source_inventory_entry(entry) for entry in source_inventory],
        "directories": [_serialize_directory_inventory_entry(entry) for entry in directory_inventory],
        "index": {
            "project_name": index.project_name,
            "idf": index.idf,
            "chunks": [_serialize_indexed_chunk(chunk) for chunk in index.chunks],
        },
    }
    _write_text_atomic(cache_path, json.dumps(payload, ensure_ascii=False))


def _deserialize_project_index(payload: dict, *, root_path: Path, temp_root_path: Path) -> ProjectIndex:
    index_payload = payload["index"]
    chunks = []
    for chunk_data in index_payload["chunks"]:
        semantic_vector = chunk_data.get("semantic_vector")
        if semantic_vector is not None:
            semantic_vector = (
                {int(key): value for key, value in semantic_vector[0].items()},
                semantic_vector[1],
            )
        chunks.append(
            IndexedChunk(
                project_name=chunk_data["project_name"],
                root=str(root_path),
                path=chunk_data["path"],
                chunk_id=chunk_data["chunk_id"],
                text=chunk_data["text"],
                source_kind=chunk_data["source_kind"],
                scope=chunk_data["scope"],
                scope_flags=tuple(chunk_data["scope_flags"]),
                token_counts=dict(chunk_data["token_counts"]),
                weighted_tokens=dict(chunk_data["weighted_tokens"]),
                vector_norm=chunk_data["vector_norm"],
                semantic_vector=semantic_vector,
            )
        )
    return ProjectIndex(
        project_name=index_payload["project_name"],
        root=str(root_path),
        temp_root=str(temp_root_path),
        chunks=tuple(chunks),
        idf=dict(index_payload["idf"]),
    )


def _write_index_manifest(
    *,
    project_name: str,
    root_path: Path,
    temp_root_path: Path,
    chunk_count: int,
    cache_status: str,
    cache_path: Path | None,
    cache_signature: str | None,
) -> None:
    manifest_path = temp_root_path / f"{project_name.lower().replace(' ', '_')}_index_manifest.json"
    manifest = {
        "experimental": True,
        "authority": "derived-assistive",
        "non_authoritative": True,
        "read_only": True,
        "project_name": project_name,
        "root": str(root_path),
        "temp_root": str(temp_root_path),
        "chunk_count": chunk_count,
        "source_extensions": sorted(TEXT_EXTENSIONS | PATH_ONLY_EXTENSIONS),
        "cache": {
            "status": cache_status,
            "entry": cache_path.name if cache_path is not None else None,
            "signature": cache_signature,
        },
    }
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def _slugify_project_name(project_name: str) -> str:
    return project_name.lower().replace(" ", "_")


def _fingerprint_text(value: str) -> str:
    return sha256(value.encode("utf-8")).hexdigest()


def _build_source_inventory(root_path: Path, candidate_files: list[Path]) -> list[SourceInventoryEntry]:
    inventory: list[SourceInventoryEntry] = []
    for file_path in candidate_files:
        try:
            stats = file_path.stat()
        except OSError:
            continue
        source_kind = _classify_inventory_source_kind(file_path, stats.st_size)
        if source_kind is None:
            continue
        inventory.append(
            SourceInventoryEntry(
                path=file_path.relative_to(root_path).as_posix(),
                source_kind=source_kind,
                size=stats.st_size,
                mtime_ns=stats.st_mtime_ns,
                ctime_ns=stats.st_ctime_ns,
            )
        )
    return inventory


def _build_directory_inventory(root_path: Path, directories: list[Path]) -> list[DirectoryInventoryEntry]:
    inventory: list[DirectoryInventoryEntry] = []
    for directory in directories:
        try:
            stats = directory.stat()
        except OSError:
            continue
        inventory.append(
            DirectoryInventoryEntry(
                path=_relative_dir_path(root_path, directory),
                mtime_ns=stats.st_mtime_ns,
                ctime_ns=stats.st_ctime_ns,
            )
        )
    return inventory


def _classify_inventory_source_kind(file_path: Path, size: int) -> str | None:
    if is_path_only_extension(file_path):
        return "path-metadata"
    if is_textual_extension(file_path) or (file_path.suffix == "" and size <= 200_000):
        return "text"
    return None


def _serialize_source_inventory_entry(entry: SourceInventoryEntry) -> dict:
    return {
        "path": entry.path,
        "source_kind": entry.source_kind,
        "size": entry.size,
        "mtime_ns": entry.mtime_ns,
        "ctime_ns": entry.ctime_ns,
    }


def _serialize_directory_inventory_entry(entry: DirectoryInventoryEntry) -> dict:
    return {
        "path": entry.path,
        "mtime_ns": entry.mtime_ns,
        "ctime_ns": entry.ctime_ns,
    }


def _deserialize_source_inventory(payload: object) -> list[SourceInventoryEntry] | None:
    if not isinstance(payload, list):
        return None
    entries: list[SourceInventoryEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            return None
        try:
            entries.append(
                SourceInventoryEntry(
                    path=str(item["path"]),
                    source_kind=str(item["source_kind"]),
                    size=int(item["size"]),
                    mtime_ns=int(item["mtime_ns"]),
                    ctime_ns=int(item["ctime_ns"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            return None
    return entries


def _deserialize_directory_inventory(payload: object) -> list[DirectoryInventoryEntry] | None:
    if not isinstance(payload, list):
        return None
    entries: list[DirectoryInventoryEntry] = []
    for item in payload:
        if not isinstance(item, dict):
            return None
        try:
            entries.append(
                DirectoryInventoryEntry(
                    path=str(item["path"]),
                    mtime_ns=int(item["mtime_ns"]),
                    ctime_ns=int(item["ctime_ns"]),
                )
            )
        except (KeyError, TypeError, ValueError):
            return None
    return entries


def _cached_tree_state_matches(
    root_path: Path,
    source_inventory: list[SourceInventoryEntry],
    directory_inventory: list[DirectoryInventoryEntry],
) -> bool:
    for directory in directory_inventory:
        directory_path = _directory_path_from_relative(root_path, directory.path)
        try:
            stats = directory_path.stat()
        except OSError:
            return False
        if not directory_path.is_dir():
            return False
        if stats.st_mtime_ns != directory.mtime_ns or stats.st_ctime_ns != directory.ctime_ns:
            return False

    for source in source_inventory:
        file_path = root_path / Path(source.path)
        try:
            stats = file_path.stat()
        except OSError:
            return False
        if _classify_inventory_source_kind(file_path, stats.st_size) != source.source_kind:
            return False
        if stats.st_size != source.size:
            return False
        if stats.st_mtime_ns != source.mtime_ns or stats.st_ctime_ns != source.ctime_ns:
            return False
    return True


def _relative_dir_path(root_path: Path, directory: Path) -> str:
    if directory == root_path:
        return "."
    return directory.relative_to(root_path).as_posix()


def _directory_path_from_relative(root_path: Path, relative: str) -> Path:
    if relative == ".":
        return root_path
    return root_path / Path(relative)


def _cache_file_name(project_name: str, root_path: Path) -> str:
    return f"{_slugify_project_name(project_name)}_{_fingerprint_text(str(root_path))[:16]}.json"


@lru_cache(maxsize=1)
def _builder_fingerprint() -> str:
    builder_inputs = [
        Path(__file__),
        Path(__file__).with_name("chunker.py"),
        Path(__file__).with_name("scope_classifier.py"),
        Path(__file__).with_name("semantic_vectors.py"),
        Path(__file__).with_name("lexical_scoring.py"),
    ]
    parts = []
    for path in builder_inputs:
        parts.append(path.name)
        parts.append(path.read_text(encoding="utf-8"))
    return _fingerprint_text("\n".join(parts))


def _serialize_indexed_chunk(chunk: IndexedChunk) -> dict:
    payload = asdict(chunk)
    payload.pop("root", None)
    return payload


def _write_text_atomic(path: Path, text: str) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass
