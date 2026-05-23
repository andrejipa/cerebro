from __future__ import annotations

import json
import unittest

from experiments.claim_extraction import ClaimCandidate
from experiments.claim_evaluation import evaluate_claims
from experiments.control_plane_assessment import (
    build_control_plane_assessment,
    render_control_plane_assessment_json,
    render_control_plane_assessment_markdown,
)
from experiments.epistemic_guard import (
    ActionProfile,
    DecisionEnvelope,
    EvidenceClaim,
    EvidenceSource,
    DecisionScenario,
    evaluate_decision_scenario,
)


def _runtime(*, current_task_id: str = "task-ready") -> dict:
    return {
        "plan": {
            "status": "ready",
            "current_task_id": current_task_id,
            "tasks": [
                {
                    "id": "task-ready",
                    "title": "Ready task",
                    "status": "ready",
                    "working_set": ["docs/operations/example.md"],
                    "acceptance_criteria": ["report renders"],
                }
            ],
        },
        "actions": [],
        "approvals": {"items": []},
        "verification": {"status": "passed", "pending_action_ids": []},
        "memory": {"notes": []},
    }


def _envelope(readiness: str = "advisory_report_allowed") -> DecisionEnvelope:
    if readiness == "blocked":
        scenario = DecisionScenario(
            scenario_id="runtime-mutation",
            intent="touch runtime without trigger",
            action_profile=ActionProfile(
                zone="runtime",
                reads=("core/action_runtime.py",),
                writes=("core/action_runtime.py",),
                authority_impact="canonical",
                runtime_impact="direct",
                active_trigger=False,
            ),
            sources=(EvidenceSource("source-1", "docs/operations/SYSTEM_STATE.md"),),
            claims=(EvidenceClaim("claim-1", "runtime", "trigger", "missing", "source-1"),),
        )
        return evaluate_decision_scenario(scenario)

    scenario = DecisionScenario(
        scenario_id="advisory-report",
        intent="render advisory report",
        action_profile=ActionProfile(
            zone="derived",
            reads=("docs/operations/SYSTEM_STATE.md",),
            writes=(),
            authority_impact="none",
            runtime_impact="none",
        ),
        sources=(EvidenceSource("source-1", "docs/operations/SYSTEM_STATE.md"),),
        claims=(EvidenceClaim("claim-1", "report", "state_change", "none", "source-1"),),
    )
    return evaluate_decision_scenario(scenario)


class ControlPlaneAssessmentTests(unittest.TestCase):
    def test_ready_task_still_blocks_when_epistemic_guard_blocks(self) -> None:
        assessment = build_control_plane_assessment(_runtime(), envelopes=(_envelope("blocked"),))

        self.assertEqual("task-ready", assessment.selected_task_id)
        self.assertEqual("canonical_change_requires_trigger", assessment.epistemic_action_readiness)
        self.assertIn("missing_active_trigger_for_runtime_or_canonical_change", assessment.blockers)
        self.assertEqual("review_blockers", assessment.recommended_human_decision)
        self.assertTrue(assessment.must_not_execute_automatically)
        self.assertEqual("none", assessment.state_change)

    def test_advisory_allowed_is_not_permission(self) -> None:
        assessment = build_control_plane_assessment(_runtime(), envelopes=(_envelope(),))
        payload = json.loads(render_control_plane_assessment_json(assessment))

        self.assertEqual("advisory_report_allowed", assessment.epistemic_action_readiness)
        self.assertTrue(payload["advisory_pass_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])

    def test_operational_signal_summary_does_not_drive_selection(self) -> None:
        signals = {
            "authority": "derived-observability-only",
            "non_authoritative": True,
            "totals": {"count": 5, "candidate_trigger_count": 5},
        }

        assessment = build_control_plane_assessment(
            _runtime(),
            envelopes=(_envelope(),),
            operational_signals=signals,
        )

        self.assertEqual("task-ready", assessment.selected_task_id)
        self.assertEqual(5, assessment.operational_signal_summary["candidate_trigger_count"])
        self.assertEqual("derived-observability-only", assessment.operational_signal_summary["authority"])
        self.assertTrue(assessment.operational_signal_summary["non_authoritative"])

    def test_claim_evaluation_ready_does_not_create_runtime_authority(self) -> None:
        claim_report = evaluate_claims(
            (
                ClaimCandidate(
                    subject="assessment",
                    predicate="state_change",
                    object="none",
                    polarity="positive",
                    modality="factual",
                    criticality_hint="low",
                    source_path="docs/operations/SYSTEM_STATE.md",
                    evidence_span="state_change none",
                    source_role="primary",
                    authority_hint="source-local",
                    extraction_basis="explicit",
                    claim_id="claim-ready",
                ),
            )
        )

        assessment = build_control_plane_assessment(
            _runtime(),
            envelopes=(_envelope(),),
            claim_evaluation=claim_report,
        )

        self.assertEqual({"ready_count": 1, "blocked_count": 0, "insufficient_count": 0}, assessment.claim_evaluation_summary)
        self.assertIn("non-authoritative", assessment.authority)
        self.assertTrue(assessment.must_not_execute_automatically)

    def test_task_selection_mismatch_becomes_review_blocker(self) -> None:
        assessment = build_control_plane_assessment(_runtime(current_task_id=""), envelopes=(_envelope(),))

        self.assertEqual("mismatch", assessment.task_selection_status)
        self.assertIn("task_selection_inconsistent", assessment.blockers)
        self.assertEqual("review_blockers", assessment.recommended_human_decision)

    def test_markdown_renders_non_authoritative_boundary(self) -> None:
        markdown = render_control_plane_assessment_markdown(
            build_control_plane_assessment(_runtime(), envelopes=(_envelope(),))
        )

        self.assertIn("state_change: none", markdown)
        self.assertIn("authority: non-authoritative; advisory control-plane assessment only", markdown)
        self.assertIn("advisory_pass_is_not_permission: true", markdown)


if __name__ == "__main__":
    unittest.main()
