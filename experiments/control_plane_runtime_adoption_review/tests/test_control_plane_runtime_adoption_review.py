from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_action_review import build_control_plane_action_review_bundle
from experiments.control_plane_boundary_audit import ControlPlaneBoundaryAuditReport, audit_control_plane_boundary_tree
from experiments.control_plane_decision_version_review import build_control_plane_decision_version_review
from experiments.control_plane_guardrail_eval import evaluate_control_plane_guardrails
from experiments.control_plane_integrity_review import build_control_plane_integrity_review
from experiments.control_plane_lineage_invariant_eval import evaluate_control_plane_packet_projection_lineage
from experiments.control_plane_review_packet import build_control_plane_review_packet
from experiments.control_plane_rule_promotion_review import build_control_plane_rule_promotion_review
from experiments.control_plane_runtime_adoption_review import (
    ControlPlaneRuntimeAdoptionReviewError,
    build_control_plane_runtime_adoption_review,
    render_control_plane_runtime_adoption_review_json,
    render_control_plane_runtime_adoption_review_markdown,
)
from experiments.control_plane_telemetry_projection import project_control_plane_packet_to_telemetry


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"


def _proposal(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "proposal_id": "proposal-runtime-research",
        "proposal_thread_id": "runtime-research",
        "revision": 1,
        "runtime_family": "opentelemetry",
        "adoption_stage": "research",
        "target_boundary": "observability",
        "current_status": "draft",
        "risk_level": "low",
        "supersedes_proposal_id": "",
        "evidence_ids": ["evidence-1"],
        "depends_on_decision_ids": [],
        "referenced_rule_ids": [],
        "requires_human_decision": False,
        "human_decision_id": "none",
        "requests_runtime_enablement": False,
        "requests_adapter_import": False,
        "requests_io_or_network": False,
        "requests_scheduler_authority": False,
        "auto_apply": False,
        "rollback_plan": "",
        "observability_plan": "",
        "security_plan": "",
        "summary": "Research-only runtime adoption note.",
        "rationale": "This proposal is non-authoritative and does not enable a runtime.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _runtime_proposal(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload = _proposal(
        {
            "proposal_id": "proposal-mcp-boundary",
            "proposal_thread_id": "mcp-boundary",
            "runtime_family": "mcp",
            "adoption_stage": "runtime_boundary_request",
            "target_boundary": "tool_bridge",
            "current_status": "active_candidate",
            "risk_level": "high",
            "depends_on_decision_ids": ["decision-current"],
            "referenced_rule_ids": ["rule-runtime-contract-refresh"],
            "requires_human_decision": True,
            "human_decision_id": "human-approval-1",
            "requests_runtime_enablement": True,
            "rollback_plan": "Disable the proposed boundary and keep current advisory-only behavior.",
            "observability_plan": "Record advisory review status without exporting authority.",
            "security_plan": "Require allowlisted tools, human review, and sanitized evidence.",
            "summary": "Runtime boundary candidate for advisory review only.",
            "rationale": "The proposal does not grant permission and must not execute automatically.",
        }
    )
    if overrides:
        payload.update(overrides)
    return payload


