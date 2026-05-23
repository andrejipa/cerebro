"""Public reusable fixtures for the external freshness contract v1."""

from __future__ import annotations

from extensions.external_freshness_verifier.contract import (
    serialize_external_bundle_normalization_report,
    serialize_external_freshness_report,
    serialize_external_freshness_request,
)
from extensions.external_freshness_verifier.verifier import (
    ExternalBundleNormalizationReport,
    ExternalBundleSourceAlias,
    ExternalFindingInput,
    ExternalFreshnessReport,
    ExternalFreshnessRequest,
    ExternalGap,
    ExternalSourceInput,
    VerifiedClaim,
    VerifiedConflict,
    VerifiedSourceRecord,
)


def build_external_freshness_request_fixture_v1() -> ExternalFreshnessRequest:
    """Return a reusable Python request fixture for local composition and tests."""
    return ExternalFreshnessRequest(
        question_or_proposal="Podemos seguir com a mudanca externa proposta?",
        trigger_reason="precisa confirmar se a politica tecnica externa continua atual",
        paths_under_review=("seguir",),
        search_scope=("docs.example",),
        allowed_source_classes=("primaria_tecnica", "secundaria_confiavel"),
        internal_proven_items=("source:tracked.txt", "checkpoint.next_step"),
        sources=(
            ExternalSourceInput(
                source_id="s1",
                url="https://docs.example/policy",
                source_authority="Vendor Docs",
                source_class="primaria_tecnica",
                source_date="2026-04-05",
                collected_at="2026-04-11T12:00:00+00:00",
                source_title="Current policy",
                citation_locator="section-4",
                acquisition_method="web_search",
                acquisition_query="docs example policy april 2026",
                acquisition_trace_id="ws_fixture_1",
                notes="fixture request raw source",
            ),
            ExternalSourceInput(
                source_id="s2",
                url="https://docs.example/policy#section-4",
                source_authority="Vendor Docs",
                source_class="primaria_tecnica",
                source_date="2026-04-05",
                collected_at="2026-04-11T12:00:00+00:00",
                source_title="Current policy section",
                acquisition_method="manual",
                notes="fixture alias candidate",
            ),
        ),
        findings=(
            ExternalFindingInput(
                claim_id="c1",
                topic_id="vendor-policy",
                summary="A politica tecnica atual ainda permite o caminho proposto.",
                source_ids=("s1", "s2"),
                claim_time_sensitivity_context="alta",
                path_effect="supports_path",
                depends_on_current_validity=True,
                requires_normative_force=False,
                internal_confirmation_reference="source:tracked.txt",
            ),
        ),
    )


def build_external_bundle_normalization_report_fixture_v1() -> ExternalBundleNormalizationReport:
    """Return a reusable Python normalization-report fixture for local composition and tests."""
    return ExternalBundleNormalizationReport(
        component="Normalizador de Bundle Externo",
        normalized_at="2026-04-11T12:00:00+00:00",
        snapshot_revision=2,
        snapshot_validation_result="ok",
        canonical_internal_refs=("checkpoint.next_step", "source:tracked.txt"),
        source_aliases=(
            ExternalBundleSourceAlias(
                original_source_id="s1",
                canonical_source_id="s2",
                canonical_resource_url="https://docs.example/policy",
                reason="equivalent_resource_url",
            ),
        ),
        normalized_request=ExternalFreshnessRequest(
            question_or_proposal="Podemos seguir com a mudanca externa proposta?",
            trigger_reason="precisa confirmar se a politica tecnica externa continua atual",
            paths_under_review=("seguir",),
            search_scope=("docs.example",),
            allowed_source_classes=("primaria_tecnica", "secundaria_confiavel"),
            internal_proven_items=("source:tracked.txt", "checkpoint.next_step"),
            sources=(
                ExternalSourceInput(
                    source_id="s2",
                    url="https://docs.example/policy",
                    source_authority="Vendor Docs",
                    source_class="primaria_tecnica",
                    source_date="2026-04-05",
                    collected_at="2026-04-11T12:00:00+00:00",
                    source_title="Current policy section",
                    citation_locator="section-4",
                    acquisition_method="manual",
                    notes="fixture normalized source",
                ),
            ),
            findings=(
                ExternalFindingInput(
                    claim_id="c1",
                    topic_id="vendor-policy",
                    summary="A politica tecnica atual ainda permite o caminho proposto.",
                    source_ids=("s2",),
                    claim_time_sensitivity_context="alta",
                    path_effect="supports_path",
                    depends_on_current_validity=True,
                    requires_normative_force=False,
                    internal_confirmation_reference="source:tracked.txt",
                ),
            ),
        ),
    )


