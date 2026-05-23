from __future__ import annotations

import json
import unittest
from dataclasses import replace

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_action_review import (
    build_control_plane_action_review_bundle,
)
from experiments.control_plane_boundary_audit import ControlPlaneBoundaryAuditReport
from experiments.control_plane_observation_set_review import (
    ControlPlaneObservationSetReviewError,
    build_control_plane_observation_set_review,
    render_control_plane_observation_set_review_json,
    render_control_plane_observation_set_review_markdown,
)


def _clean_boundary_report() -> ControlPlaneBoundaryAuditReport:
    return ControlPlaneBoundaryAuditReport(
        schema_version="1",
        audit_role="audits_control_plane_experiment_boundary_drift",
        package_count=1,
        source_count=3,
        audit_status="boundary_markers_preserved",
        finding_count=0,
        severity_counts={},
        package_counts={},
        finding_codes=(),
        findings=(),
        audited_packages=("control_plane_observation_set_review",),
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


def _bundle(observation: dict[str, object], capability: CapabilityAssessment | None = None):
    capabilities = (capability,) if capability is not None else ()
    return build_control_plane_action_review_bundle(
        observation,
        boundary_audit=_clean_boundary_report(),
        capability_assessments=capabilities,
    )


def _advisory_capability(request_id: str = "req-clean") -> CapabilityAssessment:
    return CapabilityAssessment(
        request_id=request_id,
        matched_rule_id="clean",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


class ControlPlaneObservationSetReviewTests(unittest.TestCase):
    def test_waiting_observation_with_unsatisfied_deps_is_coherent_but_not_permission(self) -> None:
        obs = _observation()
        center = _center([obs])
        bundle = _bundle(obs)

        review = build_control_plane_observation_set_review(
            center,
            action_review_bundles=(bundle,),
            focus_observation_id="third-party-pilot-cycle-1",
        )

        self.assertEqual("observation_set_contract_observed", review.review_status)
        self.assertEqual(1, review.observation_count)
        self.assertEqual(0, review.open_ready_count)
        self.assertEqual(("third-party-pilot-cycle-1",), review.observation_ids)
        self.assertEqual((), review.observed_open_ready_frontier_ids)
        self.assertEqual(("third-party-pilot-cycle-1",), review.bundled_observation_ids)
        self.assertEqual(0, review.finding_count)
        self.assertTrue(review.review_is_not_permission)
        self.assertTrue(review.observation_frontier_is_not_scheduler)

    def test_open_ready_frontier_uses_open_first_then_priority_without_scheduling(self) -> None:
        waiting_high = _observation({"id": "waiting-high", "status": "waiting", "priority": "high"})
        open_low = _observation({"id": "open-low", "status": "open", "kind": "slice", "priority": "low", "dependencies": [], "dependencies_satisfied": True})
        open_high = _observation({"id": "open-high", "status": "open", "kind": "slice", "priority": "high", "dependencies": [], "dependencies_satisfied": True})

        review = build_control_plane_observation_set_review(_center([waiting_high, open_low, open_high]), focus_observation_id="open-high")

        self.assertEqual("observation_set_contract_observed", review.review_status)
        self.assertEqual(2, review.open_ready_count)
        self.assertEqual(("open-high",), review.observed_open_ready_frontier_ids)
        self.assertTrue(review.observation_frontier_is_not_scheduler)

    def test_rejects_duplicate_and_path_unsafe_observation_ids(self) -> None:
        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "duplicate observation ids"):
            build_control_plane_observation_set_review(_center([_observation({"id": "dup"}), _observation({"id": "dup"})]))

        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "path-segment safe"):
            build_control_plane_observation_set_review(_center([_observation({"id": "../escape"})]))

    def test_auto_continuation_and_resolved_live_items_are_findings(self) -> None:
        review = build_control_plane_observation_set_review(
            _center(
                [
                    _observation({"id": "auto-open", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True, "auto_continuation": True}),
                    _observation({"id": "resolved-live", "status": "resolved", "kind": "slice", "dependencies": [], "dependencies_satisfied": True}),
                ]
            )
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("auto_continuation_requested", review.finding_codes)
        self.assertIn("resolved_observation_still_live", review.finding_codes)

    def test_open_observation_with_unsatisfied_dependencies_or_closed_trigger_is_visible(self) -> None:
        review = build_control_plane_observation_set_review(
            _center(
                [
                    _observation({"id": "open-missing", "status": "open", "kind": "slice", "dependencies": ["human"], "dependencies_satisfied": False}),
                    _observation({"id": "open-trigger-closed", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True, "trigger": "not open"}),
                ]
            )
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("open_observation_dependencies_unsatisfied", review.finding_codes)
        self.assertIn("open_observation_trigger_not_open", review.finding_codes)

    def test_bundle_not_in_snapshot_and_focus_mismatch_are_findings(self) -> None:
        open_a = _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        open_b = _observation({"id": "open-b", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        orphan = _observation({"id": "orphan", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})

        review = build_control_plane_observation_set_review(
            _center([open_a, open_b]),
            action_review_bundles=(_bundle(orphan),),
            focus_observation_id="missing-focus",
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("bundle_observation_not_in_snapshot", review.finding_codes)
        self.assertIn("focus_observation_not_in_snapshot", review.finding_codes)
        self.assertIn("focus_observation_not_bundled", review.finding_codes)
        self.assertIn("focus_outside_open_ready_frontier", review.finding_codes)

    def test_bundle_snapshot_drift_is_detected(self) -> None:
        snapshot = _observation({"id": "open-drift", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        bundle = _bundle(snapshot)
        drifted = replace(bundle, observation=replace(bundle.observation, status="waiting", dependencies_satisfied=False, auto_continuation=True))

        review = build_control_plane_observation_set_review(
            _center([snapshot]),
            action_review_bundles=(drifted,),
            focus_observation_id="open-drift",
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("bundle_status_drift", review.finding_codes)
        self.assertIn("bundle_dependency_status_drift", review.finding_codes)
        self.assertIn("bundle_auto_continuation_drift", review.finding_codes)

    def test_bundle_payload_drift_is_detected_for_all_contract_fields(self) -> None:
        snapshot = _observation({"id": "open-payload", "status": "open", "kind": "slice", "dependencies": ["same"], "dependencies_satisfied": True})
        bundled = {
            **snapshot,
            "title": "Changed title",
            "kind": "checkpoint",
            "priority": "low",
            "boundary": "changed boundary",
            "trigger": "not open",
            "dependencies": ["different"],
            "next_action": "changed next action",
            "halt_if": "changed halt",
        }

        review = build_control_plane_observation_set_review(
            _center([snapshot]),
            action_review_bundles=(_bundle(bundled),),
            focus_observation_id="open-payload",
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("bundle_observation_payload_drift", review.finding_codes)
        payload_finding = next(finding for finding in review.findings if finding.code == "bundle_observation_payload_drift")
        self.assertIn("boundary", payload_finding.detail)
        self.assertIn("trigger", payload_finding.detail)
        self.assertIn("dependencies", payload_finding.detail)

    def test_multiple_advisory_bundles_under_single_flight_require_review(self) -> None:
        open_a = _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        open_b = _observation({"id": "open-b", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})

        review = build_control_plane_observation_set_review(
            _center([open_a, open_b]),
            action_review_bundles=(_bundle(open_a, _advisory_capability("req-a")), _bundle(open_b, _advisory_capability("req-b"))),
            focus_observation_id="open-a",
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("multiple_advisory_bundles_under_single_flight", review.finding_codes)

    def test_rejects_action_bundle_guardrail_drift(self) -> None:
        open_item = _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        bundle = replace(_bundle(open_item), bundle_is_not_permission=False)

        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "guardrails"):
            build_control_plane_observation_set_review(
                _center([open_item]),
                action_review_bundles=(bundle,),
                focus_observation_id="open-a",
            )

    def test_rejects_authority_laundering_on_review_and_bundle(self) -> None:
        open_item = _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies": [], "dependencies_satisfied": True})
        bundle = replace(_bundle(open_item), authority="non-authoritative; grants permission to execute")

        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "forbidden claim"):
            build_control_plane_observation_set_review(
                _center([open_item]),
                action_review_bundles=(bundle,),
                focus_observation_id="open-a",
            )

        review = build_control_plane_observation_set_review(_center())
        laundered = replace(review, authority="non-authoritative; schedules work as runtime authority")
        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "forbidden claim"):
            render_control_plane_observation_set_review_json(laundered)

    def test_rejects_forged_summary_counts_and_identity_lists(self) -> None:
        review = build_control_plane_observation_set_review(_center())

        forged_observation_count = replace(review, observation_count=999)
        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "observation_count"):
            render_control_plane_observation_set_review_json(forged_observation_count)

        forged_bundle_count = replace(review, bundle_count=1)
        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "bundle_count"):
            render_control_plane_observation_set_review_json(forged_bundle_count)

        forged_frontier = replace(review, open_ready_observation_ids=(), observed_open_ready_frontier_ids=("ghost",))
        with self.assertRaisesRegex(ControlPlaneObservationSetReviewError, "frontier ids"):
            render_control_plane_observation_set_review_markdown(forged_frontier)

    def test_queue_contract_drift_is_reported_without_reading_files(self) -> None:
        review = build_control_plane_observation_set_review(
            _center(overrides={"queue_authority": "markdown-primary", "single_flight": False, "overlap_policy": "parallel"})
        )

        self.assertEqual("observation_set_contract_drift_observed", review.review_status)
        self.assertIn("queue_authority_not_machine_primary", review.finding_codes)
        self.assertIn("single_flight_not_enabled", review.finding_codes)
        self.assertIn("overlap_policy_not_wait", review.finding_codes)

    def test_renderers_preserve_non_authority_markers(self) -> None:
        review = build_control_plane_observation_set_review(_center())

        payload = json.loads(render_control_plane_observation_set_review_json(review))
        markdown = render_control_plane_observation_set_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])
        self.assertIn("review_is_not_permission", markdown)
        self.assertIn("observation_frontier_is_not_scheduler", markdown)
        self.assertIn("must_not_execute_automatically", markdown)


if __name__ == "__main__":
    unittest.main()
