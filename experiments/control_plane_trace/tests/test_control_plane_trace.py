from __future__ import annotations

import json
import unittest

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_trace import (
    ControlPlaneTraceError,
    build_control_plane_trace,
    render_control_plane_trace_json,
    render_control_plane_trace_markdown,
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


class ControlPlaneTraceTests(unittest.TestCase):
    def test_advisory_trace_is_not_permission(self) -> None:
        trace = build_control_plane_trace("trace-1", _assessment(), capability_assessments=(_capability(),))
        payload = json.loads(render_control_plane_trace_json(trace))

        self.assertEqual("advisory_review_only", trace.combined_review_status)
        self.assertEqual("none", trace.recommended_human_decision)
        self.assertTrue(payload["trace_is_not_permission"])
        self.assertTrue(payload["assessment_pass_is_not_permission"])
        self.assertTrue(payload["capability_allow_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])

    def test_blocked_assessment_blocks_trace(self) -> None:
        trace = build_control_plane_trace(
            "trace-blocked",
            _assessment(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(_capability(),),
        )

        self.assertEqual("blocked_review", trace.combined_review_status)
        self.assertEqual("review_blockers", trace.recommended_human_decision)
        self.assertIn("missing_active_trigger_for_runtime_or_canonical_change", trace.blockers)
        self.assertIn("action_blocked", [event.event_type for event in trace.trace_events])

    def test_blocked_capability_blocks_trace_without_executing(self) -> None:
        trace = build_control_plane_trace(
            "trace-cap-blocked",
            _assessment(),
            capability_assessments=(
                _capability(
                    "blocked",
                    reasons=("network_access_denied_by_capability",),
                    required_human_decision="open_network_boundary_review",
                ),
            ),
        )

        self.assertEqual("blocked_review", trace.combined_review_status)
        self.assertIn("req-tests", trace.required_capability_reviews)
        self.assertIn("capability:req-tests:network_access_denied_by_capability", trace.blockers)
        self.assertIn("evidence_rejected", [event.event_type for event in trace.trace_events])
        self.assertTrue(trace.must_not_execute_automatically)

    def test_review_required_when_capability_requires_review(self) -> None:
        trace = build_control_plane_trace(
            "trace-review",
            _assessment(),
            capability_assessments=(
                _capability(
                    "review_required",
                    reasons=("approval_required_but_missing",),
                    required_human_decision="provide_human_approval",
                ),
            ),
        )

        self.assertEqual("human_review_required", trace.combined_review_status)
        self.assertEqual("review_capability_request", trace.recommended_human_decision)
        self.assertEqual(("req-tests",), trace.required_capability_reviews)
        self.assertIn("approval_checked", [event.event_type for event in trace.trace_events])

    def test_missing_capability_assessment_forces_review(self) -> None:
        trace = build_control_plane_trace("trace-no-cap", _assessment())

        self.assertEqual("human_review_required", trace.combined_review_status)
        self.assertEqual("provide_capability_assessment", trace.recommended_human_decision)
        self.assertEqual((), trace.capability_statuses)

    def test_replay_digest_is_stable_for_same_inputs(self) -> None:
        first = build_control_plane_trace("trace-stable", _assessment(), capability_assessments=(_capability(),))
        second = build_control_plane_trace("trace-stable", _assessment(), capability_assessments=(_capability(),))

        self.assertEqual(first.replay_digest, second.replay_digest)
        self.assertTrue(first.replay_digest.startswith("sha256:"))

    def test_trace_id_must_be_path_segment_safe(self) -> None:
        with self.assertRaisesRegex(ControlPlaneTraceError, "path-segment safe"):
            build_control_plane_trace("../escape", _assessment(), capability_assessments=(_capability(),))

    def test_markdown_renders_trace_and_boundary(self) -> None:
        markdown = render_control_plane_trace_markdown(
            build_control_plane_trace("trace-md", _assessment(), capability_assessments=(_capability(),))
        )

        self.assertIn("state_change: none", markdown)
        self.assertIn("trace_is_not_permission: true", markdown)
        self.assertIn("decision_opened", markdown)
        self.assertIn("decision_closed", markdown)

    def test_non_authoritative_inputs_are_required(self) -> None:
        with self.assertRaisesRegex(ControlPlaneTraceError, "assessment input"):
            build_control_plane_trace(
                "trace-bad-assessment",
                _assessment(state_change="write"),
                capability_assessments=(_capability(),),
            )
        with self.assertRaisesRegex(ControlPlaneTraceError, "capability input"):
            build_control_plane_trace(
                "trace-bad-capability",
                _assessment(),
                capability_assessments=(_capability(authority="runtime authority"),),
            )


if __name__ == "__main__":
    unittest.main()
