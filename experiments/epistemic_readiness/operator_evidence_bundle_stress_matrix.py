from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .decision_taxonomy_conformance import evaluate_decision_taxonomy_conformance
from .metacognitive_handoff import evaluate_metacognitive_handoff
from .operator_decision_packet import build_operator_decision_packet
from .operator_evidence_bundle import (
    OPERATOR_EVIDENCE_BUNDLE_AUTHORITY,
    OPERATOR_EVIDENCE_BUNDLE_SCHEMA_VERSION,
    OperatorEvidenceBundleInput,
    OperatorEvidenceBundleReport,
    build_operator_evidence_bundle,
)
from .operator_packet_stress_matrix import _clean_payloads, build_operator_packet_stress_matrix


OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator evidence bundle stress matrix only"
)

_SCENARIO_IDS = (
    "clean_bundle",
    "missing_operator_packet",
    "mutating_operator_packet",
    "malformed_stress_matrix",
    "mutating_source_artifact",
    "duplicate_input_id",
    "digest_summary_mismatch",
)


@dataclass(frozen=True)
class OperatorEvidenceBundleStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    observed_recommended_human_decision: str
    observed_action_readiness: str
    bundle_summary: str
    blocker_count: int
    boundary_error_count: int
    expected_error: bool = False
    observed_error: str = ""
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown operator evidence bundle stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("operator evidence bundle stress scenarios must not change state")
        if self.authority != OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported bundle stress scenario authority: {self.authority}")
        if not self.bundle_summary:
            raise ValueError("operator evidence bundle stress scenarios require bundle_summary")
        if self.blocker_count < 0:
            raise ValueError("blocker_count must be non-negative")
        if self.boundary_error_count < 0:
            raise ValueError("boundary_error_count must be non-negative")
        if self.observed_action_readiness == "blocked" and not (
            self.blocker_count or self.boundary_error_count or self.observed_error
        ):
            raise ValueError("blocked bundle stress scenarios must expose blockers or boundary errors")

    @property
    def passed(self) -> bool:
        return (
            self.observed_recommended_human_decision
            == self.expected_recommended_human_decision
            and self.observed_action_readiness == self.expected_action_readiness
            and bool(self.observed_error) is self.expected_error
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "title": self.title,
            "purpose": self.purpose,
            "state_change": self.state_change,
            "authority": self.authority,
            "expected": {
                "recommended_human_decision": self.expected_recommended_human_decision,
                "action_readiness": self.expected_action_readiness,
                "boundary_error": self.expected_error,
            },
            "observed": {
                "recommended_human_decision": self.observed_recommended_human_decision,
                "action_readiness": self.observed_action_readiness,
                "boundary_error": bool(self.observed_error),
                "error": self.observed_error,
            },
            "passed": self.passed,
            "bundle_summary": self.bundle_summary,
            "blocker_count": self.blocker_count,
            "boundary_error_count": self.boundary_error_count,
            "forbidden_interpretations": [
                "treat bundle output as permission",
                "hide degraded bundle input",
                "hide malformed bundle boundary input",
                "treat artifact digests as truth",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorEvidenceBundleStressMatrixReport:
    scenarios: tuple[OperatorEvidenceBundleStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator evidence bundle stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence bundle stress matrix must not change state")
        if self.authority != OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported bundle stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("operator evidence bundle stress matrix scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "operator evidence bundle stress matrix must contain the closed "
                "scenario set in stable order"
            )
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("operator evidence bundle stress scenarios must preserve state_change none")

    @property
    def pass_count(self) -> int:
        return sum(1 for scenario in self.scenarios if scenario.passed)

    @property
    def fail_count(self) -> int:
        return len(self.scenarios) - self.pass_count

    @property
    def all_scenarios_passed(self) -> bool:
        return self.fail_count == 0

    @property
    def blocker_count(self) -> int:
        return sum(scenario.blocker_count for scenario in self.scenarios)

    @property
    def boundary_error_count(self) -> int:
        return sum(scenario.boundary_error_count for scenario in self.scenarios)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "matrix_role": self.matrix_role,
            "summary": {
                "scenario_count": len(self.scenarios),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "all_scenarios_passed": self.all_scenarios_passed,
                "blocker_count": self.blocker_count,
                "boundary_error_count": self.boundary_error_count,
                "scenario_ids": list(_SCENARIO_IDS),
                "decisions": {
                    scenario.scenario_id: {
                        "recommended_human_decision": (
                            scenario.observed_recommended_human_decision
                        ),
                        "action_readiness": scenario.observed_action_readiness,
                        "boundary_error": bool(scenario.observed_error),
                    }
                    for scenario in self.scenarios
                },
            },
            "scenarios": [scenario.to_dict() for scenario in self.scenarios],
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "bundle_stress_matrix_is_not_permission": True,
                "bundle_stress_matrix_is_not_memory": True,
                "bundle_stress_matrix_is_not_authority": True,
                "bundle_stress_matrix_is_not_runtime_gate": True,
                "bundle_stress_matrix_is_not_claim_graph": True,
                "bundle_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "artifact_digest_is_not_truth": True,
                "malformed_bundle_input_is_blocking_evidence": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare operator evidence bundle output under degraded evidence",
                    "show missing or mutating bundle inputs as blockers",
                    "show malformed stress matrices as boundary errors",
                    "show duplicate or digest-mismatched inputs as blocking evidence",
                    "recommend future hardening slices",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat bundle output as permission",
                    "treat passing scenarios as permission",
                    "treat artifact digests as truth",
                    "hide blockers",
                    "hide malformed bundle input",
                    "hide stale or mismatched digest input",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_bundle_stress_matrix() -> OperatorEvidenceBundleStressMatrixReport:
    scenarios = (
        _build_clean_bundle_scenario(),
        _build_missing_operator_packet_scenario(),
        _build_mutating_operator_packet_scenario(),
        _build_malformed_stress_matrix_scenario(),
        _build_mutating_source_artifact_scenario(),
        _build_duplicate_input_id_scenario(),
        _build_digest_summary_mismatch_scenario(),
    )
    return OperatorEvidenceBundleStressMatrixReport(scenarios=scenarios)


def render_operator_evidence_bundle_stress_matrix_json(
    report: OperatorEvidenceBundleStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_bundle_stress_matrix_markdown(
    report: OperatorEvidenceBundleStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Bundle Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- bundle_stress_matrix_is_not_permission: true",
        "- bundle_stress_matrix_is_not_memory: true",
        "- bundle_stress_matrix_is_not_authority: true",
        "- bundle_stress_matrix_is_not_runtime_gate: true",
        "- bundle_stress_matrix_is_not_claim_graph: true",
        "- bundle_output_is_not_permission: true",
        "- passing_scenario_is_not_permission: true",
        "- artifact_digest_is_not_truth: true",
        "- malformed_bundle_input_is_blocking_evidence: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Stress Summary",
        "",
        f"- scenario_count: `{len(report.scenarios)}`",
        f"- pass_count: `{report.pass_count}`",
        f"- fail_count: `{report.fail_count}`",
        f"- all_scenarios_passed: `{str(report.all_scenarios_passed).lower()}`",
        f"- blocker_count: `{report.blocker_count}`",
        f"- boundary_error_count: `{report.boundary_error_count}`",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Expected Decision | Observed Decision | Expected Readiness | Observed Readiness | Boundary Error | Passed |",
        "|---|---|---|---|---|---|---|",
    ]
    for scenario in report.scenarios:
        lines.append(
            f"| `{scenario.scenario_id}` | "
            f"`{scenario.expected_recommended_human_decision}` | "
            f"`{scenario.observed_recommended_human_decision}` | "
            f"`{scenario.expected_action_readiness}` | "
            f"`{scenario.observed_action_readiness}` | "
            f"`{str(bool(scenario.observed_error)).lower()}` | "
            f"`{str(scenario.passed).lower()}` |"
        )
    lines.extend(["", "## Visible Errors", ""])
    for scenario in report.scenarios:
        if scenario.observed_error:
            lines.append(f"- `{scenario.scenario_id}`: {scenario.observed_error}")
    lines.extend(
        [
            "",
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat bundle output as permission",
            "- treat passing scenarios as permission",
            "- treat artifact digests as truth",
            "- hide blockers",
            "- hide malformed bundle input",
            "- hide stale or mismatched digest input",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _build_clean_bundle_scenario() -> OperatorEvidenceBundleStressScenario:
    bundle, _packet, _stress, _sources = _clean_bundle_payloads()
    summary = _mapping(bundle.get("summary"), "bundle.summary")
    return OperatorEvidenceBundleStressScenario(
        scenario_id="clean_bundle",
        title="Clean evidence bundle remains no-action",
        purpose="Prove clean bundle construction summarizes evidence without granting permission.",
        expected_recommended_human_decision="none",
        expected_action_readiness="no_action",
        observed_recommended_human_decision=_string_value(
            summary.get("packet_recommended_human_decision"),
            "bundle.summary.packet_recommended_human_decision",
        ),
        observed_action_readiness=_string_value(
            summary.get("packet_action_readiness"),
            "bundle.summary.packet_action_readiness",
        ),
        bundle_summary=_bundle_summary(bundle),
        blocker_count=0,
        boundary_error_count=0,
    )


def _build_missing_operator_packet_scenario() -> OperatorEvidenceBundleStressScenario:
    _bundle, _packet, stress, _sources = _clean_bundle_payloads()
    return _error_scenario(
        scenario_id="missing_operator_packet",
        title="Missing operator packet blocks bundle construction",
        purpose="Prove absent packet evidence is exposed as boundary error.",
        operation=lambda: build_operator_evidence_bundle({}, stress),
    )


def _build_mutating_operator_packet_scenario() -> OperatorEvidenceBundleStressScenario:
    _bundle, packet, stress, _sources = _clean_bundle_payloads()
    bad_packet = _deep_copy(packet)
    bad_packet["state_change"] = "canonical-mutation"
    return _error_scenario(
        scenario_id="mutating_operator_packet",
        title="Mutating operator packet is rejected",
        purpose="Prove state-changing packet evidence cannot enter the bundle.",
        operation=lambda: build_operator_evidence_bundle(bad_packet, stress),
    )


def _build_malformed_stress_matrix_scenario() -> OperatorEvidenceBundleStressScenario:
    _bundle, packet, stress, _sources = _clean_bundle_payloads()
    bad_stress = _deep_copy(stress)
    bad_stress["guardrails"]["stress_matrix_is_not_permission"] = False
    return _error_scenario(
        scenario_id="malformed_stress_matrix",
        title="Malformed stress matrix guardrail is rejected",
        purpose="Prove guardrail failure cannot be hidden inside the bundle.",
        operation=lambda: build_operator_evidence_bundle(packet, bad_stress),
    )


def _build_mutating_source_artifact_scenario() -> OperatorEvidenceBundleStressScenario:
    _bundle, packet, stress, _sources = _clean_bundle_payloads()
    mutating_source = {"state_change": "canonical-mutation"}
    return _error_scenario(
        scenario_id="mutating_source_artifact",
        title="Mutating source artifact is rejected",
        purpose="Prove source artifact digests cannot smuggle state-changing evidence.",
        operation=lambda: build_operator_evidence_bundle(
            packet,
            stress,
            {"mutating_source_artifact": mutating_source},
        ),
    )


def _build_duplicate_input_id_scenario() -> OperatorEvidenceBundleStressScenario:
    _bundle, packet, stress, _sources = _clean_bundle_payloads()
    valid_bundle = build_operator_evidence_bundle(packet, stress)
    duplicate = valid_bundle.inputs[0]
    return _error_scenario(
        scenario_id="duplicate_input_id",
        title="Duplicate input artifact ids are rejected",
        purpose="Prove input identity collision cannot make bundle evidence ambiguous.",
        operation=lambda: OperatorEvidenceBundleReport(
            packet_recommended_human_decision=valid_bundle.packet_recommended_human_decision,
            packet_action_readiness=valid_bundle.packet_action_readiness,
            packet_conformance_passed=valid_bundle.packet_conformance_passed,
            stress_scenario_count=valid_bundle.stress_scenario_count,
            stress_pass_count=valid_bundle.stress_pass_count,
            stress_fail_count=valid_bundle.stress_fail_count,
            stress_all_scenarios_passed=valid_bundle.stress_all_scenarios_passed,
            boundary_error_count=valid_bundle.boundary_error_count,
            inputs=(duplicate, duplicate),
        ),
    )


def _build_digest_summary_mismatch_scenario() -> OperatorEvidenceBundleStressScenario:
    clean_bundle, packet, stress, sources = _clean_bundle_payloads()
    mutated_bundle = _deep_copy(clean_bundle)
    input_rows = _list_of_mappings(mutated_bundle.get("inputs"), "bundle.inputs")
    input_rows[0]["digest"] = "0" * 64
    input_rows[0]["summary"] = "decision=none; readiness=blocked; conformance_passed=false"
    mutated_bundle["inputs"] = input_rows
    expected_payloads = {
        "operator_decision_packet": packet,
        "operator_packet_stress_matrix": stress,
        **sources,
    }
    expected_summaries = {
        item["artifact_id"]: item["summary"]
        for item in _list_of_mappings(clean_bundle.get("inputs"), "clean_bundle.inputs")
    }
    return _error_scenario(
        scenario_id="digest_summary_mismatch",
        title="Digest and summary mismatch is rejected",
        purpose="Prove stale or tampered bundle input rows are visible blockers.",
        operation=lambda: _validate_bundle_against_expected_payloads(
            mutated_bundle,
            expected_payloads,
            expected_summaries,
        ),
    )


def _error_scenario(
    *,
    scenario_id: str,
    title: str,
    purpose: str,
    operation: Any,
) -> OperatorEvidenceBundleStressScenario:
    try:
        operation()
    except ValueError as exc:
        return OperatorEvidenceBundleStressScenario(
            scenario_id=scenario_id,
            title=title,
            purpose=purpose,
            expected_recommended_human_decision="review_blockers",
            expected_action_readiness="blocked",
            observed_recommended_human_decision="review_blockers",
            observed_action_readiness="blocked",
            bundle_summary="bundle input rejected before advisory handoff could hide degraded evidence",
            blocker_count=1,
            boundary_error_count=1,
            expected_error=True,
            observed_error=str(exc),
        )
    raise ValueError(f"{scenario_id} did not expose degraded bundle input")


def _clean_bundle_payloads() -> tuple[
    dict[str, Any],
    dict[str, Any],
    dict[str, Any],
    dict[str, dict[str, Any]],
]:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    conformance = evaluate_decision_taxonomy_conformance()
    packet = build_operator_decision_packet(
        handoff.to_dict(),
        conformance.to_dict(),
        drift_policy,
        lifecycle,
    ).to_dict()
    stress = build_operator_packet_stress_matrix().to_dict()
    sources = {
        "baseline_lifecycle": lifecycle,
        "decision_taxonomy_conformance": conformance.to_dict(),
        "drift_policy": drift_policy,
        "metacognitive_handoff": handoff.to_dict(),
    }
    bundle = build_operator_evidence_bundle(packet, stress, sources).to_dict()
    return bundle, packet, stress, sources


def _validate_bundle_against_expected_payloads(
    bundle_payload: Mapping[str, Any],
    expected_payloads: Mapping[str, Mapping[str, Any]],
    expected_summaries: Mapping[str, str],
) -> None:
    bundle = _mapping(bundle_payload, "bundle")
    if bundle.get("schema_version") != OPERATOR_EVIDENCE_BUNDLE_SCHEMA_VERSION:
        raise ValueError(f"unsupported bundle schema_version: {bundle.get('schema_version')}")
    if bundle.get("state_change") != "none":
        raise ValueError("bundle must declare state_change = none")
    if bundle.get("authority") != OPERATOR_EVIDENCE_BUNDLE_AUTHORITY:
        raise ValueError(f"unsupported bundle authority: {bundle.get('authority')}")

    input_rows = _list_of_mappings(bundle.get("inputs"), "bundle.inputs")
    rows_by_id = {row.get("artifact_id"): row for row in input_rows}
    if len(rows_by_id) != len(input_rows):
        raise ValueError("operator evidence bundle input artifact ids must be unique")

    errors: list[str] = []
    for artifact_id, expected_payload in sorted(expected_payloads.items()):
        row = _mapping(rows_by_id.get(artifact_id), f"bundle.inputs.{artifact_id}")
        expected_digest = _stable_digest(expected_payload)
        if row.get("digest") != expected_digest:
            errors.append(f"digest mismatch for {artifact_id}")
        expected_summary = expected_summaries.get(artifact_id)
        if expected_summary and row.get("summary") != expected_summary:
            errors.append(f"summary mismatch for {artifact_id}")
    if errors:
        raise ValueError("operator evidence bundle digest/summary mismatch: " + "; ".join(errors))


def _bundle_summary(bundle: Mapping[str, Any]) -> str:
    summary = _mapping(bundle.get("summary"), "bundle.summary")
    return (
        f"decision={summary['packet_recommended_human_decision']}; "
        f"readiness={summary['packet_action_readiness']}; "
        f"input_count={summary['input_count']}; "
        f"source_artifact_count={summary['source_artifact_count']}; "
        f"stress_boundary_errors={summary['boundary_error_count']}"
    )


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


def _deep_copy(payload: Mapping[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(payload))


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return dict(value)


def _list_of_mappings(value: Any, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be JSON objects")
        result.append(dict(item))
    return result


def _string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value
