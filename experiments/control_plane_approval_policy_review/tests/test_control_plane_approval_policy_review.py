from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_approval_policy_review import (
    ControlPlaneApprovalPolicyReviewError,
    build_control_plane_approval_policy_review,
    render_control_plane_approval_policy_review_json,
    render_control_plane_approval_policy_review_markdown,
)
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_evidence_policy_review import ControlPlaneEvidencePolicyReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"


def _integrity_review(status: str = "control_plane_integrity_preserved") -> ControlPlaneIntegrityReview:
    return ControlPlaneIntegrityReview(
        schema_version="1",
        review_role="test_integrity_review",
        review_status=status,
        evidence_count=0,
        finding_count=0,
        source_status_counts={},
        severity_counts={},
        finding_codes=(),
        evidence=(),
        findings=(),
    )


def _evidence_policy_review(status: str = "evidence_policy_candidate_observed") -> ControlPlaneEvidencePolicyReview:
    return ControlPlaneEvidencePolicyReview(
        schema_version="1",
        review_role="test_evidence_policy_review",
        review_status=status,
        review_as_of=REVIEW_AS_OF,
        policy_count=1,
        policy_thread_count=1,
        policy_ids=("evidence-policy",),
        policy_thread_ids=("evidence-policy-thread",),
        latest_policy_ids=("evidence-policy",),
        non_latest_policy_ids=(),
        active_policy_ids=("evidence-policy",),
        blocked_policy_ids=(),
        evidence_record_count=1,
        evidence_ids=("evidence-clean",),
        accepted_evidence_ids=("evidence-clean",),
        rejected_evidence_ids=(),
        quarantined_evidence_ids=(),
        insufficient_evidence_ids=(),
        expired_evidence_ids=(),
        raw_evidence_ids=(),
        sensitive_evidence_ids=(),
        secret_evidence_ids=(),
        referenced_decision_ids=(),
        referenced_rule_ids=(),
        decision_review_status="not_supplied",
        integrity_review_status="control_plane_integrity_preserved",
        rule_promotion_review_status="not_supplied",
        action_bundle_count=0,
        finding_count=0,
        severity_counts={},
        finding_codes=(),
        findings=(),
    )


def _decision_review() -> ControlPlaneDecisionVersionReview:
    return ControlPlaneDecisionVersionReview(
        schema_version="1",
        review_role="test_decision_review",
        review_status="decision_version_contract_observed",
        review_as_of=REVIEW_AS_OF,
        decision_count=2,
        decision_thread_count=2,
        current_decision_ids=("decision-current",),
        non_current_decision_ids=("decision-old",),
        decision_ids=("decision-current", "decision-old"),
        decision_thread_ids=("decision-current-thread", "decision-old-thread"),
        handoff_status="not_supplied",
        transition_status="not_supplied",
        action_bundle_count=0,
        referenced_evidence_count=0,
        referenced_evidence_ids=(),
        finding_count=0,
        severity_counts={},
        finding_codes=(),
        findings=(),
    )


