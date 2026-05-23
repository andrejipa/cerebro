from __future__ import annotations

import json
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.control_plane_action_review import build_control_plane_action_review_bundle
from experiments.control_plane_boundary_audit import audit_control_plane_boundary_tree
from experiments.control_plane_handoff_review import (
    ControlPlaneHandoffReviewError,
    build_control_plane_handoff_review,
    render_control_plane_handoff_review_json,
    render_control_plane_handoff_review_markdown,
)
from experiments.control_plane_observation_set_review import build_control_plane_observation_set_review
from experiments.control_plane_observation_transition_review import build_control_plane_observation_transition_review


REPO_ROOT = Path(__file__).resolve().parents[3]


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


def _center(observations: list[dict[str, object]] | None = None, overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "queue_authority": "machine-primary",
        "selection_order": "status=open first, then priority, then the current checked-in order",
        "single_flight": True,
        "overlap_policy": "wait",
        "observations": observations if observations is not None else [_observation()],
    }
    if overrides:
        payload.update(overrides)
    return payload


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
        "referenced_evidence_ids": ["handoff-note-1"],
        "summary": "Context handoff only; blocked checkpoint remains blocked.",
        "stop_condition": "Stop until the target-local human checkpoint is satisfied.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneHandoffReviewTests(unittest.TestCase):
    def test_context_only_handoff_for_waiting_item_is_observed_without_permission(self) -> None:
        # third-party-pilot-cycle-1 was resolved; use synthetic center/handoff with equivalent payload
        center_payload = _center()
        set_review = build_control_plane_observation_set_review(center_payload)
        transition_review = build_control_plane_observation_transition_review(center_payload, center_payload)

        review = build_control_plane_handoff_review(
            _handoff(),
            observation_set_review=set_review,
            transition_review=transition_review,
        )

        self.assertEqual("handoff_contract_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertEqual((), review.observed_frontier_ids)
        self.assertTrue(review.handoff_review_is_not_permission)
        self.assertTrue(review.handoff_is_not_scheduler)
        self.assertTrue(review.handoff_is_not_execution_approval)

    def test_ready_claim_without_frontier_is_high_drift(self) -> None:
        review = build_control_plane_handoff_review(
            _handoff({"handoff_status": "claimed_ready", "claimed_next_posture": "implementation_ready"}),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )

        self.assertEqual("handoff_drift_observed", review.review_status)
        self.assertIn("handoff_claims_ready_outside_frontier", review.finding_codes)
        self.assertIn("handoff_missing_action_review_bundle", review.finding_codes)

    def test_action_bundle_waiting_posture_blocks_ready_handoff(self) -> None:
        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=boundary_audit)
        set_review = build_control_plane_observation_set_review(_center(), action_review_bundles=(bundle,))

        review = build_control_plane_handoff_review(
            _handoff({"handoff_status": "ready_for_review", "claimed_next_posture": "advisory_review_only"}),
            observation_set_review=set_review,
            action_review_bundles=(bundle,),
        )

        self.assertIn("handoff_conflicts_with_action_posture", review.finding_codes)

    def test_transition_drift_cannot_be_laundered_as_clean_handoff(self) -> None:
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
        set_review = build_control_plane_observation_set_review(after)
        transition_review = build_control_plane_observation_transition_review(before, after)

        review = build_control_plane_handoff_review(
            _handoff(
                {
                    "handoff_status": "claimed_ready",
                    "claimed_next_posture": "implementation_ready",
                    "claimed_transition_status": "clean",
                }
            ),
            observation_set_review=set_review,
            transition_review=transition_review,
        )

        self.assertEqual("handoff_drift_observed", review.review_status)
        self.assertIn("handoff_claims_clean_over_transition_drift", review.finding_codes)

    def test_auto_continue_and_authority_text_are_high_drift(self) -> None:
        review = build_control_plane_handoff_review(
            _handoff(
                {
                    "auto_continue": True,
                    "summary": "This handoff grants permission to execute and schedules work.",
                }
            ),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )

        self.assertIn("handoff_requests_auto_continue", review.finding_codes)
        self.assertIn("handoff_text_launders_authority", review.finding_codes)

    def test_absent_observation_is_reported(self) -> None:
        review = build_control_plane_handoff_review(
            _handoff({"observation_id": "missing-item", "required_human_decision": "none"}),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )

        self.assertIn("handoff_observation_not_in_snapshot", review.finding_codes)

    def test_dropped_human_decision_from_action_bundle_is_reported(self) -> None:
        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=boundary_audit)

        review = build_control_plane_handoff_review(
            _handoff({"required_human_decision": "none"}),
            observation_set_review=build_control_plane_observation_set_review(_center(), action_review_bundles=(bundle,)),
            action_review_bundles=(bundle,),
        )

        self.assertIn("handoff_drops_required_human_decision", review.finding_codes)

    def test_rejects_path_unsafe_ids_and_duplicate_evidence_ids(self) -> None:
        set_review = build_control_plane_observation_set_review(_center())

        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "path-segment safe"):
            build_control_plane_handoff_review(
                _handoff({"handoff_id": "../escape"}),
                observation_set_review=set_review,
            )

        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "duplicate"):
            build_control_plane_handoff_review(
                _handoff({"referenced_evidence_ids": ["ev-1", "ev-1"]}),
                observation_set_review=set_review,
            )

    def test_rejects_guardrail_drift_on_supplied_reviews_and_bundles(self) -> None:
        set_review = build_control_plane_observation_set_review(_center())
        bad_set_review = replace(set_review, authority="non-authoritative; scheduler chooses work")

        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "forbidden claim"):
            build_control_plane_handoff_review(_handoff(), observation_set_review=bad_set_review)

        transition_review = build_control_plane_observation_transition_review(_center(), _center())
        bad_transition = replace(transition_review, must_not_execute_automatically=False)
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "guardrails"):
            build_control_plane_handoff_review(
                _handoff(),
                observation_set_review=set_review,
                transition_review=bad_transition,
            )

        boundary_audit = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=boundary_audit)
        bad_bundle = replace(bundle, authority="non-authoritative; permission to execute")
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "forbidden claim"):
            build_control_plane_handoff_review(
                _handoff(),
                observation_set_review=set_review,
                action_review_bundles=(bad_bundle,),
            )

    def test_renderers_reject_forged_summary_fields(self) -> None:
        review = build_control_plane_handoff_review(
            _handoff(),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )

        forged_count = replace(review, finding_count=99)
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "finding_count"):
            render_control_plane_handoff_review_json(forged_count)

        forged_codes = replace(review, finding_codes=("ghost",))
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "finding_codes"):
            render_control_plane_handoff_review_markdown(forged_codes)

        forged_evidence = replace(review, referenced_evidence_count=99)
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "referenced_evidence_count"):
            render_control_plane_handoff_review_json(forged_evidence)

        drift_review = build_control_plane_handoff_review(
            _handoff({"auto_continue": True}),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )
        forged_status = replace(drift_review, review_status="handoff_contract_observed")
        with self.assertRaisesRegex(ControlPlaneHandoffReviewError, "review_status"):
            render_control_plane_handoff_review_markdown(forged_status)

    def test_renderers_preserve_non_authority_markers(self) -> None:
        review = build_control_plane_handoff_review(
            _handoff(),
            observation_set_review=build_control_plane_observation_set_review(_center()),
        )

        payload = json.loads(render_control_plane_handoff_review_json(review))
        markdown = render_control_plane_handoff_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])
        self.assertIn("handoff_review_is_not_permission", markdown)
        self.assertIn("handoff_is_not_scheduler", markdown)
        self.assertIn("handoff_is_not_execution_approval", markdown)
        self.assertIn("observed_frontier_is_not_scheduler", markdown)
        self.assertIn("must_not_execute_automatically", markdown)


if __name__ == "__main__":
    unittest.main()
