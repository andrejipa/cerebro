from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .baseline_lifecycle import BASELINE_LIFECYCLE_AUTHORITY, BASELINE_LIFECYCLE_SCHEMA_VERSION
from .drift_policy import DRIFT_POLICY_AUTHORITY, DRIFT_POLICY_SCHEMA_VERSION
from .self_audit import SELF_AUDIT_AUTHORITY, SELF_AUDIT_SCHEMA_VERSION
from .trace import TRACE_AUTHORITY, TRACE_SCHEMA_VERSION


METACOGNITIVE_HANDOFF_SCHEMA_VERSION = "1"
METACOGNITIVE_HANDOFF_AUTHORITY = (
    "non-authoritative; advisory metacognitive handoff evidence only"
)

_VALID_HUMAN_DECISIONS = {
    "none",
    "acknowledge",
    "approve_baseline_refresh",
    "review_blockers",
    "adjudicate_conflict",
    "provide_missing_evidence",
}
_VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "advisory_report_allowed",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class MetacognitiveHandoffReport:
    source_count: int
    candidates_extracted: int
    findings_evaluated: int
    ready_count: int
    blocked_count: int
    insufficient_count: int
    known: tuple[str, ...]
    unknown: tuple[str, ...]
    conflicts: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    risk_notes: tuple[str, ...]
    recommended_human_decision: str
    action_readiness: str
    state_change: str = "none"
    authority: str = METACOGNITIVE_HANDOFF_AUTHORITY
    report_role: str = "advisory metacognitive handoff only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("metacognitive handoff reports must not change state")
        if self.recommended_human_decision not in _VALID_HUMAN_DECISIONS:
            raise ValueError(
                f"invalid recommended_human_decision: {self.recommended_human_decision}"
            )
        if self.action_readiness not in _VALID_ACTION_READINESS:
            raise ValueError(f"invalid action_readiness: {self.action_readiness}")
        for field_name, value in (
            ("source_count", self.source_count),
            ("candidates_extracted", self.candidates_extracted),
            ("findings_evaluated", self.findings_evaluated),
            ("ready_count", self.ready_count),
            ("blocked_count", self.blocked_count),
            ("insufficient_count", self.insufficient_count),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": METACOGNITIVE_HANDOFF_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "report_role": self.report_role,
            "summary": {
                "source_count": self.source_count,
                "candidates_extracted": self.candidates_extracted,
                "findings_evaluated": self.findings_evaluated,
                "ready_count": self.ready_count,
                "blocked_count": self.blocked_count,
                "insufficient_count": self.insufficient_count,
                "known_count": len(self.known),
                "unknown_count": len(self.unknown),
                "conflict_count": len(self.conflicts),
                "missing_evidence_count": len(self.missing_evidence),
                "risk_note_count": len(self.risk_notes),
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
            },
            "known": list(self.known),
            "unknown": list(self.unknown),
            "conflicts": list(self.conflicts),
            "missing_evidence": list(self.missing_evidence),
            "risk_notes": list(self.risk_notes),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "handoff_is_not_permission": True,
                "handoff_is_not_memory": True,
                "handoff_is_not_authority": True,
                "handoff_is_not_runtime_gate": True,
                "handoff_is_not_claim_graph": True,
            },
            "boundary": {
                "may_suggest": [
                    "summarize known evidence",
                    "summarize unknowns without treating silence as negative evidence",
                    "request human review",
                    "recommend a future trigger",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat handoff as permission",
                ],
            },
        }


