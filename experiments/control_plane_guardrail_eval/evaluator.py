from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable

from experiments.control_plane_telemetry_projection import (
    ControlPlaneTelemetryEvent,
    ControlPlaneTelemetryProjection,
    ControlPlaneTelemetrySpan,
)


class ControlPlaneGuardrailEvalError(ValueError):
    """Raised when a guardrail evaluation input is malformed."""


@dataclass(frozen=True)
class ControlPlaneGuardrailFinding:
    code: str
    category: str
    severity: str
    location: str
    span_id: str
    event_name: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneGuardrailReport:
    schema_version: str
    eval_role: str
    source_projection_role: str
    eval_status: str
    finding_count: int
    category_counts: dict[str, int]
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneGuardrailFinding, ...]
    source_span_count: int
    source_event_count: int
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane guardrail evaluation only"
    eval_is_not_permission: bool = True
    finding_is_not_truth: bool = True
    finding_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


_FORBIDDEN_AUTHORITY_TOKENS = {
    "canonical_truth": "truth",
    "execution_approved": "permission",
    "permission_granted": "permission",
    "runtime_authority": "authority",
    "stable_semconv": "stability",
}

_FORBIDDEN_STATUS_TOKENS = (
    "approved",
    "approval_granted",
    "authorized",
    "executed",
    "execution_approved",
    "ok",
    "passed",
    "permission",
    "ready_to_execute",
    "success",
)

_NEGATIVE_MARKERS = (
    "_is_not_",
    "not_",
    "non-authoritative",
    "non_authoritative",
)

_FORBIDDEN_ATTRIBUTE_PREFIXES = (
    "gen_ai.input.",
    "gen_ai.output.",
    "gen_ai.usage.",
)

_FORBIDDEN_ATTRIBUTE_NAMES = {
    "gen_ai.input.messages",
    "gen_ai.output.messages",
    "gen_ai.request.model",
}

_PACKET_STATUS = {
    "packet_advisory_review_only": "observed_advisory_non_authoritative",
    "packet_blocked": "observed_blocked",
    "packet_human_review_required": "observed_human_review_required",
    "packet_replay_invalid": "observed_replay_invalid",
}


def _finding(
    code: str,
    category: str,
    severity: str,
    location: str,
    detail: str,
    *,
    span_id: str = "",
    event_name: str = "",
) -> ControlPlaneGuardrailFinding:
    return ControlPlaneGuardrailFinding(
        code=code,
        category=category,
        severity=severity,
        location=location,
        span_id=span_id,
        event_name=event_name,
        detail=detail,
    )


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _validate_projection_boundary(projection: ControlPlaneTelemetryProjection) -> None:
    if projection.state_change != "none" or "non-authoritative" not in projection.authority:
        raise ControlPlaneGuardrailEvalError("projection must be non-authoritative with state_change none")
    if (
        not projection.projection_is_not_opentelemetry_export
        or not projection.projection_is_not_export
        or not projection.projection_is_not_permission
        or not projection.telemetry_is_not_permission
        or not projection.span_status_is_not_truth
        or not projection.semconv_compat_is_not_stability
        or not projection.must_not_execute_automatically
    ):
        raise ControlPlaneGuardrailEvalError("projection guardrails must remain true")
    if projection.span_count != len(projection.spans):
        raise ControlPlaneGuardrailEvalError("projection span_count must match spans")
    if projection.event_count != sum(len(span.events) for span in projection.spans):
        raise ControlPlaneGuardrailEvalError("projection event_count must match events")
    if not projection.spans:
        raise ControlPlaneGuardrailEvalError("projection must contain at least one span")


