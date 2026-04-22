"""Helpers for sandboxed command execution against disposable project clones."""

from __future__ import annotations

import hashlib
import os
import shutil
import tempfile
from pathlib import Path


def _sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(65536), b""):
            digest.update(chunk)
    return digest.hexdigest()


def capture_tree_manifest(root: Path) -> dict[str, tuple]:
    """Return an observable manifest for one project tree."""
    manifest: dict[str, tuple] = {
        ".": ("dir", root.stat().st_mtime_ns),
    }
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        dirnames.sort()
        filenames.sort()
        for dirname in dirnames:
            directory = current_path / dirname
            relative = directory.relative_to(root).as_posix()
            if directory.is_symlink():
                manifest[relative] = ("symlink", os.readlink(directory))
                continue
            manifest[relative] = ("dir", directory.stat().st_mtime_ns)
        for filename in filenames:
            entry = current_path / filename
            relative = entry.relative_to(root).as_posix()
            if entry.is_symlink():
                manifest[relative] = ("symlink", os.readlink(entry))
                continue
            if entry.is_file():
                stat = entry.stat()
                manifest[relative] = ("file", stat.st_size, stat.st_mtime_ns, _sha256_file(entry))
                continue
            stat = entry.stat()
            manifest[relative] = ("other", stat.st_mode, stat.st_mtime_ns)
    return manifest


def has_meaningful_manifest_change(before_marker: tuple | None, after_marker: tuple | None) -> bool:
    """Ignore directory mtime churn and focus on observable tree drift."""
    if before_marker == after_marker:
        return False
    if before_marker is None or after_marker is None:
        return True
    if before_marker[0] == "dir" and after_marker[0] == "dir":
        return False
    return True


def summarize_manifest_diff(before: dict[str, tuple], after: dict[str, tuple], *, limit: int = 5) -> str:
    """Return a bounded human-readable summary of observable tree drift."""
    changes: list[str] = []
    for relative in sorted(set(before).union(after)):
        before_marker = before.get(relative)
        after_marker = after.get(relative)
        if not has_meaningful_manifest_change(before_marker, after_marker):
            continue
        if before_marker is None:
            changes.append(f"created {relative}")
        elif after_marker is None:
            changes.append(f"deleted {relative}")
        else:
            changes.append(f"changed {relative}")
    if not changes:
        return ""
    summary = "; ".join(changes[:limit])
    if len(changes) > limit:
        summary = f"{summary}; +{len(changes) - limit} more"
    return summary


def prepare_project_sandbox(root: Path) -> tuple[tempfile.TemporaryDirectory[str], Path]:
    """Clone the current project root into a disposable sandbox."""
    sandbox_dir = tempfile.TemporaryDirectory()
    sandbox_root = Path(sandbox_dir.name) / "workspace"
    try:
        shutil.copytree(root, sandbox_root, dirs_exist_ok=True)
    except OSError:
        sandbox_dir.cleanup()
        raise
    return sandbox_dir, sandbox_root
