from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .operator_decision_packet import (
    OPERATOR_DECISION_PACKET_AUTHORITY,
    OPERATOR_DECISION_PACKET_SCHEMA_VERSION,
)
from .operator_packet_stress_matrix import (
    OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY,
    OPERATOR_PACKET_STRESS_MATRIX_SCHEMA_VERSION,
)


OPERATOR_EVIDENCE_BUNDLE_SCHEMA_VERSION = "1"
OPERATOR_EVIDENCE_BUNDLE_AUTHORITY = (
    "non-authoritative; advisory operator evidence bundle only"
)

_HEX_DIGITS = set("0123456789abcdef")


@dataclass(frozen=True)
class OperatorEvidenceBundleInput:
    artifact_id: str
    digest: str
    summary: str
    artifact_role: str = "advisory input evidence"
    state_change: str = "none"

    def __post_init__(self) -> None:
        if not self.artifact_id:
            raise ValueError("bundle input artifact_id must be non-empty")
        if not self.summary:
            raise ValueError("bundle input summary must be non-empty")
        if self.state_change != "none":
            raise ValueError("bundle inputs must preserve state_change none")
        if len(self.digest) != 64 or any(char not in _HEX_DIGITS for char in self.digest):
            raise ValueError("bundle input digest must be a lowercase sha256 hex digest")

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_role": self.artifact_role,
            "digest": self.digest,
            "summary": self.summary,
            "state_change": self.state_change,
        }


