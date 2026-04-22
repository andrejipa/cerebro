from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
import math
import unicodedata

from .indexer import IndexedChunk


QUERY_ALIASES = {
    "progressao": ("progression",),
    "logica": ("logic",),
    "retomada": ("contexto", "entrada"),
    "vigente": ("oficial", "atual"),
}


@dataclass(frozen=True)
class PreparedQuery:
    weighted_tokens: dict[str, float]
    vector_norm: float


def tokenize_query(query: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", query).encode("ascii", "ignore").decode("ascii")
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized.lower():
        if char.isalnum() or char == "_":
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    expanded = list(tokens)
    for token in tokens:
        expanded.extend(QUERY_ALIASES.get(token, ()))
    return expanded


def prepare_query(query_tokens: list[str], idf: dict[str, float]) -> PreparedQuery:
    query_counts = Counter(query_tokens)
    query_weights: dict[str, float] = {}
    query_norm_sq = 0.0
    for token, count in query_counts.items():
        weight = (1.0 + math.log(count)) * idf.get(token, 0.0)
        if weight <= 0:
            continue
        query_weights[token] = weight
        query_norm_sq += weight * weight
    return PreparedQuery(weighted_tokens=query_weights, vector_norm=math.sqrt(query_norm_sq))


def score_prepared_query_against_chunk(query: PreparedQuery, chunk: IndexedChunk) -> float:
    if not query.weighted_tokens or query.vector_norm == 0.0 or chunk.vector_norm == 0:
        return 0.0

    dot = 0.0
    for token, query_weight in query.weighted_tokens.items():
        chunk_weight = chunk.weighted_tokens.get(token)
        if chunk_weight:
            dot += query_weight * chunk_weight
    if dot == 0.0:
        return 0.0
    return dot / (query.vector_norm * chunk.vector_norm)


def score_query_against_chunk(query_tokens: list[str], chunk: IndexedChunk, idf: dict[str, float]) -> float:
    return score_prepared_query_against_chunk(prepare_query(query_tokens, idf), chunk)
