from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any, Iterable

from core.decision_runtime import choose_next_task, evaluate_task_selection_consistency
from experiments.claim_evaluation import EvaluationReport
from experiments.epistemic_guard import DecisionEnvelope


class ControlPlaneAssessmentError(ValueError):
    """Raised when advisory assessment inputs are malformed."""


@dataclass(frozen=True)
class ControlPlaneAssessment:
    selected_task_id: str
    decision_runtime_reason: str
    task_selection_status: str
    task_selection_reason: str
    epistemic_action_readiness: str
    blockers: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    stale_claims: tuple[str, ...]
    conflicts: tuple[str, ...]
    claim_evaluation_summary: dict[str, int]
    operational_signal_summary: dict[str, Any]
    recommended_human_decision: str
    must_not_execute_automatically: bool
    advisory_pass_is_not_permission: bool
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane assessment only"


def _aggregate_readiness(envelopes: tuple[DecisionEnvelope, ...]) -> str:
    if not envelopes:
        return "not_evaluated"
    readiness = {envelope.action_readiness for envelope in envelopes}
    for candidate in (
        "canonical_change_requires_trigger",
        "blocked",
        "human_approval_required",
        "derived_experiment_allowed",
        "advisory_report_allowed",
    ):
        if candidate in readiness:
            return candidate
    return "propose_only"


def _aggregate_human_decision(envelopes: tuple[DecisionEnvelope, ...]) -> str:
    decisions = {envelope.recommended_human_decision for envelope in envelopes}
    for decision in (
        "review_blockers",
        "adjudicate_conflict",
        "approve_action",
        "provide_missing_evidence",
    ):
        if decision in decisions:
            return decision
    return "none"


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _claim_summary(report: EvaluationReport | None) -> dict[str, int]:
    if report is None:
        return {
            "ready_count": 0,
            "blocked_count": 0,
            "insufficient_count": 0,
        }
    return {
        "ready_count": report.ready_count,
        "blocked_count": report.blocked_count,
        "insufficient_count": report.insufficient_count,
    }


def _operational_signal_summary(payload: dict[str, Any] | None) -> dict[str, Any]:
    if payload is None:
        return {
            "record_count": 0,
            "candidate_trigger_count": 0,
            "authority": "not_provided",
            "non_authoritative": True,
        }

    totals = payload.get("totals", {})
    if not isinstance(totals, dict):
        totals = {}
    return {
        "record_count": int(totals.get("count", 0)) if isinstance(totals.get("count", 0), int) else 0,
        "candidate_trigger_count": (
            int(totals.get("candidate_trigger_count", 0))
            if isinstance(totals.get("candidate_trigger_count", 0), int)
            else 0
        ),
        "authority": str(payload.get("authority", "unknown")),
        "non_authoritative": bool(payload.get("non_authoritative", False)),
    }


def build_control_plane_assessment(
    agent_runtime: dict,
    *,
    envelopes: Iterable[DecisionEnvelope] = (),
    claim_evaluation: EvaluationReport | None = None,
    operational_signals: dict[str, Any] | None = None,
    recent_events: tuple[dict, ...] = (),
) -> ControlPlaneAssessment:
    """Compose existing decision surfaces into one advisory report.

    The function is intentionally read-only. It delegates task selection to
    `decision_runtime` and only aggregates advisory experiment outputs.
    """

    if not isinstance(agent_runtime, dict):
        raise ControlPlaneAssessmentError("agent_runtime must be a dict")

    ordered_envelopes = tuple(envelopes)
    selection = choose_next_task(agent_runtime, recent_events)
    consistency = evaluate_task_selection_consistency(agent_runtime, recent_events)

    blockers = _ordered_unique(blocker for envelope in ordered_envelopes for blocker in envelope.blockers)
    missing = _ordered_unique(item for envelope in ordered_envelopes for item in envelope.missing_evidence)
    stale = _ordered_unique(item for envelope in ordered_envelopes for item in envelope.stale_claims)
    conflicts = _ordered_unique(item for envelope in ordered_envelopes for item in envelope.conflicts)
    readiness = _aggregate_readiness(ordered_envelopes)
    human_decision = _aggregate_human_decision(ordered_envelopes)

    if readiness in {"not_evaluated", "advisory_report_allowed", "derived_experiment_allowed"}:
        if consistency.get("status") == "mismatch":
            human_decision = "review_blockers"
            blockers = _ordered_unique((*blockers, "task_selection_inconsistent"))

    return ControlPlaneAssessment(
        selected_task_id=str(selection.get("task_id", "")),
        decision_runtime_reason=str(selection.get("reason", "")),
        task_selection_status=str(consistency.get("status", "")),
        task_selection_reason=str(consistency.get("reason", "")),
        epistemic_action_readiness=readiness,
        blockers=blockers,
        missing_evidence=missing,
        stale_claims=stale,
        conflicts=conflicts,
        claim_evaluation_summary=_claim_summary(claim_evaluation),
        operational_signal_summary=_operational_signal_summary(operational_signals),
        recommended_human_decision=human_decision,
        must_not_execute_automatically=True,
        advisory_pass_is_not_permission=True,
    )


def render_control_plane_assessment_json(assessment: ControlPlaneAssessment) -> str:
    payload = asdict(assessment)
    payload["state_change"] = "none"
    payload["authority"] = assessment.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_assessment_markdown(assessment: ControlPlaneAssessment) -> str:
    lines = [
        "# Control Plane Assessment",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane assessment only",
        "- advisory_pass_is_not_permission: true",
        "- must_not_execute_automatically: true",
        "",
        "## Task Selection",
        "",
        f"- selected_task_id: {assessment.selected_task_id or 'none'}",
        f"- decision_runtime_reason: {assessment.decision_runtime_reason or 'none'}",
        f"- task_selection_status: {assessment.task_selection_status or 'unknown'}",
        f"- task_selection_reason: {assessment.task_selection_reason or 'none'}",
        "",
        "## Advisory Readiness",
        "",
        f"- epistemic_action_readiness: {assessment.epistemic_action_readiness}",
        f"- recommended_human_decision: {assessment.recommended_human_decision}",
        f"- blockers: {', '.join(assessment.blockers) if assessment.blockers else 'none'}",
        f"- missing_evidence: {', '.join(assessment.missing_evidence) if assessment.missing_evidence else 'none'}",
        f"- stale_claims: {', '.join(assessment.stale_claims) if assessment.stale_claims else 'none'}",
        f"- conflicts: {', '.join(assessment.conflicts) if assessment.conflicts else 'none'}",
        "",
        "## Claim Evaluation",
        "",
        f"- ready_count: {assessment.claim_evaluation_summary['ready_count']}",
        f"- blocked_count: {assessment.claim_evaluation_summary['blocked_count']}",
        f"- insufficient_count: {assessment.claim_evaluation_summary['insufficient_count']}",
        "",
        "## Operational Signals",
        "",
        f"- record_count: {assessment.operational_signal_summary['record_count']}",
        f"- candidate_trigger_count: {assessment.operational_signal_summary['candidate_trigger_count']}",
        f"- authority: {assessment.operational_signal_summary['authority']}",
        f"- non_authoritative: {str(assessment.operational_signal_summary['non_authoritative']).lower()}",
    ]
    return "\n".join(lines).rstrip() + "\n"
