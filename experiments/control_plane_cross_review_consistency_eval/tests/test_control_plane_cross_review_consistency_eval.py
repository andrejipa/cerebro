from __future__ import annotations

import json
import unittest
from dataclasses import dataclass, replace
from pathlib import Path

from experiments.control_plane_cross_review_consistency_eval import (
    ControlPlaneCrossReviewConsistencyError,
    evaluate_control_plane_cross_review_consistency,
    render_control_plane_cross_review_consistency_json,
    render_control_plane_cross_review_consistency_markdown,
)


@dataclass(frozen=True)
class Finding:
    code: str
    severity: str


@dataclass(frozen=True)
class Subject:
    subject_id: str
    review_status: str = "control_plane_integrity_preserved"
    trace_id: str = ""
    replay_digest: str = ""
    finding_count: int = 0
    finding_codes: tuple[str, ...] = ()
    severity_counts: dict[str, int] | None = None
    findings: tuple[Finding, ...] = ()
    blockers: tuple[str, ...] = ()
    missing_evidence: tuple[str, ...] = ()
    blocked_item_ids: tuple[str, ...] = ()
    ready_candidate_ids: tuple[str, ...] = ()
    allowed_tool_ids: tuple[str, ...] = ()
    active_policy_ids: tuple[str, ...] = ()
    action_posture: str = ""
    integrity_status: str = "control_plane_integrity_preserved"
    packet_verdict: str = "packet_advisory_review_only"
    state_change: str = "none"
    authority: str = "non-authoritative; advisory test subject only"
    must_not_execute_automatically: bool = True

    def __post_init__(self) -> None:
        if self.severity_counts is None:
            object.__setattr__(self, "severity_counts", {})


def _clean_subject(subject_id: str = "review-a") -> Subject:
    return Subject(subject_id=subject_id)


