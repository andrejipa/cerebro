from __future__ import annotations

from dataclasses import asdict

from .dataset import infer_query_type
from .indexer import ProjectIndex
from .pipeline_types import RankedResult
from .rerankers.heuristic import rerank_candidates
from .rerankers.hybrid import merge_candidates
from .retrievers.lexical import retrieve_lexical
from .retrievers.semantic import retrieve_semantic


def _lexical_candidate_limit(top_k: int) -> int:
    return max(40, top_k * 8)


def _semantic_candidate_limit(top_k: int) -> int:
    return max(50, top_k * 10)


def _build_output(
    *,
    variant: str,
    query: str,
    preferred_scope: str | None,
    query_type: str,
    ranked_results: list[RankedResult],
) -> dict:
    return {
        "experimental": True,
        "authority": "derived-assistive",
        "non_authoritative": True,
        "read_only": True,
        "variant": variant,
        "query": query,
        "preferred_scope": preferred_scope,
        "query_type": query_type,
        "results": [asdict(result) for result in ranked_results],
    }


def _rank_variant(
    index: ProjectIndex,
    *,
    query: str,
    preferred_scope: str | None,
    top_k: int,
    variant: str,
    query_type: str,
    lexical_candidates: list | None = None,
    semantic_candidates: list | None = None,
) -> list[RankedResult]:
    lexical_limit = _lexical_candidate_limit(top_k)
    semantic_limit = _semantic_candidate_limit(top_k)

    if variant == "A":
        candidates = lexical_candidates or retrieve_lexical(index, query=query, candidate_k=lexical_limit)
        return rerank_candidates(
            candidates,
            preferred_scope=preferred_scope,
            query_type=query_type,
            top_k=top_k,
            mode="baseline",
        )
    if variant == "B":
        candidates = lexical_candidates or retrieve_lexical(index, query=query, candidate_k=lexical_limit)
        return rerank_candidates(
            candidates,
            preferred_scope=preferred_scope,
            query_type=query_type,
            top_k=top_k,
            mode="improved",
        )
    if variant == "C":
        candidates = semantic_candidates or retrieve_semantic(index, query=query, candidate_k=semantic_limit)
        return rerank_candidates(
            candidates,
            preferred_scope=preferred_scope,
            query_type=query_type,
            top_k=top_k,
            mode="improved",
        )
    if variant == "D":
        lexical = lexical_candidates or retrieve_lexical(index, query=query, candidate_k=lexical_limit)
        semantic = semantic_candidates or retrieve_semantic(index, query=query, candidate_k=semantic_limit)
        return rerank_candidates(
            merge_candidates(lexical, semantic),
            preferred_scope=preferred_scope,
            query_type=query_type,
            top_k=top_k,
            mode="improved",
        )
    raise ValueError(f"Unsupported recall variant: {variant}")


def run_query(
    index: ProjectIndex,
    *,
    query: str,
    preferred_scope: str | None = None,
    top_k: int = 5,
    variant: str = "A",
    query_type: str | None = None,
) -> dict:
    query_type = query_type or infer_query_type(query, preferred_scope)
    ranked_results = _rank_variant(
        index,
        query=query,
        preferred_scope=preferred_scope,
        top_k=top_k,
        variant=variant,
        query_type=query_type,
    )
    return _build_output(
        variant=variant,
        query=query,
        preferred_scope=preferred_scope,
        query_type=query_type,
        ranked_results=ranked_results,
    )


def run_query_variants(
    index: ProjectIndex,
    *,
    query: str,
    preferred_scope: str | None = None,
    top_k: int = 5,
    query_type: str | None = None,
    variants: tuple[str, ...] = ("A", "B", "C", "D"),
) -> dict[str, dict]:
    query_type = query_type or infer_query_type(query, preferred_scope)
    lexical_candidates = None
    semantic_candidates = None

    if any(variant in {"A", "B", "D"} for variant in variants):
        lexical_candidates = retrieve_lexical(index, query=query, candidate_k=_lexical_candidate_limit(top_k))
    if any(variant in {"C", "D"} for variant in variants):
        semantic_candidates = retrieve_semantic(index, query=query, candidate_k=_semantic_candidate_limit(top_k))

    outputs: dict[str, dict] = {}
    for variant in variants:
        ranked_results = _rank_variant(
            index,
            query=query,
            preferred_scope=preferred_scope,
            top_k=top_k,
            variant=variant,
            query_type=query_type,
            lexical_candidates=lexical_candidates,
            semantic_candidates=semantic_candidates,
        )
        outputs[variant] = _build_output(
            variant=variant,
            query=query,
            preferred_scope=preferred_scope,
            query_type=query_type,
            ranked_results=ranked_results,
        )
    return outputs
