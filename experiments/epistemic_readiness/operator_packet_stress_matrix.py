from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .baseline_lifecycle import evaluate_baseline_lifecycle
from .decision_taxonomy_conformance import evaluate_decision_taxonomy_conformance
from .diff import compare_decision_traces
from .drift_policy import evaluate_drift_policy
from .metacognitive_handoff import evaluate_metacognitive_handoff
from .operator_decision_packet import OperatorDecisionPacket, build_operator_decision_packet
from .self_audit import audit_protocol_from_trace_diff
from .trace import TRACE_AUTHORITY, TRACE_SCHEMA_VERSION


OPERATOR_PACKET_STRESS_MATRIX_SCHEMA_VERSION = "1"
OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory operator packet stress matrix evidence only"
)

_SCENARIO_IDS = (
    "clean_no_action",
    "handoff_human_review",
    "conformance_failure",
    "drift_review_required",
    "lifecycle_blocker",
    "malformed_boundary",
)


@dataclass(frozen=True)
class OperatorPacketStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    observed_recommended_human_decision: str
    observed_action_readiness: str
    packet_summary: str
    blocker_count: int
    missing_evidence_count: int
    expected_error: bool = False
    observed_error: str = ""
    state_change: str = "none"
    authority: str = OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown operator packet stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("operator packet stress scenarios must not change state")
        if self.authority != OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported stress scenario authority: {self.authority}")
        if not self.packet_summary:
            raise ValueError("operator packet stress scenarios require packet_summary")
        if self.blocker_count < 0:
            raise ValueError("blocker_count must be non-negative")
        if self.missing_evidence_count < 0:
            raise ValueError("missing_evidence_count must be non-negative")
        if self.observed_action_readiness == "blocked" and not (
            self.blocker_count or self.observed_error
        ):
            raise ValueError("blocked stress scenarios must expose blockers or boundary errors")

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
            "packet_summary": self.packet_summary,
            "blocker_count": self.blocker_count,
            "missing_evidence_count": self.missing_evidence_count,
            "forbidden_interpretations": [
                "treat packet output as permission",
                "hide degraded evidence",
                "hide malformed boundary input",
                "infer negative evidence from silence",
            ],
        }


