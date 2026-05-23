from __future__ import annotations

import json
import tomllib
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_action_review import (
    ControlPlaneActionReviewError,
    build_control_plane_action_review_bundle,
    render_control_plane_action_review_bundle_json,
    render_control_plane_action_review_bundle_markdown,
)
from experiments.control_plane_boundary_audit import (
    ControlPlaneBoundaryAuditFinding,
    ControlPlaneBoundaryAuditReport,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


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
        audited_packages=("control_plane_action_review",),
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


def _advisory_capability(request_id: str = "req-clean") -> CapabilityAssessment:
    return CapabilityAssessment(
        request_id=request_id,
        matched_rule_id="clean",
        decision="advisory_allow",
        reasons=("capability_request_within_declared_policy",),
        warnings=("advisory_allow_is_not_permission",),
        required_human_decision="none",
    )


class ControlPlaneActionReviewTests(unittest.TestCase):
    def test_waiting_checkpoint_with_unsatisfied_dependencies_stays_blocked(self) -> None:
        # third-party-pilot-cycle-1 was resolved; use the same payload via the synthetic helper
        bundle = build_control_plane_action_review_bundle(
            _observation(),
            boundary_audit=_clean_boundary_report(),
        )

        self.assertEqual("waiting_checkpoint_blocked", bundle.action_posture)
        self.assertEqual("packet_blocked", bundle.packet_verdict)
        self.assertEqual("blocked_review", bundle.combined_review_status)
        self.assertEqual("satisfy_checkpoint_dependencies", bundle.recommended_human_decision)
        self.assertIn("observation_status_waiting", bundle.blockers)
        self.assertIn("claude-third-party-recon", bundle.missing_evidence)
        self.assertEqual("guardrails_preserved", bundle.guardrail_status)
        self.assertEqual("lineage_invariants_preserved", bundle.lineage_status)
        self.assertEqual("control_plane_integrity_preserved", bundle.integrity_status)
        self.assertTrue(bundle.bundle_is_not_permission)
        self.assertTrue(bundle.action_posture_is_not_execution_approval)

    def test_markdown_sounding_next_action_cannot_override_machine_status(self) -> None:
        bundle = build_control_plane_action_review_bundle(
            _observation({"next_action": "Run the target mutation now"}),
            boundary_audit=_clean_boundary_report(),
        )

        self.assertEqual("waiting_checkpoint_blocked", bundle.action_posture)
        self.assertIn("observation_status_waiting", bundle.blockers)

    def test_open_observation_with_review_required_capability_needs_human_review(self) -> None:
        capability = CapabilityAssessment(
            request_id="req-network",
            matched_rule_id="network-review",
            decision="review_required",
            reasons=("network_access_requires_review",),
            warnings=(),
            required_human_decision="review_network_use",
        )

        bundle = build_control_plane_action_review_bundle(
            _observation(
                {
                    "id": "open-slice",
                    "status": "open",
                    "kind": "slice",
                    "dependencies_satisfied": True,
                    "dependencies": [],
                }
            ),
            boundary_audit=_clean_boundary_report(),
            capability_assessments=(capability,),
        )

        self.assertEqual("human_review_required", bundle.action_posture)
        self.assertEqual("packet_human_review_required", bundle.packet_verdict)
        self.assertEqual(("req-network:review_required",), bundle.capability_decisions)
        self.assertEqual("review_network_use", bundle.recommended_human_decision)

    def test_blocked_capability_and_boundary_drift_are_visible(self) -> None:
        capability = CapabilityAssessment(
            request_id="req-cerebro-write",
            matched_rule_id="write-policy",
            decision="blocked",
            reasons=("cerebro_write_requires_runtime_authority",),
            warnings=(),
            required_human_decision="open_runtime_authority_trigger",
        )
        boundary = replace(
            _clean_boundary_report(),
            audit_status="boundary_drift_observed",
            finding_count=1,
            severity_counts={"high": 1},
            package_counts={"control_plane_action_review": 1},
            finding_codes=("forbidden_runtime_surface_import",),
            findings=(
                ControlPlaneBoundaryAuditFinding(
                    code="forbidden_runtime_surface_import",
                    severity="high",
                    package_name="control_plane_action_review",
                    relative_path="bundle.py",
                    detail="cli.main",
                ),
            ),
        )

        bundle = build_control_plane_action_review_bundle(
            _observation({"id": "blocked-slice", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
            boundary_audit=boundary,
            capability_assessments=(capability,),
        )

        self.assertEqual("blocked_by_integrity_drift", bundle.action_posture)
        self.assertIn("capability:req-cerebro-write:cerebro_write_requires_runtime_authority", bundle.blockers)
        self.assertEqual("control_plane_integrity_drift_observed", bundle.integrity_status)

    def test_boundary_drift_blocks_otherwise_advisory_observation(self) -> None:
        boundary = replace(
            _clean_boundary_report(),
            audit_status="boundary_drift_observed",
            finding_count=1,
            severity_counts={"high": 1},
            package_counts={"control_plane_action_review": 1},
            finding_codes=("permission_laundering_text",),
            findings=(
                ControlPlaneBoundaryAuditFinding(
                    code="permission_laundering_text",
                    severity="high",
                    package_name="control_plane_action_review",
                    relative_path="README.md",
                    detail="permission marker appeared without local negation",
                ),
            ),
        )

        bundle = build_control_plane_action_review_bundle(
            _observation({"id": "open-drift", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
            boundary_audit=boundary,
            capability_assessments=(_advisory_capability(),),
        )

        self.assertEqual("blocked_by_integrity_drift", bundle.action_posture)
        self.assertEqual("packet_advisory_review_only", bundle.packet_verdict)
        self.assertEqual("control_plane_integrity_drift_observed", bundle.integrity_status)

    def test_unsatisfied_dependencies_are_missing_evidence_for_any_observation_kind(self) -> None:
        bundle = build_control_plane_action_review_bundle(
            _observation(
                {
                    "id": "open-missing-deps",
                    "status": "open",
                    "kind": "slice",
                    "dependencies": ["human-source-set"],
                    "dependencies_satisfied": False,
                }
            ),
            boundary_audit=_clean_boundary_report(),
        )

        self.assertEqual("blocked_by_review", bundle.action_posture)
        self.assertIn("observation_dependencies_unsatisfied", bundle.blockers)
        self.assertEqual(("human-source-set",), bundle.missing_evidence)

    def test_rejects_capability_assessment_guardrail_drift(self) -> None:
        capability = CapabilityAssessment(
            request_id="req-unsafe",
            matched_rule_id="unsafe",
            decision="advisory_allow",
            reasons=("capability_request_within_declared_policy",),
            warnings=("advisory_allow_is_not_permission",),
            required_human_decision="none",
            advisory_allow_is_not_permission=False,
        )

        with self.assertRaisesRegex(ControlPlaneActionReviewError, "guardrails"):
            build_control_plane_action_review_bundle(
                _observation({"id": "open-unsafe-capability", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
                boundary_audit=_clean_boundary_report(),
                capability_assessments=(capability,),
            )

    def test_rejects_unknown_capability_decision(self) -> None:
        capability = CapabilityAssessment(
            request_id="req-unknown",
            matched_rule_id="unknown",
            decision="allow",
            reasons=("legacy_allow_token",),
            warnings=(),
            required_human_decision="none",
        )

        with self.assertRaisesRegex(ControlPlaneActionReviewError, "unknown capability decision"):
            build_control_plane_action_review_bundle(
                _observation({"id": "open-unknown-capability", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
                boundary_audit=_clean_boundary_report(),
                capability_assessments=(capability,),
            )

    def test_auto_continuation_blocks_even_when_observation_is_open(self) -> None:
        bundle = build_control_plane_action_review_bundle(
            _observation(
                {
                    "id": "open-auto",
                    "status": "open",
                    "kind": "slice",
                    "dependencies_satisfied": True,
                    "dependencies": [],
                    "auto_continuation": True,
                }
            ),
            boundary_audit=_clean_boundary_report(),
            capability_assessments=(_advisory_capability(),),
        )

        self.assertEqual("blocked_by_review", bundle.action_posture)
        self.assertIn("auto_continuation_requested", bundle.blockers)
        self.assertEqual("disable_auto_continuation", bundle.recommended_human_decision)

    def test_renderer_rejects_matrix_and_telemetry_from_different_bundle(self) -> None:
        bundle_a = build_control_plane_action_review_bundle(
            _observation({"id": "open-a", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
            boundary_audit=_clean_boundary_report(),
            capability_assessments=(_advisory_capability("req-a"),),
        )
        bundle_b = build_control_plane_action_review_bundle(
            _observation({"id": "open-b", "status": "open", "kind": "slice", "dependencies_satisfied": True, "dependencies": []}),
            boundary_audit=_clean_boundary_report(),
            capability_assessments=(_advisory_capability("req-b"),),
        )

        with self.assertRaisesRegex(ControlPlaneActionReviewError, "matrix row trace id"):
            render_control_plane_action_review_bundle_json(replace(bundle_a, matrix=bundle_b.matrix))
        with self.assertRaisesRegex(ControlPlaneActionReviewError, "telemetry projection"):
            render_control_plane_action_review_bundle_json(replace(bundle_a, telemetry_projection=bundle_b.telemetry_projection))

    def test_replay_digest_is_deterministic_for_same_inputs(self) -> None:
        first = build_control_plane_action_review_bundle(_observation(), boundary_audit=_clean_boundary_report())
        second = build_control_plane_action_review_bundle(_observation(), boundary_audit=_clean_boundary_report())

        self.assertEqual(first.replay_digest, second.replay_digest)

    def test_rejects_malformed_observation_and_authority_drift(self) -> None:
        with self.assertRaisesRegex(ControlPlaneActionReviewError, "path-segment"):
            build_control_plane_action_review_bundle(
                _observation({"id": "../escape"}),
                boundary_audit=_clean_boundary_report(),
            )
        with self.assertRaisesRegex(ControlPlaneActionReviewError, "boolean"):
            build_control_plane_action_review_bundle(
                _observation({"dependencies_satisfied": "false"}),
                boundary_audit=_clean_boundary_report(),
            )
        with self.assertRaisesRegex(ControlPlaneActionReviewError, "mapping"):
            build_control_plane_action_review_bundle(
                ["not", "a", "mapping"],  # type: ignore[arg-type]
                boundary_audit=_clean_boundary_report(),
            )
        with self.assertRaisesRegex(ControlPlaneActionReviewError, "non-authoritative"):
            build_control_plane_action_review_bundle(
                _observation(),
                boundary_audit=replace(_clean_boundary_report(), authority="runtime authority"),
            )

    def test_renderers_preserve_non_authority_markers(self) -> None:
        bundle = build_control_plane_action_review_bundle(_observation(), boundary_audit=_clean_boundary_report())

        payload = json.loads(render_control_plane_action_review_bundle_json(bundle))
        markdown = render_control_plane_action_review_bundle_markdown(bundle)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["bundle_is_not_permission"])
        self.assertTrue(payload["action_posture_is_not_execution_approval"])
        self.assertTrue(payload["replay_pass_is_not_truth"])
        self.assertIn("bundle_is_not_permission: true", markdown)
        self.assertIn("action_posture_is_not_execution_approval: true", markdown)

    def test_package_has_no_io_cli_runtime_or_opentelemetry_imports(self) -> None:
        package_root = Path(__file__).resolve().parents[1]
        python_text = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py"))

        self.assertNotIn("import opentelemetry", python_text)
        self.assertNotIn("from opentelemetry", python_text)
        self.assertNotIn("subprocess", python_text)
        self.assertNotIn("write_text", python_text)
        self.assertNotIn("open(", python_text)


if __name__ == "__main__":
    unittest.main()
