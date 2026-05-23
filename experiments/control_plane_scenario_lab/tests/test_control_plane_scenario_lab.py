from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_scenario_lab import (
    ControlPlaneAdversarialProbe,
    ControlPlaneScenario,
    ControlPlaneScenarioLabError,
    build_control_plane_adversarial_report,
    build_control_plane_scenario_lab_report,
    builtin_control_plane_adversarial_probes,
    builtin_control_plane_scenarios,
    render_control_plane_adversarial_json,
    render_control_plane_adversarial_markdown,
    render_control_plane_scenario_lab_json,
    render_control_plane_scenario_lab_markdown,
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
        "request_id": "req-tests",
        "matched_rule_id": "python-unittest",
        "decision": decision,
        "reasons": ("capability_request_within_declared_policy",),
        "warnings": ("advisory_allow_is_not_permission",) if decision == "advisory_allow" else (),
        "required_human_decision": "none" if decision == "advisory_allow" else "review_capability_request",
    }
    values.update(overrides)
    return CapabilityAssessment(**values)


class ControlPlaneScenarioLabTests(unittest.TestCase):
    def test_builtin_scenarios_exercise_advisory_human_and_blocked_paths(self) -> None:
        report = build_control_plane_scenario_lab_report(builtin_control_plane_scenarios())

        self.assertEqual(4, report.scenario_count)
        self.assertEqual(4, report.expectation_status_counts["expectations_observed_as_declared"])
        self.assertEqual(0, report.expectation_failure_count)
        self.assertEqual(4, report.matrix.packet_count)
        self.assertEqual(1, report.matrix.packet_verdict_counts["packet_advisory_review_only"])
        self.assertEqual(2, report.matrix.packet_verdict_counts["packet_human_review_required"])
        self.assertEqual(1, report.matrix.packet_verdict_counts["packet_blocked"])
        self.assertTrue(report.lab_is_not_permission)
        self.assertTrue(report.expectation_match_is_not_execution_approval)
        self.assertTrue(report.replay_pass_is_not_truth)
        self.assertTrue(report.must_not_execute_automatically)
        self.assertEqual("none", report.state_change)
        self.assertIn("non-authoritative", report.authority)

    def test_expectation_drift_is_reported_without_permission_semantics(self) -> None:
        scenario = ControlPlaneScenario(
            scenario_id="scenario-drift",
            assessment=_assessment(),
            capability_assessments=(_capability(),),
            expected_packet_verdict="packet_blocked",
            expected_combined_review_status="blocked_review",
            expected_required_human_decision="review_blockers",
        )

        report = build_control_plane_scenario_lab_report((scenario,))
        result = report.results[0]

        self.assertEqual("expectation_drift_observed", result.expectation_status)
        self.assertEqual(3, len(result.expectation_failures))
        self.assertEqual(("scenario-drift",), report.scenarios_with_expectation_drift)
        self.assertTrue(report.expectation_match_is_not_execution_approval)

    def test_empty_duplicate_and_unsafe_scenarios_are_rejected(self) -> None:
        scenario = ControlPlaneScenario(
            scenario_id="scenario-ok",
            assessment=_assessment(),
            capability_assessments=(_capability(),),
        )

        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "at least one"):
            build_control_plane_scenario_lab_report(())
        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "duplicate"):
            build_control_plane_scenario_lab_report((scenario, scenario))
        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "path-segment safe"):
            build_control_plane_scenario_lab_report((replace(scenario, scenario_id="../escape"),))

    def test_rejects_authority_drift_from_inputs(self) -> None:
        scenario = ControlPlaneScenario(
            scenario_id="scenario-bad",
            assessment=replace(_assessment(), authority="runtime authority"),
            capability_assessments=(_capability(),),
        )

        with self.assertRaisesRegex(Exception, "non-authoritative"):
            build_control_plane_scenario_lab_report((scenario,))

    def test_renderers_preserve_boundaries_and_matrix_projection(self) -> None:
        report = build_control_plane_scenario_lab_report((builtin_control_plane_scenarios()[0],))

        payload = json.loads(render_control_plane_scenario_lab_json(report))
        markdown = render_control_plane_scenario_lab_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["lab_is_not_permission"])
        self.assertTrue(payload["expectation_match_is_not_execution_approval"])
        self.assertEqual(1, payload["matrix"]["packet_count"])
        self.assertIn("lab_is_not_permission: true", markdown)
        self.assertIn("expectation_match_is_not_execution_approval: true", markdown)
        self.assertIn("scenario-advisory", markdown)

    def test_builtin_adversarial_probes_observe_expected_findings(self) -> None:
        report = build_control_plane_adversarial_report(builtin_control_plane_adversarial_probes())

        self.assertEqual(11, report.probe_count)
        self.assertEqual(11, report.expectation_status_counts["expected_findings_observed"])
        self.assertEqual(0, report.expectation_status_counts.get("expected_findings_missing", 0))
        self.assertEqual(13, report.finding_count)
        self.assertEqual(2, report.probe_status_counts["adversarial_drift_detected"])
        self.assertEqual(2, report.probe_status_counts["adversarial_drift_rejected"])
        self.assertEqual(1, report.probe_status_counts["boundary_preserved"])
        self.assertEqual(6, report.probe_status_counts["semantic_boundary_observed"])
        self.assertTrue(report.lab_is_not_permission)
        self.assertTrue(report.adversarial_findings_are_not_execution_approval)
        self.assertTrue(report.replay_pass_is_not_truth)
        self.assertTrue(report.must_not_execute_automatically)
        self.assertEqual("none", report.state_change)
        self.assertIn("non-authoritative", report.authority)

    def test_adversarial_probe_expectation_drift_is_reported_without_gate_language(self) -> None:
        probe = ControlPlaneAdversarialProbe(
            probe_id="probe-wrong-expectation",
            probe_kind="replay_missing_open",
            description="wrong expectation",
            expected_finding_codes=("replay:authority_drift",),
        )

        report = build_control_plane_adversarial_report((probe,))
        result = report.results[0]

        self.assertEqual("expected_findings_missing", result.expectation_status)
        self.assertEqual(("missing_expected_finding:replay:authority_drift",), result.expectation_failures)
        self.assertTrue(report.adversarial_findings_are_not_execution_approval)

    def test_adversarial_probe_rejects_empty_duplicate_unsafe_and_unknown_kind(self) -> None:
        probe = builtin_control_plane_adversarial_probes()[0]

        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "at least one"):
            build_control_plane_adversarial_report(())
        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "duplicate"):
            build_control_plane_adversarial_report((probe, probe))
        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "path-segment safe"):
            build_control_plane_adversarial_report((replace(probe, probe_id="../escape"),))
        with self.assertRaisesRegex(ControlPlaneScenarioLabError, "unknown probe_kind"):
            build_control_plane_adversarial_report((replace(probe, probe_id="probe-unknown", probe_kind="unknown"),))

    def test_adversarial_renderers_preserve_non_authority_markers(self) -> None:
        report = build_control_plane_adversarial_report((builtin_control_plane_adversarial_probes()[0],))

        payload = json.loads(render_control_plane_adversarial_json(report))
        markdown = render_control_plane_adversarial_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["lab_is_not_permission"])
        self.assertTrue(payload["adversarial_findings_are_not_execution_approval"])
        self.assertTrue(payload["replay_pass_is_not_truth"])
        self.assertIn("lab_is_not_permission: true", markdown)
        self.assertIn("adversarial_findings_are_not_execution_approval: true", markdown)
        self.assertIn("probe-replay-authority-drift", markdown)


if __name__ == "__main__":
    unittest.main()