@dataclass(frozen=True)
class OperatorPacketStressMatrixReport:
    scenarios: tuple[OperatorPacketStressScenario, ...]
    state_change: str = "none"
    authority: str = OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence operator packet stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator packet stress matrix must not change state")
        if self.authority != OPERATOR_PACKET_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("operator packet stress matrix scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "operator packet stress matrix must contain the closed scenario set "
                "in stable order"
            )
        for scenario in self.scenarios:
            if scenario.state_change != "none":
                raise ValueError("operator packet stress scenarios must preserve state_change none")

    @property
    def pass_count(self) -> int:
        return sum(1 for scenario in self.scenarios if scenario.passed)

    @property
    def fail_count(self) -> int:
        return len(self.scenarios) - self.pass_count

    @property
    def all_scenarios_passed(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_PACKET_STRESS_MATRIX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "matrix_role": self.matrix_role,
            "summary": {
                "scenario_count": len(self.scenarios),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "all_scenarios_passed": self.all_scenarios_passed,
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
                "stress_matrix_is_not_permission": True,
                "stress_matrix_is_not_memory": True,
                "stress_matrix_is_not_authority": True,
                "stress_matrix_is_not_runtime_gate": True,
                "stress_matrix_is_not_claim_graph": True,
                "operator_packet_output_is_not_permission": True,
                "passing_scenario_is_not_permission": True,
                "malformed_boundary_is_blocking_evidence": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare operator packet output under degraded evidence",
                    "show which degraded evidence requires human review",
                    "show which degraded evidence blocks action",
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
                    "treat packet output as permission",
                    "treat passing scenarios as permission",
                    "hide blockers",
                    "hide malformed boundary input",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_packet_stress_matrix() -> OperatorPacketStressMatrixReport:
    scenarios = (
        _build_clean_scenario(),
        _build_handoff_human_review_scenario(),
        _build_conformance_failure_scenario(),
        _build_drift_review_scenario(),
        _build_lifecycle_blocker_scenario(),
        _build_malformed_boundary_scenario(),
    )
    return OperatorPacketStressMatrixReport(scenarios=scenarios)


def render_operator_packet_stress_matrix_json(
    report: OperatorPacketStressMatrixReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_packet_stress_matrix_markdown(
    report: OperatorPacketStressMatrixReport,
) -> str:
    lines = [
        "# Epistemic Readiness Operator Packet Stress Matrix",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- matrix_role: {report.matrix_role}",
        "- stress_matrix_is_not_permission: true",
        "- stress_matrix_is_not_memory: true",
        "- stress_matrix_is_not_authority: true",
        "- stress_matrix_is_not_runtime_gate: true",
        "- stress_matrix_is_not_claim_graph: true",
        "- operator_packet_output_is_not_permission: true",
        "- passing_scenario_is_not_permission: true",
        "- malformed_boundary_is_blocking_evidence: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: `{len(report.scenarios)}`",
        f"- pass_count: `{report.pass_count}`",
        f"- fail_count: `{report.fail_count}`",
        f"- all_scenarios_passed: `{str(report.all_scenarios_passed).lower()}`",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Expected Decision | Observed Decision | Expected Readiness | Observed Readiness | Boundary Error | Pass |",
        "|---|---|---|---|---|---|---|",
    ]
    for scenario in report.scenarios:
        passed = "yes" if scenario.passed else "no"
        error = "yes" if scenario.observed_error else "no"
        lines.append(
            f"| `{scenario.scenario_id}` | "
            f"`{scenario.expected_recommended_human_decision}` | "
            f"`{scenario.observed_recommended_human_decision}` | "
            f"`{scenario.expected_action_readiness}` | "
            f"`{scenario.observed_action_readiness}` | "
            f"{error} | {passed} |"
        )
    lines.extend(["", "## Scenario Details", ""])
    for scenario in report.scenarios:
        lines.extend(
            [
                f"### {scenario.scenario_id}",
                "",
                f"- title: {scenario.title}",
                f"- purpose: {scenario.purpose}",
                f"- observed_decision: `{scenario.observed_recommended_human_decision}`",
                f"- observed_readiness: `{scenario.observed_action_readiness}`",
                f"- blocker_count: `{scenario.blocker_count}`",
                f"- missing_evidence_count: `{scenario.missing_evidence_count}`",
                f"- boundary_error: `{scenario.observed_error or 'none'}`",
                f"- passed: `{str(scenario.passed).lower()}`",
                f"- packet_summary: {scenario.packet_summary}",
                "",
            ]
        )
    lines.extend(
        [
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat packet output as permission",
            "- treat passing scenarios as permission",
            "- hide blockers",
            "- hide malformed boundary input",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _build_clean_scenario() -> OperatorPacketStressScenario:
    packet = _clean_packet()
    return _scenario_from_packet(
        scenario_id="clean_no_action",
        title="Clean evidence stays no-action",
        purpose="Prove clean advisory evidence asks for no human decision and grants no permission.",
        expected_decision="none",
        expected_readiness="no_action",
        packet=packet,
    )


def _build_handoff_human_review_scenario() -> OperatorPacketStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    trace["summary"]["ready_count"] = 0
    trace["summary"]["insufficient_count"] = 1
    trace["findings"][0]["sufficiency"] = "insufficient"
    trace["findings"][0]["operational_readiness"] = "needs_review"
    packet = _packet_from_payloads(trace, lifecycle, self_audit, drift_policy)
    return _scenario_from_packet(
        scenario_id="handoff_human_review",
        title="Insufficient handoff evidence asks for human review",
        purpose="Prove low sufficiency is preserved as missing evidence instead of permission.",
        expected_decision="provide_missing_evidence",
        expected_readiness="human_approval_required",
        packet=packet,
    )


def _build_conformance_failure_scenario() -> OperatorPacketStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    conformance = evaluate_decision_taxonomy_conformance().to_dict()
    conformance["summary"]["all_cases_passed"] = False
    conformance["summary"]["fail_count"] = 1
    conformance["summary"]["covered_pairs"] = []
    conformance["cases"][0]["conformance_passed"] = False
    conformance["cases"][0]["issues"] = ["synthetic conformance regression"]
    packet = build_operator_decision_packet(
        handoff.to_dict(),
        conformance,
        drift_policy,
        lifecycle,
    )
    return _scenario_from_packet(
        scenario_id="conformance_failure",
        title="Failed decision conformance blocks action",
        purpose="Prove incompatible taxonomy evidence remains visible as a blocker.",
        expected_decision="review_blockers",
        expected_readiness="blocked",
        packet=packet,
    )


def _build_drift_review_scenario() -> OperatorPacketStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    drift_policy["classification"] = "material_refresh_candidate"
    drift_policy["recommendation"] = "refresh_candidate_requires_human_approval"
    drift_policy["required_human_action"] = "approve_baseline_refresh"
    drift_policy["action_readiness"] = "human_approval_required"
    drift_policy["reasons"] = ["semantic drift requires human review: synthetic"]
    packet = _packet_from_payloads(trace, lifecycle, self_audit, drift_policy)
    return _scenario_from_packet(
        scenario_id="drift_review_required",
        title="Material drift asks for baseline refresh approval",
        purpose="Prove drift can request approval without refreshing or mutating anything.",
        expected_decision="approve_baseline_refresh",
        expected_readiness="human_approval_required",
        packet=packet,
    )


def _build_lifecycle_blocker_scenario() -> OperatorPacketStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    lifecycle["recommendation"] = "refresh_blocked"
    lifecycle["required_human_action"] = "review_blockers"
    lifecycle["action_readiness"] = "blocked"
    lifecycle["regression"]["has_regression"] = True
    lifecycle["regression"]["reasons"] = ["synthetic lifecycle regression"]
    packet = _packet_from_payloads(trace, lifecycle, self_audit, drift_policy)
    return _scenario_from_packet(
        scenario_id="lifecycle_blocker",
        title="Baseline lifecycle blocker stops action",
        purpose="Prove lifecycle blockers dominate normal approval and stop the packet.",
        expected_decision="review_blockers",
        expected_readiness="blocked",
        packet=packet,
    )


def _build_malformed_boundary_scenario() -> OperatorPacketStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    conformance = evaluate_decision_taxonomy_conformance()
    malformed_drift = _deep_copy(drift_policy)
    malformed_drift["guardrails"]["drift_policy_is_not_permission"] = False
    try:
        build_operator_decision_packet(
            handoff.to_dict(),
            conformance.to_dict(),
            malformed_drift,
            lifecycle,
        )
    except ValueError as exc:
        return OperatorPacketStressScenario(
            scenario_id="malformed_boundary",
            title="Malformed boundary input is rejected",
            purpose="Prove false guardrails degrade to blocked review instead of silent pass.",
            expected_recommended_human_decision="review_blockers",
            expected_action_readiness="blocked",
            observed_recommended_human_decision="review_blockers",
            observed_action_readiness="blocked",
            packet_summary=f"Boundary rejected before packet construction: {exc}",
            blocker_count=1,
            missing_evidence_count=0,
            expected_error=True,
            observed_error=str(exc),
        )
    raise ValueError("malformed boundary scenario unexpectedly constructed a packet")


def _scenario_from_packet(
    *,
    scenario_id: str,
    title: str,
    purpose: str,
    expected_decision: str,
    expected_readiness: str,
    packet: OperatorDecisionPacket,
) -> OperatorPacketStressScenario:
    if packet.state_change != "none":
        raise ValueError("operator packet stress packet must preserve state_change none")
    return OperatorPacketStressScenario(
        scenario_id=scenario_id,
        title=title,
        purpose=purpose,
        expected_recommended_human_decision=expected_decision,
        expected_action_readiness=expected_readiness,
        observed_recommended_human_decision=packet.recommended_human_decision,
        observed_action_readiness=packet.action_readiness,
        packet_summary=packet.decision_summary,
        blocker_count=len(packet.blockers),
        missing_evidence_count=len(packet.missing_evidence),
    )


def _clean_packet() -> OperatorDecisionPacket:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    return _packet_from_payloads(trace, lifecycle, self_audit, drift_policy)


def _packet_from_payloads(
    trace: dict[str, Any],
    lifecycle: dict[str, Any],
    self_audit: dict[str, Any],
    drift_policy: dict[str, Any],
) -> OperatorDecisionPacket:
    handoff = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    conformance = evaluate_decision_taxonomy_conformance()
    return build_operator_decision_packet(
        handoff.to_dict(),
        conformance.to_dict(),
        drift_policy,
        lifecycle,
    )


def _clean_payloads() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    baseline_trace = _minimal_trace_payload()
    current_trace = _deep_copy(baseline_trace)
    diff = compare_decision_traces(baseline_trace, current_trace)
    self_audit = audit_protocol_from_trace_diff(diff.to_dict()).to_dict()
    lifecycle = evaluate_baseline_lifecycle(
        baseline_trace,
        current_trace,
        diff.to_dict(),
        self_audit,
    ).to_dict()
    drift_policy = evaluate_drift_policy(diff.to_dict(), self_audit, lifecycle).to_dict()
    return _deep_copy(current_trace), lifecycle, self_audit, drift_policy


def _minimal_trace_payload() -> dict[str, Any]:
    return {
        "schema_version": TRACE_SCHEMA_VERSION,
        "state_change": "none",
        "authority": TRACE_AUTHORITY,
        "trace_role": "advisory replay evidence only",
        "manifest": {
            "path": "synthetic/operator_packet_stress_matrix.toml",
            "schema_version": "1",
            "generated_report": "synthetic/report.md",
            "generated_trace": "synthetic/trace.json",
            "generator": "experiments.epistemic_readiness.operator_packet_stress_matrix",
            "renderer": "experiments.epistemic_readiness.operator_packet_stress_matrix",
            "trigger": (
                "FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_PACKET_"
                "STRESS_MATRIX_SLICE_19"
            ),
            "source_count": 1,
            "action_id": "operator-packet-stress-matrix",
        },
        "summary": {
            "action_readiness": "derived_experiment_allowed",
            "source_count": 1,
            "candidates_extracted": 1,
            "findings_evaluated": 1,
            "ready_count": 1,
            "blocked_count": 0,
            "insufficient_count": 0,
        },
        "guardrails": {
            "registered_is_not_true": True,
            "retrieved_is_not_relevant": True,
            "remembered_is_not_trusted": True,
            "silence_is_not_negative_evidence": True,
            "report_readiness_is_not_permission": True,
            "risk_readiness_is_not_permission": True,
            "trace_presence_is_not_permission": True,
            "manifest_presence_is_not_permission": True,
        },
        "source_reads": [
            {
                "path": "synthetic/operator_packet_stress_matrix.md",
                "role": "stress-fixture",
                "requested_max_lines": 40,
                "lines_read": 8,
                "bytes_read": 400,
                "truncated": False,
            }
        ],
        "candidates": [
            {
                "claim_id": "operator-packet-stress-claim-1",
                "source_path": "synthetic/operator_packet_stress_matrix.md",
                "evidence_span": "line 1",
                "subject": "operator decision packet",
                "predicate": "preserves degraded evidence boundary",
                "object": "yes",
                "polarity": "positive",
                "modality": "asserted",
                "criticality_hint": "high",
                "source_role": "stress-fixture",
                "authority_hint": "advisory",
                "extraction_basis": "synthetic bounded operator packet stress fixture",
            }
        ],
        "findings": [
            {
                "claim_id": "operator-packet-stress-claim-1",
                "authority": "advisory",
                "confidence": "high",
                "sufficiency": "sufficient",
                "conflict": "none",
                "supersession": "none",
                "staleness": "fresh",
                "operational_readiness": "ready",
                "reasons": ["synthetic clean operator packet stress fixture"],
            }
        ],
        "risk_assessment": {
            "action_id": "operator-packet-stress-matrix",
            "purpose": "stress operator packet degraded-evidence decisions",
            "zone": "zone_1",
            "risk_score": 1,
            "declared_gate_level": "G2",
            "required_gate_level": "G2",
            "budget_status": "within_budget",
            "budget_violations": [],
            "human_approval_required": False,
            "action_readiness": "derived_experiment_allowed",
            "stop_conditions": [],
            "state_change": "none",
            "authority": "non-authoritative; advisory risk evidence only",
        },
        "boundary": {
            "may_suggest": ["stress operator packet output"],
            "must_not_apply": [
                "mutate state",
                "treat operator packet stress output as permission",
            ],
        },
    }


def _deep_copy(value: dict[str, Any]) -> dict[str, Any]:
    return json.loads(json.dumps(value))

