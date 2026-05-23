from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_review_packet import build_control_plane_review_packet
from experiments.control_plane_telemetry_projection import (
    ControlPlaneTelemetryEvent,
    ControlPlaneTelemetrySpan,
    project_control_plane_packet_to_telemetry,
)
from experiments.control_plane_guardrail_eval import (
    ControlPlaneGuardrailEvalError,
    evaluate_control_plane_guardrails,
    evaluate_control_plane_telemetry_guardrails,
    render_control_plane_guardrail_eval_json,
    render_control_plane_guardrail_eval_markdown,
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
        request_id="req-tests",
        matched_rule_id="python-unittest",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


def _projection():
    packet = build_control_plane_review_packet(
        "trace-advisory",
        _assessment(),
        capability_assessments=(_capability(),),
    )
    return project_control_plane_packet_to_telemetry(packet)


class ControlPlaneGuardrailEvalTests(unittest.TestCase):
    def test_clean_projection_preserves_guardrails_without_permission_semantics(self) -> None:
        report = evaluate_control_plane_telemetry_guardrails(_projection())

        self.assertEqual("guardrails_preserved", report.eval_status)
        self.assertEqual(0, report.finding_count)
        self.assertEqual({}, report.category_counts)
        self.assertEqual({}, report.severity_counts)
        self.assertTrue(report.eval_is_not_permission)
        self.assertTrue(report.finding_is_not_truth)
        self.assertTrue(report.finding_is_not_execution_approval)
        self.assertTrue(report.must_not_execute_automatically)
        self.assertEqual("none", report.state_change)
        self.assertIn("non-authoritative", report.authority)

    def test_detects_status_permission_and_packet_status_laundering(self) -> None:
        projection = _projection()
        span = replace(
            projection.spans[0],
            status="ok_permission_success",
            attributes={
                **projection.spans[0].attributes,
                "cerebro.control_plane.packet_verdict": "packet_blocked",
            },
        )
        report = evaluate_control_plane_telemetry_guardrails(replace(projection, spans=(span,)))

        self.assertEqual("guardrail_drift_observed", report.eval_status)
        self.assertIn("span_status_launders_authority", report.finding_codes)
        self.assertIn("packet_status_contradiction", report.finding_codes)
        self.assertGreaterEqual(report.severity_counts["critical"], 1)
        self.assertGreaterEqual(report.category_counts["authority"], 1)

    def test_detects_export_stable_semconv_and_sensitive_genai_attributes(self) -> None:
        projection = _projection()
        span = replace(
            projection.spans[0],
            attributes={
                **projection.spans[0].attributes,
                "otel.compat.exported": True,
                "otel.compat.profile": "genai-semconv-stable",
                "gen_ai.input.messages": "redacted",
                "gen_ai.request.model": "model-name",
                "gen_ai.usage.input_tokens": 5,
            },
        )
        drifted = replace(
            projection,
            compatibility_profile="otel-semconv-genai-stable",
            semconv_status="stable",
            spans=(span,),
        )

        report = evaluate_control_plane_telemetry_guardrails(drifted)

        self.assertIn("telemetry_export_laundering", report.finding_codes)
        self.assertIn("semconv_status_laundering", report.finding_codes)
        self.assertIn("compatibility_profile_lacks_development_marker", report.finding_codes)
        self.assertIn("semconv_stability_laundering", report.finding_codes)
        self.assertIn("sensitive_genai_attribute_projected", report.finding_codes)

    def test_detects_text_laundering_in_names_events_and_attributes(self) -> None:
        projection = _projection()
        span = projection.spans[0]
        event = ControlPlaneTelemetryEvent(
            name="cerebro.control_plane.execution_approved",
            attributes={
                "cerebro.control_plane.event_is_not_permission": True,
                "custom.claim": "runtime_authority",
            },
        )
        drifted_span = replace(
            span,
            name="cerebro.control_plane.stable_semconv",
            attributes={
                **span.attributes,
                "custom.truth": "canonical_truth",
            },
            events=(event,),
        )

        report = evaluate_control_plane_guardrails(replace(projection, spans=(drifted_span,), event_count=1))

        self.assertIn("text_launders_authority", report.finding_codes)
        self.assertGreaterEqual(report.category_counts["truth"], 1)
        self.assertGreaterEqual(report.category_counts["permission"], 1)
        self.assertGreaterEqual(report.category_counts["authority"], 1)
        self.assertGreaterEqual(report.category_counts["stability"], 1)

    def test_detects_missing_span_and_event_guardrails(self) -> None:
        projection = _projection()
        span = projection.spans[0]
        event = ControlPlaneTelemetryEvent(
            name=span.events[0].name,
            attributes={
                key: value
                for key, value in span.events[0].attributes.items()
                if key != "cerebro.control_plane.event_is_not_permission"
            },
        )
        drifted_span = replace(
            span,
            attributes={
                key: value
                for key, value in span.attributes.items()
                if key != "cerebro.control_plane.span_status_is_not_truth"
            },
            events=(event, *span.events[1:]),
        )

        report = evaluate_control_plane_telemetry_guardrails(replace(projection, spans=(drifted_span,)))

        self.assertIn("span_truth_guardrail_missing", report.finding_codes)
        self.assertIn("event_permission_guardrail_missing", report.finding_codes)

    def test_rejects_projection_boundary_guardrail_drift(self) -> None:
        projection = _projection()

        with self.assertRaisesRegex(ControlPlaneGuardrailEvalError, "guardrails"):
            evaluate_control_plane_telemetry_guardrails(
                replace(projection, projection_is_not_permission=False)
            )
        with self.assertRaisesRegex(ControlPlaneGuardrailEvalError, "non-authoritative"):
            evaluate_control_plane_telemetry_guardrails(replace(projection, authority="runtime authority"))

    def test_renderers_preserve_eval_non_authority_markers(self) -> None:
        report = evaluate_control_plane_telemetry_guardrails(_projection())

        payload = json.loads(render_control_plane_guardrail_eval_json(report))
        markdown = render_control_plane_guardrail_eval_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["eval_is_not_permission"])
        self.assertTrue(payload["finding_is_not_truth"])
        self.assertTrue(payload["finding_is_not_execution_approval"])
        self.assertIn("eval_is_not_permission: true", markdown)
        self.assertIn("finding_is_not_truth: true", markdown)
        self.assertIn("finding_is_not_execution_approval: true", markdown)

    def test_package_source_has_no_runtime_or_io_surface(self) -> None:
        from pathlib import Path

        package_root = Path(__file__).resolve().parents[1]
        python_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", python_text)
        self.assertNotIn("from opentelemetry", python_text)
        self.assertNotIn("subprocess", python_text)
        self.assertNotIn("requests", python_text)
        self.assertNotIn("write_text", python_text)
        self.assertNotIn("open(", python_text)


if __name__ == "__main__":
    unittest.main()
