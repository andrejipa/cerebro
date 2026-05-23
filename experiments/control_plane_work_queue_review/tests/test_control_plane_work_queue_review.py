from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_evidence_policy_review import build_control_plane_evidence_policy_review
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_work_queue_review import (
    ControlPlaneWorkQueueReviewError,
    build_control_plane_work_queue_review,
    render_control_plane_work_queue_review_json,
    render_control_plane_work_queue_review_markdown,
)


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


def _evidence_policy_review():
    policy = {
        "policy_id": "policy-evidence",
        "policy_thread_id": "evidence-policy",
        "revision": 1,
        "lifecycle_status": "active_candidate",
        "policy_scope": "control_plane",
        "authority_boundary": "candidate_policy",
        "supersedes_policy_id": "",
        "evidence_ids": ["policy-source-1"],
        "depends_on_decision_ids": [],
        "referenced_rule_ids": [],
        "allowed_evidence_kinds": ["test_run", "review_report", "sanitized_artifact"],
        "accepted_statuses": ["accepted"],
        "requires_human_decision_for_sensitive": True,
        "requires_redaction_for_sensitive": True,
        "rejects_raw_evidence": True,
        "rejects_secret_material": True,
        "retention_policy_defined": True,
        "expiration_policy_defined": True,
        "provenance_policy_defined": True,
        "rejection_policy_defined": True,
        "audit_logging_defined": True,
        "claims_evidence_authority": False,
        "grants_execution_permission": False,
        "registers_evidence_store": False,
        "reads_live_evidence_store": False,
        "mutates_state": False,
        "auto_apply": False,
        "contains_secret_material": False,
        "summary": "Candidate evidence policy for advisory work queue review only.",
        "rationale": "This policy is non-authoritative and does not grant permission.",
    }
    record = {
        "evidence_id": "evidence-clean",
        "evidence_kind": "test_run",
        "status": "accepted",
        "data_sensitivity": "internal",
        "source_scope": "local_repo",
        "collected_at": REVIEW_AS_OF,
        "expires_on": "2026-06-01",
        "policy_ids": ["policy-evidence"],
        "human_decision_id": "",
        "sanitized": True,
        "redacted": True,
        "contains_raw_evidence": False,
        "contains_secret_material": False,
        "contains_personal_data": False,
        "claims_truth": False,
        "grants_permission": False,
        "summary": "Sanitized evidence reference only.",
        "rationale": "Evidence is not truth and does not grant permission.",
    }
    return build_control_plane_evidence_policy_review(
        [policy],
        review_as_of=REVIEW_AS_OF,
        evidence_record_payloads=[record],
        integrity_review=_integrity_review(),
    )


