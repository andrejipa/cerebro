from __future__ import annotations

from contextlib import contextmanager, suppress
import json
import os
from pathlib import Path
import time
from typing import Any

from .schema import (
    SCHEMA_VERSION,
    append_record,
    atomic_write_registry,
    ensure_allowed_registry_path,
    load_registry_text,
)


class OperationalSignalsLogError(RuntimeError):
    """Fail-closed error for derived operational-signals registry writes."""


def default_registry_path() -> Path:
    return Path(__file__).with_name("unmet_use_cases.toml")


def load_registry(path: str | Path | None = None) -> dict[str, Any]:
    registry_path = ensure_allowed_registry_path(path or default_registry_path())
    return load_registry_text(registry_path)


def record_unmet_use_case(record: dict[str, Any], *, path: str | Path | None = None) -> dict[str, Any]:
    registry_path = ensure_allowed_registry_path(path or default_registry_path())
    with _registry_lock(registry_path):
        registry = load_registry_text(registry_path)
        updated = append_record(registry, record)
        atomic_write_registry(registry_path, updated)
    return updated["unmet_use_case"][-1]


def initialize_registry(path: str | Path | None = None) -> Path:
    registry_path = ensure_allowed_registry_path(path or default_registry_path())
    with _registry_lock(registry_path):
        if not registry_path.exists():
            atomic_write_registry(registry_path, {"schema_version": SCHEMA_VERSION, "unmet_use_case": []})
    return registry_path


@contextmanager
def _registry_lock(path: Path, *, timeout_seconds: float = 5.0, poll_seconds: float = 0.05):
    lock_path = path.with_suffix(path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                _write_lock_metadata(lock_fd)
            except Exception:
                os.close(lock_fd)
                with suppress(FileNotFoundError):
                    lock_path.unlink()
                raise
            break
        except FileExistsError:
            if _try_recover_stale_lock(lock_path):
                continue
            if time.monotonic() >= deadline:
                if _try_recover_stale_lock(lock_path, allow_unowned=True):
                    continue
                raise OperationalSignalsLogError(
                    f"timed out waiting for operational_signals registry lock: {lock_path}"
                )
            time.sleep(poll_seconds)
        except OSError as exc:
            raise OperationalSignalsLogError(
                f"failed to acquire operational_signals registry lock: {lock_path}"
            ) from exc
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
                raise OperationalSignalsLogError(
                    f"failed to release operational_signals registry lock: {lock_path}"
                ) from exc
            raise OperationalSignalsLogError(
                f"{body_error}; failed to release operational_signals registry lock: {lock_path}"
            ) from exc


def _write_lock_metadata(lock_fd: int) -> None:
    payload = json.dumps(_current_lock_metadata()).encode("utf-8")
    try:
        os.write(lock_fd, payload)
    except OSError as exc:
        raise OperationalSignalsLogError(
            "failed to persist operational_signals registry lock metadata"
        ) from exc


def _current_lock_metadata() -> dict[str, Any]:
    pid = os.getpid()
    metadata: dict[str, Any] = {"pid": pid, "created_at": time.time()}
    process_identity = _read_process_identity(pid)
    if process_identity is not None:
        metadata["process_identity"] = process_identity
    return metadata


def _try_recover_stale_lock(lock_path: Path, *, allow_unowned: bool = False) -> bool:
    metadata = _read_lock_metadata(lock_path)
    if metadata is None:
        if not allow_unowned:
            return False
    else:
        pid = metadata.get("pid")
        if not isinstance(pid, int):
            if not allow_unowned:
                return False
        elif _lock_owner_still_matches(metadata):
            return False
    try:
        lock_path.unlink()
    except FileNotFoundError:
        return True
    except OSError:
        return False
    return True


def _read_lock_metadata(lock_path: Path) -> dict[str, Any] | None:
    try:
        payload = lock_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    if not payload:
        return None
    try:
        metadata = json.loads(payload)
    except json.JSONDecodeError:
        return None
    if not isinstance(metadata, dict):
        return None
    return metadata


def _pid_is_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        return _windows_pid_is_running(pid)
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError as exc:
        return True
    return True


def _lock_owner_still_matches(metadata: dict[str, Any]) -> bool:
    pid = metadata.get("pid")
    if not isinstance(pid, int):
        return False
    if not _pid_is_running(pid):
        return False
    expected_identity = metadata.get("process_identity")
    if expected_identity is None:
        return True
    current_identity = _read_process_identity(pid)
    if current_identity is None:
        return True
    return current_identity == expected_identity


def _read_process_identity(pid: int) -> dict[str, Any] | None:
    if pid <= 0:
        return None
    if os.name == "nt":
        return _read_windows_process_identity(pid)
    if os.name == "posix":
        return _read_procfs_process_identity(pid)
    return None


def _read_procfs_process_identity(pid: int) -> dict[str, Any] | None:
    stat_path = Path(f"/proc/{pid}/stat")
    try:
        payload = stat_path.read_text(encoding="utf-8").strip()
    except OSError:
        return None
    marker = payload.rfind(")")
    if marker < 0:
        return None
    fields = payload[marker + 2 :].split()
    if len(fields) <= 19:
        return None
    return {"platform": "posix-procfs", "start_ticks": fields[19]}


def _windows_pid_is_running(pid: int) -> bool:
    import ctypes

    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if handle:
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    last_error = ctypes.GetLastError()
    if last_error == 87:
        return False
    if last_error == 5:
        return True
    return True


def _read_windows_process_identity(pid: int) -> dict[str, Any] | None:
    import ctypes
    from ctypes import wintypes

    process_query_limited_information = 0x1000
    handle = ctypes.windll.kernel32.OpenProcess(
        process_query_limited_information,
        False,
        pid,
    )
    if not handle:
        return None
    try:
        creation = wintypes.FILETIME()
        exit_time = wintypes.FILETIME()
        kernel = wintypes.FILETIME()
        user = wintypes.FILETIME()
        if not ctypes.windll.kernel32.GetProcessTimes(
            handle,
            ctypes.byref(creation),
            ctypes.byref(exit_time),
            ctypes.byref(kernel),
            ctypes.byref(user),
        ):
            return None
        return {
            "platform": "windows",
            "creation_time_100ns": (creation.dwHighDateTime << 32) | creation.dwLowDateTime,
        }
    finally:
        ctypes.windll.kernel32.CloseHandle(handle)
