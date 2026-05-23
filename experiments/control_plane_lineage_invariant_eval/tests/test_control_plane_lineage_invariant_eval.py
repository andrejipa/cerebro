from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_guardrail_eval import evaluate_control_plane_guardrails
from experiments.control_plane_lineage_invariant_eval import (
    ControlPlaneLineageInvariantError,
    evaluate_control_plane_adversarial_projection_lineage,
    evaluate_control_plane_guardrail_eval_lineage,
    evaluate_control_plane_lab_projection_lineage,
    evaluate_control_plane_matrix_projection_lineage,
    evaluate_control_plane_packet_projection_lineage,
    render_control_plane_lineage_invariant_json,
    render_control_plane_lineage_invariant_markdown,
)
from experiments.control_plane_review_matrix import build_control_plane_review_matrix
from experiments.control_plane_review_packet import build_control_plane_review_packet
from experiments.control_plane_scenario_lab import (
    ControlPlaneScenario,
    build_control_plane_adversarial_report,
    build_control_plane_scenario_lab_report,
    builtin_control_plane_adversarial_probes,
    builtin_control_plane_scenarios,
)
from experiments.control_plane_telemetry_projection import (
    project_control_plane_adversarial_report_to_telemetry,
    project_control_plane_matrix_to_telemetry,
    project_control_plane_packet_to_telemetry,
    project_control_plane_scenario_lab_to_telemetry,
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


def _capability(decision: str = "advisory_allow") -> CapabilityAssessment:
    return CapabilityAssessment(
        request_id=f"req-{decision}",
        matched_rule_id="lineage-test-rule",
        decision=decision,
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",) if decision == "advisory_allow" else (),
        required_human_decision="none" if decision == "advisory_allow" else "review_capability_request",
    )


class ControlPlaneLineageInvariantEvalTests(unittest.TestCase):
    def test_packet_projection_preserves_trace_verdict_blockers_and_replay_issues(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-blocked",
            _assessment(blockers=("runtime_boundary_closed",), recommended_human_decision="review_blockers"),
            capability_assessments=(_capability(),),
        )
        projection = project_control_plane_packet_to_telemetry(packet)

        report = evaluate_control_plane_packet_projection_lineage(packet, projection)

        self.assertEqual("lineage_invariants_preserved", report.eval_status)
        self.assertEqual(0, report.finding_count)
        self.assertTrue(report.eval_is_not_permission)
        self.assertTrue(report.invariant_pass_is_not_truth)

    def test_packet_projection_detects_missing_blocker_event(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-blocker-missing",
            _assessment(blockers=("runtime_boundary_closed",), recommended_human_decision="review_blockers"),
            capability_assessments=(_capability(),),
        )
        projection = project_control_plane_packet_to_telemetry(packet)
        span = replace(
            projection.spans[0],
            events=tuple(
                event
                for event in projection.spans[0].events
                if event.name != "cerebro.control_plane.blocker_observed"
            ),
        )
        drifted = replace(projection, spans=(span,), event_count=len(span.events))

        report = evaluate_control_plane_packet_projection_lineage(packet, drifted)

        self.assertEqual("lineage_drift_observed", report.eval_status)
        self.assertIn("packet_blocker_event_missing", report.finding_codes)

    def test_packet_projection_detects_trace_event_detail_and_replay_status_drift(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-packet-detail-drift",
            _assessment(),
            capability_assessments=(_capability(),),
        )
        projection = project_control_plane_packet_to_telemetry(packet)
        event = replace(
            projection.spans[0].events[0],
            attributes={
                **projection.spans[0].events[0].attributes,
                "cerebro.control_plane.detail": "changed-detail",
            },
        )
        span = replace(
            projection.spans[0],
            attributes={
                **projection.spans[0].attributes,
                "cerebro.control_plane.replay_digest": "sha256:changed",
                "cerebro.control_plane.replay_status": "changed_status",
            },
            events=(event, *projection.spans[0].events[1:]),
        )
        drifted = replace(projection, spans=(span,))

        report = evaluate_control_plane_packet_projection_lineage(packet, drifted)

        self.assertIn("packet_trace_event_detail_mismatch", report.finding_codes)
        self.assertIn("packet_replay_digest_mismatch", report.finding_codes)
        self.assertIn("packet_replay_status_mismatch", report.finding_codes)

    def test_matrix_projection_preserves_packet_count_and_human_decision_summary(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-review",
            _assessment(),
            capability_assessments=(_capability("review_required"),),
        )
        matrix = build_control_plane_review_matrix((packet,))
        projection = project_control_plane_matrix_to_telemetry(matrix)

        report = evaluate_control_plane_matrix_projection_lineage(matrix, projection)

        self.assertEqual(0, report.finding_count)
        self.assertEqual("lineage_invariants_preserved", report.eval_status)

    def test_matrix_projection_detects_missing_human_decision_identity(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-review-drift",
            _assessment(),
            capability_assessments=(_capability("review_required"),),
        )
        matrix = build_control_plane_review_matrix((packet,))
        projection = project_control_plane_matrix_to_telemetry(matrix)
        event = replace(
            projection.spans[0].events[0],
            attributes={
                **projection.spans[0].events[0].attributes,
                "cerebro.control_plane.required_human_decision": "none",
            },
        )
        span = replace(projection.spans[0], events=(event,))
        drifted = replace(projection, spans=(span,))

        report = evaluate_control_plane_matrix_projection_lineage(matrix, drifted)

        self.assertIn("matrix_human_decision_missing", report.finding_codes)

    def test_matrix_projection_detects_row_verdict_or_review_status_drift(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-row-drift",
            _assessment(),
            capability_assessments=(_capability("review_required"),),
        )
        matrix = build_control_plane_review_matrix((packet,))
        projection = project_control_plane_matrix_to_telemetry(matrix)
        event = replace(
            projection.spans[0].events[0],
            attributes={
                **projection.spans[0].events[0].attributes,
                "cerebro.control_plane.packet_verdict": "packet_blocked",
                "cerebro.control_plane.combined_review_status": "blocked_review",
            },
        )
        span = replace(
            projection.spans[0],
            attributes={
                **projection.spans[0].attributes,
                "cerebro.control_plane.packet_verdict_counts": json.dumps({"packet_blocked": 1}),
            },
            events=(event,),
        )
        drifted = replace(projection, spans=(span,))

        report = evaluate_control_plane_matrix_projection_lineage(matrix, drifted)

        self.assertIn("matrix_packet_verdict_counts_mismatch", report.finding_codes)
        self.assertIn("matrix_row_packet_verdict_mismatch", report.finding_codes)
        self.assertIn("matrix_row_combined_review_status_mismatch", report.finding_codes)

    def test_scenario_lab_projection_preserves_expectation_drift_and_failure_counts(self) -> None:
        lab = build_control_plane_scenario_lab_report(
            (
                ControlPlaneScenario(
                    scenario_id="scenario-drift",
                    assessment=_assessment(blockers=("runtime_boundary_closed",), recommended_human_decision="review_blockers"),
                    capability_assessments=(_capability(),),
                    expected_packet_verdict="packet_advisory_review_only",
                    expected_combined_review_status="advisory_review_only",
                ),
            )
        )
        projection = project_control_plane_scenario_lab_to_telemetry(lab)

        report = evaluate_control_plane_lab_projection_lineage(lab, projection)

        self.assertEqual(0, report.finding_count)

    def test_scenario_lab_projection_detects_missing_expectation_failure_event(self) -> None:
        lab = build_control_plane_scenario_lab_report(
            (
                ControlPlaneScenario(
                    scenario_id="scenario-drift-missing-event",
                    assessment=_assessment(blockers=("runtime_boundary_closed",), recommended_human_decision="review_blockers"),
                    capability_assessments=(_capability(),),
                    expected_packet_verdict="packet_advisory_review_only",
                    expected_combined_review_status="advisory_review_only",
                ),
            )
        )
        projection = project_control_plane_scenario_lab_to_telemetry(lab)
        spans = tuple(
            replace(
                span,
                events=tuple(
                    event
                    for event in span.events
                    if event.name != "cerebro.control_plane.expectation_failure_observed"
                ),
            )
            for span in projection.spans
        )
        drifted = replace(projection, spans=spans, event_count=sum(len(span.events) for span in spans))

        report = evaluate_control_plane_lab_projection_lineage(lab, drifted)

        self.assertIn("expectation_failure_event_count_mismatch", report.finding_codes)
        self.assertIn("scenario_expectation_failure_event_missing", report.finding_codes)

    def test_scenario_lab_projection_detects_child_span_status_drift(self) -> None:
        lab = build_control_plane_scenario_lab_report(builtin_control_plane_scenarios())
        projection = project_control_plane_scenario_lab_to_telemetry(lab)
        child_index = next(
            index
            for index, span in enumerate(projection.spans)
            if span.name == "cerebro.control_plane.scenario"
        )
        spans = list(projection.spans)
        spans[child_index] = replace(
            spans[child_index],
            status="changed_status",
            attributes={
                **spans[child_index].attributes,
                "cerebro.control_plane.packet_verdict": "packet_blocked",
            },
        )
        drifted = replace(projection, spans=tuple(spans))

        report = evaluate_control_plane_lab_projection_lineage(lab, drifted)

        self.assertIn("scenario_child_status_mismatch", report.finding_codes)
        self.assertIn("scenario_child_packet_verdict_mismatch", report.finding_codes)

    def test_adversarial_projection_preserves_finding_count_and_probe_ids(self) -> None:
        adversarial = build_control_plane_adversarial_report(builtin_control_plane_adversarial_probes())
        projection = project_control_plane_adversarial_report_to_telemetry(adversarial)

        report = evaluate_control_plane_adversarial_projection_lineage(adversarial, projection)

        self.assertEqual(0, report.finding_count)

    def test_adversarial_projection_detects_missing_finding_code_event(self) -> None:
        adversarial = build_control_plane_adversarial_report(builtin_control_plane_adversarial_probes())
        projection = project_control_plane_adversarial_report_to_telemetry(adversarial)
        root = projection.spans[0]
        span = replace(root, events=root.events[1:])
        drifted = replace(
            projection,
            spans=(span, *projection.spans[1:]),
            event_count=sum(len(item.events) for item in (span, *projection.spans[1:])),
        )

        report = evaluate_control_plane_adversarial_projection_lineage(adversarial, drifted)

        self.assertIn("adversarial_finding_event_count_mismatch", report.finding_codes)
        self.assertIn("adversarial_finding_detail_missing", report.finding_codes)

    def test_adversarial_projection_detects_finding_severity_detail_drift(self) -> None:
        adversarial = build_control_plane_adversarial_report(builtin_control_plane_adversarial_probes())
        projection = project_control_plane_adversarial_report_to_telemetry(adversarial)
        root = projection.spans[0]
        event = replace(
            root.events[0],
            attributes={
                **root.events[0].attributes,
                "cerebro.control_plane.finding_severity": "info",
                "cerebro.control_plane.finding_detail": "changed detail",
            },
        )
        span = replace(root, events=(event, *root.events[1:]))
        drifted = replace(projection, spans=(span, *projection.spans[1:]))

        report = evaluate_control_plane_adversarial_projection_lineage(adversarial, drifted)

        self.assertIn("adversarial_finding_detail_missing", report.finding_codes)

    def test_guardrail_eval_lineage_binds_to_same_projection_counts(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-guardrail",
            _assessment(),
            capability_assessments=(_capability(),),
        )
        projection = project_control_plane_packet_to_telemetry(packet)
        guardrail_report = evaluate_control_plane_guardrails(projection)

        report = evaluate_control_plane_guardrail_eval_lineage(projection, guardrail_report)

        self.assertEqual(0, report.finding_count)

        drifted = replace(guardrail_report, source_event_count=guardrail_report.source_event_count + 1)
        drift_report = evaluate_control_plane_guardrail_eval_lineage(projection, drifted)
        self.assertIn("guardrail_source_event_count_mismatch", drift_report.finding_codes)

        role_drift = replace(guardrail_report, source_projection_role="different_projection_role")
        role_report = evaluate_control_plane_guardrail_eval_lineage(projection, role_drift)
        self.assertIn("guardrail_source_projection_role_mismatch", role_report.finding_codes)

        status_drift = replace(
            guardrail_report,
            eval_status="permission_granted",
            finding_codes=("unexpected",),
            category_counts={"permission": 1},
        )
        status_report = evaluate_control_plane_guardrail_eval_lineage(projection, status_drift)
        self.assertIn("guardrail_eval_status_unknown", status_report.finding_codes)
        self.assertIn("guardrail_finding_codes_mismatch", status_report.finding_codes)
        self.assertIn("guardrail_category_counts_mismatch", status_report.finding_codes)

    def test_renderers_preserve_non_authority_markers(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-render",
            _assessment(),
            capability_assessments=(_capability(),),
        )
        report = evaluate_control_plane_packet_projection_lineage(
            packet,
            project_control_plane_packet_to_telemetry(packet),
        )

        payload = json.loads(render_control_plane_lineage_invariant_json(report))
        markdown = render_control_plane_lineage_invariant_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["eval_is_not_permission"])
        self.assertTrue(payload["invariant_pass_is_not_truth"])
        self.assertTrue(payload["finding_is_not_execution_approval"])
        self.assertIn("eval_is_not_permission: true", markdown)
        self.assertIn("invariant_pass_is_not_truth: true", markdown)

    def test_rejects_authoritative_inputs_and_guardrail_drift(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-authority",
            _assessment(),
            capability_assessments=(_capability(),),
        )
        projection = project_control_plane_packet_to_telemetry(packet)

        with self.assertRaisesRegex(ControlPlaneLineageInvariantError, "non-authoritative"):
            evaluate_control_plane_packet_projection_lineage(
                replace(packet, authority="runtime authority"),
                projection,
            )
        with self.assertRaisesRegex(ControlPlaneLineageInvariantError, "guardrails"):
            evaluate_control_plane_packet_projection_lineage(
                packet,
                replace(projection, projection_is_not_permission=False),
            )

    def test_package_has_no_io_cli_runtime_or_opentelemetry_imports(self) -> None:
        from pathlib import Path

        package_root = Path(__file__).resolve().parents[1]
        python_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", python_text)
        self.assertNotIn("from opentelemetry", python_text)
        self.assertNotIn("subprocess", python_text)
        self.assertNotIn("write_text", python_text)
        self.assertNotIn("open(", python_text)


if __name__ == "__main__":
    unittest.main()
