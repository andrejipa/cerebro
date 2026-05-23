from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .pre_action import PreActionGuardReport
from .pre_action_stress import PreActionStressMatrixReport


@dataclass(frozen=True)
class PreActionDecisionPacket:
    proposed_action_id: str
    proposed_action_intent: str
    operator_posture: str
    action_readiness: str
    recommended_human_decision: str
    report_action_readiness: str
    report_recommended_human_decision: str
    stress_all_cases_passed: bool
    stress_case_count: int
    stress_fail_count: int
    stress_blocked_or_human_count: int
    stress_boundary_error_count: int
    envelope_count: int
    report_blocker_count: int
    report_missing_evidence_count: int
    report_stale_claim_count: int
    report_conflict_count: int
    packet_blocker_count: int
    review_note_count: int
    packet_is_not_permission: bool
    stress_pass_is_not_permission: bool
    report_pass_is_not_permission: bool
    must_not_execute_automatically: bool
    state_change: str
    authority: str
    blockers: tuple[str, ...]
    review_notes: tuple[str, ...]

    @property
    def blocked(self) -> bool:
        return self.operator_posture == "no_go_blocked"


def _packet_blockers(
    report: PreActionGuardReport,
    stress: PreActionStressMatrixReport,
) -> tuple[str, ...]:
    blockers: list[str] = []
    if not stress.all_cases_passed:
        blockers.append("pre_action_stress_matrix_failed")
    if report.action_readiness == "blocked":
        blockers.append("pre_action_report_blocked")
    if report.action_readiness == "canonical_change_requires_trigger":
        blockers.append("canonical_change_requires_trigger")
    if report.blocker_count:
        blockers.append("pre_action_report_has_blockers")
    if report.conflict_count:
        blockers.append("pre_action_report_has_conflicts")
    return tuple(blockers)


def _packet_review_notes(
    report: PreActionGuardReport,
    stress: PreActionStressMatrixReport,
) -> tuple[str, ...]:
    notes = [
        "packet_is_not_permission",
        "stress_pass_is_not_permission",
        "report_pass_is_not_permission",
        "must_not_execute_automatically",
    ]
    if stress.blocked_or_human_count:
        notes.append("stress_matrix_covers_degraded_blocked_or_human_cases")
    if stress.boundary_error_count:
        notes.append("stress_matrix_covers_boundary_errors")
    if report.missing_evidence_count:
        notes.append("report_has_missing_evidence")
    if report.stale_claim_count:
        notes.append("report_has_stale_claims")
    if report.action_readiness == "human_approval_required":
        notes.append("report_requires_human_approval")
    return tuple(notes)


def _operator_posture(report: PreActionGuardReport, blockers: tuple[str, ...]) -> str:
    if blockers:
        return "no_go_blocked"
    if report.action_readiness == "human_approval_required":
        return "go_requires_human_review"
    return "go_for_advisory_review"


def _action_readiness(
    report: PreActionGuardReport,
    stress: PreActionStressMatrixReport,
    blockers: tuple[str, ...],
) -> str:
    if blockers or not stress.all_cases_passed:
        return "blocked"
    return report.action_readiness


def _recommended_human_decision(
    report: PreActionGuardReport,
    blockers: tuple[str, ...],
) -> str:
    if blockers:
        return "review_blockers"
    return report.recommended_human_decision


def build_pre_action_decision_packet(
    report: PreActionGuardReport,
    stress: PreActionStressMatrixReport,
) -> PreActionDecisionPacket:
    blockers = _packet_blockers(report, stress)
    notes = _packet_review_notes(report, stress)
    posture = _operator_posture(report, blockers)
    action = report.proposed_action

    return PreActionDecisionPacket(
        proposed_action_id=action.action_id,
        proposed_action_intent=action.intent,
        operator_posture=posture,
        action_readiness=_action_readiness(report, stress, blockers),
        recommended_human_decision=_recommended_human_decision(report, blockers),
        report_action_readiness=report.action_readiness,
        report_recommended_human_decision=report.recommended_human_decision,
        stress_all_cases_passed=stress.all_cases_passed,
        stress_case_count=stress.case_count,
        stress_fail_count=stress.fail_count,
        stress_blocked_or_human_count=stress.blocked_or_human_count,
        stress_boundary_error_count=stress.boundary_error_count,
        envelope_count=report.envelope_count,
        report_blocker_count=report.blocker_count,
        report_missing_evidence_count=report.missing_evidence_count,
        report_stale_claim_count=report.stale_claim_count,
        report_conflict_count=report.conflict_count,
        packet_blocker_count=len(blockers),
        review_note_count=len(notes),
        packet_is_not_permission=True,
        stress_pass_is_not_permission=True,
        report_pass_is_not_permission=True,
        must_not_execute_automatically=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action decision packet only",
        blockers=blockers,
        review_notes=notes,
    )


def render_pre_action_decision_packet_json(packet: PreActionDecisionPacket) -> str:
    return json.dumps(asdict(packet), indent=2, sort_keys=True) + "\n"


def render_pre_action_decision_packet_markdown(packet: PreActionDecisionPacket) -> str:
    lines = [
        "# Epistemic Guard Pre-Action Decision Packet",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory pre-action decision packet only",
        "- packet_is_not_permission: true",
        "- stress_pass_is_not_permission: true",
        "- report_pass_is_not_permission: true",
        "- must_not_execute_automatically: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Proposed Action",
        "",
        f"- action_id: {packet.proposed_action_id}",
        f"- intent: {packet.proposed_action_intent}",
        "",
        "## Decision",
        "",
        f"- operator_posture: {packet.operator_posture}",
        f"- action_readiness: {packet.action_readiness}",
        f"- recommended_human_decision: {packet.recommended_human_decision}",
        "",
        "## Evidence Summary",
        "",
        f"- envelope_count: {packet.envelope_count}",
        f"- report_action_readiness: {packet.report_action_readiness}",
        f"- report_recommended_human_decision: {packet.report_recommended_human_decision}",
        f"- report_blocker_count: {packet.report_blocker_count}",
        f"- report_missing_evidence_count: {packet.report_missing_evidence_count}",
        f"- report_stale_claim_count: {packet.report_stale_claim_count}",
        f"- report_conflict_count: {packet.report_conflict_count}",
        f"- stress_all_cases_passed: {str(packet.stress_all_cases_passed).lower()}",
        f"- stress_case_count: {packet.stress_case_count}",
        f"- stress_fail_count: {packet.stress_fail_count}",
        f"- stress_blocked_or_human_count: {packet.stress_blocked_or_human_count}",
        f"- stress_boundary_error_count: {packet.stress_boundary_error_count}",
        f"- packet_blocker_count: {packet.packet_blocker_count}",
        f"- review_note_count: {packet.review_note_count}",
        "",
        "## Blockers",
        "",
        f"- {', '.join(packet.blockers) if packet.blockers else 'none'}",
        "",
        "## Review Notes",
        "",
    ]
    lines.extend(f"- {note}" for note in packet.review_notes)
    return "\n".join(lines).rstrip() + "\n"
