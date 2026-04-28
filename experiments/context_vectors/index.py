from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os

from core import StateStore, StateStoreError, StateValidationError

from .vectorizer import SparseVector, cosine_similarity, embed_text


DEFAULT_MAX_HEAD_BYTES = 24 * 1024
DEFAULT_MAX_HEAD_LINES = 80
DEFAULT_MAX_FILES = 500

TEXT_SUFFIXES: frozenset[str] = frozenset(
    {".adoc", ".json", ".md", ".py", ".rst", ".sql", ".toml", ".ts", ".tsx", ".txt", ".yaml", ".yml"}
)

SKIP_DIRS: frozenset[str] = frozenset(
    {
        ".cache",
        ".cerebro",
        ".git",
        ".next",
        ".obsidian",
        ".tmp",
        ".venv",
        "__pycache__",
        "build",
        "cerebro",
        "coverage",
        "dist",
        "env",
        "jre",
        "_local",
        "livros_fontes",
        "material_apoio",
        "node_modules",
        "tmp",
        "venv",
    }
)


@dataclass(frozen=True)
class DocumentVector:
    relative_path: str
    source_status: str
    heading: str
    excerpt: str
    vector: SparseVector


@dataclass(frozen=True)
class VectorTrace:
    project_root: str
    scanned_files: int
    indexed_files: int
    skipped_files: int
    registered_source_count: int
    state_status: str
    state_change: str = "none"


@dataclass(frozen=True)
class VectorIndex:
    project_root: str
    documents: tuple[DocumentVector, ...]
    trace: VectorTrace


@dataclass(frozen=True)
class QueryHit:
    relative_path: str
    source_status: str
    score: float
    heading: str
    excerpt: str


class ContextVectorError(RuntimeError):
    pass


def _skip_dir(name: str) -> bool:
    lower = name.lower()
    if lower.startswith(".") or lower in SKIP_DIRS:
        return True
    if lower.startswith("90_") or lower.startswith("98_"):
        return True
    return "historico" in lower


def _iter_candidate_files(root: Path, max_files: int) -> tuple[list[Path], int]:
    files: list[Path] = []
    skipped = 0
    for current_root, dirnames, filenames in os.walk(root):
        dirnames[:] = [dirname for dirname in dirnames if not _skip_dir(dirname)]
        for filename in filenames:
            if filename.startswith("."):
                skipped += 1
                continue
            if Path(filename).suffix.lower() not in TEXT_SUFFIXES:
                skipped += 1
                continue
            if len(files) >= max_files:
                skipped += 1
                continue
            files.append(Path(current_root) / filename)
    return sorted(files), skipped


def _read_head(path: Path, *, max_bytes: int, max_lines: int) -> str | None:
    if path.suffix.lower() not in TEXT_SUFFIXES:
        return None
    try:
        if path.is_symlink() or not path.is_file():
            return None
        with path.open("rb") as handle:
            blob = handle.read(max_bytes + 1)
    except OSError:
        return None
    if b"\x00" in blob:
        return None
    if len(blob) > max_bytes:
        blob = blob[:max_bytes]
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None
    lines = text.splitlines()
    if len(lines) > max_lines:
        lines = lines[:max_lines]
    return "\n".join(lines)


def _heading(text: str) -> str:
    for line in text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped
    for line in text.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped[:120]
    return ""


def _metadata_tokens(text: str) -> set[str]:
    current: list[str] = []
    tokens: set[str] = set()
    for char in text.lower():
        if char.isalnum():
            current.append(char)
            continue
        if current:
            tokens.add("".join(current))
            current.clear()
    if current:
        tokens.add("".join(current))
    return tokens


