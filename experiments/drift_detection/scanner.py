"""Scan a set of directories and produce FileHashEntry records."""
from __future__ import annotations
from pathlib import Path
from .hasher import ast_hash
from .schema import FileHashEntry


DEFAULT_SCAN_ROOTS = ["core", "cli", "extensions"]
EXCLUDE_PATTERNS = {"__pycache__", ".pyc", ".pyo"}


def scan(repo_root: Path, roots: list[str] | None = None) -> list[FileHashEntry]:
    """Return AST hashes for all .py files under the given roots."""
    roots = roots or DEFAULT_SCAN_ROOTS
    entries: list[FileHashEntry] = []
    for root in roots:
        base = repo_root / root
        if not base.exists():
            continue
        for py_file in sorted(base.rglob("*.py")):
            if any(ex in py_file.parts for ex in EXCLUDE_PATTERNS):
                continue
            rel = str(py_file.relative_to(repo_root))
            h = ast_hash(py_file)
            lc = len(py_file.read_text(encoding="utf-8", errors="replace").splitlines())
            entries.append(FileHashEntry(path=rel, ast_hash=h or "PARSE_ERROR", line_count=lc))
    return entries
