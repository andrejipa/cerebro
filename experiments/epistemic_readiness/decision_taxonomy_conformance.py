from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any

from .handoff_stress_matrix import (
    HANDOFF_STRESS_MATRIX_AUTHORITY,
    HandoffStressMatrixReport,
    build_handoff_stress_matrix,
)
from .human_decision_taxonomy import (
    HUMAN_DECISION_TAXONOMY_AUTHORITY,
    HumanDecisionTaxonomyReport,
    build_human_decision_taxonomy,
)


DECISION_TAXONOMY_CONFORMANCE_SCHEMA_VERSION = "1"
DECISION_TAXONOMY_CONFORMANCE_AUTHORITY = (
    "non-authoritative; advisory decision taxonomy conformance evidence only"
)


@dataclass(frozen=True)
class DecisionTaxonomyConformanceCase:
    scenario_id: str
    recommended_human_decision: str
    action_readiness: str
    taxonomy_compatible: bool
    stress_scenario_passed: bool
    escalation_level: str
    required_evidence: tuple[str, ...]
    allowed_next_actions: tuple[str, ...]
    forbidden_interpretations: tuple[str, ...]
    issues: tuple[str, ...]
    state_change: str = "none"
    authority: str = DECISION_TAXONOMY_CONFORMANCE_AUTHORITY

    def __post_init__(self) -> None:
        if not self.scenario_id:
            raise ValueError("conformance case scenario_id must be non-empty")
        if not self.recommended_human_decision:
            raise ValueError("conformance case decision must be non-empty")
        if not self.action_readiness:
            raise ValueError("conformance case action_readiness must be non-empty")
        if self.state_change != "none":
            raise ValueError("conformance cases must not change state")
        if self.authority != DECISION_TAXONOMY_CONFORMANCE_AUTHORITY:
            raise ValueError(f"unsupported conformance authority: {self.authority}")
        if "treat conformance pass as permission" not in self.forbidden_interpretations:
            raise ValueError("conformance cases must forbid treating pass as permission")

    @property
    def conformance_passed(self) -> bool:
        return self.taxonomy_compatible and self.stress_scenario_passed and not self.issues

    def to_dict(self) -> dict[str, Any]:
        return {
            "scenario_id": self.scenario_id,
            "recommended_human_decision": self.recommended_human_decision,
            "action_readiness": self.action_readiness,
            "taxonomy_compatible": self.taxonomy_compatible,
            "stress_scenario_passed": self.stress_scenario_passed,
            "conformance_passed": self.conformance_passed,
            "escalation_level": self.escalation_level,
            "required_evidence": list(self.required_evidence),
            "allowed_next_actions": list(self.allowed_next_actions),
            "forbidden_interpretations": list(self.forbidden_interpretations),
            "issues": list(self.issues),
            "state_change": self.state_change,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class DecisionTaxonomyConformanceReport:
    cases: tuple[DecisionTaxonomyConformanceCase, ...]
    state_change: str = "none"
    authority: str = DECISION_TAXONOMY_CONFORMANCE_AUTHORITY
    conformance_role: str = "advisory stress-matrix-to-taxonomy conformance evidence only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("decision taxonomy conformance report must not change state")
        if self.authority != DECISION_TAXONOMY_CONFORMANCE_AUTHORITY:
            raise ValueError(f"unsupported conformance report authority: {self.authority}")
        scenario_ids = tuple(case.scenario_id for case in self.cases)
        if not scenario_ids:
            raise ValueError("decision taxonomy conformance report requires cases")
        if len(set(scenario_ids)) != len(scenario_ids):
            raise ValueError("decision taxonomy conformance case ids must be unique")
        for case in self.cases:
            if case.state_change != "none":
                raise ValueError("conformance cases must preserve state_change none")

    @property
    def pass_count(self) -> int:
        return sum(1 for case in self.cases if case.conformance_passed)

    @property
    def fail_count(self) -> int:
        return len(self.cases) - self.pass_count

    @property
    def all_cases_passed(self) -> bool:
        return self.fail_count == 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DECISION_TAXONOMY_CONFORMANCE_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "conformance_role": self.conformance_role,
            "summary": {
                "case_count": len(self.cases),
                "pass_count": self.pass_count,
                "fail_count": self.fail_count,
                "all_cases_passed": self.all_cases_passed,
                "covered_pairs": [
                    {
                        "scenario_id": case.scenario_id,
                        "recommended_human_decision": case.recommended_human_decision,
                        "action_readiness": case.action_readiness,
                    }
                    for case in self.cases
                    if case.conformance_passed
                ],
            },
            "cases": [case.to_dict() for case in self.cases],
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "conformance_is_not_permission": True,
                "conformance_is_not_memory": True,
                "conformance_is_not_authority": True,
                "conformance_is_not_runtime_gate": True,
                "conformance_is_not_claim_graph": True,
                "covered_pair_is_not_permission": True,
                "incompatible_pair_must_be_visible": True,
            },
            "boundary": {
                "may_suggest": [
                    "verify stress-matrix decision/readiness pairs are covered by the taxonomy",
                    "surface incompatible pairs for future hardening",
                    "recommend a future corrective trigger when coverage fails",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat conformance pass as permission",
                    "hide incompatible pairs",
                    "infer negative evidence from silence",
                ],
            },
        }


