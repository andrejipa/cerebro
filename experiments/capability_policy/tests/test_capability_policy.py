from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from experiments.capability_policy import (
    CapabilityPolicyError,
    CapabilityRequest,
    CapabilityRule,
    evaluate_capability_request,
    load_capability_manifest,
    render_capability_assessment_json,
    render_capability_assessment_markdown,
)


def _workspace_tmp_dir() -> tempfile.TemporaryDirectory[str]:
    root = Path("/tmp") / "cerebro_capability_policy_tests"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


def _rule(
    *,
    rule_id: str = "python-unittest",
    decision: str = "allow",
    argv_prefix: tuple[str, ...] = ("python", "-m", "unittest"),
    path_scope: tuple[str, ...] = ("tests", "experiments"),
    max_data_sensitivity: str = "internal",
    network_access: str = "denied",
    approval_required: bool = False,
    output_budget_kb: int = 64,
) -> CapabilityRule:
    return CapabilityRule(
        rule_id=rule_id,
        decision=decision,
        argv_prefix=argv_prefix,
        path_scope=path_scope,
        max_data_sensitivity=max_data_sensitivity,
        network_access=network_access,
        approval_required=approval_required,
        output_budget_kb=output_budget_kb,
        retention="ephemeral",
        rollback_expectation="not_applicable",
        rationale="local test command",
    )


def _manifest_text(extra: str = "") -> str:
    return (
        """
schema_version = "1"

[[capability]]
rule_id = "python-unittest"
decision = "allow"
argv_prefix = ["python", "-m", "unittest"]
path_scope = ["tests", "experiments"]
max_data_sensitivity = "internal"
network_access = "denied"
approval_required = false
output_budget_kb = 64
retention = "ephemeral"
rollback_expectation = "not_applicable"
rationale = "Local unit tests are inspectable and bounded."
"""
        + extra
    )


class CapabilityPolicyTests(unittest.TestCase):
    def test_manifest_loads_reexecutable_capability_rules(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "capabilities.toml"
            manifest.write_text(_manifest_text(), encoding="utf-8")

            rules = load_capability_manifest("capabilities.toml", root=root)

        self.assertEqual(len(rules), 1)
        self.assertEqual("python-unittest", rules[0].rule_id)
        self.assertEqual(("python", "-m", "unittest"), rules[0].argv_prefix)

    def test_manifest_rejects_root_escape_cerebro_location_and_duplicate_ids(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            outside = root.parent / "outside_capabilities.toml"
            outside.write_text(_manifest_text(), encoding="utf-8")
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir()
            cerebro_manifest = cerebro_dir / "capabilities.toml"
            cerebro_manifest.write_text(_manifest_text(), encoding="utf-8")
            duplicate = root / "duplicate.toml"
            duplicate.write_text(_manifest_text(_manifest_text().replace('schema_version = "1"', "")), encoding="utf-8")

            with self.assertRaisesRegex(CapabilityPolicyError, "escapes root"):
                load_capability_manifest(outside, root=root)
            with self.assertRaisesRegex(CapabilityPolicyError, ".cerebro"):
                load_capability_manifest(cerebro_manifest, root=root)
            with self.assertRaisesRegex(CapabilityPolicyError, "duplicate rule_id"):
                load_capability_manifest(duplicate, root=root)

    def test_advisory_allow_is_not_permission(self) -> None:
        assessment = evaluate_capability_request(
            (_rule(),),
            CapabilityRequest(
                request_id="req-tests",
                argv=("python", "-m", "unittest", "tests.test_doc_governance", "-v"),
                reads=("tests/test_doc_governance.py",),
                writes=(),
                data_sensitivity="internal",
                expected_output_kb=32,
            ),
        )
        payload = json.loads(render_capability_assessment_json(assessment))

        self.assertEqual("advisory_allow", assessment.decision)
        self.assertEqual("none", assessment.required_human_decision)
        self.assertTrue(payload["advisory_allow_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertEqual("none", payload["state_change"])
        self.assertIn("non-authoritative", payload["authority"])

    def test_no_matching_rule_blocks_request(self) -> None:
        assessment = evaluate_capability_request(
            (_rule(),),
            CapabilityRequest(request_id="req-shell", argv=("powershell", "-Command", "Invoke-WebRequest")),
        )

        self.assertEqual("blocked", assessment.decision)
        self.assertEqual("none", assessment.matched_rule_id)
        self.assertIn("no_matching_capability_rule", assessment.reasons)

    def test_network_and_sensitive_data_fail_closed(self) -> None:
        assessment = evaluate_capability_request(
            (_rule(),),
            CapabilityRequest(
                request_id="req-network",
                argv=("python", "-m", "unittest"),
                reads=("tests/test_doc_governance.py",),
                data_sensitivity="secret",
                network_access=True,
            ),
        )

        self.assertEqual("blocked", assessment.decision)
        self.assertIn("data_sensitivity_exceeds_capability", assessment.reasons)
        self.assertIn("network_access_denied_by_capability", assessment.reasons)

    def test_out_of_scope_and_cerebro_write_blocks(self) -> None:
        assessment = evaluate_capability_request(
            (_rule(path_scope=("tests", ".cerebro")),),
            CapabilityRequest(
                request_id="req-cerebro-write",
                argv=("python", "-m", "unittest"),
                reads=("tests/test_doc_governance.py",),
                writes=(".cerebro/state.json",),
            ),
        )

        self.assertEqual("blocked", assessment.decision)
        self.assertIn("cerebro_write_requires_runtime_authority", assessment.reasons)

    def test_review_required_rule_and_missing_approval_stay_human_decision(self) -> None:
        assessment = evaluate_capability_request(
            (_rule(decision="review_required", approval_required=True),),
            CapabilityRequest(
                request_id="req-review",
                argv=("python", "-m", "unittest"),
                reads=("tests/test_doc_governance.py",),
            ),
        )

        self.assertEqual("review_required", assessment.decision)
        self.assertIn("capability_rule_requires_review", assessment.reasons)
        self.assertIn("approval_required_but_missing", assessment.reasons)
        self.assertEqual("provide_human_approval", assessment.required_human_decision)

    def test_rendered_markdown_preserves_boundary_markers(self) -> None:
        markdown = render_capability_assessment_markdown(
            evaluate_capability_request(
                (_rule(),),
                CapabilityRequest(
                    request_id="req-tests",
                    argv=("python", "-m", "unittest"),
                    reads=("tests/test_doc_governance.py",),
                ),
            )
        )

        self.assertIn("state_change: none", markdown)
        self.assertIn("authority: non-authoritative; advisory capability policy only", markdown)
        self.assertIn("advisory_allow_is_not_permission: true", markdown)


if __name__ == "__main__":
    unittest.main()
