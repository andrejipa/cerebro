from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_loop_stop_eval import (
    ControlPlaneLoopStopEvalError,
    ControlPlaneLoopStopStep,
    evaluate_control_plane_loop_stop,
    render_control_plane_loop_stop_json,
    render_control_plane_loop_stop_markdown,
)


def _step(iteration_id: str = "iter-1", **overrides: object) -> ControlPlaneLoopStopStep:
    values = {
        "loop_id": "loop-a",
        "iteration_id": iteration_id,
        "sequence_index": 1,
        "review_as_of": "2026-05-08",
        "subject_id": "third-party-pilot-cycle-1",
        "subject_kind": "slice",
        "continuation_claim": "continue",
        "validation_status": "passed",
        "validation_revision": "rev-1",
        "expected_revision": "rev-1",
        "queue_head_id": "third-party-pilot-cycle-1",
        "queue_head_status": "open",
        "queue_head_latest": True,
        "dependencies_satisfied": True,
        "trigger_status": "active",
        "stop_condition_id": "stop-a",
        "stop_condition_status": "not_met",
        "human_decision_ids": (),
        "evidence_ids": ("evidence-a",),
        "evidence_digest": "digest-a",
        "referenced_review_ids": ("review-a",),
        "referenced_review_statuses": ("control_plane_integrity_preserved",),
        "blocked_ids": (),
        "missing_evidence_ids": (),
        "ready_ids": ("third-party-pilot-cycle-1",),
        "observed_frontier_ids": ("third-party-pilot-cycle-1",),
        "active_agent_ids": ("agent-a",),
        "agent_focus_id": "third-party-pilot-cycle-1",
        "auto_continue_requested": False,
        "claims_scheduler_authority": False,
        "grants_execution_permission": False,
        "mutates_state": False,
        "reads_live_queue": False,
        "summary": "advisory loop frame only",
        "rationale": "not permission and not a scheduler",
    }
    values.update(overrides)
    return ControlPlaneLoopStopStep(**values)


