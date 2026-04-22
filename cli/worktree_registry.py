"""Helpers for the local git-worktree registry."""

from __future__ import annotations

from collections.abc import Callable
from contextlib import contextmanager
import os
from pathlib import Path
import re
import tempfile
import time
import tomllib


WORKTREE_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class WorktreeRegistryError(RuntimeError):
    """Raised when the local worktree registry cannot be loaded or saved safely."""


def _local_cerebro_dirname() -> str:
    return "." + "cerebro"


def worktree_registry_path(repo_root: Path) -> Path:
    """Return the worktree registry path for one repository root."""
    return Path(repo_root).resolve() / _local_cerebro_dirname() / "worktrees.toml"


def validate_worktree_name(name: str) -> str:
    """Validate a strict one-segment worktree slug."""
    candidate = name.strip()
    if not candidate:
        raise WorktreeRegistryError("worktree name is required")
    path_candidate = Path(candidate)
    if path_candidate.is_absolute():
        raise WorktreeRegistryError(f"worktree name must be a slug, not an absolute path: {name}")
    if any(part == ".." for part in path_candidate.parts):
        raise WorktreeRegistryError(f"worktree name cannot contain '..': {name}")
    if len(path_candidate.parts) != 1:
        raise WorktreeRegistryError(f"worktree name must be one path segment: {name}")
    if "/" in candidate or "\\" in candidate:
        raise WorktreeRegistryError(f"worktree name must not contain path separators: {name}")
    if not WORKTREE_NAME_PATTERN.fullmatch(candidate):
        raise WorktreeRegistryError(
            "worktree name must start with an alphanumeric character and contain only letters, digits, '.', '_' or '-'"
        )
    return candidate


def load_worktrees(repo_root: Path) -> list[dict[str, str]]:
    """Load worktree entries from the repository-local registry."""
    return _load_worktrees_unlocked(worktree_registry_path(repo_root))


def save_worktrees(repo_root: Path, worktrees: list[dict[str, str]]) -> None:
    """Persist worktree entries atomically under a local registry lock."""
    repo_root = Path(repo_root).resolve()
    validated = [_validate_worktree_entry(repo_root, item) for item in worktrees]
    path = worktree_registry_path(repo_root)
    with _worktree_registry_lock(path):
        _save_worktrees_unlocked(path, validated)


def update_worktrees(
    repo_root: Path,
    updater: Callable[[list[dict[str, str]]], list[dict[str, str]]],
) -> list[dict[str, str]]:
    """Read-modify-write worktree entries under one registry lock."""
    repo_root = Path(repo_root).resolve()
    path = worktree_registry_path(repo_root)
    with _worktree_registry_lock(path):
        current = _load_worktrees_unlocked(path)
        updated = updater(current)
        validated = [_validate_worktree_entry(repo_root, item) for item in updated]
        _save_worktrees_unlocked(path, validated)
        return validated


class LockedWorktreeRegistry:
    """Access the registry under one explicit external lock boundary."""

    def __init__(self, repo_root: Path, path: Path):
        self._repo_root = Path(repo_root).resolve()
        self._path = Path(path).resolve()

    def load(self) -> list[dict[str, str]]:
        return _load_worktrees_unlocked(self._path)

    def save(self, worktrees: list[dict[str, str]]) -> list[dict[str, str]]:
        validated = [_validate_worktree_entry(self._repo_root, item) for item in worktrees]
        _save_worktrees_unlocked(self._path, validated)
        return validated


@contextmanager
def locked_worktree_registry(repo_root: Path, *, timeout_seconds: float = 30.0):
    """Expose one locked read-modify-write boundary for worktree commands."""
    repo_root = Path(repo_root).resolve()
    path = worktree_registry_path(repo_root)
    with _worktree_registry_lock(path, timeout_seconds=timeout_seconds):
        yield LockedWorktreeRegistry(repo_root, path)