def evaluate_metacognitive_handoff(
    readiness_trace: Mapping[str, Any],
    baseline_lifecycle: Mapping[str, Any],
    protocol_self_audit: Mapping[str, Any],
    drift_policy: Mapping[str, Any],
) -> MetacognitiveHandoffReport:
    trace_payload = _validate_trace_payload(readiness_trace)
    lifecycle_payload = _validate_lifecycle_payload(baseline_lifecycle)
    audit_payload = _validate_self_audit_payload(protocol_self_audit)
    drift_payload = _validate_drift_policy_payload(drift_policy)

    summary = _mapping(trace_payload.get("summary"), "summary")
    findings = _list_of_mappings(trace_payload.get("findings"), "findings")
    source_count = _int_value(summary.get("source_count"), "source_count")
    candidates_extracted = _int_value(summary.get("candidates_extracted"), "candidates_extracted")
    findings_evaluated = _int_value(summary.get("findings_evaluated"), "findings_evaluated")
    ready_count = _int_value(summary.get("ready_count"), "ready_count")
    blocked_count = _int_value(summary.get("blocked_count"), "blocked_count")
    insufficient_count = _int_value(summary.get("insufficient_count"), "insufficient_count")

    lifecycle_recommendation = _string_value(lifecycle_payload.get("recommendation"), "recommendation")
    lifecycle_human_action = _string_value(
        lifecycle_payload.get("required_human_action"), "required_human_action"
    )
    drift_classification = _string_value(drift_payload.get("classification"), "classification")
    drift_human_action = _string_value(
        drift_payload.get("required_human_action"), "required_human_action"
    )
    drift_action_readiness = _string_value(
        drift_payload.get("action_readiness"), "action_readiness"
    )
    audit_candidate_count = _int_value(audit_payload.get("candidate_count"), "candidate_count")
    audit_high_count = _int_value(audit_payload.get("high_or_blocking_count"), "high_or_blocking_count")

    known = [
        f"readiness trace covers {source_count} bounded source reads",
        f"{findings_evaluated} findings evaluated; {ready_count} ready; "
        f"{blocked_count} blocked; {insufficient_count} insufficient",
    ]
    if lifecycle_recommendation == "baseline_already_current":
        known.append("replay baseline and current trace match")
    if drift_classification == "no_drift":
        known.append("drift policy reports no drift and no action")
    if audit_candidate_count == 0 and audit_high_count == 0:
        known.append("protocol self-audit reports no candidates")

    unknown = [
        "bounded source heads do not prove full-project completeness",
        "silence is not negative evidence; absent claims are not evidence of absence",
        "readiness evidence does not grant permission to mutate state",
    ]
    conflicts = _finding_conflicts(findings)
    missing_evidence = _finding_missing_evidence(findings)
    risk_notes = [
        "registered != true",
        "retrieved != relevant",
        "remembered != trusted",
        "handoff output is advisory and not permission",
    ]

    if blocked_count:
        missing_evidence.append(f"{blocked_count} findings are blocked")
    if insufficient_count:
        missing_evidence.append(f"{insufficient_count} findings are insufficient")
    if lifecycle_human_action != "none":
        missing_evidence.append(f"baseline lifecycle requires human action: {lifecycle_human_action}")
    if drift_human_action != "none":
        missing_evidence.append(f"drift policy requires human action: {drift_human_action}")
    if audit_candidate_count:
        risk_notes.append(f"protocol self-audit reported {audit_candidate_count} candidates")
    if audit_high_count:
        missing_evidence.append(
            f"protocol self-audit reported {audit_high_count} high/blocking candidates"
        )
    if drift_classification != "no_drift":
        risk_notes.append(f"drift policy classification is {drift_classification}")

    regression_reasons = _regression_reasons(lifecycle_payload, drift_payload)
    conflicts.extend(regression_reasons)

    action_readiness: str
    recommended_human_decision: str
    if _has_blocker(lifecycle_payload, drift_payload, blocked_count, audit_high_count, regression_reasons):
        action_readiness = "blocked"
        recommended_human_decision = "review_blockers"
    elif conflicts:
        action_readiness = "human_approval_required"
        recommended_human_decision = "adjudicate_conflict"
    elif missing_evidence:
        action_readiness = "human_approval_required"
        recommended_human_decision = _first_human_action(
            drift_human_action,
            lifecycle_human_action,
            fallback="provide_missing_evidence",
        )
    elif drift_action_readiness == "advisory_report_allowed" or audit_candidate_count:
        action_readiness = "advisory_report_allowed"
        recommended_human_decision = "acknowledge"
    else:
        action_readiness = "no_action"
        recommended_human_decision = "none"

    return MetacognitiveHandoffReport(
        source_count=source_count,
        candidates_extracted=candidates_extracted,
        findings_evaluated=findings_evaluated,
        ready_count=ready_count,
        blocked_count=blocked_count,
        insufficient_count=insufficient_count,
        known=tuple(known),
        unknown=tuple(unknown),
        conflicts=tuple(conflicts),
        missing_evidence=tuple(missing_evidence),
        risk_notes=tuple(risk_notes),
        recommended_human_decision=recommended_human_decision,
        action_readiness=action_readiness,
    )


