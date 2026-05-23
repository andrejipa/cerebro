from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .baseline_lifecycle import BASELINE_LIFECYCLE_AUTHORITY, BASELINE_LIFECYCLE_SCHEMA_VERSION
from .drift_policy import DRIFT_POLICY_AUTHORITY, DRIFT_POLICY_SCHEMA_VERSION
from .metacognitive_handoff import (
    METACOGNITIVE_HANDOFF_AUTHORITY,
    MetacognitiveHandoffReport,
    evaluate_metacognitive_handoff,
)
from .self_audit import SELF_AUDIT_AUTHORITY, SELF_AUDIT_SCHEMA_VERSION
from .trace import TRACE_AUTHORITY, TRACE_SCHEMA_VERSION


HANDOFF_STRESS_MATRIX_SCHEMA_VERSION = "1"
HANDOFF_STRESS_MATRIX_AUTHORITY = (
    "non-authoritative; advisory handoff stress matrix evidence only"
)

_SCENARIO_IDS = (
    "clean_no_action",
    "insufficient_evidence",
    "active_conflict",
    "drift_review_required",
    "protocol_blocker",
)


@dataclass(frozen=True)
class HandoffStressScenario:
    scenario_id: str
    title: str
    purpose: str
    expected_recommended_human_decision: str
    expected_action_readiness: str
    handoff_report: MetacognitiveHandoffReport
    state_change: str = "none"
    authority: str = HANDOFF_STRESS_MATRIX_AUTHORITY

    def __post_init__(self) -> None:
        if self.scenario_id not in _SCENARIO_IDS:
            raise ValueError(f"unknown stress scenario: {self.scenario_id}")
        if self.state_change != "none":
            raise ValueError("handoff stress scenarios must not change state")
        if self.authority != HANDOFF_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported stress scenario authority: {self.authority}")
        if self.handoff_report.state_change != "none":
            raise ValueError("handoff report must not change state")
        if self.handoff_report.authority != METACOGNITIVE_HANDOFF_AUTHORITY:
            raise ValueError(f"unsupported handoff authority: {self.handoff_report.authority}")

    @property
    def observed_recommended_human_decision(self) -> str:
        return self.handoff_report.recommended_human_decision

    @property
    def observed_action_readiness(self) -> str:
        return self.handoff_report.action_readiness

    @property
    def passed(self) -> bool:
        return (
            self.observed_recommended_human_decision
            == self.expected_recommended_human_decision
            and self.observed_action_readiness == self.expected_action_readiness
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
            },
            "observed": {
                "recommended_human_decision": self.observed_recommended_human_decision,
                "action_readiness": self.observed_action_readiness,
            },
            "passed": self.passed,
            "handoff_summary": self.handoff_report.to_dict()["summary"],
            "signals": {
                "known": list(self.handoff_report.known),
                "unknown": list(self.handoff_report.unknown),
                "conflicts": list(self.handoff_report.conflicts),
                "missing_evidence": list(self.handoff_report.missing_evidence),
                "risk_notes": list(self.handoff_report.risk_notes),
            },
        }


