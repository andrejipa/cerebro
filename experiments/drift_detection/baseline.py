"""Read and write baseline snapshots.

Format (v2): a JSON object with ``captured_at`` (ISO-8601 UTC) and ``entries``
list.  The legacy v1 format (bare JSON array) is still accepted on load for
backward compatibility with snapshots written before this change.
"""
from __future__ import annotations
import json
from datetime import datetime, timezone
from pathlib import Path
from .schema import FileHashEntry

DEFAULT_BASELINE_NAME = "baseline_snapshot.json"


def _now_utc() -> str:
    return datetime.now(timezone.utc).isoformat()


def save_baseline(entries: list[FileHashEntry], snapshot_path: Path) -> None:
    """Write baseline snapshot (v2 format with captured_at timestamp)."""
    rows = [{"path": e.path, "ast_hash": e.ast_hash, "line_count": e.line_count}
            for e in entries]
    payload = {"captured_at": _now_utc(), "entries": rows}
    snapshot_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def load_baseline(snapshot_path: Path) -> list[FileHashEntry] | None:
    """Return file hash entries from baseline (v1 or v2 format)."""
    if not snapshot_path.exists():
        return None
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    rows = raw if isinstance(raw, list) else raw.get("entries", [])
    return [FileHashEntry(path=r["path"], ast_hash=r["ast_hash"],
                          line_count=r["line_count"]) for r in rows]


def load_baseline_with_meta(snapshot_path: Path) -> tuple[list[FileHashEntry], str | None] | None:
    """Return (entries, captured_at_iso) or None if snapshot absent.

    ``captured_at`` is None for legacy v1 snapshots that lack the timestamp.
    """
    if not snapshot_path.exists():
        return None
    raw = json.loads(snapshot_path.read_text(encoding="utf-8"))
    if isinstance(raw, list):
        rows = raw
        captured_at = None
    else:
        rows = raw.get("entries", [])
        captured_at = raw.get("captured_at")
    entries = [FileHashEntry(path=r["path"], ast_hash=r["ast_hash"],
                             line_count=r["line_count"]) for r in rows]
    return entries, captured_at
