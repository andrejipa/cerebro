"""Deterministic token overlap scoring (no LLM)."""
from __future__ import annotations
import re
from dataclasses import dataclass

_TOKEN_RE = re.compile(r"[A-Za-z0-9]+")


def _tokenize(text: str) -> frozenset[str]:
    """Return lowercase tokens from text, ignoring punctuation/whitespace."""
    return frozenset(t.lower() for t in _TOKEN_RE.findall(text) if len(t) > 1)


def jaccard(a: frozenset[str], b: frozenset[str]) -> float:
    """Jaccard similarity: |intersection| / |union|.  Returns 0.0 for empty sets."""
    if not a and not b:
        return 0.0
    union = a | b
    if not union:
        return 0.0
    return round(len(a & b) / len(union), 4)


def classify_alignment(score: float) -> str:
    """Classify alignment from Jaccard score."""
    if score >= 0.15:
        return "high"
    if score >= 0.04:
        return "medium"
    return "low"


@dataclass(frozen=True)
class SourceAlignment:
    path: str
    role: str
    jaccard_score: float
    alignment: str
    shared_tokens: int
    checkpoint_tokens: int
    source_tokens: int
    source_available: bool


def score_alignment(checkpoint_text: str, sources: list) -> list[SourceAlignment]:
    """Compute alignment between checkpoint text and each source.

    *sources* is a list of SourceRecord instances.
    Returns SourceAlignment entries sorted by jaccard_score descending.
    """
    cp_tokens = _tokenize(checkpoint_text)
    results: list[SourceAlignment] = []
    for src in sources:
        if src.content is None:
            results.append(SourceAlignment(
                path=src.path, role=src.role,
                jaccard_score=0.0, alignment="unavailable",
                shared_tokens=0, checkpoint_tokens=len(cp_tokens),
                source_tokens=0, source_available=False,
            ))
            continue
        src_tokens = _tokenize(src.content)
        score = jaccard(cp_tokens, src_tokens)
        results.append(SourceAlignment(
            path=src.path, role=src.role,
            jaccard_score=score,
            alignment=classify_alignment(score),
            shared_tokens=len(cp_tokens & src_tokens),
            checkpoint_tokens=len(cp_tokens),
            source_tokens=len(src_tokens),
            source_available=True,
        ))
    return sorted(results, key=lambda r: r.jaccard_score, reverse=True)
