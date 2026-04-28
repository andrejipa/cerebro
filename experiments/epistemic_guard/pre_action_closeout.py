from __future__ import annotations

import json
from dataclasses import asdict, dataclass

from .pre_action_packet import PreActionDecisionPacket
from .pre_action_packet_stress import PreActionPacketStressReproReport


@dataclass(frozen=True)
class PreActionPacketReviewCloseout:
    closeout_status: str
    action_readiness: str
    recommended_human_decision: str
    recursive_hardening_stopped: bool
    input_count: int
    blocker_count: int
    missing_review_evidence_count: int
    packet_operator_posture: str
    packet_action_readiness: str
    packet_recommended_human_decision: str
    packet_blocker_count: int
    stress_repro_case_count: int
    stress_repro_pass_count: int
    stress_repro_fail_count: int
    stress_repro_blocked_case_count: int
    stress_repro_human_review_case_count: int
    stress_repro_mismatch_case_count: int
    stress_repro_boundary_error_count: int
    reopen_trigger_count: int
    closeout_is_not_permission: bool
    no_action_is_not_permission: bool
    stress_repro_is_not_permission: bool
    digest_equality_is_not_truth: bool
    must_not_execute_automatically: bool
    silence_is_not_negative_evidence: bool
    state_change: str
    authority: str
    blockers: tuple[str, ...]
    reopen_triggers: tuple[str, ...]


def _closeout_blockers(
    packet: PreActionDecisionPacket,
    stress_repro: PreActionPacketStressReproReport,
) -> tuple[str, ...]:
    blockers: list[str] = []

    if packet.state_change != "none":
        blockers.append("packet_state_change_not_none")
    if stress_repro.state_change != "none":
        blockers.append("stress_repro_state_change_not_none")
    if not packet.packet_is_not_permission:
        blockers.append("packet_permission_guardrail_missing")
    if not packet.must_not_execute_automatically:
        blockers.append("packet_execution_guardrail_missing")
    if not stress_repro.stress_pass_is_not_permission:
        blockers.append("stress_pass_permission_guardrail_missing")
    if not stress_repro.reproducibility_is_not_permission:
        blockers.append("reproducibility_permission_guardrail_missing")
    if not stress_repro.digest_equality_is_not_truth:
        blockers.append("digest_truth_guardrail_missing")
    if not stress_repro.must_not_execute_automatically:
        blockers.append("stress_repro_execution_guardrail_missing")

    if packet.operator_posture == "no_go_blocked":
        blockers.append("packet_operator_posture_blocked")
    if packet.action_readiness in {"blocked", "canonical_change_requires_trigger"}:
        blockers.append(f"packet_action_readiness:{packet.action_readiness}")
    if packet.packet_blocker_count:
        blockers.append("packet_has_blockers")

    if not stress_repro.all_cases_passed:
        blockers.append("packet_stress_repro_failed")
    if stress_repro.fail_count:
        blockers.append("packet_stress_repro_has_failures")
    if stress_repro.case_count < 10:
        blockers.append("packet_stress_repro_missing_required_cases")
    if stress_repro.mismatch_case_count < 3:
        blockers.append("packet_stress_repro_missing_degraded_artifact_coverage")
    if stress_repro.boundary_error_count < 2:
        blockers.append("packet_stress_repro_missing_boundary_coverage")

    return tuple(blockers)


