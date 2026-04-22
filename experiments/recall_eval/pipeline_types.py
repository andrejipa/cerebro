from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class RetrievedCandidate:
    path: str
    scope: str
    excerpt: str
    source_kind: str
    raw_score: float
    score_components: dict[str, float]
    reason_flags: tuple[str, ...] = field(default_factory=tuple)


@dataclass(frozen=True)
class RankedResult:
    rank: int
    raw_score: float
    final_score: float
    path: str
    scope: str
    reason_flags: tuple[str, ...]
    excerpt: str