def _metadata_bonus(query: str, document: DocumentVector) -> float:
    query_tokens = _metadata_tokens(query)
    path_tokens = _metadata_tokens(document.relative_path)
    heading_tokens = _metadata_tokens(document.heading)
    metadata_tokens = path_tokens | heading_tokens
    path_depth = document.relative_path.count("/")

    direct_matches = query_tokens & metadata_tokens
    bonus = min(0.045, 0.015 * len(direct_matches))
    path_matches = query_tokens & path_tokens
    if len(path_matches) >= 2:
        bonus += min(0.14, 0.055 * len(path_matches))

    has_current_work_intent = bool({"atual", "current", "proximo", "next", "step", "passo"} & query_tokens)
    has_implementation_intent = bool({"edge", "functions", "schema", "supabase", "implementar", "implement"} & query_tokens)
    is_continuity_file = bool({"memoria", "memory", "continuidade", "continuity"} & metadata_tokens)
    if has_current_work_intent and has_implementation_intent and is_continuity_file:
        bonus += 0.055

    has_live_surface_intent = bool(
        {"atual", "current", "vigente", "hoje", "estado", "retomada", "entrada", "start"} & query_tokens
    )
    is_live_surface = bool({"vigente", "trabalho", "painel", "relatorios", "dossie"} & path_tokens)
    if has_live_surface_intent and is_live_surface:
        bonus += 0.04

    asks_for_entry = bool({"entrada", "start", "inicio", "ponto", "bootstrap"} & query_tokens)
    is_project_entry = {"entrada", "inicio", "projeto"} <= path_tokens
    if asks_for_entry and is_project_entry:
        bonus += 0.075

    asks_for_index = bool({"readme", "indice", "index", "ordem", "leitura"} & query_tokens)
    is_readme = "readme" in path_tokens
    if asks_for_index and is_readme:
        bonus += 0.05

    asks_for_general_surface = bool(
        {
            "cadastro",
            "estrutura",
            "gestao",
            "mestre",
            "organizacao",
            "sistema",
            "system",
            "geral",
        }
        & query_tokens
    )
    if asks_for_general_surface and is_readme and path_depth <= 2:
        bonus += 0.06

    asks_for_irpf_system = "sistema" in query_tokens and "irpf" in query_tokens
    if asks_for_irpf_system and {"irpf", "readme", "sistema"} <= metadata_tokens:
        bonus += 0.09

    asks_for_client_registry = bool({"cadastro", "mestre", "clientes"} <= query_tokens)
    if asks_for_client_registry and {"cadastro", "mestre", "readme"} <= metadata_tokens:
        bonus += 0.09
    if asks_for_client_registry and path_depth >= 3 and "00_mapa_do_cliente" in document.relative_path.lower():
        bonus -= 0.07

    if "conceito" in path_tokens and "conceito" not in query_tokens:
        bonus -= 0.025

    is_session_memory = bool({"sessao", "manual", "continuidade"} & path_tokens)
    asks_for_session_memory = bool({"sessao", "manual", "continuidade", "continuity"} & query_tokens)
    if is_session_memory and not asks_for_session_memory:
        bonus -= 0.04

    is_template = "template" in metadata_tokens
    if is_template and "template" not in query_tokens:
        bonus -= 0.035

    return bonus


def _registered_sources(root: Path) -> tuple[set[str], str]:
    if not (root / ".cerebro" / "state.json").exists():
        return set(), "absent"
    try:
        store = StateStore(root)
        return {Path(source.path).as_posix() for source in store.read_sources()}, "valid"
    except (StateStoreError, StateValidationError) as exc:
        return set(), f"invalid: {exc}"


def build_vector_index(
    root: str | Path,
    *,
    max_files: int = DEFAULT_MAX_FILES,
    max_head_bytes: int = DEFAULT_MAX_HEAD_BYTES,
    max_head_lines: int = DEFAULT_MAX_HEAD_LINES,
) -> VectorIndex:
    if max_files <= 0:
        raise ValueError(f"max_files must be positive: {max_files}")
    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ContextVectorError(f"project root does not exist or is not a directory: {root_path}")

    registered, state_status = _registered_sources(root_path)
    files, skipped_by_limit = _iter_candidate_files(root_path, max_files)
    documents: list[DocumentVector] = []
    skipped = skipped_by_limit

    for absolute in files:
        relative = absolute.relative_to(root_path).as_posix()
        head = _read_head(absolute, max_bytes=max_head_bytes, max_lines=max_head_lines)
        if head is None or not head.strip():
            skipped += 1
            continue
        source_status = "registered" if relative in registered else "unregistered"
        documents.append(
            DocumentVector(
                relative_path=relative,
                source_status=source_status,
                heading=_heading(head),
                excerpt=head[:240].replace("\n", " "),
                vector=embed_text(f"{relative}\n{head}"),
            )
        )

    trace = VectorTrace(
        project_root=str(root_path),
        scanned_files=len(files),
        indexed_files=len(documents),
        skipped_files=skipped,
        registered_source_count=len(registered),
        state_status=state_status,
    )
    return VectorIndex(project_root=str(root_path), documents=tuple(documents), trace=trace)


def query_index(index: VectorIndex, query: str, *, limit: int = 10, min_score: float = 0.0) -> tuple[QueryHit, ...]:
    if limit <= 0:
        raise ValueError(f"limit must be positive: {limit}")
    query_vector = embed_text(query)
    hits: list[QueryHit] = []
    for document in index.documents:
        score = cosine_similarity(query_vector, document.vector) + _metadata_bonus(query, document)
        if score <= min_score:
            continue
        hits.append(
            QueryHit(
                relative_path=document.relative_path,
                source_status=document.source_status,
                score=score,
                heading=document.heading,
                excerpt=document.excerpt,
            )
        )
    hits.sort(key=lambda hit: (-hit.score, hit.relative_path))
    return tuple(hits[:limit])
