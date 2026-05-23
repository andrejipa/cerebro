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
from experiments.control_plane_rule_promotion_review import (
    ControlPlaneRulePromotionReviewError,
    build_control_plane_rule_promotion_review,
    render_control_plane_rule_promotion_review_json,
    render_control_plane_rule_promotion_review_markdown,
)
from experiments.control_plane_telemetry_projection import project_control_plane_packet_to_telemetry


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"


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


def _decision(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision_id": "decision-current",
        "decision_thread_id": "rule-promotion-thread",
        "observation_id": "rule-promotion",
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
        "summary": "Human approval for advisory boundary review only.",
        "rationale": "This decision record does not grant execution approval.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _observation(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "rule-promotion",
        "title": "Rule promotion review",
        "status": "open",
        "kind": "slice",
        "priority": "high",
        "boundary": "derived experiment only",
        "trigger": "FORMAL_RESUME_TRIGGER_CONTROL_PLANE_RULE_PROMOTION_REVIEW_SLICE_1.md",
        "dependencies": [],
        "dependencies_satisfied": True,
        "auto_continuation": False,
        "next_action": "Review rule-promotion candidate without applying it.",
        "halt_if": "Any review output is treated as runtime permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _clean_decision_review():
    return build_control_plane_decision_version_review([_decision()], review_as_of=REVIEW_AS_OF)


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
        audited_packages=("control_plane_rule_promotion_review",),
    )


