"""Compare current scan to baseline and produce a DriftReport."""
from __future__ import annotations
from datetime import datetime, timezone
from .schema import DriftEntry, DriftReport, FileHashEntry


def detect(
    baseline: list[FileHashEntry],
    current: list[FileHashEntry],
    baseline_name: str = "baseline_snapshot.json",
) -> DriftReport:
    base_map = {e.path: e for e in baseline}
    curr_map = {e.path: e for e in current}

    entries: list[DriftEntry] = []
    for path, curr in curr_map.items():
        if path not in base_map:
            entries.append(DriftEntry(path=path, kind="added",
                                      baseline_hash=None, current_hash=curr.ast_hash))
        elif base_map[path].ast_hash != curr.ast_hash:
            entries.append(DriftEntry(path=path, kind="modified",
                                      baseline_hash=base_map[path].ast_hash,
                                      current_hash=curr.ast_hash))
    for path in base_map:
        if path not in curr_map:
            entries.append(DriftEntry(path=path, kind="removed",
                                      baseline_hash=base_map[path].ast_hash,
                                      current_hash=None))

    return DriftReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        baseline_snapshot=baseline_name,
        scanned_files=len(current),
        drift_entries=sorted(entries, key=lambda e: e.path),
    )
