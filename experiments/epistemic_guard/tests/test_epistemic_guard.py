from __future__ import annotations

import json
import tempfile
import unittest
from dataclasses import replace
from pathlib import Path

from experiments.epistemic_guard import (
    DecisionManifestError,
    PreActionGuardError,
    PreActionPacketStressError,
    PreActionStressMatrixReport,
    all_fixture_scenarios,
    build_default_pre_action_stress_matrix,
    build_pre_action_decision_packet,
    build_pre_action_packet_review_closeout,
    build_pre_action_packet_stress_repro_report,
    build_pre_action_guard_report_from_manifest,
    check_pre_action_packet_artifacts,
    evaluate_decision_scenario,
    evaluate_manifest_file,
    load_decision_manifest,
    render_pre_action_decision_packet_json,
    render_pre_action_decision_packet_markdown,
    render_pre_action_packet_review_closeout_json,
    render_pre_action_packet_review_closeout_markdown,
    render_pre_action_packet_stress_repro_json,
    render_pre_action_packet_stress_repro_markdown,
    render_pre_action_guard_report_json,
    render_pre_action_guard_report_markdown,
    render_pre_action_stress_matrix_json,
    render_pre_action_stress_matrix_markdown,
    render_envelopes_json,
    render_envelopes_markdown,
)
from experiments.epistemic_guard.fixtures import (
    approval_expired_by_source_set_change,
    clean_advisory_report,
    existing_state_ambiguity,
    missing_trigger_for_runtime_mutation,
    protocol_induced_stale_source_route,
    read_write_drift,
    silence_is_not_negative_evidence,
    stale_next_action,
)


def _workspace_tmp_dir() -> tempfile.TemporaryDirectory[str]:
    root = Path("/tmp") / "cerebro_epistemic_guard_tests"
    root.mkdir(parents=True, exist_ok=True)
    return tempfile.TemporaryDirectory(dir=root)


def _manifest_text(extra: str = "") -> str:
    return f"""
schema_version = "1"

[[scenario]]
scenario_id = "manifest_clean"
intent = "Produce a declared advisory report from manifest evidence."
action_profile = {{ zone = "ZONE_1", reads = ["SYSTEM_STATE.md"], writes = [], authority_impact = "none", runtime_impact = "none", reversibility = "high" }}
sources = [
  {{ source_id = "system", path = "SYSTEM_STATE.md", freshness = "current", role = "primary" }},
]
claims = [
  {{ claim_id = "claim-boundary", subject = "runtime_boundary", predicate = "is", value = "closed", source_id = "system" }},
]
requirements = [
  {{ requirement_id = "req-boundary", subject = "runtime_boundary", predicate = "is", description = "current runtime boundary", required_for = "advisory report" }},
]
{extra}
"""


def _pre_action_manifest_text(extra: str = "") -> str:
    return (
        """
schema_version = "1"

[proposed_action]
action_id = "pre-action-slice"
intent = "Produce a pre-action guard report from declared evidence."
action_kind = "derived_experiment"
proposed_by = "operator"
created_at = "2026-04-24"
expected_state_change = "none"
notes = ["advisory only"]
"""
        + _manifest_text(extra).replace('schema_version = "1"\n\n', "")
    )


def _clean_pre_action_packet(root: Path):
    manifest = root / "pre_action.toml"
    manifest.write_text(_pre_action_manifest_text(), encoding="utf-8")
    report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)
    return build_pre_action_decision_packet(report, build_default_pre_action_stress_matrix())


def _clean_packet_stress_repro_report(root: Path):
    packet = _clean_pre_action_packet(root)
    json_path = root / "packet.json"
    markdown_path = root / "packet.md"
    json_path.write_text(render_pre_action_decision_packet_json(packet), encoding="utf-8")
    markdown_path.write_text(render_pre_action_decision_packet_markdown(packet), encoding="utf-8")
    stress_repro = build_pre_action_packet_stress_repro_report(
        packet,
        json_path=json_path,
        markdown_path=markdown_path,
        root=root,
        degraded_artifact_root=root / "degraded",
    )
    return packet, stress_repro