@dataclass(frozen=True)
class HandoffStressMatrixReport:
    scenarios: tuple[HandoffStressScenario, ...]
    state_change: str = "none"
    authority: str = HANDOFF_STRESS_MATRIX_AUTHORITY
    matrix_role: str = "advisory degraded-evidence handoff stress matrix only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("handoff stress matrix must not change state")
        if self.authority != HANDOFF_STRESS_MATRIX_AUTHORITY:
            raise ValueError(f"unsupported stress matrix authority: {self.authority}")
        scenario_ids = tuple(scenario.scenario_id for scenario in self.scenarios)
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("handoff stress matrix scenario ids must be unique")
        if scenario_ids != _SCENARIO_IDS:
            raise ValueError(
                "handoff stress matrix must contain the closed scenario set in stable order"
            )

    @property
    def pass_count(self) -> int:
        return sum(1 for scenario in self.scenarios if scenario.passed)

    @property
    def fail_count(self) -> int:
        return len(self.scenarios) - self.pass_count

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": HANDOFF_STRESS_MATRIX_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "matrix_role": self.matrix_role,
            "summary": {
                "scenario_count": len(self.scenarios),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "scenario_ids": list(_SCENARIO_IDS),
                "decisions": {
                    scenario.scenario_id: {
                        "recommended_human_decision": (
                            scenario.observed_recommended_human_decision
                        ),
                        "action_readiness": scenario.observed_action_readiness,
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
                "passing_scenario_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "compare handoff output under degraded evidence",
                    "identify degraded evidence that requires human review",
                    "identify blocker evidence that must stop action",
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
                    "treat green scenarios as permission",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_handoff_stress_matrix() -> HandoffStressMatrixReport:
    scenarios = (
        _build_clean_scenario(),
        _build_insufficient_scenario(),
        _build_conflict_scenario(),
        _build_drift_review_scenario(),
        _build_protocol_blocker_scenario(),
    )
    return HandoffStressMatrixReport(scenarios=scenarios)


def render_handoff_stress_matrix_json(report: HandoffStressMatrixReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_handoff_stress_matrix_markdown(report: HandoffStressMatrixReport) -> str:
    lines = [
        "# Epistemic Readiness Handoff Stress Matrix",
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
        "- passing_scenario_is_not_permission: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: `{len(report.scenarios)}`",
        f"- pass_count: `{report.pass_count}`",
        f"- fail_count: `{report.fail_count}`",
        "",
        "## Scenario Matrix",
        "",
        "| Scenario | Expected Decision | Observed Decision | Expected Readiness | Observed Readiness | Pass |",
        "|---|---|---|---|---|---|",
    ]
    for scenario in report.scenarios:
        passed = "yes" if scenario.passed else "no"
        lines.append(
            f"| `{scenario.scenario_id}` | "
            f"`{scenario.expected_recommended_human_decision}` | "
            f"`{scenario.observed_recommended_human_decision}` | "
            f"`{scenario.expected_action_readiness}` | "
            f"`{scenario.observed_action_readiness}` | {passed} |"
        )
    lines.extend(["", "## Scenario Details", ""])
    for scenario in report.scenarios:
        lines.extend(
            [
                f"### {scenario.scenario_id}",
                "",
                f"- title: {scenario.title}",
                f"- purpose: {scenario.purpose}",
                f"- recommended_human_decision: `{scenario.observed_recommended_human_decision}`",
                f"- action_readiness: `{scenario.observed_action_readiness}`",
                f"- passed: `{str(scenario.passed).lower()}`",
                "",
                "Missing evidence:",
                "",
            ]
        )
        if scenario.handoff_report.missing_evidence:
            lines.extend(
                f"- {item}" for item in scenario.handoff_report.missing_evidence
            )
        else:
            lines.append("- none")
        lines.extend(["", "Conflicts:", ""])
        if scenario.handoff_report.conflicts:
            lines.extend(f"- {item}" for item in scenario.handoff_report.conflicts)
        else:
            lines.append("- none")
        lines.append("")
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
            "- treat green scenarios as permission",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _build_clean_scenario() -> HandoffStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    return HandoffStressScenario(
        scenario_id="clean_no_action",
        title="Clean evidence produces no human decision",
        purpose="Prove the handoff can say no action when all evidence is clean.",
        expected_recommended_human_decision="none",
        expected_action_readiness="no_action",
        handoff_report=report,
    )


def _build_insufficient_scenario() -> HandoffStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    trace["summary"]["insufficient_count"] = 1
    trace["summary"]["ready_count"] = 0
    trace["findings"][0]["sufficiency"] = "insufficient"
    trace["findings"][0]["operational_readiness"] = "needs_review"
    report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    return HandoffStressScenario(
        scenario_id="insufficient_evidence",
        title="Insufficient evidence asks for missing evidence",
        purpose="Prove low sufficiency is not treated as permission to continue.",
        expected_recommended_human_decision="provide_missing_evidence",
        expected_action_readiness="human_approval_required",
        handoff_report=report,
    )


def _build_conflict_scenario() -> HandoffStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    trace["findings"][0]["conflict"] = "active"
    report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    return HandoffStressScenario(
        scenario_id="active_conflict",
        title="Active conflict asks for adjudication",
        purpose="Prove conflict dominates clean readiness and forces review.",
        expected_recommended_human_decision="adjudicate_conflict",
        expected_action_readiness="human_approval_required",
        handoff_report=report,
    )


def _build_drift_review_scenario() -> HandoffStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    lifecycle["recommendation"] = "refresh_candidate_requires_human_approval"
    lifecycle["required_human_action"] = "approve_baseline_refresh"
    lifecycle["action_readiness"] = "human_approval_required"
    drift_policy["classification"] = "material_refresh_candidate"
    drift_policy["recommendation"] = "refresh_candidate_requires_human_approval"
    drift_policy["required_human_action"] = "approve_baseline_refresh"
    drift_policy["action_readiness"] = "human_approval_required"
    report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    return HandoffStressScenario(
        scenario_id="drift_review_required",
        title="Material drift requires explicit baseline refresh approval",
        purpose="Prove drift evidence requests approval without refreshing anything.",
        expected_recommended_human_decision="approve_baseline_refresh",
        expected_action_readiness="human_approval_required",
        handoff_report=report,
    )


def _build_protocol_blocker_scenario() -> HandoffStressScenario:
    trace, lifecycle, self_audit, drift_policy = _clean_payloads()
    self_audit["candidate_count"] = 1
    self_audit["high_or_blocking_count"] = 1
    drift_policy["classification"] = "blocked_regression_or_protocol_risk"
    drift_policy["recommendation"] = "refresh_blocked_pending_review"
    drift_policy["required_human_action"] = "review_blockers"
    drift_policy["action_readiness"] = "blocked"
    report = evaluate_metacognitive_handoff(trace, lifecycle, self_audit, drift_policy)
    return HandoffStressScenario(
        scenario_id="protocol_blocker",
        title="Protocol blocker stops action",
        purpose="Prove protocol risk blocks action instead of asking for normal approval.",
        expected_recommended_human_decision="review_blockers",
        expected_action_readiness="blocked",
        handoff_report=report,
    )


def _clean_payloads() -> tuple[dict[str, Any], dict[str, Any], dict[str, Any], dict[str, Any]]:
    trace = {
        "schema_version": TRACE_SCHEMA_VERSION,
        "state_change": "none",
        "authority": TRACE_AUTHORITY,
        "trace_role": "advisory replay evidence only",
        "manifest": {
            "path": "synthetic/handoff_stress_matrix.toml",
            "schema_version": "1",
            "generated_report": "synthetic/report.md",
            "generated_trace": "synthetic/trace.json",
            "generator": "experiments.epistemic_readiness.handoff_stress_matrix",
            "renderer": "experiments.epistemic_readiness.handoff_stress_matrix",
            "trigger": "FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_HANDOFF_STRESS_MATRIX_SLICE_15",
            "source_count": 1,
            "action_id": "handoff-stress-matrix",
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
                "path": "synthetic/handoff_stress_matrix.md",
                "role": "stress-fixture",
                "requested_max_lines": 40,
                "lines_read": 8,
                "bytes_read": 400,
                "truncated": False,
            }
        ],
        "candidates": [
            {
                "claim_id": "stress-claim-1",
                "source_path": "synthetic/handoff_stress_matrix.md",
                "evidence_span": "line 1",
                "subject": "handoff evaluator",
                "predicate": "preserves boundary",
                "object": "yes",
                "polarity": "positive",
                "modality": "asserted",
                "criticality_hint": "high",
                "source_role": "stress-fixture",
                "authority_hint": "advisory",
                "extraction_basis": "synthetic bounded stress fixture",
            }
        ],
        "findings": [
            {
                "claim_id": "stress-claim-1",
                "authority": "advisory",
                "confidence": "high",
                "sufficiency": "sufficient",
                "conflict": "none",
                "supersession": "none",
                "staleness": "fresh",
                "operational_readiness": "ready",
                "reasons": ["synthetic clean stress fixture"],
            }
        ],
        "risk_assessment": {
            "action_id": "handoff-stress-matrix",
            "purpose": "stress metacognitive handoff decisions",
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
            "may_suggest": ["stress handoff output"],
            "must_not_apply": ["mutate state", "treat stress output as permission"],
        },
    }
    lifecycle = {
        "schema_version": BASELINE_LIFECYCLE_SCHEMA_VERSION,
        "state_change": "none",
        "authority": BASELINE_LIFECYCLE_AUTHORITY,
        "recommendation": "baseline_already_current",
        "required_human_action": "none",
        "action_readiness": "no_action",
        "regression": {"has_regression": False, "reasons": []},
    }
    self_audit = {
        "schema_version": SELF_AUDIT_SCHEMA_VERSION,
        "state_change": "none",
        "authority": SELF_AUDIT_AUTHORITY,
        "candidate_count": 0,
        "high_or_blocking_count": 0,
    }
    drift_policy = {
        "schema_version": DRIFT_POLICY_SCHEMA_VERSION,
        "state_change": "none",
        "authority": DRIFT_POLICY_AUTHORITY,
        "classification": "no_drift",
        "recommendation": "no_action",
        "required_human_action": "none",
        "action_readiness": "no_action",
        "regression": {"has_regression": False, "reasons": []},
    }
    return trace, lifecycle, self_audit, drift_policy
