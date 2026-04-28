from __future__ import annotations

from .evals import EvaluationCase, EvaluationResult, evaluate_queries
from .index import (
    DEFAULT_MAX_FILES,
    DEFAULT_MAX_HEAD_BYTES,
    DEFAULT_MAX_HEAD_LINES,
    DocumentVector,
    QueryHit,
    VectorIndex,
    build_vector_index,
    query_index,
)
from .oracle import (
    OracleCase,
    OracleCaseResult,
    OracleEvaluationReport,
    CEREBRO_SELF_ORACLE_CASES,
    ESCRITORIO_IRPF_CAIXA_RURAL_ORACLE_CASES,
    PORTAL_HUMAITA_ORACLE_CASES,
    RPG_CAMINHADA_ORACLE_CASES,
    evaluate_oracle,
    render_oracle_markdown,
)
from .vectorizer import SparseVector, cosine_similarity, embed_text

__all__ = [
    "DEFAULT_MAX_FILES",
    "DEFAULT_MAX_HEAD_BYTES",
    "DEFAULT_MAX_HEAD_LINES",
    "DocumentVector",
    "EvaluationCase",
    "EvaluationResult",
    "QueryHit",
    "OracleCase",
    "OracleCaseResult",
    "OracleEvaluationReport",
    "CEREBRO_SELF_ORACLE_CASES",
    "ESCRITORIO_IRPF_CAIXA_RURAL_ORACLE_CASES",
    "PORTAL_HUMAITA_ORACLE_CASES",
    "RPG_CAMINHADA_ORACLE_CASES",
    "SparseVector",
    "VectorIndex",
    "build_vector_index",
    "cosine_similarity",
    "embed_text",
    "evaluate_oracle",
    "evaluate_queries",
    "query_index",
    "render_oracle_markdown",
]