class EpistemicGuardTests(unittest.TestCase):
    def test_stale_next_action_blocks_schema_creation_decision(self) -> None:
        envelope = evaluate_decision_scenario(stale_next_action())

        self.assertEqual(envelope.sufficiency, "insufficient")
        self.assertEqual(envelope.action_readiness, "human_approval_required")
        self.assertEqual(envelope.recommended_human_decision, "adjudicate_conflict")
        self.assertTrue(envelope.stale_claims)
        self.assertTrue(envelope.conflicts)

    def test_silence_is_missing_evidence_not_negative_schema_claim(self) -> None:
        envelope = evaluate_decision_scenario(silence_is_not_negative_evidence())

        self.assertEqual(envelope.sufficiency, "partial")
        self.assertEqual(envelope.action_readiness, "human_approval_required")
        self.assertEqual(envelope.recommended_human_decision, "provide_missing_evidence")
        self.assertTrue(envelope.missing_evidence)
        self.assertFalse(any("schema exists false" in claim for claim in envelope.claim_summary))

    def test_existing_state_ambiguity_blocks_third_party_pilot(self) -> None:
        envelope = evaluate_decision_scenario(existing_state_ambiguity())

        self.assertEqual(envelope.action_readiness, "blocked")
        self.assertIn("existing_state_ambiguity", envelope.blockers)
        self.assertEqual(envelope.recommended_human_decision, "adjudicate_conflict")

    def test_missing_trigger_for_runtime_mutation_requires_trigger(self) -> None:
        envelope = evaluate_decision_scenario(missing_trigger_for_runtime_mutation())

        self.assertEqual(envelope.action_readiness, "canonical_change_requires_trigger")
        self.assertIn("missing_active_trigger_for_runtime_or_canonical_change", envelope.blockers)
        self.assertEqual(envelope.approval_status, "missing_for_authority_impact")

    def test_approval_expires_when_source_set_changes(self) -> None:
        envelope = evaluate_decision_scenario(approval_expired_by_source_set_change())

        self.assertEqual(envelope.approval_status, "expired_by_source_set_change")
        self.assertEqual(envelope.action_readiness, "blocked")
        self.assertIn("approval_expired_by_source_set_change", envelope.blockers)

    def test_read_write_drift_blocks_prewrite_guard(self) -> None:
        envelope = evaluate_decision_scenario(read_write_drift())

        self.assertEqual(envelope.prewrite_guard_status, "blocked_read_write_drift")
        self.assertEqual(envelope.action_readiness, "blocked")
        self.assertIn("read_write_drift:SYSTEM_STATE.md", envelope.blockers)

    def test_protocol_induced_stale_source_route_requires_human_decision(self) -> None:
        envelope = evaluate_decision_scenario(protocol_induced_stale_source_route())

        self.assertEqual(envelope.sufficiency, "insufficient")
        self.assertEqual(envelope.action_readiness, "human_approval_required")
        self.assertIn("protocol_route_correlates_with_stale_source", envelope.warnings)
        self.assertTrue(envelope.stale_claims)

    def test_clean_advisory_report_is_allowed_but_not_permission(self) -> None:
        envelope = evaluate_decision_scenario(clean_advisory_report())

        self.assertEqual(envelope.sufficiency, "sufficient")
        self.assertEqual(envelope.action_readiness, "advisory_report_allowed")
        self.assertEqual(envelope.recommended_human_decision, "none")
        self.assertEqual(envelope.state_change, "none")
        self.assertIn("advisory_is_not_authority", envelope.guardrails)

    def test_all_fixture_outputs_preserve_state_change_none(self) -> None:
        envelopes = [evaluate_decision_scenario(scenario) for scenario in all_fixture_scenarios()]

        self.assertEqual(len(envelopes), 8)
        self.assertEqual({envelope.state_change for envelope in envelopes}, {"none"})
        self.assertEqual({envelope.authority for envelope in envelopes}, {"non-authoritative; advisory decision envelope only"})

    def test_rendered_json_and_markdown_are_stable_and_non_authoritative(self) -> None:
        envelopes = [evaluate_decision_scenario(scenario) for scenario in all_fixture_scenarios()]

        payload = json.loads(render_envelopes_json(envelopes))
        markdown = render_envelopes_markdown(envelopes)

        self.assertEqual(payload["state_change"], "none")
        self.assertEqual(len(payload["envelopes"]), 8)
        self.assertIn("# Epistemic Guard Decision Envelope Oracle", markdown)
        self.assertIn("- advisory_pass_is_not_permission: true", markdown)
        self.assertIn("- silence_is_not_negative_evidence: true", markdown)
        self.assertIn("- derived_experiment_allowed_count:", markdown)
        self.assertIn("### clean_advisory_report", markdown)

    def test_load_manifest_builds_reexecutable_decision_envelope(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "decision.toml"
            manifest.write_text(_manifest_text(), encoding="utf-8")

            scenarios = load_decision_manifest("decision.toml", root=root)
            envelopes = evaluate_manifest_file("decision.toml", root=root)

        self.assertEqual(len(scenarios), 1)
        self.assertEqual(envelopes[0].action_readiness, "advisory_report_allowed")
        self.assertEqual(envelopes[0].state_change, "none")

    def test_manifest_preserves_approval_and_prewrite_drift(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "decision.toml"
            manifest.write_text(
                _manifest_text(
                    """
approval = { status = "approved", approval_id = "approval-1", approved_reads = ["SYSTEM_STATE.md"], approved_writes = ["report.md"] }
prewrite_guard = { read_digests = [{ path = "SYSTEM_STATE.md", digest = "old" }], current_digests = [{ path = "SYSTEM_STATE.md", digest = "new" }] }
"""
                ).replace('writes = []', 'writes = ["report.md"]'),
                encoding="utf-8",
            )

            envelope = evaluate_manifest_file("decision.toml", root=root)[0]

        self.assertEqual(envelope.prewrite_guard_status, "blocked_read_write_drift")
        self.assertIn("read_write_drift:SYSTEM_STATE.md", envelope.blockers)

    def test_manifest_rejects_root_escape_and_cerebro_manifest_paths(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            outside = root.parent / "outside_manifest.toml"
            outside.write_text(_manifest_text(), encoding="utf-8")
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir()
            cerebro_manifest = cerebro_dir / "decision.toml"
            cerebro_manifest.write_text(_manifest_text(), encoding="utf-8")

            with self.assertRaisesRegex(DecisionManifestError, "escapes root"):
                load_decision_manifest(outside, root=root)
            with self.assertRaisesRegex(DecisionManifestError, ".cerebro"):
                load_decision_manifest(cerebro_manifest, root=root)

    def test_manifest_rejects_missing_schema_and_duplicate_scenario_ids(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            missing_schema = root / "missing.toml"
            missing_schema.write_text(_manifest_text().replace('schema_version = "1"', ""), encoding="utf-8")
            duplicate = root / "duplicate.toml"
            duplicate.write_text(_manifest_text() + _manifest_text().replace('schema_version = "1"', ""), encoding="utf-8")

            with self.assertRaisesRegex(DecisionManifestError, "schema_version"):
                load_decision_manifest(missing_schema, root=root)
            with self.assertRaisesRegex(DecisionManifestError, "duplicate scenario_id"):
                load_decision_manifest(duplicate, root=root)

    def test_manifest_rejects_duplicate_source_and_undeclared_claim_source(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            duplicate_source = root / "duplicate_source.toml"
            duplicate_source.write_text(
                """
schema_version = "1"

[[scenario]]
scenario_id = "manifest_bad_sources"
intent = "Invalid duplicate source manifest."
action_profile = { zone = "ZONE_1", reads = ["SYSTEM_STATE.md"], writes = [], authority_impact = "none", runtime_impact = "none", reversibility = "high" }
sources = [
  { source_id = "system", path = "SYSTEM_STATE.md" },
  { source_id = "system", path = "OPPORTUNITY_MAP.md" },
]
claims = [
  { claim_id = "claim-boundary", subject = "runtime_boundary", predicate = "is", value = "closed", source_id = "system" },
]
""",
                encoding="utf-8",
            )
            undeclared_source = root / "undeclared_source.toml"

            with self.assertRaisesRegex(DecisionManifestError, "duplicates source_id"):
                load_decision_manifest(duplicate_source, root=root)
            undeclared_source.write_text(
                """
schema_version = "1"

[[scenario]]
scenario_id = "manifest_bad_claim_source"
intent = "Invalid undeclared claim source manifest."
action_profile = { zone = "ZONE_1", reads = ["SYSTEM_STATE.md"], writes = [], authority_impact = "none", runtime_impact = "none", reversibility = "high" }
sources = [
  { source_id = "system", path = "SYSTEM_STATE.md" },
]
claims = [
  { claim_id = "claim-boundary", subject = "runtime_boundary", predicate = "is", value = "closed", source_id = "missing" },
]
""",
                encoding="utf-8",
            )
            with self.assertRaisesRegex(DecisionManifestError, "undeclared source"):
                load_decision_manifest(undeclared_source, root=root)

    def test_pre_action_report_aggregates_clean_manifest_without_permission(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "pre_action.toml"
            manifest.write_text(_pre_action_manifest_text(), encoding="utf-8")

            report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)
            payload = json.loads(render_pre_action_guard_report_json(report))
            markdown = render_pre_action_guard_report_markdown(report)

        self.assertEqual(report.proposed_action.action_id, "pre-action-slice")
        self.assertEqual(report.action_readiness, "advisory_report_allowed")
        self.assertEqual(report.recommended_human_decision, "none")
        self.assertEqual(report.state_change, "none")
        self.assertTrue(report.must_not_execute_automatically)
        self.assertTrue(report.advisory_pass_is_not_permission)
        self.assertEqual(payload["state_change"], "none")
        self.assertIn("# Epistemic Guard Pre-Action Report", markdown)
        self.assertIn("- advisory_pass_is_not_permission: true", markdown)

    def test_pre_action_report_aggregates_blocked_manifest(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "pre_action.toml"
            manifest.write_text(
                _pre_action_manifest_text().replace(
                    'runtime_impact = "none"',
                    'runtime_impact = "direct"',
                ),
                encoding="utf-8",
            )

            report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)

        self.assertEqual(report.action_readiness, "canonical_change_requires_trigger")
        self.assertEqual(report.recommended_human_decision, "review_blockers")
        self.assertGreater(report.blocker_count, 0)
        self.assertTrue(report.blocked)

    def test_pre_action_manifest_requires_proposed_action_and_state_change_none(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            missing = root / "missing.toml"
            missing.write_text(_manifest_text(), encoding="utf-8")
            mutating = root / "mutating.toml"
            mutating.write_text(
                _pre_action_manifest_text().replace(
                    'expected_state_change = "none"',
                    'expected_state_change = "writes_runtime"',
                ),
                encoding="utf-8",
            )

            with self.assertRaisesRegex(PreActionGuardError, "proposed_action"):
                build_pre_action_guard_report_from_manifest("missing.toml", root=root)
            with self.assertRaisesRegex(PreActionGuardError, "expected_state_change"):
                build_pre_action_guard_report_from_manifest("mutating.toml", root=root)

    def test_pre_action_manifest_rejects_root_escape_and_cerebro_paths(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            outside = root.parent / "outside_pre_action.toml"
            outside.write_text(_pre_action_manifest_text(), encoding="utf-8")
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir()
            cerebro_manifest = cerebro_dir / "pre_action.toml"
            cerebro_manifest.write_text(_pre_action_manifest_text(), encoding="utf-8")

            with self.assertRaisesRegex(PreActionGuardError, "escapes root"):
                build_pre_action_guard_report_from_manifest(outside, root=root)
            with self.assertRaisesRegex(PreActionGuardError, ".cerebro"):
                build_pre_action_guard_report_from_manifest(cerebro_manifest, root=root)

    def test_pre_action_stress_matrix_covers_degraded_operator_cases(self) -> None:
        report = build_default_pre_action_stress_matrix()
        cases = {case.case_id: case for case in report.cases}

        self.assertEqual(report.case_count, 6)
        self.assertTrue(report.all_cases_passed)
        self.assertEqual(report.fail_count, 0)
        self.assertEqual(report.boundary_error_count, 2)
        self.assertEqual(cases["clean_pre_action_report"].actual_action_readiness, "advisory_report_allowed")
        self.assertEqual(
            cases["runtime_promotion_without_trigger"].actual_action_readiness,
            "canonical_change_requires_trigger",
        )
        self.assertEqual(cases["stale_approval"].actual_action_readiness, "blocked")
        self.assertEqual(cases["read_write_drift"].actual_action_readiness, "blocked")
        self.assertTrue(cases["missing_proposed_action"].boundary_error)
        self.assertTrue(cases["mutating_expected_state"].boundary_error)
        self.assertEqual(report.state_change, "none")

    def test_pre_action_stress_matrix_renderers_preserve_non_permission_guardrails(self) -> None:
        report = build_default_pre_action_stress_matrix()

        payload = json.loads(render_pre_action_stress_matrix_json(report))
        markdown = render_pre_action_stress_matrix_markdown(report)

        self.assertEqual(payload["state_change"], "none")
        self.assertTrue(payload["stress_pass_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertIn("# Epistemic Guard Pre-Action Stress Matrix", markdown)
        self.assertIn("- stress_pass_is_not_permission: true", markdown)
        self.assertIn("- must_not_execute_automatically: true", markdown)
        self.assertIn("### runtime_promotion_without_trigger", markdown)
        self.assertIn("### read_write_drift", markdown)

    def test_pre_action_decision_packet_combines_clean_report_and_stress_matrix(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "pre_action.toml"
            manifest.write_text(_pre_action_manifest_text(), encoding="utf-8")

            report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)
            stress = build_default_pre_action_stress_matrix()
            packet = build_pre_action_decision_packet(report, stress)

        self.assertEqual(packet.operator_posture, "go_for_advisory_review")
        self.assertEqual(packet.action_readiness, "advisory_report_allowed")
        self.assertEqual(packet.recommended_human_decision, "none")
        self.assertEqual(packet.packet_blocker_count, 0)
        self.assertEqual(packet.stress_case_count, 6)
        self.assertEqual(packet.stress_blocked_or_human_count, 5)
        self.assertTrue(packet.packet_is_not_permission)
        self.assertTrue(packet.stress_pass_is_not_permission)
        self.assertTrue(packet.report_pass_is_not_permission)
        self.assertEqual(packet.state_change, "none")

    def test_pre_action_decision_packet_blocks_blocked_report(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "pre_action.toml"
            manifest.write_text(
                _pre_action_manifest_text().replace(
                    'runtime_impact = "none"',
                    'runtime_impact = "direct"',
                ),
                encoding="utf-8",
            )

            report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)
            packet = build_pre_action_decision_packet(report, build_default_pre_action_stress_matrix())

        self.assertEqual(packet.operator_posture, "no_go_blocked")
        self.assertEqual(packet.action_readiness, "blocked")
        self.assertEqual(packet.recommended_human_decision, "review_blockers")
        self.assertIn("canonical_change_requires_trigger", packet.blockers)
        self.assertIn("pre_action_report_has_blockers", packet.blockers)

    def test_pre_action_decision_packet_blocks_failed_stress_matrix(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            manifest = root / "pre_action.toml"
            manifest.write_text(_pre_action_manifest_text(), encoding="utf-8")
            report = build_pre_action_guard_report_from_manifest("pre_action.toml", root=root)

        failed_stress = PreActionStressMatrixReport(
            case_count=1,
            pass_count=0,
            fail_count=1,
            all_cases_passed=False,
            blocked_or_human_count=0,
            blocker_count=1,
            boundary_error_count=0,
            stress_pass_is_not_permission=True,
            must_not_execute_automatically=True,
            state_change="none",
            authority="non-authoritative; advisory pre-action stress matrix only",
            cases=(),
        )
        packet = build_pre_action_decision_packet(report, failed_stress)

        self.assertEqual(packet.operator_posture, "no_go_blocked")
        self.assertEqual(packet.action_readiness, "blocked")
        self.assertEqual(packet.recommended_human_decision, "review_blockers")
        self.assertIn("pre_action_stress_matrix_failed", packet.blockers)

    def test_pre_action_decision_packet_renderers_preserve_non_permission_guardrails(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet = _clean_pre_action_packet(root)

        payload = json.loads(render_pre_action_decision_packet_json(packet))
        markdown = render_pre_action_decision_packet_markdown(packet)

        self.assertEqual(payload["state_change"], "none")
        self.assertEqual(payload["operator_posture"], "go_for_advisory_review")
        self.assertTrue(payload["packet_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertIn("# Epistemic Guard Pre-Action Decision Packet", markdown)
        self.assertIn("- packet_is_not_permission: true", markdown)
        self.assertIn("- must_not_execute_automatically: true", markdown)
        self.assertIn("- operator_posture: go_for_advisory_review", markdown)

    def test_pre_action_packet_stress_repro_report_covers_degraded_packet_artifacts(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet = _clean_pre_action_packet(root)
            json_path = root / "packet.json"
            markdown_path = root / "packet.md"
            json_path.write_text(render_pre_action_decision_packet_json(packet), encoding="utf-8")
            markdown_path.write_text(render_pre_action_decision_packet_markdown(packet), encoding="utf-8")

            report = build_pre_action_packet_stress_repro_report(
                packet,
                json_path=json_path,
                markdown_path=markdown_path,
                root=root,
                degraded_artifact_root=root / "degraded",
            )
            cases = {case.case_id: case for case in report.cases}

        self.assertEqual(report.case_count, 10)
        self.assertTrue(report.all_cases_passed)
        self.assertEqual(report.fail_count, 0)
        self.assertEqual(report.reproducible_case_count, 1)
        self.assertEqual(report.mismatch_case_count, 3)
        self.assertEqual(report.boundary_error_count, 2)
        self.assertEqual(cases["clean_packet"].actual_operator_posture, "go_for_advisory_review")
        self.assertEqual(cases["blocked_report_packet"].actual_operator_posture, "no_go_blocked")
        self.assertEqual(cases["human_review_packet"].actual_operator_posture, "go_requires_human_review")
        self.assertEqual(cases["failed_stress_packet"].actual_operator_posture, "no_go_blocked")
        self.assertEqual(cases["stale_json_artifact"].actual_reproducibility_status, "blocked")
        self.assertEqual(cases["malformed_json_artifact"].actual_reproducibility_status, "blocked")
        self.assertEqual(cases["missing_json_artifact"].actual_reproducibility_status, "blocked")
        self.assertTrue(cases["root_escape_artifact"].boundary_error)
        self.assertTrue(cases["cerebro_state_artifact_target"].boundary_error)
        self.assertEqual(report.state_change, "none")

    def test_pre_action_packet_artifact_check_blocks_stale_malformed_and_missing(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet = _clean_pre_action_packet(root)
            good_md = root / "packet.md"
            good_md.write_text(render_pre_action_decision_packet_markdown(packet), encoding="utf-8")
            stale_json = root / "stale.json"
            stale_json.write_text(
                render_pre_action_decision_packet_json(packet).replace(
                    '"packet_blocker_count": 0',
                    '"packet_blocker_count": 999',
                ),
                encoding="utf-8",
            )
            malformed_json = root / "malformed.json"
            malformed_json.write_text("{", encoding="utf-8")

            stale = check_pre_action_packet_artifacts(packet, json_path=stale_json, markdown_path=good_md, root=root)
            malformed = check_pre_action_packet_artifacts(
                packet,
                json_path=malformed_json,
                markdown_path=good_md,
                root=root,
            )
            missing = check_pre_action_packet_artifacts(
                packet,
                json_path=root / "missing.json",
                markdown_path=good_md,
                root=root,
            )

        self.assertEqual(stale.reproducibility_status, "blocked")
        self.assertEqual(stale.mismatch_count, 1)
        self.assertEqual(malformed.reproducibility_status, "blocked")
        self.assertEqual(malformed.malformed_artifact_count, 1)
        self.assertEqual(missing.reproducibility_status, "blocked")
        self.assertEqual(missing.missing_artifact_count, 1)
        self.assertTrue(stale.reproducibility_is_not_permission)
        self.assertTrue(stale.digest_equality_is_not_truth)

    def test_pre_action_packet_artifact_check_rejects_root_escape_and_cerebro_paths(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet = _clean_pre_action_packet(root)
            good_md = root / "packet.md"
            good_json = root / "packet.json"
            good_md.write_text(render_pre_action_decision_packet_markdown(packet), encoding="utf-8")
            good_json.write_text(render_pre_action_decision_packet_json(packet), encoding="utf-8")

            with self.assertRaisesRegex(PreActionPacketStressError, "escapes root"):
                check_pre_action_packet_artifacts(
                    packet,
                    json_path=root.parent / "outside.json",
                    markdown_path=good_md,
                    root=root,
                )
            with self.assertRaisesRegex(PreActionPacketStressError, ".cerebro"):
                check_pre_action_packet_artifacts(
                    packet,
                    json_path=root / ".cerebro" / "packet.json",
                    markdown_path=good_md,
                    root=root,
                )

    def test_pre_action_packet_stress_repro_renderers_preserve_non_permission_guardrails(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet = _clean_pre_action_packet(root)
            json_path = root / "packet.json"
            markdown_path = root / "packet.md"
            json_path.write_text(render_pre_action_decision_packet_json(packet), encoding="utf-8")
            markdown_path.write_text(render_pre_action_decision_packet_markdown(packet), encoding="utf-8")
            report = build_pre_action_packet_stress_repro_report(
                packet,
                json_path=json_path,
                markdown_path=markdown_path,
                root=root,
                degraded_artifact_root=root / "degraded",
            )

        payload = json.loads(render_pre_action_packet_stress_repro_json(report))
        markdown = render_pre_action_packet_stress_repro_markdown(report)

        self.assertEqual(payload["state_change"], "none")
        self.assertTrue(payload["stress_pass_is_not_permission"])
        self.assertTrue(payload["reproducibility_is_not_permission"])
        self.assertTrue(payload["digest_equality_is_not_truth"])
        self.assertIn("# Epistemic Guard Pre-Action Packet Stress/Repro Report", markdown)
        self.assertIn("- reproducibility_is_not_permission: true", markdown)
        self.assertIn("### stale_json_artifact", markdown)
        self.assertIn("### root_escape_artifact", markdown)

    def test_pre_action_packet_review_closeout_closes_clean_evidence_until_new_evidence(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet, stress_repro = _clean_packet_stress_repro_report(root)

        closeout = build_pre_action_packet_review_closeout(packet, stress_repro)

        self.assertEqual(closeout.closeout_status, "closed_until_new_evidence")
        self.assertEqual(closeout.action_readiness, "no_action")
        self.assertEqual(closeout.recommended_human_decision, "none")
        self.assertTrue(closeout.recursive_hardening_stopped)
        self.assertEqual(closeout.input_count, 2)
        self.assertEqual(closeout.blocker_count, 0)
        self.assertEqual(closeout.missing_review_evidence_count, 0)
        self.assertEqual(closeout.stress_repro_case_count, 10)
        self.assertEqual(closeout.reopen_trigger_count, 5)
        self.assertEqual(closeout.state_change, "none")
        self.assertTrue(closeout.closeout_is_not_permission)
        self.assertTrue(closeout.no_action_is_not_permission)

    def test_pre_action_packet_review_closeout_blocks_blocked_packet(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet, stress_repro = _clean_packet_stress_repro_report(root)

        blocked_packet = replace(
            packet,
            operator_posture="no_go_blocked",
            action_readiness="blocked",
            recommended_human_decision="review_blockers",
            packet_blocker_count=1,
            blockers=("synthetic_blocker",),
        )
        closeout = build_pre_action_packet_review_closeout(blocked_packet, stress_repro)

        self.assertEqual(closeout.closeout_status, "review_blocked")
        self.assertEqual(closeout.action_readiness, "blocked")
        self.assertEqual(closeout.recommended_human_decision, "review_blockers")
        self.assertFalse(closeout.recursive_hardening_stopped)
        self.assertIn("packet_operator_posture_blocked", closeout.blockers)
        self.assertIn("packet_action_readiness:blocked", closeout.blockers)
        self.assertIn("packet_has_blockers", closeout.blockers)

    def test_pre_action_packet_review_closeout_blocks_failed_or_incomplete_stress_repro(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet, stress_repro = _clean_packet_stress_repro_report(root)

        degraded = replace(
            stress_repro,
            fail_count=1,
            all_cases_passed=False,
            case_count=8,
            mismatch_case_count=1,
            boundary_error_count=1,
        )
        closeout = build_pre_action_packet_review_closeout(packet, degraded)

        self.assertEqual(closeout.closeout_status, "review_blocked")
        self.assertEqual(closeout.action_readiness, "blocked")
        self.assertIn("packet_stress_repro_failed", closeout.blockers)
        self.assertIn("packet_stress_repro_has_failures", closeout.blockers)
        self.assertIn("packet_stress_repro_missing_required_cases", closeout.blockers)
        self.assertIn("packet_stress_repro_missing_degraded_artifact_coverage", closeout.blockers)
        self.assertIn("packet_stress_repro_missing_boundary_coverage", closeout.blockers)

    def test_pre_action_packet_review_closeout_renderers_preserve_non_permission_guardrails(self) -> None:
        with _workspace_tmp_dir() as tmp_dir:
            root = Path(tmp_dir)
            packet, stress_repro = _clean_packet_stress_repro_report(root)
            closeout = build_pre_action_packet_review_closeout(packet, stress_repro)

        payload = json.loads(render_pre_action_packet_review_closeout_json(closeout))
        markdown = render_pre_action_packet_review_closeout_markdown(closeout)

        self.assertEqual(payload["state_change"], "none")
        self.assertEqual(payload["closeout_status"], "closed_until_new_evidence")
        self.assertTrue(payload["closeout_is_not_permission"])
        self.assertTrue(payload["no_action_is_not_permission"])
        self.assertTrue(payload["stress_repro_is_not_permission"])
        self.assertTrue(payload["must_not_execute_automatically"])
        self.assertIn("# Epistemic Guard Pre-Action Packet Review Closeout", markdown)
        self.assertIn("- closeout_is_not_permission: true", markdown)
        self.assertIn("- no_action_is_not_permission: true", markdown)
        self.assertIn("- recursive_hardening_stopped: true", markdown)
        self.assertIn("- packet_artifact_reproducibility_mismatch", markdown)


if __name__ == "__main__":
    unittest.main()
