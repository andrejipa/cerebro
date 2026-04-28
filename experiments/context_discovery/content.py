"""Bounded content reading and heading-signal extraction.

This module is kept narrow on purpose. It performs the one thing that the
`cli/commands/bootstrap_scan.py` surface is formally forbidden from doing:
open files on disk, read a bounded head, and extract lightweight content
signals. It does so outside of any canonical runtime path, and every read is
capped by both line count and byte count.
"""

from __future__ import annotations

from pathlib import Path
import re


MAX_CONTENT_LINES = 40
MAX_CONTENT_BYTES = 16 * 1024

TEXTUAL_SUFFIXES: frozenset[str] = frozenset(
    {".adoc", ".json", ".md", ".rst", ".toml", ".txt", ".yaml", ".yml"}
)

_HEADING_TOKENS_PROJECT: frozenset[str] = frozenset(
    {"project", "projeto", "scope", "escopo", "overview", "visao", "visão"}
)
_HEADING_TOKENS_ARCHITECTURE: frozenset[str] = frozenset(
    {"architecture", "arquitetura", "adr", "decision", "decisao", "decisão"}
)
_HEADING_TOKENS_CONTINUITY: frozenset[str] = frozenset(
    {
        "handoff",
        "retomada",
        "continuidade",
        "continuity",
        "context",
        "contexto",
        "resumo",
        "memoria",
        "memória",
    }
)
_HEADING_TOKENS_CURRENT_STATE: frozenset[str] = frozenset(
    {"current", "atual", "estado", "state", "vigente", "status"}
)
_ADR_CODE_PATTERN = re.compile(r"\badr[-_]?\d{2,4}\b", re.IGNORECASE)
_HEADING_WORD_SPLIT = re.compile(r"[^a-zà-úçãõáéíóúâêôü0-9]+")


def read_content_head(absolute_path: Path) -> str | None:
    """Read a bounded head of a textual file, or return None.

    Returns None when the file is missing, is a symlink, is a directory, is
    not decodable as UTF-8, contains null bytes (treated as binary), or its
    suffix is not recognised as textual. The caller treats None as "no
    content signal available" and must not infer anything from it.
    """

    if absolute_path.suffix.lower() not in TEXTUAL_SUFFIXES:
        return None
    try:
        if absolute_path.is_symlink():
            return None
        if not absolute_path.is_file():
            return None
        with absolute_path.open("rb") as handle:
            blob = handle.read(MAX_CONTENT_BYTES + 1)
    except OSError:
        return None

    if len(blob) > MAX_CONTENT_BYTES:
        blob = blob[:MAX_CONTENT_BYTES]
    if b"\x00" in blob:
        return None
    try:
        text = blob.decode("utf-8")
    except UnicodeDecodeError:
        return None

    lines = text.splitlines()
    if len(lines) > MAX_CONTENT_LINES:
        lines = lines[:MAX_CONTENT_LINES]
    return "\n".join(lines)


def first_heading(content_head: str) -> str:
    """Return the first markdown-style heading line, or the first non-empty line."""

    if not content_head:
        return ""
    for line in content_head.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            return stripped
    for line in content_head.splitlines():
        stripped = line.strip()
        if stripped:
            return stripped
    return ""


def _heading_word_tokens(heading_line: str) -> frozenset[str]:
    stripped = heading_line.lstrip("#").strip().lower()
    return frozenset(token for token in _HEADING_WORD_SPLIT.split(stripped) if token)


def content_role_signals(suffix: str, content_head: str) -> list[tuple[str, int, str]]:
    """Return (role, score, reason) tuples describing what this content looks like.

    Roles are coarse: `project-scope`, `architecture-decision`, `continuity`,
    `current-state`. Scores are modest, intentionally; final ranking is the
    caller's responsibility. Each role is emitted at most once per file.
    """

    if not content_head:
        return []

    signals: list[tuple[str, int, str]] = []
    saw = {"project-scope": False, "architecture-decision": False, "continuity": False, "current-state": False}

    for raw_line in content_head.splitlines():
        if not raw_line.startswith("#"):
            continue
        tokens = _heading_word_tokens(raw_line)
        if not tokens:
            continue
        if not saw["project-scope"] and tokens & _HEADING_TOKENS_PROJECT:
            signals.append(("project-scope", 40, "content: project-scope heading"))
            saw["project-scope"] = True
        if not saw["architecture-decision"] and tokens & _HEADING_TOKENS_ARCHITECTURE:
            signals.append(("architecture-decision", 40, "content: architecture-decision heading"))
            saw["architecture-decision"] = True
        if not saw["continuity"] and tokens & _HEADING_TOKENS_CONTINUITY:
            signals.append(("continuity", 40, "content: continuity or handoff heading"))
            saw["continuity"] = True
        if (
            not saw["current-state"]
            and "atual" in tokens
            and tokens & {"estado", "current", "state"}
        ):
            signals.append(("current-state", 35, "content: current-state heading"))
            saw["current-state"] = True

    if not saw["architecture-decision"] and _ADR_CODE_PATTERN.search(content_head):
        signals.append(("architecture-decision", 20, "content: ADR identifier reference"))

    suffix_lower = suffix.lower()
    if suffix_lower == ".toml" and re.search(
        r"^\s*\[(project|tool\.[a-z][a-z0-9_\-]*)\]",
        content_head,
        re.IGNORECASE | re.MULTILINE,
    ):
        signals.append(("project-scope", 12, "content: toml project block"))
    if suffix_lower == ".json" and re.search(r'"name"\s*:\s*"[^"\n]+"', content_head):
        signals.append(("project-scope", 8, "content: json name field"))

    return signals
