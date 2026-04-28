from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from .baseline_lifecycle import BASELINE_LIFECYCLE_AUTHORITY, BASELINE_LIFECYCLE_SCHEMA_VERSION
from .diff import TRACE_DIFF_AUTHORITY, TRACE_DIFF_SCHEMA_VERSION
from .self_audit import SELF_AUDIT_AUTHORITY, SELF_AUDIT_SCHEMA_VERSION


DRIFT_POLICY_SCHEMA_VERSION = "1"
DRIFT_POLICY_AUTHORITY = "non-authoritative; advisory replay drift policy evidence only"

_VALID_CLASSIFICATIONS = {
    "no_drift",
    "traceability_drift_only",
    "source_surface_drift",
    "material_refresh_candidate",
    "blocked_regression_or_protocol_risk",
}
_VALID_RECOMMENDATIONS = {
    "no_action",
    "observe_traceability_drift",
    "refresh_candidate_requires_human_approval",
    "refresh_blocked_pending_review",
}
_VALID_HUMAN_ACTIONS = {
    "none",
    "acknowledge",
    "approve_baseline_refresh",
    "review_blockers",
}
_VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "advisory_report_allowed",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class DriftPolicyReport:
    baseline_label: str
    current_label: str
    trace_diff_digest: str
    protocol_self_audit_digest: str
    baseline_lifecycle_digest: str
    classification: str
    recommendation: str
    required_human_action: str
    action_readiness: str
    reasons: tuple[str, ...]
    source_drift_total: int
    semantic_drift_total: int
    traceability_drift_total: int
    metadata_drift_total: int
    regression_reasons: tuple[str, ...]
    self_audit_candidate_count: int
    self_audit_high_or_blocking_count: int
    lifecycle_recommendation: str
    lifecycle_action_readiness: str
    state_change: str = "none"
    authority: str = DRIFT_POLICY_AUTHORITY
    report_role: str = "advisory replay drift disposition only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("drift policy reports must not change state")
        if self.classification not in _VALID_CLASSIFICATIONS:
            raise ValueError(f"invalid drift classification: {self.classification}")
        if self.recommendation not in _VALID_RECOMMENDATIONS:
            raise ValueError(f"invalid drift recommendation: {self.recommendation}")
        if self.required_human_action not in _VALID_HUMAN_ACTIONS:
            raise ValueError(f"invalid required human action: {self.required_human_action}")
        if self.action_readiness not in _VALID_ACTION_READINESS:
            raise ValueError(f"invalid action readiness: {self.action_readiness}")
        for field_name, value in (
            ("source_drift_total", self.source_drift_total),
            ("semantic_drift_total", self.semantic_drift_total),
            ("traceability_drift_total", self.traceability_drift_total),
            ("metadata_drift_total", self.metadata_drift_total),
            ("self_audit_candidate_count", self.self_audit_candidate_count),
            ("self_audit_high_or_blocking_count", self.self_audit_high_or_blocking_count),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")
        if not self.baseline_label:
            raise ValueError("baseline_label is required")
        if not self.current_label:
            raise ValueError("current_label is required")

    @property
    def drift_total(self) -> int:
        return (
            self.source_drift_total
            + self.semantic_drift_total
            + self.traceability_drift_total
            + self.metadata_drift_total
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": DRIFT_POLICY_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "report_role": self.report_role,
            "baseline_label": self.baseline_label,
            "current_label": self.current_label,
            "digests": {
                "trace_diff": self.trace_diff_digest,
                "protocol_self_audit": self.protocol_self_audit_digest,
                "baseline_lifecycle": self.baseline_lifecycle_digest,
            },
            "classification": self.classification,
            "recommendation": self.recommendation,
            "required_human_action": self.required_human_action,
            "action_readiness": self.action_readiness,
            "reasons": list(self.reasons),
            "drift": {
                "source_total": self.source_drift_total,
                "semantic_total": self.semantic_drift_total,
                "traceability_total": self.traceability_drift_total,
                "metadata_total": self.metadata_drift_total,
                "total": self.drift_total,
            },
            "regression": {
                "has_regression": bool(self.regression_reasons),
                "reasons": list(self.regression_reasons),
            },
            "protocol_self_audit": {
                "candidate_count": self.self_audit_candidate_count,
                "high_or_blocking_count": self.self_audit_high_or_blocking_count,
            },
            "baseline_lifecycle": {
                "recommendation": self.lifecycle_recommendation,
                "action_readiness": self.lifecycle_action_readiness,
            },
            "guardrails": {
                "drift_policy_is_not_permission": True,
                "drift_policy_is_not_authority": True,
                "drift_policy_is_not_memory": True,
                "drift_policy_is_not_runtime_gate": True,
                "baseline_refresh_is_not_automatic": True,
                "anti_noise_no_auto_learning": True,
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
            },
            "boundary": {
                "may_suggest": [
                    "classify replay drift",
                    "request human acknowledgement",
                    "propose a human-approved baseline refresh",
                    "block refresh when drift regresses or protocol self-audit is high",
                ],
                "must_not_apply": [
                    "mutate state",
                    "update baseline automatically",
                    "hide drift",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat drift policy as permission",
                ],
            },
        }


def evaluate_drift_policy(
    trace_diff: Mapping[str, Any],
    protocol_self_audit: Mapping[str, Any],
    baseline_lifecycle: Mapping[str, Any],
) -> DriftPolicyReport:
    diff_payload = _validate_trace_diff_payload(trace_diff)
    audit_payload = _validate_self_audit_payload(protocol_self_audit)
    lifecycle_payload = _validate_lifecycle_payload(baseline_lifecycle)

    source_total = _collection_total(_mapping(diff_payload.get("source_reads"), "source_reads"), include_traceability=False)
    candidate_diff = _mapping(diff_payload.get("candidates"), "candidates")
    finding_diff = _mapping(diff_payload.get("findings"), "findings")
    semantic_total = _semantic_total(candidate_diff) + _semantic_total(finding_diff)
    traceability_total = _traceability_total(candidate_diff) + _traceability_total(finding_diff)
    metadata_total = (
        len(_list_of_mappings(diff_payload.get("summary_changes"), "summary_changes"))
        + len(_list_of_mappings(diff_payload.get("risk_assessment_changes"), "risk_assessment_changes"))
        + len(_list_of_mappings(diff_payload.get("guardrail_changes"), "guardrail_changes"))
    )
    regression_reasons = _string_tuple(diff_payload.get("regression_reasons"), "regression_reasons")
    audit_high = _int_value(audit_payload.get("high_or_blocking_count"), "high_or_blocking_count")
    audit_count = _int_value(audit_payload.get("candidate_count"), "candidate_count")
    lifecycle_recommendation = _string_value(lifecycle_payload.get("recommendation"), "recommendation")
    lifecycle_action_readiness = _string_value(lifecycle_payload.get("action_readiness"), "action_readiness")

    classification: str
    recommendation: str
    required_human_action: str
    action_readiness: str
    reasons: list[str] = []

    if diff_payload.get("has_regression") is True or regression_reasons or audit_high:
        classification = "blocked_regression_or_protocol_risk"
        recommendation = "refresh_blocked_pending_review"
        required_human_action = "review_blockers"
        action_readiness = "blocked"
        if regression_reasons:
            reasons.extend(f"regression: {reason}" for reason in regression_reasons)
        if audit_high:
            reasons.append(f"protocol self-audit high/blocking candidates: {audit_high}")
    elif source_total == 0 and semantic_total == 0 and traceability_total == 0 and metadata_total == 0:
        classification = "no_drift"
        recommendation = "no_action"
        required_human_action = "none"
        action_readiness = "no_action"
        reasons.append("baseline and current replay evidence match")
    elif semantic_total or metadata_total:
        classification = "material_refresh_candidate"
        recommendation = "refresh_candidate_requires_human_approval"
        required_human_action = "approve_baseline_refresh"
        action_readiness = "human_approval_required"
        if semantic_total:
            reasons.append(f"semantic drift requires human review: {semantic_total}")
        if metadata_total:
            reasons.append(f"summary/risk/guardrail drift requires human review: {metadata_total}")
    elif source_total:
        classification = "source_surface_drift"
        recommendation = "refresh_candidate_requires_human_approval"
        required_human_action = "approve_baseline_refresh"
        action_readiness = "human_approval_required"
        reasons.append(f"source read surface drift requires human review: {source_total}")
    else:
        classification = "traceability_drift_only"
        recommendation = "observe_traceability_drift"
        required_human_action = "acknowledge"
        action_readiness = "advisory_report_allowed"
        reasons.append(f"only evidence identifiers or spans moved: {traceability_total}")

    if lifecycle_recommendation == "refresh_blocked" and classification != "blocked_regression_or_protocol_risk":
        classification = "blocked_regression_or_protocol_risk"
        recommendation = "refresh_blocked_pending_review"
        required_human_action = "review_blockers"
        action_readiness = "blocked"
        reasons.append("baseline lifecycle blocked refresh")

    return DriftPolicyReport(
        baseline_label=_string_value(diff_payload.get("baseline_label"), "baseline_label"),
        current_label=_string_value(diff_payload.get("current_label"), "current_label"),
        trace_diff_digest=_stable_digest(diff_payload),
        protocol_self_audit_digest=_stable_digest(audit_payload),
        baseline_lifecycle_digest=_stable_digest(lifecycle_payload),
        classification=classification,
        recommendation=recommendation,
        required_human_action=required_human_action,
        action_readiness=action_readiness,
        reasons=tuple(reasons),
        source_drift_total=source_total,
        semantic_drift_total=semantic_total,
        traceability_drift_total=traceability_total,
        metadata_drift_total=metadata_total,
        regression_reasons=regression_reasons,
        self_audit_candidate_count=audit_count,
        self_audit_high_or_blocking_count=audit_high,
        lifecycle_recommendation=lifecycle_recommendation,
        lifecycle_action_readiness=lifecycle_action_readiness,
    )


def render_drift_policy_json(report: DriftPolicyReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_drift_policy_markdown(report: DriftPolicyReport) -> str:
    lines = [
        "# Epistemic Readiness Drift Policy",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- report_role: {report.report_role}",
        "- drift_policy_is_not_permission: true",
        "- drift_policy_is_not_authority: true",
        "- drift_policy_is_not_memory: true",
        "- baseline_refresh_is_not_automatic: true",
        "",
        "## Disposition",
        "",
        f"- baseline_label: `{report.baseline_label}`",
        f"- current_label: `{report.current_label}`",
        f"- classification: `{report.classification}`",
        f"- recommendation: `{report.recommendation}`",
        f"- required_human_action: `{report.required_human_action}`",
        f"- action_readiness: `{report.action_readiness}`",
        "",
        "## Drift Totals",
        "",
        f"- source_total: `{report.source_drift_total}`",
        f"- semantic_total: `{report.semantic_drift_total}`",
        f"- traceability_total: `{report.traceability_drift_total}`",
        f"- metadata_total: `{report.metadata_drift_total}`",
        f"- total: `{report.drift_total}`",
        "",
        "## Regression And Self-Audit",
        "",
        f"- has_regression: `{str(bool(report.regression_reasons)).lower()}`",
        f"- self_audit_candidate_count: `{report.self_audit_candidate_count}`",
        f"- self_audit_high_or_blocking_count: `{report.self_audit_high_or_blocking_count}`",
        f"- lifecycle_recommendation: `{report.lifecycle_recommendation}`",
        f"- lifecycle_action_readiness: `{report.lifecycle_action_readiness}`",
        "",
        "## Reasons",
        "",
    ]
    if report.reasons:
        lines.extend(f"- {reason}" for reason in report.reasons)
    else:
        lines.append("- none")
    if report.regression_reasons:
        lines.extend(["", "## Regression Reasons", ""])
        lines.extend(f"- {reason}" for reason in report.regression_reasons)
    lines.extend(
        [
            "",
            "## Must Not Apply",
            "",
            "- mutate state",
            "- update baseline automatically",
            "- hide drift",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat drift policy as permission",
            "",
        ]
    )
    return "\n".join(lines)


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
    for key in ("source_reads", "candidates", "findings"):
        _mapping(result.get(key), key)
    return result


def _validate_self_audit_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("protocol_self_audit must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != SELF_AUDIT_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported protocol_self_audit schema_version: {result.get('schema_version')}"
        )
    if result.get("state_change") != "none":
        raise ValueError("protocol_self_audit must declare state_change = none")
    if result.get("authority") != SELF_AUDIT_AUTHORITY:
        raise ValueError(f"unsupported protocol_self_audit authority: {result.get('authority')}")
    _int_value(result.get("candidate_count"), "candidate_count")
    _int_value(result.get("high_or_blocking_count"), "high_or_blocking_count")
    return result


def _validate_lifecycle_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    if not isinstance(payload, Mapping):
        raise ValueError("baseline_lifecycle must be a JSON object")
    result = dict(payload)
    if result.get("schema_version") != BASELINE_LIFECYCLE_SCHEMA_VERSION:
        raise ValueError(
            f"unsupported baseline_lifecycle schema_version: {result.get('schema_version')}"
        )
    if result.get("state_change") != "none":
        raise ValueError("baseline_lifecycle must declare state_change = none")
    if result.get("authority") != BASELINE_LIFECYCLE_AUTHORITY:
        raise ValueError(f"unsupported baseline_lifecycle authority: {result.get('authority')}")
    _string_value(result.get("recommendation"), "recommendation")
    _string_value(result.get("action_readiness"), "action_readiness")
    return result


def _collection_total(collection: Mapping[str, Any], *, include_traceability: bool) -> int:
    total = (
        len(_string_tuple(collection.get("added"), "added"))
        + len(_string_tuple(collection.get("removed"), "removed"))
        + len(_list_of_mappings(collection.get("changed"), "changed"))
    )
    if include_traceability:
        total += len(_list_of_mappings(collection.get("traceability_changed"), "traceability_changed"))
    return total


def _semantic_total(collection: Mapping[str, Any]) -> int:
    return _collection_total(collection, include_traceability=False)


def _traceability_total(collection: Mapping[str, Any]) -> int:
    return len(_list_of_mappings(collection.get("traceability_changed"), "traceability_changed"))


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


def _string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _int_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value