def _status_findings(span: ControlPlaneTelemetrySpan, index: int) -> tuple[ControlPlaneGuardrailFinding, ...]:
    status = span.status.lower()
    findings: list[ControlPlaneGuardrailFinding] = []
    for token in _FORBIDDEN_STATUS_TOKENS:
        if token in status:
            findings.append(
                _finding(
                    "span_status_launders_authority",
                    "authority",
                    "critical",
                    f"spans[{index}].status",
                    f"span status contains forbidden authority token: {token}",
                    span_id=span.span_id,
                )
            )
    packet_verdict = span.attributes.get("cerebro.control_plane.packet_verdict")
    expected_status = _PACKET_STATUS.get(str(packet_verdict))
    if expected_status is not None and span.status != expected_status:
        findings.append(
            _finding(
                "packet_status_contradiction",
                "truth",
                "high",
                f"spans[{index}]",
                f"packet verdict {packet_verdict} projected as {span.status}, expected {expected_status}",
                span_id=span.span_id,
            )
        )
    return tuple(findings)


def _text_laundering_findings(
    value: object,
    *,
    location: str,
    span_id: str = "",
    event_name: str = "",
) -> tuple[ControlPlaneGuardrailFinding, ...]:
    text = str(value).lower()
    if any(marker in text for marker in _NEGATIVE_MARKERS):
        return ()
    findings: list[ControlPlaneGuardrailFinding] = []
    for token, category in _FORBIDDEN_AUTHORITY_TOKENS.items():
        if token in text:
            findings.append(
                _finding(
                    "text_launders_authority",
                    category,
                    "high",
                    location,
                    f"text contains forbidden authority token: {token}",
                    span_id=span_id,
                    event_name=event_name,
                )
            )
    return tuple(findings)


def _attribute_findings(
    attributes: dict[str, object],
    *,
    location: str,
    require_span_guardrails: bool,
) -> tuple[ControlPlaneGuardrailFinding, ...]:
    findings: list[ControlPlaneGuardrailFinding] = []
    for name, value in attributes.items():
        if name in _FORBIDDEN_ATTRIBUTE_NAMES or any(name.startswith(prefix) for prefix in _FORBIDDEN_ATTRIBUTE_PREFIXES):
            findings.append(
                _finding(
                    "sensitive_genai_attribute_projected",
                    "stability",
                    "critical",
                    f"{location}.{name}",
                    "projection must not emit model, message, or token-usage attributes",
                )
            )
        if name == "otel.compat.exported" and value is not False:
            findings.append(
                _finding(
                    "telemetry_export_laundering",
                    "authority",
                    "critical",
                    f"{location}.{name}",
                    "projection claimed exported telemetry",
                )
            )
        if name == "otel.compat.profile" and "development" not in str(value):
            findings.append(
                _finding(
                    "semconv_stability_laundering",
                    "stability",
                    "high",
                    f"{location}.{name}",
                    "compatibility profile must remain development-marked",
                )
            )
        findings.extend(_text_laundering_findings(name, location=f"{location}.{name}"))
        findings.extend(_text_laundering_findings(value, location=f"{location}.{name}"))
    if require_span_guardrails and attributes.get("cerebro.control_plane.span_status_is_not_truth") is not True:
        findings.append(
            _finding(
                "span_truth_guardrail_missing",
                "truth",
                "critical",
                f"{location}.cerebro.control_plane.span_status_is_not_truth",
                "span status must be explicitly marked as non-truth evidence",
            )
        )
    return tuple(findings)


def _event_findings(event: ControlPlaneTelemetryEvent, span_index: int, event_index: int) -> tuple[ControlPlaneGuardrailFinding, ...]:
    location = f"spans[{span_index}].events[{event_index}]"
    findings = list(_attribute_findings(event.attributes, location=location, require_span_guardrails=False))
    findings.extend(_text_laundering_findings(event.name, location=f"{location}.name", event_name=event.name))
    if event.attributes.get("cerebro.control_plane.event_is_not_permission") is not True:
        findings.append(
            _finding(
                "event_permission_guardrail_missing",
                "permission",
                "high",
                f"{location}.cerebro.control_plane.event_is_not_permission",
                "telemetry event must be explicitly marked as non-permission evidence",
                event_name=event.name,
            )
        )
    return tuple(findings)


