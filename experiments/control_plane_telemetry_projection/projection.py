from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.control_plane_review_matrix import ControlPlaneReviewMatrix
from experiments.control_plane_review_packet import ControlPlaneReviewPacket
from experiments.control_plane_scenario_lab import (
    ControlPlaneAdversarialReport,
    ControlPlaneScenarioLabReport,
)


class ControlPlaneTelemetryProjectionError(ValueError):
    """Raised when telemetry projection would cross its advisory boundary."""


AttributeValue = str | int | bool


@dataclass(frozen=True)
class ControlPlaneTelemetryEvent:
    name: str
    attributes: dict[str, AttributeValue]


@dataclass(frozen=True)
class ControlPlaneTelemetrySpan:
    span_id: str
    parent_span_id: str
    name: str
    kind: str
    status: str
    attributes: dict[str, AttributeValue]
    events: tuple[ControlPlaneTelemetryEvent, ...]


@dataclass(frozen=True)
class ControlPlaneTelemetryProjection:
    schema_version: str
    projection_role: str
    compatibility_profile: str
    semconv_status: str
    source_count: int
    span_count: int
    event_count: int
    spans: tuple[ControlPlaneTelemetrySpan, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory in-memory telemetry projection only"
    projection_is_not_opentelemetry_export: bool = True
    projection_is_not_export: bool = True
    projection_is_not_permission: bool = True
    telemetry_is_not_permission: bool = True
    span_status_is_not_truth: bool = True
    semconv_compat_is_not_stability: bool = True
    must_not_execute_automatically: bool = True


def _validate_path_segment(value: str, *, field: str) -> None:
    if not value:
        raise ControlPlaneTelemetryProjectionError(f"{field} is required")
    allowed = set("abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-")
    if any(char not in allowed for char in value):
        raise ControlPlaneTelemetryProjectionError(f"{field} must be path-segment safe")


def _validate_packet(packet: ControlPlaneReviewPacket) -> None:
    _validate_path_segment(packet.trace_id, field="trace_id")
    if packet.state_change != "none" or "non-authoritative" not in packet.authority:
        raise ControlPlaneTelemetryProjectionError("packet must be non-authoritative with state_change none")
    if (
        not packet.packet_is_not_permission
        or not packet.replay_pass_is_not_truth
        or not packet.packet_pass_is_not_execution_approval
        or not packet.must_not_execute_automatically
    ):
        raise ControlPlaneTelemetryProjectionError("packet guardrails must remain true")
    if packet.trace.state_change != "none" or "non-authoritative" not in packet.trace.authority:
        raise ControlPlaneTelemetryProjectionError("trace must be non-authoritative with state_change none")
    if (
        packet.replay_evaluation.state_change != "none"
        or "non-authoritative" not in packet.replay_evaluation.authority
    ):
        raise ControlPlaneTelemetryProjectionError("replay evaluation must be non-authoritative")
    if packet.trace.replay_digest != packet.replay_digest:
        raise ControlPlaneTelemetryProjectionError("packet replay_digest must match trace")
    if packet.replay_evaluation.replay_digest != packet.replay_digest:
        raise ControlPlaneTelemetryProjectionError("packet replay_digest must match replay evaluation")


def _validate_matrix(matrix: ControlPlaneReviewMatrix) -> None:
    if matrix.state_change != "none" or "non-authoritative" not in matrix.authority:
        raise ControlPlaneTelemetryProjectionError("matrix must be non-authoritative with state_change none")
    if (
        not matrix.matrix_is_not_permission
        or not matrix.matrix_pass_is_not_execution_approval
        or not matrix.replay_pass_is_not_truth
        or not matrix.must_not_execute_automatically
    ):
        raise ControlPlaneTelemetryProjectionError("matrix guardrails must remain true")
    if matrix.packet_count != len(matrix.rows):
        raise ControlPlaneTelemetryProjectionError("matrix packet_count must match rows")
    for row in matrix.rows:
        _validate_path_segment(row.trace_id, field="trace_id")


def _validate_scenario_lab(report: ControlPlaneScenarioLabReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneTelemetryProjectionError("scenario lab must be non-authoritative")
    if (
        not report.lab_is_not_permission
        or not report.expectation_match_is_not_execution_approval
        or not report.replay_pass_is_not_truth
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneTelemetryProjectionError("scenario lab guardrails must remain true")
    if report.scenario_count != len(report.results):
        raise ControlPlaneTelemetryProjectionError("scenario_count must match results")
    for result in report.results:
        _validate_path_segment(result.scenario_id, field="scenario_id")


def _validate_adversarial_report(report: ControlPlaneAdversarialReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneTelemetryProjectionError("adversarial report must be non-authoritative")
    if (
        not report.lab_is_not_permission
        or not report.adversarial_findings_are_not_execution_approval
        or not report.replay_pass_is_not_truth
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneTelemetryProjectionError("adversarial report guardrails must remain true")
    if report.probe_count != len(report.results):
        raise ControlPlaneTelemetryProjectionError("probe_count must match results")
    if report.finding_count != len(report.findings):
        raise ControlPlaneTelemetryProjectionError("finding_count must match findings")
    for result in report.results:
        _validate_path_segment(result.probe_id, field="probe_id")


def _stable_id(*parts: str) -> str:
    seed = "\x1f".join(parts).encode("utf-8")
    return hashlib.sha256(seed).hexdigest()[:16]


def _packet_status(packet: ControlPlaneReviewPacket) -> str:
    if packet.packet_verdict == "packet_replay_invalid":
        return "observed_replay_invalid"
    if packet.packet_verdict == "packet_blocked":
        return "observed_blocked"
    if packet.packet_verdict == "packet_human_review_required":
        return "observed_human_review_required"
    return "observed_advisory_non_authoritative"


def _trace_events(packet: ControlPlaneReviewPacket) -> tuple[ControlPlaneTelemetryEvent, ...]:
    events: list[ControlPlaneTelemetryEvent] = []
    for sequence, event in enumerate(packet.trace.trace_events, start=1):
        events.append(
            ControlPlaneTelemetryEvent(
                name=f"cerebro.control_plane.{event.event_type}",
                attributes={
                    "cerebro.control_plane.sequence": sequence,
                    "cerebro.control_plane.trace_id": packet.trace_id,
                    "cerebro.control_plane.subject": event.subject,
                    "cerebro.control_plane.detail": event.detail,
                    "cerebro.control_plane.event_is_not_permission": True,
                },
            )
        )
    for blocker in packet.blockers:
        events.append(
            ControlPlaneTelemetryEvent(
                name="cerebro.control_plane.blocker_observed",
                attributes={
                    "cerebro.control_plane.trace_id": packet.trace_id,
                    "cerebro.control_plane.blocker": blocker,
                    "cerebro.control_plane.event_is_not_permission": True,
                },
            )
        )
    for issue_code in packet.replay_issue_codes:
        events.append(
            ControlPlaneTelemetryEvent(
                name="cerebro.control_plane.replay_issue_observed",
                attributes={
                    "cerebro.control_plane.trace_id": packet.trace_id,
                    "cerebro.control_plane.replay_issue_code": issue_code,
                    "cerebro.control_plane.event_is_not_permission": True,
                },
            )
        )
    return tuple(events)


def _packet_span(packet: ControlPlaneReviewPacket) -> ControlPlaneTelemetrySpan:
    return ControlPlaneTelemetrySpan(
        span_id=_stable_id("control-plane-review-packet", packet.trace_id, packet.replay_digest),
        parent_span_id="",
        name="cerebro.control_plane.review_packet",
        kind="INTERNAL",
        status=_packet_status(packet),
        attributes={
            "cerebro.control_plane.trace_id": packet.trace_id,
            "cerebro.control_plane.packet_verdict": packet.packet_verdict,
            "cerebro.control_plane.combined_review_status": packet.combined_review_status,
            "cerebro.control_plane.recommended_human_decision": packet.recommended_human_decision,
            "cerebro.control_plane.selected_task_id": packet.selected_task_id or "none",
            "cerebro.control_plane.replay_digest": packet.replay_digest,
            "cerebro.control_plane.replay_evaluation_verdict": packet.replay_evaluation_verdict,
            "cerebro.control_plane.replay_status": packet.replay_status,
            "cerebro.control_plane.blocker_count": len(packet.blockers),
            "cerebro.control_plane.required_capability_review_count": len(packet.required_capability_reviews),
            "cerebro.control_plane.trace_event_count": packet.trace_event_count,
            "cerebro.control_plane.packet_is_not_permission": packet.packet_is_not_permission,
            "cerebro.control_plane.replay_pass_is_not_truth": packet.replay_pass_is_not_truth,
            "cerebro.control_plane.packet_pass_is_not_execution_approval": (
                packet.packet_pass_is_not_execution_approval
            ),
            "cerebro.control_plane.span_status_is_not_truth": True,
            "cerebro.control_plane.must_not_execute_automatically": packet.must_not_execute_automatically,
            "otel.compat.profile": "genai-semconv-development-compatible-projection",
            "otel.compat.exported": False,
        },
        events=_trace_events(packet),
    )


def _matrix_span(matrix: ControlPlaneReviewMatrix) -> ControlPlaneTelemetrySpan:
    events = tuple(
        ControlPlaneTelemetryEvent(
            name="cerebro.control_plane.review_matrix.row_observed",
            attributes={
                "cerebro.control_plane.trace_id": row.trace_id,
                "cerebro.control_plane.packet_verdict": row.packet_verdict,
                "cerebro.control_plane.combined_review_status": row.combined_review_status,
                "cerebro.control_plane.replay_evaluation_verdict": row.replay_evaluation_verdict,
                "cerebro.control_plane.required_human_decision": row.recommended_human_decision,
                "cerebro.control_plane.event_is_not_permission": True,
            },
        )
        for row in matrix.rows
    )
    digest_seed = json.dumps([row.trace_id for row in matrix.rows], sort_keys=True)
    return ControlPlaneTelemetrySpan(
        span_id=_stable_id("control-plane-review-matrix", digest_seed),
        parent_span_id="",
        name="cerebro.control_plane.review_matrix",
        kind="INTERNAL",
        status="observed_matrix_non_authoritative",
        attributes={
            "cerebro.control_plane.packet_count": matrix.packet_count,
            "cerebro.control_plane.packet_verdict_counts": json.dumps(
                matrix.packet_verdict_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cerebro.control_plane.combined_review_status_counts": json.dumps(
                matrix.combined_review_status_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cerebro.control_plane.replay_evaluation_verdict_counts": json.dumps(
                matrix.replay_evaluation_verdict_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cerebro.control_plane.required_human_decision_count": len(matrix.required_human_decisions),
            "cerebro.control_plane.matrix_is_not_permission": matrix.matrix_is_not_permission,
            "cerebro.control_plane.matrix_pass_is_not_execution_approval": (
                matrix.matrix_pass_is_not_execution_approval
            ),
            "cerebro.control_plane.span_status_is_not_truth": True,
            "otel.compat.exported": False,
        },
        events=events,
    )


def _scenario_lab_spans(report: ControlPlaneScenarioLabReport) -> tuple[ControlPlaneTelemetrySpan, ...]:
    root_id = _stable_id("control-plane-scenario-lab", ",".join(result.scenario_id for result in report.results))
    root = ControlPlaneTelemetrySpan(
        span_id=root_id,
        parent_span_id="",
        name="cerebro.control_plane.scenario_lab",
        kind="INTERNAL",
        status="observed_scenario_lab_non_authoritative",
        attributes={
            "cerebro.control_plane.scenario_count": report.scenario_count,
            "cerebro.control_plane.expectation_failure_count": report.expectation_failure_count,
            "cerebro.control_plane.expectation_status_counts": json.dumps(
                report.expectation_status_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cerebro.control_plane.lab_is_not_permission": report.lab_is_not_permission,
            "cerebro.control_plane.expectation_match_is_not_execution_approval": (
                report.expectation_match_is_not_execution_approval
            ),
            "cerebro.control_plane.span_status_is_not_truth": True,
            "otel.compat.exported": False,
        },
        events=tuple(
            ControlPlaneTelemetryEvent(
                name="cerebro.control_plane.scenario_expectation_drift_observed",
                attributes={
                    "cerebro.control_plane.scenario_id": scenario_id,
                    "cerebro.control_plane.event_is_not_permission": True,
                },
            )
            for scenario_id in report.scenarios_with_expectation_drift
        ),
    )
    children = tuple(
        ControlPlaneTelemetrySpan(
            span_id=_stable_id("control-plane-scenario", result.scenario_id),
            parent_span_id=root_id,
            name="cerebro.control_plane.scenario",
            kind="INTERNAL",
            status=result.expectation_status,
            attributes={
                "cerebro.control_plane.scenario_id": result.scenario_id,
                "cerebro.control_plane.packet_verdict": result.packet_verdict,
                "cerebro.control_plane.combined_review_status": result.combined_review_status,
                "cerebro.control_plane.replay_evaluation_verdict": result.replay_evaluation_verdict,
                "cerebro.control_plane.required_human_decision": result.recommended_human_decision,
                "cerebro.control_plane.expectation_status": result.expectation_status,
                "cerebro.control_plane.blocker_count": result.blocker_count,
                "cerebro.control_plane.span_status_is_not_truth": True,
                "otel.compat.exported": False,
            },
            events=tuple(
                ControlPlaneTelemetryEvent(
                    name="cerebro.control_plane.expectation_failure_observed",
                    attributes={
                        "cerebro.control_plane.scenario_id": result.scenario_id,
                        "cerebro.control_plane.expectation_failure": failure,
                        "cerebro.control_plane.event_is_not_permission": True,
                    },
                )
                for failure in result.expectation_failures
            ),
        )
        for result in report.results
    )
    return (root, *children)


def _adversarial_spans(report: ControlPlaneAdversarialReport) -> tuple[ControlPlaneTelemetrySpan, ...]:
    root_id = _stable_id("control-plane-adversarial-lab", ",".join(result.probe_id for result in report.results))
    finding_events = tuple(
        ControlPlaneTelemetryEvent(
            name="cerebro.control_plane.adversarial_finding_observed",
            attributes={
                "cerebro.control_plane.probe_id": finding.probe_id,
                "cerebro.control_plane.finding_code": finding.code,
                "cerebro.control_plane.finding_severity": finding.severity,
                "cerebro.control_plane.finding_detail": finding.detail,
                "cerebro.control_plane.event_is_not_permission": True,
            },
        )
        for finding in report.findings
    )
    root = ControlPlaneTelemetrySpan(
        span_id=root_id,
        parent_span_id="",
        name="cerebro.control_plane.adversarial_lab",
        kind="INTERNAL",
        status="observed_adversarial_lab_non_authoritative",
        attributes={
            "cerebro.control_plane.probe_count": report.probe_count,
            "cerebro.control_plane.finding_count": report.finding_count,
            "cerebro.control_plane.probe_status_counts": json.dumps(
                report.probe_status_counts,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "cerebro.control_plane.adversarial_findings_are_not_execution_approval": (
                report.adversarial_findings_are_not_execution_approval
            ),
            "cerebro.control_plane.span_status_is_not_truth": True,
            "otel.compat.exported": False,
        },
        events=finding_events,
    )
    children = tuple(
        ControlPlaneTelemetrySpan(
            span_id=_stable_id("control-plane-adversarial-probe", result.probe_id),
            parent_span_id=root_id,
            name="cerebro.control_plane.adversarial_probe",
            kind="INTERNAL",
            status=result.probe_status,
            attributes={
                "cerebro.control_plane.probe_id": result.probe_id,
                "cerebro.control_plane.probe_kind": result.probe_kind,
                "cerebro.control_plane.expectation_status": result.expectation_status,
                "cerebro.control_plane.finding_count": len(result.finding_codes),
                "cerebro.control_plane.span_status_is_not_truth": True,
                "otel.compat.exported": False,
            },
            events=tuple(
                ControlPlaneTelemetryEvent(
                    name="cerebro.control_plane.expected_finding_missing",
                    attributes={
                        "cerebro.control_plane.probe_id": result.probe_id,
                        "cerebro.control_plane.expectation_failure": failure,
                        "cerebro.control_plane.event_is_not_permission": True,
                    },
                )
                for failure in result.expectation_failures
            ),
        )
        for result in report.results
    )
    return (root, *children)


def _validate_projection(projection: ControlPlaneTelemetryProjection) -> None:
    if projection.state_change != "none" or "non-authoritative" not in projection.authority:
        raise ControlPlaneTelemetryProjectionError("projection must be non-authoritative with state_change none")
    if (
        not projection.projection_is_not_opentelemetry_export
        or not projection.projection_is_not_export
        or not projection.projection_is_not_permission
        or not projection.telemetry_is_not_permission
        or not projection.span_status_is_not_truth
        or not projection.semconv_compat_is_not_stability
        or not projection.must_not_execute_automatically
    ):
        raise ControlPlaneTelemetryProjectionError("projection guardrails must remain true")
    if projection.semconv_status != "development":
        raise ControlPlaneTelemetryProjectionError("semconv status must remain development")
    if projection.span_count != len(projection.spans):
        raise ControlPlaneTelemetryProjectionError("span_count must match spans")
    if projection.event_count != sum(len(span.events) for span in projection.spans):
        raise ControlPlaneTelemetryProjectionError("event_count must match span events")
    if not projection.spans:
        raise ControlPlaneTelemetryProjectionError("projection must contain at least one span")
    span_ids = [span.span_id for span in projection.spans]
    duplicates = sorted({span_id for span_id in span_ids if span_ids.count(span_id) > 1})
    if duplicates:
        raise ControlPlaneTelemetryProjectionError(f"duplicate span_id: {', '.join(duplicates)}")
    for span in projection.spans:
        if span.kind != "INTERNAL":
            raise ControlPlaneTelemetryProjectionError("spans must remain INTERNAL")
        if span.attributes.get("otel.compat.exported") is not False:
            raise ControlPlaneTelemetryProjectionError("projection must not claim exported telemetry")
        if span.attributes.get("cerebro.control_plane.span_status_is_not_truth") is not True:
            raise ControlPlaneTelemetryProjectionError("span status must remain non-truth evidence")


def project_control_plane_packets_to_telemetry(
    packets: Iterable[ControlPlaneReviewPacket],
) -> ControlPlaneTelemetryProjection:
    """Project review packets to deterministic in-memory telemetry-like spans."""

    packet_items = tuple(packets)
    if not packet_items:
        raise ControlPlaneTelemetryProjectionError("telemetry projection requires at least one packet")
    trace_ids = [packet.trace_id for packet in packet_items]
    duplicates = sorted({trace_id for trace_id in trace_ids if trace_ids.count(trace_id) > 1})
    if duplicates:
        raise ControlPlaneTelemetryProjectionError(f"duplicate trace_id: {', '.join(duplicates)}")

    spans = []
    for packet in packet_items:
        _validate_packet(packet)
        spans.append(_packet_span(packet))

    span_items = tuple(spans)
    projection = ControlPlaneTelemetryProjection(
        schema_version="1",
        projection_role="maps_control_plane_review_packets_to_in_memory_observability_events",
        compatibility_profile="otel-semconv-genai-development-compatible-projection",
        semconv_status="development",
        source_count=len(packet_items),
        span_count=len(span_items),
        event_count=sum(len(span.events) for span in span_items),
        spans=span_items,
    )
    _validate_projection(projection)
    return projection


def project_control_plane_packet_to_telemetry(
    packet: ControlPlaneReviewPacket,
) -> ControlPlaneTelemetryProjection:
    return project_control_plane_packets_to_telemetry((packet,))


def _projection_from_spans(
    spans: tuple[ControlPlaneTelemetrySpan, ...],
    *,
    source_count: int,
    role: str,
) -> ControlPlaneTelemetryProjection:
    projection = ControlPlaneTelemetryProjection(
        schema_version="1",
        projection_role=role,
        compatibility_profile="otel-semconv-genai-development-compatible-projection",
        semconv_status="development",
        source_count=source_count,
        span_count=len(spans),
        event_count=sum(len(span.events) for span in spans),
        spans=spans,
    )
    _validate_projection(projection)
    return projection


def project_control_plane_matrix_to_telemetry(
    matrix: ControlPlaneReviewMatrix,
) -> ControlPlaneTelemetryProjection:
    _validate_matrix(matrix)
    return _projection_from_spans(
        (_matrix_span(matrix),),
        source_count=1,
        role="maps_control_plane_review_matrix_to_in_memory_observability_events",
    )


def project_control_plane_scenario_lab_to_telemetry(
    report: ControlPlaneScenarioLabReport,
) -> ControlPlaneTelemetryProjection:
    _validate_scenario_lab(report)
    return _projection_from_spans(
        _scenario_lab_spans(report),
        source_count=1,
        role="maps_control_plane_scenario_lab_to_in_memory_observability_events",
    )


def project_control_plane_adversarial_report_to_telemetry(
    report: ControlPlaneAdversarialReport,
) -> ControlPlaneTelemetryProjection:
    _validate_adversarial_report(report)
    return _projection_from_spans(
        _adversarial_spans(report),
        source_count=1,
        role="maps_control_plane_adversarial_report_to_in_memory_observability_events",
    )


def render_control_plane_telemetry_json(projection: ControlPlaneTelemetryProjection) -> str:
    _validate_projection(projection)
    payload = asdict(projection)
    payload["state_change"] = "none"
    payload["authority"] = projection.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_telemetry_markdown(projection: ControlPlaneTelemetryProjection) -> str:
    _validate_projection(projection)
    lines = [
        "# Control Plane Telemetry Projection",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory in-memory telemetry projection only",
        "- projection_is_not_opentelemetry_export: true",
        "- projection_is_not_export: true",
        "- projection_is_not_permission: true",
        "- telemetry_is_not_permission: true",
        "- span_status_is_not_truth: true",
        "- semconv_compat_is_not_stability: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- projection_role: {projection.projection_role}",
        f"- compatibility_profile: {projection.compatibility_profile}",
        f"- semconv_status: {projection.semconv_status}",
        f"- source_count: {projection.source_count}",
        f"- span_count: {projection.span_count}",
        f"- event_count: {projection.event_count}",
        "",
        "## Spans",
        "",
    ]
    for span in projection.spans:
        trace = span.attributes.get("cerebro.control_plane.trace_id", "none")
        packet = span.attributes.get("cerebro.control_plane.packet_verdict", "none")
        lines.append(
            f"- {span.name}: status={span.status}; "
            f"trace={trace}; "
            f"packet={packet}; "
            f"events={len(span.events)}"
        )
    return "\n".join(lines).rstrip() + "\n"
