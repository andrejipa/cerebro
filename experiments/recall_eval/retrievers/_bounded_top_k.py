from __future__ import annotations

from dataclasses import dataclass
import heapq

from ..pipeline_types import RetrievedCandidate


@dataclass(frozen=True)
class _CandidateHeapItem:
    candidate: RetrievedCandidate

    def __lt__(self, other: object) -> bool:
        if not isinstance(other, _CandidateHeapItem):
            return NotImplemented
        self_candidate = self.candidate
        other_candidate = other.candidate
        if self_candidate.raw_score != other_candidate.raw_score:
            return self_candidate.raw_score < other_candidate.raw_score
        return self_candidate.path > other_candidate.path


def bounded_top_candidates(
    candidates: list[RetrievedCandidate],
    *,
    candidate_k: int,
) -> list[RetrievedCandidate]:
    if candidate_k <= 0:
        return []
    heap: list[_CandidateHeapItem] = []
    for candidate in candidates:
        item = _CandidateHeapItem(candidate)
        if len(heap) < candidate_k:
            heapq.heappush(heap, item)
            continue
        if heap[0] < item:
            heapq.heapreplace(heap, item)
    return sorted(
        (item.candidate for item in heap),
        key=lambda item: (-item.raw_score, item.path),
    )
