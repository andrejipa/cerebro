"""Runtime lock and stale-lock recovery helpers behind the StateStore facade."""

from __future__ import annotations

import errno
import os
import threading
import time
from contextlib import contextmanager
from pathlib import Path
from typing import Callable


class StateRuntimeLockService:
    """Own the runtime lock file lifecycle without taking canonical authority."""

    _process_runtime_lock_counts: dict[str, int] = {}
    _process_runtime_lock_guard = threading.Lock()

    def __init__(
        self,
        *,
        cerebro_dir: Path,
        lock_path: Path,
        error_cls: type[Exception],
        timeout_seconds: Callable[[], float],
        poll_seconds: Callable[[], float],
        release_retry_limit: Callable[[], int],
        pid_probe: Callable[[int], object],
        monotonic: Callable[[], float],
        sleep_fn: Callable[[float], None],
        get_pid: Callable[[], int],
    ) -> None:
        self.cerebro_dir = Path(cerebro_dir)
        self.lock_path = Path(lock_path)
        self._error_cls = error_cls
        self._timeout_seconds = timeout_seconds
        self._poll_seconds = poll_seconds
        self._release_retry_limit = release_retry_limit
        self._pid_probe = pid_probe
        self._monotonic = monotonic
        self._sleep_fn = sleep_fn
        self._get_pid = get_pid
        self._lock_fd: int | None = None
        self._lock_depth = 0

    def register_process_runtime_lock(self) -> None:
        """Mark the runtime lock as held somewhere in the current process."""
        key = str(self.lock_path)
        with StateRuntimeLockService._process_runtime_lock_guard:
            StateRuntimeLockService._process_runtime_lock_counts[key] = (
                StateRuntimeLockService._process_runtime_lock_counts.get(key, 0) + 1
            )

    def unregister_process_runtime_lock(self) -> None:
        """Clear the current-process marker for this runtime lock."""
        key = str(self.lock_path)
        with StateRuntimeLockService._process_runtime_lock_guard:
            count = StateRuntimeLockService._process_runtime_lock_counts.get(key, 0)
            if count <= 1:
                StateRuntimeLockService._process_runtime_lock_counts.pop(key, None)
            else:
                StateRuntimeLockService._process_runtime_lock_counts[key] = count - 1

    def process_runtime_lock_is_held(self) -> bool:
        """Return whether any StateStore in this process still owns the lock."""
        key = str(self.lock_path)
        with StateRuntimeLockService._process_runtime_lock_guard:
            return StateRuntimeLockService._process_runtime_lock_counts.get(key, 0) > 0

    def read_runtime_lock_owner_pid(self) -> int | None:
        """Return the lock-owner pid when the lock file is readable and valid."""
        try:
            raw = self.lock_path.read_text(encoding="ascii").strip()
        except OSError:
            return None

        if not raw.isdigit():
            return None

        owner_pid = int(raw)
        return owner_pid if owner_pid > 0 else None

    def pid_is_running(self, pid: int) -> bool:
        """Return whether the runtime-lock owner still appears to be active."""
        if pid <= 0:
            return False

        if pid == self._get_pid():
            return self.process_runtime_lock_is_held()

        try:
            self._pid_probe(pid)
        except ProcessLookupError:
            return False
        except PermissionError:
            return True
        except OSError as exc:
            if exc.errno == errno.ESRCH:
                return False
            if getattr(exc, "winerror", None) == 87:
                return False
            return True
        return True

    def try_remove_runtime_lock_file(self) -> bool:
        """Best-effort removal for the lock file after work already completed."""
        for attempt in range(self._release_retry_limit()):
            try:
                if self.lock_path.exists():
                    self.lock_path.unlink()
                return True
            except FileNotFoundError:
                return True
            except OSError:
                if attempt == self._release_retry_limit() - 1:
                    return False
                self._sleep_fn(self._poll_seconds())
        return False

    def try_recover_stale_runtime_lock(self) -> bool:
        """Remove a stale runtime lock left behind by an inactive owner."""
        owner_pid = self.read_runtime_lock_owner_pid()
        if owner_pid is None:
            return False

        if self.pid_is_running(owner_pid):
            return False

        return self.try_remove_runtime_lock_file()

    def release_runtime_lock(self) -> None:
        """Release lock ownership without reclassifying completed work as failure."""
        fd = self._lock_fd
        self._lock_depth = 0
        self._lock_fd = None

        if fd is not None:
            try:
                os.close(fd)
            except OSError:
                pass

        self.unregister_process_runtime_lock()
        self.try_remove_runtime_lock_file()

    @contextmanager
    def runtime_lock(self):
        """Serialize runtime mutations across instances to avoid lost updates."""
        if self._lock_depth > 0:
            self._lock_depth += 1
            try:
                yield
            finally:
                self._lock_depth -= 1
            return

        self.cerebro_dir.mkdir(parents=True, exist_ok=True)
        start = self._monotonic()
        while True:
            try:
                fd = os.open(self.lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
                os.write(fd, str(self._get_pid()).encode("ascii"))
                self._lock_fd = fd
                self._lock_depth = 1
                self.register_process_runtime_lock()
                break
            except FileExistsError:
                if self.try_recover_stale_runtime_lock():
                    continue
                if self._monotonic() - start >= self._timeout_seconds():
                    raise self._error_cls(
                        "timed out waiting for runtime lock: "
                        f"{self.lock_path}; another Cerebro process may still be running or a previous run may have left a stale lock"
                    )
                self._sleep_fn(self._poll_seconds())

        try:
            yield
        finally:
            self.release_runtime_lock()
