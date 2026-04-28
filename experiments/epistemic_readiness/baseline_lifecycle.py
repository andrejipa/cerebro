from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .diff import TRACE_DIFF_AUTHORITY, TRACE_DIFF_SCHEMA_VERSION
from .self_audit import SELF_AUDIT_AUTHORITY, SELF_AUDIT_SCHEMA_VERSION
from .trace import TRACE_AUTHORITY, TRACE_SCHEMA_VERSION


BASELINE_LIFECYCLE_SCHEMA_VERSION = "1"
BASELINE_LIFECYCLE_AUTHORITY = "non-authoritative; advisory baseline lifecycle evidence only"


@dataclass(frozen=True)
class DriftCounts:
    added: int
    removed: int
    changed: int
    traceability_changed: int

    @property
    def total(self) -> int:
        return self.added + self.removed + self.changed + self.traceability_changed

    def to_dict(self) -> dict[str, int]:
        return {
            "added": self.added,
            "removed": self.removed,
            "changed": self.changed,
            "traceability_changed": self.traceability_changed,
            "total": self.total,
        }


@dataclass(frozen=True)
class BaselineLifecycleReport:
    baseline_label: str
    current_label: str
    baseline_trace_digest: str
    current_trace_digest: str
    trace_diff_digest: str
    self_audit_digest: str
    source_drift: DriftCounts
    candidate_drift: DriftCounts
    finding_drift: DriftCounts
    summary_change_count: int
    risk_assessment_change_count: int
    guardrail_change_count: int
    regression_reasons: tuple[str, ...]
    self_audit_candidate_count: int
    self_audit_high_or_blocking_count: int
    recommendation: str
    required_human_action: str
    action_readiness: str
    state_change: str = "none"
    authority: str = BASELINE_LIFECYCLE_AUTHORITY
    report_role: str = "advisory baseline lifecycle proposal only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("baseline lifecycle reports must not change state")
        if not self.baseline_label:
            raise ValueError("baseline_label is required")
        if not self.current_label:
            raise ValueError("current_label is required")
        if self.recommendation not in {
            "baseline_already_current",
            "refresh_candidate_requires_human_approval",
            "refresh_blocked",
        }:
            raise ValueError(f"invalid baseline lifecycle recommendation: {self.recommendation}")

    @property
    def drift_total(self) -> int:
        return (
            self.source_drift.total
            + self.candidate_drift.total
            + self.finding_drift.total
            + self.summary_change_count
            + self.risk_assessment_change_count
            + self.guardrail_change_count
        )

    @property
    def has_regression(self) -> bool:
        return bool(self.regression_reasons)

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": BASELINE_LIFECYCLE_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "report_role": self.report_role,
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "digests": {
                "baseline_trace": self.baseline_trace_digest,
                "current_trace": self.current_trace_digest,
                "trace_diff": self.trace_diff_digest,
                "protocol_self_audit": self.self_audit_digest,
            },
            "drift": {
                "sources": self.source_drift.to_dict(),
                "candidates": self.candidate_drift.to_dict(),
                "findings": self.finding_drift.to_dict(),
                "summary_changes": self.summary_change_count,
                "risk_assessment_changes": self.risk_assessment_change_count,
                "guardrail_changes": self.guardrail_change_count,
                "total": self.drift_total,
            },
            "regression": {
                "has_regression": self.has_regression,
                "reasons": list(self.regression_reasons),
            },
            "protocol_self_audit": {
                "candidate_count": self.self_audit_candidate_count,
                "high_or_blocking_count": self.self_audit_high_or_blocking_count,
            },
            "recommendation": self.recommendation,
            "required_human_action": self.required_human_action,
            "action_readiness": self.action_readiness,
            "guardrails": {
                "baseline_lifecycle_is_not_permission": True,
                "baseline_lifecycle_is_not_authority": True,
                "baseline_refresh_is_not_automatic": True,
                "baseline_freshness_is_not_truth": True,
                "human_approval_required_for_refresh": self.recommendation
                == "refresh_candidate_requires_human_approval",
                "silence_is_not_negative_evidence": True,
            },
            "boundary": {
                "may_suggest": [
                    "inspect baseline drift",
                    "propose human-approved baseline refresh",
                    "request human review",
                    "block refresh when replay evidence regresses",
                ],
                "must_not_apply": [
                    "mutate state",
                    "overwrite baseline automatically",
                    "treat baseline freshness as authority",
                    "treat baseline freshness as permission",
                    "treat baseline lifecycle as memory",
                    "hide semantic drift",
                    "hide source drift",
                    "hide traceability drift",
                    "create canonical claim graph",
                    "act as runtime gate",
                ],
            },
        }


