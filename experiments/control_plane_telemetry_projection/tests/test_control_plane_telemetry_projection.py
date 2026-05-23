from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_review_matrix import build_control_plane_review_matrix
from experiments.control_plane_review_packet import build_control_plane_review_packet
from experiments.control_plane_scenario_lab import (
    ControlPlaneScenario,
    build_control_plane_adversarial_report,
    build_control_plane_scenario_lab_report,
    builtin_control_plane_adversarial_probes,
)
from experiments.control_plane_telemetry_projection import (
    ControlPlaneTelemetryProjectionError,
    project_control_plane_adversarial_report_to_telemetry,
    project_control_plane_matrix_to_telemetry,
    project_control_plane_packets_to_telemetry,
    project_control_plane_packet_to_telemetry,
    project_control_plane_scenario_lab_to_telemetry,
    render_control_plane_telemetry_json,
    render_control_plane_telemetry_markdown,
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


def _capability(decision: str = "advisory_allow", **overrides) -> CapabilityAssessment:
    values = {
        "request_id": f"req-{decision}",
        "matched_rule_id": "python-unittest",
        "decision": decision,
        "reasons": ("capability_request_within_declared_policy",),
        "warnings": ("advisory_allow_is_not_permission",) if decision == "advisory_allow" else (),
        "required_human_decision": "none" if decision == "advisory_allow" else "review_capability_request",
    }
    values.update(overrides)
    return CapabilityAssessment(**values)


def _packet(name: str, *, assessment: ControlPlaneAssessment | None = None, capability: CapabilityAssessment | None = None):
    capabilities = () if capability is None else (capability,)
    return build_control_plane_review_packet(
        f"trace-{name}",
        _assessment() if assessment is None else assessment,
        capability_assessments=capabilities,
    )


class ControlPlaneTelemetryProjectionTests(unittest.TestCase):
    def test_projects_packet_to_internal_span_without_export_authority(self) -> None:
        projection = project_control_plane_packet_to_telemetry(_packet("advisory", capability=_capability()))
        span = projection.spans[0]

        self.assertEqual("otel-semconv-genai-development-compatible-projection", projection.compatibility_profile)
        self.assertEqual("development", projection.semconv_status)
        self.assertEqual(1, projection.source_count)
        self.assertEqual(1, projection.span_count)
        self.assertEqual("INTERNAL", span.kind)
        self.assertEqual("observed_advisory_non_authoritative", span.status)
        self.assertEqual("trace-advisory", span.attributes["cerebro.control_plane.trace_id"])
        self.assertEqual("packet_advisory_review_only", span.attributes["cerebro.control_plane.packet_verdict"])
        self.assertFalse(span.attributes["otel.compat.exported"])
        self.assertTrue(span.attributes["cerebro.control_plane.packet_is_not_permission"])
        self.assertTrue(span.attributes["cerebro.control_plane.span_status_is_not_truth"])
        self.assertTrue(projection.projection_is_not_opentelemetry_export)
        self.assertTrue(projection.projection_is_not_export)
        self.assertTrue(projection.projection_is_not_permission)
        self.assertTrue(projection.telemetry_is_not_permission)
        self.assertTrue(projection.span_status_is_not_truth)
        self.assertTrue(projection.semconv_compat_is_not_stability)
        self.assertTrue(projection.must_not_execute_automatically)
        self.assertEqual("none", projection.state_change)
        self.assertIn("non-authoritative", projection.authority)

    def test_projects_blockers_and_replay_issues_as_non_permission_events(self) -> None:
        blocked = _packet(
            "blocked",
            assessment=_assessment(
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability=_capability(),
        )
        invalid = replace(
            _packet("invalid", capability=_capability()),
            packet_verdict="packet_replay_invalid",
            replay_evaluation_verdict="replay_contract_failed",
            replay_issue_codes=("ledger_parse_failed",),
        )

        projection = project_control_plane_packets_to_telemetry((blocked, invalid))
        event_names = [event.name for span in projection.spans for event in span.events]

        self.assertEqual(2, projection.source_count)
        self.assertEqual(2, projection.span_count)
        self.assertIn("cerebro.control_plane.blocker_observed", event_names)
        self.assertIn("cerebro.control_plane.replay_issue_observed", event_names)
        self.assertIn("observed_blocked", {span.status for span in projection.spans})
        self.assertIn("observed_replay_invalid", {span.status for span in projection.spans})
        self.assertEqual(projection.event_count, sum(len(span.events) for span in projection.spans))

    def test_projects_matrix_without_collapsing_counts_to_permission(self) -> None:
        matrix = build_control_plane_review_matrix(
            (
                _packet("advisory", capability=_capability()),
                _packet("human"),
            )
        )

        projection = project_control_plane_matrix_to_telemetry(matrix)
        span = projection.spans[0]

        self.assertEqual("cerebro.control_plane.review_matrix", span.name)
        self.assertEqual("observed_matrix_non_authoritative", span.status)
        self.assertEqual(2, span.attributes["cerebro.control_plane.packet_count"])
        self.assertTrue(span.attributes["cerebro.control_plane.matrix_is_not_permission"])
        self.assertTrue(span.attributes["cerebro.control_plane.matrix_pass_is_not_execution_approval"])
        self.assertEqual(2, len(span.events))
        self.assertNotIn("permission", span.status)

    def test_projects_scenario_lab_expectation_drift_as_events(self) -> None:
        report = build_control_plane_scenario_lab_report(
            (
                ControlPlaneScenario(
                    scenario_id="scenario-drift",
                    assessment=_assessment(),
                    capability_assessments=(_capability(),),
                    expected_packet_verdict="packet_blocked",
                ),
            )
        )

        projection = project_control_plane_scenario_lab_to_telemetry(report)
        event_names = [event.name for span in projection.spans for event in span.events]

        self.assertEqual(2, projection.span_count)
        self.assertEqual("cerebro.control_plane.scenario_lab", projection.spans[0].name)
        self.assertIn("cerebro.control_plane.scenario_expectation_drift_observed", event_names)
        self.assertIn("cerebro.control_plane.expectation_failure_observed", event_names)
        self.assertTrue(projection.span_status_is_not_truth)

    def test_projects_adversarial_findings_as_non_permission_events(self) -> None:
        report = build_control_plane_adversarial_report((builtin_control_plane_adversarial_probes()[0],))

        projection = project_control_plane_adversarial_report_to_telemetry(report)
        root = projection.spans[0]
        event_names = [event.name for span in projection.spans for event in span.events]

        self.assertEqual(2, projection.span_count)
        self.assertEqual("cerebro.control_plane.adversarial_lab", root.name)
        self.assertTrue(root.attributes["cerebro.control_plane.adversarial_findings_are_not_execution_approval"])
        self.assertIn("cerebro.control_plane.adversarial_finding_observed", event_names)
        self.assertNotIn("approval", root.status)

    def test_projection_is_deterministic_for_same_packet(self) -> None:
        packet = _packet("stable", capability=_capability())

        first = project_control_plane_packet_to_telemetry(packet)
        second = project_control_plane_packet_to_telemetry(packet)

        self.assertEqual(first.spans[0].span_id, second.spans[0].span_id)
        self.assertEqual(render_control_plane_telemetry_json(first), render_control_plane_telemetry_json(second))

    def test_rejects_empty_duplicate_unsafe_and_guardrail_drift(self) -> None:
        packet = _packet("advisory", capability=_capability())

        with self.assertRaisesRegex(ControlPlaneTelemetryProjectionError, "at least one"):
            project_control_plane_packets_to_telemetry(())
        with self.assertRaisesRegex(ControlPlaneTelemetryProjectionError, "duplicate"):
            project_control_plane_packets_to_telemetry((packet, packet))
        with self.assertRaisesRegex(ControlPlaneTelemetryProjectionError, "path-segment safe"):
            project_control_plane_packet_to_telemetry(replace(packet, trace_id="../escape"))
        with self.assertRaisesRegex(ControlPlaneTelemetryProjectionError, "guardrails"):
            project_control_plane_packet_to_telemetry(replace(packet, packet_is_not_permission=False))

    def test_renderers_preserve_development_and_non_authority_markers(self) -> None:
        projection = project_control_plane_packet_to_telemetry(_packet("advisory", capability=_capability()))

        payload = json.loads(render_control_plane_telemetry_json(projection))
        markdown = render_control_plane_telemetry_markdown(projection)

        self.assertEqual("none", payload["state_change"])
        self.assertEqual("development", payload["semconv_status"])
        self.assertTrue(payload["projection_is_not_opentelemetry_export"])
        self.assertTrue(payload["projection_is_not_export"])
        self.assertTrue(payload["projection_is_not_permission"])
        self.assertTrue(payload["telemetry_is_not_permission"])
        self.assertTrue(payload["span_status_is_not_truth"])
        self.assertTrue(payload["semconv_compat_is_not_stability"])
        self.assertIn("projection_is_not_opentelemetry_export: true", markdown)
        self.assertIn("projection_is_not_export: true", markdown)
        self.assertIn("projection_is_not_permission: true", markdown)
        self.assertIn("telemetry_is_not_permission: true", markdown)
        self.assertIn("span_status_is_not_truth: true", markdown)
        self.assertIn("semconv_compat_is_not_stability: true", markdown)
        self.assertIn("development", markdown)

    def test_projection_source_has_no_otel_sdk_or_sensitive_genai_fields(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        python_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", python_text)
        self.assertNotIn("from opentelemetry", python_text)
        self.assertNotIn("gen_ai.input.messages", python_text)
        self.assertNotIn("gen_ai.output.messages", python_text)
        self.assertNotIn("gen_ai.usage", python_text)


if __name__ == "__main__":
    unittest.main()
