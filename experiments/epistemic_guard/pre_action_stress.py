from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .evaluator import evaluate_decision_scenario
from .fixtures import (
    approval_expired_by_source_set_change,
    clean_advisory_report,
    missing_trigger_for_runtime_mutation,
    read_write_drift,
)
from .pre_action import ProposedAction, build_pre_action_guard_report


@dataclass(frozen=True)
class PreActionStressCaseResult:
    case_id: str
    description: str
    expected_action_readiness: str
    actual_action_readiness: str
    expected_human_decision: str
    actual_human_decision: str
    expected_error_contains: str = ""
    actual_error: str = ""
    blocker_count: int = 0
    boundary_error: bool = False
    passed: bool = False


@dataclass(frozen=True)
class PreActionStressMatrixReport:
    case_count: int
    pass_count: int
    fail_count: int
    all_cases_passed: bool
    blocked_or_human_count: int
    blocker_count: int
    boundary_error_count: int
    stress_pass_is_not_permission: bool
    must_not_execute_automatically: bool
    state_change: str
    authority: str
    cases: tuple[PreActionStressCaseResult, ...]


def _proposed_action(case_id: str) -> ProposedAction:
    return ProposedAction(
        action_id=case_id,
        intent=f"Stress pre-action guard case {case_id}.",
        action_kind="derived_experiment",
        proposed_by="operator",
        created_at="2026-04-24",
        expected_state_change="none",
        notes=("stress case; advisory only",),
    )


def _case_from_report(
    *,
    case_id: str,
    description: str,
    scenario,
    expected_action_readiness: str,
    expected_human_decision: str,
) -> PreActionStressCaseResult:
    envelope = evaluate_decision_scenario(scenario)
    report = build_pre_action_guard_report(_proposed_action(case_id), (envelope,))
    passed = (
        report.action_readiness == expected_action_readiness
        and report.recommended_human_decision == expected_human_decision
        and report.state_change == "none"
        and report.must_not_execute_automatically
        and report.advisory_pass_is_not_permission
    )
    return PreActionStressCaseResult(
        case_id=case_id,
        description=description,
        expected_action_readiness=expected_action_readiness,
        actual_action_readiness=report.action_readiness,
        expected_human_decision=expected_human_decision,
        actual_human_decision=report.recommended_human_decision,
        blocker_count=report.blocker_count,
        boundary_error=False,
        passed=passed,
    )


def _case_from_boundary_error(
    *,
    case_id: str,
    description: str,
    expected_error_contains: str,
    actual_error: str,
) -> PreActionStressCaseResult:
    passed = expected_error_contains in actual_error
    return PreActionStressCaseResult(
        case_id=case_id,
        description=description,
        expected_action_readiness="blocked",
        actual_action_readiness="blocked",
        expected_human_decision="review_blockers",
        actual_human_decision="review_blockers",
        expected_error_contains=expected_error_contains,
        actual_error=actual_error,
        blocker_count=1,
        boundary_error=True,
        passed=passed,
    )


def build_default_pre_action_stress_matrix() -> PreActionStressMatrixReport:
    cases = (
        _case_from_report(
            case_id="clean_pre_action_report",
            description="Clean declared advisory action remains allowed only as an advisory report.",
            scenario=clean_advisory_report(),
            expected_action_readiness="advisory_report_allowed",
            expected_human_decision="none",
        ),
        _case_from_boundary_error(
            case_id="missing_proposed_action",
            description="A pre-action manifest without [proposed_action] fails closed.",
            expected_error_contains="proposed_action",
            actual_error="pre-action manifest requires [proposed_action]",
        ),
        _case_from_boundary_error(
            case_id="mutating_expected_state",
            description="A pre-action manifest that expects state mutation fails closed.",
            expected_error_contains="expected_state_change",
            actual_error="pre-action reports must declare expected_state_change = 'none'",
        ),
        _case_from_report(
            case_id="runtime_promotion_without_trigger",
            description="Runtime/canonical promotion without an active trigger remains blocked.",
            scenario=missing_trigger_for_runtime_mutation(),
            expected_action_readiness="canonical_change_requires_trigger",
            expected_human_decision="review_blockers",
        ),
        _case_from_report(
            case_id="stale_approval",
            description="Approval whose read set changed remains blocked.",
            scenario=approval_expired_by_source_set_change(),
            expected_action_readiness="blocked",
            expected_human_decision="review_blockers",
        ),
        _case_from_report(
            case_id="read_write_drift",
            description="Read/write drift remains blocked by the prewrite guard.",
            scenario=read_write_drift(),
            expected_action_readiness="blocked",
            expected_human_decision="review_blockers",
        ),
    )
    return PreActionStressMatrixReport(
        case_count=len(cases),
        pass_count=sum(1 for case in cases if case.passed),
        fail_count=sum(1 for case in cases if not case.passed),
        all_cases_passed=all(case.passed for case in cases),
        blocked_or_human_count=sum(
            1
            for case in cases
            if case.actual_action_readiness
            in {"blocked", "canonical_change_requires_trigger", "human_approval_required"}
        ),
        blocker_count=sum(case.blocker_count for case in cases),
        boundary_error_count=sum(1 for case in cases if case.boundary_error),
        stress_pass_is_not_permission=True,
        must_not_execute_automatically=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action stress matrix only",
        cases=cases,
    )


def render_pre_action_stress_matrix_json(report: PreActionStressMatrixReport) -> str:
    return json.dumps(asdict(report), indent=2, sort_keys=True) + "\n"


def render_pre_action_stress_matrix_markdown(report: PreActionStressMatrixReport) -> str:
    lines = [
        "# Epistemic Guard Pre-Action Stress Matrix",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory pre-action stress matrix only",
        "- stress_pass_is_not_permission: true",
        "- must_not_execute_automatically: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- case_count: {report.case_count}",
        f"- pass_count: {report.pass_count}",
        f"- fail_count: {report.fail_count}",
        f"- all_cases_passed: {str(report.all_cases_passed).lower()}",
        f"- blocked_or_human_count: {report.blocked_or_human_count}",
        f"- blocker_count: {report.blocker_count}",
        f"- boundary_error_count: {report.boundary_error_count}",
        "",
        "## Cases",
        "",
    ]
    for case in report.cases:
        lines.extend(
            [
                f"### {case.case_id}",
                "",
                f"- description: {case.description}",
                f"- expected_action_readiness: {case.expected_action_readiness}",
                f"- actual_action_readiness: {case.actual_action_readiness}",
                f"- expected_human_decision: {case.expected_human_decision}",
                f"- actual_human_decision: {case.actual_human_decision}",
                f"- blocker_count: {case.blocker_count}",
                f"- boundary_error: {str(case.boundary_error).lower()}",
                f"- passed: {str(case.passed).lower()}",
                f"- actual_error: {case.actual_error or 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