class ControlPlaneCrossReviewConsistencyEvalTests(unittest.TestCase):
    def test_clean_subjects_preserve_cross_review_consistency(self) -> None:
        report = evaluate_control_plane_cross_review_consistency(
            (_clean_subject("integrity-a"), _clean_subject("approval-a")),
            review_as_of="2026-05-08",
        )

        self.assertEqual("cross_review_consistency_preserved", report.eval_status)
        self.assertEqual(2, report.subject_count)
        self.assertEqual(0, report.finding_count)
        self.assertTrue(report.consistency_eval_is_not_permission)
        self.assertTrue(report.consistency_status_is_not_truth)

    def test_duplicate_subject_id_and_shared_trace_digest_conflict_block(self) -> None:
        left = Subject(subject_id="packet-a", trace_id="trace-a", replay_digest="digest-a")
        right = Subject(subject_id="packet-a", trace_id="trace-a", replay_digest="digest-b")

        report = evaluate_control_plane_cross_review_consistency((left, right), review_as_of="2026-05-08")

        self.assertEqual("cross_review_consistency_drift_observed", report.eval_status)
        self.assertIn("duplicate_subject_id", report.finding_codes)
        self.assertIn("shared_identity_replay_digest_conflict", report.finding_codes)

    def test_shared_identity_clean_and_blocked_status_conflict(self) -> None:
        clean = Subject(subject_id="packet-a", trace_id="trace-a", review_status="control_plane_integrity_preserved")
        blocked = Subject(
            subject_id="packet-b",
            trace_id="trace-a",
            review_status="control_plane_integrity_drift_observed",
            finding_count=1,
            finding_codes=("permission_laundering_text",),
            severity_counts={"high": 1},
            findings=(Finding("permission_laundering_text", "high"),),
        )

        report = evaluate_control_plane_cross_review_consistency((clean, blocked), review_as_of="2026-05-08")

        self.assertIn("shared_identity_status_conflict", report.finding_codes)
        self.assertIn("packet-b", report.blocked_dependency_subject_ids)

    def test_action_clean_over_integrity_packet_or_blockers_is_detected(self) -> None:
        action = Subject(
            subject_id="action-a",
            action_posture="advisory_review_only",
            integrity_status="control_plane_integrity_drift_observed",
            packet_verdict="packet_blocked",
            blockers=("observation_status_waiting",),
        )

        report = evaluate_control_plane_cross_review_consistency((action,), review_as_of="2026-05-08")

        self.assertIn("action_clean_over_integrity_drift", report.finding_codes)
        self.assertIn("action_clean_over_packet_blocker", report.finding_codes)
        self.assertIn("action_clean_with_blockers", report.finding_codes)

    def test_ready_allowed_and_active_candidates_over_blocked_dependency_are_detected(self) -> None:
        blocked = Subject(
            subject_id="integrity-blocked",
            review_status="control_plane_integrity_drift_observed",
            finding_count=1,
            finding_codes=("lineage_drift",),
            severity_counts={"high": 1},
            findings=(Finding("lineage_drift", "high"),),
        )
        ready = Subject(subject_id="queue-ready", review_status="work_queue_candidates_observed", ready_candidate_ids=("work-a",))
        allowed = Subject(subject_id="tool-allowed", review_status="tool_manifest_candidate_observed", allowed_tool_ids=("tool-a",))
        active = Subject(subject_id="approval-active", review_status="approval_policy_candidate_observed", active_policy_ids=("policy-a",))

        report = evaluate_control_plane_cross_review_consistency(
            (blocked, ready, allowed, active),
            review_as_of="2026-05-08",
        )

        self.assertIn("ready_subject_over_blocked_dependency", report.finding_codes)
        self.assertIn("allowed_tool_over_blocked_dependency", report.finding_codes)
        self.assertIn("active_candidate_over_blocked_dependency", report.finding_codes)

    def test_local_subject_boundary_and_status_contradictions_are_detected(self) -> None:
        subject = Subject(
            subject_id="queue-a",
            review_status="work_queue_candidates_observed",
            blocked_item_ids=("work-blocked",),
            state_change="write",
            authority="runtime authority",
            must_not_execute_automatically=False,
        )

        report = evaluate_control_plane_cross_review_consistency((subject,), review_as_of="2026-05-08")

        self.assertIn("subject_mutates_state", report.finding_codes)
        self.assertIn("subject_lacks_non_authority", report.finding_codes)
        self.assertIn("subject_allows_auto_execution", report.finding_codes)
        self.assertIn("clean_status_with_blocked_ids", report.finding_codes)

    def test_forged_finding_summaries_and_missing_evidence_are_detected(self) -> None:
        subject = Subject(
            subject_id="evidence-a",
            review_status="evidence_policy_candidate_observed",
            finding_count=0,
            finding_codes=(),
            severity_counts={},
            findings=(Finding("raw_evidence_retained", "high"),),
            missing_evidence=("human_decision",),
        )

        report = evaluate_control_plane_cross_review_consistency((subject,), review_as_of="2026-05-08")

        self.assertIn("subject_forged_finding_count", report.finding_codes)
        self.assertIn("subject_forged_finding_codes", report.finding_codes)
        self.assertIn("subject_forged_severity_counts", report.finding_codes)
        self.assertIn("clean_status_with_missing_evidence", report.finding_codes)

    def test_rejects_empty_bad_dates_and_unsafe_ids(self) -> None:
        with self.assertRaisesRegex(ControlPlaneCrossReviewConsistencyError, "at least one"):
            evaluate_control_plane_cross_review_consistency((), review_as_of="2026-05-08")
        with self.assertRaisesRegex(ControlPlaneCrossReviewConsistencyError, "ISO date"):
            evaluate_control_plane_cross_review_consistency((_clean_subject(),), review_as_of="08-05-2026")
        with self.assertRaisesRegex(ControlPlaneCrossReviewConsistencyError, "path-segment"):
            evaluate_control_plane_cross_review_consistency((Subject(subject_id="../escape"),), review_as_of="2026-05-08")

    def test_renderers_preserve_guardrails_and_reject_forged_report(self) -> None:
        report = evaluate_control_plane_cross_review_consistency((_clean_subject(),), review_as_of="2026-05-08")

        payload = json.loads(render_control_plane_cross_review_consistency_json(report))
        markdown = render_control_plane_cross_review_consistency_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["consistency_eval_is_not_permission"])
        self.assertIn("consistency_eval_is_not_permission: true", markdown)
        with self.assertRaisesRegex(ControlPlaneCrossReviewConsistencyError, "finding_count"):
            render_control_plane_cross_review_consistency_json(replace(report, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneCrossReviewConsistencyError, "guardrails"):
            render_control_plane_cross_review_consistency_markdown(
                replace(report, consistency_eval_is_not_scheduler=False)
            )

    def test_package_source_has_no_runtime_io_or_store_surfaces(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", text)
        self.assertNotIn("from opentelemetry", text)
        self.assertNotIn("subprocess", text)
        self.assertNotIn("write_text", text)
        self.assertNotIn("read_text", text)
        self.assertNotIn("open(", text)
        self.assertNotIn("approval_store", text)
        self.assertNotIn("observation_center", text)


if __name__ == "__main__":
    unittest.main()
