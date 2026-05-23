"""Data structures for drift detection reports."""
from __future__ import annotations
from dataclasses import dataclass, field


@dataclass
class FileHashEntry:
    path: str
    ast_hash: str
    line_count: int


@dataclass
class DriftEntry:
    path: str
    kind: str  # "modified" | "added" | "removed"
    baseline_hash: str | None
    current_hash: str | None


@dataclass
class DriftReport:
    generated_at: str
    baseline_snapshot: str
    scanned_files: int
    drift_entries: list[DriftEntry] = field(default_factory=list)
    staleness_score: float | None = None
    staleness_classification: str | None = None

    @property
    def has_drift(self) -> bool:
        return len(self.drift_entries) > 0

    @property
    def summary(self) -> str:
        if not self.has_drift:
            return "No drift detected."
        counts = {}
        for e in self.drift_entries:
            counts[e.kind] = counts.get(e.kind, 0) + 1
        parts = [f"{v} {k}" for k, v in sorted(counts.items())]
        return "Drift detected: " + ", ".join(parts)
