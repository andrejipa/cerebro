from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.control_plane_guardrail_eval import ControlPlaneGuardrailReport
from experiments.control_plane_review_matrix import ControlPlaneReviewMatrix
from experiments.control_plane_review_packet import ControlPlaneReviewPacket
from experiments.control_plane_scenario_lab import (
    ControlPlaneAdversarialReport,
    ControlPlaneScenarioLabReport,
)
from experiments.control_plane_telemetry_projection import (
    ControlPlaneTelemetryEvent,
    ControlPlaneTelemetryProjection,
    ControlPlaneTelemetrySpan,
)


class ControlPlaneLineageInvariantError(ValueError):
    """Raised when a lineage invariant input crossed its advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneLineageInvariantFinding:
    code: str
    severity: str
    layer_pair: str
    source_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneLineageInvariantReport:
    schema_version: str
    eval_role: str
    eval_status: str
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneLineageInvariantFinding, ...]
    checked_layer_pairs: tuple[str, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory cross-layer invariant evaluation only"
    eval_is_not_permission: bool = True
    invariant_pass_is_not_truth: bool = True
    finding_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


_PACKET_STATUS = {
    "packet_advisory_review_only": "observed_advisory_non_authoritative",
    "packet_blocked": "observed_blocked",
    "packet_human_review_required": "observed_human_review_required",
    "packet_replay_invalid": "observed_replay_invalid",
}


def _finding(
    code: str,
    severity: str,
    layer_pair: str,
    source_id: str,
    detail: str,
) -> ControlPlaneLineageInvariantFinding:
    return ControlPlaneLineageInvariantFinding(
        code=code,
        severity=severity,
        layer_pair=layer_pair,
        source_id=source_id,
        detail=detail,
    )


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _validate_non_authoritative(obj: object, label: str, guardrails: tuple[str, ...]) -> None:
    if getattr(obj, "state_change", None) != "none" or "non-authoritative" not in str(getattr(obj, "authority", "")):
        raise ControlPlaneLineageInvariantError(f"{label} must be non-authoritative with state_change none")
    missing = [guardrail for guardrail in guardrails if getattr(obj, guardrail, None) is not True]
    if missing:
        raise ControlPlaneLineageInvariantError(f"{label} guardrails must remain true: {', '.join(missing)}")


def _validate_projection(projection: ControlPlaneTelemetryProjection) -> None:
    _validate_non_authoritative(
        projection,
        "projection",
        (
            "projection_is_not_opentelemetry_export",
            "projection_is_not_export",
            "projection_is_not_permission",
            "telemetry_is_not_permission",
            "span_status_is_not_truth",
            "semconv_compat_is_not_stability",
            "must_not_execute_automatically",
        ),
    )
    if projection.span_count != len(projection.spans):
        raise ControlPlaneLineageInvariantError("projection span_count must match spans")
    if projection.event_count != sum(len(span.events) for span in projection.spans):
        raise ControlPlaneLineageInvariantError("projection event_count must match events")


def _events(spans: Iterable[ControlPlaneTelemetrySpan]) -> tuple[ControlPlaneTelemetryEvent, ...]:
    return tuple(event for span in spans for event in span.events)


def _events_named(spans: Iterable[ControlPlaneTelemetrySpan], event_name: str) -> tuple[ControlPlaneTelemetryEvent, ...]:
    return tuple(event for event in _events(spans) if event.name == event_name)


def _spans_with_attribute(
    projection: ControlPlaneTelemetryProjection,
    name: str,
    value: object,
) -> tuple[ControlPlaneTelemetrySpan, ...]:
    return tuple(span for span in projection.spans if span.attributes.get(name) == value)


def _json_counts(value: object) -> dict[str, int]:
    if not isinstance(value, str):
        return {}
    try:
        payload = json.loads(value)
    except json.JSONDecodeError:
        return {}
    if not isinstance(payload, dict):
        return {}
    counts: dict[str, int] = {}
    for key, item in payload.items():
        if isinstance(key, str) and isinstance(item, int):
            counts[key] = item
    return counts


def _report(
    findings: Iterable[ControlPlaneLineageInvariantFinding],
    *,
    layer_pair: str,
) -> ControlPlaneLineageInvariantReport:
    finding_items = tuple(findings)
    report = ControlPlaneLineageInvariantReport(
        schema_version="1",
        eval_role="evaluates_control_plane_cross_layer_lineage_invariants",
        eval_status="lineage_drift_observed" if finding_items else "lineage_invariants_preserved",
        finding_count=len(finding_items),
        severity_counts=_count(finding.severity for finding in finding_items),
        finding_codes=tuple(finding.code for finding in finding_items),
        findings=finding_items,
        checked_layer_pairs=(layer_pair,),
    )
    _validate_report(report)
    return report


def _validate_report(report: ControlPlaneLineageInvariantReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneLineageInvariantError("report must be non-authoritative with state_change none")
    if (
        not report.eval_is_not_permission
        or not report.invariant_pass_is_not_truth
        or not report.finding_is_not_execution_approval
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneLineageInvariantError("report guardrails must remain true")
    if report.finding_count != len(report.findings):
        raise ControlPlaneLineageInvariantError("finding_count must match findings")


def evaluate_control_plane_packet_projection_lineage(
    packet: ControlPlaneReviewPacket,
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneLineageInvariantReport:
    _validate_non_authoritative(
        packet,
        "packet",
        (
            "packet_is_not_permission",
            "replay_pass_is_not_truth",
            "packet_pass_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    _validate_projection(projection)
    layer_pair = "review_packet->telemetry_projection"
    findings: list[ControlPlaneLineageInvariantFinding] = []
    spans = _spans_with_attribute(projection, "cerebro.control_plane.trace_id", packet.trace_id)
    if len(spans) != 1:
        findings.append(
            _finding("packet_trace_span_count_mismatch", "critical", layer_pair, packet.trace_id, f"expected 1 span, observed {len(spans)}")
        )
        return _report(findings, layer_pair=layer_pair)

    span = spans[0]
    if span.attributes.get("cerebro.control_plane.packet_verdict") != packet.packet_verdict:
        findings.append(
            _finding("packet_verdict_projection_mismatch", "critical", layer_pair, packet.trace_id, "packet verdict changed in projection")
        )
    expected_status = _PACKET_STATUS.get(packet.packet_verdict)
    if expected_status is not None and span.status != expected_status:
        findings.append(
            _finding("packet_status_projection_mismatch", "critical", layer_pair, packet.trace_id, f"expected {expected_status}, observed {span.status}")
        )
    if span.attributes.get("cerebro.control_plane.blocker_count") != len(packet.blockers):
        findings.append(
            _finding("packet_blocker_count_mismatch", "high", layer_pair, packet.trace_id, "blocker count changed in projection")
        )
    if span.attributes.get("cerebro.control_plane.trace_event_count") != packet.trace_event_count:
        findings.append(
            _finding("packet_trace_event_count_mismatch", "high", layer_pair, packet.trace_id, "trace_event_count changed in projection")
        )
    projected_fields = {
        "combined_review_status": packet.combined_review_status,
        "recommended_human_decision": packet.recommended_human_decision,
        "replay_digest": packet.replay_digest,
        "replay_evaluation_verdict": packet.replay_evaluation_verdict,
        "replay_status": packet.replay_status,
    }
    for field, expected in projected_fields.items():
        observed = span.attributes.get(f"cerebro.control_plane.{field}")
        if observed != expected:
            findings.append(
                _finding(
                    f"packet_{field}_mismatch",
                    "critical",
                    layer_pair,
                    packet.trace_id,
                    f"expected {expected}, observed {observed}",
                )
            )

    blocker_events = _events_named(spans, "cerebro.control_plane.blocker_observed")
    observed_blockers = {str(event.attributes.get("cerebro.control_plane.blocker")) for event in blocker_events}
    for blocker in packet.blockers:
        if blocker not in observed_blockers:
            findings.append(
                _finding("packet_blocker_event_missing", "high", layer_pair, packet.trace_id, f"missing blocker event: {blocker}")
            )

    replay_issue_events = _events_named(spans, "cerebro.control_plane.replay_issue_observed")
    observed_issues = {str(event.attributes.get("cerebro.control_plane.replay_issue_code")) for event in replay_issue_events}
    for issue_code in packet.replay_issue_codes:
        if issue_code not in observed_issues:
            findings.append(
                _finding("packet_replay_issue_event_missing", "high", layer_pair, packet.trace_id, f"missing replay issue event: {issue_code}")
            )
    trace_events = tuple(
        event
        for event in span.events
        if event.name.startswith("cerebro.control_plane.")
        and event.name
        not in {
            "cerebro.control_plane.blocker_observed",
            "cerebro.control_plane.replay_issue_observed",
        }
    )
    if len(trace_events) != len(packet.trace.trace_events):
        findings.append(
            _finding(
                "packet_trace_event_projection_count_mismatch",
                "high",
                layer_pair,
                packet.trace_id,
                f"expected {len(packet.trace.trace_events)} trace events, observed {len(trace_events)}",
            )
        )
    for sequence, trace_event in enumerate(packet.trace.trace_events, start=1):
        observed = next(
            (
                event
                for event in trace_events
                if event.attributes.get("cerebro.control_plane.sequence") == sequence
            ),
            None,
        )
        if observed is None:
            findings.append(_finding("packet_trace_event_missing", "high", layer_pair, packet.trace_id, f"missing trace event sequence {sequence}"))
            continue
        expected_name = f"cerebro.control_plane.{trace_event.event_type}"
        if observed.name != expected_name:
            findings.append(_finding("packet_trace_event_type_mismatch", "high", layer_pair, packet.trace_id, f"expected {expected_name}, observed {observed.name}"))
        if observed.attributes.get("cerebro.control_plane.subject") != trace_event.subject:
            findings.append(_finding("packet_trace_event_subject_mismatch", "high", layer_pair, packet.trace_id, f"trace event subject changed at sequence {sequence}"))
        if observed.attributes.get("cerebro.control_plane.detail") != trace_event.detail:
            findings.append(_finding("packet_trace_event_detail_mismatch", "high", layer_pair, packet.trace_id, f"trace event detail changed at sequence {sequence}"))
    return _report(findings, layer_pair=layer_pair)


def evaluate_control_plane_matrix_projection_lineage(
    matrix: ControlPlaneReviewMatrix,
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneLineageInvariantReport:
    _validate_non_authoritative(
        matrix,
        "matrix",
        (
            "matrix_is_not_permission",
            "matrix_pass_is_not_execution_approval",
            "replay_pass_is_not_truth",
            "must_not_execute_automatically",
        ),
    )
    _validate_projection(projection)
    layer_pair = "review_matrix->telemetry_projection"
    findings: list[ControlPlaneLineageInvariantFinding] = []
    spans = tuple(span for span in projection.spans if span.name == "cerebro.control_plane.review_matrix")
    if len(spans) != 1:
        findings.append(_finding("matrix_span_count_mismatch", "critical", layer_pair, "matrix", f"expected 1 matrix span, observed {len(spans)}"))
        return _report(findings, layer_pair=layer_pair)
    span = spans[0]
    if span.attributes.get("cerebro.control_plane.packet_count") != matrix.packet_count:
        findings.append(_finding("matrix_packet_count_mismatch", "critical", layer_pair, "matrix", "packet_count changed in projection"))
    if span.attributes.get("cerebro.control_plane.required_human_decision_count") != len(matrix.required_human_decisions):
        findings.append(_finding("matrix_human_decision_count_mismatch", "high", layer_pair, "matrix", "human decision count changed in projection"))
    summary_fields = {
        "packet_verdict_counts": matrix.packet_verdict_counts,
        "combined_review_status_counts": matrix.combined_review_status_counts,
        "replay_evaluation_verdict_counts": matrix.replay_evaluation_verdict_counts,
    }
    for field, expected in summary_fields.items():
        observed = _json_counts(span.attributes.get(f"cerebro.control_plane.{field}"))
        if observed != expected:
            findings.append(_finding(f"matrix_{field}_mismatch", "high", layer_pair, "matrix", f"expected {expected}, observed {observed}"))

    row_events = _events_named(spans, "cerebro.control_plane.review_matrix.row_observed")
    if len(row_events) != matrix.packet_count:
        findings.append(_finding("matrix_row_event_count_mismatch", "high", layer_pair, "matrix", f"expected {matrix.packet_count} row events, observed {len(row_events)}"))
    observed_trace_ids = {str(event.attributes.get("cerebro.control_plane.trace_id")) for event in row_events}
    for row in matrix.rows:
        if row.trace_id not in observed_trace_ids:
            findings.append(_finding("matrix_row_event_missing", "high", layer_pair, row.trace_id, "matrix row disappeared in projection"))
            continue
        row_event = next(
            event
            for event in row_events
            if event.attributes.get("cerebro.control_plane.trace_id") == row.trace_id
        )
        row_fields = {
            "packet_verdict": row.packet_verdict,
            "combined_review_status": row.combined_review_status,
            "replay_evaluation_verdict": row.replay_evaluation_verdict,
            "required_human_decision": row.recommended_human_decision,
        }
        for field, expected in row_fields.items():
            observed = row_event.attributes.get(f"cerebro.control_plane.{field}")
            if observed != expected:
                findings.append(_finding(f"matrix_row_{field}_mismatch", "high", layer_pair, row.trace_id, f"expected {expected}, observed {observed}"))
    observed_human_decisions = {
        str(event.attributes.get("cerebro.control_plane.required_human_decision"))
        for event in row_events
        if str(event.attributes.get("cerebro.control_plane.required_human_decision")) != "none"
    }
    for decision in matrix.required_human_decisions:
        if decision not in observed_human_decisions:
            findings.append(_finding("matrix_human_decision_missing", "high", layer_pair, decision, "required human decision disappeared in projection"))
    return _report(findings, layer_pair=layer_pair)


def evaluate_control_plane_lab_projection_lineage(
    report: ControlPlaneScenarioLabReport,
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneLineageInvariantReport:
    _validate_non_authoritative(
        report,
        "scenario lab report",
        (
            "lab_is_not_permission",
            "expectation_match_is_not_execution_approval",
            "replay_pass_is_not_truth",
            "must_not_execute_automatically",
        ),
    )
    _validate_projection(projection)
    layer_pair = "scenario_lab->telemetry_projection"
    findings: list[ControlPlaneLineageInvariantFinding] = []
    root_spans = tuple(span for span in projection.spans if span.name == "cerebro.control_plane.scenario_lab")
    if len(root_spans) != 1:
        findings.append(_finding("scenario_lab_root_span_count_mismatch", "critical", layer_pair, "scenario_lab", f"expected 1 root span, observed {len(root_spans)}"))
        return _report(findings, layer_pair=layer_pair)
    root = root_spans[0]
    if root.attributes.get("cerebro.control_plane.scenario_count") != report.scenario_count:
        findings.append(_finding("scenario_count_mismatch", "critical", layer_pair, "scenario_lab", "scenario_count changed in projection"))
    if root.attributes.get("cerebro.control_plane.expectation_failure_count") != report.expectation_failure_count:
        findings.append(_finding("expectation_failure_count_mismatch", "high", layer_pair, "scenario_lab", "expectation failure count changed in projection"))

    drift_events = _events_named(root_spans, "cerebro.control_plane.scenario_expectation_drift_observed")
    observed_drift_ids = {str(event.attributes.get("cerebro.control_plane.scenario_id")) for event in drift_events}
    for scenario_id in report.scenarios_with_expectation_drift:
        if scenario_id not in observed_drift_ids:
            findings.append(_finding("scenario_drift_event_missing", "high", layer_pair, scenario_id, "scenario drift disappeared in projection"))
    failure_events = _events_named(projection.spans, "cerebro.control_plane.expectation_failure_observed")
    if len(failure_events) != report.expectation_failure_count:
        findings.append(
            _finding(
                "expectation_failure_event_count_mismatch",
                "high",
                layer_pair,
                "scenario_lab",
                f"expected {report.expectation_failure_count} expectation failure events, observed {len(failure_events)}",
            )
        )
    observed_failures = {
        (
            str(event.attributes.get("cerebro.control_plane.scenario_id")),
            str(event.attributes.get("cerebro.control_plane.expectation_failure")),
        )
        for event in failure_events
    }
    child_scenario_ids = {
        str(span.attributes.get("cerebro.control_plane.scenario_id"))
        for span in projection.spans
        if span.name == "cerebro.control_plane.scenario"
    }
    for result in report.results:
        child_span = next(
            (
                span
                for span in projection.spans
                if span.name == "cerebro.control_plane.scenario"
                and span.attributes.get("cerebro.control_plane.scenario_id") == result.scenario_id
            ),
            None,
        )
        if result.scenario_id not in child_scenario_ids or child_span is None:
            findings.append(_finding("scenario_child_span_missing", "high", layer_pair, result.scenario_id, "scenario result span disappeared in projection"))
        else:
            if child_span.status != result.expectation_status:
                findings.append(_finding("scenario_child_status_mismatch", "high", layer_pair, result.scenario_id, f"expected {result.expectation_status}, observed {child_span.status}"))
            scenario_fields = {
                "packet_verdict": result.packet_verdict,
                "combined_review_status": result.combined_review_status,
                "replay_evaluation_verdict": result.replay_evaluation_verdict,
                "required_human_decision": result.recommended_human_decision,
                "expectation_status": result.expectation_status,
                "blocker_count": result.blocker_count,
            }
            for field, expected in scenario_fields.items():
                observed = child_span.attributes.get(f"cerebro.control_plane.{field}")
                if observed != expected:
                    findings.append(_finding(f"scenario_child_{field}_mismatch", "high", layer_pair, result.scenario_id, f"expected {expected}, observed {observed}"))
        for failure in result.expectation_failures:
            if (result.scenario_id, failure) not in observed_failures:
                findings.append(_finding("scenario_expectation_failure_event_missing", "high", layer_pair, result.scenario_id, f"missing expectation failure event: {failure}"))
    return _report(findings, layer_pair=layer_pair)


def evaluate_control_plane_adversarial_projection_lineage(
    report: ControlPlaneAdversarialReport,
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneLineageInvariantReport:
    _validate_non_authoritative(
        report,
        "adversarial report",
        (
            "lab_is_not_permission",
            "adversarial_findings_are_not_execution_approval",
            "replay_pass_is_not_truth",
            "must_not_execute_automatically",
        ),
    )
    _validate_projection(projection)
    layer_pair = "adversarial_report->telemetry_projection"
    findings: list[ControlPlaneLineageInvariantFinding] = []
    root_spans = tuple(span for span in projection.spans if span.name == "cerebro.control_plane.adversarial_lab")
    if len(root_spans) != 1:
        findings.append(_finding("adversarial_root_span_count_mismatch", "critical", layer_pair, "adversarial_report", f"expected 1 root span, observed {len(root_spans)}"))
        return _report(findings, layer_pair=layer_pair)
    root = root_spans[0]
    if root.attributes.get("cerebro.control_plane.finding_count") != report.finding_count:
        findings.append(_finding("adversarial_finding_count_mismatch", "critical", layer_pair, "adversarial_report", "finding_count changed in projection"))

    finding_events = _events_named(root_spans, "cerebro.control_plane.adversarial_finding_observed")
    if len(finding_events) != report.finding_count:
        findings.append(
            _finding(
                "adversarial_finding_event_count_mismatch",
                "high",
                layer_pair,
                "adversarial_report",
                f"expected {report.finding_count} finding events, observed {len(finding_events)}",
            )
        )
    observed_finding_keys = {
        (
            str(event.attributes.get("cerebro.control_plane.probe_id")),
            str(event.attributes.get("cerebro.control_plane.finding_code")),
            str(event.attributes.get("cerebro.control_plane.finding_severity")),
            str(event.attributes.get("cerebro.control_plane.finding_detail")),
        )
        for event in finding_events
    }
    observed_probe_ids = {str(event.attributes.get("cerebro.control_plane.probe_id")) for event in finding_events}
    for finding in report.findings:
        if finding.probe_id not in observed_probe_ids:
            findings.append(_finding("adversarial_finding_event_missing", "high", layer_pair, finding.probe_id, "adversarial finding disappeared in projection"))
        if (finding.probe_id, finding.code, finding.severity, finding.detail) not in observed_finding_keys:
            findings.append(_finding("adversarial_finding_detail_missing", "high", layer_pair, finding.probe_id, f"missing finding event details: {finding.code}"))
    child_probe_spans = {
        str(span.attributes.get("cerebro.control_plane.probe_id")): span
        for span in projection.spans
        if span.name == "cerebro.control_plane.adversarial_probe"
    }
    for result in report.results:
        span = child_probe_spans.get(result.probe_id)
        if span is None:
            findings.append(_finding("adversarial_probe_span_missing", "high", layer_pair, result.probe_id, "adversarial probe span disappeared in projection"))
            continue
        if span.status != result.probe_status:
            findings.append(_finding("adversarial_probe_status_mismatch", "high", layer_pair, result.probe_id, f"expected {result.probe_status}, observed {span.status}"))
        probe_fields = {
            "probe_kind": result.probe_kind,
            "expectation_status": result.expectation_status,
        }
        for field, expected in probe_fields.items():
            observed = span.attributes.get(f"cerebro.control_plane.{field}")
            if observed != expected:
                findings.append(_finding(f"adversarial_probe_{field}_mismatch", "high", layer_pair, result.probe_id, f"expected {expected}, observed {observed}"))
        if span.attributes.get("cerebro.control_plane.finding_count") != len(result.finding_codes):
            findings.append(_finding("adversarial_probe_finding_count_mismatch", "high", layer_pair, result.probe_id, "probe finding_count changed in projection"))
    return _report(findings, layer_pair=layer_pair)


def evaluate_control_plane_guardrail_eval_lineage(
    projection: ControlPlaneTelemetryProjection,
    guardrail_report: ControlPlaneGuardrailReport,
) -> ControlPlaneLineageInvariantReport:
    _validate_projection(projection)
    _validate_non_authoritative(
        guardrail_report,
        "guardrail report",
        (
            "eval_is_not_permission",
            "finding_is_not_truth",
            "finding_is_not_execution_approval",
            "must_not_execute_automatically",
        ),
    )
    layer_pair = "telemetry_projection->guardrail_eval"
    findings: list[ControlPlaneLineageInvariantFinding] = []
    if guardrail_report.eval_status not in {"guardrails_preserved", "guardrail_drift_observed"}:
        findings.append(_finding("guardrail_eval_status_unknown", "high", layer_pair, "guardrail_eval", f"unknown eval_status: {guardrail_report.eval_status}"))
    if guardrail_report.source_projection_role != projection.projection_role:
        findings.append(_finding("guardrail_source_projection_role_mismatch", "high", layer_pair, "guardrail_eval", "source projection role does not match projection"))
    if guardrail_report.source_span_count != projection.span_count:
        findings.append(_finding("guardrail_source_span_count_mismatch", "critical", layer_pair, "guardrail_eval", "source_span_count does not match projection"))
    if guardrail_report.source_event_count != projection.event_count:
        findings.append(_finding("guardrail_source_event_count_mismatch", "critical", layer_pair, "guardrail_eval", "source_event_count does not match projection"))
    if guardrail_report.finding_count != len(guardrail_report.findings):
        findings.append(_finding("guardrail_finding_count_mismatch", "critical", layer_pair, "guardrail_eval", "finding_count does not match findings"))
    if guardrail_report.finding_codes != tuple(finding.code for finding in guardrail_report.findings):
        findings.append(_finding("guardrail_finding_codes_mismatch", "high", layer_pair, "guardrail_eval", "finding_codes do not match findings"))
    if guardrail_report.category_counts != _count(finding.category for finding in guardrail_report.findings):
        findings.append(_finding("guardrail_category_counts_mismatch", "high", layer_pair, "guardrail_eval", "category_counts do not match findings"))
    if guardrail_report.severity_counts != _count(finding.severity for finding in guardrail_report.findings):
        findings.append(_finding("guardrail_severity_counts_mismatch", "high", layer_pair, "guardrail_eval", "severity_counts do not match findings"))
    if guardrail_report.finding_count == 0 and guardrail_report.eval_status != "guardrails_preserved":
        findings.append(_finding("guardrail_zero_findings_status_mismatch", "high", layer_pair, "guardrail_eval", "zero findings must use guardrails_preserved status"))
    if guardrail_report.finding_count > 0 and guardrail_report.eval_status != "guardrail_drift_observed":
        findings.append(_finding("guardrail_nonzero_findings_status_mismatch", "high", layer_pair, "guardrail_eval", "nonzero findings must use guardrail_drift_observed status"))
    return _report(findings, layer_pair=layer_pair)


def render_control_plane_lineage_invariant_json(report: ControlPlaneLineageInvariantReport) -> str:
    _validate_report(report)
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_lineage_invariant_markdown(report: ControlPlaneLineageInvariantReport) -> str:
    _validate_report(report)
    lines = [
        "# Control Plane Lineage Invariant Evaluation",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory cross-layer invariant evaluation only",
        "- eval_is_not_permission: true",
        "- invariant_pass_is_not_truth: true",
        "- finding_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- eval_role: {report.eval_role}",
        f"- eval_status: {report.eval_status}",
        f"- checked_layer_pairs: {', '.join(report.checked_layer_pairs)}",
        f"- finding_count: {report.finding_count}",
        f"- severity_counts: {report.severity_counts}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("- none")
    else:
        for finding in report.findings:
            lines.append(
                f"- {finding.severity}:{finding.layer_pair}:{finding.code} "
                f"for {finding.source_id} - {finding.detail}"
            )
    return "\n".join(lines).rstrip() + "\n"
