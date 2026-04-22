from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import hashlib


TEXT_EXTENSIONS = {
    ".md",
    ".txt",
    ".py",
    ".ps1",
    ".toml",
    ".json",
    ".yaml",
    ".yml",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".html",
    ".css",
    ".scss",
    ".sql",
    ".csv",
    ".tsv",
    ".xml",
    ".ini",
    ".cfg",
    ".bat",
    ".sh",
    ".java",
    ".c",
    ".cpp",
    ".h",
    ".cs",
    ".rb",
    ".php",
    ".base",
    ".example",
    ".rels",
}

PATH_ONLY_EXTENSIONS = {
    ".pdf",
    ".xlsx",
    ".zip",
    ".png",
    ".jpg",
    ".jpeg",
    ".jar",
    ".dll",
    ".exe",
}


@dataclass(frozen=True)
class TextChunk:
    project_name: str
    root: str
    path: str
    chunk_id: int
    text: str
    source_kind: str
    content_hash: str


def is_textual_extension(path: str | Path) -> bool:
    return Path(path).suffix.lower() in TEXT_EXTENSIONS


def is_path_only_extension(path: str | Path) -> bool:
    return Path(path).suffix.lower() in PATH_ONLY_EXTENSIONS


def chunk_text(
    *,
    project_name: str,
    root: str,
    path: str,
    text: str,
    source_kind: str = "text",
    max_chars: int = 1200,
    overlap_chars: int = 200,
) -> list[TextChunk]:
    normalized = (text or "").replace("\r\n", "\n").replace("\r", "\n")
    seeded = f"{path}\n{normalized}".strip()
    if not seeded:
        seeded = path

    chunks: list[TextChunk] = []
    start = 0
    chunk_id = 0
    while start < len(seeded):
        end = min(len(seeded), start + max_chars)
        window = seeded[start:end].strip()
        if not window:
            break
        content_hash = hashlib.sha256(window.encode("utf-8")).hexdigest()
        chunks.append(
            TextChunk(
                project_name=project_name,
                root=root,
                path=path,
                chunk_id=chunk_id,
                text=window,
                source_kind=source_kind,
                content_hash=content_hash,
            )
        )
        if end >= len(seeded):
            break
        start = max(0, end - overlap_chars)
        chunk_id += 1
    return chunks
