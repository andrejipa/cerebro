from __future__ import annotations

import tempfile
import unittest
import json
from pathlib import Path

from experiments.epistemic_readiness import (
    ActionProposal,
    BaselineMetrics,
    BlastRadiusDeclaration,
    DecisionTaxonomyConformanceCase,
    DecisionTaxonomyConformanceReport,
    HandoffStressMatrixReport,
    HumanDecisionTaxonomyReport,
    OperatorEvidenceChainCloseoutInput,
    OperatorEvidenceChainCloseoutReport,
    OperatorEvidenceBundleInput,
    OperatorEvidenceBundleReport,
    OperatorEvidenceBundleStressMatrixReport,
    OperatorEvidenceBundleStressScenario,
    OperatorEvidenceFinalReviewIndexReport,
    OperatorEvidenceFinalReviewIndexStressArtifactCheck,
    OperatorEvidenceFinalReviewIndexStressMatrixReport,
    OperatorEvidenceFinalReviewIndexStressReproducibilityReport,
    OperatorEvidenceFinalReviewIndexStressScenario,
    OperatorEvidenceFinalReviewInput,
    OperatorEvidenceIntakeArtifact,
    OperatorEvidenceIntakeInput,
    OperatorEvidenceIntakeManifest,
    OperatorEvidenceProvenanceArtifactSpec,
    OperatorEvidenceProvenanceIndexReport,
    OperatorEvidenceProvenanceStressMatrixReport,
    OperatorEvidenceReviewCapsule,
    OperatorEvidenceReviewCapsuleArtifactCheck,
    OperatorEvidenceReviewCapsuleReproducibilityReport,
    OperatorEvidenceReviewCapsuleStressMatrixReport,
    OperatorEvidenceIntakeReproducibilityReport,
    OperatorEvidenceIntakeReport,
    OperatorEvidenceIntakeStressMatrixReport,
    OperatorEvidenceIntakeStressScenario,
    OperatorPacketStressMatrixReport,
    OperatorPacketStressScenario,
    ReplayBundlePaths,
    RiskBudget,
    SourceManifestEntry,
    audit_protocol_from_trace_diff,
    build_decision_trace,
    build_replay_bundle,
    compare_decision_traces,
    evaluate_baseline_lifecycle,
    evaluate_decision_taxonomy_conformance,
    evaluate_drift_policy,
    evaluate_metacognitive_handoff,
    evaluate_risk_budget,
    generate_readiness_report,
    generate_readiness_report_from_manifest,
    build_handoff_stress_matrix,
    build_human_decision_taxonomy,
    build_operator_decision_packet,
    build_operator_evidence_chain_closeout,
    build_operator_evidence_bundle,
    build_operator_evidence_bundle_stress_matrix,
    build_operator_evidence_final_review_index,
    build_operator_evidence_final_review_index_stress_matrix,
    build_operator_evidence_intake_report,
    build_operator_evidence_intake_report_from_manifest,
    build_operator_evidence_intake_stress_matrix,
    build_operator_evidence_provenance_index,
    build_operator_evidence_provenance_stress_matrix,
    build_operator_evidence_review_capsule,
    build_operator_evidence_review_capsule_stress_matrix,
    build_operator_packet_stress_matrix,
    check_operator_evidence_intake_reproducibility,
    check_operator_evidence_final_review_index_stress_reproducibility,
    check_operator_evidence_review_capsule_reproducibility,
    interpret_handoff_decision,
    load_decision_trace_json,
    load_operator_evidence_intake_manifest,
    load_readiness_manifest,
    load_trace_diff_json,
    render_decision_trace_json,
    render_decision_taxonomy_conformance_json,
    render_decision_taxonomy_conformance_markdown,
    render_baseline_lifecycle_json,
    render_baseline_lifecycle_markdown,
    render_drift_policy_json,
    render_drift_policy_markdown,
    render_handoff_stress_matrix_json,
    render_handoff_stress_matrix_markdown,
    render_human_decision_taxonomy_json,
    render_human_decision_taxonomy_markdown,
    render_metacognitive_handoff_json,
    render_metacognitive_handoff_markdown,
    render_operator_decision_packet_json,
    render_operator_decision_packet_markdown,
    render_operator_evidence_chain_closeout_json,
    render_operator_evidence_chain_closeout_markdown,
    render_operator_evidence_bundle_json,
    render_operator_evidence_bundle_markdown,
    render_operator_evidence_bundle_stress_matrix_json,
    render_operator_evidence_bundle_stress_matrix_markdown,
    render_operator_evidence_final_review_index_json,
    render_operator_evidence_final_review_index_markdown,
    render_operator_evidence_final_review_index_stress_matrix_json,
    render_operator_evidence_final_review_index_stress_matrix_markdown,
    render_operator_evidence_final_review_index_stress_reproducibility_json,
    render_operator_evidence_final_review_index_stress_reproducibility_markdown,
    render_operator_evidence_intake_report_json,
    render_operator_evidence_intake_report_markdown,
    render_operator_evidence_intake_reproducibility_json,
    render_operator_evidence_intake_reproducibility_markdown,
    render_operator_evidence_provenance_index_json,
    render_operator_evidence_provenance_index_markdown,
    render_operator_evidence_provenance_stress_matrix_json,
    render_operator_evidence_provenance_stress_matrix_markdown,
    render_operator_evidence_review_capsule_json,
    render_operator_evidence_review_capsule_markdown,
    render_operator_evidence_review_capsule_reproducibility_json,
    render_operator_evidence_review_capsule_reproducibility_markdown,
    render_operator_evidence_review_capsule_stress_matrix_json,
    render_operator_evidence_review_capsule_stress_matrix_markdown,
    render_operator_evidence_intake_stress_matrix_json,
    render_operator_evidence_intake_stress_matrix_markdown,
    render_operator_packet_stress_matrix_json,
    render_operator_packet_stress_matrix_markdown,
    render_protocol_self_audit_json,
    render_protocol_self_audit_markdown,
    render_readiness_markdown,
    render_trace_diff_json,
    render_trace_diff_markdown,
    resolve_generated_report_path,
    resolve_generated_trace_path,
    write_replay_bundle,
)


def _minimal_trace_payload() -> dict:
    return {
        "schema_version": "1",
        "state_change": "none",
        "authority": "non-authoritative; advisory trace evidence only",
        "trace_role": "advisory replay evidence only",
        "manifest": {
            "path": "manifest.toml",
            "schema_version": "1",
            "generated_report": "report.md",
            "generated_trace": "trace.json",
            "generator": "test",
            "renderer": "test",
            "trigger": "FORMAL_RESUME_TRIGGER_TEST",
            "source_count": 1,
            "action_id": "test-action",
        },
        "summary": {
            "action_readiness": "derived_experiment_allowed",
            "source_count": 1,
            "candidates_extracted": 1,
            "findings_evaluated": 1,
            "ready_count": 1,
            "blocked_count": 0,
            "insufficient_count": 0,
        },
        "guardrails": {
            "registered_is_not_true": True,
            "retrieved_is_not_relevant": True,
            "remembered_is_not_trusted": True,
            "silence_is_not_negative_evidence": True,
            "report_readiness_is_not_permission": True,
            "risk_readiness_is_not_permission": True,
            "trace_presence_is_not_permission": True,
            "manifest_presence_is_not_permission": True,
        },
        "source_reads": [
            {
                "path": "a.md",
                "role": "primary",
                "requested_max_lines": 80,
                "lines_read": 2,
                "bytes_read": 20,
                "truncated": False,
            }
        ],
        "candidates": [
            {
                "claim_id": "claim-1",
                "source_path": "a.md",
                "evidence_span": "line 1",
                "subject": "schema",
                "predicate": "exists",
                "object": "yes",
                "polarity": "positive",
                "modality": "asserted",
                "criticality_hint": "medium",
                "source_role": "primary",
                "authority_hint": "canonical",
                "extraction_basis": "fixture",
            }
        ],
        "findings": [
            {
                "claim_id": "claim-1",
                "authority": "canonical",
                "confidence": "high",
                "sufficiency": "sufficient",
                "conflict": "none",
                "supersession": "none",
                "staleness": "fresh",
                "operational_readiness": "ready",
                "reasons": ["test"],
            }
        ],
        "risk_assessment": {
            "action_id": "test-action",
            "purpose": "test",
            "zone": "zone_1",
            "risk_score": 1,
            "declared_gate_level": "G2",
            "required_gate_level": "G2",
            "budget_status": "within_budget",
            "budget_violations": [],
            "human_approval_required": False,
            "action_readiness": "derived_experiment_allowed",
            "stop_conditions": [],
            "state_change": "none",
            "authority": "non-authoritative; advisory risk evidence only",
        },
        "boundary": {
            "may_suggest": ["inspect evidence"],
            "must_not_apply": ["mutate state"],
        },
    }


def _minimal_trace_diff_payload() -> dict:
    baseline = _minimal_trace_payload()
    current = json.loads(json.dumps(baseline))
    return compare_decision_traces(baseline, current).to_dict()


def _clean_handoff_payloads() -> tuple[dict, dict, dict, dict]:
    trace = _minimal_trace_payload()
    diff = compare_decision_traces(trace, json.loads(json.dumps(trace)))
    self_audit = audit_protocol_from_trace_diff(diff.to_dict())
    lifecycle = evaluate_baseline_lifecycle(trace, trace, diff.to_dict(), self_audit.to_dict())
    drift_policy = evaluate_drift_policy(diff.to_dict(), self_audit.to_dict(), lifecycle.to_dict())
    return trace, lifecycle.to_dict(), self_audit.to_dict(), drift_policy.to_dict()


def _write_replay_manifest(root: Path) -> Path:
    manifest_path = root / "manifest.toml"
    manifest_path.write_text(
        """
schema_version = "1"
generated_report = "derived/report.md"
generated_trace = "derived/trace.json"
generator = "experiments.epistemic_readiness.generate_readiness_report_from_manifest"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"
""".lstrip(),
        encoding="utf-8",
    )
    return manifest_path


