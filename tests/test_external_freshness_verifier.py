from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.external_freshness_verifier import (
    ExternalBundleSourceAlias,
    ExternalFindingInput,
    ExternalFreshnessRequest,
    ExternalFreshnessVerifierError,
    ExternalSourceInput,
    normalize_external_bundle,
    render_external_freshness_markdown,
    verify_external_freshness,
    write_external_freshness_markdown,
)
from tests.runtime_fixtures import seed_checkpointed_runtime


def _seed_runtime(root: Path) -> StateStore:
    run_init(root, None)
    store, _ = seed_checkpointed_runtime(root)
    store.validate_state()
    return store


class ExternalFreshnessVerifierTests(unittest.TestCase):
    def test_recent_primary_normative_claim_remains_probable_with_promotion_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Podemos seguir com a mudanca?",
                trigger_reason="precisa confirmar regra externa atual",
                paths_under_review=("seguir",),
                search_scope=("receita.economia.gov.br",),
                allowed_source_classes=("primaria_normativa", "primaria_tecnica"),
                internal_proven_items=("source:tracked.txt",),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://normas.receita.economia.gov.br/norma",
                        source_authority="Receita",
                        source_class="primaria_normativa",
                        source_date="2026-03-15",
                        collected_at="2026-04-11T12:00:00+00:00",
                        source_title="Norma oficial",
                        citation_locator="section-4",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        acquisition_method="web_search",
                        acquisition_query="norma receita abril 2026",
                        acquisition_trace_id="ws_123",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="A regra normativa segue valida para a execucao proposta.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                        internal_confirmation_reference="source:tracked.txt",
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.time_sensitivity_context, "alta")
            self.assertEqual(len(report.provavel), 1)
            self.assertEqual(len(report.hipotese), 0)
            self.assertEqual(report.provavel[0].promotion_status, "promotion_candidate")
            self.assertEqual(
                report.provavel[0].promotion_basis,
                "fonte_normativa_primaria_e_confirmacao_interna_disponivel",
            )
            self.assertEqual(
                report.provavel[0].citation_refs,
                (f"{report.source_register[0].bundle_source_key}@section-4",),
            )
            self.assertEqual(report.snapshot_revision, 2)
            self.assertEqual(report.snapshot_validation_result, "ok")
            self.assertEqual(report.source_register[0].normalized_domain, "normas.receita.economia.gov.br")
            self.assertEqual(report.source_register[0].acquisition_method, "web_search")
            self.assertEqual(report.source_register[0].content_hash, "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa")
            self.assertEqual(report.source_register[0].freshness_status, "recente")
            self.assertEqual(report.source_register[0].temporal_risk, "baixo")
            self.assertEqual(report.bundle_identity_scope, "report_scoped")
            self.assertEqual(report.source_register[0].bundle_identity_scope, "report_scoped")

    def test_missing_date_in_high_sensitivity_present_day_claim_becomes_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="A regra ainda vale hoje?",
                trigger_reason="risco de desatualizacao externa",
                paths_under_review=("manter",),
                search_scope=("gov.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://gov.example/doc",
                        source_authority="Gov",
                        source_class="primaria_tecnica",
                        source_date="",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="A orientacao tecnica continua valida no presente.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(report.provavel), 0)
            self.assertEqual(len(report.hipotese), 1)
            self.assertIn("missing_source_date_in_high_sensitivity_context", report.hipotese[0].downgrade_reasons)
            self.assertIn("temporal_risk_alto", report.hipotese[0].downgrade_reasons)
            self.assertEqual(report.source_register[0].freshness_status, "possivelmente_desatualizada")
            self.assertEqual(report.source_register[0].temporal_risk, "alto")

    def test_more_recent_trustworthy_conflict_downgrades_older_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Qual caminho permanece atual?",
                trigger_reason="duas fontes externas divergem",
                paths_under_review=("seguir", "recuar"),
                search_scope=("vendor.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="old",
                        url="https://vendor.example/v1",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2025-02-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="new",
                        url="https://vendor.example/v2",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="old-claim",
                        topic_id="api-policy",
                        summary="A politica antiga ainda permite o caminho seguir.",
                        source_ids=("old",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="new-claim",
                        topic_id="api-policy",
                        summary="A politica mais nova bloqueia o caminho seguir.",
                        source_ids=("new",),
                        claim_time_sensitivity_context="alta",
                        path_effect="challenges_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual({claim.claim_id for claim in report.provavel}, {"new-claim"})
            self.assertEqual({claim.claim_id for claim in report.hipotese}, {"old-claim"})
            self.assertIn("newer_trustworthy_conflict_unresolved", report.hipotese[0].downgrade_reasons)
            self.assertTrue(any(conflict.claim_id == "old-claim" for conflict in report.conflitos))
            self.assertEqual(report.source_register[0].source_id, "new")
            self.assertEqual(report.source_register[0].freshness_status, "recente")

    def test_more_recent_trustworthy_secondary_conflict_still_downgrades_older_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Qual caminho permanece atual?",
                trigger_reason="fonte secundaria confiavel mais recente diverge",
                paths_under_review=("seguir", "recuar"),
                search_scope=("vendor.example",),
                allowed_source_classes=("primaria_tecnica", "secundaria_confiavel"),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="old",
                        url="https://vendor.example/v1",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2025-08-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="new",
                        url="https://vendor.example/v2",
                        source_authority="Trusted blog",
                        source_class="secundaria_confiavel",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="old-claim",
                        topic_id="api-policy",
                        summary="A politica antiga ainda permite o caminho seguir.",
                        source_ids=("old",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="new-claim",
                        topic_id="api-policy",
                        summary="A fonte mais nova bloqueia o caminho seguir.",
                        source_ids=("new",),
                        claim_time_sensitivity_context="alta",
                        path_effect="challenges_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual({claim.claim_id for claim in report.provavel}, {"new-claim"})
            self.assertEqual({claim.claim_id for claim in report.hipotese}, {"old-claim"})
            self.assertIn("newer_trustworthy_conflict_unresolved", report.hipotese[0].downgrade_reasons)
            self.assertTrue(
                any(
                    conflict.claim_id == "old-claim" and conflict.conflict_type == "externo_mais_recente"
                    for conflict in report.conflitos
                )
            )
            source_by_id = {source.source_id: source for source in report.source_register}
            self.assertEqual(source_by_id["old"].temporal_risk, "alto")

    def test_newer_secondary_does_not_override_older_normative_in_medium_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Qual caminho permanece atual?",
                trigger_reason="recencia deve ser ponderada com autoridade",
                paths_under_review=("seguir", "recuar"),
                search_scope=("vendor.example",),
                allowed_source_classes=("primaria_normativa", "secundaria_confiavel"),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="old",
                        url="https://vendor.example/normative",
                        source_authority="Normative source",
                        source_class="primaria_normativa",
                        source_date="2024-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="new",
                        url="https://vendor.example/secondary",
                        source_authority="Trusted blog",
                        source_class="secundaria_confiavel",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="old-claim",
                        topic_id="policy",
                        summary="A fonte normativa anterior ainda suporta o caminho.",
                        source_ids=("old",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="new-claim",
                        topic_id="policy",
                        summary="A fonte secundaria mais recente questiona o caminho.",
                        source_ids=("new",),
                        claim_time_sensitivity_context="media",
                        path_effect="challenges_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual({claim.claim_id for claim in report.provavel}, {"old-claim", "new-claim"})
            self.assertEqual(report.hipotese, ())
            self.assertEqual(
                {(conflict.claim_id, conflict.conflict_type) for conflict in report.conflitos},
                {
                    ("old-claim", "autoridade_divergente"),
                    ("new-claim", "autoridade_divergente"),
                },
            )

    def test_runtime_conflicts_emit_only_forwarded_resolution_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Qual caminho permanece atual?",
                trigger_reason="duas fontes externas divergem",
                paths_under_review=("seguir", "recuar"),
                search_scope=("vendor.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="old",
                        url="https://vendor.example/v1",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2025-02-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="new",
                        url="https://vendor.example/v2",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="old-claim",
                        topic_id="api-policy",
                        summary="A politica antiga ainda permite o caminho seguir.",
                        source_ids=("old",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="new-claim",
                        topic_id="api-policy",
                        summary="A politica mais nova bloqueia o caminho seguir.",
                        source_ids=("new",),
                        claim_time_sensitivity_context="alta",
                        path_effect="challenges_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertTrue(report.conflitos)
            self.assertEqual(
                {conflict.resolution_status for conflict in report.conflitos},
                {"encaminhado_ao_comprovador"},
            )

    def test_conflict_with_same_source_deduplicates_conflicting_source_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="mesma fonte sustenta caminhos opostos",
                paths_under_review=("seguir", "recuar"),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="support",
                        topic_id="topic-1",
                        summary="Suporta",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="challenge",
                        topic_id="topic-1",
                        summary="Desafia",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="challenges_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(
                {conflict.conflicting_source_ids for conflict in report.conflitos},
                {("s1",)},
            )

    def test_runtime_gaps_emit_only_normative_or_technical_required_source_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Que classe de fonte falta para sustentar as claims?",
                trigger_reason="confirmar subset runtime de lacunas",
                paths_under_review=("seguir",),
                search_scope=("blog.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://blog.example/post",
                        source_authority="Blog tecnico",
                        source_class="secundaria_confiavel",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="technical-claim",
                        topic_id="topic-1",
                        summary="Falta suporte tecnico confiavel para seguir.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="normative-claim",
                        topic_id="topic-2",
                        summary="Falta base normativa primaria para seguir.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(report.lacunas), 2)
            self.assertEqual(
                {gap.required_source_class for gap in report.lacunas},
                {"primaria_tecnica", "primaria_normativa"},
            )

    def test_top_level_time_sensitivity_tracks_highest_finding_even_when_output_is_only_gaps(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Que classe de fonte falta?",
                trigger_reason="estresse de contexto de topo sem claims viaveis",
                paths_under_review=("seguir",),
                search_scope=("blog.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://blog.example/post",
                        source_authority="Blog tecnico",
                        source_class="secundaria_confiavel",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Falta base normativa primaria para seguir.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.provavel, ())
            self.assertEqual(report.hipotese, ())
            self.assertEqual(len(report.lacunas), 1)
            self.assertEqual(report.time_sensitivity_context, "alta")

    def test_low_sensitivity_intermediate_source_depends_on_current_validity_stays_medium_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="A referencia ainda deve pesar para a rodada atual?",
                trigger_reason="precisa conferir risco temporal em contexto baixo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/reference",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2022-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="A referencia ainda precisa valer para a execucao presente.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="baixa",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.source_register[0].freshness_status, "intermediaria")
            self.assertEqual(report.source_register[0].temporal_risk, "medio")
            self.assertEqual({claim.claim_id for claim in report.provavel}, {"c1"})

    def test_low_sensitivity_stale_source_without_present_day_dependency_stays_low_risk(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="A referencia historica ainda ajuda a compor contexto?",
                trigger_reason="precisa evitar overweight em material antigo mas util",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/history",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2010-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="A referencia antiga ainda ilumina o contexto, sem exigir validade presente.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="baixa",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.source_register[0].freshness_status, "possivelmente_desatualizada")
            self.assertEqual(report.source_register[0].temporal_risk, "baixo")
            self.assertEqual({claim.claim_id for claim in report.provavel}, {"c1"})

    def test_secondary_source_cannot_support_normative_force_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="A base normativa esta comprovada?",
                trigger_reason="exige forca normativa",
                paths_under_review=("alterar",),
                search_scope=("blog.example",),
                allowed_source_classes=("secundaria_confiavel",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://blog.example/post",
                        source_authority="Blog tecnico",
                        source_class="secundaria_confiavel",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Existe base normativa suficiente para executar a alteracao.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(report.hipotese), 1)
            self.assertIn("normative_force_without_primary_normative_source", report.hipotese[0].downgrade_reasons)
            self.assertEqual(report.hipotese[0].promotion_status, "not_eligible_for_promotion")

    def test_primary_technical_source_cannot_support_normative_force_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Existe base normativa suficiente?",
                trigger_reason="congelar subset runtime atual",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/guide",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Ha base normativa suficiente para executar.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.provavel, ())
            self.assertEqual(len(report.hipotese), 1)
            self.assertIn("normative_force_without_primary_normative_source", report.hipotese[0].downgrade_reasons)
            self.assertEqual(report.hipotese[0].promotion_status, "not_eligible_for_promotion")
            self.assertEqual(report.hipotese[0].promotion_basis, "nenhuma")

    def test_shared_source_temporal_risk_does_not_force_low_sensitivity_claim_into_hypothesis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Como duas claims compartilham uma fonte antiga?",
                trigger_reason="evitar vazamento temporal entre claims",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="shared",
                        url="https://docs.example/shared",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2020-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="high-claim",
                        topic_id="topic-high",
                        summary="A claim alta depende do estado atual.",
                        source_ids=("shared",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="low-claim",
                        topic_id="topic-low",
                        summary="A claim baixa usa a mesma fonte apenas como contexto historico.",
                        source_ids=("shared",),
                        claim_time_sensitivity_context="baixa",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual({claim.claim_id for claim in report.hipotese}, {"high-claim"})
            self.assertEqual({claim.claim_id for claim in report.provavel}, {"low-claim"})
            self.assertIn("temporal_risk_alto", report.hipotese[0].downgrade_reasons)
            self.assertNotIn("temporal_risk_alto", report.provavel[0].downgrade_reasons)
            self.assertEqual(report.source_register[0].temporal_risk, "alto")

    def test_present_day_claim_with_recent_and_stale_sources_reports_mixed_temporal_basis(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="fontes mistas na mesma claim",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="recent",
                        url="https://docs.example/recent",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-10",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="stale",
                        url="https://docs.example/stale",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2024-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("recent", "stale"),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(report.hipotese), 1)
            self.assertIn("stale_source_for_present_day_claim", report.hipotese[0].downgrade_reasons)
            self.assertIn("temporal_risk_alto", report.hipotese[0].downgrade_reasons)
            self.assertEqual(
                report.hipotese[0].temporal_basis,
                "present-day claim mixes recent sources with stale or undated sources",
            )
            self.assertIn(
                "present-day claim mixes recent sources with stale or undated sources",
                report.hipotese[0].why_classified,
            )

    def test_top_level_time_sensitivity_uses_highest_claim_context(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Precisamos combinar duas referencias?",
                trigger_reason="mescla de contextos externos",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s-high",
                        url="https://docs.example/high",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-05",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="s-low",
                        url="https://docs.example/low",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2020-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c-high",
                        topic_id="topic-high",
                        summary="A referencia atual governa o fluxo atual.",
                        source_ids=("s-high",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                    ExternalFindingInput(
                        claim_id="c-low",
                        topic_id="topic-low",
                        summary="A referencia historica contextualiza o desenho.",
                        source_ids=("s-low",),
                        claim_time_sensitivity_context="baixa",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.time_sensitivity_context, "alta")
            self.assertEqual({claim.claim_time_sensitivity_context for claim in report.provavel}, {"alta", "baixa"})

    def test_verifier_rejects_unknown_allowed_source_class(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("nao_existente",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request)

    def test_verifier_rejects_duplicate_source_ids_inside_claim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s1"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request)

    def test_internal_proven_items_must_bind_to_canonical_snapshot_refs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=("qualquer-coisa",),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                        internal_confirmation_reference="qualquer-coisa",
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request)

    def test_internal_confirmation_alone_does_not_create_promotion_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=("source:tracked.txt",),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                        internal_confirmation_reference="source:tracked.txt",
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.provavel[0].promotion_status, "not_eligible_for_promotion")
            self.assertEqual(report.provavel[0].promotion_basis, "nenhuma")

    def test_hypothesis_cannot_remain_promotion_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="A regra ainda vale hoje?",
                trigger_reason="fonte normativa antiga precisa ser estressada",
                paths_under_review=("seguir",),
                search_scope=("gov.example",),
                allowed_source_classes=("primaria_normativa",),
                internal_proven_items=("source:tracked.txt",),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://gov.example/norma",
                        source_authority="Gov",
                        source_class="primaria_normativa",
                        source_date="2020-01-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="A regra normativa ainda governaria a execucao presente.",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                        internal_confirmation_reference="source:tracked.txt",
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(report.hipotese), 1)
            self.assertEqual(report.hipotese[0].promotion_status, "not_eligible_for_promotion")
            self.assertEqual(report.hipotese[0].promotion_basis, "nenhuma")
            self.assertIn("stale_source_for_present_day_claim", report.hipotese[0].downgrade_reasons)

    def test_bundle_normalizer_deduplicates_equivalent_urls_and_emits_alias(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy#section-1",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(bundle.component, "Normalizador de Bundle Externo")
            self.assertEqual(bundle.snapshot_revision, 2)
            self.assertEqual(bundle.snapshot_validation_result, "ok")
            self.assertEqual(bundle.normalized_request.sources[0].url, "https://docs.example/policy")
            self.assertEqual(bundle.normalized_request.findings[0].source_ids, ("s2",))
            self.assertEqual(
                bundle.source_aliases,
                (
                    ExternalBundleSourceAlias(
                        original_source_id="s1",
                        canonical_source_id="s2",
                        canonical_resource_url="https://docs.example/policy",
                        reason="equivalent_resource_url",
                    ),
                ),
            )

    def test_query_variants_without_content_hash_remain_distinct_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy?view=full",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy?view=compact",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(tuple(source.source_id for source in bundle.normalized_request.sources), ("s1", "s2"))
            self.assertEqual(bundle.normalized_request.findings[0].source_ids, ("s1", "s2"))
            self.assertEqual(bundle.source_aliases, ())

    def test_query_variants_with_matching_content_hash_collapse_and_preserve_canonical_query(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy?view=full",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy?view=compact#section-2",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(tuple(source.source_id for source in bundle.normalized_request.sources), ("s2",))
            self.assertEqual(bundle.normalized_request.sources[0].url, "https://docs.example/policy?view=compact")
            self.assertEqual(bundle.normalized_request.sources[0].citation_locator, "section-2")
            self.assertEqual(bundle.normalized_request.findings[0].source_ids, ("s2",))
            self.assertEqual(
                bundle.source_aliases,
                (
                    ExternalBundleSourceAlias(
                        original_source_id="s1",
                        canonical_source_id="s2",
                        canonical_resource_url="https://docs.example/policy?view=compact",
                        reason="matching_content_hash",
                    ),
                ),
            )

    def test_matching_content_hash_does_not_collapse_cross_resource_or_cross_domain_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example", "mirror.example"),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="docs",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    ExternalSourceInput(
                        source_id="mirror",
                        url="https://mirror.example/copied-policy",
                        source_authority="Mirror",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("docs", "mirror"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(tuple(source.source_id for source in bundle.normalized_request.sources), ("docs", "mirror"))
            self.assertEqual(bundle.normalized_request.findings[0].source_ids, ("docs", "mirror"))
            self.assertEqual(bundle.source_aliases, ())

    def test_same_url_collapses_when_only_one_duplicate_has_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy#section-9",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(tuple(source.source_id for source in bundle.normalized_request.sources), ("s1",))
            self.assertEqual(bundle.normalized_request.sources[0].citation_locator, "section-9")
            self.assertEqual(bundle.normalized_request.findings[0].source_ids, ("s1",))
            self.assertEqual(
                bundle.source_aliases,
                (
                    ExternalBundleSourceAlias(
                        original_source_id="s2",
                        canonical_source_id="s1",
                        canonical_resource_url="https://docs.example/policy",
                        reason="equivalent_resource_url",
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")
            self.assertEqual(report.provavel[0].citation_refs, (f"{report.source_register[0].bundle_source_key}@section-9",))

    def test_alias_backfill_only_fills_missing_canonical_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Authority A",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        source_title="Title A",
                        acquisition_query="query-a",
                        acquisition_trace_id="trace-a",
                        notes="notes-a",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/policy#section-b",
                        source_authority="Authority B",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        source_title="Title B",
                        citation_locator="section-b",
                        acquisition_query="query-b",
                        acquisition_trace_id="trace-b",
                        notes="notes-b",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1", "s2"),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            bundle = normalize_external_bundle(root, request, normalized_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(tuple(source.source_id for source in bundle.normalized_request.sources), ("s2",))
            self.assertEqual(bundle.normalized_request.sources[0].source_authority, "Authority B")
            self.assertEqual(bundle.normalized_request.sources[0].source_title, "Title B")
            self.assertEqual(bundle.normalized_request.sources[0].citation_locator, "section-b")
            self.assertEqual(bundle.normalized_request.sources[0].acquisition_query, "query-b")
            self.assertEqual(bundle.normalized_request.sources[0].acquisition_trace_id, "trace-b")
            self.assertEqual(bundle.normalized_request.sources[0].notes, "notes-b")

    def test_alias_collapse_rewrites_report_claim_sources_and_citations_end_to_end(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Alias end-to-end",
                trigger_reason="precisa congelar a cadeia final claim -> alias -> citation",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/resource?ref=one",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        citation_locator="section-1",
                    ),
                    ExternalSourceInput(
                        source_id="s2",
                        url="https://docs.example/resource?ref=two",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
                        citation_locator="section-1",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual([(alias.original_source_id, alias.canonical_source_id) for alias in report.source_aliases], [("s1", "s2")])
            self.assertEqual([source.source_id for source in report.source_register], ["s2"])
            self.assertEqual(report.provavel[0].source_ids, ("s2",))
            self.assertEqual(report.provavel[0].citation_refs, (f"{report.source_register[0].bundle_source_key}@section-1",))

    def test_source_register_keeps_normalized_orphan_sources_from_bundle(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Fonte orfa no bundle",
                trigger_reason="congelar inventario normalizado do source_register",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="used",
                        url="https://docs.example/used",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                    ExternalSourceInput(
                        source_id="orphan",
                        url="https://docs.example/orphan",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-03-20",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("used",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=False,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual([source.source_id for source in report.source_register], ["orphan", "used"])
            self.assertEqual(report.provavel[0].source_ids, ("used",))
            self.assertEqual(report.conflitos, ())
            self.assertEqual(report.lacunas, ())

    def test_same_source_across_snapshots_uses_report_scoped_bundle_identity(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            first = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Updated summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            second = verify_external_freshness(root, request, queried_at="2026-04-11T12:30:00+00:00")

            self.assertEqual(first.bundle_identity_scope, "report_scoped")
            self.assertEqual(second.bundle_identity_scope, "report_scoped")
            self.assertEqual(first.source_register[0].bundle_identity_scope, "report_scoped")
            self.assertEqual(second.source_register[0].bundle_identity_scope, "report_scoped")
            self.assertNotEqual(first.snapshot_revision, second.snapshot_revision)
            self.assertNotEqual(first.source_register[0].bundle_source_key, second.source_register[0].bundle_source_key)

    def test_invalid_source_class_raises_component_error_instead_of_keyerror(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="bogus",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

    def test_verifier_rejects_source_outside_search_scope(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://vendor.example/x",
                        source_authority="Vendor",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request)

    def test_verifier_accepts_search_scope_entry_with_port_when_domain_matches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example:8443",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example:8443/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            report = verify_external_freshness(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(report.provavel[0].claim_id, "c1")

    def test_verifier_rejects_non_https_url_and_invalid_content_hash(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="http://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                        content_hash="not-a-hash",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            with self.assertRaises(ExternalFreshnessVerifierError):
                verify_external_freshness(root, request)

    def test_markdown_writer_stays_read_only_and_rejects_runtime_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            store = _seed_runtime(root)
            before_state = store.state_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            markdown = render_external_freshness_markdown(root, request, queried_at="2026-04-11T12:00:00+00:00")
            self.assertIn("# External Freshness Verifier", markdown)
            self.assertIn("domain=docs.example", markdown)
            self.assertIn("Snapshot revision: 2", markdown)
            self.assertIn("Bundle identity scope: report_scoped", markdown)
            self.assertIn("citations=['bundle_", markdown)

            out_path = write_external_freshness_markdown(root, request, "freshness.md", queried_at="2026-04-11T12:00:00+00:00")
            self.assertTrue(out_path.exists())

            with self.assertRaises(ExternalFreshnessVerifierError):
                write_external_freshness_markdown(root, request, ".cerebro/blocked.md", queried_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(before_revision, store.read_snapshot().revision)
            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))

    def test_markdown_render_normalizes_multiline_text_and_keeps_audit_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Linha 1\n- Linha 2",
                trigger_reason="Motivo\n[extra]",
                paths_under_review=("seguir", "recuar"),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="used",
                        url="https://docs.example/policy#sec-1,part-2",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="",
                        collected_at="2026-04-11T12:00:00+00:00",
                        source_title="Titulo\nquebrado",
                        citation_locator="sec-1,part-2",
                        acquisition_query="policy current",
                    ),
                    ExternalSourceInput(
                        source_id="orphan",
                        url="https://docs.example/orphan",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo\nquebrado",
                        source_ids=("used",),
                        claim_time_sensitivity_context="alta",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=False,
                    ),
                ),
            )

            markdown = render_external_freshness_markdown(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertIn("Question or proposal: Linha 1\\n- Linha 2", markdown)
            self.assertIn("Trigger reason: Motivo\\n[extra]", markdown)
            self.assertNotIn("- c1: Resumo\nquebrado", markdown)
            self.assertIn("Resumo\\nquebrado", markdown)
            self.assertIn("Source register note: freshness/risk are aggregated per source; claim sections remain claim-local", markdown)
            self.assertIn("used: strength=primaria_tecnica, usage=referenced", markdown)
            self.assertIn("orphan: strength=primaria_tecnica, usage=orphan", markdown)
            self.assertIn("url=https://docs.example/policy", markdown)
            self.assertIn("locator=sec-1,part-2", markdown)
            self.assertIn("title=Titulo\\nquebrado", markdown)
            self.assertIn("query=policy current", markdown)
            self.assertIn("temporal_basis=present-day claim anchored by stale or undated sources", markdown)
            self.assertIn("downgrade_reasons=['missing_source_date_in_high_sensitivity_context', 'stale_source_for_present_day_claim', 'temporal_risk_alto']", markdown)
            self.assertIn("citations=['bundle_", markdown)
            self.assertIn("@sec-1,part-2']", markdown)

    def test_markdown_marks_gap_source_as_referenced_when_finding_points_to_it(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="allowed class removes trusted source",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_normativa",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/policy",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(
                    ExternalFindingInput(
                        claim_id="c1",
                        topic_id="topic-1",
                        summary="Resumo",
                        source_ids=("s1",),
                        claim_time_sensitivity_context="media",
                        path_effect="supports_path",
                        depends_on_current_validity=True,
                        requires_normative_force=True,
                    ),
                ),
            )

            markdown = render_external_freshness_markdown(root, request, queried_at="2026-04-11T12:00:00+00:00")

            self.assertIn("s1: strength=descartada, usage=referenced", markdown)
            self.assertIn("## Lacunas", markdown)
            self.assertIn("gap-c1: Resumo [required_source_class=primaria_normativa;", markdown)

    def test_verifier_rejects_empty_findings_tuple(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            _seed_runtime(root)

            request = ExternalFreshnessRequest(
                question_or_proposal="Pergunta",
                trigger_reason="Motivo",
                paths_under_review=("seguir",),
                search_scope=("docs.example",),
                allowed_source_classes=("primaria_tecnica",),
                internal_proven_items=(),
                sources=(
                    ExternalSourceInput(
                        source_id="s1",
                        url="https://docs.example/x",
                        source_authority="Docs",
                        source_class="primaria_tecnica",
                        source_date="2026-04-01",
                        collected_at="2026-04-11T12:00:00+00:00",
                    ),
                ),
                findings=(),
            )

            with self.assertRaisesRegex(ExternalFreshnessVerifierError, "findings must be a non-empty tuple"):
                verify_external_freshness(root, request)
