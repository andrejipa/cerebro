from __future__ import annotations

from contextlib import contextmanager
import os
import shutil
import uuid
from pathlib import Path


LOCAL_TEMP_ROOT = Path(os.environ.get("TEMP") or ".tmp_test").resolve() / "cerebro_operational_signals_tests"
LOCAL_TEMP_ROOT.mkdir(parents=True, exist_ok=True)


@contextmanager
def workspace_tempdir() -> Path:
    temp_dir = LOCAL_TEMP_ROOT / f"tmp-{uuid.uuid4().hex}"
    temp_dir.mkdir(parents=True, exist_ok=False)
    try:
        yield temp_dir
    finally:
        shutil.rmtree(temp_dir, ignore_errors=False)
