from __future__ import annotations

from .indexer import ProjectIndex
from .lexical_scoring import score_query_against_chunk, tokenize_query
from .pipeline_types import RankedResult
from .rerankers.heuristic import rerank_candidates
from .retrievers.lexical import retrieve_lexical


def rank_index(
    index: ProjectIndex,
    query: str,
    preferred_scope: str | None = None,
    top_k: int = 5,
) -> list[RankedResult]:
    candidates = retrieve_lexical(index, query=query, candidate_k=max(40, top_k * 8))
    return rerank_candidates(
        candidates,
        preferred_scope=preferred_scope,
        query_type="continuity",
        top_k=top_k,
        mode="baseline",
    )
