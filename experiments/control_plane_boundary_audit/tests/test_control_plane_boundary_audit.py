from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.control_plane_boundary_audit import (
    CONTROL_PLANE_BOUNDARY_PACKAGES,
    ControlPlaneBoundaryAuditError,
    ControlPlaneBoundarySource,
    audit_control_plane_boundary_sources,
    audit_control_plane_boundary_tree,
    collect_control_plane_boundary_sources,
    render_control_plane_boundary_audit_json,
    render_control_plane_boundary_audit_markdown,
)


REPO_ROOT = Path(__file__).resolve().parents[3]


class ControlPlaneBoundaryAuditTests(unittest.TestCase):
    def test_current_control_plane_packages_preserve_boundary_markers(self) -> None:
        report = audit_control_plane_boundary_tree(REPO_ROOT / "experiments")

        self.assertEqual("boundary_markers_preserved", report.audit_status)
        self.assertEqual(0, report.finding_count)
        self.assertEqual(tuple(sorted(CONTROL_PLANE_BOUNDARY_PACKAGES)), report.audited_packages)
        self.assertEqual("none", report.state_change)
        self.assertIn("non-authoritative", report.authority)
        self.assertTrue(report.audit_is_not_permission)
        self.assertTrue(report.finding_is_not_truth)
        self.assertTrue(report.audit_pass_is_not_execution_approval)
        self.assertTrue(report.must_not_execute_automatically)

    def test_collects_only_bounded_top_level_package_sources(self) -> None:
        sources = collect_control_plane_boundary_sources(
            REPO_ROOT / "experiments",
            package_names=("control_plane_guardrail_eval",),
        )

        paths = {source.relative_path for source in sources}
        self.assertIn("__init__.py", paths)
        self.assertIn("evaluator.py", paths)
        self.assertIn("README.md", paths)
        self.assertNotIn("tests/test_control_plane_guardrail_eval.py", paths)

    def test_collects_nested_production_sources_without_tests(self) -> None:
        with tempfile.TemporaryDirectory() as raw_root:
            experiments_root = Path(raw_root) / "experiments"
            package_root = experiments_root / "control_plane_guardrail_eval"
            nested_root = package_root / "nested"
            tests_root = package_root / "tests"
            nested_root.mkdir(parents=True)
            tests_root.mkdir()
            (package_root / "__init__.py").write_text(
                "state_change = 'none'\nauthority = 'non-authoritative'\nmust_not_execute_automatically = True\n",
                encoding="utf-8",
            )
            (nested_root / "adapter_guard.py").write_text(
                "state_change = 'none'\nauthority = 'non-authoritative'\nmust_not_execute_automatically = True\n",
                encoding="utf-8",
            )
            (tests_root / "test_fixture.py").write_text("import opentelemetry\n", encoding="utf-8")

            sources = collect_control_plane_boundary_sources(
                experiments_root,
                package_names=("control_plane_guardrail_eval",),
            )

        paths = {source.relative_path for source in sources}
        self.assertIn("nested/adapter_guard.py", paths)
        self.assertNotIn("tests/test_fixture.py", paths)

    def test_detects_forbidden_imports_runtime_adapters_and_io_calls(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_guardrail_eval",
            relative_path="bad.py",
            text="""
import opentelemetry
import subprocess
import cli.main
import extensions.foo
from cli.main import build_parser

def run(path):
    open(path, "w")
    path.write_text("x")

state_change = "none"
authority = "non-authoritative"
must_not_execute_automatically = True
""",
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertEqual("boundary_drift_observed", report.audit_status)
        self.assertIn("forbidden_import_surface", report.finding_codes)
        self.assertIn("forbidden_runtime_surface_import", report.finding_codes)
        self.assertIn("forbidden_dynamic_or_file_call", report.finding_codes)
        self.assertIn("forbidden_mutating_or_io_call", report.finding_codes)

    def test_detects_missing_markers_and_permission_laundering_text(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_review_packet",
            relative_path="README.md",
            text="This package grants runtime_authority and permission_granted for an mcp adapter.",
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("state_change_marker_missing", report.finding_codes)
        self.assertIn("non_authority_marker_missing", report.finding_codes)
        self.assertIn("no_auto_execution_marker_missing", report.finding_codes)
        self.assertIn("adapter_or_runtime_laundering_text", report.finding_codes)
        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_negative_markers_do_not_trigger_permission_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_telemetry_projection",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "runtime_authority is not granted and permission_granted is not allowed"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertEqual(0, report.finding_count)

    def test_negative_marker_only_suppresses_same_line_not_whole_file(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_telemetry_projection",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "runtime_authority is not granted here.\n"
                "permission_granted is available elsewhere"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_natural_language_permission_and_scheduler_laundering_are_detected(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_observation_transition_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "This review grants permission to execute and acts as the scheduler."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_handoff_file_reads_and_handoff_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_handoff_review",
            relative_path="review.py",
            text='''
from pathlib import Path

def load():
    Path("docs/operations/observation_center.toml").read_text(encoding="utf-8")
    return "handoff approved; handoff selected next action"

state_change = "none"
authority = "non-authoritative"
must_not_execute_automatically = True
''',
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("forbidden_observation_center_read_text", report.finding_codes)
        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_decision_version_runtime_and_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_decision_version_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "This decision approved the runtime and decision selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_rule_promotion_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_rule_promotion_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "This promotion approved the runtime; the rule promoted and applies rule."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_rule_version_and_store_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_rule_promotion_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The latest rule is truth and the canonical rule store selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_runtime_adoption_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_runtime_adoption_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "Runtime adoption approved; adapter grants permission and the otel trace is truth."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_runtime_state_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_runtime_state_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The state store is truth and the snapshot selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_runtime_contract_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_runtime_contract_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The canonical runtime contract is truth and the contract selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_runtime_state_transition_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_runtime_state_transition_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The transition result is truth and the transition selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_tool_manifest_authority_and_registry_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_tool_manifest_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The tool manifest approved execution; tool registry is truth and call_tool is enabled."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)
        self.assertIn("forbidden_observation_center_read_text", report.finding_codes)

    def test_detects_evidence_policy_truth_permission_and_retention_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_evidence_policy_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "Evidence is truth; evidence grants permission; silence is negative evidence; "
                "stores raw evidence and stores secret material."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_work_queue_scheduler_priority_and_ready_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_work_queue_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The canonical work queue selected next action. "
                "Priority is truth and ready-to-run work grants permission. "
                "The work queue schedules work."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_work_queue_dependency_owner_and_dispatch_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_work_queue_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "Dependency satisfaction grants permission. "
                "Owner assignment is truth. "
                "Auto dispatch selected next action."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_work_queue_source_reader_and_store_authority_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_work_queue_review",
            relative_path="review.py",
            text='''
def load():
    return "read_work_queue uses work_queue.json; state reader is authority"

state_change = "none"
authority = "non-authoritative"
must_not_execute_automatically = True
''',
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("forbidden_observation_center_read_text", report.finding_codes)
        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_negative_work_queue_boundary_markers_do_not_trigger_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_work_queue_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "work queue is not truth; priority is not truth; "
                "dependency satisfaction does not grant permission; "
                "ready-to-run is not execution approval; "
                "owner assignment is not authority; "
                "auto dispatch must not happen; "
                "state reader is not authority"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertEqual(0, report.finding_count)

    def test_work_queue_negative_marker_only_suppresses_same_line(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_work_queue_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "priority is not truth here.\n"
                "owner assignment grants permission elsewhere"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_approval_policy_permission_expiration_scope_fingerprint_and_reuse_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_approval_policy_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n\n"
                "The canonical approval policy grants execution. "
                "Expired approval grants permission. "
                "Scope wildcard grants permission. "
                "Fingerprint reuse allowed. "
                "Approval applies across tasks."
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_detects_approval_store_reader_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_approval_policy_review",
            relative_path="review.py",
            text='''
def load():
    return "read_approval_policy uses approval_policy.json; approval record is truth"

state_change = "none"
authority = "non-authoritative"
must_not_execute_automatically = True
''',
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("forbidden_observation_center_read_text", report.finding_codes)
        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_negative_approval_policy_guardrails_do_not_trigger_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_approval_policy_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "approval policy is not authority; "
                "approval status is not truth; "
                "approval does not grant permission; "
                "fingerprint must match; "
                "approval is not reusable; "
                "expired approval is not valid after expiration; "
                "approval is not valid outside scope"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertEqual(0, report.finding_count)

    def test_approval_policy_negative_marker_only_suppresses_same_line(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_approval_policy_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "approval status is not truth here.\n"
                "approval status grants permission elsewhere"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertIn("permission_laundering_text", report.finding_codes)

    def test_negative_rule_version_markers_do_not_trigger_laundering(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_rule_promotion_review",
            relative_path="README.md",
            text=(
                "state_change: none\n"
                "non-authoritative package\n"
                "must_not_execute_automatically: true\n"
                "rule version is not truth and this is not a canonical rule store"
            ),
        )

        report = audit_control_plane_boundary_sources((source,))

        self.assertEqual(0, report.finding_count)

    def test_rejects_unexpected_package_and_root_escape_path(self) -> None:
        with self.assertRaisesRegex(ControlPlaneBoundaryAuditError, "unexpected"):
            audit_control_plane_boundary_sources(
                (
                    ControlPlaneBoundarySource(
                        package_name="not_control_plane",
                        relative_path="README.md",
                        text="state_change none non-authoritative must_not_execute_automatically",
                    ),
                )
            )

        with self.assertRaisesRegex(ControlPlaneBoundaryAuditError, "escape"):
            audit_control_plane_boundary_sources(
                (
                    ControlPlaneBoundarySource(
                        package_name="control_plane_guardrail_eval",
                        relative_path="../README.md",
                        text="state_change none non-authoritative must_not_execute_automatically",
                    ),
                )
            )

    def test_renderers_preserve_non_authority_markers(self) -> None:
        source = ControlPlaneBoundarySource(
            package_name="control_plane_guardrail_eval",
            relative_path="README.md",
            text="state_change none non-authoritative must_not_execute_automatically",
        )
        report = audit_control_plane_boundary_sources((source,))

        payload = json.loads(render_control_plane_boundary_audit_json(report))
        markdown = render_control_plane_boundary_audit_markdown(report)

        self.assertEqual("none", payload["state_change"])
        self.assertTrue(payload["audit_is_not_permission"])
        self.assertTrue(payload["finding_is_not_truth"])
        self.assertTrue(payload["audit_pass_is_not_execution_approval"])
        self.assertIn("audit_is_not_permission: true", markdown)
        self.assertIn("finding_is_not_truth: true", markdown)
        self.assertIn("audit_pass_is_not_execution_approval: true", markdown)


if __name__ == "__main__":
    unittest.main()
