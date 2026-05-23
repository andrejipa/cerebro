from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_runtime_state_review import (
    ControlPlaneRuntimeStateReviewError,
    build_control_plane_runtime_state_review,
    render_control_plane_runtime_state_review_json,
    render_control_plane_runtime_state_review_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"


def _integrity_review(status: str = "control_plane_integrity_preserved") -> ControlPlaneIntegrityReview:
    return ControlPlaneIntegrityReview(
        schema_version="1",
        review_role="test_integrity_review",
        review_status=status,
        evidence_count=0,
        finding_count=0,
        source_status_counts={},
        severity_counts={},
        finding_codes=(),
        evidence=(),
        findings=(),
    )


def _snapshot(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "snapshot_id": "snapshot-1",
        "snapshot_thread_id": "runtime-state",
        "revision": 1,
        "captured_at": REVIEW_AS_OF,
        "state_scope": "cerebro_runtime",
        "lifecycle_status": "observed",
        "queue_authority": "not_supplied",
        "schema_version_claim": "1",
        "active_observation_ids": [],
        "open_ready_observation_ids": [],
        "blocked_observation_ids": [],
        "current_decision_ids": [],
        "active_rule_ids": [],
        "runtime_adoption_candidate_ids": [],
        "evidence_ids": ["evidence-1"],
        "supersedes_snapshot_id": "",
        "contains_secret_material": False,
        "contains_raw_evidence": False,
        "claims_canonical_state": False,
        "claims_scheduler_authority": False,
        "claims_execution_permission": False,
        "auto_apply": False,
        "generated_by": "test",
        "summary": "Advisory runtime-state snapshot only.",
        "rationale": "This snapshot is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _state_payload(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "version": "1",
        "revision": 3,
        "sources": [],
        "checkpoint": {},
        "last_validation": {},
        "agent_runtime": {
            "plan": {
                "goal": "Review state",
                "summary": "One task",
                "status": "ready",
                "current_task_id": "task-1",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Review",
                        "status": "ready",
                        "depends_on": [],
                        "action_ids": ["act-1"],
                    }
                ],
            },
            "execution_policy": {},
            "command_registry": {
                "commands": [
                    {
                        "id": "cmd-1",
                        "argv": ["python", "-m", "unittest"],
                        "cwd": ".",
                        "allow_in_verify": True,
                    }
                ]
            },
            "approvals": {"items": [{"id": "apr-1", "status": "approved", "task_id": "task-1", "resolved_at": REVIEW_AS_OF}]},
            "actions": [
                {
                    "id": "act-1",
                    "kind": "fs.write_patch",
                    "status": "planned",
                    "task_id": "task-1",
                    "approval_id": "apr-1",
                }
            ],
            "batch_registry": {"used_ids": []},
            "verification": {
                "required_command_ids": ["cmd-1"],
                "pending_action_ids": [],
                "status": "idle",
                "checks": [],
            },
            "memory": {"notes": []},
            "audit": {
                "last_action_id": "act-1",
                "active_session_id": "session-1",
                "active_session_claim_id": "claim-1",
                "trace_thread_id": "trace-1",
                "next_event_id": 3,
                "trace_status": "healthy",
                "trace_integrity": "reliable",
                "rollback_points": [],
            },
        },
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneRuntimeStateReviewTests(unittest.TestCase):
    def test_clean_snapshot_and_state_payload_are_observed_without_permission(self) -> None:
        review = build_control_plane_runtime_state_review(
            [_snapshot()],
            review_as_of=REVIEW_AS_OF,
            state_payload=_state_payload(),
            recent_events_payload=(
                {"event_id": 1, "trace_thread_id": "trace-1", "event_type": "plan_updated"},
                {"event_id": 2, "trace_thread_id": "trace-1", "event_type": "verification_checked"},
            ),
            session_payload={"session_id": "session-1", "based_on_revision": 3, "owner_claim_id": "claim-1"},
            lock_snapshot_payload={"lock_present": False, "lock_payload": {}, "process_lock_held": False},
            integrity_review=_integrity_review(),
        )

        self.assertEqual("runtime_state_snapshot_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.state_review_is_not_permission)
        self.assertTrue(review.snapshot_is_not_canonical_state)
        self.assertTrue(review.observed_state_is_not_scheduler)

    def test_rejects_duplicate_unsafe_unknown_enum_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "duplicate snapshot ids"):
            build_control_plane_runtime_state_review([_snapshot(), _snapshot()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "path-segment safe"):
            build_control_plane_runtime_state_review([_snapshot({"snapshot_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "unknown state_scope"):
            build_control_plane_runtime_state_review([_snapshot({"state_scope": "real_runtime"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "review_as_of must be an ISO date"):
            build_control_plane_runtime_state_review([_snapshot()], review_as_of="today")

    def test_snapshot_revision_and_supersession_drift_blocks_review(self) -> None:
        review = build_control_plane_runtime_state_review(
            [
                _snapshot({"snapshot_id": "snapshot-r1", "snapshot_thread_id": "thread", "revision": 1, "lifecycle_status": "observed"}),
                _snapshot(
                    {
                        "snapshot_id": "snapshot-r3",
                        "snapshot_thread_id": "thread",
                        "revision": 3,
                        "supersedes_snapshot_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertEqual("runtime_state_contract_blocked", review.review_status)
        self.assertIn("snapshot_revision_gap", review.finding_codes)
        self.assertIn("snapshot_supersedes_unknown_id", review.finding_codes)
        self.assertIn("observed_snapshot_not_latest_revision", review.finding_codes)

    def test_snapshot_authority_secret_raw_evidence_and_text_laundering_block(self) -> None:
        review = build_control_plane_runtime_state_review(
            [
                _snapshot(
                    {
                        "claims_canonical_state": True,
                        "claims_scheduler_authority": True,
                        "claims_execution_permission": True,
                        "auto_apply": True,
                        "contains_secret_material": True,
                        "contains_raw_evidence": True,
                        "summary": "This canonical state grants permission and selected next action.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )

        self.assertIn("snapshot_claims_canonical_state", review.finding_codes)
        self.assertIn("snapshot_claims_scheduler_authority", review.finding_codes)
        self.assertIn("snapshot_claims_execution_permission", review.finding_codes)
        self.assertIn("snapshot_requests_auto_apply", review.finding_codes)
        self.assertIn("snapshot_contains_secret_material", review.finding_codes)
        self.assertIn("snapshot_contains_raw_evidence", review.finding_codes)
        self.assertIn("snapshot_text_launders_runtime_state_authority", review.finding_codes)

    def test_plan_dependency_unknown_self_cycle_and_status_contradictions_are_found(self) -> None:
        state = _state_payload()
        tasks = state["agent_runtime"]["plan"]["tasks"]  # type: ignore[index]
        tasks[:] = [
            {"id": "task-a", "status": "ready", "depends_on": ["missing-task", "task-a"], "action_ids": []},
            {"id": "task-b", "status": "ready", "depends_on": ["task-c"], "action_ids": []},
            {"id": "task-c", "status": "ready", "depends_on": ["task-b"], "action_ids": []},
        ]
        state["agent_runtime"]["plan"]["current_task_id"] = "missing-current"  # type: ignore[index]
        state["agent_runtime"]["plan"]["status"] = "idle"  # type: ignore[index]

        review = build_control_plane_runtime_state_review(
            [_snapshot()],
            review_as_of=REVIEW_AS_OF,
            state_payload=state,
            integrity_review=_integrity_review(),
        )

        self.assertIn("runtime_plan_current_task_unknown", review.finding_codes)
        self.assertIn("runtime_plan_dependency_unknown", review.finding_codes)
        self.assertIn("runtime_plan_dependency_self_reference", review.finding_codes)
        self.assertIn("runtime_plan_dependency_cycle", review.finding_codes)
        self.assertIn("runtime_plan_status_contradiction", review.finding_codes)

    def test_action_approval_and_verification_relation_drift_is_found(self) -> None:
        state = _state_payload()
        runtime = state["agent_runtime"]  # type: ignore[index]
        runtime["actions"] = [
            {
                "id": "act-2",
                "kind": "fs.write_patch",
                "status": "planned",
                "task_id": "missing-task",
                "approval_id": "missing-approval",
            }
        ]
        runtime["approvals"]["items"] = [  # type: ignore[index]
            {"id": "apr-pending", "status": "pending", "task_id": "missing-task", "resolved_at": REVIEW_AS_OF}
        ]
        runtime["verification"] = {
            "required_command_ids": ["missing-cmd"],
            "pending_action_ids": ["missing-action"],
            "status": "passed",
            "checks": [{"id": "check-1", "command_id": "missing-cmd", "status": "failed"}],
        }

        review = build_control_plane_runtime_state_review(
            [_snapshot()],
            review_as_of=REVIEW_AS_OF,
            state_payload=state,
            integrity_review=_integrity_review(),
        )

        self.assertIn("runtime_action_unknown_task", review.finding_codes)
        self.assertIn("runtime_action_unknown_approval", review.finding_codes)
        self.assertIn("runtime_approval_status_contradiction", review.finding_codes)
        self.assertIn("runtime_verification_unknown_command", review.finding_codes)
        self.assertIn("runtime_verification_unknown_pending_action", review.finding_codes)
        self.assertIn("runtime_verification_status_contradiction", review.finding_codes)

    def test_trace_session_and_lock_drift_are_advisory_findings(self) -> None:
        review = build_control_plane_runtime_state_review(
            [_snapshot()],
            review_as_of=REVIEW_AS_OF,
            state_payload=_state_payload(),
            recent_events_payload=(
                {"event_id": 1, "trace_thread_id": "other-trace"},
                {"event_id": 2, "trace_thread_id": "trace-1"},
                {"event_id": 2, "trace_thread_id": "trace-1"},
                {"event_id": 3, "trace_thread_id": "trace-1"},
            ),
            session_payload={"session_id": "session-1", "based_on_revision": 99, "owner_claim_id": "other-claim"},
            lock_snapshot_payload={"lock_present": True, "lock_payload": "broken", "process_lock_held": True},
            integrity_review=_integrity_review(),
        )

        self.assertIn("runtime_trace_event_id_not_monotonic", review.finding_codes)
        self.assertIn("runtime_trace_event_thread_mismatch", review.finding_codes)
        self.assertIn("runtime_trace_next_event_id_inconsistent", review.finding_codes)
        self.assertIn("runtime_session_revision_ahead_of_state", review.finding_codes)
        self.assertIn("runtime_session_claim_mismatch", review.finding_codes)
        self.assertIn("runtime_lock_payload_invalid", review.finding_codes)
        self.assertIn("runtime_lock_owner_observed_not_authority", review.finding_codes)

    def test_integration_drift_blocks_snapshot_over_bad_reviews(self) -> None:
        review = build_control_plane_runtime_state_review(
            [_snapshot({"current_decision_ids": ["decision-1"], "active_rule_ids": ["rule-1"]})],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review("control_plane_integrity_drift_observed"),
        )

        self.assertIn("snapshot_missing_decision_review", review.finding_codes)
        self.assertIn("snapshot_missing_rule_promotion_review", review.finding_codes)
        self.assertIn("snapshot_over_integrity_drift", review.finding_codes)

    def test_rejects_supplied_review_guardrail_drift(self) -> None:
        bad_integrity = replace(_integrity_review(), review_is_not_permission=False)

        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "guardrails"):
            build_control_plane_runtime_state_review(
                [_snapshot()],
                review_as_of=REVIEW_AS_OF,
                integrity_review=bad_integrity,
            )

    def test_renderers_preserve_guardrails_and_reject_forged_summary(self) -> None:
        review = build_control_plane_runtime_state_review(
            [_snapshot()],
            review_as_of=REVIEW_AS_OF,
            state_payload=_state_payload(),
            integrity_review=_integrity_review(),
        )
        payload = json.loads(render_control_plane_runtime_state_review_json(review))
        markdown = render_control_plane_runtime_state_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["state_review_is_not_permission"])
        self.assertIn("snapshot_is_not_canonical_state: true", markdown)
        self.assertIn("observed_state_is_not_scheduler: true", markdown)
        self.assertIn("must_not_execute_automatically: true", markdown)

        forged = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "finding_count"):
            render_control_plane_runtime_state_review_json(forged)

        forged_latest_overlap = replace(
            review,
            latest_snapshot_ids=("snapshot-1",),
            non_latest_snapshot_ids=("snapshot-1",),
        )
        with self.assertRaisesRegex(ControlPlaneRuntimeStateReviewError, "disjoint"):
            render_control_plane_runtime_state_review_json(forged_latest_overlap)

    def test_package_contains_no_state_store_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_runtime_state_review"
        source_text = "\n".join(
            path.read_text(encoding="utf-8").lower()
            for path in sorted(package_root.glob("*.py"))
        )

        forbidden_fragments = (
            "core.state_store",
            "core.agent_runtime",
            "core.validation",
            "statestore",
            "runtime_lock(",
            "read_text",
            "write_text",
            ".cerebro",
            "docs/operations",
            "subprocess",
            "import requests",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()