def _policy(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "policy_id": "approval-policy",
        "policy_thread_id": "approval-thread",
        "revision": 1,
        "lifecycle_status": "active_candidate",
        "policy_scope": "control_plane",
        "approval_kind": "human_execution",
        "authority_boundary": "candidate_policy",
        "supersedes_policy_id": "",
        "evidence_ids": ["evidence-clean"],
        "required_evidence_kinds": ["human_decision", "test_run"],
        "depends_on_decision_ids": [],
        "referenced_rule_ids": [],
        "referenced_tool_manifest_ids": [],
        "referenced_work_item_ids": [],
        "allowed_request_statuses": ["requested", "approved", "rejected", "revoked", "expired"],
        "requires_human_decision": True,
        "requires_current_decision": True,
        "requires_accepted_evidence": True,
        "requires_integrity_preserved": True,
        "requires_tool_review": False,
        "requires_work_queue_review": False,
        "requires_explicit_scope": True,
        "requires_action_fingerprint": True,
        "requires_expiration": True,
        "requires_audit_logging": True,
        "requires_revocation_path": True,
        "rejects_blanket_approval": True,
        "rejects_reuse_after_scope_drift": True,
        "claims_approval_authority": False,
        "grants_execution_permission": False,
        "acts_as_permission_layer": False,
        "registers_approval_store": False,
        "reads_live_approval_store": False,
        "schedules_work": False,
        "selects_next_action": False,
        "mutates_state": False,
        "auto_apply": False,
        "contains_secret_material": False,
        "summary": "Advisory approval policy candidate only.",
        "rationale": "Approval policy review is not permission and does not approve execution.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneApprovalPolicyReviewTests(unittest.TestCase):
    def test_clean_approval_policy_candidate_is_observed_without_permission(self) -> None:
        review = build_control_plane_approval_policy_review(
            [_policy()],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        self.assertEqual("approval_policy_candidate_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.approval_policy_review_is_not_permission)
        self.assertTrue(review.approval_policy_review_is_not_approval_store)
        self.assertTrue(review.approval_status_is_not_execution_approval)
        self.assertTrue(review.approval_presence_is_not_sufficient_evidence)

    def test_rejects_empty_duplicate_unsafe_unknown_enum_duplicate_tuple_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "at least one"):
            build_control_plane_approval_policy_review([], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "duplicate policy ids"):
            build_control_plane_approval_policy_review([_policy(), _policy()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "path-segment safe"):
            build_control_plane_approval_policy_review([_policy({"policy_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "unknown lifecycle_status"):
            build_control_plane_approval_policy_review([_policy({"lifecycle_status": "canonical"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "unknown approval_kind"):
            build_control_plane_approval_policy_review([_policy({"approval_kind": "blanket"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "contains unknown values"):
            build_control_plane_approval_policy_review([_policy({"allowed_request_statuses": ["done"]})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "must not contain duplicates"):
            build_control_plane_approval_policy_review([_policy({"evidence_ids": ["evidence-clean", "evidence-clean"]})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "review_as_of must be an ISO date"):
            build_control_plane_approval_policy_review([_policy()], review_as_of="today")

    def test_revision_supersession_and_active_drift_are_found(self) -> None:
        review = build_control_plane_approval_policy_review(
            [
                _policy({"policy_id": "policy-r1", "policy_thread_id": "thread", "revision": 1}),
                _policy(
                    {
                        "policy_id": "policy-r3",
                        "policy_thread_id": "thread",
                        "revision": 3,
                        "supersedes_policy_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        self.assertEqual("approval_policy_review_blocked", review.review_status)
        self.assertIn("approval_policy_revision_gap", review.finding_codes)
        self.assertIn("approval_policy_supersedes_unknown_id", review.finding_codes)
        self.assertIn("multiple_active_approval_policy_candidates", review.finding_codes)

    def test_missing_policy_controls_block_review(self) -> None:
        review = build_control_plane_approval_policy_review(
            [
                _policy(
                    {
                        "evidence_ids": [],
                        "required_evidence_kinds": [],
                        "requires_human_decision": False,
                        "requires_current_decision": False,
                        "requires_accepted_evidence": False,
                        "requires_integrity_preserved": False,
                        "requires_explicit_scope": False,
                        "requires_action_fingerprint": False,
                        "requires_expiration": False,
                        "requires_audit_logging": False,
                        "requires_revocation_path": False,
                        "rejects_blanket_approval": False,
                        "rejects_reuse_after_scope_drift": False,
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        expected = {
            "approval_policy_missing_evidence",
            "approval_policy_missing_required_evidence_kinds",
            "approval_policy_missing_human_decision_requirement",
            "approval_policy_missing_current_decision_requirement",
            "approval_policy_missing_accepted_evidence_requirement",
            "approval_policy_missing_integrity_requirement",
            "approval_policy_missing_explicit_scope",
            "approval_policy_missing_action_fingerprint",
            "approval_policy_missing_expiration",
            "approval_policy_missing_audit_logging",
            "approval_policy_missing_revocation_path",
            "approval_policy_allows_blanket_approval",
            "approval_policy_allows_reuse_after_scope_drift",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_authority_flags_and_text_laundering_block_review(self) -> None:
        review = build_control_plane_approval_policy_review(
            [
                _policy(
                    {
                        "authority_boundary": "approval_store_boundary_request",
                        "claims_approval_authority": True,
                        "grants_execution_permission": True,
                        "acts_as_permission_layer": True,
                        "registers_approval_store": True,
                        "reads_live_approval_store": True,
                        "schedules_work": True,
                        "selects_next_action": True,
                        "mutates_state": True,
                        "auto_apply": True,
                        "contains_secret_material": True,
                        "summary": "Approval grants permission and approval store is truth.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        expected = {
            "approval_policy_requests_store_boundary",
            "approval_policy_claims_approval_authority",
            "approval_policy_grants_execution_permission",
            "approval_policy_acts_as_permission_layer",
            "approval_policy_registers_approval_store",
            "approval_policy_reads_live_approval_store",
            "approval_policy_schedules_work",
            "approval_policy_selects_next_action",
            "approval_policy_mutates_state",
            "approval_policy_auto_apply",
            "approval_policy_contains_secret_material",
            "approval_policy_text_launders_authority",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_cross_review_drift_is_reported_as_findings_not_permission(self) -> None:
        review = build_control_plane_approval_policy_review(
            [
                _policy(
                    {
                        "depends_on_decision_ids": ["decision-old", "decision-missing"],
                        "referenced_rule_ids": ["rule-missing"],
                        "referenced_tool_manifest_ids": ["manifest-missing"],
                        "referenced_work_item_ids": ["work-missing"],
                        "requires_tool_review": True,
                        "requires_work_queue_review": True,
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=_decision_review(),
            evidence_policy_review=_evidence_policy_review("evidence_policy_review_attention_required"),
            integrity_review=_integrity_review("control_plane_integrity_drift_observed"),
        )

        expected = {
            "approval_policy_references_non_current_decision",
            "approval_policy_missing_rule_promotion_review",
            "approval_policy_over_evidence_policy_drift",
            "approval_policy_missing_tool_manifest_review",
            "approval_policy_missing_work_queue_review",
            "approval_policy_over_integrity_drift",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))
        self.assertTrue(review.approval_policy_review_is_not_permission)
        self.assertEqual("approval_policy_review_blocked", review.review_status)

    def test_renderers_preserve_guardrails_and_reject_forged_summaries(self) -> None:
        review = build_control_plane_approval_policy_review(
            [_policy()],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        payload = json.loads(render_control_plane_approval_policy_review_json(review))
        markdown = render_control_plane_approval_policy_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["approval_policy_review_is_not_permission"])
        self.assertIn("approval_policy_review_is_not_permission: true", markdown)
        self.assertIn("approval_presence_is_not_sufficient_evidence: true", markdown)

        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "finding_count"):
            render_control_plane_approval_policy_review_json(replace(review, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "finding_codes"):
            render_control_plane_approval_policy_review_json(replace(review, finding_codes=("forged",)))
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "severity_counts"):
            render_control_plane_approval_policy_review_json(replace(review, severity_counts={"high": 2}))
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "guardrails"):
            render_control_plane_approval_policy_review_json(replace(review, approval_policy_review_is_not_permission=False))
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "disjoint"):
            render_control_plane_approval_policy_review_json(replace(review, non_latest_policy_ids=("approval-policy",)))

    def test_supplied_review_guardrail_drift_is_rejected(self) -> None:
        with self.assertRaisesRegex(ControlPlaneApprovalPolicyReviewError, "must not mutate state"):
            build_control_plane_approval_policy_review(
                [_policy()],
                review_as_of=REVIEW_AS_OF,
                evidence_policy_review=replace(_evidence_policy_review(), state_change="mutated"),
                integrity_review=_integrity_review(),
            )

    def test_package_source_contains_no_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_approval_policy_review"
        source = "\n".join(path.read_text(encoding="utf-8") for path in sorted(package_root.glob("*.py")))

        forbidden = (
            "read_text(",
            "write_text(",
            ".cerebro",
            "docs/operations",
            "core.",
            "subprocess",
            "requests.",
            "temporalio",
            "langgraph",
            "opentelemetry",
            "from cli",
            "from extensions",
        )
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
