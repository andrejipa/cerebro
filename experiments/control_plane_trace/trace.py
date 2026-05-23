from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment


class ControlPlaneTraceError(ValueError):
    """Raised when a control-plane trace cannot be built safely."""


_TRACE_EVENT_TYPES = {
    "decision_opened",
    "evidence_read",
    "evidence_rejected",
    "approval_checked",
    "action_blocked",
    "verification_recorded",
    "rollback_recorded",
    "decision_closed",
}


@dataclass(frozen=True)
class ControlPlaneTraceEvent:
    event_type: str
    subject: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneTrace:
    trace_id: str
    trace_role: str
    selected_task_id: str
    combined_review_status: str
    recommended_human_decision: str
    blockers: tuple[str, ...]
    required_capability_reviews: tuple[str, ...]
    assessment_readiness: str
    task_selection_status: str
    capability_statuses: tuple[str, ...]
    review_notes: tuple[str, ...]
    trace_events: tuple[ControlPlaneTraceEvent, ...]
    replay_digest: str
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane trace only"
    trace_is_not_permission: bool = True
    assessment_pass_is_not_permission: bool = True
    capability_allow_is_not_permission: bool = True
    must_not_execute_automatically: bool = True


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _validate_trace_id(trace_id: str) -> None:
    if not trace_id:
        raise ControlPlaneTraceError("trace_id is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in trace_id):
        raise ControlPlaneTraceError("trace_id must be path-segment safe")


def _trace(event_type: str, subject: str, detail: str) -> ControlPlaneTraceEvent:
    if event_type not in _TRACE_EVENT_TYPES:
        raise ControlPlaneTraceError(f"unknown trace event type: {event_type}")
    return ControlPlaneTraceEvent(event_type=event_type, subject=subject, detail=detail)


def _capability_decision(capabilities: tuple[CapabilityAssessment, ...]) -> str:
    decisions = {assessment.decision for assessment in capabilities}
    if "blocked" in decisions:
        return "blocked"
    if "review_required" in decisions:
        return "review_required"
    if not capabilities:
        return "not_evaluated"
    return "advisory_allow"


def _combined_review_status(assessment: ControlPlaneAssessment, capability_decision: str) -> str:
    if assessment.blockers or capability_decision == "blocked":
        return "blocked_review"
    if (
        assessment.recommended_human_decision != "none"
        or capability_decision in {"review_required", "not_evaluated"}
        or assessment.epistemic_action_readiness in {
            "not_evaluated",
            "human_approval_required",
            "canonical_change_requires_trigger",
            "blocked",
        }
    ):
        return "human_review_required"
    return "advisory_review_only"


def _human_decision(
    assessment: ControlPlaneAssessment,
    combined_review_status: str,
    capability_decision: str,
) -> str:
    if combined_review_status == "blocked_review":
        if assessment.recommended_human_decision != "none":
            return assessment.recommended_human_decision
        return "review_blockers"
    if combined_review_status == "human_review_required":
        if assessment.recommended_human_decision != "none":
            return assessment.recommended_human_decision
        if capability_decision == "not_evaluated":
            return "provide_capability_assessment"
        return "review_capability_request"
    return "none"


def _replay_digest(packet_seed: dict) -> str:
    encoded = json.dumps(packet_seed, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return "sha256:" + hashlib.sha256(encoded).hexdigest()


def _validate_input_authority(assessment: ControlPlaneAssessment, capabilities: tuple[CapabilityAssessment, ...]) -> None:
    if assessment.state_change != "none" or "non-authoritative" not in assessment.authority:
        raise ControlPlaneTraceError("assessment input must be non-authoritative with state_change none")
    for capability in capabilities:
        if capability.state_change != "none" or "non-authoritative" not in capability.authority:
            raise ControlPlaneTraceError("capability input must be non-authoritative with state_change none")


def build_control_plane_trace(
    trace_id: str,
    assessment: ControlPlaneAssessment,
    *,
    capability_assessments: Iterable[CapabilityAssessment] = (),
) -> ControlPlaneTrace:
    """Build a replayable advisory trace from existing advisory evidence."""

    _validate_trace_id(trace_id)
    capabilities = tuple(capability_assessments)
    _validate_input_authority(assessment, capabilities)
    cap_decision = _capability_decision(capabilities)
    combined_status = _combined_review_status(assessment, cap_decision)
    recommended_human_decision = _human_decision(assessment, combined_status, cap_decision)

    capability_reviews = _ordered_unique(
        capability.request_id
        for capability in capabilities
        if capability.decision in {"review_required", "blocked"}
    )
    blockers = _ordered_unique(
        (
            *assessment.blockers,
            *(
                f"capability:{capability.request_id}:{reason}"
                for capability in capabilities
                if capability.decision == "blocked"
                for reason in capability.reasons
            ),
        )
    )

    seed = {
        "trace_id": trace_id,
        "selected_task_id": assessment.selected_task_id,
        "assessment": {
            "readiness": assessment.epistemic_action_readiness,
            "task_selection_status": assessment.task_selection_status,
            "recommended_human_decision": assessment.recommended_human_decision,
            "blockers": list(assessment.blockers),
            "missing_evidence": list(assessment.missing_evidence),
        },
        "capabilities": [
            {
                "request_id": capability.request_id,
                "matched_rule_id": capability.matched_rule_id,
                "decision": capability.decision,
                "reasons": list(capability.reasons),
                "required_human_decision": capability.required_human_decision,
            }
            for capability in capabilities
        ],
    }
    digest = _replay_digest(seed)

    events = [
        _trace("decision_opened", trace_id, f"selected_task_id={assessment.selected_task_id or 'none'}"),
        _trace("evidence_read", "control_plane_assessment", assessment.epistemic_action_readiness),
    ]
    for capability in capabilities:
        event_type = "evidence_rejected" if capability.decision == "blocked" else "evidence_read"
        events.append(_trace(event_type, f"capability:{capability.request_id}", capability.decision))
    if recommended_human_decision != "none":
        events.append(_trace("approval_checked", trace_id, recommended_human_decision))
    if combined_status == "blocked_review":
        events.append(_trace("action_blocked", trace_id, ",".join(blockers) if blockers else "blocked"))
    events.append(_trace("decision_closed", trace_id, f"{combined_status}:{digest}"))

    review_notes = _ordered_unique(
        (
            "assessment_pass_is_not_permission",
            "capability_allow_is_not_permission",
            "trace_is_not_permission",
        )
    )

    return ControlPlaneTrace(
        trace_id=trace_id,
        trace_role="correlates_assessment_and_capability_policy",
        selected_task_id=assessment.selected_task_id,
        combined_review_status=combined_status,
        recommended_human_decision=recommended_human_decision,
        blockers=blockers,
        required_capability_reviews=capability_reviews,
        assessment_readiness=assessment.epistemic_action_readiness,
        task_selection_status=assessment.task_selection_status,
        capability_statuses=tuple(f"{cap.request_id}:{cap.decision}" for cap in capabilities),
        review_notes=review_notes,
        trace_events=tuple(events),
        replay_digest=digest,
    )


def render_control_plane_trace_json(trace: ControlPlaneTrace) -> str:
    payload = asdict(trace)
    payload["state_change"] = "none"
    payload["authority"] = trace.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_trace_markdown(trace: ControlPlaneTrace) -> str:
    lines = [
        "# Control Plane Trace",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane trace only",
        "- trace_is_not_permission: true",
        "- assessment_pass_is_not_permission: true",
        "- capability_allow_is_not_permission: true",
        "- must_not_execute_automatically: true",
        "",
        "## Review",
        "",
        f"- trace_id: {trace.trace_id}",
        f"- trace_role: {trace.trace_role}",
        f"- selected_task_id: {trace.selected_task_id or 'none'}",
        f"- task_selection_status: {trace.task_selection_status}",
        f"- assessment_readiness: {trace.assessment_readiness}",
        f"- combined_review_status: {trace.combined_review_status}",
        f"- recommended_human_decision: {trace.recommended_human_decision}",
        f"- replay_digest: {trace.replay_digest}",
        f"- blockers: {', '.join(trace.blockers) if trace.blockers else 'none'}",
        f"- required_capability_reviews: {', '.join(trace.required_capability_reviews) if trace.required_capability_reviews else 'none'}",
        "",
        "## Trace",
        "",
    ]
    lines.extend(f"- {event.event_type}: {event.subject} - {event.detail}" for event in trace.trace_events)
    return "\n".join(lines).rstrip() + "\n"