def _decision(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision_id": "decision-current",
        "decision_thread_id": "runtime-adoption-thread",
        "observation_id": "runtime-adoption",
        "revision": 1,
        "decision_kind": "approval",
        "status": "current",
        "decided_by": "HumanOperator",
        "decided_at": REVIEW_AS_OF,
        "valid_until": "",
        "supersedes_decision_id": "",
        "human_decision_id": "human-approval-1",
        "referenced_evidence_ids": ["evidence-1"],
        "auto_continue": False,
        "summary": "Human approval for advisory runtime adoption review only.",
        "rationale": "This decision record does not grant execution approval.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _rule(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_id": "rule-runtime-contract-refresh",
        "rule_thread_id": "runtime-contract-refresh",
        "revision": 1,
        "rule_family": "runtime_contract",
        "current_status": "active",
        "proposed_change": "refresh",
        "risk_level": "medium",
        "supersedes_rule_id": "",
        "evidence_ids": ["evidence-1"],
        "depends_on_decision_ids": [],
        "human_decision_required": False,
        "human_decision_id": "none",
        "auto_apply": False,
        "summary": "Refresh candidate for advisory review only.",
        "rationale": "The review is non-authoritative and does not apply policy.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _observation(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "runtime-adoption",
        "title": "Runtime adoption review",
        "status": "open",
        "kind": "slice",
        "priority": "high",
        "boundary": "derived experiment only",
        "trigger": "FORMAL_RESUME_TRIGGER_CONTROL_PLANE_RUNTIME_ADOPTION_REVIEW_SLICE_1.md",
        "dependencies": [],
        "dependencies_satisfied": True,
        "auto_continuation": False,
        "next_action": "Review runtime adoption candidate without enabling it.",
        "halt_if": "Any review output is treated as runtime permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _clean_decision_review():
    return build_control_plane_decision_version_review([_decision()], review_as_of=REVIEW_AS_OF)


def _clean_rule_promotion_review():
    return build_control_plane_rule_promotion_review([_rule()], review_as_of=REVIEW_AS_OF)


def _clean_boundary_report() -> ControlPlaneBoundaryAuditReport:
    return ControlPlaneBoundaryAuditReport(
        schema_version="1",
        audit_role="audits_control_plane_experiment_boundary_drift",
        package_count=1,
        source_count=3,
        audit_status="boundary_markers_preserved",
        finding_count=0,
        severity_counts={},
        package_counts={},
        finding_codes=(),
        findings=(),
        audited_packages=("control_plane_runtime_adoption_review",),
    )


def _assessment() -> ControlPlaneAssessment:
    return ControlPlaneAssessment(
        selected_task_id="runtime-adoption",
        decision_runtime_reason="caller supplied advisory review target",
        task_selection_status="match",
        task_selection_reason="test fixture only; no scheduler authority",
        epistemic_action_readiness="advisory_report_allowed",
        blockers=(),
        missing_evidence=(),
        stale_claims=(),
        conflicts=(),
        claim_evaluation_summary={"ready_count": 1, "blocked_count": 0, "insufficient_count": 0},
        operational_signal_summary={
            "record_count": 0,
            "candidate_trigger_count": 0,
            "authority": "derived-observability-only",
            "non_authoritative": True,
        },
        recommended_human_decision="none",
        must_not_execute_automatically=True,
        advisory_pass_is_not_permission=True,
    )


def _capability() -> CapabilityAssessment:
    return CapabilityAssessment(
        request_id="req-runtime-adoption",
        matched_rule_id="runtime-adoption-test-rule",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


def _clean_integrity_review():
    packet = build_control_plane_review_packet(
        "runtime-adoption",
        _assessment(),
        capability_assessments=(_capability(),),
    )
    projection = project_control_plane_packet_to_telemetry(packet)
    return build_control_plane_integrity_review(
        boundary_audit=_clean_boundary_report(),
        guardrail_reports=(evaluate_control_plane_guardrails(projection),),
        lineage_reports=(evaluate_control_plane_packet_projection_lineage(packet, projection),),
    )


class ControlPlaneRuntimeAdoptionReviewTests(unittest.TestCase):
    def test_research_proposal_is_observed_without_permission(self) -> None:
        review = build_control_plane_runtime_adoption_review([_proposal()], review_as_of=REVIEW_AS_OF)

        self.assertEqual("runtime_adoption_contract_observed", review.review_status)
        self.assertEqual(("proposal-runtime-research",), review.research_candidate_ids)
        self.assertEqual(("proposal-runtime-research",), review.non_active_candidate_ids)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.adoption_review_is_not_permission)
        self.assertTrue(review.adoption_status_is_not_execution_approval)
        self.assertTrue(review.technology_selection_is_not_authority)

    def test_runtime_boundary_candidate_with_clean_evidence_is_only_candidate_observed(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [_runtime_proposal()],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
            rule_promotion_review=_clean_rule_promotion_review(),
        )

        self.assertEqual("runtime_adoption_candidate_observed", review.review_status)
        self.assertEqual(("proposal-mcp-boundary",), review.runtime_candidate_ids)
        self.assertEqual(0, review.finding_count)

    def test_rejects_duplicate_unsafe_unknown_enum_and_bad_revision_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "duplicate proposal ids"):
            build_control_plane_runtime_adoption_review([_proposal(), _proposal()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "path-segment safe"):
            build_control_plane_runtime_adoption_review([_proposal({"proposal_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "unknown runtime_family"):
            build_control_plane_runtime_adoption_review([_proposal({"runtime_family": "magic"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "review_as_of must be an ISO date"):
            build_control_plane_runtime_adoption_review([_proposal()], review_as_of="today")

        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "revision must be a positive integer"):
            build_control_plane_runtime_adoption_review([_proposal({"revision": 0})], review_as_of=REVIEW_AS_OF)

    def test_revision_gap_supersession_and_stale_runtime_candidate_are_blocked(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _runtime_proposal(
                    {
                        "proposal_id": "proposal-r1",
                        "proposal_thread_id": "runtime-thread",
                        "revision": 1,
                        "current_status": "superseded",
                    }
                ),
                _runtime_proposal(
                    {
                        "proposal_id": "proposal-r3",
                        "proposal_thread_id": "runtime-thread",
                        "revision": 3,
                        "supersedes_proposal_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
            rule_promotion_review=_clean_rule_promotion_review(),
        )

        self.assertEqual("runtime_adoption_blocked", review.review_status)
        self.assertIn("proposal_revision_gap", review.finding_codes)
        self.assertIn("proposal_supersedes_unknown_id", review.finding_codes)
        self.assertIn("runtime_change_over_stale_candidate", review.finding_codes)

    def test_cross_thread_non_previous_and_active_not_latest_are_blocked(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _proposal(
                    {
                        "proposal_id": "proposal-a1",
                        "proposal_thread_id": "thread-a",
                        "current_status": "active_candidate",
                    }
                ),
                _proposal(
                    {
                        "proposal_id": "proposal-a2",
                        "proposal_thread_id": "thread-a",
                        "revision": 2,
                        "supersedes_proposal_id": "proposal-b1",
                        "current_status": "active_candidate",
                    }
                ),
                _proposal(
                    {
                        "proposal_id": "proposal-b1",
                        "proposal_thread_id": "thread-b",
                        "current_status": "draft",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("multiple_active_runtime_proposals_in_thread", review.finding_codes)
        self.assertIn("active_runtime_proposal_not_latest_revision", review.finding_codes)
        self.assertIn("proposal_supersedes_cross_thread", review.finding_codes)

    def test_supersedes_must_point_to_previous_revision(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _proposal({"proposal_id": "proposal-r1", "proposal_thread_id": "thread", "current_status": "superseded"}),
                _proposal(
                    {
                        "proposal_id": "proposal-r2",
                        "proposal_thread_id": "thread",
                        "revision": 2,
                        "supersedes_proposal_id": "proposal-r1",
                        "current_status": "superseded",
                    }
                ),
                _proposal(
                    {
                        "proposal_id": "proposal-r3",
                        "proposal_thread_id": "thread",
                        "revision": 3,
                        "supersedes_proposal_id": "proposal-r1",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("proposal_supersedes_non_previous_revision", review.finding_codes)

    def test_auto_apply_adapter_network_scheduler_and_authority_text_block_adoption(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _runtime_proposal(
                    {
                        "auto_apply": True,
                        "requests_adapter_import": True,
                        "requests_io_or_network": True,
                        "requests_scheduler_authority": True,
                        "summary": "This adapter grants permission and is approved to run.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
            rule_promotion_review=_clean_rule_promotion_review(),
        )

        self.assertIn("proposal_requests_auto_apply", review.finding_codes)
        self.assertIn("proposal_requests_adapter_import", review.finding_codes)
        self.assertIn("proposal_requests_io_or_network", review.finding_codes)
        self.assertIn("proposal_requests_scheduler_authority", review.finding_codes)
        self.assertIn("proposal_text_launders_runtime_authority", review.finding_codes)

    def test_runtime_enablement_requires_human_decision_reviews_and_rule_reference(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _runtime_proposal(
                    {
                        "depends_on_decision_ids": [],
                        "referenced_rule_ids": [],
                        "requires_human_decision": False,
                        "human_decision_id": "none",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("runtime_enablement_without_human_decision", review.finding_codes)
        self.assertIn("runtime_enablement_missing_human_decision_id", review.finding_codes)
        self.assertIn("high_risk_runtime_proposal_missing_decision_reference", review.finding_codes)
        self.assertIn("runtime_adoption_missing_rule_reference", review.finding_codes)
        self.assertIn("runtime_enablement_missing_decision_review", review.finding_codes)
        self.assertIn("runtime_enablement_missing_integrity_review", review.finding_codes)

    def test_unknown_non_current_decisions_and_rule_drift_block_adoption(self) -> None:
        decision_review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-old", "revision": 1, "status": "superseded"}),
                _decision({"decision_id": "decision-current", "revision": 2, "supersedes_decision_id": "decision-old"}),
            ],
            review_as_of=REVIEW_AS_OF,
        )
        rule_review = build_control_plane_rule_promotion_review(
            [
                _rule({"rule_id": "rule-old", "current_status": "obsolete"}),
                _rule({"rule_id": "rule-runtime-contract-refresh", "rule_thread_id": "runtime-contract-current"}),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        review = build_control_plane_runtime_adoption_review(
            [
                _runtime_proposal(
                    {
                        "depends_on_decision_ids": ["decision-old", "missing-decision"],
                        "referenced_rule_ids": ["rule-old", "missing-rule"],
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=decision_review,
            integrity_review=_clean_integrity_review(),
            rule_promotion_review=rule_review,
        )

        self.assertIn("runtime_proposal_references_non_current_decision", review.finding_codes)
        self.assertIn("runtime_proposal_references_unknown_decision", review.finding_codes)
        self.assertIn("runtime_enablement_missing_current_decision_reference", review.finding_codes)
        self.assertIn("proposal_references_non_active_rule", review.finding_codes)
        self.assertIn("proposal_references_unknown_rule", review.finding_codes)

    def test_decision_integrity_rule_and_action_drift_block_adoption(self) -> None:
        drifted_decision_review = build_control_plane_decision_version_review(
            [_decision({"auto_continue": True})],
            review_as_of=REVIEW_AS_OF,
        )
        drifted_integrity_review = replace(_clean_integrity_review(), review_status="control_plane_integrity_drift_observed")
        blocked_rule_review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-contract-refresh",
                        "current_status": "blocked",
                        "proposed_change": "keep",
                        "risk_level": "high",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )
        bundle = build_control_plane_action_review_bundle(
            _observation({"status": "waiting", "dependencies": ["operator"], "dependencies_satisfied": False}),
            boundary_audit=audit_control_plane_boundary_tree(REPO_ROOT / "experiments"),
        )

        review = build_control_plane_runtime_adoption_review(
            [_runtime_proposal()],
            review_as_of=REVIEW_AS_OF,
            decision_review=drifted_decision_review,
            integrity_review=drifted_integrity_review,
            rule_promotion_review=blocked_rule_review,
            action_review_bundles=(bundle,),
        )

        self.assertIn("runtime_enablement_over_decision_drift", review.finding_codes)
        self.assertIn("runtime_enablement_over_integrity_drift", review.finding_codes)
        self.assertIn("proposal_references_rule_promotion_blocked", review.finding_codes)
        self.assertIn("runtime_enablement_over_rule_promotion_drift", review.finding_codes)
        self.assertIn("runtime_adoption_over_blocked_action_posture", review.finding_codes)
        self.assertIn("runtime_adoption_over_unresolved_action_decision", review.finding_codes)

    def test_plan_requirements_cover_pilot_production_network_and_observability(self) -> None:
        review = build_control_plane_runtime_adoption_review(
            [
                _runtime_proposal(
                    {
                        "runtime_family": "temporal",
                        "adoption_stage": "production",
                        "target_boundary": "workflow_orchestration",
                        "requests_io_or_network": True,
                        "rollback_plan": "",
                        "observability_plan": "",
                        "security_plan": "",
                    }
                ),
                _runtime_proposal(
                    {
                        "proposal_id": "proposal-otel-export",
                        "proposal_thread_id": "otel-export",
                        "runtime_family": "opentelemetry",
                        "target_boundary": "observability",
                        "requests_runtime_enablement": True,
                        "observability_plan": "",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
            rule_promotion_review=_clean_rule_promotion_review(),
        )

        self.assertIn("runtime_adoption_missing_rollback_plan", review.finding_codes)
        self.assertIn("runtime_adoption_missing_observability_plan", review.finding_codes)
        self.assertIn("runtime_adoption_missing_security_plan", review.finding_codes)
        self.assertIn("opentelemetry_export_must_not_be_authority", review.finding_codes)

    def test_rejects_supplied_review_guardrail_drift(self) -> None:
        bad_decision_review = replace(_clean_decision_review(), decision_review_is_not_permission=False)

        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "guardrails"):
            build_control_plane_runtime_adoption_review(
                [_runtime_proposal()],
                review_as_of=REVIEW_AS_OF,
                decision_review=bad_decision_review,
            )

    def test_renderers_preserve_guardrails_and_reject_forged_summary(self) -> None:
        review = build_control_plane_runtime_adoption_review([_proposal()], review_as_of=REVIEW_AS_OF)
        payload = json.loads(render_control_plane_runtime_adoption_review_json(review))
        markdown = render_control_plane_runtime_adoption_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["adoption_review_is_not_permission"])
        self.assertIn("adoption_status_is_not_execution_approval: true", markdown)
        self.assertIn("proposal_thread_count: 1", markdown)
        self.assertIn("must_not_execute_automatically: true", markdown)

        forged = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "finding_count"):
            render_control_plane_runtime_adoption_review_json(forged)

        forged_active_overlap = replace(
            review,
            active_candidate_ids=("proposal-runtime-research",),
            non_active_candidate_ids=("proposal-runtime-research",),
        )
        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "disjoint"):
            render_control_plane_runtime_adoption_review_json(forged_active_overlap)

        forged_runtime_overlap = replace(
            review,
            runtime_candidate_ids=("proposal-runtime-research",),
            research_candidate_ids=("proposal-runtime-research",),
        )
        with self.assertRaisesRegex(ControlPlaneRuntimeAdoptionReviewError, "disjoint"):
            render_control_plane_runtime_adoption_review_json(forged_runtime_overlap)

    def test_package_contains_no_runtime_imports_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_runtime_adoption_review"
        source_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in sorted(package_root.glob("*.py"))
        )

        forbidden_fragments = (
            "import temporalio",
            "import opentelemetry",
            "import openai",
            "import langgraph",
            "import requests",
            "import subprocess",
            "path(",
            "read_text",
            "write_text",
            "tomllib",
            ".cerebro",
            "docs/operations",
            "observation_center.toml",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()
