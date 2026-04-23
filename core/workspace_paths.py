"""Shared pure helpers for resolving workspace-relative paths."""

from __future__ import annotations

from pathlib import Path


def resolve_workspace_relative_path(root: Path, raw_path: str) -> Path:
    """Resolve a relative workspace path and guarantee it stays within root."""
    candidate = Path(raw_path)
    if candidate.is_absolute():
        raise ValueError(f"path must be relative: {raw_path}")
    if any(part == ".." for part in candidate.parts):
        raise ValueError(f"path cannot contain '..': {raw_path}")

    root_resolved = root.resolve()
    resolved = (root_resolved / candidate).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError as exc:
        raise ValueError(f"path resolves outside workspace: {raw_path}") from exc
    return resolved
