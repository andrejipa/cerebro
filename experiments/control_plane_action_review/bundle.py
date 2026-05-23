from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from experiments.capability_policy import CapabilityAssessment
from experiments.control_plane_assessment import ControlPlaneAssessment
from experiments.control_plane_boundary_audit import ControlPlaneBoundaryAuditReport
from experiments.control_plane_guardrail_eval import evaluate_control_plane_guardrails
from experiments.control_plane_integrity_review import (
    ControlPlaneIntegrityReview,
    ControlPlaneIntegrityReviewError,
    build_control_plane_integrity_review,
)
from experiments.control_plane_lineage_invariant_eval import evaluate_control_plane_packet_projection_lineage
from experiments.control_plane_review_matrix import (
    ControlPlaneReviewMatrix,
    build_control_plane_review_matrix,
)
from experiments.control_plane_review_packet import (
    ControlPlaneReviewPacket,
    build_control_plane_review_packet,
)
from experiments.control_plane_telemetry_projection import (
    ControlPlaneTelemetryProjection,
    project_control_plane_packet_to_telemetry,
)


class ControlPlaneActionReviewError(ValueError):
    """Raised when a pre-action review bundle input is malformed."""


@dataclass(frozen=True)
class ControlPlaneActionObservation:
    observation_id: str
    title: str
    status: str
    kind: str
    priority: str
    boundary: str
    trigger: str
    dependencies: tuple[str, ...]
    dependencies_satisfied: bool
    auto_continuation: bool
    next_action: str
    halt_if: str


@dataclass(frozen=True)
class ControlPlaneActionReviewBundle:
    schema_version: str
    bundle_role: str
    observation: ControlPlaneActionObservation
    action_posture: str
    recommended_human_decision: str
    blockers: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    packet_verdict: str
    combined_review_status: str
    replay_digest: str
    replay_evaluation_verdict: str
    matrix_packet_count: int
    telemetry_span_count: int
    telemetry_event_count: int
    guardrail_status: str
    lineage_status: str
    integrity_status: str
    capability_decisions: tuple[str, ...]
    assessment: ControlPlaneAssessment
    packet: ControlPlaneReviewPacket
    matrix: ControlPlaneReviewMatrix
    telemetry_projection: ControlPlaneTelemetryProjection
    integrity_review: ControlPlaneIntegrityReview
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane action review bundle only"
    bundle_is_not_permission: bool = True
    action_posture_is_not_execution_approval: bool = True
    replay_pass_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_OBSERVATION_STATUSES = {"open", "waiting", "blocked", "resolved"}
