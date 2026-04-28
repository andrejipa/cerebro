"""Deterministic staleness scoring for registered project sources.

Provides a simple, auditable score (0.0 = fresh, 1.0 = critical) based on:
  - elapsed days since the source was last known to be current
  - number of structural (AST-level) changes observed since baseline

Formula:
  score = min(1.0, (days_elapsed / STALE_DAYS) * TIME_WEIGHT
                 + (structural_changes / CHANGE_CEILING) * CHANGE_WEIGHT)

Both components are independent: a source can be stale from age alone or
from rapid structural churn alone.

Non-authoritative: this module never reads or writes .cerebro/, never calls
import-context, and never modifies canonical state. It only computes scores.
"""
from __future__ import annotations

from dataclasses import dataclass

STALE_DAYS: int = 90          # Days until the time component maxes out
CHANGE_CEILING: int = 5       # Structural changes until change component maxes
TIME_WEIGHT: float = 0.6      # Weight of the time component in the final score
CHANGE_WEIGHT: float = 0.4    # Weight of the change component in the final score


@dataclass(frozen=True)
class StalenessResult:
    path: str
    days_elapsed: int
    structural_changes: int
    score: float
    classification: str  # "fresh" | "aging" | "stale" | "critical"


def score_staleness(days_elapsed: int, structural_changes: int) -> float:
    """Return a staleness score in [0.0, 1.0].

    Both inputs must be non-negative integers. The result is rounded to
    three decimal places for stable serialisation.
    """
    if days_elapsed < 0:
        raise ValueError(f"days_elapsed must be non-negative, got {days_elapsed}")
    if structural_changes < 0:
        raise ValueError(f"structural_changes must be non-negative, got {structural_changes}")
    time_component = min(1.0, days_elapsed / STALE_DAYS) * TIME_WEIGHT
    change_component = min(1.0, structural_changes / CHANGE_CEILING) * CHANGE_WEIGHT
    return round(time_component + change_component, 3)


def classify_staleness(score: float) -> str:
    """Map a staleness score to a human-readable classification."""
    if score < 0.3:
        return "fresh"
    if score < 0.6:
        return "aging"
    if score < 0.8:
        return "stale"
    return "critical"


def score_source(path: str, days_elapsed: int, structural_changes: int) -> StalenessResult:
    """Return a StalenessResult for one registered source."""
    s = score_staleness(days_elapsed, structural_changes)
    return StalenessResult(
        path=path,
        days_elapsed=days_elapsed,
        structural_changes=structural_changes,
        score=s,
        classification=classify_staleness(s),
    )


def score_sources(
    sources: list[dict],
) -> list[StalenessResult]:
    """Score a list of source descriptors.

    Each descriptor must have:
      - "path": str
      - "days_elapsed": int   (days since last known-good verification)
      - "structural_changes": int   (AST-level changes observed since baseline)

    Returns results sorted by descending score (most stale first).
    """
    results = [
        score_source(
            path=s["path"],
            days_elapsed=s["days_elapsed"],
            structural_changes=s["structural_changes"],
        )
        for s in sources
    ]
    return sorted(results, key=lambda r: r.score, reverse=True)