def _span_findings(span: ControlPlaneTelemetrySpan, index: int) -> tuple[ControlPlaneGuardrailFinding, ...]:
    findings: list[ControlPlaneGuardrailFinding] = []
    location = f"spans[{index}]"
    if span.kind != "INTERNAL":
        findings.append(
            _finding(
                "span_kind_drift",
                "authority",
                "high",
                f"{location}.kind",
                "projection spans must remain INTERNAL",
                span_id=span.span_id,
            )
        )
    findings.extend(_status_findings(span, index))
    findings.extend(_text_laundering_findings(span.name, location=f"{location}.name", span_id=span.span_id))
    findings.extend(_attribute_findings(span.attributes, location=location, require_span_guardrails=True))
    for event_index, event in enumerate(span.events):
        findings.extend(_event_findings(event, index, event_index))
    return tuple(findings)


def _projection_findings(projection: ControlPlaneTelemetryProjection) -> tuple[ControlPlaneGuardrailFinding, ...]:
    findings: list[ControlPlaneGuardrailFinding] = []
    if projection.semconv_status != "development":
        findings.append(
            _finding(
                "semconv_status_laundering",
                "stability",
                "critical",
                "projection.semconv_status",
                "GenAI semantic-convention compatibility must remain development-marked",
            )
        )
    if "development" not in projection.compatibility_profile:
        findings.append(
            _finding(
                "compatibility_profile_lacks_development_marker",
                "stability",
                "high",
                "projection.compatibility_profile",
                "compatibility profile must not imply stable OTel compliance",
            )
        )
    for index, span in enumerate(projection.spans):
        findings.extend(_span_findings(span, index))
    return tuple(findings)


def _validate_report(report: ControlPlaneGuardrailReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneGuardrailEvalError("report must be non-authoritative with state_change none")
    if (
        not report.eval_is_not_permission
        or not report.finding_is_not_truth
        or not report.finding_is_not_execution_approval
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneGuardrailEvalError("report guardrails must remain true")
    if report.finding_count != len(report.findings):
        raise ControlPlaneGuardrailEvalError("finding_count must match findings")


def evaluate_control_plane_telemetry_guardrails(
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneGuardrailReport:
    """Evaluate whether a telemetry projection preserved non-authority guardrails."""

    _validate_projection_boundary(projection)
    findings = _projection_findings(projection)
    report = ControlPlaneGuardrailReport(
        schema_version="1",
        eval_role="detects_control_plane_telemetry_authority_laundering",
        source_projection_role=projection.projection_role,
        eval_status="guardrail_drift_observed" if findings else "guardrails_preserved",
        finding_count=len(findings),
        category_counts=_count(finding.category for finding in findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
        source_span_count=projection.span_count,
        source_event_count=projection.event_count,
    )
    _validate_report(report)
    return report


def render_control_plane_guardrail_eval_json(report: ControlPlaneGuardrailReport) -> str:
    _validate_report(report)
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_guardrail_eval_markdown(report: ControlPlaneGuardrailReport) -> str:
    _validate_report(report)
    lines = [
        "# Control Plane Guardrail Evaluation",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane guardrail evaluation only",
        "- eval_is_not_permission: true",
        "- finding_is_not_truth: true",
        "- finding_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- eval_role: {report.eval_role}",
        f"- source_projection_role: {report.source_projection_role}",
        f"- eval_status: {report.eval_status}",
        f"- finding_count: {report.finding_count}",
        f"- category_counts: {report.category_counts}",
        f"- severity_counts: {report.severity_counts}",
        f"- source_span_count: {report.source_span_count}",
        f"- source_event_count: {report.source_event_count}",
        "",
        "## Findings",
        "",
    ]
    if not report.findings:
        lines.append("- none")
    else:
        for finding in report.findings:
            lines.append(
                f"- {finding.severity}:{finding.category}:{finding.code} "
                f"at {finding.location} - {finding.detail}"
            )
    return "\n".join(lines).rstrip() + "\n"


def evaluate_control_plane_guardrails(
    projection: ControlPlaneTelemetryProjection,
) -> ControlPlaneGuardrailReport:
    return evaluate_control_plane_telemetry_guardrails(projection)
