"""Read-only external freshness verifier over supplied external evidence."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

from extensions._support import exported_timestamp, read_snapshot, write_markdown_output


_COMPONENT_NAME = "Verificador de Atualidade Externa"
_BUNDLE_NORMALIZER_NAME = "Normalizador de Bundle Externo"
_BUNDLE_IDENTITY_SCOPE = "report_scoped"
_OPERATIONAL_NOTE = "external read-only analysis output; non-canonical; not a runtime decision"

_ALLOWED_SOURCE_CLASSES = (
    "primaria_normativa",
    "primaria_tecnica",
    "secundaria_confiavel",
)
_ALLOWED_TIME_SENSITIVITY = ("alta", "media", "baixa")
_ALLOWED_PATH_EFFECT = ("supports_path", "challenges_path")
_ALLOWED_FRESHNESS_STATUS = ("recente", "intermediaria", "possivelmente_desatualizada")
_ALLOWED_TEMPORAL_RISK = ("baixo", "medio", "alto")
_ALLOWED_ACQUISITION_METHODS = ("manual", "web_search", "deep_research", "mcp", "other")

_TIME_RANK = {"baixa": 1, "media": 2, "alta": 3}
_SOURCE_STRENGTH_RANK = {
    "descartada": 0,
    "secundaria_confiavel": 1,
    "primaria_tecnica": 2,
    "primaria_normativa": 3,
}
_RECENT_DAYS = {"alta": 90, "media": 365, "baixa": 1095}
_INTERMEDIATE_DAYS = {"alta": 365, "media": 1095, "baixa": 3650}


class ExternalFreshnessVerifierError(Exception):
    """Raised when the external freshness verifier cannot run safely."""


@dataclass(frozen=True)
class ExternalSourceInput:
    """External source metadata supplied to the verifier."""

    source_id: str
    url: str
    source_authority: str
    source_class: str
    source_date: str
    collected_at: str
    source_title: str = ""
    citation_locator: str = ""
    content_hash: str = ""
    acquisition_method: str = "manual"
    acquisition_query: str = ""
    acquisition_trace_id: str = ""
    notes: str = ""


@dataclass(frozen=True)
class ExternalFindingInput:
    """One external claim under review."""

    claim_id: str
    topic_id: str
    summary: str
    source_ids: tuple[str, ...]
    claim_time_sensitivity_context: str
    path_effect: str
    depends_on_current_validity: bool
    requires_normative_force: bool
    internal_confirmation_reference: str = ""


@dataclass(frozen=True)
class ExternalFreshnessRequest:
    """Structured request for the external freshness verifier."""

    question_or_proposal: str
    trigger_reason: str
    paths_under_review: tuple[str, ...]
    search_scope: tuple[str, ...]
    allowed_source_classes: tuple[str, ...]
    internal_proven_items: tuple[str, ...]
    sources: tuple[ExternalSourceInput, ...]
    findings: tuple[ExternalFindingInput, ...]


@dataclass(frozen=True)
class ExternalBundleSourceAlias:
    """Alias emitted when multiple raw sources collapse to one canonical bundle source."""

    original_source_id: str
    canonical_source_id: str
    canonical_resource_url: str
    reason: str


@dataclass(frozen=True)
class ExternalBundleNormalizationReport:
    """Deterministic normalization result for one supplied external evidence bundle."""

    component: str
    normalized_at: str
    snapshot_revision: int
    snapshot_validation_result: str
    canonical_internal_refs: tuple[str, ...]
    source_aliases: tuple[ExternalBundleSourceAlias, ...]
    normalized_request: ExternalFreshnessRequest


@dataclass(frozen=True)
class VerifiedSourceRecord:
    """One verified source entry."""

    source_id: str
    bundle_source_key: str
    url: str
    normalized_domain: str
    source_title: str
    source_authority: str
    source_strength: str
    source_date: str
    collected_at: str
    freshness_status: str
    temporal_risk: str
    citation_locator: str
    content_hash: str
    acquisition_method: str
    acquisition_query: str
    acquisition_trace_id: str
    notes: str
    bundle_identity_scope: str = _BUNDLE_IDENTITY_SCOPE


@dataclass(frozen=True)
class VerifiedClaim:
    """One verified claim entry."""

    claim_id: str
    summary: str
    source_ids: tuple[str, ...]
    citation_refs: tuple[str, ...]
    claim_time_sensitivity_context: str
    why_classified: str
    promotion_status: str
    promotion_basis: str
    temporal_basis: str
    downgrade_reasons: tuple[str, ...]


@dataclass(frozen=True)
class VerifiedConflict:
    """One unresolved conflict entry."""

    claim_id: str
    conflict_type: str
    conflicting_source_ids: tuple[str, ...]
    resolution_status: str
    why_not_resolved_automatically: str


@dataclass(frozen=True)
class ExternalGap:
    """One explicit gap emitted by the verifier."""

    gap_id: str
    missing_fact: str
    why_it_matters: str
    required_source_class: str


@dataclass(frozen=True)
class ExternalFreshnessReport:
    """Structured non-canonical verifier output."""

    component: str
    queried_at: str
    question_or_proposal: str
    trigger_reason: str
    paths_under_review: tuple[str, ...]
    snapshot_revision: int
    snapshot_validation_result: str
    time_sensitivity_context: str
    source_aliases: tuple[ExternalBundleSourceAlias, ...]
    source_register: tuple[VerifiedSourceRecord, ...]
    provavel: tuple[VerifiedClaim, ...]
    hipotese: tuple[VerifiedClaim, ...]
    conflitos: tuple[VerifiedConflict, ...]
    lacunas: tuple[ExternalGap, ...]
    operational_note: str
    bundle_identity_scope: str = _BUNDLE_IDENTITY_SCOPE


@dataclass(frozen=True)
class _SourceEvaluation:
    record: VerifiedSourceRecord
    source_date_value: date | None
    strength_rank: int
    has_current_validity_claim: bool


@dataclass(frozen=True)
class _NormalizedSourceCandidate:
    source: ExternalSourceInput
    canonical_resource_url: str
    resource_family_url: str
    effective_citation_locator: str
    dedupe_key: str
    source_date_value: date | None


def normalize_external_bundle(
    root: str | Path,
    request: ExternalFreshnessRequest,
    normalized_at: str | None = None,
) -> ExternalBundleNormalizationReport:
    """Normalize one supplied external bundle without changing runtime state."""
    _, snapshot = read_snapshot(root, ExternalFreshnessVerifierError)
    normalized_at_value = exported_timestamp(normalized_at)
    return _normalize_external_bundle(request, snapshot, normalized_at_value)


def verify_external_freshness(
    root: str | Path,
    request: ExternalFreshnessRequest,
    queried_at: str | None = None,
) -> ExternalFreshnessReport:
    """Classify supplied external evidence against the current canonical context."""
    queried_at_value = exported_timestamp(queried_at)
    _, snapshot = read_snapshot(root, ExternalFreshnessVerifierError)
    normalization = _normalize_external_bundle(request, snapshot, queried_at_value)
    request = normalization.normalized_request

    findings_by_id = {finding.claim_id: finding for finding in request.findings}
    highest_context_by_source = _highest_context_by_source(request.findings)
    current_validity_by_source = _current_validity_by_source(request.findings)
    source_evaluations = _evaluate_sources(
        request,
        highest_context_by_source,
        current_validity_by_source,
        normalization.snapshot_revision,
    )
    conflicts_by_claim, conflict_loser_source_ids = _build_conflicts(request.findings, source_evaluations)
    source_evaluations = _elevate_conflict_loser_temporal_risk(source_evaluations, conflict_loser_source_ids)

    provavel: list[VerifiedClaim] = []
    hipotese: list[VerifiedClaim] = []
    conflitos: list[VerifiedConflict] = []
    lacunas: list[ExternalGap] = []

    for claim_id in sorted(findings_by_id):
        finding = findings_by_id[claim_id]
        claim_sources = [source_evaluations[source_id] for source_id in finding.source_ids]
        trusted_sources = [entry for entry in claim_sources if entry.record.source_strength != "descartada"]

        if not trusted_sources:
            lacunas.append(
                ExternalGap(
                    gap_id=f"gap-{finding.claim_id}",
                    missing_fact=finding.summary,
                    why_it_matters="no trusted external source remained after allowed-source filtering",
                    required_source_class="primaria_normativa" if finding.requires_normative_force else "primaria_tecnica",
                )
            )
            continue

        downgrade_reasons = _claim_downgrade_reasons(finding, trusted_sources, conflicts_by_claim.get(finding.claim_id, ()))
        promotion_basis = _promotion_basis(finding, trusted_sources, request.internal_proven_items)
        if downgrade_reasons:
            promotion_basis = "nenhuma"
        promotion_status = "promotion_candidate" if promotion_basis != "nenhuma" else "not_eligible_for_promotion"
        temporal_basis = _temporal_basis(finding, trusted_sources)
        why_classified = _why_classified(downgrade_reasons, temporal_basis, promotion_status)
        claim = VerifiedClaim(
            claim_id=finding.claim_id,
            summary=finding.summary,
            source_ids=tuple(sorted(source.record.source_id for source in trusted_sources)),
            citation_refs=tuple(
                sorted(
                    _citation_ref(source.record.bundle_source_key, source.record.citation_locator)
                    for source in trusted_sources
                )
            ),
            claim_time_sensitivity_context=finding.claim_time_sensitivity_context,
            why_classified=why_classified,
            promotion_status=promotion_status,
            promotion_basis=promotion_basis,
            temporal_basis=temporal_basis,
            downgrade_reasons=tuple(downgrade_reasons),
        )

        if downgrade_reasons:
            hipotese.append(claim)
        else:
            provavel.append(claim)

        for conflict in conflicts_by_claim.get(finding.claim_id, ()):
            conflitos.append(conflict)

    highest_output_context = _highest_output_context(request.findings)

    return ExternalFreshnessReport(
        component=_COMPONENT_NAME,
        queried_at=queried_at_value,
        question_or_proposal=request.question_or_proposal,
        trigger_reason=request.trigger_reason,
        paths_under_review=tuple(request.paths_under_review),
        snapshot_revision=normalization.snapshot_revision,
        snapshot_validation_result=normalization.snapshot_validation_result,
        time_sensitivity_context=highest_output_context,
        source_aliases=normalization.source_aliases,
        source_register=tuple(source_evaluations[source_id].record for source_id in sorted(source_evaluations)),
        provavel=tuple(sorted(provavel, key=lambda item: item.claim_id)),
        hipotese=tuple(sorted(hipotese, key=lambda item: item.claim_id)),
        conflitos=tuple(sorted(_dedupe_conflicts(conflitos), key=lambda item: (item.claim_id, item.conflict_type, item.conflicting_source_ids))),
        lacunas=tuple(sorted(lacunas, key=lambda item: item.gap_id)),
        operational_note=_OPERATIONAL_NOTE,
        bundle_identity_scope=_BUNDLE_IDENTITY_SCOPE,
    )


def render_external_freshness_markdown(
    root: str | Path,
    request: ExternalFreshnessRequest,
    queried_at: str | None = None,
) -> str:
    """Render the external freshness report as Markdown."""
    report = verify_external_freshness(root, request, queried_at=queried_at)
    alias_map = {
        alias.original_source_id: alias.canonical_source_id
        for alias in report.source_aliases
    }
    referenced_source_ids = {
        alias_map.get(source_id, source_id)
        for finding in request.findings
        for source_id in finding.source_ids
    }

    lines = [
        "# External Freshness Verifier",
        "",
        f"- Component: {report.component}",
        f"- Queried at: {report.queried_at}",
        f"- Question or proposal: {_render_markdown_text(report.question_or_proposal)}",
        f"- Trigger reason: {_render_markdown_text(report.trigger_reason)}",
        f"- Paths under review: {_render_markdown_list(report.paths_under_review)}",
        f"- Snapshot revision: {report.snapshot_revision}",
        f"- Snapshot validation result: {report.snapshot_validation_result}",
        f"- Highest time sensitivity: {report.time_sensitivity_context}",
        f"- Bundle identity scope: {report.bundle_identity_scope}",
        f"- Operational note: {report.operational_note}",
        "- Source register note: freshness/risk are aggregated per source; claim sections remain claim-local",
    ]

    lines.extend(_render_alias_section(report.source_aliases))
    lines.extend(_render_source_section(report.source_register, referenced_source_ids))
    lines.extend(_render_claim_section("Provavel", report.provavel))
    lines.extend(_render_claim_section("Hipotese", report.hipotese))
    lines.extend(_render_conflict_section(report.conflitos))
    lines.extend(_render_gap_section(report.lacunas))

    return "\n".join(lines) + "\n"


def write_external_freshness_markdown(
    root: str | Path,
    request: ExternalFreshnessRequest,
    output_path: str | Path,
    queried_at: str | None = None,
) -> Path:
    """Write the external freshness report outside runtime-owned paths."""
    markdown = render_external_freshness_markdown(root, request, queried_at=queried_at)
    return write_markdown_output(root, output_path, markdown, ExternalFreshnessVerifierError)


def _validate_request(
    request: ExternalFreshnessRequest,
    canonical_internal_refs: tuple[str, ...] | None = None,
) -> None:
    if not request.question_or_proposal.strip():
        raise ExternalFreshnessVerifierError("question_or_proposal must be a non-empty string")
    if not request.trigger_reason.strip():
        raise ExternalFreshnessVerifierError("trigger_reason must be a non-empty string")
    if not request.paths_under_review:
        raise ExternalFreshnessVerifierError("paths_under_review must be a non-empty tuple")
    if not request.search_scope:
        raise ExternalFreshnessVerifierError("search_scope must be a non-empty tuple")
    if not request.allowed_source_classes:
        raise ExternalFreshnessVerifierError("allowed_source_classes must be a non-empty tuple")
    if canonical_internal_refs is not None:
        allowed_internal_refs = set(canonical_internal_refs)
        unknown_internal_refs = sorted({item for item in request.internal_proven_items if item not in allowed_internal_refs})
        if unknown_internal_refs:
            raise ExternalFreshnessVerifierError(
                "internal_proven_items contains references outside the canonical snapshot: "
                + ", ".join(unknown_internal_refs)
            )

    invalid_allowed = set(request.allowed_source_classes) - set(_ALLOWED_SOURCE_CLASSES)
    if invalid_allowed:
        raise ExternalFreshnessVerifierError(f"allowed_source_classes contains unsupported values: {', '.join(sorted(invalid_allowed))}")
    normalized_scope = tuple(_normalize_search_scope_entry(entry) for entry in request.search_scope)
    if len(set(normalized_scope)) != len(normalized_scope):
        raise ExternalFreshnessVerifierError("search_scope contains duplicate normalized domains")

    if not request.sources:
        raise ExternalFreshnessVerifierError("sources must be a non-empty tuple")
    if not request.findings:
        raise ExternalFreshnessVerifierError("findings must be a non-empty tuple")

    source_ids: set[str] = set()
    for source in request.sources:
        if not source.source_id.strip():
            raise ExternalFreshnessVerifierError("source_id must be a non-empty string")
        if source.source_id in source_ids:
            raise ExternalFreshnessVerifierError(f"duplicate source_id: {source.source_id}")
        source_ids.add(source.source_id)
        if source.source_class not in _ALLOWED_SOURCE_CLASSES:
            raise ExternalFreshnessVerifierError(f"unsupported source_class: {source.source_class}")
        if not source.url.strip():
            raise ExternalFreshnessVerifierError(f"url must be non-empty for source {source.source_id}")
        normalized_domain = _normalize_url_domain(source.url, source.source_id)
        if not _domain_allowed(normalized_domain, normalized_scope):
            raise ExternalFreshnessVerifierError(
                f"source url domain is outside search_scope for source {source.source_id}: {normalized_domain}"
            )
        if not source.source_authority.strip():
            raise ExternalFreshnessVerifierError(f"source_authority must be non-empty for source {source.source_id}")
        if not source.collected_at.strip():
            raise ExternalFreshnessVerifierError(f"collected_at must be non-empty for source {source.source_id}")
        if source.acquisition_method not in _ALLOWED_ACQUISITION_METHODS:
            raise ExternalFreshnessVerifierError(
                f"unsupported acquisition_method for source {source.source_id}: {source.acquisition_method}"
            )
        _parse_iso_date(source.collected_at, f"collected_at for {source.source_id}")
        if source.source_date.strip():
            source_date_value = _parse_iso_date(source.source_date, f"source_date for {source.source_id}")
            collected_at_value = _parse_iso_date(source.collected_at, f"collected_at for {source.source_id}")
            if source_date_value > collected_at_value:
                raise ExternalFreshnessVerifierError(f"source_date cannot be after collected_at for source {source.source_id}")
        if source.content_hash and not _is_sha256_hex(source.content_hash):
            raise ExternalFreshnessVerifierError(f"content_hash must be a 64-char lowercase hex sha256 for source {source.source_id}")

    claim_ids: set[str] = set()
    for finding in request.findings:
        if not finding.claim_id.strip():
            raise ExternalFreshnessVerifierError("claim_id must be a non-empty string")
        if finding.claim_id in claim_ids:
            raise ExternalFreshnessVerifierError(f"duplicate claim_id: {finding.claim_id}")
        claim_ids.add(finding.claim_id)
        if not finding.topic_id.strip():
            raise ExternalFreshnessVerifierError(f"topic_id must be non-empty for claim {finding.claim_id}")
        if not finding.summary.strip():
            raise ExternalFreshnessVerifierError(f"summary must be non-empty for claim {finding.claim_id}")
        if finding.claim_time_sensitivity_context not in _ALLOWED_TIME_SENSITIVITY:
            raise ExternalFreshnessVerifierError(
                f"unsupported claim_time_sensitivity_context for claim {finding.claim_id}: {finding.claim_time_sensitivity_context}"
            )
        if finding.path_effect not in _ALLOWED_PATH_EFFECT:
            raise ExternalFreshnessVerifierError(f"unsupported path_effect for claim {finding.claim_id}: {finding.path_effect}")
        if not finding.source_ids:
            raise ExternalFreshnessVerifierError(f"claim {finding.claim_id} must reference at least one source")
        if len(set(finding.source_ids)) != len(finding.source_ids):
            raise ExternalFreshnessVerifierError(f"claim {finding.claim_id} contains duplicate source_ids")
        unknown_sources = [source_id for source_id in finding.source_ids if source_id not in source_ids]
        if unknown_sources:
            raise ExternalFreshnessVerifierError(
                f"claim {finding.claim_id} references unknown source ids: {', '.join(sorted(unknown_sources))}"
            )
        if (
            finding.internal_confirmation_reference
            and finding.internal_confirmation_reference not in request.internal_proven_items
        ):
            raise ExternalFreshnessVerifierError(
                f"claim {finding.claim_id} references internal_confirmation_reference not present in internal_proven_items"
            )


def _normalize_external_bundle(
    request: ExternalFreshnessRequest,
    snapshot: object,
    normalized_at_value: str,
) -> ExternalBundleNormalizationReport:
    canonical_internal_refs = _canonical_internal_refs(snapshot)
    _validate_request(request)

    normalized_sources, source_aliases = _normalize_sources(request)
    normalized_source_ids = {source.source_id for source in normalized_sources}
    normalized_findings = _normalize_findings(request.findings, source_aliases, normalized_source_ids)
    normalized_request = ExternalFreshnessRequest(
        question_or_proposal=request.question_or_proposal,
        trigger_reason=request.trigger_reason,
        paths_under_review=tuple(request.paths_under_review),
        search_scope=tuple(request.search_scope),
        allowed_source_classes=tuple(request.allowed_source_classes),
        internal_proven_items=tuple(sorted(set(request.internal_proven_items))),
        sources=tuple(normalized_sources),
        findings=tuple(normalized_findings),
    )
    _validate_request(normalized_request, canonical_internal_refs=canonical_internal_refs)

    return ExternalBundleNormalizationReport(
        component=_BUNDLE_NORMALIZER_NAME,
        normalized_at=normalized_at_value,
        snapshot_revision=snapshot.revision,
        snapshot_validation_result=snapshot.last_validation.result,
        canonical_internal_refs=canonical_internal_refs,
        source_aliases=tuple(sorted(source_aliases.values(), key=lambda item: (item.canonical_source_id, item.original_source_id))),
        normalized_request=normalized_request,
    )


def _canonical_internal_refs(snapshot: object) -> tuple[str, ...]:
    refs: list[str] = []
    for source in snapshot.sources:
        refs.append(f"source:{source.path}")
    if snapshot.checkpoint.goal.strip():
        refs.append("checkpoint.goal")
    if snapshot.checkpoint.summary.strip():
        refs.append("checkpoint.summary")
    if snapshot.checkpoint.next_step.strip():
        refs.append("checkpoint.next_step")
    for index, constraint in enumerate(snapshot.checkpoint.constraints):
        if constraint.strip():
            refs.append(f"checkpoint.constraint:{index}")
    return tuple(sorted(set(refs)))


def _normalize_sources(
    request: ExternalFreshnessRequest,
) -> tuple[tuple[ExternalSourceInput, ...], dict[str, ExternalBundleSourceAlias]]:
    raw_source_ids: set[str] = set()
    candidates_by_id: dict[str, _NormalizedSourceCandidate] = {}
    grouped_by_hash: dict[tuple[str, str], list[_NormalizedSourceCandidate]] = {}
    grouped_by_url: dict[str, list[_NormalizedSourceCandidate]] = {}

    for source in request.sources:
        if not source.source_id.strip():
            raise ExternalFreshnessVerifierError("source_id must be a non-empty string")
        if source.source_id in raw_source_ids:
            raise ExternalFreshnessVerifierError(f"duplicate source_id: {source.source_id}")
        raw_source_ids.add(source.source_id)

        canonical_resource_url, fragment_locator = _normalize_resource_url(source.url, source.source_id)
        resource_family_url = _resource_family_url(source.url, source.source_id)
        effective_locator = source.citation_locator.strip() or fragment_locator
        source_date_value = _parse_optional_iso_date(source.source_date, f"source_date for {source.source_id}")
        dedupe_key = source.content_hash or canonical_resource_url
        candidate = _NormalizedSourceCandidate(
            source=source,
            canonical_resource_url=canonical_resource_url,
            resource_family_url=resource_family_url,
            effective_citation_locator=effective_locator,
            dedupe_key=dedupe_key,
            source_date_value=source_date_value,
        )
        candidates_by_id[source.source_id] = candidate
        grouped_by_url.setdefault(canonical_resource_url, []).append(candidate)
        if source.content_hash:
            grouped_by_hash.setdefault((source.content_hash, resource_family_url), []).append(candidate)

    grouped: list[list[_NormalizedSourceCandidate]] = []
    seen_group_members: set[str] = set()

    for hash_scope in sorted(grouped_by_hash):
        group = grouped_by_hash[hash_scope]
        grouped.append(group)
        seen_group_members.update(candidate.source.source_id for candidate in group)

    for canonical_resource_url in sorted(grouped_by_url):
        url_group = grouped_by_url[canonical_resource_url]
        hashed_candidates = [candidate for candidate in url_group if candidate.source.content_hash]
        no_hash_candidates = [candidate for candidate in url_group if not candidate.source.content_hash]
        hash_values = {candidate.source.content_hash for candidate in hashed_candidates}

        if not hashed_candidates:
            grouped.append(list(url_group))
            seen_group_members.update(candidate.source.source_id for candidate in url_group)
            continue

        if len(hash_values) == 1:
            only_hash = next(iter(hash_values))
            resource_family_url = hashed_candidates[0].resource_family_url
            hash_group = grouped_by_hash[(only_hash, resource_family_url)]
            existing_ids = {candidate.source.source_id for candidate in hash_group}
            for candidate in no_hash_candidates:
                if candidate.source.source_id in existing_ids:
                    continue
                hash_group.append(candidate)
                seen_group_members.add(candidate.source.source_id)
            continue

        if no_hash_candidates:
            grouped.append(list(no_hash_candidates))
            seen_group_members.update(candidate.source.source_id for candidate in no_hash_candidates)

    for source_id in sorted(candidates_by_id):
        if source_id in seen_group_members:
            continue
        grouped.append([candidates_by_id[source_id]])
        seen_group_members.add(source_id)

    aliases: dict[str, ExternalBundleSourceAlias] = {}
    normalized_sources: list[ExternalSourceInput] = []
    for group in sorted(grouped, key=lambda items: tuple(sorted(candidate.source.source_id for candidate in items))):
        canonical = max(group, key=lambda item: _source_bundle_preference(item, request.allowed_source_classes))
        normalized_sources.append(
            ExternalSourceInput(
                source_id=canonical.source.source_id,
                url=canonical.canonical_resource_url,
                source_authority=canonical.source.source_authority,
                source_class=canonical.source.source_class,
                source_date=canonical.source.source_date,
                collected_at=canonical.source.collected_at,
                source_title=_preferred_group_text(canonical, group, request.allowed_source_classes, lambda item: item.source.source_title),
                citation_locator=_preferred_group_text(canonical, group, request.allowed_source_classes, lambda item: item.effective_citation_locator),
                content_hash=canonical.source.content_hash,
                acquisition_method=canonical.source.acquisition_method,
                acquisition_query=_preferred_group_text(canonical, group, request.allowed_source_classes, lambda item: item.source.acquisition_query),
                acquisition_trace_id=_preferred_group_text(canonical, group, request.allowed_source_classes, lambda item: item.source.acquisition_trace_id),
                notes=_preferred_group_text(canonical, group, request.allowed_source_classes, lambda item: item.source.notes),
            )
        )
        for candidate in group:
            if candidate.source.source_id == canonical.source.source_id:
                continue
            aliases[candidate.source.source_id] = ExternalBundleSourceAlias(
                original_source_id=candidate.source.source_id,
                canonical_source_id=canonical.source.source_id,
                canonical_resource_url=canonical.canonical_resource_url,
                reason="matching_content_hash"
                if candidate.source.content_hash and candidate.source.content_hash == canonical.source.content_hash
                else "equivalent_resource_url",
            )

    return tuple(sorted(normalized_sources, key=lambda item: item.source_id)), aliases


def _source_bundle_preference(
    candidate: _NormalizedSourceCandidate,
    allowed_source_classes: tuple[str, ...],
) -> tuple[int, int, int, int, int, str]:
    allowed_rank = 1 if candidate.source.source_class in allowed_source_classes else 0
    source_date_score = candidate.source_date_value.toordinal() if candidate.source_date_value is not None else 0
    return (
        allowed_rank,
        _SOURCE_STRENGTH_RANK[candidate.source.source_class],
        1 if candidate.source.content_hash else 0,
        1 if candidate.effective_citation_locator else 0,
        source_date_score,
        candidate.source.source_id,
    )


def _preferred_group_text(
    canonical: _NormalizedSourceCandidate,
    group: list[_NormalizedSourceCandidate],
    allowed_source_classes: tuple[str, ...],
    value_getter,
) -> str:
    canonical_value = value_getter(canonical).strip()
    if canonical_value:
        return canonical_value
    candidates = [candidate for candidate in group if value_getter(candidate).strip()]
    if not candidates:
        return ""
    best = max(candidates, key=lambda item: _source_bundle_preference(item, allowed_source_classes))
    return value_getter(best).strip()


def _normalize_findings(
    findings: tuple[ExternalFindingInput, ...],
    source_aliases: dict[str, ExternalBundleSourceAlias],
    normalized_source_ids: set[str],
) -> tuple[ExternalFindingInput, ...]:
    normalized_findings: list[ExternalFindingInput] = []
    for finding in findings:
        if len(set(finding.source_ids)) != len(finding.source_ids):
            raise ExternalFreshnessVerifierError(f"claim {finding.claim_id} contains duplicate source_ids")

        normalized_source_refs: list[str] = []
        seen_sources: set[str] = set()
        for source_id in finding.source_ids:
            canonical_source_id = source_aliases.get(source_id, None)
            if canonical_source_id is not None:
                source_id = canonical_source_id.canonical_source_id
            if source_id not in normalized_source_ids:
                raise ExternalFreshnessVerifierError(
                    f"claim {finding.claim_id} references unknown normalized source id: {source_id}"
                )
            if source_id in seen_sources:
                continue
            seen_sources.add(source_id)
            normalized_source_refs.append(source_id)

        normalized_findings.append(
            ExternalFindingInput(
                claim_id=finding.claim_id,
                topic_id=finding.topic_id,
                summary=finding.summary,
                source_ids=tuple(normalized_source_refs),
                claim_time_sensitivity_context=finding.claim_time_sensitivity_context,
                path_effect=finding.path_effect,
                depends_on_current_validity=finding.depends_on_current_validity,
                requires_normative_force=finding.requires_normative_force,
                internal_confirmation_reference=finding.internal_confirmation_reference,
            )
        )

    return tuple(normalized_findings)


def _highest_context_by_source(findings: tuple[ExternalFindingInput, ...]) -> dict[str, str]:
    highest: dict[str, str] = {}
    for finding in findings:
        for source_id in finding.source_ids:
            current = highest.get(source_id, "baixa")
            if _TIME_RANK[finding.claim_time_sensitivity_context] > _TIME_RANK[current]:
                highest[source_id] = finding.claim_time_sensitivity_context
            elif source_id not in highest:
                highest[source_id] = finding.claim_time_sensitivity_context
    return highest


def _current_validity_by_source(findings: tuple[ExternalFindingInput, ...]) -> dict[str, bool]:
    by_source: dict[str, bool] = {}
    for finding in findings:
        for source_id in finding.source_ids:
            by_source[source_id] = by_source.get(source_id, False) or finding.depends_on_current_validity
    return by_source


def _evaluate_sources(
    request: ExternalFreshnessRequest,
    highest_context_by_source: dict[str, str],
    current_validity_by_source: dict[str, bool],
    snapshot_revision: int,
) -> dict[str, _SourceEvaluation]:
    evaluated: dict[str, _SourceEvaluation] = {}
    for source in request.sources:
        sensitivity = highest_context_by_source.get(source.source_id, "baixa")
        normalized_domain = _normalize_url_domain(source.url, source.source_id)
        collected_at_value = _parse_iso_date(source.collected_at, f"collected_at for {source.source_id}")
        source_date_value = _parse_optional_iso_date(source.source_date, f"source_date for {source.source_id}")
        source_strength = source.source_class if source.source_class in request.allowed_source_classes else "descartada"
        freshness_status = _classify_freshness_status(source_date_value, collected_at_value, sensitivity)
        temporal_risk = _classify_temporal_risk(
            freshness_status,
            sensitivity,
            current_validity_by_source.get(source.source_id, False),
            source_date_value is None,
        )
        record = VerifiedSourceRecord(
            source_id=source.source_id,
            bundle_source_key=_bundle_source_key(snapshot_revision, source.url, source.content_hash),
            url=source.url,
            normalized_domain=normalized_domain,
            source_title=source.source_title,
            source_authority=source.source_authority,
            source_strength=source_strength,
            source_date=source.source_date,
            collected_at=source.collected_at,
            freshness_status=freshness_status,
            temporal_risk=temporal_risk,
            citation_locator=source.citation_locator,
            content_hash=source.content_hash,
            acquisition_method=source.acquisition_method,
            acquisition_query=source.acquisition_query,
            acquisition_trace_id=source.acquisition_trace_id,
            notes=source.notes,
            bundle_identity_scope=_BUNDLE_IDENTITY_SCOPE,
        )
        evaluated[source.source_id] = _SourceEvaluation(
            record=record,
            source_date_value=source_date_value,
            strength_rank=_SOURCE_STRENGTH_RANK[source_strength],
            has_current_validity_claim=current_validity_by_source.get(source.source_id, False),
        )
    return evaluated


def _classify_freshness_status(source_date_value: date | None, collected_at_value: date, sensitivity: str) -> str:
    if source_date_value is None:
        return "possivelmente_desatualizada"
    age_days = (collected_at_value - source_date_value).days
    if age_days <= _RECENT_DAYS[sensitivity]:
        return "recente"
    if age_days <= _INTERMEDIATE_DAYS[sensitivity]:
        return "intermediaria"
    return "possivelmente_desatualizada"


def _classify_temporal_risk(
    freshness_status: str,
    sensitivity: str,
    depends_on_current_validity: bool,
    source_date_missing: bool,
) -> str:
    if source_date_missing and sensitivity == "alta":
        return "alto"
    if freshness_status == "possivelmente_desatualizada" and depends_on_current_validity:
        return "alto"
    if freshness_status == "recente":
        return "baixo"
    if freshness_status == "intermediaria":
        return "medio" if depends_on_current_validity else "baixo"
    return "baixo" if sensitivity == "baixa" else "alto"


def _build_conflicts(
    findings: tuple[ExternalFindingInput, ...],
    source_evaluations: dict[str, _SourceEvaluation],
) -> tuple[dict[str, tuple[VerifiedConflict, ...]], set[str]]:
    findings_by_topic: dict[str, list[ExternalFindingInput]] = {}
    for finding in findings:
        findings_by_topic.setdefault(finding.topic_id, []).append(finding)

    conflicts_by_claim: dict[str, list[VerifiedConflict]] = {}
    losing_source_ids: set[str] = set()
    for topic_findings in findings_by_topic.values():
        if len(topic_findings) < 2:
            continue

        for index, finding in enumerate(topic_findings):
            for other in topic_findings[index + 1 :]:
                if finding.path_effect == other.path_effect:
                    continue
                conflict_a, conflict_b, losers = _pairwise_conflict(finding, other, source_evaluations)
                if conflict_a is not None:
                    conflicts_by_claim.setdefault(finding.claim_id, []).append(conflict_a)
                if conflict_b is not None:
                    conflicts_by_claim.setdefault(other.claim_id, []).append(conflict_b)
                losing_source_ids.update(losers)

    return {claim_id: tuple(conflicts) for claim_id, conflicts in conflicts_by_claim.items()}, losing_source_ids


def _pairwise_conflict(
    finding: ExternalFindingInput,
    other: ExternalFindingInput,
    source_evaluations: dict[str, _SourceEvaluation],
) -> tuple[VerifiedConflict | None, VerifiedConflict | None, set[str]]:
    effective_sensitivity = (
        finding.claim_time_sensitivity_context
        if _TIME_RANK[finding.claim_time_sensitivity_context] >= _TIME_RANK[other.claim_time_sensitivity_context]
        else other.claim_time_sensitivity_context
    )
    finding_best = _best_trusted_source(finding.source_ids, source_evaluations, finding.claim_time_sensitivity_context)
    other_best = _best_trusted_source(other.source_ids, source_evaluations, other.claim_time_sensitivity_context)
    if finding_best is None or other_best is None:
        return None, None, set()

    if _is_clear_newer_winner(finding_best, other_best, effective_sensitivity):
        return (
            None,
            _make_conflict(other, finding_best.record.source_id, other_best.record.source_id, "externo_mais_recente"),
            {other_best.record.source_id},
        )
    if _is_clear_newer_winner(other_best, finding_best, effective_sensitivity):
        return (
            _make_conflict(finding, other_best.record.source_id, finding_best.record.source_id, "externo_mais_recente"),
            None,
            {finding_best.record.source_id},
        )

    conflict_a = _make_conflict(finding, other_best.record.source_id, finding_best.record.source_id, "autoridade_divergente")
    conflict_b = _make_conflict(other, finding_best.record.source_id, other_best.record.source_id, "autoridade_divergente")
    return conflict_a, conflict_b, set()


def _best_trusted_source(
    source_ids: tuple[str, ...],
    source_evaluations: dict[str, _SourceEvaluation],
    sensitivity: str,
) -> _SourceEvaluation | None:
    trusted = [
        source_evaluations[source_id]
        for source_id in source_ids
        if source_evaluations[source_id].record.source_strength != "descartada"
    ]
    if not trusted:
        return None
    return max(trusted, key=lambda item: _source_preference(item, sensitivity))


def _source_preference(source: _SourceEvaluation, sensitivity: str) -> tuple[int, int, int]:
    freshness_rank = {
        "possivelmente_desatualizada": 1,
        "intermediaria": 2,
        "recente": 3,
    }[source.record.freshness_status]
    date_score = source.source_date_value.toordinal() if source.source_date_value is not None else 0
    if sensitivity == "alta":
        return (freshness_rank, source.strength_rank, date_score)
    return (source.strength_rank, freshness_rank, date_score)


def _is_clear_newer_winner(winner: _SourceEvaluation, loser: _SourceEvaluation, sensitivity: str) -> bool:
    if winner.record.source_strength == "descartada" or loser.record.source_strength == "descartada":
        return False
    if winner.source_date_value is None or loser.source_date_value is None:
        return False
    if winner.source_date_value <= loser.source_date_value:
        return False
    if sensitivity == "alta":
        return True
    return winner.strength_rank >= loser.strength_rank


def _elevate_conflict_loser_temporal_risk(
    source_evaluations: dict[str, _SourceEvaluation],
    losing_source_ids: set[str],
) -> dict[str, _SourceEvaluation]:
    if not losing_source_ids:
        return source_evaluations

    updated: dict[str, _SourceEvaluation] = {}
    for source_id, evaluation in source_evaluations.items():
        if source_id not in losing_source_ids or evaluation.record.temporal_risk == "alto":
            updated[source_id] = evaluation
            continue

        updated_record = VerifiedSourceRecord(
            source_id=evaluation.record.source_id,
            bundle_source_key=evaluation.record.bundle_source_key,
            url=evaluation.record.url,
            normalized_domain=evaluation.record.normalized_domain,
            source_title=evaluation.record.source_title,
            source_authority=evaluation.record.source_authority,
            source_strength=evaluation.record.source_strength,
            source_date=evaluation.record.source_date,
            collected_at=evaluation.record.collected_at,
            freshness_status=evaluation.record.freshness_status,
            temporal_risk="alto",
            citation_locator=evaluation.record.citation_locator,
            content_hash=evaluation.record.content_hash,
            acquisition_method=evaluation.record.acquisition_method,
            acquisition_query=evaluation.record.acquisition_query,
            acquisition_trace_id=evaluation.record.acquisition_trace_id,
            notes=evaluation.record.notes,
            bundle_identity_scope=evaluation.record.bundle_identity_scope,
        )
        updated[source_id] = _SourceEvaluation(
            record=updated_record,
            source_date_value=evaluation.source_date_value,
            strength_rank=evaluation.strength_rank,
            has_current_validity_claim=evaluation.has_current_validity_claim,
        )
    return updated


def _make_conflict(
    finding: ExternalFindingInput,
    winning_source_id: str,
    losing_source_id: str,
    conflict_type: str,
) -> VerifiedConflict:
    return VerifiedConflict(
        claim_id=finding.claim_id,
        conflict_type=conflict_type,
        conflicting_source_ids=tuple(sorted({winning_source_id, losing_source_id})),
        resolution_status="encaminhado_ao_comprovador",
        why_not_resolved_automatically="external conflicts may inform the round but remain subordinate to Comprovador and Guardião",
    )


def _claim_downgrade_reasons(
    finding: ExternalFindingInput,
    trusted_sources: list[_SourceEvaluation],
    conflicts: tuple[VerifiedConflict, ...],
) -> tuple[str, ...]:
    reasons: list[str] = []
    if finding.claim_time_sensitivity_context == "alta" and finding.depends_on_current_validity:
        if any(not source.record.source_date for source in trusted_sources):
            reasons.append("missing_source_date_in_high_sensitivity_context")

    if finding.depends_on_current_validity and any(
        source.record.freshness_status == "possivelmente_desatualizada" for source in trusted_sources
    ):
        reasons.append("stale_source_for_present_day_claim")

    if finding.requires_normative_force and not any(
        source.record.source_strength == "primaria_normativa" for source in trusted_sources
    ):
        reasons.append("normative_force_without_primary_normative_source")

    if any(_claim_temporal_risk(source, finding) == "alto" for source in trusted_sources):
        reasons.append("temporal_risk_alto")

    if any(conflict.conflict_type == "externo_mais_recente" for conflict in conflicts):
        reasons.append("newer_trustworthy_conflict_unresolved")

    return tuple(dict.fromkeys(reasons))


def _promotion_basis(
    finding: ExternalFindingInput,
    trusted_sources: list[_SourceEvaluation],
    internal_proven_items: tuple[str, ...],
) -> str:
    has_normative = any(source.record.source_strength == "primaria_normativa" for source in trusted_sources)
    has_internal_confirmation = bool(
        finding.internal_confirmation_reference
        and finding.internal_confirmation_reference in internal_proven_items
    )
    if has_normative and has_internal_confirmation:
        return "fonte_normativa_primaria_e_confirmacao_interna_disponivel"
    if has_normative:
        return "fonte_normativa_primaria"
    return "nenhuma"


def _temporal_basis(finding: ExternalFindingInput, trusted_sources: list[_SourceEvaluation]) -> str:
    if finding.depends_on_current_validity:
        any_high_risk = any(_claim_temporal_risk(source, finding) == "alto" for source in trusted_sources)
        if any(source.record.freshness_status == "recente" for source in trusted_sources):
            if any_high_risk:
                return "present-day claim mixes recent sources with stale or undated sources"
            return "present-day claim anchored by at least one recent source"
        if any(source.record.freshness_status == "intermediaria" for source in trusted_sources):
            return "present-day claim anchored only by intermediate-age sources"
        return "present-day claim anchored by stale or undated sources"

    if finding.claim_time_sensitivity_context == "baixa":
        return "low-sensitivity claim using explicit historical or stable references"
    return "claim does not require present-day validity but still carries explicit freshness weighting"


def _claim_temporal_risk(source: _SourceEvaluation, finding: ExternalFindingInput) -> str:
    return _classify_temporal_risk(
        source.record.freshness_status,
        finding.claim_time_sensitivity_context,
        finding.depends_on_current_validity,
        not source.record.source_date,
    )


def _why_classified(
    downgrade_reasons: tuple[str, ...],
    temporal_basis: str,
    promotion_status: str,
) -> str:
    if downgrade_reasons:
        return f"reclassified to hipotese because {', '.join(downgrade_reasons)}; {temporal_basis}"
    if promotion_status == "promotion_candidate":
        return f"remains provavel with promotion basis pending Comprovador review; {temporal_basis}"
    return f"remains provavel without promotion basis; {temporal_basis}"


def _highest_output_context(findings: tuple[ExternalFindingInput, ...]) -> str:
    if not findings:
        return "baixa"
    highest = max(findings, key=lambda item: _TIME_RANK[item.claim_time_sensitivity_context])
    return highest.claim_time_sensitivity_context


def _dedupe_conflicts(conflicts: list[VerifiedConflict]) -> tuple[VerifiedConflict, ...]:
    seen: set[tuple[str, str, tuple[str, ...]]] = set()
    deduped: list[VerifiedConflict] = []
    for conflict in conflicts:
        key = (conflict.claim_id, conflict.conflict_type, conflict.conflicting_source_ids)
        if key in seen:
            continue
        seen.add(key)
        deduped.append(conflict)
    return tuple(deduped)


def _parse_iso_date(raw: str, field_name: str) -> date:
    text = raw.strip()
    if not text:
        raise ExternalFreshnessVerifierError(f"{field_name} must be a non-empty ISO date or datetime string")
    if "T" in text or text.endswith("Z") or "+" in text:
        try:
            return datetime.fromisoformat(text.replace("Z", "+00:00")).date()
        except ValueError as exc:
            raise ExternalFreshnessVerifierError(f"invalid {field_name}: {text}") from exc
    try:
        return date.fromisoformat(text)
    except ValueError as exc:
        raise ExternalFreshnessVerifierError(f"invalid {field_name}: {text}") from exc


def _parse_optional_iso_date(raw: str, field_name: str) -> date | None:
    text = raw.strip()
    if not text:
        return None
    return _parse_iso_date(text, field_name)


def _normalize_search_scope_entry(entry: str) -> str:
    text = entry.strip().lower()
    if not text:
        raise ExternalFreshnessVerifierError("search_scope entries must be non-empty strings")
    if "://" in text:
        parts = urlsplit(text)
        host = parts.hostname or ""
    else:
        parts = urlsplit(f"//{text}")
        host = parts.hostname or ""
    normalized = host.strip(".")
    if not normalized:
        raise ExternalFreshnessVerifierError(f"invalid search_scope entry: {entry}")
    return normalized


def _normalize_url_domain(url: str, source_id: str) -> str:
    parts = urlsplit(url)
    if parts.scheme.lower() != "https":
        raise ExternalFreshnessVerifierError(f"url must use https for source {source_id}")
    host = (parts.hostname or "").strip(".").lower()
    if not host:
        raise ExternalFreshnessVerifierError(f"url must include a hostname for source {source_id}")
    return host


def _normalize_resource_url(url: str, source_id: str) -> tuple[str, str]:
    parts = urlsplit(url)
    domain = _normalize_url_domain(url, source_id)
    if parts.port in (None, 443):
        netloc = domain
    else:
        netloc = f"{domain}:{parts.port}"
    path = parts.path or "/"
    canonical_url = urlunsplit(("https", netloc, path, parts.query, ""))
    return canonical_url, parts.fragment.strip()


def _resource_family_url(url: str, source_id: str) -> str:
    parts = urlsplit(url)
    domain = _normalize_url_domain(url, source_id)
    if parts.port in (None, 443):
        netloc = domain
    else:
        netloc = f"{domain}:{parts.port}"
    path = parts.path or "/"
    return urlunsplit(("https", netloc, path, "", ""))


def _domain_allowed(domain: str, search_scope: tuple[str, ...]) -> bool:
    return any(domain == allowed or domain.endswith(f".{allowed}") for allowed in search_scope)


def _is_sha256_hex(value: str) -> bool:
    return len(value) == 64 and all(character in "0123456789abcdef" for character in value)


def _bundle_source_key(snapshot_revision: int, url: str, content_hash: str) -> str:
    key_material = content_hash or url
    digest = hashlib.sha256(f"{snapshot_revision}|{key_material}".encode("utf-8")).hexdigest()[:16]
    return f"bundle_{digest}"


def _citation_ref(bundle_source_key: str, citation_locator: str) -> str:
    locator = citation_locator.strip()
    if not locator:
        return bundle_source_key
    return f"{bundle_source_key}@{locator}"


def _render_markdown_text(value: str) -> str:
    return value.replace("\r\n", "\n").replace("\r", "\n").replace("\n", "\\n").strip()


def _render_markdown_optional(value: str) -> str:
    text = _render_markdown_text(value)
    return text if text else "-"


def _render_markdown_list(values: tuple[str, ...]) -> str:
    return repr([_render_markdown_text(value) for value in values])


def _render_alias_section(source_aliases: tuple[ExternalBundleSourceAlias, ...]) -> list[str]:
    lines = ["", "## Source Aliases"]
    if not source_aliases:
        lines.append("- none")
        return lines
    for alias in source_aliases:
        lines.append(
            "- "
            f"{_render_markdown_text(alias.original_source_id)} -> {_render_markdown_text(alias.canonical_source_id)} "
            f"[reason={alias.reason}; url={alias.canonical_resource_url}]"
        )
    return lines


def _render_source_section(
    source_register: tuple[VerifiedSourceRecord, ...],
    referenced_source_ids: set[str],
) -> list[str]:
    lines = ["", "## Sources"]
    if not source_register:
        lines.append("- none")
        return lines
    for source in source_register:
        usage = "referenced" if source.source_id in referenced_source_ids else "orphan"
        source_fields = [
            f"strength={source.source_strength}",
            f"usage={usage}",
            f"bundle_key={source.bundle_source_key}",
            f"scope={source.bundle_identity_scope}",
            f"url={source.url}",
            f"locator={_render_markdown_optional(source.citation_locator)}",
            f"domain={source.normalized_domain}",
            f"authority={_render_markdown_optional(source.source_authority)}",
            f"source_date={_render_markdown_optional(source.source_date)}",
            f"freshness={source.freshness_status}",
            f"risk={source.temporal_risk}",
            f"acquisition={source.acquisition_method}",
            f"collected_at={source.collected_at}",
            f"title={_render_markdown_optional(source.source_title)}",
            f"trace_id={_render_markdown_optional(source.acquisition_trace_id)}",
            f"content_hash={_render_markdown_optional(source.content_hash)}",
        ]
        if source.acquisition_query:
            source_fields.append(f"query={_render_markdown_text(source.acquisition_query)}")
        if source.notes:
            source_fields.append(f"notes={_render_markdown_text(source.notes)}")
        lines.append(
            "- "
            f"{_render_markdown_text(source.source_id)}: {', '.join(source_fields)}"
        )
    return lines


def _render_claim_section(title: str, claims: tuple[VerifiedClaim, ...]) -> list[str]:
    lines = ["", f"## {title}"]
    if not claims:
        lines.append("- none")
        return lines
    for claim in claims:
        lines.append(
            "- "
            f"{_render_markdown_text(claim.claim_id)}: {_render_markdown_text(claim.summary)} "
            f"[context={claim.claim_time_sensitivity_context}; promotion={claim.promotion_status}; "
            f"basis={claim.promotion_basis}; temporal_basis={_render_markdown_text(claim.temporal_basis)}; "
            f"why={_render_markdown_text(claim.why_classified)}; "
            f"sources={_render_markdown_list(claim.source_ids)}; "
            f"downgrade_reasons={_render_markdown_list(claim.downgrade_reasons)}; "
            f"citations={_render_markdown_list(claim.citation_refs)}]"
        )
    return lines


def _render_conflict_section(conflicts: tuple[VerifiedConflict, ...]) -> list[str]:
    lines = ["", "## Conflitos"]
    if not conflicts:
        lines.append("- none")
        return lines
    for conflict in conflicts:
        lines.append(
            "- "
            f"{_render_markdown_text(conflict.claim_id)}: {conflict.conflict_type} "
            f"[sources={_render_markdown_list(conflict.conflicting_source_ids)}; "
            f"resolution={conflict.resolution_status}; "
            f"why={_render_markdown_text(conflict.why_not_resolved_automatically)}]"
        )
    return lines


def _render_gap_section(gaps: tuple[ExternalGap, ...]) -> list[str]:
    lines = ["", "## Lacunas"]
    if not gaps:
        lines.append("- none")
        return lines
    for gap in gaps:
        lines.append(
            "- "
            f"{_render_markdown_text(gap.gap_id)}: {_render_markdown_text(gap.missing_fact)} "
            f"[required_source_class={gap.required_source_class}; "
            f"why={_render_markdown_text(gap.why_it_matters)}]"
        )
    return lines
