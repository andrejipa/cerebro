from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_evidence_policy_review import (
    ControlPlaneEvidencePolicyReviewError,
    build_control_plane_evidence_policy_review,
    render_control_plane_evidence_policy_review_json,
    render_control_plane_evidence_policy_review_markdown,
)
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


def _policy(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
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
        "allowed_evidence_kinds": ["human_decision", "test_run", "review_report", "sanitized_artifact"],
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
        "summary": "Candidate evidence policy for advisory review only.",
        "rationale": "This policy is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _record(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
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
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneEvidencePolicyReviewTests(unittest.TestCase):
    def test_clean_policy_and_record_are_observed_without_permission(self) -> None:
        review = build_control_plane_evidence_policy_review(
            [_policy()],
            review_as_of=REVIEW_AS_OF,
            evidence_record_payloads=[_record()],
            integrity_review=_integrity_review(),
        )

        self.assertEqual("evidence_policy_candidate_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.evidence_policy_review_is_not_permission)
        self.assertTrue(review.accepted_evidence_is_not_truth)
        self.assertTrue(review.evidence_record_is_not_truth)
        self.assertTrue(review.silence_is_not_negative_evidence)
        self.assertTrue(review.secret_material_must_not_be_retained)
        self.assertEqual(("evidence-clean",), review.accepted_evidence_ids)

    def test_rejects_empty_duplicate_unsafe_unknown_enum_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "at least one"):
            build_control_plane_evidence_policy_review([], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "duplicate policy ids"):
            build_control_plane_evidence_policy_review([_policy(), _policy()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "path-segment safe"):
            build_control_plane_evidence_policy_review([_policy({"policy_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "unknown lifecycle_status"):
            build_control_plane_evidence_policy_review([_policy({"lifecycle_status": "canonical"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "unknown values"):
            build_control_plane_evidence_policy_review(
                [_policy({"allowed_evidence_kinds": ["oracle"]})],
                review_as_of=REVIEW_AS_OF,
            )

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "review_as_of must be an ISO date"):
            build_control_plane_evidence_policy_review([_policy()], review_as_of="today")

        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "duplicate evidence record ids"):
            build_control_plane_evidence_policy_review(
                [_policy()],
                review_as_of=REVIEW_AS_OF,
                evidence_record_payloads=[_record(), _record()],
            )

    def test_revision_supersession_and_active_drift_are_found(self) -> None:
        review = build_control_plane_evidence_policy_review(
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
            integrity_review=_integrity_review(),
        )

        self.assertEqual("evidence_policy_review_blocked", review.review_status)
        self.assertIn("evidence_policy_revision_gap", review.finding_codes)
        self.assertIn("evidence_policy_supersedes_unknown_id", review.finding_codes)
        self.assertIn("multiple_active_evidence_policy_candidates", review.finding_codes)

    def test_policy_missing_controls_and_boundary_flags_are_blocked(self) -> None:
        review = build_control_plane_evidence_policy_review(
            [
                _policy(
                    {
                        "evidence_ids": [],
                        "allowed_evidence_kinds": [],
                        "accepted_statuses": [],
                        "requires_human_decision_for_sensitive": False,
                        "requires_redaction_for_sensitive": False,
                        "rejects_raw_evidence": False,
                        "rejects_secret_material": False,
                        "retention_policy_defined": False,
                        "expiration_policy_defined": False,
                        "provenance_policy_defined": False,
                        "claims_evidence_authority": True,
                        "grants_execution_permission": True,
                        "registers_evidence_store": True,
                        "reads_live_evidence_store": True,
                        "mutates_state": True,
                        "auto_apply": True,
                        "contains_secret_material": True,
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        expected = {
            "evidence_policy_missing_evidence",
            "evidence_policy_does_not_define_acceptance",
            "evidence_policy_missing_allowed_kinds",
            "evidence_policy_allows_raw_evidence",
            "evidence_policy_allows_secret_material",
            "evidence_policy_missing_sensitive_human_decision",
            "evidence_policy_missing_sensitive_redaction",
            "evidence_policy_missing_retention_policy",
            "evidence_policy_missing_expiration_policy",
            "evidence_policy_missing_provenance_policy",
            "evidence_policy_claims_evidence_authority",
            "evidence_policy_grants_execution_permission",
            "evidence_policy_registers_evidence_store",
            "evidence_policy_reads_live_evidence_store",
            "evidence_policy_mutates_state",
            "evidence_policy_auto_apply",
            "evidence_policy_contains_secret_material",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_accepted_raw_secret_sensitive_expired_evidence_is_blocked(self) -> None:
        review = build_control_plane_evidence_policy_review(
            [_policy()],
            review_as_of=REVIEW_AS_OF,
            evidence_record_payloads=[
                _record(
                    {
                        "evidence_id": "evidence-bad",
                        "evidence_kind": "raw_dump",
                        "data_sensitivity": "secret",
                        "expires_on": "2026-01-01",
                        "human_decision_id": "",
                        "sanitized": False,
                        "redacted": False,
                        "contains_raw_evidence": True,
                        "contains_secret_material": True,
                        "contains_personal_data": True,
                        "claims_truth": True,
                        "grants_permission": True,
                        "summary": "Evidence approved execution.",
                    }
                )
            ],
            integrity_review=_integrity_review(),
        )

        expected = {
            "accepted_evidence_kind_not_allowed",
            "accepted_evidence_contains_raw_material",
            "accepted_evidence_contains_secret_material",
            "accepted_sensitive_evidence_not_redacted",
            "accepted_evidence_not_sanitized",
            "accepted_personal_data_without_human_decision",
            "accepted_sensitive_evidence_without_human_decision",
            "accepted_evidence_expired",
            "evidence_record_claims_truth",
            "evidence_record_grants_permission",
            "evidence_record_text_launders_authority",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_cross_review_drift_is_reported(self) -> None:
        review = build_control_plane_evidence_policy_review(
            [_policy({"depends_on_decision_ids": ["decision-missing"], "referenced_rule_ids": ["rule-missing"]})],
            review_as_of=REVIEW_AS_OF,
            evidence_record_payloads=[_record({"human_decision_id": "decision-missing"})],
            integrity_review=_integrity_review(status="control_plane_integrity_drift_detected"),
        )

        self.assertIn("evidence_policy_missing_decision_review", review.finding_codes)
        self.assertIn("evidence_policy_missing_rule_promotion_review", review.finding_codes)
        self.assertIn("evidence_policy_over_integrity_drift", review.finding_codes)

    def test_renderers_preserve_guardrails_and_reject_forged_summary_fields(self) -> None:
        review = build_control_plane_evidence_policy_review(
            [_policy()],
            review_as_of=REVIEW_AS_OF,
            evidence_record_payloads=[_record()],
            integrity_review=_integrity_review(),
        )

        payload = json.loads(render_control_plane_evidence_policy_review_json(review))
        markdown = render_control_plane_evidence_policy_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["evidence_policy_review_is_not_permission"])
        self.assertTrue(payload["silence_is_not_negative_evidence"])
        self.assertIn("evidence_policy_review_is_not_permission: true", markdown)
        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "finding_count"):
            render_control_plane_evidence_policy_review_json(replace(review, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "finding_codes"):
            render_control_plane_evidence_policy_review_json(replace(review, finding_codes=("forged",)))
        with self.assertRaisesRegex(ControlPlaneEvidencePolicyReviewError, "guardrails"):
            render_control_plane_evidence_policy_review_json(replace(review, accepted_evidence_is_not_truth=False))

    def test_package_source_contains_no_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_evidence_policy_review"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py")).lower()

        forbidden = [
            "read_text(",
            "write_text(",
            ".cerebro",
            "docs/operations",
            "core.state_store",
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