class ControlPlaneLoopStopEvalTests(unittest.TestCase):
    def test_clean_continue_frame_is_observed_without_permission(self) -> None:
        report = evaluate_control_plane_loop_stop((_step(),), review_as_of="2026-05-08")

        self.assertEqual("loop_frame_observed", report.eval_status)
        self.assertEqual(1, report.step_count)
        self.assertEqual(0, report.finding_count)
        self.assertTrue(report.loop_stop_eval_is_not_permission)
        self.assertTrue(report.loop_stop_eval_is_not_scheduler)

    def test_stop_frame_with_met_condition_is_honored(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (_step(continuation_claim="stop", stop_condition_status="met", validation_status="passed"),),
            review_as_of="2026-05-08",
        )

        self.assertEqual("loop_frame_observed", report.eval_status)
        self.assertEqual(("iter-1",), report.stopped_step_ids)
        self.assertEqual(("iter-1",), report.met_stop_step_ids)

    def test_continue_after_failed_validation_or_stop_condition_is_blocked(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (
                _step(
                    validation_status="failed",
                    stop_condition_status="met",
                    human_decision_ids=(),
                    evidence_ids=("evidence-a",),
                ),
            ),
            review_as_of="2026-05-08",
        )

        self.assertEqual("loop_frame_blocked", report.eval_status)
        self.assertIn("continue_with_invalid_validation", report.finding_codes)
        self.assertIn("continue_after_stop_condition_met", report.finding_codes)
        self.assertEqual(("iter-1",), report.unsafe_continuation_step_ids)
        self.assertEqual(("iter-1",), report.missing_human_override_step_ids)

    def test_human_override_is_evidence_but_not_permission(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (
                _step(
                    stop_condition_status="met",
                    human_decision_ids=("decision-a",),
                    evidence_ids=("evidence-a",),
                    rationale="human override evidence is present; not permission",
                ),
            ),
            review_as_of="2026-05-08",
        )

        self.assertIn("continue_after_stop_condition_met", report.finding_codes)
        self.assertEqual((), report.missing_human_override_step_ids)
        self.assertTrue(report.loop_stop_eval_is_not_permission)

    def test_continue_over_waiting_queue_missing_trigger_and_unsatisfied_dependencies(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (
                _step(
                    queue_head_status="waiting",
                    trigger_status="missing",
                    dependencies_satisfied=False,
                    referenced_review_statuses=("work_queue_review_blocked",),
                    blocked_ids=("third-party-pilot-cycle-1",),
                    missing_evidence_ids=("legacy-state-decision",),
                ),
            ),
            review_as_of="2026-05-08",
        )

        self.assertIn("continue_without_active_trigger", report.finding_codes)
        self.assertIn("continue_over_non_open_queue_head", report.finding_codes)
        self.assertIn("continue_with_unsatisfied_dependencies", report.finding_codes)
        self.assertIn("continue_over_blocking_review_status", report.finding_codes)
        self.assertIn("continue_with_blocked_ids", report.finding_codes)
        self.assertIn("continue_with_missing_evidence", report.finding_codes)

    def test_single_flight_and_agent_focus_drift_are_detected(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (
                _step(
                    observed_frontier_ids=("head-a", "head-b"),
                    ready_ids=("head-a", "head-b"),
                    queue_head_id="head-a",
                    agent_focus_id="head-b",
                ),
            ),
            review_as_of="2026-05-08",
        )

        self.assertIn("single_flight_frontier_drift", report.finding_codes)
        self.assertIn("single_flight_ready_drift", report.finding_codes)
        self.assertIn("agent_focus_queue_head_drift", report.finding_codes)
        self.assertEqual(("iter-1",), report.single_flight_drift_step_ids)

    def test_stop_condition_drift_and_no_progress_digest_are_detected(self) -> None:
        first = _step(
            "iter-1",
            sequence_index=1,
            continuation_claim="stop",
            stop_condition_status="met",
            evidence_digest="digest-a",
        )
        second = _step(
            "iter-2",
            sequence_index=2,
            continuation_claim="continue",
            stop_condition_status="not_met",
            evidence_digest="digest-a",
            human_decision_ids=(),
            evidence_ids=("evidence-a",),
        )

        report = evaluate_control_plane_loop_stop((first, second), review_as_of="2026-05-08")

        self.assertIn("stop_condition_drift_without_evidence", report.finding_codes)
        self.assertIn("continue_without_new_evidence", report.finding_codes)
        self.assertEqual(("iter-2",), report.repeated_evidence_step_ids)

    def test_boundary_authority_and_auto_continue_drift_are_detected(self) -> None:
        report = evaluate_control_plane_loop_stop(
            (
                _step(
                    auto_continue_requested=True,
                    claims_scheduler_authority=True,
                    grants_execution_permission=True,
                    mutates_state=True,
                    reads_live_queue=True,
                    summary="permission to continue; scheduler selected next action",
                    rationale="runtime authority",
                ),
            ),
            review_as_of="2026-05-08",
        )

        self.assertIn("auto_continue_requested", report.finding_codes)
        self.assertIn("loop_step_claims_scheduler_authority", report.finding_codes)
        self.assertIn("loop_step_grants_execution_permission", report.finding_codes)
        self.assertIn("loop_step_mutates_state", report.finding_codes)
        self.assertIn("loop_step_reads_live_queue", report.finding_codes)
        self.assertIn("loop_authority_text_laundering", report.finding_codes)

    def test_rejects_bad_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "at least one"):
            evaluate_control_plane_loop_stop((), review_as_of="2026-05-08")
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "ISO date"):
            evaluate_control_plane_loop_stop((_step(),), review_as_of="08-05-2026")
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "path-segment"):
            evaluate_control_plane_loop_stop((_step(subject_id="../escape"),), review_as_of="2026-05-08")
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "unique"):
            evaluate_control_plane_loop_stop((_step(), _step()), review_as_of="2026-05-08")

    def test_mapping_input_and_renderers_preserve_guardrails(self) -> None:
        payload = _step().__dict__
        report = evaluate_control_plane_loop_stop((payload,), review_as_of="2026-05-08")

        rendered = json.loads(render_control_plane_loop_stop_json(report))
        markdown = render_control_plane_loop_stop_markdown(report)

        self.assertEqual("none", rendered["state_change"])
        self.assertTrue(rendered["loop_stop_eval_is_not_permission"])
        self.assertIn("loop_stop_eval_is_not_permission: true", markdown)
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "finding_count"):
            render_control_plane_loop_stop_json(replace(report, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneLoopStopEvalError, "guardrails"):
            render_control_plane_loop_stop_markdown(replace(report, loop_stop_eval_is_not_scheduler=False))

    def test_package_source_has_no_runtime_io_or_store_surfaces(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", text)
        self.assertNotIn("from opentelemetry", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("write_text", text)
        self.assertNotIn("read_text", text)
        self.assertNotIn("open(", text)
        self.assertNotIn("observation_center", text)
        self.assertNotIn("from core", text)
        self.assertNotIn("import core", text)


if __name__ == "__main__":
    unittest.main()
