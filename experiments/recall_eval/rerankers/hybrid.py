from __future__ import annotations

from ..pipeline_types import RetrievedCandidate


def merge_candidates(
    lexical_candidates: list[RetrievedCandidate],
    semantic_candidates: list[RetrievedCandidate],
) -> list[RetrievedCandidate]:
    merged: dict[str, RetrievedCandidate] = {}
    for candidate in lexical_candidates + semantic_candidates:
        current = merged.get(candidate.path)
        if current is None:
            merged[candidate.path] = candidate
            continue
        combined_components = {**current.score_components, **candidate.score_components}
        merged[candidate.path] = RetrievedCandidate(
            path=current.path,
            scope=current.scope,
            excerpt=current.excerpt if len(current.excerpt) >= len(candidate.excerpt) else candidate.excerpt,
            source_kind=current.source_kind,
            raw_score=max(current.raw_score, candidate.raw_score),
            score_components=combined_components,
            reason_flags=tuple(sorted(set(current.reason_flags + candidate.reason_flags))),
        )
    return list(merged.values())
