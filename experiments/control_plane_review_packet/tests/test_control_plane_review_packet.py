from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_replay_eval import evaluate_control_plane_replay_jsonl
from experiments.control_plane_review_packet import (
    ControlPlaneReviewPacketError,
    build_control_plane_review_packet,
    render_control_plane_review_packet_json,
    render_control_plane_review_packet_markdown,
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


class ControlPlaneReviewPacketTests(unittest.TestCase):
    def test_builds_advisory_packet_from_existing_layers(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-packet",
            _assessment(),
            capability_assessments=(_capability(),),
        )

        self.assertEqual("packet_advisory_review_only", packet.packet_verdict)
        self.assertEqual("advisory_review_only", packet.combined_review_status)
        self.assertEqual("replay_contract_passed", packet.replay_evaluation_verdict)
        self.assertEqual("advisory_replay_verified", packet.replay_status)
        self.assertTrue(packet.ledger_jsonl.endswith("\n"))
        self.assertEqual(packet.replay_digest, packet.trace.replay_digest)
        self.assertTrue(packet.packet_is_not_permission)
        self.assertTrue(packet.replay_pass_is_not_truth)
        self.assertTrue(packet.packet_pass_is_not_execution_approval)
        self.assertTrue(packet.must_not_execute_automatically)
        self.assertEqual(packet.replay_digest, packet.ledger.replay_digest)
        self.assertIn("packet_pass_is_not_execution_approval", packet.guardrails)
        self.assertEqual("none", packet.state_change)
        self.assertIn("non-authoritative", packet.authority)

    def test_ledger_jsonl_replays_as_the_same_contract(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-packet",
            _assessment(),
            capability_assessments=(_capability(),),
        )
        evaluation = evaluate_control_plane_replay_jsonl(packet.ledger_jsonl)

        self.assertEqual("replay_contract_passed", evaluation.verdict)
        self.assertEqual(packet.replay_digest, evaluation.replay_digest)
        self.assertEqual(packet.trace_event_count, evaluation.event_count)

    def test_blocked_trace_yields_blocked_packet_without_permission(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-blocked",
            _assessment(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(
                replace(_capability(), decision="blocked", reasons=("path_scope_violation",)),
            ),
        )

        self.assertEqual("packet_blocked", packet.packet_verdict)
        self.assertEqual("blocked_review", packet.combined_review_status)
        self.assertEqual("review_blockers", packet.recommended_human_decision)
        self.assertIn("action_blocked", [event.event_type for event in packet.trace.trace_events])
        self.assertEqual("blocked_replay_verified", packet.replay_status)
        self.assertTrue(packet.packet_is_not_permission)

    def test_missing_capability_assessment_yields_human_review_packet(self) -> None:
        packet = build_control_plane_review_packet("trace-human", _assessment())

        self.assertEqual("packet_human_review_required", packet.packet_verdict)
        self.assertEqual("human_review_required", packet.combined_review_status)
        self.assertEqual("provide_capability_assessment", packet.recommended_human_decision)
        self.assertEqual("human_review_replay_verified", packet.replay_status)

    def test_rejects_non_authoritative_assessment_or_capability(self) -> None:
        with self.assertRaisesRegex(Exception, "non-authoritative"):
            build_control_plane_review_packet(
                "trace-bad-assessment",
                replace(_assessment(), authority="runtime authority"),
                capability_assessments=(_capability(),),
            )
        with self.assertRaisesRegex(Exception, "non-authoritative"):
            build_control_plane_review_packet(
                "trace-bad-capability",
                _assessment(),
                capability_assessments=(replace(_capability(), authority="runtime authority"),),
            )

    def test_renderers_preserve_boundaries(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-packet",
            _assessment(),
            capability_assessments=(_capability(),),
        )

        payload = json.loads(render_control_plane_review_packet_json(packet))
        markdown = render_control_plane_review_packet_markdown(packet)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["packet_is_not_permission"])
        self.assertTrue(payload["replay_pass_is_not_truth"])
        self.assertTrue(payload["packet_pass_is_not_execution_approval"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertIn("packet_is_not_permission: true", markdown)
        self.assertIn("replay_pass_is_not_truth: true", markdown)
        self.assertIn("packet_pass_is_not_execution_approval: true", markdown)
        self.assertIn("packet_verdict: packet_advisory_review_only", markdown)

    def test_packet_validation_rejects_guardrail_drift(self) -> None:
        packet = build_control_plane_review_packet(
            "trace-packet",
            _assessment(),
            capability_assessments=(_capability(),),
        )

        with self.assertRaisesRegex(ControlPlaneReviewPacketError, "guardrails"):
            render_control_plane_review_packet_json(replace(packet, packet_is_not_permission=False))
        with self.assertRaisesRegex(ControlPlaneReviewPacketError, "guardrails"):
            render_control_plane_review_packet_json(replace(packet, packet_pass_is_not_execution_approval=False))
        with self.assertRaisesRegex(ControlPlaneReviewPacketError, "replay_digest"):
            render_control_plane_review_packet_json(replace(packet, replay_digest="sha256:wrong"))


if __name__ == "__main__":
    unittest.main()
