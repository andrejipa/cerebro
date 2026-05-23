from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_review_matrix import (
    ControlPlaneReviewMatrixError,
    build_control_plane_review_matrix,
    render_control_plane_review_matrix_json,
    render_control_plane_review_matrix_markdown,
)
from experiments.control_plane_review_packet import build_control_plane_review_packet


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


def _packet(name: str, *, assessment: ControlPlaneAssessment | None = None, capability: CapabilityAssessment | None = None):
    capabilities = () if capability is None else (capability,)
    return build_control_plane_review_packet(
        f"trace-{name}",
        _assessment() if assessment is None else assessment,
        capability_assessments=capabilities,
    )


class ControlPlaneReviewMatrixTests(unittest.TestCase):
    def test_matrix_aggregates_advisory_and_human_review_packets(self) -> None:
        advisory = _packet("advisory", capability=_capability())
        human = _packet("human")

        matrix = build_control_plane_review_matrix((advisory, human))

        self.assertEqual(2, matrix.packet_count)
        self.assertEqual(1, matrix.packet_verdict_counts["packet_advisory_review_only"])
        self.assertEqual(1, matrix.packet_verdict_counts["packet_human_review_required"])
        self.assertEqual(1, matrix.combined_review_status_counts["advisory_review_only"])
        self.assertEqual(1, matrix.combined_review_status_counts["human_review_required"])
        self.assertEqual(("provide_capability_assessment",), matrix.required_human_decisions)
        self.assertTrue(matrix.matrix_is_not_permission)
        self.assertTrue(matrix.matrix_pass_is_not_execution_approval)
        self.assertTrue(matrix.replay_pass_is_not_truth)
        self.assertEqual("none", matrix.state_change)
        self.assertIn("non-authoritative", matrix.authority)

    def test_blocked_packet_precedence_beats_human_review(self) -> None:
        blocked = _packet(
            "blocked",
            assessment=_assessment(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability=replace(_capability(), decision="blocked", reasons=("path_scope_violation",)),
        )
        human = _packet("human")

        matrix = build_control_plane_review_matrix((human, blocked))

        self.assertEqual(1, matrix.packet_verdict_counts["packet_blocked"])
        self.assertEqual(1, matrix.blocker_counts["missing_active_trigger_for_runtime_or_canonical_change"])
        self.assertIn("review_blockers", matrix.required_human_decisions)

    def test_replay_invalid_is_counted_without_aggregate_verdict(self) -> None:
        blocked = _packet(
            "blocked",
            assessment=_assessment(blockers=("blocker",), recommended_human_decision="review_blockers"),
            capability=_capability(),
        )
        invalid = replace(
            _packet("invalid", capability=_capability()),
            packet_verdict="packet_replay_invalid",
            replay_evaluation_verdict="replay_contract_failed",
            replay_issue_codes=("ledger_parse_failed",),
        )

        matrix = build_control_plane_review_matrix((blocked, invalid))

        self.assertEqual(1, matrix.packet_verdict_counts["packet_replay_invalid"])
        self.assertEqual(1, matrix.packet_verdict_counts["packet_blocked"])
        self.assertEqual(1, matrix.replay_issue_counts["ledger_parse_failed"])

    def test_rejects_empty_duplicate_and_unsafe_scenarios(self) -> None:
        packet = _packet("advisory", capability=_capability())

        with self.assertRaisesRegex(ControlPlaneReviewMatrixError, "at least one"):
            build_control_plane_review_matrix(())
        with self.assertRaisesRegex(ControlPlaneReviewMatrixError, "duplicate"):
            build_control_plane_review_matrix((packet, packet))
        with self.assertRaisesRegex(ControlPlaneReviewMatrixError, "path-segment safe"):
            build_control_plane_review_matrix((replace(packet, trace_id="../escape"),))

    def test_rejects_packet_guardrail_drift(self) -> None:
        packet = replace(_packet("advisory", capability=_capability()), packet_is_not_permission=False)

        with self.assertRaisesRegex(ControlPlaneReviewMatrixError, "guardrails"):
            build_control_plane_review_matrix((packet,))

    def test_renderers_preserve_non_authority_markers(self) -> None:
        matrix = build_control_plane_review_matrix((_packet("advisory", capability=_capability()),))
        payload = json.loads(render_control_plane_review_matrix_json(matrix))
        markdown = render_control_plane_review_matrix_markdown(matrix)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["matrix_is_not_permission"])
        self.assertTrue(payload["matrix_pass_is_not_execution_approval"])
        self.assertTrue(payload["replay_pass_is_not_truth"])
        self.assertIn("matrix_is_not_permission: true", markdown)
        self.assertIn("matrix_pass_is_not_execution_approval: true", markdown)
        self.assertIn("packet_verdict_counts", markdown)


if __name__ == "__main__":
    unittest.main()