def evaluate_baseline_lifecycle(
    baseline_trace: Mapping[str, Any],
    current_trace: Mapping[str, Any],
    trace_diff: Mapping[str, Any],
    protocol_self_audit: Mapping[str, Any],
    *,
    baseline_label: str = "baseline",
    current_label: str = "current",
) -> BaselineLifecycleReport:
    baseline_payload = _validate_trace_payload(baseline_trace, "baseline_trace")
    current_payload = _validate_trace_payload(current_trace, "current_trace")
    diff_payload = _validate_trace_diff_payload(trace_diff)
    audit_payload = _validate_self_audit_payload(protocol_self_audit)

    source_drift = _drift_counts(_mapping(diff_payload.get("source_reads"), "source_reads"))
    candidate_drift = _drift_counts(_mapping(diff_payload.get("candidates"), "candidates"))
    finding_drift = _drift_counts(_mapping(diff_payload.get("findings"), "findings"))
    regression_reasons = _string_tuple(diff_payload.get("regression_reasons"), "regression_reasons")
    self_audit_high_or_blocking = _int_value(audit_payload.get("high_or_blocking_count"), "high_or_blocking_count")
    self_audit_candidate_count = _int_value(audit_payload.get("candidate_count"), "candidate_count")
    summary_change_count = len(_list_of_mappings(diff_payload.get("summary_changes"), "summary_changes"))
    risk_assessment_change_count = len(
        _list_of_mappings(diff_payload.get("risk_assessment_changes"), "risk_assessment_changes")
    )
    guardrail_change_count = len(_list_of_mappings(diff_payload.get("guardrail_changes"), "guardrail_changes"))

    drift_total = (
        source_drift.total
        + candidate_drift.total
        + finding_drift.total
        + summary_change_count
        + risk_assessment_change_count
        + guardrail_change_count
    )
    if bool(diff_payload.get("has_regression")) or regression_reasons or self_audit_high_or_blocking:
        recommendation = "refresh_blocked"
        required_human_action = "review_blockers"
        action_readiness = "blocked"
    elif drift_total == 0:
        recommendation = "baseline_already_current"
        required_human_action = "none"
        action_readiness = "no_action"
    else:
        recommendation = "refresh_candidate_requires_human_approval"
        required_human_action = "approve_baseline_refresh"
        action_readiness = "human_approval_required"

    return BaselineLifecycleReport(
        baseline_label=baseline_label,
        current_label=current_label,
        baseline_trace_digest=_stable_digest(baseline_payload),
        current_trace_digest=_stable_digest(current_payload),
        trace_diff_digest=_stable_digest(diff_payload),
        self_audit_digest=_stable_digest(audit_payload),
        source_drift=source_drift,
        candidate_drift=candidate_drift,
        finding_drift=finding_drift,
        summary_change_count=summary_change_count,
        risk_assessment_change_count=risk_assessment_change_count,
        guardrail_change_count=guardrail_change_count,
        regression_reasons=regression_reasons,
        self_audit_candidate_count=self_audit_candidate_count,
        self_audit_high_or_blocking_count=self_audit_high_or_blocking,
        recommendation=recommendation,
        required_human_action=required_human_action,
        action_readiness=action_readiness,
    )


