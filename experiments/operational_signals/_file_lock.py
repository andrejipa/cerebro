from __future__ import annotations

from contextlib import contextmanager, suppress
import json
import os
from pathlib import Path
import time

from .logger import OperationalSignalsLogError
from .logger import _current_lock_metadata
from .logger import _try_recover_stale_lock


@contextmanager
def file_lock(
    lock_path: Path,
    *,
    label: str,
    timeout_seconds: float = 5.0,
    poll_seconds: float = 0.05,
):
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    while True:
        try:
            lock_fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            try:
                os.write(lock_fd, json.dumps(_current_lock_metadata()).encode("utf-8"))
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
                raise OperationalSignalsLogError(f"timed out waiting for {label} lock: {lock_path}")
            time.sleep(poll_seconds)
        except OSError as exc:
            raise OperationalSignalsLogError(f"failed to acquire {label} lock: {lock_path}") from exc
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
                raise OperationalSignalsLogError(f"failed to release {label} lock: {lock_path}") from exc
            raise OperationalSignalsLogError(
                f"{body_error}; failed to release {label} lock: {lock_path}"
            ) from exc
