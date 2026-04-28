from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from experiments.context_discovery import Candidate, discover_context
from experiments.context_discovery.discovery import DiscoveryReport, DriftRecord, MissingRecord
from experiments.context_vectors import QueryHit, VectorIndex, build_vector_index, query_index


DEFAULT_QUERY_LIMIT = 4
DEFAULT_VECTOR_LIMIT = 3


@dataclass(frozen=True)
class VectorEvidence:
    query: str
    hits: tuple[QueryHit, ...]


@dataclass(frozen=True)
class AdvisoryRecommendation:
    kind: str
    relative_path: str
    priority: int
    may_suggest: str
    must_not_apply: str
    reasons: tuple[str, ...]
    evidence: tuple[VectorEvidence, ...]


@dataclass(frozen=True)
class AdvisoryReport:
    project_root: str
    discovery: DiscoveryReport
    vector_index: VectorIndex
    recommendations: tuple[AdvisoryRecommendation, ...]
    llm_contract: tuple[str, ...]
    state_change: str = "none"


def _candidate_query(candidate: Candidate) -> str:
    parts = [candidate.role, candidate.relative_path, candidate.heading, *candidate.reasons]
    return " ".join(part for part in parts if part)


def _drift_query(drift: DriftRecord) -> str:
    return f"registered source drift changed content {drift.relative_path} {drift.current_heading}"


def _missing_query(missing: MissingRecord) -> str:
    return f"registered source missing unavailable {missing.relative_path}"


def _evidence_for(index: VectorIndex, query: str, limit: int) -> VectorEvidence:
    return VectorEvidence(query=query, hits=query_index(index, query, limit=limit))


def _candidate_recommendation(candidate: Candidate, index: VectorIndex, vector_limit: int) -> AdvisoryRecommendation:
    evidence = (_evidence_for(index, _candidate_query(candidate), vector_limit),)
    return AdvisoryRecommendation(
        kind="inspect_candidate_source",
        relative_path=candidate.relative_path,
        priority=70 + min(candidate.score, 30),
        may_suggest="inspect_before_import",
        must_not_apply="do_not_register_source_automatically",
        reasons=(
            f"content_role={candidate.role}",
            f"content_score={candidate.score}",
            *candidate.reasons,
        ),
        evidence=evidence,
    )


def _drift_recommendation(drift: DriftRecord, index: VectorIndex, vector_limit: int) -> AdvisoryRecommendation:
    evidence = (_evidence_for(index, _drift_query(drift), vector_limit),)
    return AdvisoryRecommendation(
        kind="inspect_registered_source_drift",
        relative_path=drift.relative_path,
        priority=100,
        may_suggest="inspect_current_content_and_decide_whether_canonical_context_changed",
        must_not_apply="do_not_update_registered_hash_automatically",
        reasons=(
            "registered_source_hash_mismatch",
            f"registered_sha256={drift.registered_sha256}",
            f"current_sha256={drift.current_sha256}",
        ),
        evidence=evidence,
    )


def _missing_recommendation(missing: MissingRecord, index: VectorIndex, vector_limit: int) -> AdvisoryRecommendation:
    evidence = (_evidence_for(index, _missing_query(missing), vector_limit),)
    return AdvisoryRecommendation(
        kind="inspect_missing_registered_source",
        relative_path=missing.relative_path,
        priority=95,
        may_suggest="inspect_project_history_or_replace_source_reference",
        must_not_apply="do_not_remove_registered_source_automatically",
        reasons=(
            "registered_source_missing_from_filesystem",
            f"registered_sha256={missing.registered_sha256}",
        ),
        evidence=evidence,
    )


def _query_recommendation(query: str, hit: QueryHit, rank: int) -> AdvisoryRecommendation:
    return AdvisoryRecommendation(
        kind="inspect_semantic_hit",
        relative_path=hit.relative_path,
        priority=max(30, 80 - (rank * 10)),
        may_suggest="inspect_ranked_context_for_the_query",
        must_not_apply="do_not_treat_similarity_as_canonical_truth",
        reasons=(
            f"query={query}",
            f"rank={rank}",
            f"score={hit.score:.4f}",
            f"source_status={hit.source_status}",
        ),
        evidence=(VectorEvidence(query=query, hits=(hit,)),),
    )


def advise_context(
    root: str | Path,
    *,
    queries: tuple[str, ...] | list[str] = (),
    candidate_limit: int = 10,
    max_files: int = 800,
    vector_limit: int = DEFAULT_VECTOR_LIMIT,
) -> AdvisoryReport:
    if vector_limit <= 0:
        raise ValueError(f"vector_limit must be positive: {vector_limit}")
    if len(queries) > DEFAULT_QUERY_LIMIT:
        raise ValueError(f"queries must contain at most {DEFAULT_QUERY_LIMIT} items")

    root_path = Path(root).resolve()
    discovery = discover_context(root_path, candidate_limit=candidate_limit)
    vector_index = build_vector_index(root_path, max_files=max_files)

    recommendations: list[AdvisoryRecommendation] = []
    for drift in discovery.drift_on_registered_sources:
        recommendations.append(_drift_recommendation(drift, vector_index, vector_limit))
    for missing in discovery.missing_registered_sources:
        recommendations.append(_missing_recommendation(missing, vector_index, vector_limit))
    for candidate in discovery.candidates_not_registered:
        recommendations.append(_candidate_recommendation(candidate, vector_index, vector_limit))

    known = {(rec.kind, rec.relative_path) for rec in recommendations}
    for query in queries:
        for rank, hit in enumerate(query_index(vector_index, query, limit=vector_limit), start=1):
            key = ("inspect_semantic_hit", hit.relative_path)
            if key in known:
                continue
            recommendations.append(_query_recommendation(query, hit, rank))
            known.add(key)

    recommendations.sort(key=lambda rec: (-rec.priority, rec.kind, rec.relative_path))
    llm_contract = (
        "may_suggest: inspect files, compare evidence, draft proposed context changes",
        "must_not_apply: do not mutate .cerebro/state.json, do not import sources, do not edit target project files",
        "must_preserve: state_change none; recommendations are advisory evidence only",
    )
    return AdvisoryReport(
        project_root=str(root_path),
        discovery=discovery,
        vector_index=vector_index,
        recommendations=tuple(recommendations),
        llm_contract=llm_contract,
    )
