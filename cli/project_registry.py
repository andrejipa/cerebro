"""Helpers for the optional global managed-project registry."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import datetime, timezone
import os
from pathlib import Path
import tempfile
import time
import tomllib


class ProjectRegistryError(RuntimeError):
    """Raised when the global project registry cannot be loaded or saved safely."""


def _global_cerebro_dirname() -> str:
    return "." + "cerebro"


def registry_path() -> Path:
    """Return the global project registry path under the user's home directory."""
    return Path.home().resolve() / _global_cerebro_dirname() / "projects.toml"


def load_projects() -> list[dict[str, str]]:
    """Load project entries from the optional global registry."""
    path = registry_path()
    return _load_projects_unlocked(path)


def register_or_update_project(root: Path) -> list[dict[str, str]]:
    """Register a project root or refresh its metadata, then persist it atomically."""
    resolved_root = root.expanduser().resolve()
    timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
    entry = {
        "name": resolved_root.name or str(resolved_root),
        "path": str(resolved_root),
        "last_used": timestamp,
    }

    path = registry_path()
    with _project_registry_lock(path):
        projects = _load_projects_unlocked(path)
        updated = [entry]
        for item in projects:
            if item["path"] == entry["path"]:
                continue
            updated.append(item)
        _save_projects_unlocked(path, updated)
    return updated


def save_projects(projects: list[dict[str, str]]) -> None:
    """Persist project entries atomically.

    The global registry is optional metadata. It must never become
    authoritative over the runtime root, but concurrent writers still need
    serialization so updates are not silently lost.
    """
    path = registry_path()
    with _project_registry_lock(path):
        _save_projects_unlocked(path, projects)


def _load_projects_unlocked(path: Path) -> list[dict[str, str]]:
    if not path.exists():
        return []
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except (OSError, tomllib.TOMLDecodeError) as exc:
        raise ProjectRegistryError(f"failed to read project registry: {path}") from exc
    return _normalize_projects(data, path)


def _save_projects_unlocked(path: Path, projects: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = _render_projects_toml(projects)
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
        raise ProjectRegistryError(f"failed to write project registry: {path}") from exc


@contextmanager
def _project_registry_lock(path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            break
        except FileExistsError:
            if time.monotonic() >= deadline:
                raise ProjectRegistryError(f"timed out waiting for project registry lock: {lock_path}")
            time.sleep(poll_seconds)
        except OSError as exc:
            raise ProjectRegistryError(f"failed to acquire project registry lock: {lock_path}") from exc
    try:
        os.close(lock_fd)
        yield
    finally:
        lock_path.unlink(missing_ok=True)


def _normalize_projects(data: object, path: Path) -> list[dict[str, str]]:
    if not isinstance(data, dict):
        raise ProjectRegistryError(f"project registry is invalid: {path}")
    raw_projects = data.get("projects", [])
    if not isinstance(raw_projects, list):
        raise ProjectRegistryError(f"project registry is invalid: {path}")
    projects: list[dict[str, str]] = []
    for item in raw_projects:
        if not isinstance(item, dict):
            raise ProjectRegistryError(f"project registry is invalid: {path}")
        name = item.get("name")
        project_path = item.get("path")
        last_used = item.get("last_used")
        if not all(isinstance(value, str) and value.strip() for value in (name, project_path, last_used)):
            raise ProjectRegistryError(f"project registry is invalid: {path}")
        projects.append(
            {
                "name": name.strip(),
                "path": str(Path(project_path).expanduser().resolve()),
                "last_used": last_used.strip(),
            }
        )
    return projects


def _render_projects_toml(projects: list[dict[str, str]]) -> str:
    lines = ['version = 1', ""]
    for item in projects:
        lines.append("[[projects]]")
        lines.append(f'name = "{_escape_toml_string(item["name"])}"')
        lines.append(f'path = "{_escape_toml_string(item["path"])}"')
        lines.append(f'last_used = "{_escape_toml_string(item["last_used"])}"')
        lines.append("")
    return "\n".join(lines)


def _escape_toml_string(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')