@dataclass(frozen=True)
class OperatorEvidenceBundleReport:
    packet_recommended_human_decision: str
    packet_action_readiness: str
    packet_conformance_passed: bool
    stress_scenario_count: int
    stress_pass_count: int
    stress_fail_count: int
    stress_all_scenarios_passed: bool
    boundary_error_count: int
    inputs: tuple[OperatorEvidenceBundleInput, ...]
    state_change: str = "none"
    authority: str = OPERATOR_EVIDENCE_BUNDLE_AUTHORITY
    bundle_role: str = "operator-facing advisory evidence bundle only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator evidence bundle must not change state")
        if self.authority != OPERATOR_EVIDENCE_BUNDLE_AUTHORITY:
            raise ValueError(f"unsupported operator evidence bundle authority: {self.authority}")
        if self.stress_scenario_count < 0:
            raise ValueError("stress_scenario_count must be non-negative")
        if self.stress_pass_count < 0:
            raise ValueError("stress_pass_count must be non-negative")
        if self.stress_fail_count < 0:
            raise ValueError("stress_fail_count must be non-negative")
        if self.boundary_error_count < 0:
            raise ValueError("boundary_error_count must be non-negative")
        if self.stress_pass_count + self.stress_fail_count != self.stress_scenario_count:
            raise ValueError("stress pass/fail counts must add up to scenario_count")
        artifact_ids = tuple(item.artifact_id for item in self.inputs)
        if len(set(artifact_ids)) != len(artifact_ids):
            raise ValueError("operator evidence bundle input artifact ids must be unique")
        required = {"operator_decision_packet", "operator_packet_stress_matrix"}
        if not required.issubset(set(artifact_ids)):
            raise ValueError("operator evidence bundle requires packet and stress matrix inputs")
        for item in self.inputs:
            if item.state_change != "none":
                raise ValueError("operator evidence bundle inputs must preserve state_change none")

    @property
    def input_count(self) -> int:
        return len(self.inputs)

    @property
    def source_artifact_count(self) -> int:
        return len(self.inputs) - 2

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_EVIDENCE_BUNDLE_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "bundle_role": self.bundle_role,
            "summary": {
                "packet_recommended_human_decision": self.packet_recommended_human_decision,
                "packet_action_readiness": self.packet_action_readiness,
                "packet_conformance_passed": self.packet_conformance_passed,
                "stress_scenario_count": self.stress_scenario_count,
                "stress_pass_count": self.stress_pass_count,
                "stress_fail_count": self.stress_fail_count,
                "stress_all_scenarios_passed": self.stress_all_scenarios_passed,
                "boundary_error_count": self.boundary_error_count,
                "input_count": self.input_count,
                "source_artifact_count": self.source_artifact_count,
            },
            "inputs": [item.to_dict() for item in self.inputs],
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "bundle_is_not_permission": True,
                "bundle_is_not_memory": True,
                "bundle_is_not_authority": True,
                "bundle_is_not_runtime_gate": True,
                "bundle_is_not_claim_graph": True,
                "digest_is_not_truth": True,
                "stress_pass_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "summarize current operator evidence",
                    "make cross-agent handoff cheaper",
                    "show source artifact digests for reproducibility",
                    "surface stress coverage and boundary errors",
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
                    "treat bundle as permission",
                    "treat digests as truth",
                    "hide stress failures",
                    "hide boundary errors",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_evidence_bundle(
    operator_packet: Mapping[str, Any],
    operator_packet_stress_matrix: Mapping[str, Any],
    source_artifacts: Mapping[str, Mapping[str, Any]] | None = None,
) -> OperatorEvidenceBundleReport:
    packet_payload = _validate_operator_packet(operator_packet)
    stress_payload = _validate_stress_matrix(operator_packet_stress_matrix)
    packet_summary = _mapping(packet_payload.get("summary"), "operator_packet.summary")
    stress_summary = _mapping(stress_payload.get("summary"), "stress_matrix.summary")

    inputs = [
        OperatorEvidenceBundleInput(
            artifact_id="operator_decision_packet",
            digest=_stable_digest(packet_payload),
            summary=(
                "decision="
                f"{packet_summary['recommended_human_decision']}; "
                f"readiness={packet_summary['action_readiness']}; "
                f"conformance_passed={str(packet_summary['conformance_passed']).lower()}"
            ),
        ),
        OperatorEvidenceBundleInput(
            artifact_id="operator_packet_stress_matrix",
            digest=_stable_digest(stress_payload),
            summary=(
                f"scenarios={stress_summary['scenario_count']}; "
                f"pass={stress_summary['pass_count']}; "
                f"fail={stress_summary['fail_count']}; "
                f"all_passed={str(stress_summary['all_scenarios_passed']).lower()}"
            ),
        ),
    ]

    for artifact_id, payload in sorted(dict(source_artifacts or {}).items()):
        source_payload = _validate_source_artifact(artifact_id, payload)
        inputs.append(
            OperatorEvidenceBundleInput(
                artifact_id=artifact_id,
                digest=_stable_digest(source_payload),
                summary=_source_summary(artifact_id, source_payload),
                artifact_role="source advisory artifact digest",
            )
        )

    return OperatorEvidenceBundleReport(
        packet_recommended_human_decision=_string_value(
            packet_summary.get("recommended_human_decision"),
            "operator_packet.summary.recommended_human_decision",
        ),
        packet_action_readiness=_string_value(
            packet_summary.get("action_readiness"),
            "operator_packet.summary.action_readiness",
        ),
        packet_conformance_passed=_bool_value(
            packet_summary.get("conformance_passed"),
            "operator_packet.summary.conformance_passed",
        ),
        stress_scenario_count=_int_value(
            stress_summary.get("scenario_count"),
            "stress_matrix.summary.scenario_count",
        ),
        stress_pass_count=_int_value(stress_summary.get("pass_count"), "stress_matrix.summary.pass_count"),
        stress_fail_count=_int_value(stress_summary.get("fail_count"), "stress_matrix.summary.fail_count"),
        stress_all_scenarios_passed=_bool_value(
            stress_summary.get("all_scenarios_passed"),
            "stress_matrix.summary.all_scenarios_passed",
        ),
        boundary_error_count=_boundary_error_count(stress_payload),
        inputs=tuple(inputs),
    )


