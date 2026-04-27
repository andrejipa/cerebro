"""Read and write baseline snapshots."""
from __future__ import annotations
import json
from pathlib import Path
from .schema import FileHashEntry

DEFAULT_BASELINE_NAME = "baseline_snapshot.json"


def save_baseline(entries: list[FileHashEntry], snapshot_path: Path) -> None:
    data = [{"path": e.path, "ast_hash": e.ast_hash, "line_count": e.line_count}
            for e in entries]
    snapshot_path.write_text(json.dumps(data, indent=2), encoding="utf-8")


def load_baseline(snapshot_path: Path) -> list[FileHashEntry] | None:
    if not snapshot_path.exists():
        return None
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    return [FileHashEntry(path=r["path"], ast_hash=r["ast_hash"],
                          line_count=r["line_count"]) for r in raw]
