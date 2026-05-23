from __future__ import annotations

from ..indexer import ProjectIndex
from ..lexical_scoring import prepare_query, score_prepared_query_against_chunk, tokenize_query
from ..pipeline_types import RetrievedCandidate
from ._bounded_top_k import bounded_top_candidates


def retrieve_lexical(
    index: ProjectIndex,
    *,
    query: str,
    candidate_k: int = 40,
) -> list[RetrievedCandidate]:
    query_tokens = tokenize_query(query)
    prepared_query = prepare_query(query_tokens, index.idf)
    if not prepared_query.weighted_tokens:
        return []
    candidates: list[RetrievedCandidate] = []
    for chunk in index.chunks:
        raw_score = score_prepared_query_against_chunk(prepared_query, chunk)
        if raw_score <= 0:
            continue
        candidates.append(
            RetrievedCandidate(
                path=chunk.path,
                scope=chunk.scope,
                excerpt=chunk.text[:220].replace("\n", " "),
                source_kind=chunk.source_kind,
                raw_score=raw_score,
                score_components={"lexical": raw_score},
                reason_flags=tuple(chunk.scope_flags),
            )
        )
    return bounded_top_candidates(candidates, candidate_k=candidate_k)
