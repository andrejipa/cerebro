from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from pathlib import Path
from typing import Any, Mapping

from .diff import TRACE_DIFF_AUTHORITY, TRACE_DIFF_SCHEMA_VERSION


SELF_AUDIT_SCHEMA_VERSION = "1"
SELF_AUDIT_AUTHORITY = "non-authoritative; advisory protocol self-audit evidence only"

_VALID_SEVERITY = {"info", "low", "medium", "high", "blocking"}
_REQUIRED_DIFF_BOUNDARIES = {
    "mutate state",
    "register sources",
    "act as runtime gate",
    "create canonical claim graph",
    "promote or demote authority",
    "treat trace diff as permission",
}


@dataclass(frozen=True)
class ProtocolAuditCandidate:
    candidate_id: str
    category: str
    severity: str
    signal: str
    evidence: tuple[str, ...]
    recommendation: str
    human_action: str
    state_change: str = "none"
    authority: str = SELF_AUDIT_AUTHORITY

    def __post_init__(self) -> None:
        if not self.candidate_id:
            raise ValueError("candidate_id is required")
        if not self.category:
            raise ValueError("category is required")
        if self.severity not in _VALID_SEVERITY:
            raise ValueError(f"invalid severity: {self.severity}")
        if not self.signal:
            raise ValueError("signal is required")
        if not self.evidence:
            raise ValueError("evidence is required")
        if not self.recommendation:
            raise ValueError("recommendation is required")
        if not self.human_action:
            raise ValueError("human_action is required")
        if self.state_change != "none":
            raise ValueError("protocol self-audit candidates must not change state")

    def to_dict(self) -> dict[str, Any]:
        return {
            "candidate_id": self.candidate_id,
            "category": self.category,
            "severity": self.severity,
            "signal": self.signal,
            "evidence": list(self.evidence),
            "recommendation": self.recommendation,
            "human_action": self.human_action,
            "state_change": self.state_change,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class ProtocolSelfAuditReport:
    candidates: tuple[ProtocolAuditCandidate, ...]
    source_label: str
    state_change: str = "none"
    authority: str = SELF_AUDIT_AUTHORITY
    report_role: str = "advisory protocol self-audit candidates only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("protocol self-audit reports must not change state")
        if not self.source_label:
            raise ValueError("source_label is required")

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def high_or_blocking_count(self) -> int:
        return sum(1 for candidate in self.candidates if candidate.severity in {"high", "blocking"})

    @property
    def action_readiness(self) -> str:
        if self.high_or_blocking_count:
            return "human_review_recommended"
        if self.candidates:
            return "advisory_report_allowed"
        return "observe_only"

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": SELF_AUDIT_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "report_role": self.report_role,
            "source_label": self.source_label,
            "action_readiness": self.action_readiness,
            "candidate_count": self.candidate_count,
            "high_or_blocking_count": self.high_or_blocking_count,
            "guardrails": {
                "self_audit_is_not_memory": True,
                "self_audit_is_not_permission": True,
                "self_audit_is_not_authority": True,
                "self_audit_candidates_require_review": True,
                "anti_noise_no_auto_learning": True,
                "silence_is_not_negative_evidence": True,
            },
            "candidates": [candidate.to_dict() for candidate in self.candidates],
            "boundary": {
                "may_suggest": [
                    "inspect protocol drift",
                    "request human review",
                    "propose a future trigger",
                    "write a candidate learning item for review",
                ],
                "must_not_apply": [
                    "mutate state",
                    "write memory automatically",
                    "register sources",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat self-audit as permission",
                ],
            },
        }


def load_trace_diff_json(path: str | Path) -> dict[str, Any]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    return _validate_trace_diff_payload(payload)


def audit_protocol_from_trace_diff(
    trace_diff: Mapping[str, Any],
    *,
    source_label: str = "trace-diff",
    churn_threshold: int = 10,
) -> ProtocolSelfAuditReport:
    payload = _validate_trace_diff_payload(trace_diff)
    candidates: list[ProtocolAuditCandidate] = []
    _append_boundary_candidates(candidates, payload)
    _append_regression_candidates(candidates, payload)
    _append_risk_candidates(candidates, payload)
    _append_guardrail_candidates(candidates, payload)
    _append_churn_candidates(candidates, payload, churn_threshold=churn_threshold)
    _append_source_drift_candidates(candidates, payload)
    return ProtocolSelfAuditReport(candidates=tuple(candidates), source_label=source_label)