def build_pre_action_packet_review_closeout(
    packet: PreActionDecisionPacket,
    stress_repro: PreActionPacketStressReproReport,
) -> PreActionPacketReviewCloseout:
    blockers = _closeout_blockers(packet, stress_repro)
    closed = not blockers
    reopen_triggers = (
        "new_pre_action_operator_decision",
        "packet_artifact_reproducibility_mismatch",
        "packet_or_stress_repro_blocker",
        "human_approved_promotion_question",
        "runtime_boundary_change",
    )

    return PreActionPacketReviewCloseout(
        closeout_status="closed_until_new_evidence" if closed else "review_blocked",
        action_readiness="no_action" if closed else "blocked",
        recommended_human_decision="none" if closed else "review_blockers",
        recursive_hardening_stopped=closed,
        input_count=2,
        blocker_count=len(blockers),
        missing_review_evidence_count=0 if closed else len(blockers),
        packet_operator_posture=packet.operator_posture,
        packet_action_readiness=packet.action_readiness,
        packet_recommended_human_decision=packet.recommended_human_decision,
        packet_blocker_count=packet.packet_blocker_count,
        stress_repro_case_count=stress_repro.case_count,
        stress_repro_pass_count=stress_repro.pass_count,
        stress_repro_fail_count=stress_repro.fail_count,
        stress_repro_blocked_case_count=stress_repro.blocked_case_count,
        stress_repro_human_review_case_count=stress_repro.human_review_case_count,
        stress_repro_mismatch_case_count=stress_repro.mismatch_case_count,
        stress_repro_boundary_error_count=stress_repro.boundary_error_count,
        reopen_trigger_count=len(reopen_triggers),
        closeout_is_not_permission=True,
        no_action_is_not_permission=True,
        stress_repro_is_not_permission=True,
        digest_equality_is_not_truth=True,
        must_not_execute_automatically=True,
        silence_is_not_negative_evidence=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action packet review closeout only",
        blockers=blockers,
        reopen_triggers=reopen_triggers,
    )


def render_pre_action_packet_review_closeout_json(closeout: PreActionPacketReviewCloseout) -> str:
    return json.dumps(asdict(closeout), indent=2, sort_keys=True) + "\n"


def render_pre_action_packet_review_closeout_markdown(closeout: PreActionPacketReviewCloseout) -> str:
    lines = [
        "# Epistemic Guard Pre-Action Packet Review Closeout",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory pre-action packet review closeout only",
        "- closeout_is_not_permission: true",
        "- no_action_is_not_permission: true",
        "- stress_repro_is_not_permission: true",
        "- digest_equality_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Closeout",
        "",
        f"- closeout_status: {closeout.closeout_status}",
        f"- action_readiness: {closeout.action_readiness}",
        f"- recommended_human_decision: {closeout.recommended_human_decision}",
        f"- recursive_hardening_stopped: {str(closeout.recursive_hardening_stopped).lower()}",
        f"- input_count: {closeout.input_count}",
        f"- blocker_count: {closeout.blocker_count}",
        f"- missing_review_evidence_count: {closeout.missing_review_evidence_count}",
        "",
        "## Input Summary",
        "",
        f"- packet_operator_posture: {closeout.packet_operator_posture}",
        f"- packet_action_readiness: {closeout.packet_action_readiness}",
        f"- packet_recommended_human_decision: {closeout.packet_recommended_human_decision}",
        f"- packet_blocker_count: {closeout.packet_blocker_count}",
        f"- stress_repro_case_count: {closeout.stress_repro_case_count}",
        f"- stress_repro_pass_count: {closeout.stress_repro_pass_count}",
        f"- stress_repro_fail_count: {closeout.stress_repro_fail_count}",
        f"- stress_repro_blocked_case_count: {closeout.stress_repro_blocked_case_count}",
        f"- stress_repro_human_review_case_count: {closeout.stress_repro_human_review_case_count}",
        f"- stress_repro_mismatch_case_count: {closeout.stress_repro_mismatch_case_count}",
        f"- stress_repro_boundary_error_count: {closeout.stress_repro_boundary_error_count}",
        "",
        "## Blockers",
        "",
        f"- {', '.join(closeout.blockers) if closeout.blockers else 'none'}",
        "",
        "## Reopen Triggers",
        "",
    ]
    lines.extend(f"- {trigger}" for trigger in closeout.reopen_triggers)
    return "\n".join(lines).rstrip() + "\n"