def render_metacognitive_handoff_json(report: MetacognitiveHandoffReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_metacognitive_handoff_markdown(report: MetacognitiveHandoffReport) -> str:
    lines = [
        "# Epistemic Readiness Metacognitive Handoff",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- report_role: {report.report_role}",
        "- handoff_is_not_permission: true",
        "- handoff_is_not_memory: true",
        "- handoff_is_not_authority: true",
        "- handoff_is_not_runtime_gate: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Decision",
        "",
        f"- recommended_human_decision: `{report.recommended_human_decision}`",
        f"- action_readiness: `{report.action_readiness}`",
        "",
        "## Summary",
        "",
        f"- source_count: `{report.source_count}`",
        f"- candidates_extracted: `{report.candidates_extracted}`",
        f"- findings_evaluated: `{report.findings_evaluated}`",
        f"- ready_count: `{report.ready_count}`",
        f"- blocked_count: `{report.blocked_count}`",
        f"- insufficient_count: `{report.insufficient_count}`",
        "",
    ]
    _append_section(lines, "Known", report.known)
    _append_section(lines, "Unknown", report.unknown)
    _append_section(lines, "Conflicts", report.conflicts)
    _append_section(lines, "Missing Evidence", report.missing_evidence)
    _append_section(lines, "Risk Notes", report.risk_notes)
    lines.extend(
        [
            "",
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat handoff as permission",
            "",
        ]
    )
    return "\n".join(lines)


def _append_section(lines: list[str], title: str, values: tuple[str, ...]) -> None:
    lines.extend([f"## {title}", ""])
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- none")
    lines.append("")


def _finding_conflicts(findings: list[dict[str, Any]]) -> list[str]:
    conflicts: list[str] = []
    for finding in findings:
        conflict = str(finding.get("conflict", "none"))
        if conflict != "none":
            conflicts.append(f"{finding.get('claim_id', 'unknown-claim')}: conflict={conflict}")
    return conflicts


def _finding_missing_evidence(findings: list[dict[str, Any]]) -> list[str]:
    missing: list[str] = []
    for finding in findings:
        sufficiency = str(finding.get("sufficiency", "unknown"))
        readiness = str(finding.get("operational_readiness", "unknown"))
        if sufficiency != "sufficient":
            missing.append(
                f"{finding.get('claim_id', 'unknown-claim')}: sufficiency={sufficiency}"
            )
        if readiness not in {"ready", "no_action"}:
            missing.append(
                f"{finding.get('claim_id', 'unknown-claim')}: operational_readiness={readiness}"
            )
    return missing


def _regression_reasons(
    lifecycle_payload: Mapping[str, Any],
    drift_payload: Mapping[str, Any],
) -> list[str]:
    reasons: list[str] = []
    for label, payload in (
        ("baseline lifecycle", lifecycle_payload),
        ("drift policy", drift_payload),
    ):
        regression = _mapping(payload.get("regression"), f"{label}.regression")
        if regression.get("has_regression") is True:
            raw_reasons = regression.get("reasons")
            if isinstance(raw_reasons, list) and raw_reasons:
                reasons.extend(f"{label}: {reason}" for reason in raw_reasons)
            else:
                reasons.append(f"{label}: regression detected")
    return reasons


def _has_blocker(
    lifecycle_payload: Mapping[str, Any],
    drift_payload: Mapping[str, Any],
    blocked_count: int,
    audit_high_count: int,
    regression_reasons: list[str],
) -> bool:
    lifecycle_action = _string_value(lifecycle_payload.get("action_readiness"), "action_readiness")
    drift_action = _string_value(drift_payload.get("action_readiness"), "action_readiness")
    return bool(
        blocked_count
        or audit_high_count
        or regression_reasons
        or lifecycle_action == "blocked"
        or drift_action == "blocked"
    )


def _first_human_action(*actions: str, fallback: str) -> str:
    for action in actions:
        if action != "none":
            if action in _VALID_HUMAN_DECISIONS:
                return action
            return fallback
    return fallback


def _validate_trace_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _mapping(payload, "readiness_trace")
    if result.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise ValueError(f"unsupported trace schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("readiness trace must declare state_change = none")
    if result.get("authority") != TRACE_AUTHORITY:
        raise ValueError(f"unsupported trace authority: {result.get('authority')}")
    guardrails = _mapping(result.get("guardrails"), "guardrails")
    for guardrail in (
        "registered_is_not_true",
        "retrieved_is_not_relevant",
        "remembered_is_not_trusted",
        "silence_is_not_negative_evidence",
        "trace_presence_is_not_permission",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"trace guardrail missing or false: {guardrail}")
    _mapping(result.get("summary"), "summary")
    _list_of_mappings(result.get("findings"), "findings")
    return result


def _validate_lifecycle_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _mapping(payload, "baseline_lifecycle")
    if result.get("schema_version") != BASELINE_LIFECYCLE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported baseline lifecycle schema_version: {result.get('schema_version')}"
        )
    if result.get("state_change") != "none":
        raise ValueError("baseline lifecycle must declare state_change = none")
    if result.get("authority") != BASELINE_LIFECYCLE_AUTHORITY:
        raise ValueError(f"unsupported baseline lifecycle authority: {result.get('authority')}")
    return result


def _validate_self_audit_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _mapping(payload, "protocol_self_audit")
    if result.get("schema_version") != SELF_AUDIT_SCHEMA_VERSION:
        raise ValueError(f"unsupported self-audit schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("protocol self-audit must declare state_change = none")
    if result.get("authority") != SELF_AUDIT_AUTHORITY:
        raise ValueError(f"unsupported self-audit authority: {result.get('authority')}")
    return result


def _validate_drift_policy_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _mapping(payload, "drift_policy")
    if result.get("schema_version") != DRIFT_POLICY_SCHEMA_VERSION:
        raise ValueError(f"unsupported drift policy schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("drift policy must declare state_change = none")
    if result.get("authority") != DRIFT_POLICY_AUTHORITY:
        raise ValueError(f"unsupported drift policy authority: {result.get('authority')}")
    return result


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return dict(value)


def _list_of_mappings(value: Any, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be JSON objects")
        result.append(dict(item))
    return result


def _string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _int_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
