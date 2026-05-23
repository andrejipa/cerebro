from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.control_plane_observation_set_review import build_control_plane_observation_set_review
from experiments.control_plane_observation_transition_review import (
    ControlPlaneObservationTransitionReviewError,
    build_control_plane_observation_transition_review,
    render_control_plane_observation_transition_review_json,
    render_control_plane_observation_transition_review_markdown,
)


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


def _evidence(
    observation_id: str,
    evidence_kind: str,
    evidence_id: str = "ev-1",
    human_decision: str = "human-reviewed",
) -> dict[str, object]:
    return {
        "observation_id": observation_id,
        "evidence_id": evidence_id,
        "evidence_kind": evidence_kind,
        "human_decision": human_decision,
        "detail": "caller supplied transition evidence",
    }


class ControlPlaneObservationTransitionReviewTests(unittest.TestCase):
    def test_waiting_observation_with_unsatisfied_deps_snapshot_stability_is_observed_without_permission(self) -> None:
        center = _center()

        review = build_control_plane_observation_transition_review(center, center)

        self.assertEqual("observation_transition_contract_observed", review.review_status)
        self.assertEqual(("third-party-pilot-cycle-1",), review.before_observation_ids)
        self.assertEqual((), review.added_observation_ids)
        self.assertEqual((), review.removed_observation_ids)
        self.assertEqual((), review.transitioned_observation_ids)
        self.assertEqual((), review.after_open_ready_observation_ids)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.transition_review_is_not_permission)
        self.assertTrue(review.observed_transition_is_not_truth)

    def test_silent_waiting_to_open_ready_promotion_is_high_drift(self) -> None:
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

        review = build_control_plane_observation_transition_review(before, after)

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertIn("silent_dependency_satisfaction", review.finding_codes)
        self.assertIn("silent_readiness_promotion", review.finding_codes)
        self.assertEqual(("third-party-pilot-cycle-1",), review.after_open_ready_observation_ids)

    def test_transition_evidence_accounts_for_dependency_satisfaction_and_promotion(self) -> None:
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

        review = build_control_plane_observation_transition_review(
            before,
            after,
            transition_evidence=(
                _evidence("third-party-pilot-cycle-1", "dependency_satisfaction", "ev-deps"),
                _evidence("third-party-pilot-cycle-1", "human_checkpoint", "ev-human"),
            ),
        )

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertNotIn("silent_dependency_satisfaction", review.finding_codes)
        self.assertNotIn("silent_readiness_promotion", review.finding_codes)
        self.assertIn("observation_payload_drift_across_transition", review.finding_codes)

    def test_unresolved_disappearance_and_resolution_without_evidence_are_drift(self) -> None:
        before = _center(
            [
                _observation({"id": "waiting-a"}),
                _observation({"id": "waiting-b"}),
            ]
        )
        after = _center(
            [
                _observation({"id": "waiting-b", "status": "resolved"}),
            ]
        )

        review = build_control_plane_observation_transition_review(before, after)

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertIn("unresolved_observation_disappeared", review.finding_codes)
        self.assertIn("resolved_without_transition_evidence", review.finding_codes)

    def test_resolution_and_removal_evidence_prevent_silent_transition_findings(self) -> None:
        before = _center(
            [
                _observation({"id": "waiting-a"}),
                _observation({"id": "waiting-b"}),
            ]
        )
        after = _center(
            [
                _observation({"id": "waiting-b", "status": "resolved"}),
            ]
        )

        review = build_control_plane_observation_transition_review(
            before,
            after,
            transition_evidence=(
                _evidence("waiting-a", "removal", "ev-remove"),
                _evidence("waiting-b", "resolution", "ev-resolve"),
            ),
        )

        self.assertNotIn("unresolved_observation_disappeared", review.finding_codes)
        self.assertNotIn("resolved_without_transition_evidence", review.finding_codes)

    def test_queue_contract_and_payload_drift_are_reported(self) -> None:
        before = _center()
        after = _center(
            [
                _observation(
                    {
                        "boundary": "changed boundary",
                        "trigger": "changed trigger",
                        "dependencies": ["changed"],
                        "halt_if": "changed halt",
                    }
                )
            ],
            overrides={"single_flight": False, "overlap_policy": "parallel"},
        )

        review = build_control_plane_observation_transition_review(before, after)

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertIn("queue_contract_field_changed", review.finding_codes)
        self.assertIn("observation_payload_drift_across_transition", review.finding_codes)

    def test_new_open_ready_and_multiple_open_ready_under_single_flight_are_drift(self) -> None:
        open_a = _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        open_b = _observation({"id": "open-b", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})

        review = build_control_plane_observation_transition_review(_center([]), _center([open_a, open_b]))

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertIn("new_open_ready_observation_without_evidence", review.finding_codes)
        self.assertIn("multiple_open_ready_after_transition_under_single_flight", review.finding_codes)

    def test_auto_continuation_and_resolved_reopen_are_drift(self) -> None:
        before = _center([_observation({"id": "resolved-a", "status": "resolved"})])
        after = _center([_observation({"id": "resolved-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True, "auto_continuation": True})])

        review = build_control_plane_observation_transition_review(before, after)

        self.assertEqual("observation_transition_drift_observed", review.review_status)
        self.assertIn("auto_continuation_introduced", review.finding_codes)
        self.assertIn("resolved_observation_reopened", review.finding_codes)

    def test_rejects_authority_laundering_and_summary_forgery(self) -> None:
        base = _center()
        before_review = build_control_plane_observation_set_review(base)
        laundered = replace(before_review, authority="non-authoritative; grants permission to execute")

        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "forbidden claim"):
            build_control_plane_observation_transition_review(base, base, before_review=laundered)

        scheduler_laundered = replace(build_control_plane_observation_transition_review(base, base), authority="non-authoritative; scheduler chooses work")
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "forbidden claim"):
            render_control_plane_observation_transition_review_json(scheduler_laundered)

        review = build_control_plane_observation_transition_review(base, base)
        forged_count = replace(review, before_observation_count=999)
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "before_observation_count"):
            render_control_plane_observation_transition_review_json(forged_count)

        forged_finding_codes = replace(review, finding_codes=("ghost",))
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "finding_codes"):
            render_control_plane_observation_transition_review_markdown(forged_finding_codes)

        forged_open_ready = replace(review, after_open_ready_observation_ids=("fake-open",))
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "after_open_ready_observation_ids"):
            render_control_plane_observation_transition_review_json(forged_open_ready)

        forged_shared = replace(review, shared_observation_ids=())
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "shared_observation_ids"):
            render_control_plane_observation_transition_review_markdown(forged_shared)

        forged_transitioned = replace(review, transitioned_observation_ids=("ghost",))
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "transitioned observations"):
            render_control_plane_observation_transition_review_json(forged_transitioned)

    def test_rejects_supplied_set_review_not_derived_from_payload(self) -> None:
        clean = _center()
        bad_contract = _center(overrides={"queue_authority": "human-primary"})
        clean_review = build_control_plane_observation_set_review(clean)

        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "derived from the supplied payload"):
            build_control_plane_observation_transition_review(
                bad_contract,
                clean,
                before_review=clean_review,
            )

    def test_automatic_or_none_transition_evidence_does_not_suppress_silent_promotion(self) -> None:
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

        review = build_control_plane_observation_transition_review(
            before,
            after,
            transition_evidence=(
                _evidence("third-party-pilot-cycle-1", "dependency_satisfaction", "ev-auto", " automatic "),
                _evidence("third-party-pilot-cycle-1", "human_checkpoint", "ev-none", " none "),
            ),
        )

        self.assertIn("silent_dependency_satisfaction", review.finding_codes)
        self.assertIn("silent_readiness_promotion", review.finding_codes)

    def test_rejects_path_unsafe_evidence_and_duplicate_evidence_ids(self) -> None:
        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "path-segment safe"):
            build_control_plane_observation_transition_review(
                _center(),
                _center(),
                transition_evidence=(_evidence("../escape", "removal"),),
            )

        with self.assertRaisesRegex(ControlPlaneObservationTransitionReviewError, "duplicate"):
            build_control_plane_observation_transition_review(
                _center(),
                _center(),
                transition_evidence=(
                    _evidence("third-party-pilot-cycle-1", "removal", "dup"),
                    _evidence("third-party-pilot-cycle-1", "resolution", "dup"),
                ),
            )

    def test_renderers_preserve_non_authority_markers(self) -> None:
        review = build_control_plane_observation_transition_review(_center(), _center())

        payload = json.loads(render_control_plane_observation_transition_review_json(review))
        markdown = render_control_plane_observation_transition_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])
        self.assertIn("transition_review_is_not_permission", markdown)
        self.assertIn("observed_transition_is_not_truth", markdown)
        self.assertIn("observed_frontier_is_not_scheduler", markdown)
        self.assertIn("must_not_execute_automatically", markdown)


if __name__ == "__main__":
    unittest.main()
