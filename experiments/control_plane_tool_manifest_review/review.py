from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.capability_policy import CapabilityRule
from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview


class ControlPlaneToolManifestReviewError(ValueError):
    """Raised when tool-manifest review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneToolManifestTool:
    tool_id: str
    tool_kind: str
    decision: str
    risk_level: str
    path_scope: tuple[str, ...]
    max_data_sensitivity: str
    network_access: bool
    mutates_files: bool
    mutates_state: bool
    destructive: bool
    requires_human_confirmation: bool
    captures_sensitive_output: bool
    timeout_seconds: int
    summary: str


@dataclass(frozen=True)
class ControlPlaneToolManifestCandidate:
    manifest_id: str
    manifest_thread_id: str
    revision: int
    lifecycle_status: str
    manifest_scope: str
    authority_boundary: str
    supersedes_manifest_id: str
    evidence_ids: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    capability_rule_ids: tuple[str, ...]
    tools: tuple[ControlPlaneToolManifestTool, ...]
    approval_policy_defined: bool
    evidence_policy_defined: bool
    audit_logging_defined: bool
    rollback_policy_defined: bool
    timeout_policy_defined: bool
    rate_limit_policy_defined: bool
    sandbox_policy_defined: bool
    secret_handling_defined: bool
    claims_tool_authority: bool
    grants_execution_permission: bool
    registers_tools: bool
    imports_adapters: bool
    exposes_mcp_server: bool
    schedules_tool_calls: bool
    reads_live_state: bool
    mutates_state: bool
    auto_apply: bool
    contains_secret_material: bool
    stores_raw_tool_outputs: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneToolManifestFinding:
    code: str
    severity: str
    manifest_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneToolManifestReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    manifest_count: int
    manifest_thread_count: int
    manifest_ids: tuple[str, ...]
    manifest_thread_ids: tuple[str, ...]
    latest_manifest_ids: tuple[str, ...]
    non_latest_manifest_ids: tuple[str, ...]
    active_manifest_ids: tuple[str, ...]
    blocked_manifest_ids: tuple[str, ...]
    tool_count: int
    tool_ids: tuple[str, ...]
    allowed_tool_ids: tuple[str, ...]
    review_required_tool_ids: tuple[str, ...]
    denied_tool_ids: tuple[str, ...]
    high_risk_tool_ids: tuple[str, ...]
    network_tool_ids: tuple[str, ...]
    mutating_tool_ids: tuple[str, ...]
    destructive_tool_ids: tuple[str, ...]
    evidence_count: int
    evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    capability_rule_ids: tuple[str, ...]
    decision_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    capability_rule_count: int
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneToolManifestFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane tool manifest review only"
    tool_manifest_review_is_not_permission: bool = True
    manifest_candidate_is_not_registered_tool_manifest: bool = True
    tool_decision_is_not_execution_approval: bool = True
    tool_manifest_review_is_not_adapter: bool = True
    tool_manifest_review_is_not_scheduler: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_LIFECYCLE_STATUSES = {"draft", "active_candidate", "blocked", "superseded", "archived"}
_MANIFEST_SCOPES = {"local_tools", "mcp_tools", "agent_tools", "runtime_manager", "security", "unknown"}
_AUTHORITY_BOUNDARIES = {"advisory_manifest", "candidate_manifest", "adapter_boundary_request", "unknown"}
_TOOL_KINDS = {"shell", "filesystem", "network", "mcp", "agent_handoff", "browser", "analysis", "unknown"}
_TOOL_DECISIONS = {"allow", "review_required", "deny"}
_RISK_LEVELS = {"low", "medium", "high", "critical"}
_SENSITIVITY = ("public", "internal", "sensitive", "secret")
_SEVERITIES = {"critical", "high", "medium", "low"}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "tool manifest is truth",
    "tool manifest approved",
    "tool manifest grants permission",
    "tool selected next action",
    "tool call approved",
    "tool grants permission",
    "tool registry is truth",
    "registered tool is truth",
    "tool annotations are contracts",
    "tool annotation grants permission",
    "mcp tool grants permission",
    "per tool approval grants permission",
    "permission to execute",
    "execution approval",
    "execution approved",
    "runtime authority",
    "source of truth",
    "scheduler",
    "schedules work",
    "adapter approved",
    "runtime enabled",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not an adapter",
    "not a registry",
    "not truth",
    "is not truth",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not approve",
    "does not register",
    "does not expose",
    "before any",
    "without",
)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneToolManifestReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneToolManifestReviewError(f"missing required tool-manifest field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneToolManifestReviewError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneToolManifestReviewError(f"{field} must be a positive integer")
    return value


def _non_negative_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field, 0)
    if not isinstance(value, int) or value < 0:
        raise ControlPlaneToolManifestReviewError(f"{field} must be a non-negative integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field, False)
    if not isinstance(value, bool):
        raise ControlPlaneToolManifestReviewError(f"{field} must be a boolean")
    return value


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneToolManifestReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ControlPlaneToolManifestReviewError(f"{field} must contain non-empty strings")
    ids = tuple(str(item).strip() for item in value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneToolManifestReviewError(f"{field} items must be path-segment safe")
    if len(set(ids)) != len(ids):
        raise ControlPlaneToolManifestReviewError(f"{field} must not contain duplicates")
    return ids


def _as_scope_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneToolManifestReviewError(f"{field} must be a list")
    scopes: list[str] = []
    for item in value:
        if not isinstance(item, str) or not item.strip():
            raise ControlPlaneToolManifestReviewError(f"{field} must contain non-empty strings")
        normalized = item.replace("\\", "/").strip("/")
        if not normalized or normalized in {".", "*"} or normalized.startswith("../") or "/../" in normalized:
            raise ControlPlaneToolManifestReviewError(f"{field} must contain bounded relative scopes")
        scopes.append(normalized)
    if len(set(scopes)) != len(scopes):
        raise ControlPlaneToolManifestReviewError(f"{field} must not contain duplicates")
    return tuple(scopes)


def _finding(code: str, severity: str, manifest_id: str, detail: str) -> ControlPlaneToolManifestFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneToolManifestReviewError(f"unknown severity: {severity}")
    return ControlPlaneToolManifestFinding(code=code, severity=severity, manifest_id=manifest_id, detail=detail)


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ").replace("-", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _normalize_tool(payload: Mapping[str, object]) -> ControlPlaneToolManifestTool:
    tool_id = _required_str(payload, "tool_id")
    if not _is_path_segment_safe(tool_id):
        raise ControlPlaneToolManifestReviewError("tool_id must be path-segment safe")
    tool_kind = _required_str(payload, "tool_kind")
    if tool_kind not in _TOOL_KINDS:
        raise ControlPlaneToolManifestReviewError(f"unknown tool_kind: {tool_kind}")
    decision = _required_str(payload, "decision")
    if decision not in _TOOL_DECISIONS:
        raise ControlPlaneToolManifestReviewError(f"unknown tool decision: {decision}")
    risk_level = _required_str(payload, "risk_level")
    if risk_level not in _RISK_LEVELS:
        raise ControlPlaneToolManifestReviewError(f"unknown risk_level: {risk_level}")
    max_data_sensitivity = _required_str(payload, "max_data_sensitivity")
    if max_data_sensitivity not in _SENSITIVITY:
        raise ControlPlaneToolManifestReviewError(f"unknown max_data_sensitivity: {max_data_sensitivity}")
    return ControlPlaneToolManifestTool(
        tool_id=tool_id,
        tool_kind=tool_kind,
        decision=decision,
        risk_level=risk_level,
        path_scope=_as_scope_tuple(payload.get("path_scope"), f"{tool_id}.path_scope"),
        max_data_sensitivity=max_data_sensitivity,
        network_access=_required_bool(payload, "network_access"),
        mutates_files=_required_bool(payload, "mutates_files"),
        mutates_state=_required_bool(payload, "mutates_state"),
        destructive=_required_bool(payload, "destructive"),
        requires_human_confirmation=_required_bool(payload, "requires_human_confirmation"),
        captures_sensitive_output=_required_bool(payload, "captures_sensitive_output"),
        timeout_seconds=_non_negative_int(payload, "timeout_seconds"),
        summary=_required_str(payload, "summary"),
    )


def _normalize_candidate(payload: Mapping[str, object]) -> ControlPlaneToolManifestCandidate:
    manifest_id = _required_str(payload, "manifest_id")
    manifest_thread_id = _required_str(payload, "manifest_thread_id")
    if not _is_path_segment_safe(manifest_id) or not _is_path_segment_safe(manifest_thread_id):
        raise ControlPlaneToolManifestReviewError("manifest identifiers must be path-segment safe")
    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneToolManifestReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    manifest_scope = _required_str(payload, "manifest_scope")
    if manifest_scope not in _MANIFEST_SCOPES:
        raise ControlPlaneToolManifestReviewError(f"unknown manifest_scope: {manifest_scope}")
    authority_boundary = _required_str(payload, "authority_boundary")
    if authority_boundary not in _AUTHORITY_BOUNDARIES:
        raise ControlPlaneToolManifestReviewError(f"unknown authority_boundary: {authority_boundary}")
    raw_tools = payload.get("tools")
    if not isinstance(raw_tools, list):
        raise ControlPlaneToolManifestReviewError("tools must be a list")
    tools = tuple(_normalize_tool(tool) for tool in raw_tools if isinstance(tool, Mapping))
    if len(tools) != len(raw_tools):
        raise ControlPlaneToolManifestReviewError("tools must contain mapping payloads")
    tool_ids = [tool.tool_id for tool in tools]
    if len(set(tool_ids)) != len(tool_ids):
        raise ControlPlaneToolManifestReviewError("tool ids must be unique within a manifest")
    return ControlPlaneToolManifestCandidate(
        manifest_id=manifest_id,
        manifest_thread_id=manifest_thread_id,
        revision=_required_int(payload, "revision"),
        lifecycle_status=lifecycle_status,
        manifest_scope=manifest_scope,
        authority_boundary=authority_boundary,
        supersedes_manifest_id=_optional_str(payload, "supersedes_manifest_id"),
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence_ids"),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids"), "depends_on_decision_ids"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids"), "referenced_rule_ids"),
        capability_rule_ids=_as_id_tuple(payload.get("capability_rule_ids"), "capability_rule_ids"),
        tools=tools,
        approval_policy_defined=_required_bool(payload, "approval_policy_defined"),
        evidence_policy_defined=_required_bool(payload, "evidence_policy_defined"),
        audit_logging_defined=_required_bool(payload, "audit_logging_defined"),
        rollback_policy_defined=_required_bool(payload, "rollback_policy_defined"),
        timeout_policy_defined=_required_bool(payload, "timeout_policy_defined"),
        rate_limit_policy_defined=_required_bool(payload, "rate_limit_policy_defined"),
        sandbox_policy_defined=_required_bool(payload, "sandbox_policy_defined"),
        secret_handling_defined=_required_bool(payload, "secret_handling_defined"),
        claims_tool_authority=_required_bool(payload, "claims_tool_authority"),
        grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
        registers_tools=_required_bool(payload, "registers_tools"),
        imports_adapters=_required_bool(payload, "imports_adapters"),
        exposes_mcp_server=_required_bool(payload, "exposes_mcp_server"),
        schedules_tool_calls=_required_bool(payload, "schedules_tool_calls"),
        reads_live_state=_required_bool(payload, "reads_live_state"),
        mutates_state=_required_bool(payload, "mutates_state"),
        auto_apply=_required_bool(payload, "auto_apply"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        stores_raw_tool_outputs=_required_bool(payload, "stores_raw_tool_outputs"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _latest_and_non_latest(
    candidates: tuple[ControlPlaneToolManifestCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    latest_by_thread: dict[str, ControlPlaneToolManifestCandidate] = {}
    for candidate in sorted(candidates, key=lambda item: (item.manifest_thread_id, item.revision, item.manifest_id)):
        current = latest_by_thread.get(candidate.manifest_thread_id)
        if current is None or candidate.revision > current.revision:
            latest_by_thread[candidate.manifest_thread_id] = candidate
    latest_ids = tuple(sorted(candidate.manifest_id for candidate in latest_by_thread.values()))
    non_latest_ids = tuple(sorted(candidate.manifest_id for candidate in candidates if candidate.manifest_id not in latest_ids))
    return latest_ids, non_latest_ids


def _check_supplied_review_guardrails(
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle],
) -> tuple[ControlPlaneActionReviewBundle, ...]:
    for name, review in (
        ("decision_review", decision_review),
        ("integrity_review", integrity_review),
        ("rule_promotion_review", rule_promotion_review),
    ):
        if review is not None and getattr(review, "state_change", "none") != "none":
            raise ControlPlaneToolManifestReviewError(f"{name} must not mutate state")
        if review is not None and "non-authoritative" not in getattr(review, "authority", ""):
            raise ControlPlaneToolManifestReviewError(f"{name} must remain non-authoritative")
        if review is not None and not getattr(review, "must_not_execute_automatically", True):
            raise ControlPlaneToolManifestReviewError(f"{name} must not execute automatically")
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if bundle.state_change != "none" or not bundle.must_not_execute_automatically:
            raise ControlPlaneToolManifestReviewError("action review bundles must remain advisory")
    return bundles


def _review_candidates(
    candidates: tuple[ControlPlaneToolManifestCandidate, ...],
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    capability_rules: tuple[CapabilityRule, ...],
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneToolManifestFinding, ...]:
    findings: list[ControlPlaneToolManifestFinding] = []
    by_id = {candidate.manifest_id: candidate for candidate in candidates}
    by_thread: dict[str, list[ControlPlaneToolManifestCandidate]] = {}
    for candidate in candidates:
        by_thread.setdefault(candidate.manifest_thread_id, []).append(candidate)

    for thread_candidates in by_thread.values():
        revisions = sorted(candidate.revision for candidate in thread_candidates)
        if len(set(revisions)) != len(revisions):
            duplicated = next(revision for revision in revisions if revisions.count(revision) > 1)
            for candidate in thread_candidates:
                if candidate.revision == duplicated:
                    findings.append(_finding("tool_manifest_duplicate_thread_revision", "high", candidate.manifest_id, str(duplicated)))
        expected = list(range(min(revisions), max(revisions) + 1))
        if revisions and revisions != expected:
            findings.append(
                _finding("tool_manifest_revision_gap", "high", thread_candidates[-1].manifest_id, "manifest thread revisions are not contiguous")
            )

    latest_ids, _ = _latest_and_non_latest(candidates)
    active_ids = [candidate.manifest_id for candidate in candidates if candidate.lifecycle_status == "active_candidate"]
    if len(active_ids) > 1:
        for manifest_id in active_ids:
            findings.append(_finding("multiple_active_tool_manifest_candidates", "high", manifest_id, "more than one active manifest candidate"))

    for candidate in candidates:
        if not candidate.tools:
            findings.append(_finding("tool_manifest_has_no_tools", "high", candidate.manifest_id, "manifest candidate declares no tools"))
        if not candidate.evidence_ids:
            findings.append(_finding("tool_manifest_missing_evidence", "high", candidate.manifest_id, "manifest has no evidence ids"))
        if candidate.lifecycle_status == "active_candidate" and candidate.manifest_id not in latest_ids:
            findings.append(_finding("active_tool_manifest_not_latest_revision", "high", candidate.manifest_id, "active manifest is not latest revision"))
        if candidate.supersedes_manifest_id:
            superseded = by_id.get(candidate.supersedes_manifest_id)
            if candidate.supersedes_manifest_id == candidate.manifest_id:
                findings.append(_finding("tool_manifest_supersedes_self", "high", candidate.manifest_id, "manifest supersedes itself"))
            elif superseded is None:
                findings.append(_finding("tool_manifest_supersedes_unknown_id", "high", candidate.manifest_id, "superseded manifest id is unknown"))
            elif superseded.manifest_thread_id != candidate.manifest_thread_id:
                findings.append(_finding("tool_manifest_supersedes_cross_thread", "high", candidate.manifest_id, "manifest supersedes another thread"))
            elif superseded.revision != candidate.revision - 1:
                findings.append(
                    _finding("tool_manifest_supersedes_non_previous_revision", "medium", candidate.manifest_id, "manifest skips supersession chain")
                )
        elif candidate.revision > 1:
            findings.append(_finding("tool_manifest_missing_supersession", "high", candidate.manifest_id, "manifest revision lacks supersedes_manifest_id"))

        missing_policy_checks = (
            ("tool_manifest_missing_approval_policy", "high", candidate.approval_policy_defined),
            ("tool_manifest_missing_evidence_policy", "high", candidate.evidence_policy_defined),
            ("tool_manifest_missing_audit_logging", "medium", candidate.audit_logging_defined),
            ("tool_manifest_missing_rollback_policy", "medium", candidate.rollback_policy_defined),
            ("tool_manifest_missing_timeout_policy", "medium", candidate.timeout_policy_defined),
            ("tool_manifest_missing_rate_limit_policy", "medium", candidate.rate_limit_policy_defined),
            ("tool_manifest_missing_sandbox_policy", "high", candidate.sandbox_policy_defined),
            ("tool_manifest_missing_secret_handling", "high", candidate.secret_handling_defined),
        )
        for code, severity, present in missing_policy_checks:
            if not present:
                findings.append(_finding(code, severity, candidate.manifest_id, f"{code} in candidate manifest"))

        boundary_checks = (
            ("tool_manifest_claims_tool_authority", "critical", candidate.claims_tool_authority),
            ("tool_manifest_grants_execution_permission", "critical", candidate.grants_execution_permission),
            ("tool_manifest_registers_tools", "high", candidate.registers_tools),
            ("tool_manifest_imports_adapters", "high", candidate.imports_adapters),
            ("tool_manifest_exposes_mcp_server", "high", candidate.exposes_mcp_server),
            ("tool_manifest_schedules_tool_calls", "critical", candidate.schedules_tool_calls),
            ("tool_manifest_reads_live_state", "high", candidate.reads_live_state),
            ("tool_manifest_mutates_state", "critical", candidate.mutates_state),
            ("tool_manifest_auto_apply", "critical", candidate.auto_apply),
            ("tool_manifest_contains_secret_material", "high", candidate.contains_secret_material),
            ("tool_manifest_stores_raw_tool_outputs", "high", candidate.stores_raw_tool_outputs),
        )
        for code, severity, present in boundary_checks:
            if present:
                findings.append(_finding(code, severity, candidate.manifest_id, f"{code} observed in candidate flags"))

        if candidate.authority_boundary == "adapter_boundary_request":
            findings.append(_finding("tool_manifest_requests_adapter_boundary", "high", candidate.manifest_id, "adapter boundary requested"))
        if _has_unqualified_authority_text(candidate.summary) or _has_unqualified_authority_text(candidate.rationale):
            findings.append(
                _finding(
                    "tool_manifest_text_launders_tool_authority",
                    "high",
                    candidate.manifest_id,
                    "summary or rationale contains authority wording without a local negative marker",
                )
            )

        for tool in candidate.tools:
            tool_detail = f"{candidate.manifest_id}:{tool.tool_id}"
            if tool.risk_level in {"high", "critical"} and tool.decision == "allow":
                findings.append(_finding("high_risk_tool_allowed_without_review", "high", candidate.manifest_id, tool_detail))
            if tool.network_access and tool.decision == "allow":
                findings.append(_finding("network_tool_allowed_without_review", "high", candidate.manifest_id, tool_detail))
            if (tool.mutates_files or tool.mutates_state or tool.destructive) and tool.decision == "allow":
                findings.append(_finding("mutating_tool_allowed_without_review", "critical", candidate.manifest_id, tool_detail))
            if tool.destructive and not tool.requires_human_confirmation:
                findings.append(_finding("destructive_tool_missing_human_confirmation", "critical", candidate.manifest_id, tool_detail))
            if tool.captures_sensitive_output and tool.max_data_sensitivity in {"sensitive", "secret"} and tool.decision != "deny":
                findings.append(_finding("sensitive_output_tool_not_denied", "high", candidate.manifest_id, tool_detail))
            if tool.timeout_seconds == 0 and tool.decision != "deny":
                findings.append(_finding("tool_missing_timeout", "medium", candidate.manifest_id, tool_detail))
            if _has_unqualified_authority_text(tool.summary):
                findings.append(_finding("tool_summary_launders_tool_authority", "high", candidate.manifest_id, tool_detail))

    referenced_decisions = {decision_id for candidate in candidates for decision_id in candidate.depends_on_decision_ids}
    if referenced_decisions:
        if decision_review is None:
            for candidate in candidates:
                if candidate.depends_on_decision_ids:
                    findings.append(_finding("tool_manifest_missing_decision_review", "high", candidate.manifest_id, "manifest references decisions without review"))
        else:
            current_decisions = set(decision_review.current_decision_ids)
            for candidate in candidates:
                for decision_id in candidate.depends_on_decision_ids:
                    if decision_id not in current_decisions:
                        findings.append(_finding("tool_manifest_references_non_current_decision", "high", candidate.manifest_id, decision_id))

    referenced_rules = {rule_id for candidate in candidates for rule_id in candidate.referenced_rule_ids}
    if referenced_rules:
        if rule_promotion_review is None:
            for candidate in candidates:
                if candidate.referenced_rule_ids:
                    findings.append(_finding("tool_manifest_missing_rule_promotion_review", "high", candidate.manifest_id, "manifest references rules without review"))
        else:
            active_rules = set(rule_promotion_review.active_rule_ids)
            for candidate in candidates:
                for rule_id in candidate.referenced_rule_ids:
                    if rule_id not in active_rules:
                        findings.append(_finding("tool_manifest_references_non_active_rule", "high", candidate.manifest_id, rule_id))
    if referenced_rules and rule_promotion_review is not None and rule_promotion_review.review_status != "rule_promotion_contract_observed":
        for candidate in candidates:
            if candidate.referenced_rule_ids:
                findings.append(_finding("tool_manifest_over_rule_promotion_drift", "high", candidate.manifest_id, rule_promotion_review.review_status))

    if integrity_review is None:
        for candidate in candidates:
            findings.append(_finding("tool_manifest_missing_integrity_review", "high", candidate.manifest_id, "integrity review is required"))
    elif integrity_review.review_status != "control_plane_integrity_preserved":
        for candidate in candidates:
            findings.append(_finding("tool_manifest_over_integrity_drift", "critical", candidate.manifest_id, integrity_review.review_status))

    capability_rule_ids = {rule.rule_id for rule in capability_rules}
    if any(candidate.capability_rule_ids for candidate in candidates) and not capability_rules:
        for candidate in candidates:
            if candidate.capability_rule_ids:
                findings.append(_finding("tool_manifest_missing_capability_rules", "high", candidate.manifest_id, "manifest references capability rules without supplied rules"))
    for candidate in candidates:
        for rule_id in candidate.capability_rule_ids:
            if capability_rule_ids and rule_id not in capability_rule_ids:
                findings.append(_finding("tool_manifest_references_unknown_capability_rule", "high", candidate.manifest_id, rule_id))

    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_ready":
            for candidate in candidates:
                findings.append(_finding("tool_manifest_over_action_review_blocker", "high", candidate.manifest_id, bundle.action_posture))

    return tuple(findings)


def build_control_plane_tool_manifest_review(
    manifest_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    capability_rules: Iterable[CapabilityRule] = (),
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneToolManifestReview:
    _parse_date(review_as_of, "review_as_of")
    payloads = tuple(manifest_payloads)
    if not payloads:
        raise ControlPlaneToolManifestReviewError("at least one tool-manifest candidate is required")
    candidates = tuple(_normalize_candidate(payload) for payload in payloads)
    ids = [candidate.manifest_id for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise ControlPlaneToolManifestReviewError("duplicate manifest ids are not allowed")
    bundles = _check_supplied_review_guardrails(
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=action_review_bundles,
    )
    rules = tuple(capability_rules)
    rule_ids = [rule.rule_id for rule in rules]
    if len(set(rule_ids)) != len(rule_ids):
        raise ControlPlaneToolManifestReviewError("duplicate capability rule ids are not allowed")
    findings = _review_candidates(
        candidates,
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        capability_rules=rules,
        action_review_bundles=bundles,
    )
    latest_ids, non_latest_ids = _latest_and_non_latest(candidates)
    high_or_critical = {finding.manifest_id for finding in findings if finding.severity in {"critical", "high"}}
    review_status = "tool_manifest_candidate_observed"
    if high_or_critical:
        review_status = "tool_manifest_review_blocked"
    elif findings:
        review_status = "tool_manifest_review_attention_required"

    tools = tuple(tool for candidate in candidates for tool in candidate.tools)
    evidence_ids = tuple(sorted({evidence_id for candidate in candidates for evidence_id in candidate.evidence_ids}))
    return ControlPlaneToolManifestReview(
        schema_version="1",
        review_role="reviews_tool_manifest_candidates_without_registering_tools",
        review_status=review_status,
        review_as_of=review_as_of,
        manifest_count=len(candidates),
        manifest_thread_count=len({candidate.manifest_thread_id for candidate in candidates}),
        manifest_ids=tuple(sorted(ids)),
        manifest_thread_ids=tuple(sorted({candidate.manifest_thread_id for candidate in candidates})),
        latest_manifest_ids=latest_ids,
        non_latest_manifest_ids=non_latest_ids,
        active_manifest_ids=tuple(sorted(candidate.manifest_id for candidate in candidates if candidate.lifecycle_status == "active_candidate")),
        blocked_manifest_ids=tuple(sorted(high_or_critical)),
        tool_count=len(tools),
        tool_ids=tuple(sorted({tool.tool_id for tool in tools})),
        allowed_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.decision == "allow"})),
        review_required_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.decision == "review_required"})),
        denied_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.decision == "deny"})),
        high_risk_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.risk_level in {"high", "critical"}})),
        network_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.network_access})),
        mutating_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.mutates_files or tool.mutates_state})),
        destructive_tool_ids=tuple(sorted({tool.tool_id for tool in tools if tool.destructive})),
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        referenced_decision_ids=tuple(sorted({item for candidate in candidates for item in candidate.depends_on_decision_ids})),
        referenced_rule_ids=tuple(sorted({item for candidate in candidates for item in candidate.referenced_rule_ids})),
        capability_rule_ids=tuple(sorted({item for candidate in candidates for item in candidate.capability_rule_ids})),
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        capability_rule_count=len(rules),
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )


def _validate_review(review: ControlPlaneToolManifestReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneToolManifestReviewError("tool-manifest review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneToolManifestReviewError("tool-manifest review must remain non-authoritative")
    if (
        not review.tool_manifest_review_is_not_permission
        or not review.manifest_candidate_is_not_registered_tool_manifest
        or not review.tool_decision_is_not_execution_approval
        or not review.tool_manifest_review_is_not_adapter
        or not review.tool_manifest_review_is_not_scheduler
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneToolManifestReviewError("tool-manifest review guardrails drifted")
    if review.finding_count != len(review.findings):
        raise ControlPlaneToolManifestReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneToolManifestReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneToolManifestReviewError("severity_counts do not match findings")
    if set(review.latest_manifest_ids) & set(review.non_latest_manifest_ids):
        raise ControlPlaneToolManifestReviewError("latest and non-latest manifest ids must be disjoint")
    if any(not _is_path_segment_safe(manifest_id) for manifest_id in review.manifest_ids):
        raise ControlPlaneToolManifestReviewError("manifest ids must be path-segment safe")


def render_control_plane_tool_manifest_review_json(review: ControlPlaneToolManifestReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True)


def render_control_plane_tool_manifest_review_markdown(review: ControlPlaneToolManifestReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Tool Manifest Review",
        "",
        f"- review_status: {review.review_status}",
        f"- manifest_count: {review.manifest_count}",
        f"- tool_count: {review.tool_count}",
        f"- active_manifest_ids: {', '.join(review.active_manifest_ids) if review.active_manifest_ids else 'none'}",
        f"- blocked_manifest_ids: {', '.join(review.blocked_manifest_ids) if review.blocked_manifest_ids else 'none'}",
        f"- allowed_tool_ids: {', '.join(review.allowed_tool_ids) if review.allowed_tool_ids else 'none'}",
        f"- review_required_tool_ids: {', '.join(review.review_required_tool_ids) if review.review_required_tool_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "- state_change: none",
        "- tool_manifest_review_is_not_permission: true",
        "- manifest_candidate_is_not_registered_tool_manifest: true",
        "- tool_decision_is_not_execution_approval: true",
        "- tool_manifest_review_is_not_adapter: true",
        "- tool_manifest_review_is_not_scheduler: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Findings",
    ]
    if not review.findings:
        lines.append("- none")
    for finding in review.findings:
        lines.append(f"- {finding.severity} `{finding.code}` on `{finding.manifest_id}`: {finding.detail}")
    return "\n".join(lines) + "\n"