def evaluate_decision_taxonomy_conformance(
    stress_matrix: HandoffStressMatrixReport | None = None,
    taxonomy: HumanDecisionTaxonomyReport | None = None,
) -> DecisionTaxonomyConformanceReport:
    matrix = stress_matrix if stress_matrix is not None else build_handoff_stress_matrix()
    taxonomy_report = taxonomy if taxonomy is not None else build_human_decision_taxonomy()
    _validate_inputs(matrix, taxonomy_report)

    cases = tuple(
        _evaluate_scenario(
            scenario_id=scenario.scenario_id,
            decision=scenario.observed_recommended_human_decision,
            readiness=scenario.observed_action_readiness,
            stress_scenario_passed=scenario.passed,
            taxonomy=taxonomy_report,
        )
        for scenario in matrix.scenarios
    )
    return DecisionTaxonomyConformanceReport(cases=cases)


def render_decision_taxonomy_conformance_json(
    report: DecisionTaxonomyConformanceReport,
) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_decision_taxonomy_conformance_markdown(
    report: DecisionTaxonomyConformanceReport,
) -> str:
    lines = [
        "# Epistemic Readiness Decision Taxonomy Conformance",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- conformance_role: {report.conformance_role}",
        "- conformance_is_not_permission: true",
        "- covered_pair_is_not_permission: true",
        "- incompatible_pair_must_be_visible: true",
        "- conformance_is_not_memory: true",
        "- conformance_is_not_authority: true",
        "- conformance_is_not_runtime_gate: true",
        "- conformance_is_not_claim_graph: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- case_count: `{len(report.cases)}`",
        f"- pass_count: `{report.pass_count}`",
        f"- fail_count: `{report.fail_count}`",
        f"- all_cases_passed: `{str(report.all_cases_passed).lower()}`",
        "",
        "## Conformance Matrix",
        "",
        "| Scenario | Decision | Readiness | Compatible | Stress Passed | Conformance | Issues |",
        "|---|---|---|---|---|---|---|",
    ]
    for case in report.cases:
        issues = "; ".join(case.issues) if case.issues else "none"
        lines.append(
            f"| `{case.scenario_id}` | "
            f"`{case.recommended_human_decision}` | "
            f"`{case.action_readiness}` | "
            f"`{str(case.taxonomy_compatible).lower()}` | "
            f"`{str(case.stress_scenario_passed).lower()}` | "
            f"`{str(case.conformance_passed).lower()}` | "
            f"{issues} |"
        )
    lines.extend(["", "## Case Details", ""])
    for case in report.cases:
        lines.extend(
            [
                f"### {case.scenario_id}",
                "",
                f"- recommended_human_decision: `{case.recommended_human_decision}`",
                f"- action_readiness: `{case.action_readiness}`",
                f"- escalation_level: `{case.escalation_level}`",
                f"- taxonomy_compatible: `{str(case.taxonomy_compatible).lower()}`",
                f"- stress_scenario_passed: `{str(case.stress_scenario_passed).lower()}`",
                f"- conformance_passed: `{str(case.conformance_passed).lower()}`",
                "",
                "Required evidence:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in case.required_evidence)
        lines.extend(["", "Allowed next actions:", ""])
        lines.extend(f"- {item}" for item in case.allowed_next_actions)
        lines.extend(["", "Issues:", ""])
        if case.issues:
            lines.extend(f"- {item}" for item in case.issues)
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
            "- treat conformance pass as permission",
            "- hide incompatible pairs",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_inputs(
    matrix: HandoffStressMatrixReport,
    taxonomy: HumanDecisionTaxonomyReport,
) -> None:
    if matrix.state_change != "none":
        raise ValueError("handoff stress matrix must preserve state_change none")
    if matrix.authority != HANDOFF_STRESS_MATRIX_AUTHORITY:
        raise ValueError(f"unsupported stress matrix authority: {matrix.authority}")
    if taxonomy.state_change != "none":
        raise ValueError("human decision taxonomy must preserve state_change none")
    if taxonomy.authority != HUMAN_DECISION_TAXONOMY_AUTHORITY:
        raise ValueError(f"unsupported human decision taxonomy authority: {taxonomy.authority}")


def _evaluate_scenario(
    *,
    scenario_id: str,
    decision: str,
    readiness: str,
    stress_scenario_passed: bool,
    taxonomy: HumanDecisionTaxonomyReport,
) -> DecisionTaxonomyConformanceCase:
    issues: list[str] = []
    try:
        interpretation = taxonomy.interpret(decision, readiness)
        taxonomy_compatible = interpretation.compatible
        escalation_level = interpretation.escalation_level
        required_evidence = interpretation.required_evidence
        allowed_next_actions = interpretation.allowed_next_actions
        forbidden_interpretations = interpretation.forbidden_interpretations
        issues.extend(interpretation.issues)
    except ValueError as exc:
        taxonomy_compatible = False
        escalation_level = "uncovered"
        required_evidence = ("taxonomy entry for decision/readiness pair",)
        allowed_next_actions = ("open a corrective trigger before using this pair",)
        forbidden_interpretations = (
            "treat decision as permission",
            "treat conformance pass as permission",
            "hide incompatible pairs",
        )
        issues.extend(
            (
                str(exc),
                "decision/readiness pair is not covered by taxonomy",
                "do not act from this pair without new evidence or human adjudication",
            )
        )
    if not stress_scenario_passed:
        issues.append("stress scenario expectation failed")
    if "treat conformance pass as permission" not in forbidden_interpretations:
        forbidden_interpretations = (
            *forbidden_interpretations,
            "treat conformance pass as permission",
        )
    return DecisionTaxonomyConformanceCase(
        scenario_id=scenario_id,
        recommended_human_decision=decision,
        action_readiness=readiness,
        taxonomy_compatible=taxonomy_compatible,
        stress_scenario_passed=stress_scenario_passed,
        escalation_level=escalation_level,
        required_evidence=required_evidence,
        allowed_next_actions=allowed_next_actions,
        forbidden_interpretations=forbidden_interpretations,
        issues=tuple(issues),
    )
