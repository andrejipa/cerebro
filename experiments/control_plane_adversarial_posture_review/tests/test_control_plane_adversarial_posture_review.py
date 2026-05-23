from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_adversarial_posture_review import (
    ControlPlaneAdversarialPostureReviewError,
    build_control_plane_adversarial_posture_review,
    render_control_plane_adversarial_posture_review_json,
    render_control_plane_adversarial_posture_review_markdown,
)
from experiments.control_plane_boundary_audit import (
    ControlPlaneBoundaryAuditFinding,
    ControlPlaneBoundaryAuditReport,
)
from experiments.control_plane_integrity_review.tests.test_control_plane_integrity_review import (
    _clean_boundary_report,
    _clean_guardrail_and_lineage_reports,
)


def _clean_subjects():
    guardrail, lineage = _clean_guardrail_and_lineage_reports()
    return (_clean_boundary_report(), guardrail, lineage)


class ControlPlaneAdversarialPostureReviewTests(unittest.TestCase):
    def test_clean_advisory_subjects_preserve_posture(self) -> None:
        review = build_control_plane_adversarial_posture_review(
            _clean_subjects(),
            review_as_of="2026-05-08",
            required_guardrail_names=("must_not_execute_automatically",),
        )

        self.assertEqual("adversarial_posture_preserved", review.review_status)
        self.assertEqual(3, review.subject_count)
        self.assertEqual(0, review.finding_count)
        self.assertEqual(set(review.subject_ids), set(review.clean_subject_ids))
        self.assertTrue(review.posture_review_is_not_permission)
        self.assertTrue(review.posture_status_is_not_truth)

    def test_detects_false_guardrails_and_forged_subject_summary(self) -> None:
        boundary = ControlPlaneBoundaryAuditReport(
            schema_version="1",
            audit_role="audits_control_plane_experiment_boundary_drift",
            package_count=1,
            source_count=1,
            audit_status="boundary_markers_preserved",
            finding_count=0,
            severity_counts={},
            package_counts={},
            finding_codes=(),
            findings=(
                ControlPlaneBoundaryAuditFinding(
                    code="permission_laundering_text",
                    severity="high",
                    package_name="control_plane_boundary_audit",
                    relative_path="README.md",
                    detail="hidden finding",
                ),
            ),
            audited_packages=("control_plane_boundary_audit",),
            audit_is_not_permission=False,
        )

        review = build_control_plane_adversarial_posture_review((boundary,), review_as_of="2026-05-08")

        self.assertEqual("adversarial_posture_blocked", review.review_status)
        self.assertIn("subject_guardrail_false", review.finding_codes)
        self.assertIn("subject_forged_finding_count", review.finding_codes)
        self.assertIn("subject_forged_finding_codes", review.finding_codes)
        self.assertIn("subject_forged_severity_counts", review.finding_codes)

    def test_detects_authority_status_and_text_laundering(self) -> None:
        boundary = replace(
            _clean_boundary_report(),
            audit_status="permission_granted",
            authority="non-authoritative; source of truth",
        )

        review = build_control_plane_adversarial_posture_review((boundary,), review_as_of="2026-05-08")

        self.assertIn("subject_status_launders_authority", review.finding_codes)
        self.assertIn("subject_text_launders_authority", review.finding_codes)

    def test_detects_status_contradictions_and_expected_blocker_loss(self) -> None:
        boundary = replace(
            _clean_boundary_report(),
            audit_status="boundary_markers_preserved",
            finding_count=1,
            severity_counts={"high": 1},
            package_counts={"control_plane_boundary_audit": 1},
            finding_codes=("permission_laundering_text",),
            findings=(
                ControlPlaneBoundaryAuditFinding(
                    code="permission_laundering_text",
                    severity="high",
                    package_name="control_plane_boundary_audit",
                    relative_path="README.md",
                    detail="status says clean but finding exists",
                ),
            ),
        )
        clean_boundary = _clean_boundary_report()

        review = build_control_plane_adversarial_posture_review(
            (boundary, clean_boundary),
            review_as_of="2026-05-08",
            expected_blocked_subject_ids=("boundary_audit_report.2",),
        )

        self.assertIn("clean_status_with_findings", review.finding_codes)
        self.assertIn("expected_blocker_disappeared", review.finding_codes)
        self.assertIn("boundary_audit_report.2", review.missing_expected_blocker_ids)

    def test_detects_blocking_status_without_evidence_and_missing_required_guardrail(self) -> None:
        boundary = replace(_clean_boundary_report(), audit_status="boundary_drift_observed")

        review = build_control_plane_adversarial_posture_review(
            (boundary,),
            review_as_of="2026-05-08",
            required_guardrail_names=("posture_review_is_not_permission",),
        )

        self.assertIn("blocking_status_without_evidence", review.finding_codes)
        self.assertIn("subject_missing_required_guardrail", review.finding_codes)

    def test_rejects_empty_inputs_bad_dates_and_bad_expected_ids(self) -> None:
        with self.assertRaisesRegex(ControlPlaneAdversarialPostureReviewError, "at least one"):
            build_control_plane_adversarial_posture_review((), review_as_of="2026-05-08")
        with self.assertRaisesRegex(ControlPlaneAdversarialPostureReviewError, "ISO date"):
            build_control_plane_adversarial_posture_review(_clean_subjects(), review_as_of="08-05-2026")
        with self.assertRaisesRegex(ControlPlaneAdversarialPostureReviewError, "path-segment"):
            build_control_plane_adversarial_posture_review(
                _clean_subjects(),
                review_as_of="2026-05-08",
                expected_blocked_subject_ids=("../escape",),
            )

    def test_renderers_preserve_guardrails_and_reject_forged_review(self) -> None:
        review = build_control_plane_adversarial_posture_review(_clean_subjects(), review_as_of="2026-05-08")

        payload = json.loads(render_control_plane_adversarial_posture_review_json(review))
        markdown = render_control_plane_adversarial_posture_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["posture_review_is_not_permission"])
        self.assertIn("posture_review_is_not_permission: true", markdown)
        with self.assertRaisesRegex(ControlPlaneAdversarialPostureReviewError, "finding_count"):
            render_control_plane_adversarial_posture_review_json(replace(review, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneAdversarialPostureReviewError, "guardrails"):
            render_control_plane_adversarial_posture_review_markdown(
                replace(review, posture_review_is_not_runtime_gate=False)
            )

    def test_package_source_has_no_runtime_io_or_store_surfaces(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", text)
        self.assertNotIn("from opentelemetry", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("write_text", text)
        self.assertNotIn("read_text", text)
        self.assertNotIn("open(", text)
        self.assertNotIn("approval_store", text)
        self.assertNotIn("observation_center", text)


if __name__ == "__main__":
    unittest.main()