def render_operator_evidence_bundle_json(report: OperatorEvidenceBundleReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_evidence_bundle_markdown(report: OperatorEvidenceBundleReport) -> str:
    lines = [
        "# Epistemic Readiness Operator Evidence Bundle",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- bundle_role: {report.bundle_role}",
        "- bundle_is_not_permission: true",
        "- bundle_is_not_memory: true",
        "- bundle_is_not_authority: true",
        "- bundle_is_not_runtime_gate: true",
        "- bundle_is_not_claim_graph: true",
        "- digest_is_not_truth: true",
        "- stress_pass_is_not_permission: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Operator Decision",
        "",
        f"- packet_recommended_human_decision: `{report.packet_recommended_human_decision}`",
        f"- packet_action_readiness: `{report.packet_action_readiness}`",
        f"- packet_conformance_passed: `{str(report.packet_conformance_passed).lower()}`",
        "",
        "## Stress Coverage",
        "",
        f"- stress_scenario_count: `{report.stress_scenario_count}`",
        f"- stress_pass_count: `{report.stress_pass_count}`",
        f"- stress_fail_count: `{report.stress_fail_count}`",
        f"- stress_all_scenarios_passed: `{str(report.stress_all_scenarios_passed).lower()}`",
        f"- boundary_error_count: `{report.boundary_error_count}`",
        "",
        "## Input Digests",
        "",
        "| Artifact | Role | Digest | Summary |",
        "|---|---|---|---|",
    ]
    for item in report.inputs:
        lines.append(
            f"| `{item.artifact_id}` | {item.artifact_role} | `{item.digest}` | {item.summary} |"
        )
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
            "- treat bundle as permission",
            "- treat digests as truth",
            "- hide stress failures",
            "- hide boundary errors",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_operator_packet(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="operator_packet",
        schema_version=OPERATOR_DECISION_PACKET_SCHEMA_VERSION,
        authority=OPERATOR_DECISION_PACKET_AUTHORITY,
    )
    summary = _mapping(result.get("summary"), "operator_packet.summary")
    for key in (
        "recommended_human_decision",
        "action_readiness",
        "decision_summary",
    ):
        _string_value(summary.get(key), f"operator_packet.summary.{key}")
    _bool_value(summary.get("conformance_passed"), "operator_packet.summary.conformance_passed")
    guardrails = _mapping(result.get("guardrails"), "operator_packet.guardrails")
    for guardrail in (
        "operator_packet_is_not_permission",
        "operator_packet_is_not_memory",
        "operator_packet_is_not_authority",
        "operator_packet_is_not_runtime_gate",
        "operator_packet_is_not_claim_graph",
        "conformance_pass_is_not_permission",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"operator packet guardrail missing or false: {guardrail}")
    return result


def _validate_stress_matrix(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="stress_matrix",
        schema_version=OPERATOR_PACKET_STRESS_MATRIX_SCHEMA_VERSION,
        authority=OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY,
    )
    summary = _mapping(result.get("summary"), "stress_matrix.summary")
    for key in ("scenario_count", "pass_count", "fail_count"):
        _int_value(summary.get(key), f"stress_matrix.summary.{key}")
    _bool_value(summary.get("all_scenarios_passed"), "stress_matrix.summary.all_scenarios_passed")
    _list_of_mappings(result.get("scenarios"), "stress_matrix.scenarios")
    guardrails = _mapping(result.get("guardrails"), "stress_matrix.guardrails")
    for guardrail in (
        "stress_matrix_is_not_permission",
        "stress_matrix_is_not_memory",
        "stress_matrix_is_not_authority",
        "stress_matrix_is_not_runtime_gate",
        "stress_matrix_is_not_claim_graph",
        "operator_packet_output_is_not_permission",
        "passing_scenario_is_not_permission",
        "malformed_boundary_is_blocking_evidence",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"stress matrix guardrail missing or false: {guardrail}")
    return result


def _validate_source_artifact(artifact_id: str, payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not artifact_id:
        raise ValueError("source artifact id must be non-empty")
    result = _mapping(payload, f"source_artifacts.{artifact_id}")
    if result.get("state_change", "none") != "none":
        raise ValueError(f"source artifact must preserve state_change none: {artifact_id}")
    return result


def _validate_common_payload(
    payload: Mapping[str, Any] | Any,
    *,
    field_name: str,
    schema_version: str,
    authority: str,
) -> dict[str, Any]:
    result = _mapping(payload, field_name)
    if result.get("schema_version") != schema_version:
        raise ValueError(f"unsupported {field_name} schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError(f"{field_name} must declare state_change = none")
    if result.get("authority") != authority:
        raise ValueError(f"unsupported {field_name} authority: {result.get('authority')}")
    return result


def _source_summary(artifact_id: str, payload: Mapping[str, Any]) -> str:
    schema = payload.get("schema_version", "unknown-schema")
    authority = payload.get("authority", "unknown-authority")
    state_change = payload.get("state_change", "none")
    return (
        f"{artifact_id}: schema={schema}; state_change={state_change}; "
        f"authority={authority}"
    )


def _boundary_error_count(stress_payload: Mapping[str, Any]) -> int:
    count = 0
    for scenario in _list_of_mappings(stress_payload.get("scenarios"), "stress_matrix.scenarios"):
        observed = _mapping(scenario.get("observed"), "stress_matrix.scenario.observed")
        if observed.get("boundary_error") is True:
            count += 1
    return count


def _stable_digest(payload: Mapping[str, Any]) -> str:
    rendered = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
    return hashlib.sha256(rendered.encode("utf-8")).hexdigest()


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


def _int_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _bool_value(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value