def render_protocol_self_audit_json(report: ProtocolSelfAuditReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_protocol_self_audit_markdown(report: ProtocolSelfAuditReport) -> str:
    lines = [
        "# Epistemic Protocol Self-Audit",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- report_role: {report.report_role}",
        "- self_audit_is_not_memory: true",
        "- self_audit_is_not_permission: true",
        "- anti_noise_no_auto_learning: true",
        "",
        "## Summary",
        "",
        f"- source_label: `{report.source_label}`",
        f"- action_readiness: `{report.action_readiness}`",
        f"- candidate_count: `{report.candidate_count}`",
        f"- high_or_blocking_count: `{report.high_or_blocking_count}`",
        "",
        "## Candidates",
        "",
    ]
    if not report.candidates:
        lines.append("- none")
        lines.append("")
    for candidate in report.candidates:
        lines.extend(
            [
                f"### {candidate.candidate_id}",
                "",
                f"- category: `{candidate.category}`",
                f"- severity: `{candidate.severity}`",
                f"- signal: {candidate.signal}",
                f"- recommendation: {candidate.recommendation}",
                f"- human_action: `{candidate.human_action}`",
                "- evidence:",
            ]
        )
        lines.extend(f"  - {item}" for item in candidate.evidence)
        lines.extend(
            [
                f"- state_change: {candidate.state_change}",
                f"- authority: {candidate.authority}",
                "",
            ]
        )
    lines.extend(
        [
            "## Must Not Apply",
            "",
            "- mutate state",
            "- write memory automatically",
            "- register sources",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat self-audit as permission",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_trace_diff_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("trace diff payload must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != TRACE_DIFF_SCHEMA_VERSION:
        raise ValueError(f"unsupported trace diff schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("trace diff must declare state_change = none")
    if result.get("authority") != TRACE_DIFF_AUTHORITY:
        raise ValueError(f"unsupported trace diff authority: {result.get('authority')}")
    return result


def _candidate(
    category: str,
    severity: str,
    signal: str,
    evidence: tuple[str, ...],
    recommendation: str,
    human_action: str,
) -> ProtocolAuditCandidate:
    digest = hashlib.sha256(
        "\n".join((category, severity, signal, *evidence, recommendation, human_action)).encode("utf-8")
    ).hexdigest()[:16]
    return ProtocolAuditCandidate(
        candidate_id=f"{category}-{digest}",
        category=category,
        severity=severity,
        signal=signal,
        evidence=evidence,
        recommendation=recommendation,
        human_action=human_action,
    )


def _append_boundary_candidates(candidates: list[ProtocolAuditCandidate], payload: Mapping[str, Any]) -> None:
    boundary = payload.get("boundary")
    if not isinstance(boundary, Mapping):
        candidates.append(
            _candidate(
                "anti_permission_boundary_missing",
                "high",
                "trace diff payload does not expose a boundary object",
                ("boundary object missing",),
                "Treat this diff as unusable for protocol learning until its boundary is restored.",
                "adjudicate_boundary",
            )
        )
        return
    must_not_apply = boundary.get("must_not_apply")
    if not isinstance(must_not_apply, list):
        missing = tuple(sorted(_REQUIRED_DIFF_BOUNDARIES))
    else:
        present = {str(item) for item in must_not_apply}
        missing = tuple(sorted(_REQUIRED_DIFF_BOUNDARIES - present))
    if missing:
        candidates.append(
            _candidate(
                "anti_permission_boundary_weak",
                "high",
                "trace diff is missing one or more anti-permission boundary clauses",
                tuple(f"missing: {item}" for item in missing),
                "Restore explicit must-not-apply clauses before treating the artifact as review evidence.",
                "approve_boundary_fix",
            )
        )


def _append_regression_candidates(candidates: list[ProtocolAuditCandidate], payload: Mapping[str, Any]) -> None:
    reasons = _string_tuple(payload.get("regression_reasons"))
    if payload.get("has_regression") is True or reasons:
        candidates.append(
            _candidate(
                "readiness_regression",
                "high",
                "trace diff reports readiness regression",
                reasons if reasons else ("has_regression=true",),
                "Pause promotion and inspect the specific regression before any follow-on slice.",
                "review_regression",
            )
        )


def _append_risk_candidates(candidates: list[ProtocolAuditCandidate], payload: Mapping[str, Any]) -> None:
    changes = _list_of_mappings(payload.get("risk_assessment_changes"))
    severe: list[str] = []
    moderate: list[str] = []
    for change in changes:
        field = str(change.get("field"))
        baseline = change.get("baseline")
        current = change.get("current")
        if field == "budget_status" and current == "exceeded":
            severe.append(f"budget_status: {baseline} -> {current}")
        elif field == "required_gate_level" and str(current) > str(baseline):
            severe.append(f"required_gate_level: {baseline} -> {current}")
        elif field == "human_approval_required" and current is True and baseline is False:
            moderate.append("human_approval_required: false -> true")
        elif field == "action_readiness" and current in {"blocked", "human_approval_required"}:
            severe.append(f"action_readiness: {baseline} -> {current}")
    if severe:
        candidates.append(
            _candidate(
                "risk_budget_degradation",
                "high",
                "risk assessment degraded between traces",
                tuple(severe),
                "Require human review before continuing the affected operational lane.",
                "review_risk_degradation",
            )
        )
    if moderate:
        candidates.append(
            _candidate(
                "risk_review_escalation",
                "medium",
                "risk assessment now requires extra review",
                tuple(moderate),
                "Record why review became necessary before treating the action as repeatable.",
                "acknowledge_review_escalation",
            )
        )


def _append_guardrail_candidates(candidates: list[ProtocolAuditCandidate], payload: Mapping[str, Any]) -> None:
    changes = _list_of_mappings(payload.get("guardrail_changes"))
    weakened = tuple(
        f"{change.get('field')}: {change.get('baseline')} -> {change.get('current')}"
        for change in changes
        if change.get("baseline") is True and change.get("current") is not True
    )
    if weakened:
        candidates.append(
            _candidate(
                "guardrail_weakening",
                "high",
                "one or more epistemic guardrails weakened",
                weakened,
                "Stop the lane until the guardrail drift is explained or reverted.",
                "adjudicate_guardrail_conflict",
            )
        )


def _append_churn_candidates(
    candidates: list[ProtocolAuditCandidate],
    payload: Mapping[str, Any],
    *,
    churn_threshold: int,
) -> None:
    candidate_diff = _mapping(payload.get("candidates"), "candidates")
    finding_diff = _mapping(payload.get("findings"), "findings")
    candidate_changes = _split_semantic_and_traceability_changes(_list_of_mappings(candidate_diff.get("changed")))
    finding_changes = _split_semantic_and_traceability_changes(_list_of_mappings(finding_diff.get("changed")))
    changed_candidates = candidate_changes[0]
    changed_findings = finding_changes[0]
    traceability_changed_candidates = (
        _list_of_mappings(candidate_diff.get("traceability_changed")) + candidate_changes[1]
    )
    traceability_changed_findings = _list_of_mappings(finding_diff.get("traceability_changed")) + finding_changes[1]
    semantic_total = len(changed_candidates) + len(changed_findings)
    traceability_total = len(traceability_changed_candidates) + len(traceability_changed_findings)
    if semantic_total >= churn_threshold:
        evidence = (
            f"changed_candidates={len(changed_candidates)}",
            f"changed_findings={len(changed_findings)}",
            f"candidate_identity_basis={candidate_diff.get('identity_basis')}",
            f"finding_identity_basis={finding_diff.get('identity_basis')}",
        )
        candidates.append(
            _candidate(
                "evidence_identity_churn",
                "medium",
                "many semantic trace entries changed without readiness regression",
                evidence,
                "Inspect whether semantic identity is too broad or too narrow before using this diff as stable replay evidence.",
                "review_identity_churn",
            )
        )
    if traceability_total >= churn_threshold:
        evidence = (
            f"traceability_changed_candidates={len(traceability_changed_candidates)}",
            f"traceability_changed_findings={len(traceability_changed_findings)}",
            f"candidate_identity_basis={candidate_diff.get('identity_basis')}",
            f"finding_identity_basis={finding_diff.get('identity_basis')}",
        )
        candidates.append(
            _candidate(
                "evidence_traceability_drift",
                "low",
                "many trace entries changed only in evidence identifiers or spans",
                evidence,
                "Treat this as proof-location drift, not semantic claim churn; inspect if stable baselines require refreshed evidence spans.",
                "acknowledge_traceability_drift",
            )
        )


def _split_semantic_and_traceability_changes(
    changes: list[dict[str, Any]],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    traceability_fields = {"claim_id", "semantic_id", "evidence_id", "evidence_span"}
    semantic: list[dict[str, Any]] = []
    traceability: list[dict[str, Any]] = []
    for change in changes:
        fields = change.get("changed_fields")
        if isinstance(fields, list) and fields and {str(field) for field in fields} <= traceability_fields:
            traceability.append(change)
        else:
            semantic.append(change)
    return semantic, traceability


def _append_source_drift_candidates(candidates: list[ProtocolAuditCandidate], payload: Mapping[str, Any]) -> None:
    source_diff = _mapping(payload.get("source_reads"), "source_reads")
    added = _string_tuple(source_diff.get("added"))
    removed = _string_tuple(source_diff.get("removed"))
    changed = _list_of_mappings(source_diff.get("changed"))
    if not added and not removed and not changed:
        return
    severity = "medium" if removed else "low"
    evidence = (
        f"added_sources={len(added)}",
        f"removed_sources={len(removed)}",
        f"changed_sources={len(changed)}",
    )
    candidates.append(
        _candidate(
            "source_surface_drift",
            severity,
            "source read surface changed between traces",
            evidence,
            "Check whether the changed source surface was expected before using the run as a stable baseline.",
            "acknowledge_source_drift",
        )
    )


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return dict(value)


def _list_of_mappings(value: Any) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError("expected a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError("expected a list of objects")
        result.append(dict(item))
    return result


def _string_tuple(value: Any) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError("expected a list of strings")
    return tuple(str(item) for item in value)