def render_baseline_lifecycle_json(report: BaselineLifecycleReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_baseline_lifecycle_markdown(report: BaselineLifecycleReport) -> str:
    lines = [
        "# Epistemic Readiness Baseline Lifecycle",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- report_role: {report.report_role}",
        "- baseline_lifecycle_is_not_permission: true",
        "- baseline_refresh_is_not_automatic: true",
        "- baseline_freshness_is_not_truth: true",
        "",
        "## Recommendation",
        "",
        f"- baseline_label: `{report.baseline_label}`",
        f"- current_label: `{report.current_label}`",
        f"- recommendation: `{report.recommendation}`",
        f"- required_human_action: `{report.required_human_action}`",
        f"- action_readiness: `{report.action_readiness}`",
        "",
        "## Digests",
        "",
        f"- baseline_trace: `{report.baseline_trace_digest}`",
        f"- current_trace: `{report.current_trace_digest}`",
        f"- trace_diff: `{report.trace_diff_digest}`",
        f"- protocol_self_audit: `{report.self_audit_digest}`",
        "",
        "## Drift",
        "",
        f"- total: `{report.drift_total}`",
        f"- sources: `{report.source_drift.to_dict()}`",
        f"- candidates: `{report.candidate_drift.to_dict()}`",
        f"- findings: `{report.finding_drift.to_dict()}`",
        f"- summary_changes: `{report.summary_change_count}`",
        f"- risk_assessment_changes: `{report.risk_assessment_change_count}`",
        f"- guardrail_changes: `{report.guardrail_change_count}`",
        "",
        "## Regression And Self-Audit",
        "",
        f"- has_regression: `{str(report.has_regression).lower()}`",
        f"- self_audit_candidate_count: `{report.self_audit_candidate_count}`",
        f"- self_audit_high_or_blocking_count: `{report.self_audit_high_or_blocking_count}`",
        "",
    ]
    if report.regression_reasons:
        lines.extend(["## Regression Reasons", ""])
        lines.extend(f"- {reason}" for reason in report.regression_reasons)
        lines.append("")
    lines.extend(
        [
            "## Must Not Apply",
            "",
            "- mutate state",
            "- overwrite baseline automatically",
            "- treat baseline freshness as authority",
            "- treat baseline freshness as permission",
            "- treat baseline lifecycle as memory",
            "- hide semantic drift",
            "- hide source drift",
            "- hide traceability drift",
            "- create canonical claim graph",
            "- act as runtime gate",
            "",
        ]
    )
    return "\n".join(lines)


def _validate_trace_payload(payload: Mapping[str, Any] | Any, field_name: str) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != TRACE_SCHEMA_VERSION:
        raise ValueError(f"unsupported {field_name} schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError(f"{field_name} must declare state_change = none")
    if result.get("authority") != TRACE_AUTHORITY:
        raise ValueError(f"unsupported {field_name} authority: {result.get('authority')}")
    return result


def _validate_trace_diff_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("trace_diff must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != TRACE_DIFF_SCHEMA_VERSION:
        raise ValueError(f"unsupported trace_diff schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("trace_diff must declare state_change = none")
    if result.get("authority") != TRACE_DIFF_AUTHORITY:
        raise ValueError(f"unsupported trace_diff authority: {result.get('authority')}")
    if not isinstance(result.get("has_regression"), bool):
        raise ValueError("trace_diff must include boolean has_regression")
    _string_tuple(result.get("regression_reasons"), "regression_reasons")
    for key in ("source_reads", "candidates", "findings"):
        _drift_counts(_mapping(result.get(key), key))
    return result


def _validate_self_audit_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("protocol_self_audit must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != SELF_AUDIT_SCHEMA_VERSION:
        raise ValueError(f"unsupported protocol_self_audit schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError("protocol_self_audit must declare state_change = none")
    if result.get("authority") != SELF_AUDIT_AUTHORITY:
        raise ValueError(f"unsupported protocol_self_audit authority: {result.get('authority')}")
    _int_value(result.get("candidate_count"), "candidate_count")
    _int_value(result.get("high_or_blocking_count"), "high_or_blocking_count")
    return result


def _drift_counts(collection: Mapping[str, Any]) -> DriftCounts:
    return DriftCounts(
        added=len(_string_tuple(collection.get("added"), "added")),
        removed=len(_string_tuple(collection.get("removed"), "removed")),
        changed=len(_list_of_mappings(collection.get("changed"), "changed")),
        traceability_changed=len(_list_of_mappings(collection.get("traceability_changed"), "traceability_changed")),
    )


def _stable_digest(payload: Mapping[str, Any]) -> str:
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=True).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be an object")
    return dict(value)


def _list_of_mappings(value: Any, field_name: str) -> list[dict[str, Any]]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be objects")
        result.append(dict(item))
    return result


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return tuple(str(item) for item in value)


def _int_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