def _item(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "item_id": "work-1",
        "queue_id": "control-plane-growth",
        "item_thread_id": "work-thread",
        "revision": 1,
        "lifecycle_status": "ready_candidate",
        "queue_scope": "control_plane",
        "item_kind": "qa",
        "priority": "P2",
        "status": "ready_candidate",
        "supersedes_item_id": "",
        "depends_on_item_ids": [],
        "evidence_ids": ["evidence-clean"],
        "expected_evidence_kinds": ["test_run"],
        "referenced_decision_ids": [],
        "referenced_rule_ids": [],
        "owner": "operator",
        "acceptance_criteria": ["criteria-1"],
        "dependencies_satisfied": True,
        "human_decision_required": False,
        "approval_id": "",
        "ready_for_execution": False,
        "auto_dispatch": False,
        "claims_queue_authority": False,
        "claims_scheduler_authority": False,
        "claims_priority_truth": False,
        "grants_execution_permission": False,
        "reads_live_queue": False,
        "mutates_state": False,
        "registers_queue_reader": False,
        "contains_secret_material": False,
        "summary": "Advisory candidate for review only.",
        "rationale": "Queue review is not permission and not a scheduler.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneWorkQueueReviewTests(unittest.TestCase):
    def test_clean_queue_candidate_is_observed_without_permission(self) -> None:
        review = build_control_plane_work_queue_review(
            [_item()],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        self.assertEqual("work_queue_candidates_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.work_queue_review_is_not_permission)
        self.assertTrue(review.work_queue_review_is_not_scheduler)
        self.assertTrue(review.queue_priority_is_not_truth)
        self.assertTrue(review.ready_status_is_not_execution_approval)
        self.assertEqual(("work-1",), review.ready_candidate_ids)

    def test_rejects_empty_duplicate_unsafe_unknown_enum_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "at least one"):
            build_control_plane_work_queue_review([], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "duplicate item ids"):
            build_control_plane_work_queue_review([_item(), _item()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "path-segment safe"):
            build_control_plane_work_queue_review([_item({"item_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "unknown lifecycle_status"):
            build_control_plane_work_queue_review([_item({"lifecycle_status": "canonical"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "unknown priority"):
            build_control_plane_work_queue_review([_item({"priority": "urgent"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "unknown values"):
            build_control_plane_work_queue_review([_item({"expected_evidence_kinds": ["oracle"]})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "review_as_of must be an ISO date"):
            build_control_plane_work_queue_review([_item()], review_as_of="today")

    def test_revision_supersession_and_ready_drift_are_found(self) -> None:
        review = build_control_plane_work_queue_review(
            [
                _item({"item_id": "work-r1", "item_thread_id": "thread", "revision": 1}),
                _item(
                    {
                        "item_id": "work-r3",
                        "item_thread_id": "thread",
                        "revision": 3,
                        "supersedes_item_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        self.assertEqual("work_queue_review_blocked", review.review_status)
        self.assertIn("work_queue_revision_gap", review.finding_codes)
        self.assertIn("work_queue_supersedes_unknown_id", review.finding_codes)
        self.assertIn("multiple_ready_work_queue_candidates", review.finding_codes)

    def test_readiness_dependency_and_evidence_controls_block_review(self) -> None:
        review = build_control_plane_work_queue_review(
            [
                _item({"item_id": "blocked-dep", "status": "blocked", "lifecycle_status": "blocked"}),
                _item(
                    {
                        "item_id": "work-bad",
                        "item_thread_id": "work-bad-thread",
                        "depends_on_item_ids": ["blocked-dep", "missing-dep"],
                        "evidence_ids": [],
                        "expected_evidence_kinds": [],
                        "acceptance_criteria": [],
                        "owner": "",
                        "dependencies_satisfied": False,
                        "human_decision_required": True,
                        "priority": "P0",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        expected = {
            "work_queue_unknown_dependency",
            "work_queue_depends_on_blocked_item",
            "work_queue_missing_evidence",
            "work_queue_missing_expected_evidence_kinds",
            "work_queue_missing_acceptance_criteria",
            "work_queue_missing_owner",
            "ready_work_queue_item_dependencies_unsatisfied",
            "ready_work_queue_item_missing_human_approval",
            "high_priority_work_queue_item_missing_decision",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_authority_flags_and_text_laundering_block_review(self) -> None:
        review = build_control_plane_work_queue_review(
            [
                _item(
                    {
                        "claims_queue_authority": True,
                        "claims_scheduler_authority": True,
                        "claims_priority_truth": True,
                        "grants_execution_permission": True,
                        "reads_live_queue": True,
                        "mutates_state": True,
                        "registers_queue_reader": True,
                        "auto_dispatch": True,
                        "contains_secret_material": True,
                        "summary": "The canonical work queue selected next action.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        expected = {
            "work_queue_item_claims_queue_authority",
            "work_queue_item_claims_scheduler_authority",
            "work_queue_item_claims_priority_truth",
            "work_queue_item_grants_execution_permission",
            "work_queue_item_reads_live_queue",
            "work_queue_item_mutates_state",
            "work_queue_item_registers_queue_reader",
            "work_queue_item_auto_dispatch",
            "work_queue_item_contains_secret_material",
            "work_queue_item_text_launders_authority",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_cross_review_drift_is_reported(self) -> None:
        bad_evidence = replace(_evidence_policy_review(), review_status="evidence_policy_review_blocked")
        review = build_control_plane_work_queue_review(
            [_item({"referenced_decision_ids": ["decision-missing"], "referenced_rule_ids": ["rule-missing"]})],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=bad_evidence,
            integrity_review=_integrity_review(status="control_plane_integrity_drift_observed"),
        )

        self.assertIn("work_queue_missing_decision_review", review.finding_codes)
        self.assertIn("work_queue_missing_rule_promotion_review", review.finding_codes)
        self.assertIn("work_queue_over_integrity_drift", review.finding_codes)
        self.assertIn("work_queue_over_evidence_policy_drift", review.finding_codes)

    def test_missing_required_reviews_are_findings_not_permission(self) -> None:
        review = build_control_plane_work_queue_review([_item()], review_as_of=REVIEW_AS_OF)

        self.assertEqual("work_queue_review_blocked", review.review_status)
        self.assertIn("work_queue_missing_integrity_review", review.finding_codes)
        self.assertIn("work_queue_missing_evidence_policy_review", review.finding_codes)
        self.assertTrue(review.work_queue_review_is_not_permission)
        self.assertTrue(review.work_queue_review_is_not_scheduler)

    def test_renderers_preserve_guardrails_and_reject_forged_summary_fields(self) -> None:
        review = build_control_plane_work_queue_review(
            [_item()],
            review_as_of=REVIEW_AS_OF,
            evidence_policy_review=_evidence_policy_review(),
            integrity_review=_integrity_review(),
        )

        payload = json.loads(render_control_plane_work_queue_review_json(review))
        markdown = render_control_plane_work_queue_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["work_queue_review_is_not_permission"])
        self.assertTrue(payload["work_queue_review_is_not_scheduler"])
        self.assertIn("work_queue_review_is_not_scheduler: true", markdown)
        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "finding_count"):
            render_control_plane_work_queue_review_json(replace(review, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "finding_codes"):
            render_control_plane_work_queue_review_json(replace(review, finding_codes=("forged",)))
        with self.assertRaisesRegex(ControlPlaneWorkQueueReviewError, "guardrails"):
            render_control_plane_work_queue_review_json(replace(review, work_queue_review_is_not_scheduler=False))

    def test_package_source_contains_no_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_work_queue_review"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py")).lower()

        forbidden = [
            "read_text(",
            "write_text(",
            ".cerebro",
            "docs/operations",
            "core.",
            "subprocess",
            "import requests",
            "requests.",
            "temporalio",
            "langgraph",
            "opentelemetry",
            "from cli",
            "from extensions",
            "import cli",
            "import extensions",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
