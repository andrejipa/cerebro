from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_boundary_audit import (
    ControlPlaneBoundaryAuditFinding,
    ControlPlaneBoundaryAuditReport,
)
from experiments.control_plane_guardrail_eval import (
    ControlPlaneGuardrailFinding,
    ControlPlaneGuardrailReport,
    evaluate_control_plane_guardrails,
)
from experiments.control_plane_integrity_review import (
    ControlPlaneIntegrityReviewError,
    build_control_plane_integrity_review,
    render_control_plane_integrity_review_json,
    render_control_plane_integrity_review_markdown,
)
from experiments.control_plane_lineage_invariant_eval import (
    ControlPlaneLineageInvariantFinding,
    ControlPlaneLineageInvariantReport,
    evaluate_control_plane_packet_projection_lineage,
)
from experiments.control_plane_review_packet import build_control_plane_review_packet
from experiments.control_plane_telemetry_projection import project_control_plane_packet_to_telemetry


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
        audited_packages=("control_plane_integrity_review",),
    )


def _assessment(**overrides) -> ControlPlaneAssessment:
    values = {
        "selected_task_id": "task-ready",
        "decision_runtime_reason": "selected executable task",
        "task_selection_status": "match",
        "task_selection_reason": "current task matches derived selection",
        "epistemic_action_readiness": "advisory_report_allowed",
        "blockers": (),
        "missing_evidence": (),
        "stale_claims": (),
        "conflicts": (),
        "claim_evaluation_summary": {"ready_count": 1, "blocked_count": 0, "insufficient_count": 0},
        "operational_signal_summary": {
            "record_count": 0,
            "candidate_trigger_count": 0,
            "authority": "derived-observability-only",
            "non_authoritative": True,
        },
        "recommended_human_decision": "none",
        "must_not_execute_automatically": True,
        "advisory_pass_is_not_permission": True,
    }
    values.update(overrides)
    return ControlPlaneAssessment(**values)