def _assessment() -> ControlPlaneAssessment:
    return ControlPlaneAssessment(
        selected_task_id="rule-promotion",
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
        request_id="req-rule-promotion",
        matched_rule_id="rule-promotion-test-rule",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


def _clean_integrity_review():
    packet = build_control_plane_review_packet(
        "rule-promotion",
        _assessment(),
        capability_assessments=(_capability(),),
    )
    projection = project_control_plane_packet_to_telemetry(packet)
    return build_control_plane_integrity_review(
        boundary_audit=_clean_boundary_report(),
        guardrail_reports=(evaluate_control_plane_guardrails(projection),),
        lineage_reports=(evaluate_control_plane_packet_projection_lineage(packet, projection),),
    )


class ControlPlaneRulePromotionReviewTests(unittest.TestCase):
    def test_refresh_candidate_is_observed_without_permission(self) -> None:
        review = build_control_plane_rule_promotion_review([_rule()], review_as_of=REVIEW_AS_OF)

        self.assertEqual("rule_refresh_candidate_observed", review.review_status)
        self.assertEqual(("rule-runtime-contract-refresh",), review.refresh_candidate_ids)
        self.assertEqual(("runtime-contract-refresh",), review.rule_thread_ids)
        self.assertEqual(("rule-runtime-contract-refresh",), review.active_rule_ids)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.rule_review_is_not_permission)
        self.assertTrue(review.promotion_candidate_is_not_runtime_authority)
        self.assertTrue(review.rule_record_is_not_truth)

    def test_runtime_promotion_with_clean_evidence_is_only_candidate_observed(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-boundary",
                        "proposed_change": "open_runtime_boundary",
                        "risk_level": "high",
                        "depends_on_decision_ids": ["decision-current"],
                        "human_decision_required": True,
                        "human_decision_id": "human-approval-1",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
        )

        self.assertEqual("rule_promotion_candidate_observed", review.review_status)
        self.assertEqual(("rule-runtime-boundary",), review.promotion_candidate_ids)
        self.assertEqual(0, review.finding_count)

    def test_rejects_duplicate_and_path_unsafe_rule_identity(self) -> None:
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "duplicate rule ids"):
            build_control_plane_rule_promotion_review([_rule(), _rule()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "path-segment safe"):
            build_control_plane_rule_promotion_review([_rule({"rule_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "rule_thread_id must be path-segment safe"):
            build_control_plane_rule_promotion_review([_rule({"rule_thread_id": "docs/operations"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "duplicate rule thread revisions"):
            build_control_plane_rule_promotion_review(
                [
                    _rule({"rule_id": "rule-a"}),
                    _rule({"rule_id": "rule-b"}),
                ],
                review_as_of=REVIEW_AS_OF,
            )

    def test_rejects_unknown_enums_and_bad_date(self) -> None:
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "unknown rule_family"):
            build_control_plane_rule_promotion_review([_rule({"rule_family": "memory"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "review_as_of must be an ISO date"):
            build_control_plane_rule_promotion_review([_rule()], review_as_of="today")

        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "revision must be a positive integer"):
            build_control_plane_rule_promotion_review([_rule({"revision": 0})], review_as_of=REVIEW_AS_OF)

    def test_rule_revision_gap_and_unknown_supersedes_are_blocking_drift(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-r1",
                        "rule_thread_id": "rule-thread",
                        "revision": 1,
                        "current_status": "obsolete",
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-r3",
                        "rule_thread_id": "rule-thread",
                        "revision": 3,
                        "supersedes_rule_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertEqual("rule_promotion_blocked", review.review_status)
        self.assertIn("rule_revision_gap", review.finding_codes)
        self.assertIn("rule_supersedes_unknown_id", review.finding_codes)

    def test_cross_thread_supersession_and_multiple_active_rules_are_blocking_drift(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-a1",
                        "rule_thread_id": "thread-a",
                        "revision": 1,
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-a2",
                        "rule_thread_id": "thread-a",
                        "revision": 2,
                        "supersedes_rule_id": "rule-b1",
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-b1",
                        "rule_thread_id": "thread-b",
                        "revision": 1,
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("multiple_active_rules_in_thread", review.finding_codes)
        self.assertIn("active_rule_not_latest_revision", review.finding_codes)
        self.assertIn("rule_supersedes_cross_thread", review.finding_codes)

    def test_rule_change_over_stale_candidate_is_blocked(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-r1",
                        "rule_thread_id": "rule-thread",
                        "revision": 1,
                        "proposed_change": "promote_to_runtime",
                        "risk_level": "high",
                        "depends_on_decision_ids": ["decision-current"],
                        "human_decision_required": True,
                        "human_decision_id": "human-approval-1",
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-r2",
                        "rule_thread_id": "rule-thread",
                        "revision": 2,
                        "supersedes_rule_id": "rule-r1",
                        "current_status": "draft",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
        )

        self.assertIn("rule_change_over_stale_candidate", review.finding_codes)

    def test_supersedes_must_point_to_previous_revision(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-r1",
                        "rule_thread_id": "rule-thread",
                        "revision": 1,
                        "current_status": "obsolete",
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-r2",
                        "rule_thread_id": "rule-thread",
                        "revision": 2,
                        "current_status": "obsolete",
                        "supersedes_rule_id": "rule-r1",
                    }
                ),
                _rule(
                    {
                        "rule_id": "rule-r3",
                        "rule_thread_id": "rule-thread",
                        "revision": 3,
                        "supersedes_rule_id": "rule-r1",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("rule_supersedes_non_previous_revision", review.finding_codes)

    def test_auto_apply_and_authority_text_block_rule_change(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "auto_apply": True,
                        "summary": "This rule grants permission to execute and schedules work.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertEqual("rule_promotion_blocked", review.review_status)
        self.assertIn("rule_candidate_requests_auto_apply", review.finding_codes)
        self.assertIn("rule_text_launders_authority", review.finding_codes)

    def test_runtime_promotion_requires_human_decision_and_reviews(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-boundary",
                        "proposed_change": "promote_to_runtime",
                        "risk_level": "high",
                        "human_decision_required": False,
                        "human_decision_id": "none",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("runtime_promotion_without_human_decision_requirement", review.finding_codes)
        self.assertIn("runtime_promotion_missing_human_decision_id", review.finding_codes)
        self.assertIn("runtime_promotion_missing_decision_review", review.finding_codes)
        self.assertIn("runtime_promotion_missing_integrity_review", review.finding_codes)

    def test_references_to_unknown_or_non_current_decisions_are_blocked(self) -> None:
        decision_review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-old", "revision": 1, "status": "superseded"}),
                _decision({"decision_id": "decision-current", "revision": 2, "supersedes_decision_id": "decision-old"}),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-boundary",
                        "proposed_change": "open_runtime_boundary",
                        "risk_level": "high",
                        "depends_on_decision_ids": ["decision-old", "missing-decision"],
                        "human_decision_required": True,
                        "human_decision_id": "human-approval-1",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=decision_review,
            integrity_review=_clean_integrity_review(),
        )

        self.assertIn("rule_references_non_current_decision", review.finding_codes)
        self.assertIn("rule_references_unknown_decision", review.finding_codes)
        self.assertIn("runtime_promotion_missing_current_decision_reference", review.finding_codes)

    def test_runtime_promotion_over_decision_or_integrity_drift_is_critical(self) -> None:
        drifted_decision_review = build_control_plane_decision_version_review(
            [_decision({"auto_continue": True})],
            review_as_of=REVIEW_AS_OF,
        )
        drifted_integrity_review = replace(_clean_integrity_review(), review_status="control_plane_integrity_drift_observed")

        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-boundary",
                        "proposed_change": "promote_to_runtime",
                        "risk_level": "high",
                        "depends_on_decision_ids": ["decision-current"],
                        "human_decision_required": True,
                        "human_decision_id": "human-approval-1",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=drifted_decision_review,
            integrity_review=drifted_integrity_review,
        )

        self.assertEqual("rule_promotion_blocked", review.review_status)
        self.assertIn("runtime_promotion_over_decision_drift", review.finding_codes)
        self.assertIn("runtime_promotion_over_integrity_drift", review.finding_codes)
        self.assertEqual({"critical": 2}, review.severity_counts)

    def test_refresh_missing_evidence_or_integrity_drift_requires_review(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [_rule({"evidence_ids": [], "proposed_change": "replace"})],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertEqual("rule_promotion_human_review_required", review.review_status)
        self.assertIn("rule_refresh_missing_evidence", review.finding_codes)

        drifted_integrity_review = replace(_clean_integrity_review(), review_status="control_plane_integrity_drift_observed")
        drifted = build_control_plane_rule_promotion_review(
            [_rule({"proposed_change": "replace"})],
            review_as_of=REVIEW_AS_OF,
            integrity_review=drifted_integrity_review,
        )

        self.assertEqual("rule_promotion_blocked", drifted.review_status)
        self.assertIn("rule_refresh_over_integrity_drift", drifted.finding_codes)

    def test_blocked_or_conflicting_rules_cannot_launder_readiness(self) -> None:
        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "blocked-rule",
                        "rule_thread_id": "blocked-rule-thread",
                        "current_status": "blocked",
                        "proposed_change": "keep",
                        "risk_level": "high",
                    }
                ),
                _rule(
                    {
                        "rule_id": "conflicting-rule",
                        "rule_thread_id": "conflicting-rule-thread",
                        "current_status": "conflicting",
                        "proposed_change": "refresh",
                        "human_decision_required": False,
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("blocked_rule_promoted_or_kept", review.finding_codes)
        self.assertIn("conflicting_rule_without_human_decision_requirement", review.finding_codes)

    def test_action_bundle_blockers_block_rule_promotion(self) -> None:
        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(
            _observation({"status": "waiting", "dependencies": ["operator"], "dependencies_satisfied": False}),
            boundary_audit=boundary_audit,
        )

        review = build_control_plane_rule_promotion_review(
            [
                _rule(
                    {
                        "rule_id": "rule-runtime-boundary",
                        "proposed_change": "open_runtime_boundary",
                        "risk_level": "high",
                        "depends_on_decision_ids": ["decision-current"],
                        "human_decision_required": True,
                        "human_decision_id": "human-approval-1",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_clean_decision_review(),
            integrity_review=_clean_integrity_review(),
            action_review_bundles=(bundle,),
        )

        self.assertIn("rule_change_over_blocked_action_posture", review.finding_codes)
        self.assertIn("runtime_promotion_over_unresolved_action_decision", review.finding_codes)

    def test_rejects_supplied_review_guardrail_drift(self) -> None:
        bad_decision_review = replace(_clean_decision_review(), decision_review_is_not_permission=False)
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "guardrails"):
            build_control_plane_rule_promotion_review(
                [_rule()],
                review_as_of=REVIEW_AS_OF,
                decision_review=bad_decision_review,
            )

    def test_renderers_preserve_guardrails_and_reject_forged_summary(self) -> None:
        review = build_control_plane_rule_promotion_review([_rule()], review_as_of=REVIEW_AS_OF)
        payload = json.loads(render_control_plane_rule_promotion_review_json(review))
        markdown = render_control_plane_rule_promotion_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["rule_review_is_not_permission"])
        self.assertIn("promotion_candidate_is_not_runtime_authority: true", markdown)
        self.assertIn("rule_thread_count: 1", markdown)
        self.assertIn("must_not_execute_automatically: true", markdown)

        forged = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "finding_count"):
            render_control_plane_rule_promotion_review_json(forged)

        forged_active_overlap = replace(
            review,
            active_rule_ids=("rule-runtime-contract-refresh",),
            non_active_rule_ids=("rule-runtime-contract-refresh",),
        )
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "disjoint"):
            render_control_plane_rule_promotion_review_json(forged_active_overlap)

        forged_active_gap = replace(review, active_rule_ids=(), non_active_rule_ids=())
        with self.assertRaisesRegex(ControlPlaneRulePromotionReviewError, "cover rule_ids"):
            render_control_plane_rule_promotion_review_json(forged_active_gap)


if __name__ == "__main__":
    unittest.main()