_OBSERVATION_KINDS = {"slice", "checkpoint", "blocker"}
_PRIORITIES = {"critical", "high", "medium", "low"}
_CAPABILITY_DECISIONS = {"advisory_allow", "review_required", "blocked"}


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneActionReviewError("dependencies must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneActionReviewError("dependencies must contain only non-empty strings")
    return tuple(value)


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ControlPlaneActionReviewError(f"missing required observation field: {field}")
    return value


def _observation_from_payload(payload: Mapping[str, object]) -> ControlPlaneActionObservation:
    if not isinstance(payload, Mapping):
        raise ControlPlaneActionReviewError("observation payload must be a mapping")
    observation_id = _required_str(payload, "id")
    if any(char not in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in observation_id):
        raise ControlPlaneActionReviewError("observation id must be path-segment safe")
    status = _required_str(payload, "status")
    kind = _required_str(payload, "kind")
    priority = _required_str(payload, "priority")
    if status not in _OBSERVATION_STATUSES:
        raise ControlPlaneActionReviewError(f"unknown observation status: {status}")
    if kind not in _OBSERVATION_KINDS:
        raise ControlPlaneActionReviewError(f"unknown observation kind: {kind}")
    if priority not in _PRIORITIES:
        raise ControlPlaneActionReviewError(f"unknown observation priority: {priority}")
    dependencies_satisfied = payload.get("dependencies_satisfied")
    if not isinstance(dependencies_satisfied, bool):
        raise ControlPlaneActionReviewError("dependencies_satisfied must be boolean")
    auto_continuation = payload.get("auto_continuation", False)
    if not isinstance(auto_continuation, bool):
        raise ControlPlaneActionReviewError("auto_continuation must be boolean")
    return ControlPlaneActionObservation(
        observation_id=observation_id,
        title=_required_str(payload, "title"),
        status=status,
        kind=kind,
        priority=priority,
        boundary=_required_str(payload, "boundary"),
        trigger=_required_str(payload, "trigger"),
        dependencies=_as_str_tuple(payload.get("dependencies")),
        dependencies_satisfied=dependencies_satisfied,
        auto_continuation=auto_continuation,
        next_action=_required_str(payload, "next_action"),
        halt_if=_required_str(payload, "halt_if"),
    )


def _ordered_unique(values: Iterable[str]) -> tuple[str, ...]:
    seen: set[str] = set()
    ordered: list[str] = []
    for value in values:
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return tuple(ordered)


def _assessment_for_observation(
    observation: ControlPlaneActionObservation,
    capabilities: tuple[CapabilityAssessment, ...],
) -> ControlPlaneAssessment:
    blockers: list[str] = []
    missing: list[str] = []
    readiness = "advisory_report_allowed"
    human_decision = "none"

    if observation.status == "waiting":
        readiness = "blocked"
        blockers.append("observation_status_waiting")
        human_decision = "satisfy_checkpoint_dependencies"
    elif observation.status == "blocked":
        readiness = "blocked"
        blockers.append("observation_status_blocked")
        human_decision = "open_or_update_formal_trigger"
    elif observation.status == "resolved":
        readiness = "blocked"
        blockers.append("observation_already_resolved")
        human_decision = "select_unresolved_observation"
    elif not observation.dependencies_satisfied:
        readiness = "blocked"
        blockers.append("observation_dependencies_unsatisfied")
        human_decision = "satisfy_dependencies"
    if observation.auto_continuation:
        readiness = "blocked"
        blockers.append("auto_continuation_requested")
        human_decision = "disable_auto_continuation"

    if not observation.dependencies_satisfied:
        missing.extend(observation.dependencies)
    if "not open" in observation.trigger.lower():
        blockers.append("formal_trigger_not_open")
        human_decision = "open_formal_trigger"

    for capability in capabilities:
        if capability.state_change != "none" or "non-authoritative" not in capability.authority:
            raise ControlPlaneActionReviewError("capability assessment must be non-authoritative with state_change none")
        if not capability.advisory_allow_is_not_permission or not capability.must_not_execute_automatically:
            raise ControlPlaneActionReviewError("capability assessment guardrails must remain true")
        if capability.decision not in _CAPABILITY_DECISIONS:
            raise ControlPlaneActionReviewError(f"unknown capability decision: {capability.decision}")
        if capability.decision == "blocked":
            blockers.append(f"capability_blocked:{capability.request_id}")
        elif capability.decision == "review_required" and human_decision == "none":
            human_decision = capability.required_human_decision

    return ControlPlaneAssessment(
        selected_task_id=observation.observation_id,
        decision_runtime_reason="selected observation supplied by machine-primary observation center",
        task_selection_status="observation_supplied",
        task_selection_reason=f"observation status={observation.status}; dependencies_satisfied={observation.dependencies_satisfied}",
        epistemic_action_readiness=readiness,
        blockers=_ordered_unique(blockers),
        missing_evidence=_ordered_unique(missing),
        stale_claims=(),
        conflicts=(),
        claim_evaluation_summary={"ready_count": 0, "blocked_count": len(blockers), "insufficient_count": len(missing)},
        operational_signal_summary={
            "record_count": 1,
            "candidate_trigger_count": 0,
            "authority": "machine-primary observation center projection",
            "non_authoritative": True,
        },
        recommended_human_decision=human_decision,
        must_not_execute_automatically=True,
        advisory_pass_is_not_permission=True,
    )


def _action_posture(
    assessment: ControlPlaneAssessment,
    packet: ControlPlaneReviewPacket,
    integrity_review: ControlPlaneIntegrityReview,
) -> str:
    if "observation_status_waiting" in assessment.blockers:
        return "waiting_checkpoint_blocked"
    if "formal_trigger_not_open" in assessment.blockers or "observation_status_blocked" in assessment.blockers:
        return "blocked_by_boundary"
    if integrity_review.review_status == "control_plane_integrity_drift_observed":
        return "blocked_by_integrity_drift"
    if packet.packet_verdict == "packet_blocked":
        return "blocked_by_review"
    if packet.packet_verdict == "packet_human_review_required":
        return "human_review_required"
    return "advisory_review_only"


def _validate_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none" or "non-authoritative" not in bundle.authority:
        raise ControlPlaneActionReviewError("bundle must be non-authoritative with state_change none")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneActionReviewError("bundle guardrails must remain true")
    if bundle.packet.trace_id != bundle.observation.observation_id:
        raise ControlPlaneActionReviewError("packet trace id must match observation id")
    if bundle.matrix.packet_count != 1:
        raise ControlPlaneActionReviewError("pre-action bundle matrix must summarize one observation packet")
    if len(bundle.matrix.rows) != 1:
        raise ControlPlaneActionReviewError("pre-action bundle matrix must contain one row")
    row = bundle.matrix.rows[0]
    if row.trace_id != bundle.observation.observation_id or row.trace_id != bundle.packet.trace_id:
        raise ControlPlaneActionReviewError("matrix row trace id must match observation and packet")
    if row.packet_verdict != bundle.packet.packet_verdict:
        raise ControlPlaneActionReviewError("matrix row packet verdict must match packet")
    if row.combined_review_status != bundle.packet.combined_review_status:
        raise ControlPlaneActionReviewError("matrix row review status must match packet")
    if row.recommended_human_decision != bundle.packet.recommended_human_decision:
        raise ControlPlaneActionReviewError("matrix row human decision must match packet")
    if row.replay_evaluation_verdict != bundle.packet.replay_evaluation_verdict:
        raise ControlPlaneActionReviewError("matrix row replay verdict must match packet")
    if bundle.replay_digest != bundle.packet.replay_digest:
        raise ControlPlaneActionReviewError("bundle replay digest must match packet")
    if bundle.packet_verdict != bundle.packet.packet_verdict:
        raise ControlPlaneActionReviewError("bundle packet verdict must match packet")
    if bundle.combined_review_status != bundle.packet.combined_review_status:
        raise ControlPlaneActionReviewError("bundle review status must match packet")
    if bundle.replay_evaluation_verdict != bundle.packet.replay_evaluation_verdict:
        raise ControlPlaneActionReviewError("bundle replay verdict must match packet")
    if bundle.telemetry_span_count != bundle.telemetry_projection.span_count:
        raise ControlPlaneActionReviewError("telemetry span count must match projection")
    if bundle.telemetry_event_count != bundle.telemetry_projection.event_count:
        raise ControlPlaneActionReviewError("telemetry event count must match projection")
    packet_spans = tuple(
        span
        for span in bundle.telemetry_projection.spans
        if span.attributes.get("cerebro.control_plane.trace_id") == bundle.observation.observation_id
    )
    if len(packet_spans) != 1:
        raise ControlPlaneActionReviewError("telemetry projection must contain one span for the observation")
    packet_span = packet_spans[0]
    if packet_span.attributes.get("cerebro.control_plane.packet_verdict") != bundle.packet.packet_verdict:
        raise ControlPlaneActionReviewError("telemetry packet verdict must match packet")
    if packet_span.attributes.get("cerebro.control_plane.replay_digest") != bundle.packet.replay_digest:
        raise ControlPlaneActionReviewError("telemetry replay digest must match packet")
    if bundle.integrity_status not in {"control_plane_integrity_preserved", "control_plane_integrity_drift_observed"}:
        raise ControlPlaneActionReviewError("unknown integrity status")
    if bundle.integrity_status != bundle.integrity_review.review_status:
        raise ControlPlaneActionReviewError("integrity status must match integrity review")
    evidence_statuses = {
        evidence.source_kind: evidence.source_status
        for evidence in bundle.integrity_review.evidence
    }
    if evidence_statuses.get("guardrail_eval") != bundle.guardrail_status:
        raise ControlPlaneActionReviewError("guardrail status must match integrity evidence")
    if evidence_statuses.get("lineage_invariant_eval") != bundle.lineage_status:
        raise ControlPlaneActionReviewError("lineage status must match integrity evidence")
    if bundle.action_posture == "advisory_review_only" and bundle.recommended_human_decision != "none":
        raise ControlPlaneActionReviewError("advisory review posture cannot require a human decision")
    if bundle.action_posture == "advisory_review_only" and bundle.integrity_status != "control_plane_integrity_preserved":
        raise ControlPlaneActionReviewError("advisory review posture requires preserved integrity")
    if bundle.action_posture == "advisory_review_only" and bundle.blockers:
        raise ControlPlaneActionReviewError("advisory review posture cannot carry blockers")


def build_control_plane_action_review_bundle(
    observation_payload: Mapping[str, object],
    *,
    boundary_audit: ControlPlaneBoundaryAuditReport,
    capability_assessments: Iterable[CapabilityAssessment] = (),
) -> ControlPlaneActionReviewBundle:
    """Build one read-only pre-action review bundle for an observation-center item."""

    observation = _observation_from_payload(observation_payload)
    capabilities = tuple(capability_assessments)
    assessment = _assessment_for_observation(observation, capabilities)
    packet = build_control_plane_review_packet(
        observation.observation_id,
        assessment,
        capability_assessments=capabilities,
    )
    matrix = build_control_plane_review_matrix((packet,))
    projection = project_control_plane_packet_to_telemetry(packet)
    guardrail_report = evaluate_control_plane_guardrails(projection)
    lineage_report = evaluate_control_plane_packet_projection_lineage(packet, projection)
    try:
        integrity_review = build_control_plane_integrity_review(
            boundary_audit=boundary_audit,
            guardrail_reports=(guardrail_report,),
            lineage_reports=(lineage_report,),
        )
    except ControlPlaneIntegrityReviewError as exc:
        raise ControlPlaneActionReviewError(str(exc)) from exc
    posture = _action_posture(assessment, packet, integrity_review)
    bundle = ControlPlaneActionReviewBundle(
        schema_version="1",
        bundle_role="reviews_one_observation_center_item_before_any_action",
        observation=observation,
        action_posture=posture,
        recommended_human_decision=packet.recommended_human_decision,
        blockers=packet.blockers,
        missing_evidence=assessment.missing_evidence,
        packet_verdict=packet.packet_verdict,
        combined_review_status=packet.combined_review_status,
        replay_digest=packet.replay_digest,
        replay_evaluation_verdict=packet.replay_evaluation_verdict,
        matrix_packet_count=matrix.packet_count,
        telemetry_span_count=projection.span_count,
        telemetry_event_count=projection.event_count,
        guardrail_status=guardrail_report.eval_status,
        lineage_status=lineage_report.eval_status,
        integrity_status=integrity_review.review_status,
        capability_decisions=tuple(f"{item.request_id}:{item.decision}" for item in capabilities),
        assessment=assessment,
        packet=packet,
        matrix=matrix,
        telemetry_projection=projection,
        integrity_review=integrity_review,
    )
    _validate_bundle(bundle)
    return bundle


def render_control_plane_action_review_bundle_json(bundle: ControlPlaneActionReviewBundle) -> str:
    _validate_bundle(bundle)
    payload = asdict(bundle)
    payload["state_change"] = "none"
    payload["authority"] = bundle.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_action_review_bundle_markdown(bundle: ControlPlaneActionReviewBundle) -> str:
    _validate_bundle(bundle)
    lines = [
        "# Control Plane Action Review Bundle",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane action review bundle only",
        "- bundle_is_not_permission: true",
        "- action_posture_is_not_execution_approval: true",
        "- replay_pass_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Observation",
        "",
        f"- observation_id: {bundle.observation.observation_id}",
        f"- status: {bundle.observation.status}",
        f"- kind: {bundle.observation.kind}",
        f"- priority: {bundle.observation.priority}",
        f"- dependencies_satisfied: {str(bundle.observation.dependencies_satisfied).lower()}",
        "",
        "## Review",
        "",
        f"- action_posture: {bundle.action_posture}",
        f"- recommended_human_decision: {bundle.recommended_human_decision}",
        f"- blockers: {', '.join(bundle.blockers) if bundle.blockers else 'none'}",
        f"- missing_evidence: {', '.join(bundle.missing_evidence) if bundle.missing_evidence else 'none'}",
        f"- packet_verdict: {bundle.packet_verdict}",
        f"- combined_review_status: {bundle.combined_review_status}",
        f"- replay_digest: {bundle.replay_digest}",
        f"- replay_evaluation_verdict: {bundle.replay_evaluation_verdict}",
        f"- guardrail_status: {bundle.guardrail_status}",
        f"- lineage_status: {bundle.lineage_status}",
        f"- integrity_status: {bundle.integrity_status}",
    ]
    return "\n".join(lines).rstrip() + "\n"
