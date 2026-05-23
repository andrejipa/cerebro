from __future__ import annotations

from ..indexer import ProjectIndex
from ..pipeline_types import RetrievedCandidate
from ..semantic_vectors import cosine_sparse, embed_sparse
from ._bounded_top_k import bounded_top_candidates


AVAILABLE_BACKENDS = {"local-hash"}


def ensure_backend(backend: str) -> None:
    if backend not in AVAILABLE_BACKENDS:
        raise RuntimeError(
            f"Unsupported semantic backend '{backend}'. Available experimental backend(s): {sorted(AVAILABLE_BACKENDS)}"
        )


def retrieve_semantic(
    index: ProjectIndex,
    *,
    query: str,
    candidate_k: int = 40,
    backend: str = "local-hash",
) -> list[RetrievedCandidate]:
    ensure_backend(backend)
    query_vec = embed_sparse(query)
    candidates: list[RetrievedCandidate] = []
    for chunk in index.chunks:
        chunk_vector = chunk.semantic_vector or embed_sparse(f"{chunk.path}\n{chunk.text}")
        raw_score = cosine_sparse(query_vec, chunk_vector)
        if raw_score <= 0:
            continue
        candidates.append(
            RetrievedCandidate(
                path=chunk.path,
                scope=chunk.scope,
                excerpt=chunk.text[:220].replace("\n", " "),
                source_kind=chunk.source_kind,
                raw_score=raw_score,
                score_components={"semantic": raw_score},
                reason_flags=tuple(chunk.scope_flags) + ("retrieved_semantic",),
            )
        )
    return bounded_top_candidates(candidates, candidate_k=candidate_k)