def _capability() -> CapabilityAssessment:
    return CapabilityAssessment(
        request_id="req-integrity",
        matched_rule_id="integrity-test-rule",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


def _clean_guardrail_and_lineage_reports() -> tuple[ControlPlaneGuardrailReport, ControlPlaneLineageInvariantReport]:
    packet = build_control_plane_review_packet(
        "trace-integrity",
        _assessment(),
        capability_assessments=(_capability(),),
    )
    projection = project_control_plane_packet_to_telemetry(packet)
    guardrail_report = evaluate_control_plane_guardrails(projection)
    lineage_report = evaluate_control_plane_packet_projection_lineage(packet, projection)
    return guardrail_report, lineage_report


class ControlPlaneIntegrityReviewTests(unittest.TestCase):
    def test_clean_boundary_guardrail_and_lineage_reports_preserve_integrity(self) -> None:
        guardrail_report, lineage_report = _clean_guardrail_and_lineage_reports()

        review = build_control_plane_integrity_review(
            boundary_audit=_clean_boundary_report(),
            guardrail_reports=(guardrail_report,),
            lineage_reports=(lineage_report,),
        )

        self.assertEqual("control_plane_integrity_preserved", review.review_status)
        self.assertEqual(3, review.evidence_count)
        self.assertEqual(0, review.finding_count)
        self.assertEqual(
            {
                "boundary_markers_preserved": 1,
                "guardrails_preserved": 1,
                "lineage_invariants_preserved": 1,
            },
            review.source_status_counts,
        )
        self.assertTrue(review.review_is_not_permission)
        self.assertTrue(review.integrity_pass_is_not_truth)

    def test_boundary_findings_force_integrity_drift(self) -> None:
        boundary = replace(
            _clean_boundary_report(),
            audit_status="boundary_drift_observed",
            finding_count=1,
            severity_counts={"high": 1},
            package_counts={"control_plane_integrity_review": 1},
            finding_codes=("permission_laundering_text",),
            findings=(
                ControlPlaneBoundaryAuditFinding(
                    code="permission_laundering_text",
                    severity="high",
                    package_name="control_plane_integrity_review",
                    relative_path="README.md",
                    detail="permission marker appeared without local negation",
                ),
            ),
        )
        guardrail_report, _ = _clean_guardrail_and_lineage_reports()

        review = build_control_plane_integrity_review(
            boundary_audit=boundary,
            guardrail_reports=(guardrail_report,),
        )

        self.assertEqual("control_plane_integrity_drift_observed", review.review_status)
        self.assertEqual(1, review.finding_count)
        self.assertEqual(("permission_laundering_text",), review.finding_codes)
        self.assertEqual({"high": 1}, review.severity_counts)

    def test_guardrail_and_lineage_findings_are_preserved_with_source_identity(self) -> None:
        guardrail = ControlPlaneGuardrailReport(
            schema_version="1",
            eval_role="detects_control_plane_telemetry_authority_laundering",
            source_projection_role="maps_control_plane_review_packets_to_in_memory_observability_events",
            eval_status="guardrail_drift_observed",
            finding_count=1,
            category_counts={"authority": 1},
            severity_counts={"critical": 1},
            finding_codes=("span_kind_drift",),
            findings=(
                ControlPlaneGuardrailFinding(
                    code="span_kind_drift",
                    category="authority",
                    severity="critical",
                    location="spans[0].kind",
                    span_id="span-1",
                    event_name="",
                    detail="projection spans must remain INTERNAL",
                ),
            ),
            source_span_count=1,
            source_event_count=0,
        )
        lineage = ControlPlaneLineageInvariantReport(
            schema_version="1",
            eval_role="evaluates_control_plane_cross_layer_lineage_invariants",
            eval_status="lineage_drift_observed",
            finding_count=1,
            severity_counts={"high": 1},
            finding_codes=("packet_trace_event_detail_mismatch",),
            findings=(
                ControlPlaneLineageInvariantFinding(
                    code="packet_trace_event_detail_mismatch",
                    severity="high",
                    layer_pair="review_packet->telemetry_projection",
                    source_id="trace-1",
                    detail="trace event detail changed",
                ),
            ),
            checked_layer_pairs=("review_packet->telemetry_projection",),
        )

        review = build_control_plane_integrity_review(
            boundary_audit=_clean_boundary_report(),
            guardrail_reports=(guardrail,),
            lineage_reports=(lineage,),
        )

        self.assertEqual("control_plane_integrity_drift_observed", review.review_status)
        self.assertEqual(2, review.finding_count)
        self.assertIn("span_kind_drift", review.finding_codes)
        self.assertIn("packet_trace_event_detail_mismatch", review.finding_codes)
        self.assertEqual({"critical": 1, "high": 1}, review.severity_counts)

    def test_rejects_authoritative_or_malformed_inputs(self) -> None:
        guardrail_report, lineage_report = _clean_guardrail_and_lineage_reports()

        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "non-authoritative"):
            build_control_plane_integrity_review(
                boundary_audit=replace(_clean_boundary_report(), authority="runtime authority"),
                guardrail_reports=(guardrail_report,),
            )
        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "finding_codes"):
            build_control_plane_integrity_review(
                boundary_audit=_clean_boundary_report(),
                lineage_reports=(replace(lineage_report, finding_codes=("ghost",)),),
            )
        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "severity_counts"):
            build_control_plane_integrity_review(
                boundary_audit=replace(_clean_boundary_report(), severity_counts={"high": 1}),
                guardrail_reports=(guardrail_report,),
            )
        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "category_counts"):
            build_control_plane_integrity_review(
                boundary_audit=_clean_boundary_report(),
                guardrail_reports=(replace(guardrail_report, category_counts={"authority": 1}),),
            )
        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "checked_layer_pairs"):
            build_control_plane_integrity_review(
                boundary_audit=_clean_boundary_report(),
                lineage_reports=(replace(lineage_report, checked_layer_pairs=()),),
            )
        with self.assertRaisesRegex(ControlPlaneIntegrityReviewError, "requires boundary"):
            build_control_plane_integrity_review(boundary_audit=_clean_boundary_report())

    def test_renderers_preserve_non_authority_markers(self) -> None:
        guardrail_report, lineage_report = _clean_guardrail_and_lineage_reports()
        review = build_control_plane_integrity_review(
            boundary_audit=_clean_boundary_report(),
            guardrail_reports=(guardrail_report,),
            lineage_reports=(lineage_report,),
        )

        payload = json.loads(render_control_plane_integrity_review_json(review))
        markdown = render_control_plane_integrity_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["review_is_not_permission"])
        self.assertTrue(payload["integrity_pass_is_not_truth"])
        self.assertTrue(payload["finding_is_not_execution_approval"])
        self.assertIn("review_is_not_permission: true", markdown)
        self.assertIn("integrity_pass_is_not_truth: true", markdown)
        self.assertIn("finding_is_not_execution_approval: true", markdown)

    def test_package_has_no_io_cli_runtime_or_opentelemetry_imports(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        python_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", python_text)
        self.assertNotIn("from opentelemetry", python_text)
        self.assertNotIn("subprocess", python_text)
        self.assertNotIn("write_text", python_text)
        self.assertNotIn("open(", python_text)


if __name__ == "__main__":
    unittest.main()
