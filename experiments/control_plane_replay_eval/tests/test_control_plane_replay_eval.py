from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_event_ledger import (
    build_control_plane_event_ledger,
    render_control_plane_event_ledger_jsonl,
)
from experiments.control_plane_replay_eval import (
    evaluate_control_plane_replay_jsonl,
    render_control_plane_replay_evaluation_json,
    render_control_plane_replay_evaluation_markdown,
)
from experiments.control_plane_trace import build_control_plane_trace


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


def _jsonl() -> str:
    trace = build_control_plane_trace(
        "trace-replay-eval",
        _assessment(),
        capability_assessments=(_capability(),),
    )
    return render_control_plane_event_ledger_jsonl(build_control_plane_event_ledger(trace))


class ControlPlaneReplayEvalTests(unittest.TestCase):
    def test_passes_valid_replay_without_permission(self) -> None:
        evaluation = evaluate_control_plane_replay_jsonl(_jsonl())

        self.assertEqual("replay_contract_passed", evaluation.verdict)
        self.assertEqual("none", evaluation.required_human_decision)
        self.assertEqual("none", evaluation.state_change)
        self.assertIn("non-authoritative", evaluation.authority)
        self.assertTrue(evaluation.evaluation_is_not_permission)
        self.assertTrue(evaluation.replay_pass_is_not_truth)
        self.assertTrue(evaluation.must_not_execute_automatically)
        self.assertEqual((), evaluation.issues)

    def test_renderers_preserve_non_authority_markers(self) -> None:
        evaluation = evaluate_control_plane_replay_jsonl(_jsonl())
        rendered_json = render_control_plane_replay_evaluation_json(evaluation)
        rendered_markdown = render_control_plane_replay_evaluation_markdown(evaluation)

        payload = json.loads(rendered_json)
        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["evaluation_is_not_permission"])
        self.assertTrue(payload["replay_pass_is_not_truth"])
        self.assertIn("evaluation_is_not_permission: true", rendered_markdown)
        self.assertIn("replay_pass_is_not_truth: true", rendered_markdown)

    def test_empty_and_invalid_jsonl_do_not_pass(self) -> None:
        empty = evaluate_control_plane_replay_jsonl("")
        invalid = evaluate_control_plane_replay_jsonl("{not-json}\n")

        self.assertEqual("replay_incomplete", empty.verdict)
        self.assertEqual("review_replay_contract", empty.required_human_decision)
        self.assertEqual("empty_jsonl", empty.issues[0].code)
        self.assertEqual("replay_contract_failed", invalid.verdict)
        self.assertEqual("invalid_jsonl", invalid.issues[0].code)

    def test_authority_drift_is_classified_before_generic_parse_failure(self) -> None:
        rows = [json.loads(line) for line in _jsonl().splitlines()]
        rows[1]["authority"] = "runtime authority"
        rows[1]["state_change"] = "writes_state"
        rows[1]["ledger_is_not_permission"] = False
        drifted = "\n".join(json.dumps(row) for row in rows) + "\n"

        evaluation = evaluate_control_plane_replay_jsonl(drifted)

        self.assertEqual("replay_contains_authority_drift", evaluation.verdict)
        self.assertEqual(
            {"authority_drift", "state_change_drift", "permission_guardrail_drift"},
            {issue.code for issue in evaluation.issues},
        )

    def test_missing_open_or_close_is_incomplete(self) -> None:
        rows = [json.loads(line) for line in _jsonl().splitlines()]

        missing_open = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows[1:]) + "\n")
        missing_close = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows[:-1]) + "\n")

        self.assertEqual("replay_incomplete", missing_open.verdict)
        self.assertEqual("missing_decision_opened", missing_open.issues[0].code)
        self.assertEqual("replay_incomplete", missing_close.verdict)
        self.assertEqual("missing_decision_closed", missing_close.issues[0].code)

    def test_sequence_tamper_is_incomplete(self) -> None:
        rows = [json.loads(line) for line in _jsonl().splitlines()]
        rows[1]["sequence"] = 99

        evaluation = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows) + "\n")

        self.assertEqual("replay_incomplete", evaluation.verdict)
        self.assertEqual("ledger_parse_failed", evaluation.issues[0].code)
        self.assertIn("contiguous", evaluation.issues[0].detail)

    def test_unknown_event_fails_contract(self) -> None:
        rows = [json.loads(line) for line in _jsonl().splitlines()]
        rows[1]["event_type"] = "tool_executed"

        evaluation = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows) + "\n")

        self.assertEqual("replay_contract_failed", evaluation.verdict)
        self.assertIn("unknown event_type", evaluation.issues[0].detail)

    def test_event_digest_tamper_fails_contract(self) -> None:
        rows = [json.loads(line) for line in _jsonl().splitlines()]
        rows[1]["event_digest"] = "sha256:wrong"

        evaluation = evaluate_control_plane_replay_jsonl("\n".join(json.dumps(row) for row in rows) + "\n")

        self.assertEqual("replay_contract_failed", evaluation.verdict)
        self.assertIn("event_digest", evaluation.issues[0].detail)

    def test_blocked_replay_can_pass_contract_without_becoming_permission(self) -> None:
        trace = build_control_plane_trace(
            "trace-blocked",
            _assessment(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            ),
            capability_assessments=(replace(_capability(), decision="blocked", reasons=("path_scope_violation",)),),
        )
        jsonl = render_control_plane_event_ledger_jsonl(build_control_plane_event_ledger(trace))

        evaluation = evaluate_control_plane_replay_jsonl(jsonl)

        self.assertEqual("replay_contract_passed", evaluation.verdict)
        self.assertEqual("blocked_replay_verified", evaluation.replay_status)
        self.assertIn("action_blocked", evaluation.event_types)
        self.assertTrue(evaluation.evaluation_is_not_permission)


if __name__ == "__main__":
    unittest.main()
