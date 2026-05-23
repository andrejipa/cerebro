from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_decision_version_review import build_control_plane_decision_version_review
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import build_control_plane_rule_promotion_review
from experiments.control_plane_runtime_adoption_review import build_control_plane_runtime_adoption_review
from experiments.control_plane_runtime_contract_review import (
    ControlPlaneRuntimeContractReviewError,
    build_control_plane_runtime_contract_review,
    render_control_plane_runtime_contract_review_json,
    render_control_plane_runtime_contract_review_markdown,
)
from experiments.control_plane_runtime_state_review import build_control_plane_runtime_state_review


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"
ALL_SECTIONS = [
    "mission",
    "non_goals",
    "states",
    "transitions",
    "gates",
    "permissions",
    "evidence_policy",
    "task_queue",
    "dependencies",
    "retry_policy",
    "rollback_policy",
    "observability",
    "decision_versioning",
    "handoff",
    "tool_manifest",
    "security_limits",
    "memory_policy",
    "stop_rules",
]


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


def _contract(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_id": "contract-runtime-manager",
        "contract_thread_id": "runtime-manager-contract",
        "revision": 1,
        "lifecycle_status": "active_candidate",
        "contract_scope": "runtime_manager",
        "authority_boundary": "candidate_contract",
        "supersedes_contract_id": "",
        "declared_sections": list(ALL_SECTIONS),
        "evidence_ids": ["evidence-1"],
        "depends_on_decision_ids": [],
        "referenced_rule_ids": [],
        "runtime_adoption_candidate_ids": [],
        "runtime_state_snapshot_ids": [],
        "state_model_proposed": True,
        "machine_readable_state": True,
        "queue_model_proposed": True,
        "tool_manifest_proposed": True,
        "approval_policy_defined": True,
        "evidence_policy_defined": True,
        "rollback_policy_defined": True,
        "retry_policy_defined": True,
        "observability_defined": True,
        "decision_versioning_defined": True,
        "handoff_protocol_defined": True,
        "security_limits_defined": True,
        "stop_rules_defined": True,
        "claims_runtime_authority": False,
        "claims_canonical_contract": False,
        "grants_execution_permission": False,
        "enables_scheduler": False,
        "reads_live_state": False,
        "mutates_state": False,
        "imports_adapters": False,
        "auto_apply": False,
        "contains_secret_material": False,
        "summary": "Candidate runtime manager contract for advisory review only.",
        "rationale": "This contract is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _decision(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision_id": "decision-contract",
        "decision_thread_id": "runtime-contract-decision",
        "observation_id": "runtime-contract",
        "revision": 1,
        "decision_kind": "approval",
        "status": "current",
        "decided_by": "HumanOperator",
        "decided_at": REVIEW_AS_OF,
        "valid_until": "",
        "supersedes_decision_id": "",
        "human_decision_id": "human-contract-1",
        "referenced_evidence_ids": ["evidence-1"],
        "auto_continue": False,
        "summary": "Human approval for advisory runtime contract review only.",
        "rationale": "This decision record does not grant execution approval.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _rule(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "rule_id": "rule-runtime-contract",
        "rule_thread_id": "runtime-contract-rule",
        "revision": 1,
        "rule_family": "runtime_contract",
        "current_status": "active",
        "proposed_change": "keep",
        "risk_level": "medium",
        "supersedes_rule_id": "",
        "evidence_ids": ["evidence-1"],
        "depends_on_decision_ids": [],
        "human_decision_required": False,
        "human_decision_id": "none",
        "auto_apply": False,
        "summary": "Active advisory runtime contract rule.",
        "rationale": "The rule is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _adoption(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "proposal_id": "proposal-runtime",
        "proposal_thread_id": "runtime-proposal",
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


def _snapshot(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "snapshot_id": "snapshot-runtime",
        "snapshot_thread_id": "runtime-state",
        "revision": 1,
        "captured_at": REVIEW_AS_OF,
        "state_scope": "cerebro_runtime",
        "lifecycle_status": "observed",
        "queue_authority": "not_supplied",
        "schema_version_claim": "1",
        "active_observation_ids": [],
        "open_ready_observation_ids": [],
        "blocked_observation_ids": [],
        "current_decision_ids": [],
        "active_rule_ids": [],
        "runtime_adoption_candidate_ids": [],
        "evidence_ids": ["evidence-1"],
        "supersedes_snapshot_id": "",
        "contains_secret_material": False,
        "contains_raw_evidence": False,
        "claims_canonical_state": False,
        "claims_scheduler_authority": False,
        "claims_execution_permission": False,
        "auto_apply": False,
        "generated_by": "test",
        "summary": "Advisory runtime-state snapshot only.",
        "rationale": "This snapshot is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneRuntimeContractReviewTests(unittest.TestCase):
    def test_clean_contract_candidate_is_observed_without_permission(self) -> None:
        review = build_control_plane_runtime_contract_review(
            [_contract()],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertEqual("runtime_contract_candidate_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.contract_review_is_not_permission)
        self.assertTrue(review.contract_candidate_is_not_canonical_runtime_contract)
        self.assertTrue(review.contract_review_is_not_scheduler)
        self.assertTrue(review.contract_review_is_not_state_store)

    def test_rejects_duplicate_unsafe_unknown_enum_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "duplicate contract ids"):
            build_control_plane_runtime_contract_review([_contract(), _contract()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "path-segment safe"):
            build_control_plane_runtime_contract_review([_contract({"contract_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "unknown lifecycle_status"):
            build_control_plane_runtime_contract_review([_contract({"lifecycle_status": "canonical"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "unknown declared section"):
            build_control_plane_runtime_contract_review(
                [_contract({"declared_sections": ALL_SECTIONS + ["canonical_power"]})],
                review_as_of=REVIEW_AS_OF,
            )

        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "review_as_of must be an ISO date"):
            build_control_plane_runtime_contract_review([_contract()], review_as_of="today")

    def test_revision_supersession_and_active_drift_are_found(self) -> None:
        review = build_control_plane_runtime_contract_review(
            [
                _contract({"contract_id": "contract-r1", "contract_thread_id": "thread", "revision": 1}),
                _contract(
                    {
                        "contract_id": "contract-r3",
                        "contract_thread_id": "thread",
                        "revision": 3,
                        "supersedes_contract_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertEqual("runtime_contract_review_blocked", review.review_status)
        self.assertIn("contract_revision_gap", review.finding_codes)
        self.assertIn("contract_supersedes_unknown_id", review.finding_codes)
        self.assertIn("multiple_active_runtime_contract_candidates", review.finding_codes)

    def test_missing_contract_surfaces_and_missing_evidence_block_review(self) -> None:
        sparse = _contract(
            {
                "declared_sections": ["mission", "non_goals"],
                "evidence_ids": [],
                "machine_readable_state": False,
                "queue_model_proposed": False,
                "approval_policy_defined": False,
                "evidence_policy_defined": False,
                "security_limits_defined": False,
                "stop_rules_defined": False,
            }
        )
        review = build_control_plane_runtime_contract_review(
            [sparse],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertIn("contract_missing_required_section", review.finding_codes)
        self.assertIn("contract_missing_evidence", review.finding_codes)
        self.assertIn("contract_missing_machine_readable_state", review.finding_codes)
        self.assertIn("contract_missing_queue_model", review.finding_codes)
        self.assertIn("contract_missing_approval_policy", review.finding_codes)
        self.assertIn("contract_missing_stop_rules", review.finding_codes)

    def test_authority_flags_and_text_laundering_block_review(self) -> None:
        review = build_control_plane_runtime_contract_review(
            [
                _contract(
                    {
                        "claims_runtime_authority": True,
                        "claims_canonical_contract": True,
                        "grants_execution_permission": True,
                        "enables_scheduler": True,
                        "reads_live_state": True,
                        "mutates_state": True,
                        "imports_adapters": True,
                        "auto_apply": True,
                        "contains_secret_material": True,
                        "summary": "This canonical runtime contract grants permission and selected next action.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertIn("contract_claims_runtime_authority", review.finding_codes)
        self.assertIn("contract_claims_canonical_contract", review.finding_codes)
        self.assertIn("contract_grants_execution_permission", review.finding_codes)
        self.assertIn("contract_enables_scheduler", review.finding_codes)
        self.assertIn("contract_requests_live_state_read", review.finding_codes)
        self.assertIn("contract_requests_state_mutation", review.finding_codes)
        self.assertIn("contract_requests_adapter_import", review.finding_codes)
        self.assertIn("contract_requests_auto_apply", review.finding_codes)
        self.assertIn("contract_contains_secret_material", review.finding_codes)
        self.assertIn("contract_text_launders_runtime_authority", review.finding_codes)

    def test_decision_rule_integrity_adoption_and_state_references_are_checked(self) -> None:
        decision_review = build_control_plane_decision_version_review([_decision()], review_as_of=REVIEW_AS_OF)
        rule_review = build_control_plane_rule_promotion_review([_rule()], review_as_of=REVIEW_AS_OF)
        adoption_review = build_control_plane_runtime_adoption_review([_adoption()], review_as_of=REVIEW_AS_OF)
        state_review = build_control_plane_runtime_state_review([_snapshot()], review_as_of=REVIEW_AS_OF)

        review = build_control_plane_runtime_contract_review(
            [
                _contract(
                    {
                        "depends_on_decision_ids": ["missing-decision"],
                        "referenced_rule_ids": ["missing-rule"],
                        "runtime_adoption_candidate_ids": ["missing-proposal"],
                        "runtime_state_snapshot_ids": ["missing-snapshot"],
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            decision_review=decision_review,
            rule_promotion_review=rule_review,
            runtime_adoption_review=adoption_review,
            runtime_state_review=state_review,
            integrity_review=_integrity_review("control_plane_integrity_drift_observed"),
        )

        self.assertIn("contract_references_non_current_decision", review.finding_codes)
        self.assertIn("contract_references_non_active_rule", review.finding_codes)
        self.assertIn("contract_references_unknown_runtime_adoption_candidate", review.finding_codes)
        self.assertIn("contract_references_unknown_runtime_state_snapshot", review.finding_codes)
        self.assertIn("contract_over_integrity_drift", review.finding_codes)

    def test_missing_required_reviews_are_findings_not_implicit_permission(self) -> None:
        review = build_control_plane_runtime_contract_review(
            [
                _contract(
                    {
                        "depends_on_decision_ids": ["decision-contract"],
                        "referenced_rule_ids": ["rule-runtime-contract"],
                        "runtime_adoption_candidate_ids": ["proposal-runtime"],
                        "runtime_state_snapshot_ids": ["snapshot-runtime"],
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("contract_missing_decision_review", review.finding_codes)
        self.assertIn("contract_missing_rule_promotion_review", review.finding_codes)
        self.assertIn("contract_missing_integrity_review", review.finding_codes)
        self.assertIn("contract_missing_runtime_adoption_review", review.finding_codes)
        self.assertIn("contract_missing_runtime_state_review", review.finding_codes)
        self.assertTrue(review.contract_review_is_not_permission)

    def test_rejects_supplied_review_guardrail_drift(self) -> None:
        bad_integrity = replace(_integrity_review(), review_is_not_permission=False)

        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "integrity review guardrails"):
            build_control_plane_runtime_contract_review(
                [_contract()],
                review_as_of=REVIEW_AS_OF,
                integrity_review=bad_integrity,
            )

    def test_renderers_preserve_guardrails_and_reject_forged_summary(self) -> None:
        review = build_control_plane_runtime_contract_review(
            [_contract()],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )
        payload = json.loads(render_control_plane_runtime_contract_review_json(review))
        markdown = render_control_plane_runtime_contract_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["contract_review_is_not_permission"])
        self.assertIn("contract_candidate_is_not_canonical_runtime_contract: true", markdown)
        self.assertIn("contract_review_is_not_scheduler: true", markdown)
        self.assertIn("contract_review_is_not_state_store: true", markdown)

        forged_count = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "finding_count"):
            render_control_plane_runtime_contract_review_json(forged_count)

        forged_overlap = replace(review, latest_contract_ids=("contract-runtime-manager",), non_latest_contract_ids=("contract-runtime-manager",))
        with self.assertRaisesRegex(ControlPlaneRuntimeContractReviewError, "disjoint"):
            render_control_plane_runtime_contract_review_json(forged_overlap)

    def test_package_contains_no_state_store_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_runtime_contract_review"
        source_text = "\n".join(path.read_text(encoding="utf-8").lower() for path in sorted(package_root.glob("*.py")))

        forbidden_fragments = (
            "core.",
            "cli.",
            "extensions.",
            "read_text",
            "write_text",
            ".cerebro",
            "docs/operations",
            "state.json",
            "subprocess",
            "import requests",
            "temporalio",
            "langgraph",
            "opentelemetry",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()
