from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_action_review import build_control_plane_action_review_bundle
from experiments.control_plane_boundary_audit import audit_control_plane_boundary_tree
from experiments.control_plane_decision_version_review import (
    ControlPlaneDecisionVersionReviewError,
    build_control_plane_decision_version_review,
    render_control_plane_decision_version_review_json,
    render_control_plane_decision_version_review_markdown,
)
from experiments.control_plane_handoff_review import build_control_plane_handoff_review
from experiments.control_plane_observation_set_review import build_control_plane_observation_set_review
from experiments.control_plane_observation_transition_review import build_control_plane_observation_transition_review


REPO_ROOT = Path(__file__).resolve().parents[3]
REVIEW_AS_OF = "2026-05-08"


def _observation(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "id": "third-party-pilot-cycle-1",
        "title": "Third-party project pilot cycle 1",
        "status": "waiting",
        "kind": "checkpoint",
        "priority": "high",
        "boundary": "target-local rpg_caminhada/.cerebro only after human go",
        "trigger": "FORMAL_RESUME_TRIGGER_THIRD_PARTY_PILOT.md",
        "dependencies": ["claude-third-party-recon", "human-target-selection"],
        "dependencies_satisfied": False,
        "auto_continuation": False,
        "next_action": "Open formal intake session in rpg_caminhada/.cerebro/ with boundary enforced.",
        "halt_if": "Any rpg_caminhada trigger or doc is written to Cerebro repo.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _center(observations: list[dict[str, object]] | None = None) -> dict[str, object]:
    return {
        "queue_authority": "machine-primary",
        "selection_order": "status=open first, then priority, then the current checked-in order",
        "single_flight": True,
        "overlap_policy": "wait",
        "observations": observations if observations is not None else [_observation()],
    }


def _handoff(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "handoff_id": "handoff-1",
        "source_role": "Researcher",
        "target_role": "HumanOperator",
        "observation_id": "third-party-pilot-cycle-1",
        "handoff_status": "context_only",
        "claimed_next_posture": "no_action",
        "claimed_transition_status": "not_evaluated",
        "required_human_decision": "legacy-state-and-source-set",
        "auto_continue": False,
        "referenced_evidence_ids": ["decision-current"],
        "summary": "Context handoff only; blocked checkpoint remains blocked.",
        "stop_condition": "Stop until the target-local human checkpoint is satisfied.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _decision(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "decision_id": "decision-current",
        "decision_thread_id": "third-party-intake-decision",
        "observation_id": "third-party-pilot-cycle-1",
        "revision": 1,
        "decision_kind": "blocker",
        "status": "current",
        "decided_by": "HumanOperator",
        "decided_at": "2026-05-08",
        "valid_until": "",
        "supersedes_decision_id": "",
        "human_decision_id": "none",
        "referenced_evidence_ids": ["operator-note-1"],
        "auto_continue": False,
        "summary": "Keep the target-local intake blocked until legacy-state and source-set decisions exist.",
        "rationale": "This records advisory blocked context only.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneDecisionVersionReviewTests(unittest.TestCase):
    def test_current_blocked_decision_context_is_observed_without_permission(self) -> None:
        center = _center()
        handoff_review = build_control_plane_handoff_review(
            _handoff(),
            observation_set_review=build_control_plane_observation_set_review(center),
            transition_review=build_control_plane_observation_transition_review(center, center),
        )

        review = build_control_plane_decision_version_review(
            [_decision()],
            review_as_of=REVIEW_AS_OF,
            handoff_review=handoff_review,
        )

        self.assertEqual("decision_version_contract_observed", review.review_status)
        self.assertEqual(("decision-current",), review.current_decision_ids)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.decision_review_is_not_permission)
        self.assertTrue(review.decision_current_is_not_execution_approval)
        self.assertTrue(review.decision_record_is_not_truth)

    def test_rejects_duplicate_and_path_unsafe_decision_identity(self) -> None:
        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "duplicate decision ids"):
            build_control_plane_decision_version_review(
                [_decision(), _decision()],
                review_as_of=REVIEW_AS_OF,
            )

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "path-segment safe"):
            build_control_plane_decision_version_review(
                [_decision({"decision_id": "../escape"})],
                review_as_of=REVIEW_AS_OF,
            )

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "duplicate decision thread revisions"):
            build_control_plane_decision_version_review(
                [
                    _decision({"decision_id": "decision-a"}),
                    _decision({"decision_id": "decision-b"}),
                ],
                review_as_of=REVIEW_AS_OF,
            )

    def test_revision_gap_and_unknown_supersedes_are_high_drift(self) -> None:
        review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-r1", "revision": 1, "status": "superseded"}),
                _decision(
                    {
                        "decision_id": "decision-r3",
                        "revision": 3,
                        "supersedes_decision_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertEqual("decision_version_drift_observed", review.review_status)
        self.assertIn("decision_revision_gap", review.finding_codes)
        self.assertIn("decision_supersedes_unknown_id", review.finding_codes)

    def test_multiple_current_and_non_latest_current_are_high_drift(self) -> None:
        review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-r1", "revision": 1, "status": "current"}),
                _decision({"decision_id": "decision-r2", "revision": 2, "status": "current", "supersedes_decision_id": "decision-r1"}),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("multiple_current_decisions_in_thread", review.finding_codes)
        self.assertIn("current_decision_not_latest_revision", review.finding_codes)

    def test_revision_greater_than_one_without_supersedes_requires_review(self) -> None:
        review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-r1", "revision": 1, "status": "superseded"}),
                _decision({"decision_id": "decision-r2", "revision": 2, "status": "current"}),
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertEqual("decision_version_review_required", review.review_status)
        self.assertIn("decision_revision_missing_supersedes", review.finding_codes)

    def test_current_expired_decision_and_missing_human_decision_are_high_drift(self) -> None:
        review = build_control_plane_decision_version_review(
            [
                _decision(
                    {
                        "decision_kind": "approval",
                        "valid_until": "2026-05-07",
                        "human_decision_id": "none",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("current_decision_expired", review.finding_codes)
        self.assertIn("current_decision_missing_human_decision", review.finding_codes)

    def test_auto_continue_and_authority_text_are_high_drift(self) -> None:
        review = build_control_plane_decision_version_review(
            [
                _decision(
                    {
                        "auto_continue": True,
                        "summary": "This decision grants permission to execute and schedules work.",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
        )

        self.assertIn("decision_requests_auto_continue", review.finding_codes)
        self.assertIn("decision_text_launders_authority", review.finding_codes)

    def test_handoff_referencing_non_current_decision_is_high_drift(self) -> None:
        center = _center()
        handoff_review = build_control_plane_handoff_review(
            _handoff(
                {
                    "handoff_status": "ready_for_review",
                    "claimed_next_posture": "advisory_review_only",
                    "referenced_evidence_ids": ["decision-old"],
                }
            ),
            observation_set_review=build_control_plane_observation_set_review(center),
        )

        review = build_control_plane_decision_version_review(
            [
                _decision({"decision_id": "decision-old", "revision": 1, "status": "superseded"}),
                _decision({"decision_id": "decision-current", "revision": 2, "supersedes_decision_id": "decision-old"}),
            ],
            review_as_of=REVIEW_AS_OF,
            handoff_review=handoff_review,
        )

        self.assertIn("handoff_references_non_current_decision", review.finding_codes)
        self.assertIn("handoff_missing_current_decision_reference", review.finding_codes)

    def test_action_required_human_decision_without_current_decision_is_high_drift(self) -> None:
        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=boundary_audit)

        review = build_control_plane_decision_version_review(
            [_decision({"status": "superseded"})],
            review_as_of=REVIEW_AS_OF,
            action_review_bundles=(bundle,),
        )

        self.assertIn("action_required_human_decision_unresolved", review.finding_codes)

    def test_transition_or_handoff_drift_blocks_current_approval(self) -> None:
        before = _center()
        after = _center(
            [
                _observation(
                    {
                        "status": "open",
                        "kind": "slice",
                        "dependencies": [],
                        "dependencies_satisfied": True,
                    }
                )
            ]
        )
        transition_review = build_control_plane_observation_transition_review(before, after)
        set_review = build_control_plane_observation_set_review(after)
        handoff_review = build_control_plane_handoff_review(
            _handoff({"handoff_status": "claimed_ready", "claimed_next_posture": "implementation_ready"}),
            observation_set_review=set_review,
        )

        review = build_control_plane_decision_version_review(
            [
                _decision(
                    {
                        "decision_kind": "approval",
                        "human_decision_id": "human-approval-1",
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            handoff_review=handoff_review,
            transition_review=transition_review,
        )

        self.assertIn("current_approval_over_handoff_drift", review.finding_codes)
        self.assertIn("current_approval_over_transition_drift", review.finding_codes)

    def test_rejects_guardrail_drift_on_supplied_reviews_and_bundles(self) -> None:
        center = _center()
        handoff_review = build_control_plane_handoff_review(
            _handoff(),
            observation_set_review=build_control_plane_observation_set_review(center),
        )
        bad_handoff = replace(handoff_review, authority="non-authoritative; scheduler chooses work")

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "forbidden claim"):
            build_control_plane_decision_version_review(
                [_decision()],
                review_as_of=REVIEW_AS_OF,
                handoff_review=bad_handoff,
            )

        transition_review = build_control_plane_observation_transition_review(center, center)
        bad_transition = replace(transition_review, must_not_execute_automatically=False)
        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "guardrails"):
            build_control_plane_decision_version_review(
                [_decision()],
                review_as_of=REVIEW_AS_OF,
                transition_review=bad_transition,
            )

        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=boundary_audit)
        bad_bundle = replace(bundle, authority="non-authoritative; permission to execute")
        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "forbidden claim"):
            build_control_plane_decision_version_review(
                [_decision()],
                review_as_of=REVIEW_AS_OF,
                action_review_bundles=(bad_bundle,),
            )

    def test_renderers_reject_forged_summary_fields(self) -> None:
        review = build_control_plane_decision_version_review([_decision()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "decision_count"):
            render_control_plane_decision_version_review_json(replace(review, decision_count=99))

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "finding_codes"):
            render_control_plane_decision_version_review_markdown(replace(review, finding_codes=("ghost",)))

        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "referenced_evidence_count"):
            render_control_plane_decision_version_review_json(replace(review, referenced_evidence_count=99))

        drift_review = build_control_plane_decision_version_review(
            [_decision({"auto_continue": True})],
            review_as_of=REVIEW_AS_OF,
        )
        with self.assertRaisesRegex(ControlPlaneDecisionVersionReviewError, "review_status"):
            render_control_plane_decision_version_review_markdown(
                replace(drift_review, review_status="decision_version_contract_observed")
            )

    def test_renderers_preserve_non_authority_markers(self) -> None:
        review = build_control_plane_decision_version_review([_decision()], review_as_of=REVIEW_AS_OF)

        payload = json.loads(render_control_plane_decision_version_review_json(review))
        markdown = render_control_plane_decision_version_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])
        self.assertIn("decision_review_is_not_permission", markdown)
        self.assertIn("decision_current_is_not_execution_approval", markdown)
        self.assertIn("decision_record_is_not_truth", markdown)
        self.assertIn("must_not_execute_automatically", markdown)


if __name__ == "__main__":
    unittest.main()
