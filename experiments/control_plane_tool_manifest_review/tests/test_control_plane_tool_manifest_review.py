from __future__ import annotations

import json
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.capability_policy import CapabilityRule
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_tool_manifest_review import (
    ControlPlaneToolManifestReviewError,
    build_control_plane_tool_manifest_review,
    render_control_plane_tool_manifest_review_json,
    render_control_plane_tool_manifest_review_markdown,
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


def _capability_rule(rule_id: str = "cap-read") -> CapabilityRule:
    return CapabilityRule(
        rule_id=rule_id,
        decision="allow",
        argv_prefix=("python", "-m", "unittest"),
        path_scope=("experiments",),
        max_data_sensitivity="internal",
        network_access="denied",
        approval_required=False,
        output_budget_kb=64,
        retention="ephemeral",
        rollback_expectation="not_applicable",
        rationale="Advisory test rule only.",
    )


def _tool(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "tool_id": "inspect-source",
        "tool_kind": "analysis",
        "decision": "review_required",
        "risk_level": "medium",
        "path_scope": ["experiments"],
        "max_data_sensitivity": "internal",
        "network_access": False,
        "mutates_files": False,
        "mutates_state": False,
        "destructive": False,
        "requires_human_confirmation": True,
        "captures_sensitive_output": False,
        "timeout_seconds": 30,
        "summary": "Advisory inspection tool entry only.",
    }
    if overrides:
        payload.update(overrides)
    return payload


def _manifest(overrides: dict[str, object] | None = None) -> dict[str, object]:
    payload: dict[str, object] = {
        "manifest_id": "manifest-tools",
        "manifest_thread_id": "tool-manifest",
        "revision": 1,
        "lifecycle_status": "active_candidate",
        "manifest_scope": "local_tools",
        "authority_boundary": "candidate_manifest",
        "supersedes_manifest_id": "",
        "evidence_ids": ["evidence-tool-1"],
        "depends_on_decision_ids": [],
        "referenced_rule_ids": [],
        "capability_rule_ids": ["cap-read"],
        "tools": [_tool()],
        "approval_policy_defined": True,
        "evidence_policy_defined": True,
        "audit_logging_defined": True,
        "rollback_policy_defined": True,
        "timeout_policy_defined": True,
        "rate_limit_policy_defined": True,
        "sandbox_policy_defined": True,
        "secret_handling_defined": True,
        "claims_tool_authority": False,
        "grants_execution_permission": False,
        "registers_tools": False,
        "imports_adapters": False,
        "exposes_mcp_server": False,
        "schedules_tool_calls": False,
        "reads_live_state": False,
        "mutates_state": False,
        "auto_apply": False,
        "contains_secret_material": False,
        "stores_raw_tool_outputs": False,
        "summary": "Candidate manifest for advisory review only.",
        "rationale": "This manifest is non-authoritative and does not grant permission.",
    }
    if overrides:
        payload.update(overrides)
    return payload


class ControlPlaneToolManifestReviewTests(unittest.TestCase):
    def test_clean_manifest_candidate_is_observed_without_permission(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [_manifest()],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
            capability_rules=[_capability_rule()],
        )

        self.assertEqual("tool_manifest_candidate_observed", review.review_status)
        self.assertEqual(0, review.finding_count)
        self.assertEqual(("inspect-source",), review.review_required_tool_ids)
        self.assertTrue(review.tool_manifest_review_is_not_permission)
        self.assertTrue(review.manifest_candidate_is_not_registered_tool_manifest)
        self.assertTrue(review.tool_decision_is_not_execution_approval)
        self.assertTrue(review.tool_manifest_review_is_not_adapter)
        self.assertTrue(review.tool_manifest_review_is_not_scheduler)

    def test_rejects_empty_duplicate_unsafe_unknown_enum_and_bad_date_inputs(self) -> None:
        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "at least one"):
            build_control_plane_tool_manifest_review([], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "duplicate manifest ids"):
            build_control_plane_tool_manifest_review([_manifest(), _manifest()], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "path-segment safe"):
            build_control_plane_tool_manifest_review([_manifest({"manifest_id": "../escape"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "unknown lifecycle_status"):
            build_control_plane_tool_manifest_review([_manifest({"lifecycle_status": "registered"})], review_as_of=REVIEW_AS_OF)

        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "review_as_of must be an ISO date"):
            build_control_plane_tool_manifest_review([_manifest()], review_as_of="today")

        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "tool ids must be unique"):
            build_control_plane_tool_manifest_review([_manifest({"tools": [_tool(), _tool()]})], review_as_of=REVIEW_AS_OF)

    def test_revision_supersession_and_active_drift_are_found(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [
                _manifest({"manifest_id": "manifest-r1", "manifest_thread_id": "thread", "revision": 1}),
                _manifest(
                    {
                        "manifest_id": "manifest-r3",
                        "manifest_thread_id": "thread",
                        "revision": 3,
                        "supersedes_manifest_id": "missing-r2",
                    }
                ),
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
            capability_rules=[_capability_rule()],
        )

        self.assertEqual("tool_manifest_review_blocked", review.review_status)
        self.assertIn("tool_manifest_revision_gap", review.finding_codes)
        self.assertIn("tool_manifest_supersedes_unknown_id", review.finding_codes)
        self.assertIn("multiple_active_tool_manifest_candidates", review.finding_codes)

    def test_manifest_policy_and_boundary_drift_are_blocked(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [
                _manifest(
                    {
                        "evidence_ids": [],
                        "approval_policy_defined": False,
                        "evidence_policy_defined": False,
                        "sandbox_policy_defined": False,
                        "secret_handling_defined": False,
                        "claims_tool_authority": True,
                        "grants_execution_permission": True,
                        "registers_tools": True,
                        "imports_adapters": True,
                        "exposes_mcp_server": True,
                        "schedules_tool_calls": True,
                        "reads_live_state": True,
                        "mutates_state": True,
                        "auto_apply": True,
                        "contains_secret_material": True,
                        "stores_raw_tool_outputs": True,
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
            capability_rules=[_capability_rule()],
        )

        expected = {
            "tool_manifest_missing_evidence",
            "tool_manifest_missing_approval_policy",
            "tool_manifest_missing_evidence_policy",
            "tool_manifest_missing_sandbox_policy",
            "tool_manifest_missing_secret_handling",
            "tool_manifest_claims_tool_authority",
            "tool_manifest_grants_execution_permission",
            "tool_manifest_registers_tools",
            "tool_manifest_imports_adapters",
            "tool_manifest_exposes_mcp_server",
            "tool_manifest_schedules_tool_calls",
            "tool_manifest_reads_live_state",
            "tool_manifest_mutates_state",
            "tool_manifest_auto_apply",
            "tool_manifest_contains_secret_material",
            "tool_manifest_stores_raw_tool_outputs",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_tool_risk_laundering_is_blocked(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [
                _manifest(
                    {
                        "tools": [
                            _tool(
                                {
                                    "tool_id": "dangerous-tool",
                                    "decision": "allow",
                                    "risk_level": "critical",
                                    "network_access": True,
                                    "mutates_files": True,
                                    "mutates_state": True,
                                    "destructive": True,
                                    "requires_human_confirmation": False,
                                    "captures_sensitive_output": True,
                                    "max_data_sensitivity": "secret",
                                    "timeout_seconds": 0,
                                    "summary": "Tool call approved.",
                                }
                            )
                        ]
                    }
                )
            ],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
            capability_rules=[_capability_rule()],
        )

        expected = {
            "high_risk_tool_allowed_without_review",
            "network_tool_allowed_without_review",
            "mutating_tool_allowed_without_review",
            "destructive_tool_missing_human_confirmation",
            "sensitive_output_tool_not_denied",
            "tool_missing_timeout",
            "tool_summary_launders_tool_authority",
        }
        self.assertTrue(expected.issubset(set(review.finding_codes)))

    def test_cross_review_and_capability_rule_drift_are_reported(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [_manifest({"capability_rule_ids": ["missing-capability"]})],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(status="control_plane_integrity_drift_detected"),
            capability_rules=[_capability_rule()],
        )

        self.assertIn("tool_manifest_over_integrity_drift", review.finding_codes)
        self.assertIn("tool_manifest_references_unknown_capability_rule", review.finding_codes)

        missing_rules = build_control_plane_tool_manifest_review(
            [_manifest({"capability_rule_ids": ["missing-capability"]})],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
        )
        self.assertIn("tool_manifest_missing_capability_rules", missing_rules.finding_codes)

    def test_renderers_preserve_guardrails_and_reject_forged_summary_fields(self) -> None:
        review = build_control_plane_tool_manifest_review(
            [_manifest()],
            review_as_of=REVIEW_AS_OF,
            integrity_review=_integrity_review(),
            capability_rules=[_capability_rule()],
        )

        payload = json.loads(render_control_plane_tool_manifest_review_json(review))
        markdown = render_control_plane_tool_manifest_review_markdown(review)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["tool_manifest_review_is_not_permission"])
        self.assertIn("tool_manifest_review_is_not_permission: true", markdown)
        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "finding_count"):
            render_control_plane_tool_manifest_review_json(replace(review, finding_count=99))
        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "finding_codes"):
            render_control_plane_tool_manifest_review_json(replace(review, finding_codes=("forged",)))
        with self.assertRaisesRegex(ControlPlaneToolManifestReviewError, "guardrails"):
            render_control_plane_tool_manifest_review_json(replace(review, tool_manifest_review_is_not_adapter=False))

    def test_package_source_contains_no_runtime_or_io_surfaces(self) -> None:
        package_root = REPO_ROOT / "experiments" / "control_plane_tool_manifest_review"
        source = "\n".join(path.read_text(encoding="utf-8") for path in package_root.glob("*.py")).lower()

        forbidden = [
            "read_text(",
            "write_text(",
            "subprocess",
            "import requests",
            "requests.",
            "temporalio",
            "langgraph",
            "opentelemetry",
            "from cli",
            "from extensions",
            "import cli",
            "import extensions",
        ]
        for token in forbidden:
            self.assertNotIn(token, source)


if __name__ == "__main__":
    unittest.main()