def build_external_freshness_report_fixture_v1() -> ExternalFreshnessReport:
    """Return a reusable Python final-report fixture for local composition and tests."""
    return ExternalFreshnessReport(
        component="Verificador de Atualidade Externa",
        queried_at="2026-04-11T12:00:00+00:00",
        question_or_proposal="Podemos seguir com a mudanca externa proposta?",
        trigger_reason="precisa confirmar se a politica tecnica externa continua atual",
        paths_under_review=("seguir",),
        snapshot_revision=2,
        snapshot_validation_result="ok",
        time_sensitivity_context="alta",
        source_aliases=(
            ExternalBundleSourceAlias(
                original_source_id="s1",
                canonical_source_id="s2",
                canonical_resource_url="https://docs.example/policy",
                reason="equivalent_resource_url",
            ),
        ),
        source_register=(
            VerifiedSourceRecord(
                source_id="s2",
                bundle_source_key="bundle_fixture_policy",
                bundle_identity_scope="report_scoped",
                url="https://docs.example/policy",
                normalized_domain="docs.example",
                source_title="Current policy section",
                source_authority="Vendor Docs",
                source_strength="primaria_tecnica",
                source_date="2026-04-05",
                collected_at="2026-04-11T12:00:00+00:00",
                freshness_status="recente",
                temporal_risk="baixo",
                citation_locator="section-4",
                content_hash="",
                acquisition_method="manual",
                acquisition_query="",
                acquisition_trace_id="",
                notes="fixture normalized source",
            ),
            VerifiedSourceRecord(
                source_id="s3",
                bundle_source_key="bundle_fixture_policy_older",
                bundle_identity_scope="report_scoped",
                url="https://blog.example/policy-summary",
                normalized_domain="blog.example",
                source_title="Older secondary summary",
                source_authority="Industry Blog",
                source_strength="secundaria_confiavel",
                source_date="2025-12-15",
                collected_at="2026-04-11T12:00:00+00:00",
                freshness_status="intermediaria",
                temporal_risk="medio",
                citation_locator="article",
                content_hash="",
                acquisition_method="manual",
                acquisition_query="",
                acquisition_trace_id="",
                notes="fixture conflicting source",
            ),
        ),
        provavel=(
            VerifiedClaim(
                claim_id="c1",
                summary="A politica tecnica atual ainda permite o caminho proposto.",
                source_ids=("s2",),
                citation_refs=("bundle_fixture_policy@section-4",),
                claim_time_sensitivity_context="alta",
                why_classified="remains provavel without promotion basis; present-day claim anchored by at least one recent source",
                promotion_status="not_eligible_for_promotion",
                promotion_basis="nenhuma",
                temporal_basis="present-day claim anchored by at least one recent source",
                downgrade_reasons=(),
            ),
        ),
        hipotese=(),
        conflitos=(
            VerifiedConflict(
                claim_id="c1",
                conflict_type="autoridade_divergente",
                conflicting_source_ids=("s2", "s3"),
                resolution_status="encaminhado_ao_comprovador",
                why_not_resolved_automatically="external conflicts may inform the round but remain subordinate to Comprovador and Guardião",
            ),
        ),
        lacunas=(
            ExternalGap(
                gap_id="g1",
                missing_fact="Public changelog date for the deprecation boundary",
                why_it_matters="without a dated primary note the verifier cannot strengthen the path beyond provavel",
                required_source_class="primaria_tecnica",
            ),
        ),
        operational_note="external read-only analysis output; non-canonical; not a runtime decision",
        bundle_identity_scope="report_scoped",
    )


def get_external_freshness_contract_fixture_payloads_v1() -> dict[str, dict]:
    """Return canonical serialized fixture payloads under the public v1 contract."""
    return {
        "request": serialize_external_freshness_request(build_external_freshness_request_fixture_v1()),
        "normalization_report": serialize_external_bundle_normalization_report(
            build_external_bundle_normalization_report_fixture_v1()
        ),
        "report": serialize_external_freshness_report(build_external_freshness_report_fixture_v1()),
    }


__all__ = [
    "build_external_bundle_normalization_report_fixture_v1",
    "build_external_freshness_report_fixture_v1",
    "build_external_freshness_request_fixture_v1",
    "get_external_freshness_contract_fixture_payloads_v1",
]
