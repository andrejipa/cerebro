from __future__ import annotations

from collections import defaultdict
from functools import lru_cache
from hashlib import sha256
import math
import unicodedata

EMBED_DIM = 192
QUERY_ALIASES = {
    "progressao": ("progression",),
    "logica": ("logic",),
    "retomada": ("contexto", "entrada"),
    "vigente": ("oficial", "atual"),
}


def _normalize_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return normalized.lower()


def _tokenize_query(text: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
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


def _char_ngrams(text: str, n: int = 3) -> list[str]:
    compact = " ".join(_normalize_text(text).split())
    if len(compact) < n:
        return [compact] if compact else []
    return [compact[idx : idx + n] for idx in range(0, len(compact) - n + 1)]


def _stable_bucket(namespace: str, value: str) -> int:
    digest = sha256(f"{namespace}\0{value}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") % EMBED_DIM


@lru_cache(maxsize=65536)
def embed_sparse(text: str) -> tuple[dict[int, float], float]:
    features: defaultdict[int, float] = defaultdict(float)
    expanded = _tokenize_query(text)
    for token in expanded:
        if not token:
            continue
        features[_stable_bucket("tok", token)] += 2.0
    for gram in _char_ngrams(text):
        if not gram:
            continue
        features[_stable_bucket("chr", gram)] += 0.45
    norm_sq = sum(weight * weight for weight in features.values())
    return dict(features), math.sqrt(norm_sq)


def cosine_sparse(left: tuple[dict[int, float], float], right: tuple[dict[int, float], float]) -> float:
    left_map, left_norm = left
    right_map, right_norm = right
    if left_norm == 0 or right_norm == 0:
        return 0.0
    dot = 0.0
    smaller, larger = (left_map, right_map) if len(left_map) <= len(right_map) else (right_map, left_map)
    for key, weight in smaller.items():
        other = larger.get(key)
        if other:
            dot += weight * other
    if dot == 0.0:
        return 0.0
    return dot / (left_norm * right_norm)