def _validate_worktree_entry(repo_root: Path, item: dict[str, str]) -> dict[str, str]:
    name = validate_worktree_name(item["name"])
    branch = str(item["branch"]).strip()
    created_at = str(item["created_at"]).strip()
    status = str(item["status"]).strip()
    if not branch:
        raise WorktreeRegistryError(f"worktree entry is missing branch: {name}")
    if not created_at:
        raise WorktreeRegistryError(f"worktree entry is missing created_at: {name}")
    if not status:
        raise WorktreeRegistryError(f"worktree entry is missing status: {name}")

    path_value = Path(str(item["path"])).expanduser()
    if not path_value.is_absolute():
        path_value = (repo_root / path_value).resolve()
    else:
        path_value = path_value.resolve()

    expected_parent = (repo_root / ".worktrees").resolve()
    try:
        path_value.relative_to(expected_parent)
    except ValueError as exc:
        raise WorktreeRegistryError(f"worktree path escapes .worktrees/: {path_value}") from exc
    if path_value.name != name:
        raise WorktreeRegistryError(f"worktree entry name does not match path basename: {name} != {path_value.name}")

    return {
        "name": name,
        "path": str(path_value),
        "branch": branch,
        "created_at": created_at,
        "status": status,
    }


def _load_worktrees_unlocked(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise WorktreeRegistryError(f"failed to read worktree registry: {path}") from exc
    return _normalize_worktrees(data, path)


def _normalize_worktrees(data: object, path: Path) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        raise WorktreeRegistryError(f"worktree registry is invalid: {path}")
    raw_worktrees = data.get("worktrees", [])
    if not isinstance(raw_worktrees, list):
        raise WorktreeRegistryError(f"worktree registry is invalid: {path}")

    normalized: list[dict[str, str]] = []
    repo_root = path.parent.parent.resolve()
    for item in raw_worktrees:
        if not isinstance(item, dict):
            raise WorktreeRegistryError(f"worktree registry is invalid: {path}")
        try:
            normalized.append(_validate_worktree_entry(repo_root, item))
        except KeyError as exc:
            raise WorktreeRegistryError(f"worktree registry is invalid: {path}") from exc
    return normalized


def _save_worktrees_unlocked(path: Path, worktrees: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _render_worktrees_toml(worktrees)
    with tempfile.NamedTemporaryFile(
        "w",
        encoding="utf-8",
        dir=path.parent,
        prefix=f"{path.name}.",
        suffix=".tmp",
        delete=False,
    ) as handle:
        handle.write(payload)
        temp_path = Path(handle.name)
    try:
        os.replace(temp_path, path)
    except OSError as exc:
        temp_path.unlink(missing_ok=True)
        raise WorktreeRegistryError(f"failed to write worktree registry: {path}") from exc


@contextmanager
def _worktree_registry_lock(path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise WorktreeRegistryError(f"timed out waiting for worktree registry lock: {lock_path}")
            time.sleep(poll_seconds)
        except OSError as exc:
            raise WorktreeRegistryError(f"failed to acquire worktree registry lock: {lock_path}") from exc

    body_error: Exception | None = None
    try:
        os.close(lock_fd)
        yield
    except Exception as exc:
        body_error = exc
        raise
    finally:
        try:
            lock_path.unlink(missing_ok=True)
        except OSError as exc:
            if body_error is None:
                raise WorktreeRegistryError(f"failed to release worktree registry lock: {lock_path}") from exc
            raise WorktreeRegistryError(f"{body_error}; failed to release worktree registry lock: {lock_path}") from exc


def _render_worktrees_toml(worktrees: list[dict[str, str]]) -> str:
    lines: list[str] = []
    for item in worktrees:
        lines.append("[[worktrees]]")
        lines.append(f'name = "{_escape_toml_string(item["name"])}"')
        lines.append(f'path = "{_escape_toml_string(item["path"])}"')
        lines.append(f'branch = "{_escape_toml_string(item["branch"])}"')
        lines.append(f'created_at = "{_escape_toml_string(item["created_at"])}"')
        lines.append(f'status = "{_escape_toml_string(item["status"])}"')
        lines.append("")
    return "\n".join(lines).rstrip() + ("\n" if lines else "")


def _escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
