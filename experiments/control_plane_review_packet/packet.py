from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_event_ledger import (
    ControlPlaneEventLedger,
    build_control_plane_event_ledger,
    render_control_plane_event_ledger_jsonl,
)
from experiments.control_plane_replay_eval import (
    ControlPlaneReplayEvaluation,
    evaluate_control_plane_replay_jsonl,
)
from experiments.control_plane_trace import ControlPlaneTrace, build_control_plane_trace


class ControlPlaneReviewPacketError(ValueError):
    """Raised when a review packet cannot be built safely."""


@dataclass(frozen=True)
class ControlPlaneReviewPacket:
    schema_version: str
    packet_role: str
    trace_id: str
    packet_verdict: str
    selected_task_id: str
    combined_review_status: str
    recommended_human_decision: str
    blockers: tuple[str, ...]
    required_capability_reviews: tuple[str, ...]
    replay_digest: str
    replay_evaluation_verdict: str
    replay_status: str
    replay_issue_codes: tuple[str, ...]
    trace_event_count: int
    ledger_jsonl: str
    trace: ControlPlaneTrace
    ledger: ControlPlaneEventLedger
    replay_evaluation: ControlPlaneReplayEvaluation
    guardrails: tuple[str, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane review packet only"
    packet_is_not_permission: bool = True
    replay_pass_is_not_truth: bool = True
    packet_pass_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


def _packet_verdict(trace: ControlPlaneTrace, evaluation: ControlPlaneReplayEvaluation) -> str:
    if evaluation.verdict != "replay_contract_passed":
        return "packet_replay_invalid"
    if trace.combined_review_status == "blocked_review":
        return "packet_blocked"
    if trace.combined_review_status == "human_review_required":
        return "packet_human_review_required"
    return "packet_advisory_review_only"


def _validate_packet(packet: ControlPlaneReviewPacket) -> None:
    if packet.state_change != "none" or "non-authoritative" not in packet.authority:
        raise ControlPlaneReviewPacketError("packet must be non-authoritative with state_change none")
    if (
        not packet.packet_is_not_permission
        or not packet.replay_pass_is_not_truth
        or not packet.packet_pass_is_not_execution_approval
        or not packet.must_not_execute_automatically
    ):
        raise ControlPlaneReviewPacketError("packet guardrails must remain true")
    if packet.trace.state_change != "none" or "non-authoritative" not in packet.trace.authority:
        raise ControlPlaneReviewPacketError("trace must be non-authoritative with state_change none")
    if (
        packet.replay_evaluation.state_change != "none"
        or "non-authoritative" not in packet.replay_evaluation.authority
    ):
        raise ControlPlaneReviewPacketError("replay evaluation must be non-authoritative with state_change none")
    if packet.trace.replay_digest != packet.replay_digest:
        raise ControlPlaneReviewPacketError("packet replay_digest must match trace replay_digest")
    if packet.ledger.replay_digest != packet.replay_digest:
        raise ControlPlaneReviewPacketError("packet replay_digest must match ledger")
    if packet.replay_evaluation.replay_digest != packet.replay_digest:
        raise ControlPlaneReviewPacketError("packet replay_digest must match replay evaluation")


def build_control_plane_review_packet(
    trace_id: str,
    assessment: ControlPlaneAssessment,
    *,
    capability_assessments: Iterable[CapabilityAssessment] = (),
) -> ControlPlaneReviewPacket:
    """Build a single advisory packet from existing Control Plane evidence."""

    trace = build_control_plane_trace(
        trace_id,
        assessment,
        capability_assessments=capability_assessments,
    )
    ledger = build_control_plane_event_ledger(trace)
    ledger_jsonl = render_control_plane_event_ledger_jsonl(ledger)
    replay_evaluation = evaluate_control_plane_replay_jsonl(ledger_jsonl)
    issue_codes = tuple(issue.code for issue in replay_evaluation.issues)

    packet = ControlPlaneReviewPacket(
        schema_version="1",
        packet_role="compresses_control_plane_advisory_evidence",
        trace_id=trace.trace_id,
        packet_verdict=_packet_verdict(trace, replay_evaluation),
        selected_task_id=trace.selected_task_id,
        combined_review_status=trace.combined_review_status,
        recommended_human_decision=trace.recommended_human_decision,
        blockers=trace.blockers,
        required_capability_reviews=trace.required_capability_reviews,
        replay_digest=trace.replay_digest,
        replay_evaluation_verdict=replay_evaluation.verdict,
        replay_status=replay_evaluation.replay_status,
        replay_issue_codes=issue_codes,
        trace_event_count=len(trace.trace_events),
        ledger_jsonl=ledger_jsonl,
        trace=trace,
        ledger=ledger,
        replay_evaluation=replay_evaluation,
        guardrails=(
            "packet_is_not_permission",
            "replay_pass_is_not_truth",
            "packet_pass_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    _validate_packet(packet)
    return packet


def render_control_plane_review_packet_json(packet: ControlPlaneReviewPacket) -> str:
    _validate_packet(packet)
    payload = asdict(packet)
    payload["state_change"] = "none"
    payload["authority"] = packet.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_review_packet_markdown(packet: ControlPlaneReviewPacket) -> str:
    _validate_packet(packet)
    lines = [
        "# Control Plane Review Packet",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane review packet only",
        "- packet_is_not_permission: true",
        "- replay_pass_is_not_truth: true",
        "- packet_pass_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Verdict",
        "",
        f"- trace_id: {packet.trace_id}",
        f"- packet_role: {packet.packet_role}",
        f"- packet_verdict: {packet.packet_verdict}",
        f"- selected_task_id: {packet.selected_task_id or 'none'}",
        f"- combined_review_status: {packet.combined_review_status}",
        f"- recommended_human_decision: {packet.recommended_human_decision}",
        f"- blockers: {', '.join(packet.blockers) if packet.blockers else 'none'}",
        f"- required_capability_reviews: {', '.join(packet.required_capability_reviews) if packet.required_capability_reviews else 'none'}",
        "",
        "## Replay",
        "",
        f"- replay_digest: {packet.replay_digest}",
        f"- replay_evaluation_verdict: {packet.replay_evaluation_verdict}",
        f"- replay_status: {packet.replay_status}",
        f"- replay_issue_codes: {', '.join(packet.replay_issue_codes) if packet.replay_issue_codes else 'none'}",
        f"- trace_event_count: {packet.trace_event_count}",
        f"- guardrails: {', '.join(packet.guardrails)}",
    ]
    return "\n".join(lines).rstrip() + "\n"
