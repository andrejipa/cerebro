from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_runtime_state_review import build_control_plane_runtime_state_review
from experiments.control_plane_runtime_state_transition_review import (
    ControlPlaneRuntimeStateTransitionReviewError,
    build_control_plane_runtime_state_transition_review,
    render_control_plane_runtime_state_transition_review_json,
    render_control_plane_runtime_state_transition_review_markdown,
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


def _state_review(snapshot: dict[str, object] | None = None):
    return build_control_plane_runtime_state_review(
        [snapshot or _snapshot()],
        review_as_of=REVIEW_AS_OF,
        integrity_review=_integrity_review(),
    )


def _evidence(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "evidence_id": "evidence-transition-1",
        "subject_kind": "snapshot",
        "subject_id": "snapshot-2",
        "evidence_kind": "supersession",
        "human_decision_id": "human-transition-1",
        "detail": "Human-confirmed supersession evidence; not permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneRuntimeStateTransitionReviewTests(unittest.TestCase):
    def test_clean_before_after_transition_is_observed_without_permission(self) -> None:
        before = _state_review()
        after = _state_review(
            _snapshot(
                {
                    "snapshot_id": "snapshot-2",
                    "evidence_ids": ["evidence-2"],
                }
            )
        )

        review = build_control_plane_runtime_state_transition_review(
            before,
            after,
            transition_evidence_payloads=[_evidence()],
        )

        self.assertEqual("runtime_state_transition_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertEqual(("snapshot-2",), review.added_latest_snapshot_ids)
        self.assertTrue(review.transition_review_is_not_permission)
        self.assertTrue(review.observed_transition_is_not_scheduler)
        self.assertTrue(review.transition_review_is_not_state_store)

    def test_rejects_duplicate_unsafe_unknown_evidence_and_bad_dates(self) -> None:
        before = _state_review()
        after = _state_review(_snapshot({"snapshot_id": "snapshot-2", "revision": 2, "supersedes_snapshot_id": "snapshot-1"}))

        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "duplicate transition evidence ids"):
            build_control_plane_runtime_state_transition_review(before, after, transition_evidence_payloads=[_evidence(), _evidence()])

        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "path-segment safe"):
            build_control_plane_runtime_state_transition_review(
                before,
                after,
                transition_evidence_payloads=[_evidence({"subject_id": "../escape"})],
            )

        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "unknown transition evidence_kind"):
            build_control_plane_runtime_state_transition_review(
                before,
                after,
                transition_evidence_payloads=[_evidence({"evidence_kind": "magic"})],
            )

        regressed_after = replace(after, review_as_of="2026-05-07")
        review = build_control_plane_runtime_state_transition_review(before, regressed_after, transition_evidence_payloads=[_evidence()])
        self.assertIn("runtime_transition_review_date_regressed", review.finding_codes)

    def test_temporal_laundering_without_evidence_is_blocked(self) -> None:
        before = _state_review()
        after = _state_review(
            _snapshot(
                {
                    "snapshot_id": "snapshot-2",
                    "revision": 2,
                    "active_observation_ids": ["obs-1", "obs-2"],
                    "open_ready_observation_ids": ["obs-2"],
                    "current_decision_ids": ["decision-1"],
                    "active_rule_ids": ["rule-1"],
                    "runtime_adoption_candidate_ids": ["proposal-1"],
                    "observed_state_scopes": ["cerebro_runtime"],
                }
            )
        )

        review = build_control_plane_runtime_state_transition_review(before, after)

        self.assertEqual("runtime_state_transition_drift_observed", review.review_status)
        self.assertIn("latest_snapshot_changed_without_supersession_evidence", review.finding_codes)
        self.assertIn("open_ready_observation_introduced_without_evidence", review.finding_codes)
        self.assertIn("current_decision_changed_without_human_evidence", review.finding_codes)
        self.assertIn("active_rule_changed_without_rule_evidence", review.finding_codes)
        self.assertIn("runtime_candidate_introduced_without_adoption_review", review.finding_codes)

    def test_removed_active_and_state_scope_drift_require_evidence(self) -> None:
        before = _state_review(_snapshot({"active_observation_ids": ["obs-1", "obs-removed"]}))
        after = _state_review(
            _snapshot(
                {
                    "snapshot_id": "snapshot-2",
                    "revision": 2,
                    "state_scope": "target_project",
                    "active_observation_ids": ["obs-1"],
                }
            )
        )

        review = build_control_plane_runtime_state_transition_review(
            before,
            after,
            transition_evidence_payloads=[_evidence()],
        )

        self.assertIn("active_observation_removed_without_resolution", review.finding_codes)
        self.assertIn("state_scope_changed_without_transition_evidence", review.finding_codes)

    def test_blocked_before_or_after_reviews_are_not_clean_transition(self) -> None:
        blocked_before = build_control_plane_runtime_state_review(
            [_snapshot({"claims_canonical_state": True})],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )
        after = _state_review(_snapshot({"snapshot_id": "snapshot-2", "revision": 2}))

        review = build_control_plane_runtime_state_transition_review(
            blocked_before,
            after,
            transition_evidence_payloads=[_evidence()],
        )

        self.assertIn("runtime_transition_over_blocked_before_state", review.finding_codes)

    def test_transition_evidence_laundering_and_lock_recovery_claims_are_found(self) -> None:
        before = _state_review()
        after = _state_review(_snapshot({"snapshot_id": "snapshot-2", "revision": 2}))

        review = build_control_plane_runtime_state_transition_review(
            before,
            after,
            transition_evidence_payloads=[
                _evidence({"detail": "This transition grants permission and selected next action."}),
                _evidence(
                    {
                        "evidence_id": "evidence-lock",
                        "subject_kind": "lock",
                        "subject_id": "lock-1",
                        "evidence_kind": "lock_observation",
                        "human_decision_id": "human-lock-1",
                        "detail": "lock recovered with recovery authority",
                    }
                ),
            ],
        )

        self.assertIn("transition_evidence_claims_permission", review.finding_codes)
        self.assertIn("session_or_lock_transition_claims_recovery_authority", review.finding_codes)

    def test_rejects_supplied_review_guardrail_drift(self) -> None:
        before = replace(_state_review(), state_review_is_not_permission=False)
        after = _state_review(_snapshot({"snapshot_id": "snapshot-2", "revision": 2}))

        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "guardrails drifted"):
            build_control_plane_runtime_state_transition_review(before, after, transition_evidence_payloads=[_evidence()])

    def test_renderers_preserve_guardrails_and_reject_forged_summary(self) -> None:
        before = _state_review()
        after = _state_review(_snapshot({"snapshot_id": "snapshot-2", "revision": 2}))
        review = build_control_plane_runtime_state_transition_review(
            before,
            after,
            transition_evidence_payloads=[_evidence()],
        )
        payload = json.loads(render_control_plane_runtime_state_transition_review_json(review))
        markdown = render_control_plane_runtime_state_transition_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["transition_review_is_not_permission"])
        self.assertIn("observed_transition_is_not_scheduler: true", markdown)
        self.assertIn("transition_review_is_not_state_store: true", markdown)

        forged_count = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "finding_count"):
            render_control_plane_runtime_state_transition_review_json(forged_count)

        forged_ids = replace(review, added_latest_snapshot_ids=("ghost",))
        with self.assertRaisesRegex(ControlPlaneRuntimeStateTransitionReviewError, "added_latest_snapshot_ids"):
            render_control_plane_runtime_state_transition_review_json(forged_ids)

    def test_package_contains_no_state_store_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_runtime_state_transition_review"
        source_text = "\n".join(path.read_text(encoding="utf-8").lower() for path in sorted(package_root.glob("*.py")))

        forbidden_fragments = (
            "core.",
            "cli.",
            "extensions.",
            "read_text",
            "write_text",
            ".cerebro",
            "docs/operations",
            "state.json",
            "subprocess",
            "import requests",
            "temporalio",
            "langgraph",
            "opentelemetry",
        )
        for fragment in forbidden_fragments:
            self.assertNotIn(fragment, source_text)


if __name__ == "__main__":
    unittest.main()
