from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_evidence_policy_review import ControlPlaneEvidencePolicyReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview
from experiments.control_plane_tool_manifest_review import ControlPlaneToolManifestReview
from experiments.control_plane_work_queue_review import ControlPlaneWorkQueueReview


class ControlPlaneApprovalPolicyReviewError(ValueError):
    """Raised when approval-policy review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneApprovalPolicyCandidate:
    policy_id: str
    policy_thread_id: str
    revision: int
    lifecycle_status: str
    policy_scope: str
    approval_kind: str
    authority_boundary: str
    supersedes_policy_id: str
    evidence_ids: tuple[str, ...]
    required_evidence_kinds: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    referenced_tool_manifest_ids: tuple[str, ...]
    referenced_work_item_ids: tuple[str, ...]
    allowed_request_statuses: tuple[str, ...]
    requires_human_decision: bool
    requires_current_decision: bool
    requires_accepted_evidence: bool
    requires_integrity_preserved: bool
    requires_tool_review: bool
    requires_work_queue_review: bool
    requires_explicit_scope: bool
    requires_action_fingerprint: bool
    requires_expiration: bool
    requires_audit_logging: bool
    requires_revocation_path: bool
    rejects_blanket_approval: bool
    rejects_reuse_after_scope_drift: bool
    claims_approval_authority: bool
    grants_execution_permission: bool
    acts_as_permission_layer: bool
    registers_approval_store: bool
    reads_live_approval_store: bool
    schedules_work: bool
    selects_next_action: bool
    mutates_state: bool
    auto_apply: bool
    contains_secret_material: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneApprovalPolicyFinding:
    code: str
    severity: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneApprovalPolicyReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    policy_count: int
    policy_thread_count: int
    policy_ids: tuple[str, ...]
    policy_thread_ids: tuple[str, ...]
    latest_policy_ids: tuple[str, ...]
    non_latest_policy_ids: tuple[str, ...]
    active_policy_ids: tuple[str, ...]
    blocked_policy_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    referenced_tool_manifest_ids: tuple[str, ...]
    referenced_work_item_ids: tuple[str, ...]
    decision_review_status: str
    evidence_policy_review_status: str
    tool_manifest_review_status: str
    work_queue_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneApprovalPolicyFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane approval policy review only"
    approval_policy_review_is_not_permission: bool = True
    approval_policy_review_is_not_approval_store: bool = True
    approval_status_is_not_execution_approval: bool = True
    approval_presence_is_not_sufficient_evidence: bool = True
    approval_policy_review_is_not_scheduler: bool = True
    approval_policy_review_is_not_runtime_gate: bool = True
    approval_policy_review_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_LIFECYCLE_STATUSES = {"draft", "active_candidate", "blocked", "superseded", "archived"}
_POLICY_SCOPES = {"control_plane", "runtime_manager", "tooling", "work_queue", "security", "unknown"}
_APPROVAL_KINDS = {
    "human_execution",
    "tool_use",
    "scope_change",
    "evidence_acceptance",
    "work_queue_readiness",
    "emergency_stop",
    "unknown",
}
_AUTHORITY_BOUNDARIES = {
    "advisory_policy",
    "candidate_policy",
    "approval_store_boundary_request",
    "permission_layer_boundary_request",
    "unknown",
}
_REQUEST_STATUSES = {"draft", "requested", "approved", "rejected", "revoked", "expired", "superseded"}
_EVIDENCE_KINDS = {
    "human_decision",
    "test_run",
    "review_report",
    "trace",
    "screenshot",
    "log_excerpt",
    "external_source",
    "sanitized_artifact",
    "unknown",
}
_SEVERITIES = {"critical", "high", "medium", "low"}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "approval grants permission",
    "approval is execution approval",
    "approval store is truth",
    "canonical approval store",
    "approval policy is authority",
    "canonical approval policy",
    "approval policy grants permission",
    "approval status is truth",
    "approval status grants permission",
    "expired approval grants permission",
    "approval never expires",
    "scope wildcard grants permission",
    "approval covers all scopes",
    "fingerprint is optional",
    "fingerprint reuse allowed",
    "approval applies across tasks",
    "permission layer",
    "runtime gate",
    "approved to execute",
    "ready to execute",
    "scheduler",
    "schedules work",
    "selected next action",
    "source of truth",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not approval store",
    "not runtime gate",
    "not state store",
    "not a scheduler",
    "not truth",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not approve",
    "not sufficient",
    "not reusable",
    "not valid after expiration",
    "not valid outside scope",
    "fingerprint must match",
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
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneApprovalPolicyReviewError(f"missing required approval-policy field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must be a positive integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field, False)
    if not isinstance(value, bool):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must be a boolean")
    return value


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must contain non-empty strings")
    ids = tuple(str(item).strip() for item in value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} items must be path-segment safe")
    if len(set(ids)) != len(ids):
        raise ControlPlaneApprovalPolicyReviewError(f"{field} must not contain duplicates")
    return ids


def _as_vocab_tuple(value: object, field: str, vocabulary: set[str]) -> tuple[str, ...]:
    ids = _as_id_tuple(value, field)
    unknown = sorted(item for item in ids if item not in vocabulary)
    if unknown:
        raise ControlPlaneApprovalPolicyReviewError(f"{field} contains unknown values: {', '.join(unknown)}")
    return ids


def _finding(code: str, severity: str, subject_id: str, detail: str) -> ControlPlaneApprovalPolicyFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneApprovalPolicyReviewError(f"unknown severity: {severity}")
    return ControlPlaneApprovalPolicyFinding(code=code, severity=severity, subject_id=subject_id, detail=detail)


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ").replace("-", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _normalize_candidate(payload: Mapping[str, object]) -> ControlPlaneApprovalPolicyCandidate:
    policy_id = _required_str(payload, "policy_id")
    policy_thread_id = _required_str(payload, "policy_thread_id")
    if not all(_is_path_segment_safe(value) for value in (policy_id, policy_thread_id)):
        raise ControlPlaneApprovalPolicyReviewError("approval-policy identifiers must be path-segment safe")
    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneApprovalPolicyReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    policy_scope = _required_str(payload, "policy_scope")
    if policy_scope not in _POLICY_SCOPES:
        raise ControlPlaneApprovalPolicyReviewError(f"unknown policy_scope: {policy_scope}")
    approval_kind = _required_str(payload, "approval_kind")
    if approval_kind not in _APPROVAL_KINDS:
        raise ControlPlaneApprovalPolicyReviewError(f"unknown approval_kind: {approval_kind}")
    authority_boundary = _required_str(payload, "authority_boundary")
    if authority_boundary not in _AUTHORITY_BOUNDARIES:
        raise ControlPlaneApprovalPolicyReviewError(f"unknown authority_boundary: {authority_boundary}")
    supersedes_policy_id = _optional_str(payload, "supersedes_policy_id")
    if supersedes_policy_id and not _is_path_segment_safe(supersedes_policy_id):
        raise ControlPlaneApprovalPolicyReviewError("supersedes_policy_id must be path-segment safe")
    return ControlPlaneApprovalPolicyCandidate(
        policy_id=policy_id,
        policy_thread_id=policy_thread_id,
        revision=_required_int(payload, "revision"),
        lifecycle_status=lifecycle_status,
        policy_scope=policy_scope,
        approval_kind=approval_kind,
        authority_boundary=authority_boundary,
        supersedes_policy_id=supersedes_policy_id,
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence_ids"),
        required_evidence_kinds=_as_vocab_tuple(payload.get("required_evidence_kinds"), "required_evidence_kinds", _EVIDENCE_KINDS),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids"), "depends_on_decision_ids"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids"), "referenced_rule_ids"),
        referenced_tool_manifest_ids=_as_id_tuple(payload.get("referenced_tool_manifest_ids"), "referenced_tool_manifest_ids"),
        referenced_work_item_ids=_as_id_tuple(payload.get("referenced_work_item_ids"), "referenced_work_item_ids"),
        allowed_request_statuses=_as_vocab_tuple(payload.get("allowed_request_statuses"), "allowed_request_statuses", _REQUEST_STATUSES),
        requires_human_decision=_required_bool(payload, "requires_human_decision"),
        requires_current_decision=_required_bool(payload, "requires_current_decision"),
        requires_accepted_evidence=_required_bool(payload, "requires_accepted_evidence"),
        requires_integrity_preserved=_required_bool(payload, "requires_integrity_preserved"),
        requires_tool_review=_required_bool(payload, "requires_tool_review"),
        requires_work_queue_review=_required_bool(payload, "requires_work_queue_review"),
        requires_explicit_scope=_required_bool(payload, "requires_explicit_scope"),
        requires_action_fingerprint=_required_bool(payload, "requires_action_fingerprint"),
        requires_expiration=_required_bool(payload, "requires_expiration"),
        requires_audit_logging=_required_bool(payload, "requires_audit_logging"),
        requires_revocation_path=_required_bool(payload, "requires_revocation_path"),
        rejects_blanket_approval=_required_bool(payload, "rejects_blanket_approval"),
        rejects_reuse_after_scope_drift=_required_bool(payload, "rejects_reuse_after_scope_drift"),
        claims_approval_authority=_required_bool(payload, "claims_approval_authority"),
        grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
        acts_as_permission_layer=_required_bool(payload, "acts_as_permission_layer"),
        registers_approval_store=_required_bool(payload, "registers_approval_store"),
        reads_live_approval_store=_required_bool(payload, "reads_live_approval_store"),
        schedules_work=_required_bool(payload, "schedules_work"),
        selects_next_action=_required_bool(payload, "selects_next_action"),
        mutates_state=_required_bool(payload, "mutates_state"),
        auto_apply=_required_bool(payload, "auto_apply"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _latest_and_non_latest(
    candidates: tuple[ControlPlaneApprovalPolicyCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    latest_by_thread: dict[str, ControlPlaneApprovalPolicyCandidate] = {}
    for candidate in sorted(candidates, key=lambda value: (value.policy_thread_id, value.revision, value.policy_id)):
        current = latest_by_thread.get(candidate.policy_thread_id)
        if current is None or candidate.revision > current.revision:
            latest_by_thread[candidate.policy_thread_id] = candidate
    latest_ids = tuple(sorted(candidate.policy_id for candidate in latest_by_thread.values()))
    non_latest_ids = tuple(sorted(candidate.policy_id for candidate in candidates if candidate.policy_id not in latest_ids))
    return latest_ids, non_latest_ids


def _check_supplied_review_guardrails(
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None,
    tool_manifest_review: ControlPlaneToolManifestReview | None,
    work_queue_review: ControlPlaneWorkQueueReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle],
) -> tuple[ControlPlaneActionReviewBundle, ...]:
    for name, review in (
        ("decision_review", decision_review),
        ("evidence_policy_review", evidence_policy_review),
        ("tool_manifest_review", tool_manifest_review),
        ("work_queue_review", work_queue_review),
        ("integrity_review", integrity_review),
        ("rule_promotion_review", rule_promotion_review),
    ):
        if review is not None and getattr(review, "state_change", "none") != "none":
            raise ControlPlaneApprovalPolicyReviewError(f"{name} must not mutate state")
        if review is not None and "non-authoritative" not in getattr(review, "authority", ""):
            raise ControlPlaneApprovalPolicyReviewError(f"{name} must remain non-authoritative")
        if review is not None and not getattr(review, "must_not_execute_automatically", True):
            raise ControlPlaneApprovalPolicyReviewError(f"{name} must not execute automatically")
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if bundle.state_change != "none" or not bundle.must_not_execute_automatically:
            raise ControlPlaneApprovalPolicyReviewError("action review bundles must remain advisory")
    return bundles


def _review_candidates(
    candidates: tuple[ControlPlaneApprovalPolicyCandidate, ...],
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None,
    tool_manifest_review: ControlPlaneToolManifestReview | None,
    work_queue_review: ControlPlaneWorkQueueReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneApprovalPolicyFinding, ...]:
    findings: list[ControlPlaneApprovalPolicyFinding] = []
    by_id = {candidate.policy_id: candidate for candidate in candidates}
    by_thread: dict[str, list[ControlPlaneApprovalPolicyCandidate]] = {}
    for candidate in candidates:
        by_thread.setdefault(candidate.policy_thread_id, []).append(candidate)

    for thread_candidates in by_thread.values():
        revisions = sorted(candidate.revision for candidate in thread_candidates)
        if len(set(revisions)) != len(revisions):
            duplicated = next(revision for revision in revisions if revisions.count(revision) > 1)
            for candidate in thread_candidates:
                if candidate.revision == duplicated:
                    findings.append(_finding("approval_policy_duplicate_thread_revision", "high", candidate.policy_id, str(duplicated)))
        expected = list(range(min(revisions), max(revisions) + 1))
        if revisions and revisions != expected:
            findings.append(_finding("approval_policy_revision_gap", "high", thread_candidates[-1].policy_id, "policy revisions are not contiguous"))

    latest_ids, _ = _latest_and_non_latest(candidates)
    active_ids = [candidate.policy_id for candidate in candidates if candidate.lifecycle_status == "active_candidate"]
    if len(active_ids) > 1:
        for policy_id in active_ids:
            findings.append(_finding("multiple_active_approval_policy_candidates", "high", policy_id, "more than one active approval policy candidate"))

    for candidate in candidates:
        if candidate.supersedes_policy_id:
            if candidate.supersedes_policy_id == candidate.policy_id:
                findings.append(_finding("approval_policy_supersedes_self", "high", candidate.policy_id, "policy supersedes itself"))
            superseded = by_id.get(candidate.supersedes_policy_id)
            if superseded is None:
                findings.append(_finding("approval_policy_supersedes_unknown_id", "high", candidate.policy_id, "superseded policy id is unknown"))
            elif superseded.policy_thread_id != candidate.policy_thread_id:
                findings.append(_finding("approval_policy_supersedes_cross_thread", "high", candidate.policy_id, "policy supersedes another thread"))
            elif superseded.revision != candidate.revision - 1:
                findings.append(
                    _finding("approval_policy_supersedes_non_previous_revision", "medium", candidate.policy_id, "policy skips supersession chain")
                )
        elif candidate.revision > 1:
            findings.append(_finding("approval_policy_missing_supersession", "high", candidate.policy_id, "policy revision lacks supersedes_policy_id"))

        if candidate.policy_id not in latest_ids and candidate.lifecycle_status == "active_candidate":
            findings.append(_finding("active_approval_policy_not_latest_revision", "high", candidate.policy_id, "active candidate is not latest revision"))
        if candidate.authority_boundary == "approval_store_boundary_request":
            findings.append(_finding("approval_policy_requests_store_boundary", "critical", candidate.policy_id, "approval store boundary requested"))
        if candidate.authority_boundary == "permission_layer_boundary_request":
            findings.append(_finding("approval_policy_requests_permission_layer_boundary", "critical", candidate.policy_id, "permission layer boundary requested"))
        if not candidate.evidence_ids:
            findings.append(_finding("approval_policy_missing_evidence", "high", candidate.policy_id, "approval policy has no evidence ids"))
        if not candidate.required_evidence_kinds:
            findings.append(_finding("approval_policy_missing_required_evidence_kinds", "medium", candidate.policy_id, "required evidence kinds are empty"))
        if not candidate.requires_human_decision:
            findings.append(_finding("approval_policy_missing_human_decision_requirement", "high", candidate.policy_id, "human decision is not required"))
        if not candidate.requires_current_decision:
            findings.append(_finding("approval_policy_missing_current_decision_requirement", "high", candidate.policy_id, "current decision is not required"))
        if not candidate.requires_accepted_evidence:
            findings.append(_finding("approval_policy_missing_accepted_evidence_requirement", "high", candidate.policy_id, "accepted evidence is not required"))
        if not candidate.requires_integrity_preserved:
            findings.append(_finding("approval_policy_missing_integrity_requirement", "high", candidate.policy_id, "integrity preservation is not required"))
        if candidate.referenced_tool_manifest_ids and not candidate.requires_tool_review:
            findings.append(_finding("approval_policy_missing_tool_review_requirement", "high", candidate.policy_id, "tool review is referenced but not required"))
        if candidate.referenced_work_item_ids and not candidate.requires_work_queue_review:
            findings.append(_finding("approval_policy_missing_work_queue_review_requirement", "high", candidate.policy_id, "work queue review is referenced but not required"))
        if not candidate.requires_explicit_scope:
            findings.append(_finding("approval_policy_missing_explicit_scope", "high", candidate.policy_id, "explicit scope is not required"))
        if not candidate.requires_action_fingerprint:
            findings.append(_finding("approval_policy_missing_action_fingerprint", "high", candidate.policy_id, "action fingerprint is not required"))
        if not candidate.requires_expiration:
            findings.append(_finding("approval_policy_missing_expiration", "medium", candidate.policy_id, "expiration is not required"))
        if not candidate.requires_audit_logging:
            findings.append(_finding("approval_policy_missing_audit_logging", "medium", candidate.policy_id, "audit logging is not required"))
        if not candidate.requires_revocation_path:
            findings.append(_finding("approval_policy_missing_revocation_path", "high", candidate.policy_id, "revocation path is not required"))
        if not candidate.rejects_blanket_approval:
            findings.append(_finding("approval_policy_allows_blanket_approval", "high", candidate.policy_id, "blanket approvals are not rejected"))
        if not candidate.rejects_reuse_after_scope_drift:
            findings.append(_finding("approval_policy_allows_reuse_after_scope_drift", "high", candidate.policy_id, "reuse after scope drift is not rejected"))

        boundary_checks = (
            ("approval_policy_claims_approval_authority", "critical", candidate.claims_approval_authority),
            ("approval_policy_grants_execution_permission", "critical", candidate.grants_execution_permission),
            ("approval_policy_acts_as_permission_layer", "critical", candidate.acts_as_permission_layer),
            ("approval_policy_registers_approval_store", "critical", candidate.registers_approval_store),
            ("approval_policy_reads_live_approval_store", "high", candidate.reads_live_approval_store),
            ("approval_policy_schedules_work", "critical", candidate.schedules_work),
            ("approval_policy_selects_next_action", "critical", candidate.selects_next_action),
            ("approval_policy_mutates_state", "critical", candidate.mutates_state),
            ("approval_policy_auto_apply", "critical", candidate.auto_apply),
            ("approval_policy_contains_secret_material", "high", candidate.contains_secret_material),
        )
        for code, severity, present in boundary_checks:
            if present:
                findings.append(_finding(code, severity, candidate.policy_id, f"{code} observed in candidate flags"))
        if _has_unqualified_authority_text(candidate.summary) or _has_unqualified_authority_text(candidate.rationale):
            findings.append(_finding("approval_policy_text_launders_authority", "high", candidate.policy_id, "summary or rationale contains authority wording"))

    referenced_decisions = {decision_id for candidate in candidates for decision_id in candidate.depends_on_decision_ids}
    if referenced_decisions and decision_review is None:
        for decision_id in sorted(referenced_decisions):
            findings.append(_finding("approval_policy_missing_decision_review", "high", decision_id, "decision reference lacks review"))
    elif decision_review is not None:
        current_decisions = set(decision_review.current_decision_ids)
        for decision_id in sorted(referenced_decisions - current_decisions):
            findings.append(_finding("approval_policy_references_non_current_decision", "high", decision_id, "decision is not current"))

    referenced_rules = {rule_id for candidate in candidates for rule_id in candidate.referenced_rule_ids}
    if referenced_rules:
        if rule_promotion_review is None:
            for rule_id in sorted(referenced_rules):
                findings.append(_finding("approval_policy_missing_rule_promotion_review", "high", rule_id, "rule reference lacks review"))
        else:
            active_rules = set(rule_promotion_review.active_rule_ids)
            for rule_id in sorted(referenced_rules - active_rules):
                findings.append(_finding("approval_policy_references_non_active_rule", "high", rule_id, "rule is not active"))

    if evidence_policy_review is None:
        for candidate in candidates:
            findings.append(_finding("approval_policy_missing_evidence_policy_review", "high", candidate.policy_id, "evidence policy review is required"))
    elif evidence_policy_review.review_status != "evidence_policy_candidate_observed":
        for candidate in candidates:
            findings.append(_finding("approval_policy_over_evidence_policy_drift", "high", candidate.policy_id, evidence_policy_review.review_status))

    referenced_manifests = {manifest_id for candidate in candidates for manifest_id in candidate.referenced_tool_manifest_ids}
    if referenced_manifests:
        if tool_manifest_review is None:
            for manifest_id in sorted(referenced_manifests):
                findings.append(_finding("approval_policy_missing_tool_manifest_review", "high", manifest_id, "tool manifest reference lacks review"))
        elif tool_manifest_review.review_status != "tool_manifest_candidate_observed":
            for manifest_id in sorted(referenced_manifests):
                findings.append(_finding("approval_policy_over_tool_manifest_drift", "high", manifest_id, tool_manifest_review.review_status))
        else:
            known_manifests = set(tool_manifest_review.manifest_ids)
            for manifest_id in sorted(referenced_manifests - known_manifests):
                findings.append(_finding("approval_policy_references_unknown_tool_manifest", "high", manifest_id, "tool manifest is unknown"))

    referenced_work_items = {item_id for candidate in candidates for item_id in candidate.referenced_work_item_ids}
    if referenced_work_items:
        if work_queue_review is None:
            for item_id in sorted(referenced_work_items):
                findings.append(_finding("approval_policy_missing_work_queue_review", "high", item_id, "work item reference lacks review"))
        elif work_queue_review.review_status != "work_queue_candidates_observed":
            for item_id in sorted(referenced_work_items):
                findings.append(_finding("approval_policy_over_work_queue_drift", "high", item_id, work_queue_review.review_status))
        else:
            known_items = set(work_queue_review.item_ids)
            for item_id in sorted(referenced_work_items - known_items):
                findings.append(_finding("approval_policy_references_unknown_work_item", "high", item_id, "work item is unknown"))

    if integrity_review is None:
        for candidate in candidates:
            findings.append(_finding("approval_policy_missing_integrity_review", "high", candidate.policy_id, "integrity review is required"))
    elif integrity_review.review_status != "control_plane_integrity_preserved":
        for candidate in candidates:
            findings.append(_finding("approval_policy_over_integrity_drift", "critical", candidate.policy_id, integrity_review.review_status))

    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_review_only":
            for candidate in candidates:
                findings.append(_finding("approval_policy_over_action_review_blocker", "high", candidate.policy_id, bundle.action_posture))

    return tuple(findings)


def build_control_plane_approval_policy_review(
    policy_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None = None,
    tool_manifest_review: ControlPlaneToolManifestReview | None = None,
    work_queue_review: ControlPlaneWorkQueueReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneApprovalPolicyReview:
    _parse_date(review_as_of, "review_as_of")
    raw_candidates = tuple(policy_payloads)
    if not raw_candidates:
        raise ControlPlaneApprovalPolicyReviewError("at least one approval-policy candidate is required")
    candidates = tuple(_normalize_candidate(payload) for payload in raw_candidates)
    policy_ids = [candidate.policy_id for candidate in candidates]
    if len(set(policy_ids)) != len(policy_ids):
        raise ControlPlaneApprovalPolicyReviewError("duplicate policy ids are not allowed")
    bundles = _check_supplied_review_guardrails(
        decision_review=decision_review,
        evidence_policy_review=evidence_policy_review,
        tool_manifest_review=tool_manifest_review,
        work_queue_review=work_queue_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=action_review_bundles,
    )
    findings = _review_candidates(
        candidates,
        decision_review=decision_review,
        evidence_policy_review=evidence_policy_review,
        tool_manifest_review=tool_manifest_review,
        work_queue_review=work_queue_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=bundles,
    )
    latest_ids, non_latest_ids = _latest_and_non_latest(candidates)
    high_or_critical = {finding.subject_id for finding in findings if finding.severity in {"critical", "high"}}
    review_status = "approval_policy_candidate_observed"
    if any(finding.severity in {"critical", "high"} for finding in findings):
        review_status = "approval_policy_review_blocked"
    elif findings:
        review_status = "approval_policy_review_attention_required"

    return ControlPlaneApprovalPolicyReview(
        schema_version="1",
        review_role="reviews_approval_policy_candidates_without_permission_or_store_authority",
        review_status=review_status,
        review_as_of=review_as_of,
        policy_count=len(candidates),
        policy_thread_count=len({candidate.policy_thread_id for candidate in candidates}),
        policy_ids=tuple(sorted(policy_ids)),
        policy_thread_ids=tuple(sorted({candidate.policy_thread_id for candidate in candidates})),
        latest_policy_ids=latest_ids,
        non_latest_policy_ids=non_latest_ids,
        active_policy_ids=tuple(sorted(candidate.policy_id for candidate in candidates if candidate.lifecycle_status == "active_candidate")),
        blocked_policy_ids=tuple(sorted(policy_id for policy_id in high_or_critical if policy_id in set(policy_ids))),
        evidence_ids=tuple(sorted({evidence_id for candidate in candidates for evidence_id in candidate.evidence_ids})),
        referenced_decision_ids=tuple(sorted({decision_id for candidate in candidates for decision_id in candidate.depends_on_decision_ids})),
        referenced_rule_ids=tuple(sorted({rule_id for candidate in candidates for rule_id in candidate.referenced_rule_ids})),
        referenced_tool_manifest_ids=tuple(
            sorted({manifest_id for candidate in candidates for manifest_id in candidate.referenced_tool_manifest_ids})
        ),
        referenced_work_item_ids=tuple(sorted({item_id for candidate in candidates for item_id in candidate.referenced_work_item_ids})),
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        evidence_policy_review_status=evidence_policy_review.review_status if evidence_policy_review is not None else "not_supplied",
        tool_manifest_review_status=tool_manifest_review.review_status if tool_manifest_review is not None else "not_supplied",
        work_queue_review_status=work_queue_review.review_status if work_queue_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )


def _validate_review(review: ControlPlaneApprovalPolicyReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneApprovalPolicyReviewError("approval-policy review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneApprovalPolicyReviewError("approval-policy review must remain non-authoritative")
    if (
        not review.approval_policy_review_is_not_permission
        or not review.approval_policy_review_is_not_approval_store
        or not review.approval_status_is_not_execution_approval
        or not review.approval_presence_is_not_sufficient_evidence
        or not review.approval_policy_review_is_not_scheduler
        or not review.approval_policy_review_is_not_runtime_gate
        or not review.approval_policy_review_is_not_state_store
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneApprovalPolicyReviewError("approval-policy review guardrails drifted")
    if review.finding_count != len(review.findings):
        raise ControlPlaneApprovalPolicyReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneApprovalPolicyReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneApprovalPolicyReviewError("severity_counts do not match findings")
    if set(review.latest_policy_ids) & set(review.non_latest_policy_ids):
        raise ControlPlaneApprovalPolicyReviewError("latest and non-latest policy ids must be disjoint")
    if any(not _is_path_segment_safe(policy_id) for policy_id in review.policy_ids):
        raise ControlPlaneApprovalPolicyReviewError("policy ids must be path-segment safe")


def render_control_plane_approval_policy_review_json(review: ControlPlaneApprovalPolicyReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True)


def render_control_plane_approval_policy_review_markdown(review: ControlPlaneApprovalPolicyReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Approval Policy Review",
        "",
        f"- review_status: {review.review_status}",
        f"- policy_count: {review.policy_count}",
        f"- active_policy_ids: {', '.join(review.active_policy_ids) if review.active_policy_ids else 'none'}",
        f"- blocked_policy_ids: {', '.join(review.blocked_policy_ids) if review.blocked_policy_ids else 'none'}",
        f"- referenced_decision_ids: {', '.join(review.referenced_decision_ids) if review.referenced_decision_ids else 'none'}",
        f"- referenced_tool_manifest_ids: {', '.join(review.referenced_tool_manifest_ids) if review.referenced_tool_manifest_ids else 'none'}",
        f"- referenced_work_item_ids: {', '.join(review.referenced_work_item_ids) if review.referenced_work_item_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "- state_change: none",
        "- approval_policy_review_is_not_permission: true",
        "- approval_policy_review_is_not_approval_store: true",
        "- approval_status_is_not_execution_approval: true",
        "- approval_presence_is_not_sufficient_evidence: true",
        "- approval_policy_review_is_not_scheduler: true",
        "- approval_policy_review_is_not_runtime_gate: true",
        "- approval_policy_review_is_not_state_store: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Findings",
    ]
    if not review.findings:
        lines.append("- none")
    for finding in review.findings:
        lines.append(f"- {finding.severity}: {finding.code} ({finding.subject_id}) - {finding.detail}")
    return "\n".join(lines) + "\n"
