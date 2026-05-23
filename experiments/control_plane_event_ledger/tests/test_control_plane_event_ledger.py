from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_event_ledger import (
    ControlPlaneEventLedgerError,
    build_control_plane_event_ledger,
    parse_control_plane_event_ledger_jsonl,
    render_control_plane_event_ledger_jsonl,
)
from experiments.control_plane_trace import ControlPlaneTrace, build_control_plane_trace


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


def _trace(**assessment_overrides) -> ControlPlaneTrace:
    return build_control_plane_trace(
        "trace-ledger",
        _assessment(**assessment_overrides),
        capability_assessments=(_capability(),),
    )


class ControlPlaneEventLedgerTests(unittest.TestCase):
    def test_builds_jsonl_ledger_from_trace_without_permission(self) -> None:
        ledger = build_control_plane_event_ledger(_trace())
        jsonl = render_control_plane_event_ledger_jsonl(ledger)
        rows = [json.loads(line) for line in jsonl.splitlines()]

        self.assertEqual("advisory_replay_verified", ledger.replay_status)
        self.assertEqual("decision_opened", rows[0]["event_type"])
        self.assertEqual("decision_closed", rows[-1]["event_type"])
        self.assertTrue(rows[0]["ledger_is_not_permission"])
        self.assertTrue(rows[0]["must_not_execute_automatically"])
        self.assertTrue(rows[0]["replay_digest_is_not_truth"])
        self.assertEqual("derived_control_plane_trace_event", rows[0]["ledger_role"])
        self.assertTrue(rows[0]["event_digest"].startswith("sha256:"))
        self.assertEqual("none", rows[0]["state_change"])
        self.assertIn("non-authoritative", rows[0]["authority"])

    def test_parse_round_trips_jsonl_and_preserves_digest(self) -> None:
        ledger = build_control_plane_event_ledger(_trace())
        parsed = parse_control_plane_event_ledger_jsonl(render_control_plane_event_ledger_jsonl(ledger))

        self.assertEqual(ledger.trace_id, parsed.trace_id)
        self.assertEqual(ledger.replay_digest, parsed.replay_digest)
        self.assertEqual(len(ledger.records), len(parsed.records))
        self.assertEqual("advisory_replay_verified", parsed.replay_status)

    def test_blocked_trace_replays_as_blocked(self) -> None:
        ledger = build_control_plane_event_ledger(
            _trace(
                epistemic_action_readiness="canonical_change_requires_trigger",
                blockers=("missing_active_trigger_for_runtime_or_canonical_change",),
                recommended_human_decision="review_blockers",
            )
        )

        self.assertEqual("blocked_replay_verified", ledger.replay_status)
        self.assertIn("action_blocked", [record.event_type for record in ledger.records])

    def test_rejects_trace_with_non_advisory_authority(self) -> None:
        trace = replace(_trace(), authority="runtime authority")

        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "trace input"):
            build_control_plane_event_ledger(trace)

    def test_rejects_missing_decision_opened_or_decision_closed(self) -> None:
        ledger = build_control_plane_event_ledger(_trace())

        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "start with decision_opened"):
            parse_control_plane_event_ledger_jsonl(
                render_control_plane_event_ledger_jsonl(replace(ledger, records=ledger.records[1:]))
            )
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "end with decision_closed"):
            parse_control_plane_event_ledger_jsonl(
                render_control_plane_event_ledger_jsonl(replace(ledger, records=ledger.records[:-1]))
            )

    def test_rejects_mixed_trace_ids_and_non_contiguous_sequences(self) -> None:
        ledger = build_control_plane_event_ledger(_trace())
        mixed = (ledger.records[0], replace(ledger.records[1], trace_id="other-trace"), ledger.records[-1])
        bad_sequence = (
            ledger.records[0],
            replace(ledger.records[1], sequence=5),
            *ledger.records[2:],
        )

        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "one trace_id"):
            parse_control_plane_event_ledger_jsonl("\n".join(json.dumps(record.__dict__) for record in mixed) + "\n")
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "contiguous"):
            parse_control_plane_event_ledger_jsonl(
                "\n".join(json.dumps(record.__dict__) for record in bad_sequence) + "\n"
            )

    def test_rejects_unknown_event_and_guardrail_drift(self) -> None:
        ledger = build_control_plane_event_ledger(_trace())
        unknown = replace(ledger.records[1], event_type="tool_executed")
        guardrail_drift = replace(ledger.records[1], ledger_is_not_permission=False)
        truth_drift = replace(ledger.records[1], replay_digest_is_not_truth=False)

        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "unknown event_type"):
            parse_control_plane_event_ledger_jsonl(
                "\n".join(
                    json.dumps(record.__dict__)
                    for record in (ledger.records[0], unknown, *ledger.records[2:])
                )
                + "\n"
            )
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "guardrails"):
            parse_control_plane_event_ledger_jsonl(
                "\n".join(
                    json.dumps(record.__dict__)
                    for record in (ledger.records[0], guardrail_drift, *ledger.records[2:])
                )
                + "\n"
            )
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "guardrails"):
            parse_control_plane_event_ledger_jsonl(
                "\n".join(
                    json.dumps(record.__dict__)
                    for record in (ledger.records[0], truth_drift, *ledger.records[2:])
                )
                + "\n"
            )

    def test_rejects_empty_and_invalid_jsonl(self) -> None:
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "must not be empty"):
            parse_control_plane_event_ledger_jsonl("")
        with self.assertRaisesRegex(ControlPlaneEventLedgerError, "invalid JSONL"):
            parse_control_plane_event_ledger_jsonl("{not-json}\n")


if __name__ == "__main__":
    unittest.main()
