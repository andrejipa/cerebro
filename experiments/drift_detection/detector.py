"""Compare current scan to baseline and produce a DriftReport."""
from __future__ import annotations
from datetime import datetime, timezone
from .schema import DriftEntry, DriftReport, FileHashEntry


def _days_elapsed(baseline_captured_at: str) -> int:
    """Return whole days between baseline capture time and now (UTC)."""
    try:
        captured = datetime.fromisoformat(baseline_captured_at)
        delta = datetime.now(timezone.utc) - captured
        return max(0, delta.days)
    except (ValueError, TypeError):
        return 0


def detect(
    baseline: list[FileHashEntry],
    current: list[FileHashEntry],
    baseline_name: str = "baseline_snapshot.json",
    baseline_captured_at: str | None = None,
) -> DriftReport:
    """Compare baseline to current scan.

    When *baseline_captured_at* (ISO-8601 UTC string) is provided, the report
    includes a deterministic staleness score derived from elapsed days since the
    baseline was captured and the count of structural changes detected.
    """
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

    sorted_entries = sorted(entries, key=lambda e: e.path)

    # Compute staleness when timestamp is available.
    staleness_score: float | None = None
    staleness_classification: str | None = None
    if baseline_captured_at is not None:
        from .staleness_scorer import classify_staleness, score_staleness
        days = _days_elapsed(baseline_captured_at)
        structural_changes = len(sorted_entries)
        staleness_score = score_staleness(days, structural_changes)
        staleness_classification = classify_staleness(staleness_score)

    return DriftReport(
        generated_at=datetime.now(timezone.utc).isoformat(),
        baseline_snapshot=baseline_name,
        scanned_files=len(current),
        drift_entries=sorted_entries,
        staleness_score=staleness_score,
        staleness_classification=staleness_classification,
    )
