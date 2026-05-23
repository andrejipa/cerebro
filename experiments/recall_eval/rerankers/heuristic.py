from __future__ import annotations

from collections import defaultdict
from pathlib import Path

from ..pipeline_types import RankedResult, RetrievedCandidate
from ..scope_classifier import is_historical_path, is_lateral_documentation_path, scope_filter_allows


BASELINE_PENALTIES = ("backup", "historico", "history", "acervo", "arquivo", "snapshot", "snapshots")
IMPROVED_PENALTIES = BASELINE_PENALTIES + (
    "old",
    "archived",
    "legacy",
    "duplic",
    "tmp",
    "temporarios",
    "descarte",
    "superseded",
)

BOOST_MARKERS = {
    "readme": ("boosted_readme", 1.35),
    "contexto": ("boosted_contexto", 1.25),
    "canon": ("boosted_canon", 1.4),
    "checklist": ("boosted_checklist", 1.25),
    "estado_atual": ("boosted_estado_atual", 1.3),
    "entrada": ("boosted_entrada", 1.2),
}

OFFICIAL_MARKERS = ("oficial", "vigente", "trabalho_vigente", "ponto_2_pacote_oficial", "00_entrega")
DOCUMENT_GOVERNANCE_MARKERS = ("readme", "contexto", "checklist", "estado_atual", "canon", "governanca", "manual")
CURATED_HISTORICAL_MARKERS = ("90_historico", "historico_memorias", "historico_pre_dossie", "historico_sensivel_backup_fiscal")
AUXILIARY_HISTORY_MARKERS = ("cerebro_base__backup", "teste_deploy", "scripts_historicos_raiz", "_backup_cerebro_")


def _hygiene_factor(
    candidate: RetrievedCandidate,
    *,
    preferred_scope: str | None,
    query_type: str,
    mode: str,
) -> tuple[float, list[str]]:
    path_lower = candidate.path.replace("/", "\\").lower()
    factor = 1.0
    flags: list[str] = []

    penalties = IMPROVED_PENALTIES if mode == "improved" else BASELINE_PENALTIES
    for marker in penalties:
        if marker in path_lower:
            if query_type == "historical_lookup" and marker in {"historico", "history", "arquivo"}:
                factor *= 1.08
                flags.append("boosted_historical_query_alignment")
            else:
                penalty = 0.45 if mode == "improved" else 0.55
                factor *= penalty
                flags.append(f"penalized_{marker}")

    for marker, (flag, weight) in BOOST_MARKERS.items():
        if marker in path_lower:
            factor *= weight
            flags.append(flag)

    if any(marker in path_lower for marker in OFFICIAL_MARKERS):
        factor *= 1.22
        flags.append("boosted_official_path")

    if candidate.source_kind == "path-metadata":
        factor *= 0.88 if mode == "improved" else 0.9
        flags.append("penalized_path_only")

    if preferred_scope:
        if candidate.scope == preferred_scope:
            factor *= 1.32 if mode == "improved" else 1.25
            flags.append("boosted_scope_match")
        elif candidate.scope == "mixed":
            factor *= 1.06
            flags.append("boosted_scope_mixed")

    if preferred_scope == "code":
        if candidate.scope == "documentation":
            factor *= 0.42 if mode == "improved" else 0.6
            flags.append("penalized_doc_for_code_query")
        elif candidate.scope == "code":
            factor *= 1.18
            flags.append("boosted_code_for_code_query")
        if any(marker in path_lower for marker in DOCUMENT_GOVERNANCE_MARKERS):
            factor *= 0.5
            flags.append("penalized_governance_doc_for_code_query")

    if preferred_scope == "documentation" and candidate.scope == "code":
        factor *= 0.62 if mode == "improved" else 0.75
        flags.append("penalized_code_for_doc_query")

    if query_type == "historical_lookup":
        if any(marker in path_lower for marker in CURATED_HISTORICAL_MARKERS):
            factor *= 1.45
            flags.append("boosted_curated_historical")
        if any(marker in path_lower for marker in AUXILIARY_HISTORY_MARKERS):
            factor *= 0.35
            flags.append("penalized_auxiliary_history")

    if preferred_scope != "historical" and is_historical_path(candidate.path):
        factor *= 0.55 if mode == "improved" else 0.75
        flags.append("penalized_historical_path")

    if preferred_scope != "historical" and is_lateral_documentation_path(candidate.path):
        factor *= 0.58 if mode == "improved" else 0.78
        flags.append("penalized_lateral_doc")

    if len(Path(candidate.path).parts) <= 2:
        factor *= 1.05
        flags.append("boosted_short_path")

    return factor, flags


def rerank_candidates(
    candidates: list[RetrievedCandidate],
    *,
    preferred_scope: str | None,
    query_type: str,
    top_k: int = 5,
    mode: str = "baseline",
) -> list[RankedResult]:
    assert mode in {"baseline", "improved"}
    merged: dict[str, RetrievedCandidate] = {}
    for candidate in candidates:
        current = merged.get(candidate.path)
        if current is None or candidate.raw_score > current.raw_score:
            merged[candidate.path] = candidate
        elif candidate.raw_score == current.raw_score:
            merged[candidate.path] = RetrievedCandidate(
                path=current.path,
                scope=current.scope,
                excerpt=current.excerpt,
                source_kind=current.source_kind,
                raw_score=current.raw_score,
                score_components={**current.score_components, **candidate.score_components},
                reason_flags=tuple(sorted(set(current.reason_flags + candidate.reason_flags))),
            )

    ranked_rows: list[tuple[float, float, str, str, tuple[str, ...], str]] = []
    for candidate in merged.values():
        if preferred_scope and not scope_filter_allows(preferred_scope, candidate.scope):
            continue
        factor, hygiene_flags = _hygiene_factor(
            candidate,
            preferred_scope=preferred_scope,
            query_type=query_type,
            mode=mode,
        )
        lexical = candidate.score_components.get("lexical", 0.0)
        semantic = candidate.score_components.get("semantic", 0.0)
        if lexical and semantic:
            raw_score = lexical + (semantic * 0.25)
        elif semantic:
            raw_score = semantic
        else:
            raw_score = lexical if lexical else candidate.raw_score
        final_score = raw_score * factor
        ranked_rows.append(
            (
                raw_score,
                final_score,
                candidate.path,
                candidate.scope,
                tuple(sorted(set(candidate.reason_flags + tuple(hygiene_flags)))),
                candidate.excerpt,
            )
        )

    ranked_rows.sort(key=lambda item: (-item[1], -item[0], item[2]))
    results: list[RankedResult] = []
    for raw_score, final_score, path, scope, reason_flags, excerpt in ranked_rows[:top_k]:
        results.append(
            RankedResult(
                rank=len(results) + 1,
                raw_score=round(raw_score, 6),
                final_score=round(final_score, 6),
                path=path,
                scope=scope,
                reason_flags=reason_flags,
                excerpt=excerpt,
            )
        )
    return results