class EpistemicReadinessTests(unittest.TestCase):
    def test_generates_report_from_bounded_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            state = root / "SYSTEM_STATE.md"
            state.write_text(
                "\n".join(
                    [
                        "Current posture: deliberate freeze for canonical-runtime growth remains active.",
                        "Current boundary: no Cerebro runtime boundary is open.",
                        "The Supabase schema already exists.",
                    ]
                ),
                encoding="utf-8",
            )

            report = generate_readiness_report(
                root,
                [SourceManifestEntry("SYSTEM_STATE.md", max_lines=2)],
            )

            subjects = {candidate.subject for candidate in report.candidates}
            self.assertIn("canonical-runtime growth", subjects)
            self.assertIn("Cerebro runtime boundary", subjects)
            self.assertNotIn("Supabase schema", subjects)
            self.assertEqual(report.source_reads[0].lines_read, 2)
            self.assertEqual(report.state_change, "none")

    def test_runs_extraction_and_evaluation_to_advisory_readiness(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "continuity.md").write_text(
                "The Supabase schema already exists.\n"
                "The next step is validating Edge Functions against the existing schema.\n",
                encoding="utf-8",
            )

            report = generate_readiness_report(root, [SourceManifestEntry("continuity.md")])

            self.assertEqual(report.candidate_count, 2)
            self.assertEqual(report.finding_count, 2)
            self.assertEqual(report.blocked_count, 0)
            self.assertEqual(report.action_readiness, "advisory_report_allowed")

    def test_unknown_or_absence_findings_require_human_review(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Third-party pilot remains waiting for explicit human go/no-go.\n",
                encoding="utf-8",
            )

            report = generate_readiness_report(root, [SourceManifestEntry("SYSTEM_STATE.md")])

            self.assertEqual(report.blocked_count, 1)
            self.assertEqual(report.action_readiness, "human_approval_required")

    def test_renderer_exposes_guardrails_baseline_and_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )

            report = generate_readiness_report(
                root,
                [SourceManifestEntry("SYSTEM_STATE.md")],
                baseline=BaselineMetrics(
                    candidates_extracted=0,
                    findings_evaluated=0,
                    ready_count=0,
                    blocked_count=0,
                    insufficient_count=0,
                    label="previous",
                ),
            )
            rendered = render_readiness_markdown(report)

            self.assertIn("# Epistemic Readiness Report", rendered)
            self.assertIn("- state_change: none", rendered)
            self.assertIn("- registered_is_not_true: true", rendered)
            self.assertIn("- retrieved_is_not_relevant: true", rendered)
            self.assertIn("- remembered_is_not_trusted: true", rendered)
            self.assertIn("- silence_is_not_negative_evidence: true", rendered)
            self.assertIn("## Baseline Comparison", rendered)
            self.assertIn("- report_readiness_is_not_permission: true", rendered)
            self.assertIn("must_not_apply", rendered)

    def test_rejects_cerebro_state_and_root_escape_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / ".cerebro").mkdir()
            (root / ".cerebro" / "state.json").write_text("{}", encoding="utf-8")
            outside = root.parent / "outside-readiness-source.md"
            outside.write_text("Current boundary: no Cerebro runtime boundary is open.\n", encoding="utf-8")
            try:
                with self.assertRaises(ValueError):
                    generate_readiness_report(root, [SourceManifestEntry(".cerebro/state.json")])
                with self.assertRaises(ValueError):
                    generate_readiness_report(root, [SourceManifestEntry(str(outside))])
            finally:
                outside.unlink(missing_ok=True)

    def test_report_generation_does_not_mutate_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }

            report = generate_readiness_report(root, [SourceManifestEntry("SYSTEM_STATE.md")])

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
            self.assertEqual(report.state_change, "none")
            self.assertEqual(before, after)

    def test_manifest_limits_are_enforced(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "a.md").write_text("", encoding="utf-8")

            with self.assertRaises(ValueError):
                SourceManifestEntry("a.md", max_lines=0)
            with self.assertRaises(ValueError):
                SourceManifestEntry("a.md", max_lines=201)
            with self.assertRaises(ValueError):
                generate_readiness_report(root, [SourceManifestEntry("a.md")] * 25)

    def test_reversible_derived_experiment_is_allowed_as_derived_only(self) -> None:
        proposal = ActionProposal(
            action_id="risk-slice-2",
            purpose="add read-only risk evidence to epistemic_readiness",
            zone="zone_1",
            uncertainty="low",
            blast_radius=BlastRadiusDeclaration(
                reads=("docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md",),
                authority_impact="advisory",
                scope="local",
                reversibility="high",
                rollback="git-revert",
                gate_level="G2",
            ),
            risk_budget=RiskBudget(
                max_writes=0,
                allowed_authority_impact="advisory",
                allowed_runtime_impact="none",
                max_irreversibility="low",
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.required_gate_level, "G2")
        self.assertEqual(assessment.action_readiness, "derived_experiment_allowed")
        self.assertEqual(assessment.budget_status, "within_budget")
        self.assertFalse(assessment.human_approval_required)
        self.assertEqual(assessment.state_change, "none")

    def test_docs_historical_rewrite_can_escalate_to_human_review(self) -> None:
        proposal = ActionProposal(
            action_id="rewrite-phase-closure-rationale",
            purpose="rewrite historical decision rationale in closure docs",
            zone="zone_0",
            uncertainty="medium",
            blast_radius=BlastRadiusDeclaration(
                writes=("docs/operations/PHASE_CLOSURE.md",),
                authority_impact="advisory",
                scope="project",
                reversibility="medium",
                rollback="manual-reconstruction",
                gate_level="G1",
                stop_conditions=("historical decision rationale changes",),
            ),
            risk_budget=RiskBudget(
                max_writes=1,
                allowed_paths=("docs/operations",),
                allowed_authority_impact="advisory",
                allowed_runtime_impact="none",
                max_irreversibility="medium",
                required_rollback_evidence="manual-proof",
                human_approval_required=True,
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.required_gate_level, "G2")
        self.assertEqual(assessment.action_readiness, "human_approval_required")
        self.assertIn("historical decision rationale changes", assessment.stop_conditions)

    def test_canonical_runtime_schema_change_requires_g4_trigger(self) -> None:
        proposal = ActionProposal(
            action_id="schema-authority-change",
            purpose="change canonical state schema",
            zone="zone_3",
            uncertainty="medium",
            blast_radius=BlastRadiusDeclaration(
                writes=("core/schema.py",),
                authority_impact="canonical",
                runtime_impact="direct",
                state_impact="canonical-mutation",
                scope="project",
                reversibility="low",
                rollback="git-revert",
                gate_level="G4",
                promotion_path="requires-human-approval",
            ),
            risk_budget=RiskBudget(
                max_writes=1,
                allowed_paths=("core/schema.py",),
                allowed_authority_impact="canonical",
                allowed_runtime_impact="direct",
                max_irreversibility="high",
                required_rollback_evidence="git-revert",
                human_approval_required=True,
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.required_gate_level, "G4")
        self.assertEqual(assessment.action_readiness, "canonical_change_requires_trigger")
        self.assertTrue(assessment.human_approval_required)
        self.assertIn("canonical change requires separate formal trigger", assessment.stop_conditions)

    def test_high_uncertainty_broad_noncanonical_action_blocks(self) -> None:
        proposal = ActionProposal(
            action_id="broad-provisional-import",
            purpose="use uncertain evidence across projects",
            zone="zone_1",
            uncertainty="unknown",
            blast_radius=BlastRadiusDeclaration(
                reads=("project-a", "project-b", "project-c"),
                authority_impact="provisional",
                scope="external",
                reversibility="low",
                rollback="manual-reconstruction",
                gate_level="G2",
            ),
            risk_budget=RiskBudget(
                max_writes=0,
                allowed_authority_impact="provisional",
                allowed_runtime_impact="none",
                max_irreversibility="high",
                required_rollback_evidence="manual-proof",
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.action_readiness, "blocked")
        self.assertEqual(assessment.budget_status, "within_budget")
        self.assertIn("uncertainty too high for declared blast radius", assessment.stop_conditions)

    def test_budget_overrun_blocks_even_when_action_is_otherwise_reversible(self) -> None:
        proposal = ActionProposal(
            action_id="too-many-doc-writes",
            purpose="write more docs than declared",
            zone="zone_0",
            uncertainty="low",
            blast_radius=BlastRadiusDeclaration(
                writes=("docs/operations/A.md", "docs/operations/B.md"),
                authority_impact="advisory",
                scope="local",
                reversibility="high",
                rollback="git-revert",
                gate_level="G1",
            ),
            risk_budget=RiskBudget(
                max_writes=1,
                allowed_paths=("docs/operations",),
                allowed_authority_impact="advisory",
                allowed_runtime_impact="none",
                max_irreversibility="low",
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.action_readiness, "blocked")
        self.assertEqual(assessment.budget_status, "exceeded")
        self.assertIn("writes exceed budget: 2 > 1", assessment.budget_violations)

    def test_missing_required_rollback_evidence_blocks(self) -> None:
        proposal = ActionProposal(
            action_id="manual-unrollbackable-edit",
            purpose="perform action without required rollback evidence",
            zone="zone_0",
            uncertainty="low",
            blast_radius=BlastRadiusDeclaration(
                writes=("docs/operations/SYSTEM_STATE.md",),
                authority_impact="advisory",
                scope="local",
                reversibility="none",
                rollback="not-reversible",
                gate_level="G1",
            ),
            risk_budget=RiskBudget(
                max_writes=1,
                allowed_paths=("docs/operations",),
                allowed_authority_impact="advisory",
                allowed_runtime_impact="none",
                max_irreversibility="none",
                required_rollback_evidence="git-revert",
            ),
        )

        assessment = evaluate_risk_budget(proposal)

        self.assertEqual(assessment.action_readiness, "blocked")
        self.assertIn(
            "rollback evidence missing: required git-revert, declared not-reversible",
            assessment.budget_violations,
        )

    def test_report_integrates_and_renders_risk_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            proposal = ActionProposal(
                action_id="risk-render",
                purpose="render advisory risk evidence",
                zone="zone_1",
                uncertainty="low",
                blast_radius=BlastRadiusDeclaration(
                    reads=("SYSTEM_STATE.md",),
                    authority_impact="advisory",
                    scope="local",
                    reversibility="high",
                    rollback="git-revert",
                    gate_level="G2",
                ),
                risk_budget=RiskBudget(
                    max_writes=0,
                    allowed_authority_impact="advisory",
                    allowed_runtime_impact="none",
                    max_irreversibility="low",
                ),
            )

            report = generate_readiness_report(
                root,
                [SourceManifestEntry("SYSTEM_STATE.md")],
                action_proposal=proposal,
            )
            rendered = render_readiness_markdown(report)

            self.assertEqual(report.action_readiness, "derived_experiment_allowed")
            self.assertIsNotNone(report.risk_assessment)
            self.assertIn("## Risk Budget Assessment", rendered)
            self.assertIn("- action_id: `risk-render`", rendered)
            self.assertIn("- required_gate_level: `G2`", rendered)
            self.assertIn("- report_readiness_is_not_permission: true", rendered)

    def test_loads_manifest_with_action_proposal_and_generates_risk_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = root / "manifest.toml"
            manifest_path.write_text(
                """
schema_version = "1"
generated_report = "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md"
generator = "experiments.epistemic_readiness.generate_readiness_report"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[baseline]
label = "test"
candidates_extracted = 0
findings_evaluated = 0
ready_count = 0
blocked_count = 0
insufficient_count = 0

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"

[action]
action_id = "manifest-rerun"
purpose = "regenerate an advisory readiness report"
zone = "zone_1"
uncertainty = "low"

[action.blast_radius]
writes = ["docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md"]
reads = ["SYSTEM_STATE.md"]
authority_impact = "advisory"
runtime_impact = "none"
state_impact = "derived-output"
third_party_impact = "none"
scope = "local"
reversibility = "high"
rollback = "git-revert"
gate_level = "G2"
promotion_path = "requires-trigger"
stop_conditions = ["report readiness is treated as permission"]

[action.risk_budget]
max_writes = 1
allowed_paths = ["docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md"]
allowed_authority_impact = "advisory"
allowed_runtime_impact = "none"
max_irreversibility = "low"
required_rollback_evidence = "git-revert"
human_approval_required = false
""".lstrip(),
                encoding="utf-8",
            )

            manifest = load_readiness_manifest(manifest_path)
            report = generate_readiness_report_from_manifest(root, manifest_path)
            rendered = render_readiness_markdown(report)

            self.assertEqual(manifest.trigger, "FORMAL_RESUME_TRIGGER_TEST")
            self.assertEqual(report.action_readiness, "derived_experiment_allowed")
            self.assertIsNotNone(report.risk_assessment)
            self.assertEqual(report.risk_assessment.budget_status, "within_budget")
            self.assertIn("## Risk Budget Assessment", rendered)
            self.assertIn("- action_id: `manifest-rerun`", rendered)

    def test_manifest_loader_rejects_state_change_and_missing_action_sections(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest_path = root / "manifest.toml"
            manifest_path.write_text(
                """
schema_version = "1"
generated_report = "report.md"
generator = "experiments.epistemic_readiness.generate_readiness_report"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "canonical-mutation"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"
""".lstrip(),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_readiness_manifest(manifest_path)

            manifest_path.write_text(
                """
schema_version = "1"
generated_report = "report.md"
generator = "experiments.epistemic_readiness.generate_readiness_report"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"

[action]
action_id = "missing-sections"
purpose = "invalid manifest"
zone = "zone_1"
uncertainty = "low"
""".lstrip(),
                encoding="utf-8",
            )

            with self.assertRaises(ValueError):
                load_readiness_manifest(manifest_path)

    def test_generated_report_path_rejects_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            base = """
schema_version = "1"
generated_report = "{generated_report}"
generator = "experiments.epistemic_readiness.generate_readiness_report"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"
"""
            manifest_path = root / "manifest.toml"

            manifest_path.write_text(base.format(generated_report="../outside.md").lstrip(), encoding="utf-8")
            with self.assertRaises(ValueError):
                resolve_generated_report_path(root, load_readiness_manifest(manifest_path))

            manifest_path.write_text(
                base.format(generated_report=".cerebro/readiness.md").lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                resolve_generated_report_path(root, load_readiness_manifest(manifest_path))

    def test_builds_decision_trace_from_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = root / "manifest.toml"
            manifest_path.write_text(
                """
schema_version = "1"
generated_report = "docs/operations/readiness.md"
generated_trace = "docs/operations/readiness_trace.json"
generator = "experiments.epistemic_readiness.generate_readiness_report_from_manifest"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"

[action]
action_id = "trace-rerun"
purpose = "regenerate advisory report and trace"
zone = "zone_1"
uncertainty = "low"

[action.blast_radius]
writes = ["docs/operations/readiness.md", "docs/operations/readiness_trace.json"]
reads = ["SYSTEM_STATE.md", "manifest.toml"]
authority_impact = "advisory"
runtime_impact = "none"
state_impact = "derived-output"
third_party_impact = "none"
scope = "local"
reversibility = "high"
rollback = "git-revert"
gate_level = "G2"
promotion_path = "requires-trigger"
stop_conditions = ["trace is treated as permission"]

[action.risk_budget]
max_writes = 2
allowed_paths = ["docs/operations/readiness.md", "docs/operations/readiness_trace.json"]
allowed_authority_impact = "advisory"
allowed_runtime_impact = "none"
max_irreversibility = "low"
required_rollback_evidence = "git-revert"
human_approval_required = false
""".lstrip(),
                encoding="utf-8",
            )

            trace = build_decision_trace(root, manifest_path)
            payload = trace.to_dict()
            rendered = render_decision_trace_json(trace)
            parsed = json.loads(rendered)

            self.assertEqual(payload["state_change"], "none")
            self.assertEqual(payload["manifest"]["generated_trace"], "docs/operations/readiness_trace.json")
            self.assertEqual(payload["summary"]["action_readiness"], "derived_experiment_allowed")
            self.assertEqual(payload["summary"]["candidates_extracted"], 1)
            self.assertEqual(payload["risk_assessment"]["action_id"], "trace-rerun")
            self.assertEqual(payload["risk_assessment"]["budget_status"], "within_budget")
            self.assertTrue(payload["guardrails"]["trace_presence_is_not_permission"])
            self.assertTrue(payload["guardrails"]["report_readiness_is_not_permission"])
            self.assertEqual(len(payload["candidates"]), 1)
            self.assertEqual(payload["candidates"][0]["claim_id"], payload["findings"][0]["claim_id"])
            self.assertTrue(payload["candidates"][0]["semantic_id"])
            self.assertTrue(payload["candidates"][0]["evidence_id"])
            self.assertEqual(payload["candidates"][0]["semantic_id"], payload["findings"][0]["semantic_id"])
            self.assertEqual(payload["candidates"][0]["evidence_id"], payload["findings"][0]["evidence_id"])
            self.assertEqual(parsed, payload)

    def test_generated_trace_path_rejects_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            base = """
schema_version = "1"
generated_report = "report.md"
generated_trace = "{generated_trace}"
generator = "experiments.epistemic_readiness.generate_readiness_report_from_manifest"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"
"""
            manifest_path = root / "manifest.toml"

            manifest_path.write_text(base.format(generated_trace="../outside.json").lstrip(), encoding="utf-8")
            with self.assertRaises(ValueError):
                resolve_generated_trace_path(root, load_readiness_manifest(manifest_path))

            manifest_path.write_text(
                base.format(generated_trace=".cerebro/readiness_trace.json").lstrip(),
                encoding="utf-8",
            )
            with self.assertRaises(ValueError):
                resolve_generated_trace_path(root, load_readiness_manifest(manifest_path))

    def test_decision_trace_generation_does_not_mutate_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = root / "manifest.toml"
            manifest_path.write_text(
                """
schema_version = "1"
generated_report = "readiness.md"
generated_trace = "readiness_trace.json"
generator = "experiments.epistemic_readiness.generate_readiness_report_from_manifest"
renderer = "experiments.epistemic_readiness.render_readiness_markdown"
authority = "non-authoritative; advisory evidence only"
state_change = "none"
trigger = "FORMAL_RESUME_TRIGGER_TEST"

[[source]]
path = "SYSTEM_STATE.md"
max_lines = 80
source_role = "primary"
""".lstrip(),
                encoding="utf-8",
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }

            trace = build_decision_trace(root, manifest_path)

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
            self.assertEqual(trace.state_change, "none")
            self.assertEqual(before, after)

    def test_trace_diff_detects_added_removed_and_changed_entries(self) -> None:
        baseline = _minimal_trace_payload()
        baseline["candidates"].append(
            {**baseline["candidates"][0], "claim_id": "claim-old", "subject": "old claim"}
        )
        baseline["findings"].append({**baseline["findings"][0], "claim_id": "claim-old"})
        current = json.loads(json.dumps(baseline))
        current["source_reads"].append(
            {
                "path": "b.md",
                "role": "secondary",
                "requested_max_lines": 40,
                "lines_read": 1,
                "bytes_read": 10,
                "truncated": False,
            }
        )
        current["candidates"] = [
            {**current["candidates"][0], "evidence_span": "line 2"},
            {**current["candidates"][0], "claim_id": "claim-new", "subject": "new claim"},
        ]
        current["findings"] = [
            {**current["findings"][0], "confidence": "medium"},
            {**current["findings"][0], "claim_id": "claim-new"},
        ]

        diff = compare_decision_traces(baseline, current, baseline_label="before", current_label="after")

        self.assertEqual(diff.state_change, "none")
        self.assertIn("b.md", diff.source_reads.added)
        self.assertTrue(any("new claim" in key for key in diff.candidates.added))
        self.assertTrue(any("old claim" in key for key in diff.candidates.removed))
        self.assertEqual(diff.candidates.identity_basis, "candidate_semantic_identity")
        self.assertFalse(any("evidence_span" in change.changed_fields for change in diff.candidates.changed))
        self.assertTrue(
            any("evidence_span" in change.changed_fields for change in diff.candidates.traceability_changed)
        )
        self.assertTrue(any("confidence" in change.changed_fields for change in diff.findings.changed))
        self.assertFalse(diff.has_regression)

    def test_trace_diff_separates_semantic_identity_from_traceability_drift(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["candidates"][0]["claim_id"] = "claim-moved"
        current["candidates"][0]["evidence_span"] = "line 99"
        current["candidates"][0]["evidence_id"] = "evidence-moved"
        current["findings"][0]["claim_id"] = "claim-moved"
        current["findings"][0]["evidence_id"] = "evidence-moved"

        diff = compare_decision_traces(baseline, current)
        parsed = json.loads(render_trace_diff_json(diff))
        rendered = render_trace_diff_markdown(diff)

        self.assertEqual(diff.candidates.added, ())
        self.assertEqual(diff.candidates.removed, ())
        self.assertEqual(diff.candidates.changed, ())
        self.assertEqual(len(diff.candidates.traceability_changed), 1)
        self.assertEqual(len(diff.findings.traceability_changed), 1)
        self.assertIn("traceability_changed", parsed["candidates"])
        self.assertIn("- traceability_changed: `1`", rendered)

    def test_trace_diff_flags_advisory_readiness_regression_without_authority(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["summary"]["blocked_count"] = 1
        current["summary"]["action_readiness"] = "human_approval_required"
        current["risk_assessment"]["required_gate_level"] = "G3"
        current["risk_assessment"]["human_approval_required"] = True
        current["risk_assessment"]["action_readiness"] = "human_approval_required"

        diff = compare_decision_traces(baseline, current)

        self.assertTrue(diff.has_regression)
        self.assertEqual(diff.advisory_readiness, "human_review_recommended")
        self.assertIn("blocked_count increased: 0 -> 1", diff.regression_reasons)
        self.assertIn(
            "action_readiness worsened: derived_experiment_allowed -> human_approval_required",
            diff.regression_reasons,
        )
        self.assertEqual(diff.authority, "non-authoritative; advisory trace-diff evidence only")

    def test_trace_diff_json_and_markdown_are_advisory_only(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        diff = compare_decision_traces(baseline, current)
        parsed = json.loads(render_trace_diff_json(diff))
        rendered = render_trace_diff_markdown(diff)

        self.assertEqual(parsed["state_change"], "none")
        self.assertEqual(parsed["advisory_readiness"], "no_regression_observed")
        self.assertIn("treat trace diff as permission", parsed["boundary"]["must_not_apply"])
        self.assertIn("- trace_diff_is_not_permission: true", rendered)
        self.assertIn("- promotion_or_demotion_is_not_applied: true", rendered)
        self.assertIn("- treat trace diff as permission", rendered)

    def test_load_decision_trace_json_rejects_mutating_or_non_object_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            trace_path = root / "trace.json"

            trace_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_decision_trace_json(trace_path)

            payload = _minimal_trace_payload()
            payload["state_change"] = "canonical-mutation"
            trace_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_decision_trace_json(trace_path)

            payload = _minimal_trace_payload()
            payload["schema_version"] = "999"
            trace_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_decision_trace_json(trace_path)

    def test_protocol_self_audit_flags_regression_guardrail_and_risk_candidates(self) -> None:
        payload = _minimal_trace_diff_payload()
        payload["has_regression"] = True
        payload["regression_reasons"] = ["blocked_count increased: 0 -> 1"]
        payload["risk_assessment_changes"] = [
            {"field": "budget_status", "baseline": "within_budget", "current": "exceeded"},
            {"field": "human_approval_required", "baseline": False, "current": True},
        ]
        payload["guardrail_changes"] = [
            {"field": "trace_presence_is_not_permission", "baseline": True, "current": False}
        ]

        report = audit_protocol_from_trace_diff(payload)
        categories = {candidate.category for candidate in report.candidates}

        self.assertEqual(report.state_change, "none")
        self.assertEqual(report.action_readiness, "human_review_recommended")
        self.assertIn("readiness_regression", categories)
        self.assertIn("risk_budget_degradation", categories)
        self.assertIn("risk_review_escalation", categories)
        self.assertIn("guardrail_weakening", categories)
        self.assertGreaterEqual(report.high_or_blocking_count, 3)

    def test_protocol_self_audit_flags_traceability_drift_and_source_drift_without_authority(self) -> None:
        payload = _minimal_trace_diff_payload()
        payload["source_reads"]["added"] = ["new.md"]
        payload["source_reads"]["changed"] = [{"key": "a.md", "changed_fields": ["bytes_read"]}]
        payload["candidates"]["traceability_changed"] = [
            {"key": f"claim-{index}", "changed_fields": ["claim_id", "evidence_span"]}
            for index in range(6)
        ]
        payload["findings"]["traceability_changed"] = [
            {"key": f"claim-{index}", "changed_fields": ["claim_id"]}
            for index in range(6)
        ]

        report = audit_protocol_from_trace_diff(payload, churn_threshold=10)
        rendered = render_protocol_self_audit_markdown(report)
        parsed = json.loads(render_protocol_self_audit_json(report))
        categories = {candidate.category for candidate in report.candidates}

        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertIn("evidence_traceability_drift", categories)
        self.assertNotIn("evidence_identity_churn", categories)
        self.assertIn("source_surface_drift", categories)
        self.assertEqual(parsed["state_change"], "none")
        self.assertTrue(parsed["guardrails"]["anti_noise_no_auto_learning"])
        self.assertIn("- self_audit_is_not_memory: true", rendered)
        self.assertIn("- write memory automatically", rendered)

    def test_protocol_self_audit_rejects_mutating_or_weak_trace_diff_payloads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            diff_path = root / "diff.json"

            diff_path.write_text(json.dumps(["not", "object"]), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_trace_diff_json(diff_path)

            payload = _minimal_trace_diff_payload()
            payload["state_change"] = "canonical-mutation"
            diff_path.write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaises(ValueError):
                load_trace_diff_json(diff_path)

            payload = _minimal_trace_diff_payload()
            payload["boundary"]["must_not_apply"] = ["mutate state"]
            report = audit_protocol_from_trace_diff(payload)

            self.assertEqual(report.action_readiness, "human_review_recommended")
            self.assertIn("anti_permission_boundary_weak", {candidate.category for candidate in report.candidates})

    def test_baseline_lifecycle_proposes_refresh_candidate_without_applying_it(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["source_reads"].append(
            {
                "path": "new-source.md",
                "role": "secondary",
                "requested_max_lines": 40,
                "lines_read": 1,
                "bytes_read": 8,
                "truncated": False,
            }
        )
        diff = compare_decision_traces(
            baseline,
            current,
            baseline_label="slice-7",
            current_label="slice-8",
        )
        self_audit = audit_protocol_from_trace_diff(diff.to_dict()).to_dict()

        report = evaluate_baseline_lifecycle(
            baseline,
            current,
            diff.to_dict(),
            self_audit,
            baseline_label="slice-7",
            current_label="slice-8",
        )
        parsed = json.loads(render_baseline_lifecycle_json(report))
        rendered = render_baseline_lifecycle_markdown(report)

        self.assertEqual(report.state_change, "none")
        self.assertEqual(report.recommendation, "refresh_candidate_requires_human_approval")
        self.assertEqual(report.required_human_action, "approve_baseline_refresh")
        self.assertEqual(report.action_readiness, "human_approval_required")
        self.assertEqual(report.source_drift.added, 1)
        self.assertEqual(report.self_audit_high_or_blocking_count, 0)
        self.assertTrue(parsed["guardrails"]["baseline_refresh_is_not_automatic"])
        self.assertIn("overwrite baseline automatically", parsed["boundary"]["must_not_apply"])
        self.assertIn("- baseline_refresh_is_not_automatic: true", rendered)

    def test_baseline_lifecycle_blocks_regression_or_high_self_audit(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["summary"]["blocked_count"] = 1
        current["summary"]["action_readiness"] = "human_approval_required"
        current["risk_assessment"]["action_readiness"] = "human_approval_required"
        current["risk_assessment"]["human_approval_required"] = True
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict()).to_dict()

        report = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit)

        self.assertEqual(report.recommendation, "refresh_blocked")
        self.assertEqual(report.required_human_action, "review_blockers")
        self.assertEqual(report.action_readiness, "blocked")
        self.assertTrue(report.has_regression)
        self.assertGreater(report.self_audit_high_or_blocking_count, 0)

    def test_baseline_lifecycle_detects_already_current_baseline(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict()).to_dict()

        report = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit)

        self.assertEqual(report.recommendation, "baseline_already_current")
        self.assertEqual(report.required_human_action, "none")
        self.assertEqual(report.action_readiness, "no_action")
        self.assertEqual(report.drift_total, 0)

    def test_baseline_lifecycle_rejects_mutating_or_malformed_payloads(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        diff = compare_decision_traces(baseline, current).to_dict()
        self_audit = audit_protocol_from_trace_diff(diff).to_dict()

        mutating_trace = json.loads(json.dumps(baseline))
        mutating_trace["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_baseline_lifecycle(mutating_trace, current, diff, self_audit)

        bad_diff = json.loads(json.dumps(diff))
        bad_diff["authority"] = "canonical"
        with self.assertRaises(ValueError):
            evaluate_baseline_lifecycle(baseline, current, bad_diff, self_audit)

        bad_audit = json.loads(json.dumps(self_audit))
        bad_audit["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_baseline_lifecycle(baseline, current, diff, bad_audit)

    def test_baseline_lifecycle_does_not_write_baseline_automatically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(json.dumps(_minimal_trace_payload()), encoding="utf-8")
            before = baseline_path.read_text(encoding="utf-8")
            baseline = json.loads(before)
            current = json.loads(json.dumps(baseline))
            current["source_reads"].append(
                {
                    "path": "new-source.md",
                    "role": "secondary",
                    "requested_max_lines": 40,
                    "lines_read": 1,
                    "bytes_read": 8,
                    "truncated": False,
                }
            )
            diff = compare_decision_traces(baseline, current).to_dict()
            self_audit = audit_protocol_from_trace_diff(diff).to_dict()

            report = evaluate_baseline_lifecycle(baseline, current, diff, self_audit)

            self.assertEqual(report.recommendation, "refresh_candidate_requires_human_approval")
            self.assertEqual(baseline_path.read_text(encoding="utf-8"), before)

    def test_drift_policy_classifies_current_baseline_without_action(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict())
        lifecycle = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit.to_dict())

        report = evaluate_drift_policy(diff.to_dict(), self_audit.to_dict(), lifecycle.to_dict())
        parsed = json.loads(render_drift_policy_json(report))
        rendered = render_drift_policy_markdown(report)

        self.assertEqual(report.classification, "no_drift")
        self.assertEqual(report.recommendation, "no_action")
        self.assertEqual(report.required_human_action, "none")
        self.assertEqual(report.action_readiness, "no_action")
        self.assertEqual(report.drift_total, 0)
        self.assertTrue(parsed["guardrails"]["drift_policy_is_not_permission"])
        self.assertIn("- baseline_refresh_is_not_automatic: true", rendered)

    def test_drift_policy_observes_traceability_only_drift_without_refresh_authority(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["candidates"][0]["claim_id"] = "claim-moved"
        current["candidates"][0]["evidence_id"] = "evidence-moved"
        current["candidates"][0]["evidence_span"] = "line 99"
        current["findings"][0]["claim_id"] = "claim-moved"
        current["findings"][0]["evidence_id"] = "evidence-moved"
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict())
        lifecycle = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit.to_dict())

        report = evaluate_drift_policy(diff.to_dict(), self_audit.to_dict(), lifecycle.to_dict())

        self.assertEqual(report.classification, "traceability_drift_only")
        self.assertEqual(report.recommendation, "observe_traceability_drift")
        self.assertEqual(report.required_human_action, "acknowledge")
        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertEqual(report.semantic_drift_total, 0)
        self.assertGreater(report.traceability_drift_total, 0)

    def test_drift_policy_escalates_semantic_source_or_metadata_drift_to_human_refresh(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["source_reads"].append(
            {
                "path": "new-source.md",
                "role": "secondary",
                "requested_max_lines": 40,
                "lines_read": 1,
                "bytes_read": 8,
                "truncated": False,
            }
        )
        current["candidates"].append(
            {
                "claim_id": "claim-2",
                "source_path": "new-source.md",
                "evidence_span": "line 1",
                "subject": "edge functions",
                "predicate": "ready",
                "object": "no",
                "polarity": "negative",
                "modality": "asserted",
                "criticality_hint": "high",
                "source_role": "secondary",
                "authority_hint": "advisory",
                "extraction_basis": "fixture",
            }
        )
        current["findings"].append(
            {
                "claim_id": "claim-2",
                "authority": "advisory",
                "confidence": "medium",
                "sufficiency": "partial",
                "conflict": "none",
                "supersession": "none",
                "staleness": "fresh",
                "operational_readiness": "needs_review",
                "reasons": ["new evidence"],
            }
        )
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict())
        lifecycle = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit.to_dict())

        report = evaluate_drift_policy(diff.to_dict(), self_audit.to_dict(), lifecycle.to_dict())

        self.assertEqual(report.classification, "material_refresh_candidate")
        self.assertEqual(report.recommendation, "refresh_candidate_requires_human_approval")
        self.assertEqual(report.required_human_action, "approve_baseline_refresh")
        self.assertEqual(report.action_readiness, "human_approval_required")
        self.assertGreater(report.semantic_drift_total, 0)

    def test_drift_policy_blocks_regression_or_high_self_audit(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        current["summary"]["blocked_count"] = 1
        current["summary"]["action_readiness"] = "human_approval_required"
        current["risk_assessment"]["action_readiness"] = "human_approval_required"
        current["risk_assessment"]["human_approval_required"] = True
        diff = compare_decision_traces(baseline, current)
        self_audit = audit_protocol_from_trace_diff(diff.to_dict())
        lifecycle = evaluate_baseline_lifecycle(baseline, current, diff.to_dict(), self_audit.to_dict())

        report = evaluate_drift_policy(diff.to_dict(), self_audit.to_dict(), lifecycle.to_dict())

        self.assertEqual(report.classification, "blocked_regression_or_protocol_risk")
        self.assertEqual(report.recommendation, "refresh_blocked_pending_review")
        self.assertEqual(report.required_human_action, "review_blockers")
        self.assertEqual(report.action_readiness, "blocked")
        self.assertGreater(report.self_audit_high_or_blocking_count, 0)

    def test_drift_policy_rejects_mutating_or_malformed_payloads(self) -> None:
        baseline = _minimal_trace_payload()
        current = json.loads(json.dumps(baseline))
        diff = compare_decision_traces(baseline, current).to_dict()
        self_audit = audit_protocol_from_trace_diff(diff).to_dict()
        lifecycle = evaluate_baseline_lifecycle(baseline, current, diff, self_audit).to_dict()

        bad_diff = json.loads(json.dumps(diff))
        bad_diff["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_drift_policy(bad_diff, self_audit, lifecycle)

        bad_audit = json.loads(json.dumps(self_audit))
        bad_audit["authority"] = "canonical"
        with self.assertRaises(ValueError):
            evaluate_drift_policy(diff, bad_audit, lifecycle)

        bad_lifecycle = json.loads(json.dumps(lifecycle))
        bad_lifecycle["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_drift_policy(diff, self_audit, bad_lifecycle)

    def test_replay_bundle_builds_full_advisory_bundle_without_writes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = _write_replay_manifest(root)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(
                render_decision_trace_json(build_decision_trace(root, manifest_path)),
                encoding="utf-8",
            )
            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }

            bundle = build_replay_bundle(
                root,
                manifest_path,
                baseline_path,
                baseline_label="accepted",
                current_label="rerun",
            )

            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
            summary = bundle.to_dict()["summary"]
            self.assertEqual(before, after)
            self.assertEqual(bundle.state_change, "none")
            self.assertEqual(bundle.trace_diff.has_regression, False)
            self.assertEqual(bundle.baseline_lifecycle.recommendation, "baseline_already_current")
            self.assertEqual(bundle.drift_policy.classification, "no_drift")
            self.assertEqual(summary["baseline_lifecycle_drift_total"], 0)
            self.assertEqual(summary["drift_policy_action_readiness"], "no_action")
            self.assertIn("update baseline automatically", bundle.to_dict()["boundary"]["must_not_apply"])

    def test_replay_bundle_writer_writes_only_declared_derived_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = _write_replay_manifest(root)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(
                render_decision_trace_json(build_decision_trace(root, manifest_path)),
                encoding="utf-8",
            )
            baseline_before = baseline_path.read_text(encoding="utf-8")
            bundle = build_replay_bundle(root, manifest_path, baseline_path)
            paths = ReplayBundlePaths(
                readiness_report="out/report.md",
                decision_trace="out/trace.json",
                trace_diff_json="out/diff.json",
                trace_diff_markdown="out/diff.md",
                protocol_self_audit_json="out/self_audit.json",
                protocol_self_audit_markdown="out/self_audit.md",
                baseline_lifecycle_json="out/lifecycle.json",
                baseline_lifecycle_markdown="out/lifecycle.md",
                drift_policy_json="out/drift_policy.json",
                drift_policy_markdown="out/drift_policy.md",
            )

            result = write_replay_bundle(root, bundle, paths=paths)

            self.assertEqual(
                set(result.written_paths),
                {
                    "out/report.md",
                    "out/trace.json",
                    "out/diff.json",
                    "out/diff.md",
                    "out/self_audit.json",
                    "out/self_audit.md",
                    "out/lifecycle.json",
                    "out/lifecycle.md",
                    "out/drift_policy.json",
                    "out/drift_policy.md",
                },
            )
            self.assertFalse(result.baseline_updated)
            self.assertEqual(result.state_change, "none")
            self.assertEqual(baseline_path.read_text(encoding="utf-8"), baseline_before)
            for relative_path in result.written_paths:
                self.assertTrue((root / relative_path).is_file())

    def test_replay_bundle_writer_rejects_baseline_cerebro_and_escape_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = _write_replay_manifest(root)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(
                render_decision_trace_json(build_decision_trace(root, manifest_path)),
                encoding="utf-8",
            )
            bundle = build_replay_bundle(root, manifest_path, baseline_path)

            with self.assertRaises(ValueError):
                write_replay_bundle(root, bundle, paths=ReplayBundlePaths(decision_trace=".cerebro/trace.json"))
            with self.assertRaises(ValueError):
                write_replay_bundle(
                    root,
                    bundle,
                    paths=ReplayBundlePaths(
                        decision_trace="docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json"
                    ),
                )
            with self.assertRaises(ValueError):
                write_replay_bundle(root, bundle, paths=ReplayBundlePaths(decision_trace="../outside.json"))

    def test_replay_bundle_summary_is_stable_and_non_authoritative(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "SYSTEM_STATE.md").write_text(
                "Current boundary: no Cerebro runtime boundary is open.\n",
                encoding="utf-8",
            )
            manifest_path = _write_replay_manifest(root)
            baseline_path = root / "baseline.json"
            baseline_path.write_text(
                render_decision_trace_json(build_decision_trace(root, manifest_path)),
                encoding="utf-8",
            )

            bundle = build_replay_bundle(root, manifest_path, baseline_path)
            payload = bundle.to_dict()

            self.assertEqual(payload["state_change"], "none")
            self.assertEqual(payload["authority"], "non-authoritative; advisory replay bundle evidence only")
            self.assertTrue(payload["guardrails"]["replay_success_is_not_permission"])
            self.assertTrue(payload["guardrails"]["baseline_refresh_is_not_automatic"])
            self.assertTrue(payload["guardrails"]["bundle_is_not_runtime_gate"])
            self.assertTrue(payload["guardrails"]["drift_policy_is_not_permission"])
            self.assertEqual(payload["summary"]["source_count"], 1)
            self.assertEqual(payload["summary"]["baseline_lifecycle_recommendation"], "baseline_already_current")
            self.assertEqual(payload["summary"]["drift_policy_classification"], "no_drift")
            self.assertIn("act as runtime gate", payload["boundary"]["must_not_apply"])
            self.assertIn("treat drift policy as permission", payload["boundary"]["must_not_apply"])

    def test_metacognitive_handoff_reports_clean_no_action_without_permission(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()

        report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        payload = report.to_dict()

        self.assertEqual(report.state_change, "none")
        self.assertEqual(report.action_readiness, "no_action")
        self.assertEqual(report.recommended_human_decision, "none")
        self.assertIn("replay baseline and current trace match", report.known)
        self.assertIn("silence is not negative evidence", " ".join(report.unknown))
        self.assertTrue(payload["guardrails"]["handoff_is_not_permission"])
        self.assertTrue(payload["guardrails"]["handoff_is_not_runtime_gate"])
        self.assertIn("treat handoff as permission", payload["boundary"]["must_not_apply"])

    def test_metacognitive_handoff_surfaces_conflict_and_missing_evidence(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        trace["summary"]["insufficient_count"] = 1
        trace["findings"][0]["sufficiency"] = "insufficient"
        trace["findings"][0]["conflict"] = "active"
        trace["findings"][0]["operational_readiness"] = "needs_review"

        report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)

        self.assertEqual(report.action_readiness, "human_approval_required")
        self.assertEqual(report.recommended_human_decision, "adjudicate_conflict")
        self.assertEqual(len(report.conflicts), 1)
        self.assertTrue(any("sufficiency=insufficient" in item for item in report.missing_evidence))
        self.assertTrue(any("operational_readiness=needs_review" in item for item in report.missing_evidence))

    def test_metacognitive_handoff_blocks_protocol_or_drift_blockers(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        self_audit["candidate_count"] = 1
        self_audit["high_or_blocking_count"] = 1
        drift_policy["action_readiness"] = "blocked"
        drift_policy["required_human_action"] = "review_blockers"
        drift_policy["classification"] = "blocked_regression_or_protocol_risk"
        drift_policy["recommendation"] = "refresh_blocked_pending_review"

        report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)

        self.assertEqual(report.action_readiness, "blocked")
        self.assertEqual(report.recommended_human_decision, "review_blockers")
        self.assertTrue(any("high/blocking" in item for item in report.missing_evidence))
        self.assertTrue(any("blocked_regression_or_protocol_risk" in item for item in report.risk_notes))

    def test_metacognitive_handoff_rejects_mutating_or_malformed_inputs(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()

        bad_trace = json.loads(json.dumps(trace))
        bad_trace["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_metacognitive_handoff(bad_trace, lifecycle, self_audit, drift_policy)

        bad_lifecycle = json.loads(json.dumps(lifecycle))
        bad_lifecycle["authority"] = "canonical"
        with self.assertRaises(ValueError):
            evaluate_metacognitive_handoff(trace, bad_lifecycle, self_audit, drift_policy)

        bad_audit = json.loads(json.dumps(self_audit))
        bad_audit["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            evaluate_metacognitive_handoff(trace, lifecycle, bad_audit, drift_policy)

        bad_drift = json.loads(json.dumps(drift_policy))
        bad_drift["schema_version"] = "999"
        with self.assertRaises(ValueError):
            evaluate_metacognitive_handoff(trace, lifecycle, self_audit, bad_drift)

    def test_metacognitive_handoff_json_and_markdown_are_boundary_explicit(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)

        json_payload = json.loads(render_metacognitive_handoff_json(report))
        markdown = render_metacognitive_handoff_markdown(report)

        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["recommended_human_decision"], "none")
        self.assertIn("handoff_is_not_permission: true", markdown)
        self.assertIn("silence_is_not_negative_evidence: true", markdown)
        self.assertIn("## Unknown", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_handoff_stress_matrix_proves_degraded_decisions(self) -> None:
        report = build_handoff_stress_matrix()
        payload = report.to_dict()
        decisions = payload["summary"]["decisions"]

        self.assertEqual(report.state_change, "none")
        self.assertEqual(payload["summary"]["scenario_count"], 5)
        self.assertEqual(payload["summary"]["pass_count"], 5)
        self.assertEqual(payload["summary"]["fail_count"], 0)
        self.assertEqual(decisions["clean_no_action"]["recommended_human_decision"], "none")
        self.assertEqual(decisions["clean_no_action"]["action_readiness"], "no_action")
        self.assertEqual(
            decisions["insufficient_evidence"]["recommended_human_decision"],
            "provide_missing_evidence",
        )
        self.assertEqual(
            decisions["insufficient_evidence"]["action_readiness"],
            "human_approval_required",
        )
        self.assertEqual(
            decisions["active_conflict"]["recommended_human_decision"],
            "adjudicate_conflict",
        )
        self.assertEqual(
            decisions["active_conflict"]["action_readiness"],
            "human_approval_required",
        )
        self.assertEqual(
            decisions["drift_review_required"]["recommended_human_decision"],
            "approve_baseline_refresh",
        )
        self.assertEqual(
            decisions["drift_review_required"]["action_readiness"],
            "human_approval_required",
        )
        self.assertEqual(
            decisions["protocol_blocker"]["recommended_human_decision"],
            "review_blockers",
        )
        self.assertEqual(decisions["protocol_blocker"]["action_readiness"], "blocked")

    def test_handoff_stress_matrix_is_non_authoritative_boundary_evidence(self) -> None:
        report = build_handoff_stress_matrix()
        payload = report.to_dict()

        self.assertEqual(
            payload["authority"],
            "non-authoritative; advisory handoff stress matrix evidence only",
        )
        self.assertTrue(payload["guardrails"]["stress_matrix_is_not_permission"])
        self.assertTrue(payload["guardrails"]["stress_matrix_is_not_runtime_gate"])
        self.assertTrue(payload["guardrails"]["stress_matrix_is_not_claim_graph"])
        self.assertTrue(payload["guardrails"]["passing_scenario_is_not_permission"])
        self.assertIn("treat green scenarios as permission", payload["boundary"]["must_not_apply"])
        self.assertIn("infer negative evidence from silence", payload["boundary"]["must_not_apply"])

    def test_handoff_stress_matrix_json_and_markdown_are_stable(self) -> None:
        report = build_handoff_stress_matrix()

        json_payload = json.loads(render_handoff_stress_matrix_json(report))
        markdown = render_handoff_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["summary"]["scenario_count"], 5)
        self.assertIn("# Epistemic Readiness Handoff Stress Matrix", markdown)
        self.assertIn("stress_matrix_is_not_permission: true", markdown)
        self.assertIn("passing_scenario_is_not_permission: true", markdown)
        self.assertIn("| `protocol_blocker` | `review_blockers` | `review_blockers` |", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_handoff_stress_matrix_rejects_duplicate_or_partial_scenarios(self) -> None:
        report = build_handoff_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            HandoffStressMatrixReport(scenarios=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            HandoffStressMatrixReport(scenarios=report.scenarios[:-1])

    def test_human_decision_taxonomy_covers_closed_decision_set_without_permission(self) -> None:
        report = build_human_decision_taxonomy()
        payload = report.to_dict()

        self.assertEqual(report.state_change, "none")
        self.assertEqual(
            payload["summary"]["decision_order"],
            [
                "none",
                "acknowledge",
                "approve_baseline_refresh",
                "adjudicate_conflict",
                "provide_missing_evidence",
                "review_blockers",
            ],
        )
        self.assertEqual(payload["summary"]["decision_count"], 6)
        self.assertFalse(payload["summary"]["all_entries_can_mutate_state"])
        self.assertFalse(payload["summary"]["all_entries_can_grant_permission"])
        self.assertTrue(payload["guardrails"]["human_decision_is_not_permission"])
        self.assertTrue(payload["guardrails"]["compatible_pair_is_not_permission"])
        for entry in payload["entries"]:
            self.assertFalse(entry["can_mutate_state"])
            self.assertFalse(entry["can_grant_permission"])
            self.assertIn("treat decision as permission", entry["forbidden_interpretations"])

    def test_human_decision_taxonomy_interprets_compatible_handoff_pairs(self) -> None:
        cases = {
            ("none", "no_action"): "none",
            ("acknowledge", "advisory_report_allowed"): "operator_acknowledgement",
            ("approve_baseline_refresh", "human_approval_required"): "human_approval",
            ("adjudicate_conflict", "human_approval_required"): "human_adjudication",
            ("provide_missing_evidence", "human_approval_required"): "evidence_request",
            ("review_blockers", "blocked"): "blocker_review",
        }

        for (decision, readiness), escalation_level in cases.items():
            with self.subTest(decision=decision, readiness=readiness):
                interpretation = interpret_handoff_decision(decision, readiness)
                self.assertTrue(interpretation.compatible)
                self.assertEqual(interpretation.escalation_level, escalation_level)
                self.assertEqual(interpretation.issues, ())
                self.assertIn(
                    "treat decision as permission",
                    interpretation.forbidden_interpretations,
                )
                self.assertEqual(interpretation.state_change, "none")

    def test_human_decision_taxonomy_flags_incompatible_pairs_without_authority(self) -> None:
        interpretation = interpret_handoff_decision("none", "human_approval_required")

        self.assertFalse(interpretation.compatible)
        self.assertEqual(interpretation.state_change, "none")
        self.assertTrue(any("inconsistent" in issue for issue in interpretation.issues))
        self.assertTrue(any("do not act" in issue for issue in interpretation.issues))
        self.assertIn("treat decision as permission", interpretation.forbidden_interpretations)

    def test_human_decision_taxonomy_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_human_decision_taxonomy()

        json_payload = json.loads(render_human_decision_taxonomy_json(report))
        markdown = render_human_decision_taxonomy_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["summary"]["decision_count"], 6)
        self.assertIn("# Epistemic Readiness Human Decision Taxonomy", markdown)
        self.assertIn("human_decision_is_not_permission: true", markdown)
        self.assertIn("compatible_pair_is_not_permission: true", markdown)
        self.assertIn("| `review_blockers` | `blocked` | `blocker_review` |", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_human_decision_taxonomy_rejects_duplicate_partial_or_authoritative_entries(self) -> None:
        report = build_human_decision_taxonomy()
        duplicate = report.entries[0]

        with self.assertRaises(ValueError):
            HumanDecisionTaxonomyReport(entries=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            HumanDecisionTaxonomyReport(entries=report.entries[:-1])
        with self.assertRaises(ValueError):
            type(duplicate)(
                decision=duplicate.decision,
                meaning=duplicate.meaning,
                compatible_action_readiness=duplicate.compatible_action_readiness,
                escalation_level=duplicate.escalation_level,
                required_evidence=duplicate.required_evidence,
                allowed_next_actions=duplicate.allowed_next_actions,
                forbidden_interpretations=duplicate.forbidden_interpretations,
                can_grant_permission=True,
            )

    def test_decision_taxonomy_conformance_covers_real_stress_matrix(self) -> None:
        report = evaluate_decision_taxonomy_conformance()
        payload = report.to_dict()

        self.assertEqual(report.state_change, "none")
        self.assertEqual(payload["summary"]["case_count"], 5)
        self.assertEqual(payload["summary"]["pass_count"], 5)
        self.assertEqual(payload["summary"]["fail_count"], 0)
        self.assertTrue(payload["summary"]["all_cases_passed"])
        self.assertTrue(payload["guardrails"]["conformance_is_not_permission"])
        self.assertTrue(payload["guardrails"]["covered_pair_is_not_permission"])
        self.assertTrue(payload["guardrails"]["incompatible_pair_must_be_visible"])
        for case in payload["cases"]:
            self.assertTrue(case["taxonomy_compatible"])
            self.assertTrue(case["stress_scenario_passed"])
            self.assertTrue(case["conformance_passed"])
            self.assertEqual(case["state_change"], "none")
            self.assertIn(
                "treat conformance pass as permission",
                case["forbidden_interpretations"],
            )

    def test_decision_taxonomy_conformance_surfaces_incompatible_pairs(self) -> None:
        taxonomy = build_human_decision_taxonomy()
        original = taxonomy.entries[0]
        altered_none_entry = type(original)(
            decision=original.decision,
            meaning=original.meaning,
            compatible_action_readiness=("observe_only",),
            escalation_level=original.escalation_level,
            required_evidence=original.required_evidence,
            allowed_next_actions=original.allowed_next_actions,
            forbidden_interpretations=original.forbidden_interpretations,
        )
        altered_taxonomy = HumanDecisionTaxonomyReport(
            entries=(altered_none_entry, *taxonomy.entries[1:])
        )

        report = evaluate_decision_taxonomy_conformance(
            build_handoff_stress_matrix(),
            altered_taxonomy,
        )

        clean_case = report.cases[0]
        self.assertFalse(clean_case.taxonomy_compatible)
        self.assertFalse(clean_case.conformance_passed)
        self.assertEqual(report.fail_count, 1)
        self.assertTrue(any("inconsistent" in issue for issue in clean_case.issues))
        self.assertTrue(any("do not act" in issue for issue in clean_case.issues))

    def test_decision_taxonomy_conformance_json_and_markdown_are_boundary_explicit(self) -> None:
        report = evaluate_decision_taxonomy_conformance()

        json_payload = json.loads(render_decision_taxonomy_conformance_json(report))
        markdown = render_decision_taxonomy_conformance_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["summary"]["case_count"], 5)
        self.assertIn("# Epistemic Readiness Decision Taxonomy Conformance", markdown)
        self.assertIn("conformance_is_not_permission: true", markdown)
        self.assertIn("covered_pair_is_not_permission: true", markdown)
        self.assertIn("incompatible_pair_must_be_visible: true", markdown)
        self.assertIn("| `protocol_blocker` | `review_blockers` | `blocked` |", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_decision_taxonomy_conformance_rejects_duplicate_empty_or_mutating_cases(self) -> None:
        report = evaluate_decision_taxonomy_conformance()
        duplicate = report.cases[0]

        with self.assertRaises(ValueError):
            DecisionTaxonomyConformanceReport(cases=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            DecisionTaxonomyConformanceReport(cases=())
        with self.assertRaises(ValueError):
            DecisionTaxonomyConformanceCase(
                scenario_id=duplicate.scenario_id,
                recommended_human_decision=duplicate.recommended_human_decision,
                action_readiness=duplicate.action_readiness,
                taxonomy_compatible=duplicate.taxonomy_compatible,
                stress_scenario_passed=duplicate.stress_scenario_passed,
                escalation_level=duplicate.escalation_level,
                required_evidence=duplicate.required_evidence,
                allowed_next_actions=duplicate.allowed_next_actions,
                forbidden_interpretations=duplicate.forbidden_interpretations,
                issues=duplicate.issues,
                state_change="canonical-mutation",
            )

    def test_operator_decision_packet_summarizes_clean_current_state_without_permission(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        conformance = evaluate_decision_taxonomy_conformance()

        packet = build_operator_decision_packet(
            handoff.to_dict(),
            conformance.to_dict(),
            drift_policy,
            lifecycle,
        )
        payload = packet.to_dict()

        self.assertEqual(packet.state_change, "none")
        self.assertEqual(packet.recommended_human_decision, "none")
        self.assertEqual(packet.action_readiness, "no_action")
        self.assertTrue(packet.conformance_passed)
        self.assertEqual(packet.blockers, ())
        self.assertIn("metacognitive_handoff: decision=none; readiness=no_action", packet.source_evidence)
        self.assertTrue(payload["guardrails"]["operator_packet_is_not_permission"])
        self.assertTrue(payload["guardrails"]["conformance_pass_is_not_permission"])
        self.assertIn("treat packet as permission", payload["boundary"]["must_not_apply"])

    def test_operator_decision_packet_blocks_failed_conformance(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        conformance = evaluate_decision_taxonomy_conformance().to_dict()
        conformance["summary"]["all_cases_passed"] = False
        conformance["summary"]["fail_count"] = 1
        conformance["summary"]["covered_pairs"] = []
        conformance["cases"][0]["conformance_passed"] = False
        conformance["cases"][0]["issues"] = ["pair incompatible in regression fixture"]

        packet = build_operator_decision_packet(
            handoff.to_dict(),
            conformance,
            drift_policy,
            lifecycle,
        )

        self.assertEqual(packet.recommended_human_decision, "review_blockers")
        self.assertEqual(packet.action_readiness, "blocked")
        self.assertFalse(packet.conformance_passed)
        self.assertTrue(
            any("decision taxonomy conformance has 1 failing case" in item for item in packet.blockers)
        )
        self.assertTrue(any("pair incompatible" in item for item in packet.blockers))

    def test_operator_decision_packet_preserves_handoff_human_decision(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        trace["summary"]["insufficient_count"] = 1
        trace["findings"][0]["sufficiency"] = "insufficient"
        trace["findings"][0]["operational_readiness"] = "needs_review"
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)

        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        )

        self.assertEqual(packet.recommended_human_decision, "provide_missing_evidence")
        self.assertEqual(packet.action_readiness, "human_approval_required")
        self.assertTrue(packet.conformance_passed)
        self.assertTrue(any("sufficiency=insufficient" in item for item in packet.missing_evidence))

    def test_operator_decision_packet_rejects_mutating_or_malformed_inputs(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy).to_dict()
        conformance = evaluate_decision_taxonomy_conformance().to_dict()

        bad_handoff = json.loads(json.dumps(handoff))
        bad_handoff["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            build_operator_decision_packet(bad_handoff, conformance, drift_policy, lifecycle)

        bad_conformance = json.loads(json.dumps(conformance))
        bad_conformance["authority"] = "canonical"
        with self.assertRaises(ValueError):
            build_operator_decision_packet(handoff, bad_conformance, drift_policy, lifecycle)

        bad_drift = json.loads(json.dumps(drift_policy))
        bad_drift["guardrails"]["drift_policy_is_not_permission"] = False
        with self.assertRaises(ValueError):
            build_operator_decision_packet(handoff, conformance, bad_drift, lifecycle)

        bad_lifecycle = json.loads(json.dumps(lifecycle))
        bad_lifecycle["schema_version"] = "999"
        with self.assertRaises(ValueError):
            build_operator_decision_packet(handoff, conformance, drift_policy, bad_lifecycle)

    def test_operator_decision_packet_json_and_markdown_are_boundary_explicit(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        )

        json_payload = json.loads(render_operator_decision_packet_json(packet))
        markdown = render_operator_decision_packet_markdown(packet)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["recommended_human_decision"], "none")
        self.assertIn("# Epistemic Readiness Operator Decision Packet", markdown)
        self.assertIn("operator_packet_is_not_permission: true", markdown)
        self.assertIn("conformance_pass_is_not_permission: true", markdown)
        self.assertIn("silence_is_not_negative_evidence: true", markdown)
        self.assertIn("## Source Evidence", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_packet_stress_matrix_covers_degraded_decisions_without_permission(self) -> None:
        report = build_operator_packet_stress_matrix()
        payload = report.to_dict()
        decisions = payload["summary"]["decisions"]

        self.assertEqual(report.state_change, "none")
        self.assertEqual(payload["summary"]["scenario_count"], 6)
        self.assertEqual(payload["summary"]["pass_count"], 6)
        self.assertEqual(payload["summary"]["fail_count"], 0)
        self.assertTrue(payload["summary"]["all_scenarios_passed"])
        self.assertEqual(decisions["clean_no_action"]["recommended_human_decision"], "none")
        self.assertEqual(decisions["clean_no_action"]["action_readiness"], "no_action")
        self.assertEqual(
            decisions["handoff_human_review"]["recommended_human_decision"],
            "provide_missing_evidence",
        )
        self.assertEqual(
            decisions["handoff_human_review"]["action_readiness"],
            "human_approval_required",
        )
        self.assertEqual(
            decisions["conformance_failure"]["recommended_human_decision"],
            "review_blockers",
        )
        self.assertEqual(decisions["conformance_failure"]["action_readiness"], "blocked")
        self.assertEqual(
            decisions["drift_review_required"]["recommended_human_decision"],
            "approve_baseline_refresh",
        )
        self.assertEqual(
            decisions["drift_review_required"]["action_readiness"],
            "human_approval_required",
        )
        self.assertEqual(
            decisions["lifecycle_blocker"]["recommended_human_decision"],
            "review_blockers",
        )
        self.assertEqual(decisions["lifecycle_blocker"]["action_readiness"], "blocked")
        self.assertEqual(
            decisions["malformed_boundary"]["recommended_human_decision"],
            "review_blockers",
        )
        self.assertEqual(decisions["malformed_boundary"]["action_readiness"], "blocked")
        self.assertTrue(decisions["malformed_boundary"]["boundary_error"])
        self.assertTrue(payload["guardrails"]["operator_packet_output_is_not_permission"])
        self.assertIn("treat packet output as permission", payload["boundary"]["must_not_apply"])

    def test_operator_packet_stress_matrix_keeps_blockers_and_errors_visible(self) -> None:
        report = build_operator_packet_stress_matrix()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertGreater(scenarios["conformance_failure"].blocker_count, 0)
        self.assertGreater(scenarios["lifecycle_blocker"].blocker_count, 0)
        self.assertGreater(scenarios["malformed_boundary"].blocker_count, 0)
        self.assertIn(
            "drift_policy_is_not_permission",
            scenarios["malformed_boundary"].observed_error,
        )
        self.assertEqual(scenarios["drift_review_required"].blocker_count, 0)
        self.assertEqual(scenarios["drift_review_required"].observed_error, "")

    def test_operator_packet_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_packet_stress_matrix()

        json_payload = json.loads(render_operator_packet_stress_matrix_json(report))
        markdown = render_operator_packet_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["scenario_count"], 6)
        self.assertIn("# Epistemic Readiness Operator Packet Stress Matrix", markdown)
        self.assertIn("stress_matrix_is_not_permission: true", markdown)
        self.assertIn("operator_packet_output_is_not_permission: true", markdown)
        self.assertIn("malformed_boundary_is_blocking_evidence: true", markdown)
        self.assertIn("| `malformed_boundary` | `review_blockers` | `review_blockers` |", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_packet_stress_matrix_rejects_duplicate_partial_or_mutating_scenarios(self) -> None:
        report = build_operator_packet_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorPacketStressMatrixReport(scenarios=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            OperatorPacketStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorPacketStressScenario(
                scenario_id=duplicate.scenario_id,
                title=duplicate.title,
                purpose=duplicate.purpose,
                expected_recommended_human_decision=duplicate.expected_recommended_human_decision,
                expected_action_readiness=duplicate.expected_action_readiness,
                observed_recommended_human_decision=duplicate.observed_recommended_human_decision,
                observed_action_readiness=duplicate.observed_action_readiness,
                packet_summary=duplicate.packet_summary,
                blocker_count=duplicate.blocker_count,
                missing_evidence_count=duplicate.missing_evidence_count,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_bundle_packages_packet_stress_and_digests_without_permission(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        )
        stress = build_operator_packet_stress_matrix()

        bundle = build_operator_evidence_bundle(packet.to_dict(), stress.to_dict())
        payload = bundle.to_dict()
        inputs = {item["artifact_id"]: item for item in payload["inputs"]}

        self.assertEqual(bundle.state_change, "none")
        self.assertEqual(bundle.packet_recommended_human_decision, "none")
        self.assertEqual(bundle.packet_action_readiness, "no_action")
        self.assertTrue(bundle.packet_conformance_passed)
        self.assertEqual(bundle.stress_scenario_count, 6)
        self.assertEqual(bundle.stress_pass_count, 6)
        self.assertEqual(bundle.stress_fail_count, 0)
        self.assertTrue(bundle.stress_all_scenarios_passed)
        self.assertEqual(bundle.boundary_error_count, 1)
        self.assertEqual(bundle.input_count, 2)
        self.assertEqual(bundle.source_artifact_count, 0)
        self.assertIn("operator_decision_packet", inputs)
        self.assertIn("operator_packet_stress_matrix", inputs)
        self.assertEqual(len(inputs["operator_decision_packet"]["digest"]), 64)
        self.assertTrue(payload["guardrails"]["bundle_is_not_permission"])
        self.assertTrue(payload["guardrails"]["digest_is_not_truth"])
        self.assertIn("treat bundle as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_bundle_accepts_source_artifact_digests_without_file_io(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        conformance = evaluate_decision_taxonomy_conformance()
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            conformance.to_dict(),
            drift_policy,
            lifecycle,
        )
        stress = build_operator_packet_stress_matrix()

        bundle = build_operator_evidence_bundle(
            packet.to_dict(),
            stress.to_dict(),
            {
                "decision_taxonomy_conformance": conformance.to_dict(),
                "metacognitive_handoff": handoff.to_dict(),
            },
        )
        payload = bundle.to_dict()
        inputs = {item["artifact_id"]: item for item in payload["inputs"]}

        self.assertEqual(bundle.input_count, 4)
        self.assertEqual(bundle.source_artifact_count, 2)
        self.assertEqual(
            inputs["decision_taxonomy_conformance"]["artifact_role"],
            "source advisory artifact digest",
        )
        self.assertIn(
            "authority=non-authoritative; advisory decision taxonomy conformance evidence only",
            inputs["decision_taxonomy_conformance"]["summary"],
        )
        self.assertEqual(len(inputs["metacognitive_handoff"]["digest"]), 64)

    def test_operator_evidence_bundle_rejects_mutating_or_malformed_inputs(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        ).to_dict()
        stress = build_operator_packet_stress_matrix().to_dict()

        bad_packet = json.loads(json.dumps(packet))
        bad_packet["state_change"] = "canonical-mutation"
        with self.assertRaises(ValueError):
            build_operator_evidence_bundle(bad_packet, stress)

        bad_stress = json.loads(json.dumps(stress))
        bad_stress["authority"] = "canonical"
        with self.assertRaises(ValueError):
            build_operator_evidence_bundle(packet, bad_stress)

        bad_guardrail = json.loads(json.dumps(stress))
        bad_guardrail["guardrails"]["stress_matrix_is_not_permission"] = False
        with self.assertRaises(ValueError):
            build_operator_evidence_bundle(packet, bad_guardrail)

        with self.assertRaises(ValueError):
            build_operator_evidence_bundle(
                packet,
                stress,
                {"mutating_source": {"state_change": "canonical-mutation"}},
            )

    def test_operator_evidence_bundle_json_and_markdown_are_boundary_explicit(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        )
        stress = build_operator_packet_stress_matrix()
        bundle = build_operator_evidence_bundle(packet.to_dict(), stress.to_dict())

        json_payload = json.loads(render_operator_evidence_bundle_json(bundle))
        markdown = render_operator_evidence_bundle_markdown(bundle)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["input_count"], 2)
        self.assertIn("# Epistemic Readiness Operator Evidence Bundle", markdown)
        self.assertIn("bundle_is_not_permission: true", markdown)
        self.assertIn("digest_is_not_truth: true", markdown)
        self.assertIn("stress_pass_is_not_permission: true", markdown)
        self.assertIn("## Input Digests", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_bundle_rejects_duplicate_or_mutating_inputs(self) -> None:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            evaluate_decision_taxonomy_conformance().to_dict(),
            drift_policy,
            lifecycle,
        )
        stress = build_operator_packet_stress_matrix()
        bundle = build_operator_evidence_bundle(packet.to_dict(), stress.to_dict())
        duplicate = bundle.inputs[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceBundleReport(
                packet_recommended_human_decision=bundle.packet_recommended_human_decision,
                packet_action_readiness=bundle.packet_action_readiness,
                packet_conformance_passed=bundle.packet_conformance_passed,
                stress_scenario_count=bundle.stress_scenario_count,
                stress_pass_count=bundle.stress_pass_count,
                stress_fail_count=bundle.stress_fail_count,
                stress_all_scenarios_passed=bundle.stress_all_scenarios_passed,
                boundary_error_count=bundle.boundary_error_count,
                inputs=(duplicate, duplicate),
            )

        with self.assertRaises(ValueError):
            OperatorEvidenceBundleInput(
                artifact_id="bad",
                digest=duplicate.digest,
                summary="bad",
                state_change="canonical-mutation",
            )

        with self.assertRaises(ValueError):
            OperatorEvidenceBundleInput(
                artifact_id="bad",
                digest="not-a-sha256",
                summary="bad",
            )

    def test_operator_evidence_bundle_stress_matrix_covers_degraded_bundle_inputs_without_permission(self) -> None:
        report = build_operator_evidence_bundle_stress_matrix()
        payload = report.to_dict()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertEqual(payload["summary"]["scenario_count"], 7)
        self.assertEqual(report.pass_count, 7)
        self.assertEqual(report.fail_count, 0)
        self.assertTrue(report.all_scenarios_passed)
        self.assertEqual(tuple(scenarios), (
            "clean_bundle",
            "missing_operator_packet",
            "mutating_operator_packet",
            "malformed_stress_matrix",
            "mutating_source_artifact",
            "duplicate_input_id",
            "digest_summary_mismatch",
        ))
        self.assertEqual(scenarios["clean_bundle"].observed_recommended_human_decision, "none")
        self.assertEqual(scenarios["clean_bundle"].observed_action_readiness, "no_action")
        self.assertEqual(scenarios["clean_bundle"].observed_error, "")
        for scenario_id, scenario in scenarios.items():
            if scenario_id == "clean_bundle":
                continue
            self.assertEqual(scenario.observed_recommended_human_decision, "review_blockers")
            self.assertEqual(scenario.observed_action_readiness, "blocked")
            self.assertGreater(scenario.blocker_count, 0)
            self.assertGreater(scenario.boundary_error_count, 0)
            self.assertTrue(scenario.observed_error)
        self.assertTrue(payload["guardrails"]["bundle_stress_matrix_is_not_permission"])
        self.assertTrue(payload["guardrails"]["artifact_digest_is_not_truth"])
        self.assertIn("treat bundle output as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_bundle_stress_matrix_keeps_bundle_errors_visible(self) -> None:
        report = build_operator_evidence_bundle_stress_matrix()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertIn("operator_packet", scenarios["missing_operator_packet"].observed_error)
        self.assertIn("state_change", scenarios["mutating_operator_packet"].observed_error)
        self.assertIn("stress matrix guardrail", scenarios["malformed_stress_matrix"].observed_error)
        self.assertIn("source artifact", scenarios["mutating_source_artifact"].observed_error)
        self.assertIn("unique", scenarios["duplicate_input_id"].observed_error)
        self.assertIn("digest/summary mismatch", scenarios["digest_summary_mismatch"].observed_error)
        self.assertIn("digest mismatch", scenarios["digest_summary_mismatch"].observed_error)
        self.assertIn("summary mismatch", scenarios["digest_summary_mismatch"].observed_error)

    def test_operator_evidence_bundle_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_evidence_bundle_stress_matrix()

        json_payload = json.loads(render_operator_evidence_bundle_stress_matrix_json(report))
        markdown = render_operator_evidence_bundle_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["scenario_count"], 7)
        self.assertIn("# Epistemic Readiness Operator Evidence Bundle Stress Matrix", markdown)
        self.assertIn("bundle_stress_matrix_is_not_permission: true", markdown)
        self.assertIn("bundle_output_is_not_permission: true", markdown)
        self.assertIn("artifact_digest_is_not_truth: true", markdown)
        self.assertIn("malformed_bundle_input_is_blocking_evidence: true", markdown)
        self.assertIn("| `digest_summary_mismatch` | `review_blockers` | `review_blockers` |", markdown)
        self.assertIn("## Visible Errors", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_bundle_stress_matrix_rejects_duplicate_partial_or_mutating_scenarios(self) -> None:
        report = build_operator_evidence_bundle_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceBundleStressMatrixReport(scenarios=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            OperatorEvidenceBundleStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorEvidenceBundleStressScenario(
                scenario_id=duplicate.scenario_id,
                title=duplicate.title,
                purpose=duplicate.purpose,
                expected_recommended_human_decision=duplicate.expected_recommended_human_decision,
                expected_action_readiness=duplicate.expected_action_readiness,
                observed_recommended_human_decision=duplicate.observed_recommended_human_decision,
                observed_action_readiness=duplicate.observed_action_readiness,
                bundle_summary=duplicate.bundle_summary,
                blocker_count=duplicate.blocker_count,
                boundary_error_count=duplicate.boundary_error_count,
                state_change="canonical-mutation",
            )

    def _write_clean_operator_intake_artifacts(self, root: Path) -> OperatorEvidenceIntakeManifest:
        trace, lifecycle, self_audit, drift_policy = _clean_handoff_payloads()
        handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
        conformance = evaluate_decision_taxonomy_conformance()
        packet = build_operator_decision_packet(
            handoff.to_dict(),
            conformance.to_dict(),
            drift_policy,
            lifecycle,
        )
        stress = build_operator_packet_stress_matrix()
        payloads = {
            "operator_decision_packet": packet.to_dict(),
            "operator_packet_stress_matrix": stress.to_dict(),
            "baseline_lifecycle": lifecycle,
            "decision_taxonomy_conformance": conformance.to_dict(),
            "drift_policy": drift_policy,
            "metacognitive_handoff": handoff.to_dict(),
        }
        artifacts: list[OperatorEvidenceIntakeArtifact] = []
        for artifact_id, payload in payloads.items():
            path = f"{artifact_id}.json"
            (root / path).write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
            artifacts.append(
                OperatorEvidenceIntakeArtifact(
                    artifact_id=artifact_id,
                    path=path,
                    role=(
                        "advisory bundle input"
                        if artifact_id in {"operator_decision_packet", "operator_packet_stress_matrix"}
                        else "source advisory artifact digest"
                    ),
                )
            )
        return OperatorEvidenceIntakeManifest(
            root=str(root),
            generated_report_json="intake.json",
            generated_report_markdown="intake.md",
            artifacts=tuple(artifacts),
        )

    def _write_operator_intake_manifest_file(
        self,
        root: Path,
        manifest: OperatorEvidenceIntakeManifest,
        *,
        first_expected_digest: str = "",
    ) -> Path:
        lines = [
            'schema_version = "1"',
            'state_change = "none"',
            'authority = "non-authoritative; advisory operator evidence intake manifest only"',
            'root = "."',
            f'generated_report_json = "{manifest.generated_report_json}"',
            f'generated_report_markdown = "{manifest.generated_report_markdown}"',
            "",
        ]
        for index, artifact in enumerate(manifest.artifacts):
            expected_digest = first_expected_digest if index == 0 else artifact.expected_digest
            lines.extend(
                [
                    "[[artifacts]]",
                    f'artifact_id = "{artifact.artifact_id}"',
                    f'path = "{artifact.path}"',
                    f'role = "{artifact.role}"',
                ]
            )
            if expected_digest:
                lines.append(f'expected_digest = "{expected_digest}"')
            lines.append("")
        manifest_path = root / "intake.toml"
        manifest_path.write_text("\n".join(lines), encoding="utf-8")
        return manifest_path

    def test_operator_evidence_intake_manifest_builds_bundle_from_declared_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)

            report = build_operator_evidence_intake_report(manifest)

            self.assertFalse(report.blocked)
            self.assertEqual(report.recommended_human_decision, "none")
            self.assertEqual(report.action_readiness, "advisory_report_allowed")
            self.assertEqual(report.input_count, 6)
            self.assertEqual(report.source_artifact_count, 4)
            self.assertIsNotNone(report.bundle)
            self.assertEqual(report.bundle.packet_recommended_human_decision, "none")
            self.assertEqual(report.bundle.packet_action_readiness, "no_action")
            self.assertEqual(report.bundle.stress_scenario_count, 6)
            self.assertEqual(report.bundle.stress_pass_count, 6)
            self.assertEqual(report.bundle.stress_fail_count, 0)
            self.assertEqual(report.state_change, "none")

    def test_operator_evidence_intake_manifest_loader_and_missing_artifact_blocker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = root / "intake.toml"
            manifest_path.write_text(
                "\n".join(
                    [
                        'schema_version = "1"',
                        'state_change = "none"',
                        'authority = "non-authoritative; advisory operator evidence intake manifest only"',
                        'root = "."',
                        'generated_report_json = "intake.json"',
                        'generated_report_markdown = "intake.md"',
                        "",
                        "[[artifacts]]",
                        'artifact_id = "operator_decision_packet"',
                        'path = "operator_decision_packet.json"',
                        'role = "advisory bundle input"',
                        "",
                        "[[artifacts]]",
                        'artifact_id = "operator_packet_stress_matrix"',
                        'path = "missing.json"',
                        'role = "advisory bundle input"',
                    ]
                ),
                encoding="utf-8",
            )

            loaded = load_operator_evidence_intake_manifest(manifest_path)
            report = build_operator_evidence_intake_report(loaded)
            direct_report = build_operator_evidence_intake_report_from_manifest(manifest_path)

            self.assertTrue(report.blocked)
            self.assertTrue(direct_report.blocked)
            self.assertEqual(len(loaded.artifacts), 2)
            self.assertIn("artifact file is missing", report.blockers[0])
            self.assertEqual(manifest.generated_report_json, "intake.json")

    def test_operator_evidence_intake_manifest_blocks_stale_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            stale_artifact = OperatorEvidenceIntakeArtifact(
                artifact_id=manifest.artifacts[0].artifact_id,
                path=manifest.artifacts[0].path,
                role=manifest.artifacts[0].role,
                expected_digest="0" * 64,
            )
            stale_manifest = OperatorEvidenceIntakeManifest(
                root=manifest.root,
                generated_report_json=manifest.generated_report_json,
                generated_report_markdown=manifest.generated_report_markdown,
                artifacts=(stale_artifact, *manifest.artifacts[1:]),
            )

            report = build_operator_evidence_intake_report(stale_manifest)

            self.assertTrue(report.blocked)
            self.assertIsNone(report.bundle)
            self.assertIn("digest mismatch", " ".join(report.blockers))

    def test_operator_evidence_intake_manifest_blocks_root_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir) / "root"
            root.mkdir()
            artifact = OperatorEvidenceIntakeArtifact(
                artifact_id="operator_decision_packet",
                path="../outside.json",
                role="advisory bundle input",
            )
            manifest = OperatorEvidenceIntakeManifest(
                root=str(root),
                generated_report_json="intake.json",
                generated_report_markdown="intake.md",
                artifacts=(
                    artifact,
                    OperatorEvidenceIntakeArtifact(
                        artifact_id="operator_packet_stress_matrix",
                        path="operator_packet_stress_matrix.json",
                        role="advisory bundle input",
                    ),
                ),
            )

            report = build_operator_evidence_intake_report(manifest)

            self.assertTrue(report.blocked)
            self.assertIn("escapes root", " ".join(report.blockers))

    def test_operator_evidence_intake_manifest_blocks_mutating_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            mutating = json.loads((root / "drift_policy.json").read_text(encoding="utf-8"))
            mutating["state_change"] = "canonical-mutation"
            (root / "drift_policy.json").write_text(json.dumps(mutating), encoding="utf-8")

            report = build_operator_evidence_intake_report(manifest)

            self.assertTrue(report.blocked)
            self.assertIsNone(report.bundle)
            self.assertIn("state_change none", " ".join(report.blockers))

    def test_operator_evidence_intake_manifest_rejects_duplicate_artifact_ids(self) -> None:
        artifact = OperatorEvidenceIntakeArtifact(
            artifact_id="operator_decision_packet",
            path="operator_decision_packet.json",
            role="advisory bundle input",
        )

        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeManifest(
                root=".",
                generated_report_json="intake.json",
                generated_report_markdown="intake.md",
                artifacts=(artifact, artifact),
            )

    def test_operator_evidence_intake_report_json_and_markdown_are_boundary_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report = build_operator_evidence_intake_report(
                self._write_clean_operator_intake_artifacts(root)
            )

            json_payload = json.loads(render_operator_evidence_intake_report_json(report))
            markdown = render_operator_evidence_intake_report_markdown(report)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["input_count"], 6)
            self.assertTrue(json_payload["guardrails"]["intake_report_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["digest_equality_is_not_truth"])
            self.assertIn("# Epistemic Readiness Operator Evidence Intake Report", markdown)
            self.assertIn("intake_report_is_not_permission: true", markdown)
            self.assertIn("digest_equality_is_not_truth: true", markdown)
            self.assertIn("## Blockers", markdown)
            self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_intake_report_rejects_mutating_or_incoherent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            report = build_operator_evidence_intake_report(
                self._write_clean_operator_intake_artifacts(root)
            )
            first = report.inputs[0]

            with self.assertRaises(ValueError):
                OperatorEvidenceIntakeInput(
                    artifact_id="bad",
                    path="bad.json",
                    role="bad",
                    digest=first.digest,
                    state_change="canonical-mutation",
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceIntakeReport(
                    manifest_root=str(root),
                    inputs=report.inputs,
                    blockers=(),
                    bundle=None,
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceIntakeReport(
                    manifest_root=str(root),
                    inputs=report.inputs,
                    blockers=("blocked",),
                    bundle=report.bundle,
                )

    def test_operator_evidence_intake_stress_matrix_covers_degraded_manifests_without_permission(self) -> None:
        report = build_operator_evidence_intake_stress_matrix()
        payload = report.to_dict()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertEqual(payload["summary"]["scenario_count"], 8)
        self.assertEqual(report.pass_count, 8)
        self.assertEqual(report.fail_count, 0)
        self.assertTrue(report.all_scenarios_passed)
        self.assertEqual(tuple(scenarios), (
            "clean_manifest",
            "missing_artifact",
            "stale_digest",
            "root_escape",
            "non_json_artifact",
            "mutating_payload",
            "duplicate_artifact_id",
            "missing_required_artifact",
        ))
        self.assertEqual(scenarios["clean_manifest"].observed_recommended_human_decision, "none")
        self.assertEqual(scenarios["clean_manifest"].observed_action_readiness, "advisory_report_allowed")
        self.assertEqual(scenarios["clean_manifest"].observed_error, "")
        for scenario_id, scenario in scenarios.items():
            if scenario_id == "clean_manifest":
                continue
            self.assertEqual(scenario.observed_recommended_human_decision, "review_blockers")
            self.assertEqual(scenario.observed_action_readiness, "blocked")
            self.assertGreater(scenario.blocker_count, 0)
            self.assertGreater(scenario.boundary_error_count, 0)
            self.assertTrue(scenario.observed_error)
        self.assertTrue(payload["guardrails"]["intake_stress_matrix_is_not_permission"])
        self.assertTrue(payload["guardrails"]["digest_equality_is_not_truth"])
        self.assertIn("treat intake output as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_intake_stress_matrix_keeps_manifest_errors_visible(self) -> None:
        report = build_operator_evidence_intake_stress_matrix()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertIn("artifact file is missing", scenarios["missing_artifact"].observed_error)
        self.assertIn("digest mismatch", scenarios["stale_digest"].observed_error)
        self.assertIn("escapes root", scenarios["root_escape"].observed_error)
        self.assertIn(".json", scenarios["non_json_artifact"].observed_error)
        self.assertIn("state_change none", scenarios["mutating_payload"].observed_error)
        self.assertIn("unique", scenarios["duplicate_artifact_id"].observed_error)
        self.assertIn("missing required artifact", scenarios["missing_required_artifact"].observed_error)

    def test_operator_evidence_intake_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_evidence_intake_stress_matrix()

        json_payload = json.loads(render_operator_evidence_intake_stress_matrix_json(report))
        markdown = render_operator_evidence_intake_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["scenario_count"], 8)
        self.assertIn("# Epistemic Readiness Operator Evidence Intake Stress Matrix", markdown)
        self.assertIn("intake_stress_matrix_is_not_permission: true", markdown)
        self.assertIn("intake_output_is_not_permission: true", markdown)
        self.assertIn("digest_equality_is_not_truth: true", markdown)
        self.assertIn("malformed_intake_input_is_blocking_evidence: true", markdown)
        self.assertIn("| `stale_digest` | `review_blockers` | `review_blockers` |", markdown)
        self.assertIn("## Visible Errors", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_intake_stress_matrix_rejects_duplicate_partial_or_mutating_scenarios(self) -> None:
        report = build_operator_evidence_intake_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeStressMatrixReport(scenarios=(duplicate, duplicate))
        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeStressScenario(
                scenario_id=duplicate.scenario_id,
                title=duplicate.title,
                purpose=duplicate.purpose,
                expected_recommended_human_decision=duplicate.expected_recommended_human_decision,
                expected_action_readiness=duplicate.expected_action_readiness,
                observed_recommended_human_decision=duplicate.observed_recommended_human_decision,
                observed_action_readiness=duplicate.observed_action_readiness,
                intake_summary=duplicate.intake_summary,
                blocker_count=duplicate.blocker_count,
                boundary_error_count=duplicate.boundary_error_count,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_intake_reproducibility_accepts_clean_checked_report_without_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            report = build_operator_evidence_intake_report(
                load_operator_evidence_intake_manifest(manifest_path)
            )
            checked_path = root / "intake.json"
            checked_path.write_text(render_operator_evidence_intake_report_json(report), encoding="utf-8")

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                checked_path,
            )
            payload = reproducibility.to_dict()

            self.assertEqual(reproducibility.reproducibility_status, "reproducible")
            self.assertEqual(reproducibility.recommended_human_decision, "none")
            self.assertEqual(reproducibility.action_readiness, "advisory_report_allowed")
            self.assertFalse(reproducibility.blockers)
            self.assertFalse(reproducibility.mismatches)
            self.assertTrue(reproducibility.digest_match)
            self.assertTrue(payload["guardrails"]["reproducibility_check_is_not_permission"])
            self.assertTrue(payload["guardrails"]["digest_equality_is_not_truth"])
            self.assertIn("treat reproducibility as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_intake_reproducibility_blocks_stale_checked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            report = build_operator_evidence_intake_report(
                load_operator_evidence_intake_manifest(manifest_path)
            )
            stale_payload = report.to_dict()
            stale_payload["summary"]["input_count"] = 999
            checked_path = root / "intake.json"
            checked_path.write_text(json.dumps(stale_payload, indent=2, sort_keys=True), encoding="utf-8")

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                checked_path,
            )

            self.assertEqual(reproducibility.reproducibility_status, "stale_or_mismatched")
            self.assertEqual(reproducibility.recommended_human_decision, "review_blockers")
            self.assertEqual(reproducibility.action_readiness, "blocked")
            self.assertFalse(reproducibility.blockers)
            self.assertTrue(reproducibility.mismatches)
            self.assertFalse(reproducibility.digest_match)
            self.assertIn("$.summary.input_count", " ".join(reproducibility.mismatches))

    def test_operator_evidence_intake_reproducibility_blocks_missing_checked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                root / "missing-intake.json",
            )

            self.assertEqual(reproducibility.reproducibility_status, "blocked_input")
            self.assertEqual(reproducibility.action_readiness, "blocked")
            self.assertIn("checked report file is missing", " ".join(reproducibility.blockers))

    def test_operator_evidence_intake_reproducibility_blocks_stale_manifest_digest(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            clean_manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            clean_report = build_operator_evidence_intake_report(
                load_operator_evidence_intake_manifest(clean_manifest_path)
            )
            checked_path = root / "intake.json"
            checked_path.write_text(
                render_operator_evidence_intake_report_json(clean_report),
                encoding="utf-8",
            )
            stale_manifest_path = self._write_operator_intake_manifest_file(
                root,
                manifest,
                first_expected_digest="0" * 64,
            )

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                stale_manifest_path,
                checked_path,
            )

            self.assertEqual(reproducibility.reproducibility_status, "blocked_input")
            self.assertEqual(reproducibility.action_readiness, "blocked")
            self.assertIn("digest mismatch", " ".join(reproducibility.blockers))

    def test_operator_evidence_intake_reproducibility_blocks_malformed_checked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            checked_path = root / "intake.json"
            checked_path.write_text("{not-json", encoding="utf-8")

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                checked_path,
            )

            self.assertEqual(reproducibility.reproducibility_status, "blocked_input")
            self.assertIn("checked report JSON is malformed", " ".join(reproducibility.blockers))

    def test_operator_evidence_intake_reproducibility_blocks_mutating_checked_report(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            report = build_operator_evidence_intake_report(
                load_operator_evidence_intake_manifest(manifest_path)
            )
            mutating_payload = report.to_dict()
            mutating_payload["state_change"] = "canonical-mutation"
            checked_path = root / "intake.json"
            checked_path.write_text(
                json.dumps(mutating_payload, indent=2, sort_keys=True),
                encoding="utf-8",
            )

            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                checked_path,
            )

            self.assertEqual(reproducibility.reproducibility_status, "blocked_input")
            self.assertIn("state_change none", " ".join(reproducibility.blockers))

    def test_operator_evidence_intake_reproducibility_blocks_root_escape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            outside_report = root.parent / "outside-intake.json"
            outside_report.write_text("{}", encoding="utf-8")
            try:
                reproducibility = check_operator_evidence_intake_reproducibility(
                    root,
                    manifest_path,
                    outside_report,
                )
            finally:
                outside_report.unlink(missing_ok=True)

            self.assertEqual(reproducibility.reproducibility_status, "blocked_input")
            self.assertIn("escapes project root", " ".join(reproducibility.blockers))

    def test_operator_evidence_intake_reproducibility_json_and_markdown_are_boundary_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            manifest = self._write_clean_operator_intake_artifacts(root)
            manifest_path = self._write_operator_intake_manifest_file(root, manifest)
            report = build_operator_evidence_intake_report(
                load_operator_evidence_intake_manifest(manifest_path)
            )
            checked_path = root / "intake.json"
            checked_path.write_text(render_operator_evidence_intake_report_json(report), encoding="utf-8")
            reproducibility = check_operator_evidence_intake_reproducibility(
                root,
                manifest_path,
                checked_path,
            )

            json_payload = json.loads(render_operator_evidence_intake_reproducibility_json(reproducibility))
            markdown = render_operator_evidence_intake_reproducibility_markdown(reproducibility)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["reproducibility_status"], "reproducible")
            self.assertTrue(json_payload["guardrails"]["reproducibility_check_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["report_reproducible_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["checked_artifact_mismatch_is_review_evidence_only"])
            self.assertIn("# Epistemic Readiness Operator Evidence Intake Reproducibility Check", markdown)
            self.assertIn("reproducibility_check_is_not_permission: true", markdown)
            self.assertIn("digest_equality_is_not_truth: true", markdown)
            self.assertIn("report_reproducible_is_not_permission: true", markdown)
            self.assertIn("## Blockers", markdown)
            self.assertIn("## Mismatches", markdown)
            self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_intake_reproducibility_rejects_incoherent_reports(self) -> None:
        digest_a = "a" * 64
        digest_b = "b" * 64

        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeReproducibilityReport(
                manifest_path="intake.toml",
                checked_report_path="intake.json",
                regenerated_report_digest=digest_a,
                checked_report_digest=digest_b,
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceIntakeReproducibilityReport(
                manifest_path="intake.toml",
                checked_report_path="intake.json",
                regenerated_report_digest=digest_a,
                checked_report_digest=digest_a,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_provenance_index_summarizes_clean_chain_without_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "a.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "state_change": "none",
                        "authority": "non-authoritative; advisory artifact A only",
                        "summary": {
                            "action_readiness": "advisory_report_allowed",
                            "blocker_count": 0,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (root / "b.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "state_change": "none",
                        "authority": "non-authoritative; advisory artifact B only",
                        "summary": {
                            "recommended_human_decision": "none",
                            "blocked": False,
                        },
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            (root / "manifest.toml").write_text(
                'schema_version = "1"\n'
                'state_change = "none"\n'
                'authority = "non-authoritative; advisory manifest only"\n',
                encoding="utf-8",
            )
            specs = (
                OperatorEvidenceProvenanceArtifactSpec("manifest", "manifest.toml", "toml"),
                OperatorEvidenceProvenanceArtifactSpec("a", "a.json", "json", ("manifest",)),
                OperatorEvidenceProvenanceArtifactSpec("b", "b.json", "json", ("a",)),
            )

            report = build_operator_evidence_provenance_index(root, specs)

            self.assertFalse(report.blocked)
            self.assertEqual(report.artifact_count, 3)
            self.assertEqual(report.present_count, 3)
            self.assertEqual(report.dependency_edge_count, 2)
            self.assertEqual(report.action_readiness, "advisory_report_allowed")
            self.assertEqual(report.recommended_human_decision, "none")
            self.assertEqual(len(report.digest_manifest), 64)
            self.assertIn("action_readiness=advisory_report_allowed", report.artifacts[1].summary)

    def test_operator_evidence_provenance_index_blocks_missing_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            specs = (
                OperatorEvidenceProvenanceArtifactSpec("missing", "missing.json", "json"),
            )

            report = build_operator_evidence_provenance_index(root, specs)

            self.assertTrue(report.blocked)
            self.assertEqual(report.action_readiness, "blocked")
            self.assertIn("artifact file is missing", " ".join(report.artifacts[0].blockers))

    def test_operator_evidence_provenance_index_blocks_malformed_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "bad.json").write_text("{not-json", encoding="utf-8")
            specs = (
                OperatorEvidenceProvenanceArtifactSpec("bad", "bad.json", "json"),
            )

            report = build_operator_evidence_provenance_index(root, specs)

            self.assertTrue(report.blocked)
            self.assertEqual(report.artifacts[0].parse_status, "malformed_json")
            self.assertIn("artifact JSON is malformed", " ".join(report.artifacts[0].blockers))

    def test_operator_evidence_provenance_index_blocks_mutating_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "mutating.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "state_change": "canonical-mutation",
                        "authority": "non-authoritative; advisory artifact only",
                        "summary": {"blocker_count": 0},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            specs = (
                OperatorEvidenceProvenanceArtifactSpec("mutating", "mutating.json", "json"),
            )

            report = build_operator_evidence_provenance_index(root, specs)

            self.assertTrue(report.blocked)
            self.assertIn("state_change none", " ".join(report.artifacts[0].blockers))

    def test_operator_evidence_provenance_index_blocks_root_escape_and_cerebro_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            outside_path = root.parent / f"outside-{root.name}.json"
            outside_path.write_text("{}", encoding="utf-8")
            try:
                specs = (
                    OperatorEvidenceProvenanceArtifactSpec("outside", str(outside_path), "json"),
                    OperatorEvidenceProvenanceArtifactSpec(
                        "state",
                        ".cerebro/state.json",
                        "json",
                    ),
                )

                report = build_operator_evidence_provenance_index(root, specs)
            finally:
                outside_path.unlink(missing_ok=True)

            self.assertTrue(report.blocked)
            blockers = " ".join(
                blocker
                for artifact in report.artifacts
                for blocker in artifact.blockers
            )
            self.assertIn("escapes project root", blockers)
            self.assertIn("canonical state boundary", blockers)

    def test_operator_evidence_provenance_index_reports_duplicate_and_missing_dependency_specs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for name in ("a.json", "b.json"):
                (root / name).write_text(
                    json.dumps(
                        {
                            "schema_version": "1",
                            "state_change": "none",
                            "authority": "non-authoritative; advisory artifact only",
                            "summary": {"blocker_count": 0},
                        },
                        sort_keys=True,
                    ),
                    encoding="utf-8",
                )
            specs = (
                OperatorEvidenceProvenanceArtifactSpec("a", "a.json", "json"),
                OperatorEvidenceProvenanceArtifactSpec("a", "b.json", "json", ("missing",)),
            )

            report = build_operator_evidence_provenance_index(root, specs)

            self.assertTrue(report.blocked)
            self.assertIn("duplicate artifact id declared: a", report.blockers)
            self.assertIn(
                "artifact a declares unknown upstream artifact: missing",
                report.blockers,
            )

    def test_operator_evidence_provenance_index_json_and_markdown_are_boundary_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "artifact.json").write_text(
                json.dumps(
                    {
                        "schema_version": "1",
                        "state_change": "none",
                        "authority": "non-authoritative; advisory artifact only",
                        "summary": {"action_readiness": "advisory_report_allowed"},
                    },
                    sort_keys=True,
                ),
                encoding="utf-8",
            )
            report = build_operator_evidence_provenance_index(
                root,
                (
                    OperatorEvidenceProvenanceArtifactSpec(
                        "artifact",
                        "artifact.json",
                        "json",
                    ),
                ),
            )

            json_payload = json.loads(render_operator_evidence_provenance_index_json(report))
            markdown = render_operator_evidence_provenance_index_markdown(report)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["action_readiness"], "advisory_report_allowed")
            self.assertTrue(json_payload["guardrails"]["provenance_index_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["provenance_index_is_not_source_registry"])
            self.assertTrue(json_payload["guardrails"]["dependency_map_is_not_canonical_graph"])
            self.assertIn("# Epistemic Readiness Operator Evidence Provenance Index", markdown)
            self.assertIn("provenance_index_is_not_permission: true", markdown)
            self.assertIn("dependency_map_is_not_canonical_graph: true", markdown)
            self.assertIn("digest_is_not_truth: true", markdown)
            self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_provenance_index_rejects_incoherent_report_state(self) -> None:
        with self.assertRaises(ValueError):
            OperatorEvidenceProvenanceIndexReport(
                artifacts=(),
                state_change="canonical-mutation",
            )

    def test_operator_evidence_provenance_stress_matrix_covers_degraded_index_inputs_without_permission(self) -> None:
        report = build_operator_evidence_provenance_stress_matrix()

        self.assertEqual(len(report.scenarios), 9)
        self.assertEqual(report.pass_count, 9)
        self.assertEqual(report.fail_count, 0)
        self.assertTrue(report.all_scenarios_passed)
        self.assertEqual(report.blocker_count, 7)
        self.assertEqual(report.boundary_error_count, 4)
        self.assertEqual(report.text_digest_only_count, 1)

        decisions = report.to_dict()["summary"]["decisions"]
        self.assertEqual(
            decisions["clean_provenance_chain"],
            {
                "recommended_human_decision": "none",
                "action_readiness": "advisory_report_allowed",
                "boundary_error": False,
            },
        )
        self.assertEqual(
            decisions["text_digest_only_report"],
            {
                "recommended_human_decision": "none",
                "action_readiness": "advisory_report_allowed",
                "boundary_error": False,
            },
        )
        for scenario_id in (
            "missing_artifact",
            "malformed_json",
            "mutating_artifact",
            "root_escape",
            "cerebro_state_target",
            "duplicate_artifact_id",
            "missing_upstream_dependency",
        ):
            self.assertEqual(decisions[scenario_id]["recommended_human_decision"], "review_blockers")
            self.assertEqual(decisions[scenario_id]["action_readiness"], "blocked")

    def test_operator_evidence_provenance_stress_matrix_keeps_boundary_errors_visible(self) -> None:
        report = build_operator_evidence_provenance_stress_matrix()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertIn("escapes project root", scenarios["root_escape"].observed_error)
        self.assertIn("canonical state boundary", scenarios["cerebro_state_target"].observed_error)
        self.assertIn("duplicate artifact id", scenarios["duplicate_artifact_id"].observed_error)
        self.assertIn("unknown upstream artifact", scenarios["missing_upstream_dependency"].observed_error)
        self.assertEqual(scenarios["text_digest_only_report"].text_digest_only_count, 1)
        self.assertEqual(scenarios["text_digest_only_report"].blocker_count, 0)

    def test_operator_evidence_provenance_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_evidence_provenance_stress_matrix()

        json_payload = json.loads(render_operator_evidence_provenance_stress_matrix_json(report))
        markdown = render_operator_evidence_provenance_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["scenario_count"], 9)
        self.assertEqual(json_payload["summary"]["fail_count"], 0)
        self.assertTrue(json_payload["guardrails"]["provenance_stress_matrix_is_not_permission"])
        self.assertTrue(json_payload["guardrails"]["provenance_stress_matrix_is_not_source_registry"])
        self.assertTrue(json_payload["guardrails"]["dependency_map_is_not_canonical_graph"])
        self.assertTrue(json_payload["guardrails"]["text_digest_only_is_not_truth"])
        self.assertIn("# Epistemic Readiness Operator Evidence Provenance Stress Matrix", markdown)
        self.assertIn("provenance_stress_matrix_is_not_permission: true", markdown)
        self.assertIn("provenance_stress_matrix_is_not_source_registry: true", markdown)
        self.assertIn("dependency_map_is_not_canonical_graph: true", markdown)
        self.assertIn("artifact_digest_is_not_truth: true", markdown)
        self.assertIn("text_digest_only_is_not_truth: true", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_provenance_stress_matrix_rejects_duplicate_partial_or_mutating_scenarios(self) -> None:
        report = build_operator_evidence_provenance_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceProvenanceStressMatrixReport(
                scenarios=(duplicate, duplicate) + report.scenarios[2:],
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceProvenanceStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorEvidenceProvenanceStressMatrixReport(
                scenarios=report.scenarios,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_review_capsule_summarizes_current_checked_chain_without_permission(self) -> None:
        capsule = build_operator_evidence_review_capsule(Path.cwd())

        self.assertEqual(capsule.review_status, "review_clear")
        self.assertEqual(capsule.recommended_human_decision, "none")
        self.assertEqual(capsule.action_readiness, "advisory_report_allowed")
        self.assertEqual(capsule.decision_posture, "no_action")
        self.assertEqual(capsule.decision_posture_human_decision, "none")
        self.assertEqual(capsule.reproducibility_status, "reproducible")
        self.assertIs(capsule.digest_match, True)
        self.assertEqual(capsule.provenance_artifact_count, 20)
        self.assertEqual(capsule.provenance_present_count, 20)
        self.assertEqual(capsule.stress_scenario_count, 9)
        self.assertEqual(capsule.stress_pass_count, 9)
        self.assertEqual(capsule.stress_fail_count, 0)
        self.assertEqual(capsule.stress_blocker_count, 7)
        self.assertEqual(capsule.stress_boundary_error_count, 4)
        self.assertEqual(capsule.stress_text_digest_only_count, 1)
        self.assertEqual(capsule.blockers, ())
        self.assertEqual(capsule.input_blocker_count, 0)

    def test_operator_evidence_review_capsule_blocks_missing_and_malformed_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_review_capsule_fixture(root)
            (root / "bad.json").write_text("{not-json", encoding="utf-8")

            capsule = build_operator_evidence_review_capsule(
                root,
                {
                    "operator_decision_packet": "bad.json",
                    "intake_reproducibility": "missing.json",
                    "provenance_index": "provenance.json",
                    "provenance_stress_matrix": "stress.json",
                },
            )

            self.assertEqual(capsule.review_status, "blocked_review")
            self.assertEqual(capsule.recommended_human_decision, "review_blockers")
            self.assertEqual(capsule.action_readiness, "blocked")
            blockers = " ".join(capsule.blockers)
            self.assertIn("input JSON is malformed", blockers)
            self.assertIn("input file is missing", blockers)
            self.assertIn("operator_decision_packet", capsule.missing_review_evidence)
            self.assertIn("intake_reproducibility", capsule.missing_review_evidence)

    def test_operator_evidence_review_capsule_blocks_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_review_capsule_fixture(root)
            outside = root.parent / f"outside-{root.name}.json"
            outside.write_text(json.dumps(self._review_packet_payload()), encoding="utf-8")
            try:
                capsule = build_operator_evidence_review_capsule(
                    root,
                    {
                        "operator_decision_packet": str(outside),
                        "intake_reproducibility": ".cerebro/state.json",
                        "provenance_index": "provenance.json",
                        "provenance_stress_matrix": "stress.json",
                    },
                )
            finally:
                outside.unlink(missing_ok=True)

            self.assertEqual(capsule.action_readiness, "blocked")
            blockers = " ".join(capsule.blockers)
            self.assertIn("path escapes project root", blockers)
            self.assertIn("canonical state boundary", blockers)

    def test_operator_evidence_review_capsule_json_and_markdown_are_boundary_explicit(self) -> None:
        capsule = build_operator_evidence_review_capsule(Path.cwd())

        json_payload = json.loads(render_operator_evidence_review_capsule_json(capsule))
        markdown = render_operator_evidence_review_capsule_markdown(capsule)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["review_status"], "review_clear")
        self.assertEqual(json_payload["summary"]["action_readiness"], "advisory_report_allowed")
        self.assertEqual(json_payload["summary"]["decision_posture"], "no_action")
        self.assertTrue(json_payload["guardrails"]["review_capsule_is_not_permission"])
        self.assertTrue(json_payload["guardrails"]["review_capsule_is_not_source_registry"])
        self.assertTrue(json_payload["guardrails"]["review_capsule_is_not_canonical_evidence_graph"])
        self.assertTrue(json_payload["guardrails"]["stress_pass_is_not_permission"])
        self.assertIn("# Epistemic Readiness Operator Evidence Review Capsule", markdown)
        self.assertIn("review_capsule_is_not_permission: true", markdown)
        self.assertIn("review_capsule_is_not_runtime_gate: true", markdown)
        self.assertIn("review_capsule_is_not_source_registry: true", markdown)
        self.assertIn("stress_pass_is_not_permission: true", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_review_capsule_rejects_incoherent_state(self) -> None:
        capsule = build_operator_evidence_review_capsule(Path.cwd())

        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsule(
                inputs=capsule.inputs,
                decision_posture=capsule.decision_posture,
                decision_posture_human_decision=capsule.decision_posture_human_decision,
                reproducibility_status=capsule.reproducibility_status,
                digest_match=capsule.digest_match,
                provenance_artifact_count=capsule.provenance_artifact_count,
                provenance_present_count=capsule.provenance_present_count,
                provenance_dependency_edge_count=capsule.provenance_dependency_edge_count,
                provenance_digest_manifest=capsule.provenance_digest_manifest,
                stress_scenario_count=capsule.stress_scenario_count,
                stress_pass_count=capsule.stress_pass_count,
                stress_fail_count=capsule.stress_fail_count,
                stress_blocker_count=capsule.stress_blocker_count,
                stress_boundary_error_count=capsule.stress_boundary_error_count,
                stress_text_digest_only_count=capsule.stress_text_digest_only_count,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_review_capsule_reproducibility_accepts_current_artifacts(self) -> None:
        report = check_operator_evidence_review_capsule_reproducibility(Path.cwd())
        payload = report.to_dict()

        self.assertEqual(report.reproducibility_status, "reproducible")
        self.assertEqual(report.recommended_human_decision, "none")
        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.mismatch_count, 0)
        self.assertEqual(report.missing_artifact_count, 0)
        self.assertEqual(len(report.artifacts), 2)
        self.assertTrue(report.artifacts[0].digest_match)
        self.assertTrue(report.artifacts[1].digest_match)
        self.assertTrue(payload["guardrails"]["review_capsule_reproducibility_is_not_permission"])
        self.assertTrue(payload["guardrails"]["digest_equality_is_not_truth"])
        self.assertIn("treat reproducibility as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_review_capsule_reproducibility_blocks_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_checked_review_capsule_artifacts(root)
            json_path = root / "capsule.json"
            markdown_path = root / "capsule.md"

            stale_payload = json.loads(json_path.read_text(encoding="utf-8"))
            stale_payload["summary"]["input_count"] = 99
            json_path.write_text(
                json.dumps(stale_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            markdown_path.write_text(
                markdown_path.read_text(encoding="utf-8").replace(
                    "- review_status: review_clear",
                    "- review_status: stale",
                ),
                encoding="utf-8",
            )

            report = check_operator_evidence_review_capsule_reproducibility(
                root,
                "capsule.json",
                "capsule.md",
                input_paths=input_paths,
            )

            self.assertEqual(report.reproducibility_status, "stale_or_mismatched")
            self.assertEqual(report.recommended_human_decision, "review_blockers")
            self.assertEqual(report.action_readiness, "blocked")
            self.assertEqual(report.missing_artifact_count, 0)
            self.assertGreaterEqual(report.mismatch_count, 2)
            self.assertFalse(report.artifacts[0].digest_match)
            self.assertFalse(report.artifacts[1].digest_match)
            self.assertIn("$.summary.input_count", " ".join(report.mismatches))
            self.assertIn("checked Markdown text", " ".join(report.mismatches))

    def test_operator_evidence_review_capsule_reproducibility_blocks_missing_malformed_and_mutating_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_checked_review_capsule_artifacts(root)
            markdown_path = root / "capsule.md"

            missing = check_operator_evidence_review_capsule_reproducibility(
                root,
                "missing.json",
                markdown_path,
                input_paths=input_paths,
            )
            self.assertEqual(missing.action_readiness, "blocked")
            self.assertEqual(missing.missing_artifact_count, 1)
            self.assertIn("checked artifact is missing", " ".join(missing.blockers))

            bad_json = root / "bad.json"
            bad_json.write_text("{not-json", encoding="utf-8")
            malformed = check_operator_evidence_review_capsule_reproducibility(
                root,
                bad_json,
                markdown_path,
                input_paths=input_paths,
            )
            self.assertEqual(malformed.action_readiness, "blocked")
            self.assertIn("checked JSON is malformed", " ".join(malformed.blockers))

            mutating_payload = json.loads((root / "capsule.json").read_text(encoding="utf-8"))
            mutating_payload["state_change"] = "canonical-mutation"
            mutating_json = root / "mutating.json"
            mutating_json.write_text(
                json.dumps(mutating_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            mutating = check_operator_evidence_review_capsule_reproducibility(
                root,
                mutating_json,
                markdown_path,
                input_paths=input_paths,
            )
            self.assertEqual(mutating.action_readiness, "blocked")
            self.assertIn("state_change none", " ".join(mutating.blockers))

    def test_operator_evidence_review_capsule_reproducibility_blocks_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_checked_review_capsule_artifacts(root)
            outside = root.parent / f"outside-{root.name}.json"
            outside.write_text((root / "capsule.json").read_text(encoding="utf-8"), encoding="utf-8")
            try:
                report = check_operator_evidence_review_capsule_reproducibility(
                    root,
                    str(outside),
                    ".cerebro/capsule.md",
                    input_paths=input_paths,
                )
            finally:
                outside.unlink(missing_ok=True)

            self.assertEqual(report.action_readiness, "blocked")
            blockers = " ".join(report.blockers)
            self.assertIn("path escapes project root", blockers)
            self.assertIn("canonical state boundary", blockers)

    def test_operator_evidence_review_capsule_reproducibility_json_and_markdown_are_boundary_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_checked_review_capsule_artifacts(root)
            report = check_operator_evidence_review_capsule_reproducibility(
                root,
                "capsule.json",
                "capsule.md",
                input_paths=input_paths,
            )

            json_payload = json.loads(render_operator_evidence_review_capsule_reproducibility_json(report))
            markdown = render_operator_evidence_review_capsule_reproducibility_markdown(report)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["artifact_count"], 2)
            self.assertTrue(json_payload["guardrails"]["review_capsule_reproducibility_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["review_capsule_reproducibility_is_not_source_registry"])
            self.assertTrue(json_payload["guardrails"]["digest_equality_is_not_truth"])
            self.assertIn("# Epistemic Readiness Operator Evidence Review Capsule Reproducibility Check", markdown)
            self.assertIn("review_capsule_reproducibility_is_not_permission: true", markdown)
            self.assertIn("review_capsule_reproducibility_is_not_runtime_gate: true", markdown)
            self.assertIn("artifact_reproducible_is_not_permission: true", markdown)
            self.assertIn("stale_artifact_is_review_evidence_only: true", markdown)
            self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_review_capsule_reproducibility_rejects_incoherent_state(self) -> None:
        report = check_operator_evidence_review_capsule_reproducibility(Path.cwd())

        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleReproducibilityReport(
                artifacts=report.artifacts,
                state_change="canonical-mutation",
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleReproducibilityReport(
                artifacts=(report.artifacts[0], report.artifacts[0]),
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleArtifactCheck(
                artifact_id="unknown",
                path="artifact.json",
                exists=True,
                check_status="matched",
                checked_digest="a" * 64,
                regenerated_digest="a" * 64,
                digest_match=True,
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleArtifactCheck(
                artifact_id="review_capsule_json",
                path="artifact.json",
                exists=True,
                check_status="matched",
                checked_digest="a" * 64,
                regenerated_digest="b" * 64,
                digest_match=False,
            )

    def test_operator_evidence_review_capsule_stress_matrix_covers_degraded_inputs_without_permission(self) -> None:
        report = build_operator_evidence_review_capsule_stress_matrix()
        payload = report.to_dict()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertEqual(payload["summary"]["scenario_count"], 9)
        self.assertEqual(report.pass_count, 9)
        self.assertEqual(report.fail_count, 0)
        self.assertTrue(report.all_scenarios_passed)
        self.assertEqual(
            scenarios["clean_review_capsule"].observed_recommended_human_decision,
            "none",
        )
        self.assertEqual(
            scenarios["clean_review_capsule"].observed_action_readiness,
            "advisory_report_allowed",
        )
        self.assertEqual(scenarios["clean_review_capsule"].observed_review_status, "review_clear")
        for scenario_id, scenario in scenarios.items():
            if scenario_id == "clean_review_capsule":
                continue
            self.assertEqual(scenario.observed_recommended_human_decision, "review_blockers")
            self.assertEqual(scenario.observed_action_readiness, "blocked")
            self.assertEqual(scenario.observed_review_status, "blocked_review")
            self.assertTrue(scenario.observed_error)
            self.assertGreater(scenario.blocker_count, 0)
        self.assertTrue(payload["guardrails"]["review_capsule_stress_matrix_is_not_permission"])
        self.assertTrue(payload["guardrails"]["review_capsule_output_is_not_permission"])
        self.assertTrue(payload["guardrails"]["passing_scenario_is_not_permission"])

    def test_operator_evidence_review_capsule_stress_matrix_keeps_boundary_errors_visible(self) -> None:
        report = build_operator_evidence_review_capsule_stress_matrix()
        scenarios = {scenario.scenario_id: scenario for scenario in report.scenarios}

        self.assertIn("path escapes project root", scenarios["root_escape_input"].observed_error)
        self.assertIn("canonical state boundary", scenarios["cerebro_state_input"].observed_error)
        self.assertGreater(scenarios["root_escape_input"].boundary_error_count, 0)
        self.assertGreater(scenarios["cerebro_state_input"].boundary_error_count, 0)
        self.assertGreaterEqual(report.boundary_error_count, 2)

    def test_operator_evidence_review_capsule_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_evidence_review_capsule_stress_matrix()

        json_payload = json.loads(render_operator_evidence_review_capsule_stress_matrix_json(report))
        markdown = render_operator_evidence_review_capsule_stress_matrix_markdown(report)

        self.assertEqual(json_payload["schema_version"], "1")
        self.assertEqual(json_payload["state_change"], "none")
        self.assertEqual(json_payload["summary"]["scenario_count"], 9)
        self.assertEqual(json_payload["summary"]["pass_count"], 9)
        self.assertEqual(json_payload["summary"]["fail_count"], 0)
        self.assertIn("# Epistemic Readiness Operator Evidence Review Capsule Stress Matrix", markdown)
        self.assertIn("review_capsule_stress_matrix_is_not_permission: true", markdown)
        self.assertIn("review_capsule_output_is_not_permission: true", markdown)
        self.assertIn("passing_scenario_is_not_permission: true", markdown)
        self.assertIn("digest_equality_is_not_truth: true", markdown)
        self.assertIn("degraded_capsule_evidence_is_review_evidence_only: true", markdown)
        self.assertIn("| `failed_stress_input` | `review_blockers` | `review_blockers` |", markdown)
        self.assertIn("## Visible Errors", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_review_capsule_stress_matrix_rejects_duplicate_partial_or_mutating_scenarios(self) -> None:
        report = build_operator_evidence_review_capsule_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleStressMatrixReport(
                scenarios=(duplicate, duplicate) + report.scenarios[2:],
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorEvidenceReviewCapsuleStressMatrixReport(
                scenarios=report.scenarios,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_final_review_index_summarizes_current_chain_without_permission(self) -> None:
        report = build_operator_evidence_final_review_index(Path.cwd())
        payload = report.to_dict()

        self.assertEqual(report.review_status, "final_review_clear")
        self.assertEqual(report.recommended_human_decision, "none")
        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertEqual(payload["summary"]["input_count"], 3)
        self.assertEqual(payload["summary"]["blocker_count"], 0)
        self.assertEqual(payload["summary"]["missing_review_evidence_count"], 0)
        self.assertEqual(payload["summary"]["capsule_review_status"], "review_clear")
        self.assertEqual(payload["summary"]["stress_scenario_count"], 9)
        self.assertEqual(payload["summary"]["stress_pass_count"], 9)
        self.assertEqual(payload["summary"]["stress_fail_count"], 0)
        self.assertEqual(payload["summary"]["reproducibility_status"], "reproducible")
        self.assertIs(payload["summary"]["json_digest_match"], True)
        self.assertIs(payload["summary"]["markdown_digest_match"], True)
        self.assertTrue(payload["guardrails"]["final_review_index_is_not_permission"])
        self.assertTrue(payload["guardrails"]["review_clear_is_not_permission"])

    def test_operator_evidence_final_review_index_blocks_missing_malformed_and_mutating_inputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_final_review_index_fixture(root)
            (root / "stress.json").write_text("{not-json", encoding="utf-8")
            repro_payload = json.loads((root / "repro.json").read_text(encoding="utf-8"))
            repro_payload["state_change"] = "canonical-mutation"
            (root / "repro.json").write_text(json.dumps(repro_payload), encoding="utf-8")

            report = build_operator_evidence_final_review_index(
                root,
                {
                    "review_capsule": "missing.json",
                    "review_capsule_stress_matrix": input_paths["review_capsule_stress_matrix"],
                    "review_capsule_reproducibility": input_paths[
                        "review_capsule_reproducibility"
                    ],
                },
            )

            blockers = " ".join(report.blockers)
            self.assertEqual(report.recommended_human_decision, "review_blockers")
            self.assertEqual(report.action_readiness, "blocked")
            self.assertIn("final review input is missing", blockers)
            self.assertIn("final review input is malformed", blockers)
            self.assertIn("state_change none", blockers)
            self.assertIn("review_capsule", report.missing_review_evidence)

    def test_operator_evidence_final_review_index_blocks_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_final_review_index_fixture(root)
            outside = root.parent / f"outside-{root.name}.json"
            outside.write_text((root / "capsule.json").read_text(encoding="utf-8"), encoding="utf-8")
            try:
                report = build_operator_evidence_final_review_index(
                    root,
                    {
                        "review_capsule": str(outside),
                        "review_capsule_stress_matrix": ".cerebro/state.json",
                        "review_capsule_reproducibility": input_paths[
                            "review_capsule_reproducibility"
                        ],
                    },
                )
            finally:
                outside.unlink(missing_ok=True)

            blockers = " ".join(report.blockers)
            self.assertEqual(report.action_readiness, "blocked")
            self.assertIn("path escapes project root", blockers)
            self.assertIn("canonical state boundary", blockers)

    def test_operator_evidence_final_review_index_blocks_failed_stress_or_reproducibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_final_review_index_fixture(root)
            stress_payload = json.loads((root / "stress.json").read_text(encoding="utf-8"))
            stress_payload["summary"]["pass_count"] = 8
            stress_payload["summary"]["fail_count"] = 1
            stress_payload["summary"]["all_scenarios_passed"] = False
            (root / "stress.json").write_text(json.dumps(stress_payload), encoding="utf-8")
            repro_payload = json.loads((root / "repro.json").read_text(encoding="utf-8"))
            repro_payload["summary"]["mismatch_count"] = 1
            repro_payload["summary"]["json_digest_match"] = False
            (root / "repro.json").write_text(json.dumps(repro_payload), encoding="utf-8")

            report = build_operator_evidence_final_review_index(root, input_paths)

            blockers = " ".join(report.blockers)
            self.assertEqual(report.review_status, "blocked_review")
            self.assertIn("pass_count must equal scenario_count", blockers)
            self.assertIn("fail_count must be 0", blockers)
            self.assertIn("all_scenarios_passed must be true", blockers)
            self.assertIn("mismatch_count must be 0", blockers)
            self.assertIn("json_digest_match must be true", blockers)

    def test_operator_evidence_final_review_index_json_and_markdown_are_boundary_explicit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_final_review_index_fixture(root)
            report = build_operator_evidence_final_review_index(root, input_paths)

            json_payload = json.loads(render_operator_evidence_final_review_index_json(report))
            markdown = render_operator_evidence_final_review_index_markdown(report)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["review_status"], "final_review_clear")
            self.assertTrue(json_payload["guardrails"]["final_review_index_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["final_review_index_is_not_runtime_gate"])
            self.assertTrue(json_payload["guardrails"]["review_clear_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["digest_equality_is_not_truth"])
            self.assertIn("# Epistemic Readiness Operator Evidence Final Review Index", markdown)
            self.assertIn("final_review_index_is_not_permission: true", markdown)
            self.assertIn("review_clear_is_not_permission: true", markdown)
            self.assertIn("stress_pass_is_not_permission: true", markdown)
            self.assertIn("reproducibility_is_not_permission: true", markdown)
            self.assertIn("digest_equality_is_not_truth: true", markdown)
            self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_final_review_index_rejects_incoherent_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            input_paths = self._write_final_review_index_fixture(root)
            report = build_operator_evidence_final_review_index(root, input_paths)

            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewIndexReport(
                    inputs=report.inputs,
                    state_change="canonical-mutation",
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewIndexReport(inputs=report.inputs[:-1])
            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewInput(
                    input_id="unknown",
                    path="artifact.json",
                    exists=True,
                    parse_status="parsed",
                    digest="a" * 64,
                    summary={},
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewInput(
                    input_id="review_capsule",
                    path="artifact.json",
                    exists=True,
                    parse_status="parsed",
                    digest="not-a-digest",
                    summary={},
                )

    def test_operator_evidence_final_review_index_stress_matrix_covers_degraded_inputs(self) -> None:
        report = build_operator_evidence_final_review_index_stress_matrix()
        payload = report.to_dict()

        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["state_change"], "none")
        self.assertEqual(payload["summary"]["scenario_count"], 10)
        self.assertEqual(report.pass_count, 10)
        self.assertEqual(report.fail_count, 0)
        self.assertTrue(report.all_scenarios_passed)
        self.assertGreater(report.degraded_blocker_count, 0)
        self.assertGreaterEqual(report.boundary_error_count, 2)
        self.assertTrue(
            payload["guardrails"]["final_review_index_stress_matrix_is_not_permission"]
        )
        self.assertTrue(payload["guardrails"]["final_review_index_output_is_not_permission"])

        decisions = payload["summary"]["decisions"]
        self.assertEqual(
            decisions["clean_final_review_index"]["recommended_human_decision"],
            "none",
        )
        self.assertEqual(
            decisions["clean_final_review_index"]["action_readiness"],
            "advisory_report_allowed",
        )
        for scenario in report.scenarios:
            if scenario.scenario_id == "clean_final_review_index":
                self.assertEqual(scenario.observed_error, "")
                continue
            self.assertEqual(scenario.observed_recommended_human_decision, "review_blockers")
            self.assertEqual(scenario.observed_action_readiness, "blocked")
            self.assertEqual(scenario.observed_review_status, "blocked_review")
            self.assertTrue(scenario.observed_error)

    def test_operator_evidence_final_review_index_stress_matrix_json_and_markdown_are_boundary_explicit(self) -> None:
        report = build_operator_evidence_final_review_index_stress_matrix()

        json_payload = json.loads(render_operator_evidence_final_review_index_stress_matrix_json(report))
        markdown = render_operator_evidence_final_review_index_stress_matrix_markdown(report)

        self.assertEqual(json_payload["summary"]["scenario_count"], 10)
        self.assertEqual(json_payload["summary"]["pass_count"], 10)
        self.assertEqual(json_payload["summary"]["fail_count"], 0)
        self.assertIn("# Epistemic Readiness Operator Evidence Final Review Index Stress Matrix", markdown)
        self.assertIn("final_review_index_stress_matrix_is_not_permission: true", markdown)
        self.assertIn("final_review_index_output_is_not_permission: true", markdown)
        self.assertIn("passing_scenario_is_not_permission: true", markdown)
        self.assertIn("digest_equality_is_not_truth: true", markdown)
        self.assertIn("degraded_final_review_evidence_is_review_evidence_only: true", markdown)
        self.assertIn("## Must Not Apply", markdown)

    def test_operator_evidence_final_review_index_stress_matrix_rejects_incoherent_state(self) -> None:
        report = build_operator_evidence_final_review_index_stress_matrix()
        duplicate = report.scenarios[0]

        with self.assertRaises(ValueError):
            OperatorEvidenceFinalReviewIndexStressMatrixReport(
                scenarios=(duplicate, duplicate) + report.scenarios[2:]
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceFinalReviewIndexStressMatrixReport(scenarios=report.scenarios[:-1])
        with self.assertRaises(ValueError):
            OperatorEvidenceFinalReviewIndexStressMatrixReport(
                scenarios=report.scenarios,
                state_change="canonical-mutation",
            )
        with self.assertRaises(ValueError):
            OperatorEvidenceFinalReviewIndexStressScenario(
                scenario_id="clean_final_review_index",
                title="Bad state",
                purpose="prove rejected",
                expected_recommended_human_decision="none",
                expected_action_readiness="advisory_report_allowed",
                observed_recommended_human_decision="none",
                observed_action_readiness="advisory_report_allowed",
                observed_review_status="final_review_clear",
                review_summary="bad",
                blocker_count=0,
                input_blocker_count=0,
                missing_review_evidence_count=0,
                boundary_error_count=0,
                state_change="canonical-mutation",
            )

    def test_operator_evidence_final_review_index_stress_reproducibility_accepts_current_artifacts(self) -> None:
        report = check_operator_evidence_final_review_index_stress_reproducibility(Path.cwd())
        payload = report.to_dict()

        self.assertEqual(report.reproducibility_status, "reproducible")
        self.assertEqual(report.recommended_human_decision, "none")
        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.mismatch_count, 0)
        self.assertEqual(report.missing_artifact_count, 0)
        self.assertEqual(len(report.artifacts), 2)
        self.assertTrue(report.artifacts[0].digest_match)
        self.assertTrue(report.artifacts[1].digest_match)
        self.assertTrue(
            payload["guardrails"][
                "final_review_index_stress_reproducibility_is_not_permission"
            ]
        )
        self.assertTrue(payload["guardrails"]["digest_equality_is_not_truth"])
        self.assertIn("treat reproducibility as permission", payload["boundary"]["must_not_apply"])

    def test_operator_evidence_final_review_index_stress_reproducibility_blocks_stale_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stress = build_operator_evidence_final_review_index_stress_matrix()
            json_path = root / "stress.json"
            markdown_path = root / "stress.md"
            json_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_json(stress),
                encoding="utf-8",
            )
            markdown_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_markdown(stress),
                encoding="utf-8",
            )

            stale_payload = json.loads(json_path.read_text(encoding="utf-8"))
            stale_payload["summary"]["scenario_count"] = 99
            json_path.write_text(
                json.dumps(stale_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            markdown_path.write_text(
                markdown_path.read_text(encoding="utf-8").replace(
                    "- scenario_count: 10",
                    "- scenario_count: 99",
                ),
                encoding="utf-8",
            )

            report = check_operator_evidence_final_review_index_stress_reproducibility(
                root,
                "stress.json",
                "stress.md",
            )

            self.assertEqual(report.reproducibility_status, "stale_or_mismatched")
            self.assertEqual(report.recommended_human_decision, "review_blockers")
            self.assertEqual(report.action_readiness, "blocked")
            self.assertEqual(report.missing_artifact_count, 0)
            self.assertGreaterEqual(report.mismatch_count, 2)
            self.assertFalse(report.artifacts[0].digest_match)
            self.assertFalse(report.artifacts[1].digest_match)
            self.assertIn("$.summary.scenario_count", " ".join(report.mismatches))
            self.assertIn("checked Markdown text", " ".join(report.mismatches))

    def test_operator_evidence_final_review_index_stress_reproducibility_blocks_missing_malformed_and_mutating_artifacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stress = build_operator_evidence_final_review_index_stress_matrix()
            json_path = root / "stress.json"
            markdown_path = root / "stress.md"
            json_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_json(stress),
                encoding="utf-8",
            )
            markdown_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_markdown(stress),
                encoding="utf-8",
            )

            missing = check_operator_evidence_final_review_index_stress_reproducibility(
                root,
                "missing.json",
                markdown_path,
            )
            self.assertEqual(missing.action_readiness, "blocked")
            self.assertEqual(missing.missing_artifact_count, 1)
            self.assertIn("checked artifact is missing", " ".join(missing.blockers))

            bad_json = root / "bad.json"
            bad_json.write_text("{not-json", encoding="utf-8")
            malformed = check_operator_evidence_final_review_index_stress_reproducibility(
                root,
                bad_json,
                markdown_path,
            )
            self.assertEqual(malformed.action_readiness, "blocked")
            self.assertIn("checked JSON is malformed", " ".join(malformed.blockers))

            mutating_payload = json.loads(json_path.read_text(encoding="utf-8"))
            mutating_payload["state_change"] = "canonical-mutation"
            mutating_json = root / "mutating.json"
            mutating_json.write_text(
                json.dumps(mutating_payload, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            mutating = check_operator_evidence_final_review_index_stress_reproducibility(
                root,
                mutating_json,
                markdown_path,
            )
            self.assertEqual(mutating.action_readiness, "blocked")
            self.assertIn("state_change none", " ".join(mutating.blockers))

    def test_operator_evidence_final_review_index_stress_reproducibility_blocks_root_escape_and_cerebro_targets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stress = build_operator_evidence_final_review_index_stress_matrix()
            json_path = root / "stress.json"
            json_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_json(stress),
                encoding="utf-8",
            )
            outside = root.parent / f"outside-{root.name}.json"
            outside.write_text(json_path.read_text(encoding="utf-8"), encoding="utf-8")
            try:
                report = check_operator_evidence_final_review_index_stress_reproducibility(
                    root,
                    str(outside),
                    ".cerebro/stress.md",
                )
            finally:
                outside.unlink(missing_ok=True)

            self.assertEqual(report.action_readiness, "blocked")
            blockers = " ".join(report.blockers)
            self.assertIn("path escapes project root", blockers)
            self.assertIn("canonical state boundary", blockers)

    def test_operator_evidence_final_review_index_stress_reproducibility_json_markdown_and_incoherent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stress = build_operator_evidence_final_review_index_stress_matrix()
            json_path = root / "stress.json"
            markdown_path = root / "stress.md"
            json_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_json(stress),
                encoding="utf-8",
            )
            markdown_path.write_text(
                render_operator_evidence_final_review_index_stress_matrix_markdown(stress),
                encoding="utf-8",
            )
            report = check_operator_evidence_final_review_index_stress_reproducibility(
                root,
                "stress.json",
                "stress.md",
            )

            json_payload = json.loads(
                render_operator_evidence_final_review_index_stress_reproducibility_json(report)
            )
            markdown = render_operator_evidence_final_review_index_stress_reproducibility_markdown(
                report
            )

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["artifact_count"], 2)
            self.assertTrue(
                json_payload["guardrails"][
                    "final_review_index_stress_reproducibility_is_not_permission"
                ]
            )
            self.assertTrue(
                json_payload["guardrails"][
                    "final_review_index_stress_reproducibility_is_not_source_registry"
                ]
            )
            self.assertTrue(json_payload["guardrails"]["digest_equality_is_not_truth"])
            self.assertIn(
                "# Epistemic Readiness Operator Evidence Final Review Index Stress Reproducibility Check",
                markdown,
            )
            self.assertIn(
                "final_review_index_stress_reproducibility_is_not_permission: true",
                markdown,
            )
            self.assertIn(
                "final_review_index_stress_reproducibility_is_not_runtime_gate: true",
                markdown,
            )
            self.assertIn("artifact_reproducible_is_not_permission: true", markdown)
            self.assertIn("stale_artifact_is_review_evidence_only: true", markdown)
            self.assertIn("## Must Not Apply", markdown)

            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewIndexStressReproducibilityReport(
                    artifacts=report.artifacts,
                    state_change="canonical-mutation",
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewIndexStressReproducibilityReport(
                    artifacts=(report.artifacts[0], report.artifacts[0]),
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceFinalReviewIndexStressArtifactCheck(
                    artifact_id="unknown",
                    path="artifact.json",
                    exists=True,
                    check_status="matched",
                    checked_digest="a" * 64,
                    regenerated_digest="a" * 64,
                    digest_match=True,
                )

    def test_operator_evidence_chain_closeout_accepts_current_artifacts(self) -> None:
        report = build_operator_evidence_chain_closeout(Path.cwd())
        payload = report.to_dict()

        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["state_change"], "none")
        self.assertEqual(payload["summary"]["closeout_status"], "closed_until_new_evidence")
        self.assertEqual(payload["summary"]["recommended_human_decision"], "none")
        self.assertEqual(payload["summary"]["action_readiness"], "no_action")
        self.assertTrue(payload["summary"]["recursive_hardening_stopped"])
        self.assertEqual(payload["summary"]["input_count"], 3)
        self.assertEqual(payload["summary"]["blocker_count"], 0)
        self.assertTrue(payload["guardrails"]["closeout_is_not_permission"])
        self.assertTrue(payload["guardrails"]["recursive_stop_is_not_permanent_freeze"])
        self.assertTrue(payload["guardrails"]["digest_equality_is_not_truth"])
        self.assertIn("treat closeout as permission", payload["boundary"]["must_not_apply"])
        self.assertIn(
            "any upstream closeout input becomes missing, malformed, stale, mutating, or blocked",
            payload["reopen_triggers"],
        )

    def test_operator_evidence_chain_closeout_blocks_degraded_upstream_summaries(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paths = self._write_chain_closeout_fixture(root)

            index_payload = self._closeout_final_review_payload(
                review_status="blocked_review",
                recommended_human_decision="review_blockers",
                action_readiness="blocked",
                blocker_count=1,
            )
            (root / "index.json").write_text(json.dumps(index_payload, sort_keys=True), encoding="utf-8")
            blocked_index = build_operator_evidence_chain_closeout(root, paths)
            self.assertEqual(blocked_index.closeout_status, "blocked_closeout")
            self.assertEqual(blocked_index.recommended_human_decision, "review_blockers")
            self.assertEqual(blocked_index.action_readiness, "blocked")
            self.assertFalse(blocked_index.recursive_hardening_stopped)
            self.assertIn("final review index must be final_review_clear", " ".join(blocked_index.blockers))

            self._write_chain_closeout_fixture(root)
            stress_payload = self._closeout_stress_payload(
                pass_count=9,
                fail_count=1,
                all_scenarios_passed=False,
            )
            (root / "stress.json").write_text(json.dumps(stress_payload, sort_keys=True), encoding="utf-8")
            failed_stress = build_operator_evidence_chain_closeout(root, paths)
            self.assertEqual(failed_stress.closeout_status, "blocked_closeout")
            self.assertIn("fail_count must be 0", " ".join(failed_stress.blockers))

            self._write_chain_closeout_fixture(root)
            repro_payload = self._closeout_repro_payload(
                reproducibility_status="stale_or_mismatched",
                recommended_human_decision="review_blockers",
                action_readiness="blocked",
                blocker_count=1,
                mismatch_count=1,
                json_digest_match=False,
            )
            (root / "repro.json").write_text(json.dumps(repro_payload, sort_keys=True), encoding="utf-8")
            failed_repro = build_operator_evidence_chain_closeout(root, paths)
            self.assertEqual(failed_repro.closeout_status, "blocked_closeout")
            self.assertIn("must be reproducible", " ".join(failed_repro.blockers))

    def test_operator_evidence_chain_closeout_requires_degraded_stress_coverage(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paths = self._write_chain_closeout_fixture(root)
            stress_payload = self._closeout_stress_payload(degraded_blocker_count=0)
            (root / "stress.json").write_text(json.dumps(stress_payload, sort_keys=True), encoding="utf-8")

            report = build_operator_evidence_chain_closeout(root, paths)

            self.assertEqual(report.closeout_status, "blocked_closeout")
            self.assertFalse(report.recursive_hardening_stopped)
            self.assertIn("must expose degraded blockers", " ".join(report.blockers))

    def test_operator_evidence_chain_closeout_blocks_missing_malformed_root_escape_and_cerebro_targets(
        self,
    ) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paths = self._write_chain_closeout_fixture(root)

            missing = build_operator_evidence_chain_closeout(
                root,
                {**paths, "final_review_index": "missing.json"},
            )
            self.assertEqual(missing.closeout_status, "blocked_closeout")
            self.assertIn("closeout input is missing", " ".join(missing.blockers))

            bad_json = root / "bad.json"
            bad_json.write_text("{not-json", encoding="utf-8")
            malformed = build_operator_evidence_chain_closeout(
                root,
                {**paths, "final_review_index": "bad.json"},
            )
            self.assertEqual(malformed.closeout_status, "blocked_closeout")
            self.assertIn("malformed", " ".join(malformed.blockers))

            outside = root.parent / "outside-closeout.json"
            outside.write_text(
                json.dumps(self._closeout_final_review_payload(), sort_keys=True),
                encoding="utf-8",
            )
            try:
                escaped = build_operator_evidence_chain_closeout(
                    root,
                    {**paths, "final_review_index": str(outside)},
                )
                self.assertIn("path escapes project root", " ".join(escaped.blockers))
            finally:
                outside.unlink(missing_ok=True)

            cerebro_target = build_operator_evidence_chain_closeout(
                root,
                {**paths, "final_review_index": ".cerebro/state.json"},
            )
            self.assertIn("canonical state boundary", " ".join(cerebro_target.blockers))

    def test_operator_evidence_chain_closeout_json_markdown_and_incoherent_reports(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            paths = self._write_chain_closeout_fixture(root)
            report = build_operator_evidence_chain_closeout(root, paths)

            json_payload = json.loads(render_operator_evidence_chain_closeout_json(report))
            markdown = render_operator_evidence_chain_closeout_markdown(report)

            self.assertEqual(json_payload["schema_version"], "1")
            self.assertEqual(json_payload["state_change"], "none")
            self.assertEqual(json_payload["summary"]["closeout_status"], "closed_until_new_evidence")
            self.assertTrue(json_payload["guardrails"]["closeout_is_not_permission"])
            self.assertTrue(json_payload["guardrails"]["closeout_is_not_source_registry"])
            self.assertTrue(json_payload["guardrails"]["no_action_is_not_human_approval"])
            self.assertIn("# Epistemic Readiness Operator Evidence Chain Closeout", markdown)
            self.assertIn("closeout_is_not_permission: true", markdown)
            self.assertIn("recursive_stop_is_not_permanent_freeze: true", markdown)
            self.assertIn("## Reopen Triggers", markdown)
            self.assertIn("## Must Not Apply", markdown)

            with self.assertRaises(ValueError):
                OperatorEvidenceChainCloseoutReport(
                    inputs=report.inputs,
                    state_change="canonical-mutation",
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceChainCloseoutReport(
                    inputs=(report.inputs[0], report.inputs[0], report.inputs[2]),
                )
            with self.assertRaises(ValueError):
                OperatorEvidenceChainCloseoutInput(
                    input_id="unknown",
                    path="artifact.json",
                    exists=True,
                    parse_status="parsed",
                    digest="a" * 64,
                    summary={},
                )

    def _write_chain_closeout_fixture(self, root: Path) -> dict[str, str]:
        (root / "index.json").write_text(
            json.dumps(self._closeout_final_review_payload(), sort_keys=True),
            encoding="utf-8",
        )
        (root / "stress.json").write_text(
            json.dumps(self._closeout_stress_payload(), sort_keys=True),
            encoding="utf-8",
        )
        (root / "repro.json").write_text(
            json.dumps(self._closeout_repro_payload(), sort_keys=True),
            encoding="utf-8",
        )
        return {
            "final_review_index": "index.json",
            "final_review_index_stress_matrix": "stress.json",
            "final_review_index_stress_reproducibility": "repro.json",
        }

    def _closeout_final_review_payload(
        self,
        *,
        review_status: str = "final_review_clear",
        recommended_human_decision: str = "none",
        action_readiness: str = "advisory_report_allowed",
        blocker_count: int = 0,
        input_blocker_count: int = 0,
        missing_review_evidence_count: int = 0,
    ) -> dict:
        return {
            "schema_version": "1",
            "state_change": "none",
            "authority": "non-authoritative; advisory operator evidence final review index only",
            "summary": {
                "review_status": review_status,
                "recommended_human_decision": recommended_human_decision,
                "action_readiness": action_readiness,
                "blocked": action_readiness == "blocked",
                "input_count": 3,
                "input_blocker_count": input_blocker_count,
                "blocker_count": blocker_count,
                "missing_review_evidence_count": missing_review_evidence_count,
            },
        }

    def _closeout_stress_payload(
        self,
        *,
        scenario_count: int = 10,
        pass_count: int = 10,
        fail_count: int = 0,
        all_scenarios_passed: bool = True,
        degraded_blocker_count: int = 19,
    ) -> dict:
        return {
            "schema_version": "1",
            "state_change": "none",
            "authority": (
                "non-authoritative; advisory operator evidence final review "
                "index stress matrix only"
            ),
            "summary": {
                "scenario_count": scenario_count,
                "pass_count": pass_count,
                "fail_count": fail_count,
                "all_scenarios_passed": all_scenarios_passed,
                "blocker_count": degraded_blocker_count,
                "degraded_blocker_count": degraded_blocker_count,
                "input_blocker_count": degraded_blocker_count,
                "missing_review_evidence_count": 3,
                "boundary_error_count": 2,
            },
        }

    def _closeout_repro_payload(
        self,
        *,
        reproducibility_status: str = "reproducible",
        recommended_human_decision: str = "none",
        action_readiness: str = "advisory_report_allowed",
        blocker_count: int = 0,
        mismatch_count: int = 0,
        missing_artifact_count: int = 0,
        json_digest_match: bool = True,
        markdown_digest_match: bool = True,
    ) -> dict:
        return {
            "schema_version": "1",
            "state_change": "none",
            "authority": (
                "non-authoritative; advisory operator evidence final review "
                "index stress reproducibility check only"
            ),
            "summary": {
                "reproducibility_status": reproducibility_status,
                "recommended_human_decision": recommended_human_decision,
                "action_readiness": action_readiness,
                "blocked": action_readiness == "blocked",
                "artifact_count": 2,
                "blocker_count": blocker_count,
                "mismatch_count": mismatch_count,
                "missing_artifact_count": missing_artifact_count,
                "json_digest_match": json_digest_match,
                "markdown_digest_match": markdown_digest_match,
            },
        }

    def _write_final_review_index_fixture(self, root: Path) -> dict[str, str]:
        (root / "capsule.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": "non-authoritative; advisory operator evidence review capsule only",
                    "summary": {
                        "review_status": "review_clear",
                        "recommended_human_decision": "none",
                        "action_readiness": "advisory_report_allowed",
                        "input_count": 4,
                        "input_blocker_count": 0,
                        "blocker_count": 0,
                        "missing_review_evidence_count": 0,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (root / "stress.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": (
                        "non-authoritative; advisory operator evidence review "
                        "capsule stress matrix only"
                    ),
                    "summary": {
                        "scenario_count": 9,
                        "pass_count": 9,
                        "fail_count": 0,
                        "all_scenarios_passed": True,
                        "blocker_count": 8,
                        "degraded_blocker_count": 8,
                        "input_blocker_count": 7,
                        "missing_review_evidence_count": 1,
                        "boundary_error_count": 2,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (root / "repro.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": (
                        "non-authoritative; advisory operator evidence review "
                        "capsule reproducibility check only"
                    ),
                    "summary": {
                        "reproducibility_status": "reproducible",
                        "recommended_human_decision": "none",
                        "action_readiness": "advisory_report_allowed",
                        "blocked": False,
                        "artifact_count": 2,
                        "blocker_count": 0,
                        "mismatch_count": 0,
                        "missing_artifact_count": 0,
                        "json_digest_match": True,
                        "markdown_digest_match": True,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        return {
            "review_capsule": "capsule.json",
            "review_capsule_stress_matrix": "stress.json",
            "review_capsule_reproducibility": "repro.json",
        }

    def _write_checked_review_capsule_artifacts(self, root: Path) -> dict[str, str]:
        self._write_review_capsule_fixture(root)
        input_paths = {
            "operator_decision_packet": "packet.json",
            "intake_reproducibility": "repro.json",
            "provenance_index": "provenance.json",
            "provenance_stress_matrix": "stress.json",
        }
        capsule = build_operator_evidence_review_capsule(root, input_paths)
        (root / "capsule.json").write_text(
            render_operator_evidence_review_capsule_json(capsule),
            encoding="utf-8",
        )
        (root / "capsule.md").write_text(
            render_operator_evidence_review_capsule_markdown(capsule),
            encoding="utf-8",
        )
        return input_paths

    def _write_review_capsule_fixture(self, root: Path) -> None:
        (root / "packet.json").write_text(
            json.dumps(self._review_packet_payload(), sort_keys=True),
            encoding="utf-8",
        )
        (root / "repro.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": (
                        "non-authoritative; advisory operator evidence intake "
                        "reproducibility check only"
                    ),
                    "summary": {
                        "reproducibility_status": "reproducible",
                        "recommended_human_decision": "none",
                        "action_readiness": "advisory_report_allowed",
                        "blocked": False,
                        "blocker_count": 0,
                        "mismatch_count": 0,
                        "digest_match": True,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (root / "provenance.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": "non-authoritative; advisory operator evidence provenance index only",
                    "summary": {
                        "artifact_count": 2,
                        "present_count": 2,
                        "dependency_edge_count": 1,
                        "blocker_count": 0,
                        "blocked": False,
                        "recommended_human_decision": "none",
                        "action_readiness": "advisory_report_allowed",
                        "digest_manifest": "a" * 64,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )
        (root / "stress.json").write_text(
            json.dumps(
                {
                    "schema_version": "1",
                    "state_change": "none",
                    "authority": (
                        "non-authoritative; advisory operator evidence provenance "
                        "stress matrix only"
                    ),
                    "summary": {
                        "scenario_count": 9,
                        "pass_count": 9,
                        "fail_count": 0,
                        "all_scenarios_passed": True,
                        "blocker_count": 7,
                        "boundary_error_count": 4,
                        "text_digest_only_count": 1,
                    },
                },
                sort_keys=True,
            ),
            encoding="utf-8",
        )

    def _review_packet_payload(self) -> dict:
        return {
            "schema_version": "1",
            "state_change": "none",
            "authority": "non-authoritative; advisory operator decision packet evidence only",
            "summary": {
                "recommended_human_decision": "none",
                "action_readiness": "no_action",
                "blocker_count": 0,
                "missing_evidence_count": 0,
            },
        }


if __name__ == "__main__":
    unittest.main()
