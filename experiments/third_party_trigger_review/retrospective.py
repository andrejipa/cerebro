from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

from .contract import ThirdPartyTriggerReview


@dataclass(frozen=True)
class ThirdPartyTriggerRetrospective:
    review_count: int
    readiness_counts: tuple[tuple[str, int], ...]
    finding_code_counts: tuple[tuple[str, int], ...]
    blocker_total: int
    warning_total: int
    state_change: str = "none"


def summarize_trigger_reviews(
    reviews: tuple[ThirdPartyTriggerReview, ...],
) -> ThirdPartyTriggerRetrospective:
    readiness_counts = Counter(review.readiness for review in reviews)
    finding_code_counts: Counter[str] = Counter()
    blocker_total = 0
    warning_total = 0

    for review in reviews:
        blocker_total += review.blocker_count
        warning_total += review.warning_count
        for finding in review.findings:
            finding_code_counts[finding.code] += 1

    return ThirdPartyTriggerRetrospective(
        review_count=len(reviews),
        readiness_counts=tuple(sorted(readiness_counts.items())),
        finding_code_counts=tuple(sorted(finding_code_counts.items())),
        blocker_total=blocker_total,
        warning_total=warning_total,
    )

