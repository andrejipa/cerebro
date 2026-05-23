from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from functools import lru_cache
from hashlib import sha256
import math
from types import MappingProxyType
from typing import Mapping
import unicodedata


VECTOR_DIMENSIONS = 256

TOKEN_ALIASES: dict[str, tuple[str, ...]] = {
    "adr": ("decision", "architecture"),
    "arquitetura": ("architecture",),
    "atual": ("current", "state"),
    "continuidade": ("continuity", "handoff"),
    "decisao": ("decision",),
    "decisoes": ("decision",),
    "diagnostico": ("diagnostic",),
    "estado": ("state", "current"),
    "implantacao": ("implementation", "level"),
    "memoria": ("memory", "continuity"),
    "projeto": ("project",),
    "retomada": ("handoff", "return"),
    "schema": ("database", "model"),
}


@dataclass(frozen=True)
class SparseVector:
    weights: Mapping[int, float]
    norm: float


def _normalize_ascii(text: str) -> str:
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii").lower()


def _tokenize(text: str) -> list[str]:
    normalized = _normalize_ascii(text)
    tokens: list[str] = []
    current: list[str] = []
    for char in normalized:
        if char.isalnum() or char == "_":
            current.append(char)
            continue
        if current:
            tokens.append("".join(current))
            current.clear()
    if current:
        tokens.append("".join(current))
    return tokens


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    compact = " ".join(_normalize_ascii(text).split())
    if not compact:
        return []
    if len(compact) < n:
        return [compact]
    return [compact[index : index + n] for index in range(0, len(compact) - n + 1)]


def _bucket(namespace: str, value: str) -> int:
    digest = sha256(f"{namespace}\0{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % VECTOR_DIMENSIONS


@lru_cache(maxsize=32768)
def embed_text(text: str) -> SparseVector:
    weights: defaultdict[int, float] = defaultdict(float)
    tokens = _tokenize(text)
    expanded: list[str] = []
    for token in tokens:
        expanded.append(token)
        expanded.extend(TOKEN_ALIASES.get(token, ()))

    for token in expanded:
        weights[_bucket("tok", token)] += 2.0
    for gram in _char_ngrams(text):
        weights[_bucket("chr", gram)] += 0.35

    norm = math.sqrt(sum(weight * weight for weight in weights.values()))
    return SparseVector(weights=MappingProxyType(dict(weights)), norm=norm)


def cosine_similarity(left: SparseVector, right: SparseVector) -> float:
    if left.norm == 0.0 or right.norm == 0.0:
        return 0.0
    left_map, right_map = left.weights, right.weights
    smaller, larger = (left_map, right_map) if len(left_map) <= len(right_map) else (right_map, left_map)
    dot = 0.0
    for bucket, weight in smaller.items():
        other = larger.get(bucket)
        if other:
            dot += weight * other
    if dot == 0.0:
        return 0.0
    return dot / (left.norm * right.norm)
