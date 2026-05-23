from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview


class ControlPlaneEvidencePolicyReviewError(ValueError):
    """Raised when evidence-policy review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneEvidencePolicyCandidate:
    policy_id: str
    policy_thread_id: str
    revision: int
    lifecycle_status: str
    policy_scope: str
    authority_boundary: str
    supersedes_policy_id: str
    evidence_ids: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    allowed_evidence_kinds: tuple[str, ...]
    accepted_statuses: tuple[str, ...]
    requires_human_decision_for_sensitive: bool
    requires_redaction_for_sensitive: bool
    rejects_raw_evidence: bool
    rejects_secret_material: bool
    retention_policy_defined: bool
    expiration_policy_defined: bool
    provenance_policy_defined: bool
    rejection_policy_defined: bool
    audit_logging_defined: bool
    claims_evidence_authority: bool
    grants_execution_permission: bool
    registers_evidence_store: bool
    reads_live_evidence_store: bool
    mutates_state: bool
    auto_apply: bool
    contains_secret_material: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneEvidenceRecord:
    evidence_id: str
    evidence_kind: str
    status: str
    data_sensitivity: str
    source_scope: str
    collected_at: str
    expires_on: str
    policy_ids: tuple[str, ...]
    human_decision_id: str
    sanitized: bool
    redacted: bool
    contains_raw_evidence: bool
    contains_secret_material: bool
    contains_personal_data: bool
    claims_truth: bool
    grants_permission: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneEvidencePolicyFinding:
    code: str
    severity: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneEvidencePolicyReview:
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
    evidence_record_count: int
    evidence_ids: tuple[str, ...]
    accepted_evidence_ids: tuple[str, ...]
    rejected_evidence_ids: tuple[str, ...]
    quarantined_evidence_ids: tuple[str, ...]
    insufficient_evidence_ids: tuple[str, ...]
    expired_evidence_ids: tuple[str, ...]
    raw_evidence_ids: tuple[str, ...]
    sensitive_evidence_ids: tuple[str, ...]
    secret_evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    decision_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneEvidencePolicyFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane evidence policy review only"
    evidence_policy_review_is_not_permission: bool = True
    accepted_evidence_is_not_truth: bool = True
    evidence_record_is_not_truth: bool = True
    evidence_record_is_not_runtime_state: bool = True
    evidence_policy_review_is_not_evidence_store: bool = True
    evidence_status_is_not_execution_approval: bool = True
    evidence_sufficiency_is_not_execution_approval: bool = True
    approval_presence_is_not_sufficient_evidence: bool = True
    silence_is_not_negative_evidence: bool = True
    secret_material_must_not_be_retained: bool = True
    raw_tool_output_must_not_be_retained: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_LIFECYCLE_STATUSES = {"draft", "active_candidate", "blocked", "superseded", "archived"}
_POLICY_SCOPES = {"control_plane", "runtime_manager", "tooling", "observability", "security", "unknown"}
_AUTHORITY_BOUNDARIES = {"advisory_policy", "candidate_policy", "evidence_store_boundary_request", "unknown"}
_EVIDENCE_KINDS = {
    "human_decision",
    "test_run",
    "review_report",
    "trace",
    "screenshot",
    "log_excerpt",
    "external_source",
    "sanitized_artifact",
    "raw_dump",
    "secret",
    "unknown",
}
_EVIDENCE_STATUSES = {"draft", "accepted", "rejected", "quarantined", "insufficient", "expired", "superseded"}
_SENSITIVITY = ("public", "internal", "sensitive", "secret")
_SOURCE_SCOPES = {"local_repo", "target_project", "cloud", "third_party", "external", "unknown"}
_SEVERITIES = {"critical", "high", "medium", "low"}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "evidence is truth",
    "evidence_is_truth",
    "accepted evidence is truth",
    "accepted_evidence_is_truth",
    "evidence grants permission",
    "evidence_grants_permission",
    "accepted evidence grants permission",
    "evidence approved execution",
    "evidence execution approval",
    "evidence selected next action",
    "evidence store is truth",
    "evidence_store_is_truth",
    "canonical evidence store",
    "canonical_evidence_store",
    "raw evidence is acceptable",
    "raw evidence accepted",
    "secret evidence accepted",
    "secret material accepted",
    "permission to execute",
    "execution approval",
    "runtime authority",
    "source of truth",
    "scheduler",
    "schedules work",
)
_NEGATIVE_TEXT_MARKERS = (
    "not truth",
    "is not truth",
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not an evidence store",
    "not a scheduler",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not accept raw",
    "does not store",
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
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneEvidencePolicyReviewError(f"missing required evidence-policy field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must be a positive integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field, False)
    if not isinstance(value, bool):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must be a boolean")
    return value


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must contain non-empty strings")
    ids = tuple(str(item).strip() for item in value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} items must be path-segment safe")
    if len(set(ids)) != len(ids):
        raise ControlPlaneEvidencePolicyReviewError(f"{field} must not contain duplicates")
    return ids


def _as_vocab_tuple(value: object, field: str, vocabulary: set[str]) -> tuple[str, ...]:
    ids = _as_id_tuple(value, field)
    unknown = sorted(item for item in ids if item not in vocabulary)
    if unknown:
        raise ControlPlaneEvidencePolicyReviewError(f"{field} contains unknown values: {', '.join(unknown)}")
    return ids


def _finding(code: str, severity: str, subject_id: str, detail: str) -> ControlPlaneEvidencePolicyFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown severity: {severity}")
    return ControlPlaneEvidencePolicyFinding(code=code, severity=severity, subject_id=subject_id, detail=detail)


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ").replace("-", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _normalize_policy(payload: Mapping[str, object]) -> ControlPlaneEvidencePolicyCandidate:
    policy_id = _required_str(payload, "policy_id")
    policy_thread_id = _required_str(payload, "policy_thread_id")
    if not _is_path_segment_safe(policy_id) or not _is_path_segment_safe(policy_thread_id):
        raise ControlPlaneEvidencePolicyReviewError("policy identifiers must be path-segment safe")
    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    policy_scope = _required_str(payload, "policy_scope")
    if policy_scope not in _POLICY_SCOPES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown policy_scope: {policy_scope}")
    authority_boundary = _required_str(payload, "authority_boundary")
    if authority_boundary not in _AUTHORITY_BOUNDARIES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown authority_boundary: {authority_boundary}")
    return ControlPlaneEvidencePolicyCandidate(
        policy_id=policy_id,
        policy_thread_id=policy_thread_id,
        revision=_required_int(payload, "revision"),
        lifecycle_status=lifecycle_status,
        policy_scope=policy_scope,
        authority_boundary=authority_boundary,
        supersedes_policy_id=_optional_str(payload, "supersedes_policy_id"),
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence_ids"),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids"), "depends_on_decision_ids"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids"), "referenced_rule_ids"),
        allowed_evidence_kinds=_as_vocab_tuple(payload.get("allowed_evidence_kinds"), "allowed_evidence_kinds", _EVIDENCE_KINDS),
        accepted_statuses=_as_vocab_tuple(payload.get("accepted_statuses"), "accepted_statuses", _EVIDENCE_STATUSES),
        requires_human_decision_for_sensitive=_required_bool(payload, "requires_human_decision_for_sensitive"),
        requires_redaction_for_sensitive=_required_bool(payload, "requires_redaction_for_sensitive"),
        rejects_raw_evidence=_required_bool(payload, "rejects_raw_evidence"),
        rejects_secret_material=_required_bool(payload, "rejects_secret_material"),
        retention_policy_defined=_required_bool(payload, "retention_policy_defined"),
        expiration_policy_defined=_required_bool(payload, "expiration_policy_defined"),
        provenance_policy_defined=_required_bool(payload, "provenance_policy_defined"),
        rejection_policy_defined=_required_bool(payload, "rejection_policy_defined"),
        audit_logging_defined=_required_bool(payload, "audit_logging_defined"),
        claims_evidence_authority=_required_bool(payload, "claims_evidence_authority"),
        grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
        registers_evidence_store=_required_bool(payload, "registers_evidence_store"),
        reads_live_evidence_store=_required_bool(payload, "reads_live_evidence_store"),
        mutates_state=_required_bool(payload, "mutates_state"),
        auto_apply=_required_bool(payload, "auto_apply"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _normalize_record(payload: Mapping[str, object]) -> ControlPlaneEvidenceRecord:
    evidence_id = _required_str(payload, "evidence_id")
    if not _is_path_segment_safe(evidence_id):
        raise ControlPlaneEvidencePolicyReviewError("evidence_id must be path-segment safe")
    evidence_kind = _required_str(payload, "evidence_kind")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown evidence_kind: {evidence_kind}")
    status = _required_str(payload, "status")
    if status not in _EVIDENCE_STATUSES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown evidence status: {status}")
    data_sensitivity = _required_str(payload, "data_sensitivity")
    if data_sensitivity not in _SENSITIVITY:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown data_sensitivity: {data_sensitivity}")
    source_scope = _required_str(payload, "source_scope")
    if source_scope not in _SOURCE_SCOPES:
        raise ControlPlaneEvidencePolicyReviewError(f"unknown source_scope: {source_scope}")
    collected_at = _required_str(payload, "collected_at")
    _parse_date(collected_at, "collected_at")
    expires_on = _optional_str(payload, "expires_on")
    if expires_on:
        _parse_date(expires_on, "expires_on")
    human_decision_id = _optional_str(payload, "human_decision_id")
    if human_decision_id and not _is_path_segment_safe(human_decision_id):
        raise ControlPlaneEvidencePolicyReviewError("human_decision_id must be path-segment safe")
    return ControlPlaneEvidenceRecord(
        evidence_id=evidence_id,
        evidence_kind=evidence_kind,
        status=status,
        data_sensitivity=data_sensitivity,
        source_scope=source_scope,
        collected_at=collected_at,
        expires_on=expires_on,
        policy_ids=_as_id_tuple(payload.get("policy_ids"), "policy_ids"),
        human_decision_id=human_decision_id,
        sanitized=_required_bool(payload, "sanitized"),
        redacted=_required_bool(payload, "redacted"),
        contains_raw_evidence=_required_bool(payload, "contains_raw_evidence"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        contains_personal_data=_required_bool(payload, "contains_personal_data"),
        claims_truth=_required_bool(payload, "claims_truth"),
        grants_permission=_required_bool(payload, "grants_permission"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _latest_and_non_latest(
    policies: tuple[ControlPlaneEvidencePolicyCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    latest_by_thread: dict[str, ControlPlaneEvidencePolicyCandidate] = {}
    for policy in sorted(policies, key=lambda item: (item.policy_thread_id, item.revision, item.policy_id)):
        current = latest_by_thread.get(policy.policy_thread_id)
        if current is None or policy.revision > current.revision:
            latest_by_thread[policy.policy_thread_id] = policy
    latest_ids = tuple(sorted(policy.policy_id for policy in latest_by_thread.values()))
    non_latest_ids = tuple(sorted(policy.policy_id for policy in policies if policy.policy_id not in latest_ids))
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
            raise ControlPlaneEvidencePolicyReviewError(f"{name} must not mutate state")
        if review is not None and "non-authoritative" not in getattr(review, "authority", ""):
            raise ControlPlaneEvidencePolicyReviewError(f"{name} must remain non-authoritative")
        if review is not None and not getattr(review, "must_not_execute_automatically", True):
            raise ControlPlaneEvidencePolicyReviewError(f"{name} must not execute automatically")
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if bundle.state_change != "none" or not bundle.must_not_execute_automatically:
            raise ControlPlaneEvidencePolicyReviewError("action review bundles must remain advisory")
    return bundles


def _review_policies(
    policies: tuple[ControlPlaneEvidencePolicyCandidate, ...],
    records: tuple[ControlPlaneEvidenceRecord, ...],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneEvidencePolicyFinding, ...]:
    findings: list[ControlPlaneEvidencePolicyFinding] = []
    by_id = {policy.policy_id: policy for policy in policies}
    by_thread: dict[str, list[ControlPlaneEvidencePolicyCandidate]] = {}
    for policy in policies:
        by_thread.setdefault(policy.policy_thread_id, []).append(policy)

    for thread_policies in by_thread.values():
        revisions = sorted(policy.revision for policy in thread_policies)
        if len(set(revisions)) != len(revisions):
            duplicated = next(revision for revision in revisions if revisions.count(revision) > 1)
            for policy in thread_policies:
                if policy.revision == duplicated:
                    findings.append(_finding("evidence_policy_duplicate_thread_revision", "high", policy.policy_id, str(duplicated)))
        expected = list(range(min(revisions), max(revisions) + 1))
        if revisions and revisions != expected:
            findings.append(_finding("evidence_policy_revision_gap", "high", thread_policies[-1].policy_id, "policy revisions are not contiguous"))

    latest_ids, _ = _latest_and_non_latest(policies)
    active_ids = [policy.policy_id for policy in policies if policy.lifecycle_status == "active_candidate"]
    if len(active_ids) > 1:
        for policy_id in active_ids:
            findings.append(_finding("multiple_active_evidence_policy_candidates", "high", policy_id, "more than one active policy candidate"))

    for policy in policies:
        if not policy.evidence_ids:
            findings.append(_finding("evidence_policy_missing_evidence", "high", policy.policy_id, "policy has no evidence ids"))
        if policy.lifecycle_status == "active_candidate" and policy.policy_id not in latest_ids:
            findings.append(_finding("active_evidence_policy_not_latest_revision", "high", policy.policy_id, "active policy is not latest revision"))
        if policy.supersedes_policy_id:
            superseded = by_id.get(policy.supersedes_policy_id)
            if policy.supersedes_policy_id == policy.policy_id:
                findings.append(_finding("evidence_policy_supersedes_self", "high", policy.policy_id, "policy supersedes itself"))
            elif superseded is None:
                findings.append(_finding("evidence_policy_supersedes_unknown_id", "high", policy.policy_id, "superseded policy id is unknown"))
            elif superseded.policy_thread_id != policy.policy_thread_id:
                findings.append(_finding("evidence_policy_supersedes_cross_thread", "high", policy.policy_id, "policy supersedes another thread"))
            elif superseded.revision != policy.revision - 1:
                findings.append(_finding("evidence_policy_supersedes_non_previous_revision", "medium", policy.policy_id, "policy skips supersession chain"))
        elif policy.revision > 1:
            findings.append(_finding("evidence_policy_missing_supersession", "high", policy.policy_id, "policy revision lacks supersedes_policy_id"))

        if "accepted" not in policy.accepted_statuses:
            findings.append(_finding("evidence_policy_does_not_define_acceptance", "high", policy.policy_id, "accepted status is absent"))
        if not policy.allowed_evidence_kinds:
            findings.append(_finding("evidence_policy_missing_allowed_kinds", "high", policy.policy_id, "allowed evidence kinds are empty"))
        missing_policy_checks = (
            ("evidence_policy_allows_raw_evidence", "critical", policy.rejects_raw_evidence),
            ("evidence_policy_allows_secret_material", "critical", policy.rejects_secret_material),
            ("evidence_policy_missing_sensitive_human_decision", "high", policy.requires_human_decision_for_sensitive),
            ("evidence_policy_missing_sensitive_redaction", "high", policy.requires_redaction_for_sensitive),
            ("evidence_policy_missing_retention_policy", "medium", policy.retention_policy_defined),
            ("evidence_policy_missing_expiration_policy", "medium", policy.expiration_policy_defined),
            ("evidence_policy_missing_provenance_policy", "high", policy.provenance_policy_defined),
            ("evidence_policy_missing_rejection_policy", "medium", policy.rejection_policy_defined),
            ("evidence_policy_missing_audit_logging", "medium", policy.audit_logging_defined),
        )
        for code, severity, present in missing_policy_checks:
            if not present:
                findings.append(_finding(code, severity, policy.policy_id, f"{code} in candidate policy"))

        boundary_checks = (
            ("evidence_policy_claims_evidence_authority", "critical", policy.claims_evidence_authority),
            ("evidence_policy_grants_execution_permission", "critical", policy.grants_execution_permission),
            ("evidence_policy_registers_evidence_store", "high", policy.registers_evidence_store),
            ("evidence_policy_reads_live_evidence_store", "high", policy.reads_live_evidence_store),
            ("evidence_policy_mutates_state", "critical", policy.mutates_state),
            ("evidence_policy_auto_apply", "critical", policy.auto_apply),
            ("evidence_policy_contains_secret_material", "high", policy.contains_secret_material),
        )
        for code, severity, present in boundary_checks:
            if present:
                findings.append(_finding(code, severity, policy.policy_id, f"{code} observed in candidate flags"))
        if policy.authority_boundary == "evidence_store_boundary_request":
            findings.append(_finding("evidence_policy_requests_store_boundary", "high", policy.policy_id, "evidence store boundary requested"))
        if _has_unqualified_authority_text(policy.summary) or _has_unqualified_authority_text(policy.rationale):
            findings.append(_finding("evidence_policy_text_launders_authority", "high", policy.policy_id, "summary or rationale contains authority wording"))

    active_policy_ids = {policy.policy_id for policy in policies if policy.lifecycle_status == "active_candidate"}
    allowed_kinds = {kind for policy in policies if policy.lifecycle_status == "active_candidate" for kind in policy.allowed_evidence_kinds}
    current_decisions = set(decision_review.current_decision_ids) if decision_review is not None else set()
    review_date = _parse_date(review_as_of, "review_as_of")

    for record in records:
        if record.status == "accepted":
            if not record.policy_ids:
                findings.append(_finding("accepted_evidence_missing_policy_reference", "high", record.evidence_id, "accepted evidence lacks policy ids"))
            if active_policy_ids and not set(record.policy_ids) & active_policy_ids:
                findings.append(_finding("accepted_evidence_references_no_active_policy", "high", record.evidence_id, "accepted evidence lacks active policy"))
            if allowed_kinds and record.evidence_kind not in allowed_kinds:
                findings.append(_finding("accepted_evidence_kind_not_allowed", "high", record.evidence_id, record.evidence_kind))
            if record.contains_raw_evidence or record.evidence_kind == "raw_dump":
                findings.append(_finding("accepted_evidence_contains_raw_material", "critical", record.evidence_id, "raw evidence accepted"))
            if record.contains_secret_material or record.evidence_kind == "secret" or record.data_sensitivity == "secret":
                findings.append(_finding("accepted_evidence_contains_secret_material", "critical", record.evidence_id, "secret material accepted"))
            if record.data_sensitivity in {"sensitive", "secret"} and not record.redacted:
                findings.append(_finding("accepted_sensitive_evidence_not_redacted", "high", record.evidence_id, "sensitive evidence is not redacted"))
            if not record.sanitized:
                findings.append(_finding("accepted_evidence_not_sanitized", "high", record.evidence_id, "accepted evidence is not sanitized"))
            if record.contains_personal_data and not record.human_decision_id:
                findings.append(_finding("accepted_personal_data_without_human_decision", "high", record.evidence_id, "personal data needs human decision"))
            if record.data_sensitivity in {"sensitive", "secret"} and not record.human_decision_id:
                findings.append(_finding("accepted_sensitive_evidence_without_human_decision", "high", record.evidence_id, "sensitive evidence needs human decision"))
            if record.human_decision_id and decision_review is not None and record.human_decision_id not in current_decisions:
                findings.append(_finding("accepted_evidence_references_non_current_decision", "high", record.evidence_id, record.human_decision_id))
            if record.expires_on and _parse_date(record.expires_on, "expires_on") < review_date:
                findings.append(_finding("accepted_evidence_expired", "high", record.evidence_id, record.expires_on))
        if record.status == "rejected" and record.rationale.lower().strip() in {"", "none", "n/a"}:
            findings.append(_finding("rejected_evidence_missing_rationale", "medium", record.evidence_id, "rejected evidence needs rationale"))
        if record.status == "quarantined" and record.human_decision_id:
            findings.append(_finding("quarantined_evidence_has_human_acceptance", "medium", record.evidence_id, "quarantined evidence should not carry acceptance"))
        if record.claims_truth:
            findings.append(_finding("evidence_record_claims_truth", "high", record.evidence_id, "evidence record claims truth"))
        if record.grants_permission:
            findings.append(_finding("evidence_record_grants_permission", "critical", record.evidence_id, "evidence record grants permission"))
        if _has_unqualified_authority_text(record.summary) or _has_unqualified_authority_text(record.rationale):
            findings.append(_finding("evidence_record_text_launders_authority", "high", record.evidence_id, "summary or rationale contains authority wording"))

    referenced_decisions = {decision_id for policy in policies for decision_id in policy.depends_on_decision_ids}
    referenced_decisions |= {record.human_decision_id for record in records if record.human_decision_id}
    if referenced_decisions and decision_review is None:
        for subject_id in sorted(referenced_decisions):
            findings.append(_finding("evidence_policy_missing_decision_review", "high", subject_id, "decision reference lacks review"))
    elif decision_review is not None:
        for subject_id in sorted(referenced_decisions - current_decisions):
            findings.append(_finding("evidence_policy_references_non_current_decision", "high", subject_id, "decision is not current"))

    referenced_rules = {rule_id for policy in policies for rule_id in policy.referenced_rule_ids}
    if referenced_rules:
        if rule_promotion_review is None:
            for subject_id in sorted(referenced_rules):
                findings.append(_finding("evidence_policy_missing_rule_promotion_review", "high", subject_id, "rule reference lacks review"))
        else:
            active_rules = set(rule_promotion_review.active_rule_ids)
            for subject_id in sorted(referenced_rules - active_rules):
                findings.append(_finding("evidence_policy_references_non_active_rule", "high", subject_id, "rule is not active"))
    if referenced_rules and rule_promotion_review is not None and rule_promotion_review.review_status != "rule_promotion_contract_observed":
        for policy in policies:
            if policy.referenced_rule_ids:
                findings.append(_finding("evidence_policy_over_rule_promotion_drift", "high", policy.policy_id, rule_promotion_review.review_status))

    if integrity_review is None:
        for policy in policies:
            findings.append(_finding("evidence_policy_missing_integrity_review", "high", policy.policy_id, "integrity review is required"))
    elif integrity_review.review_status != "control_plane_integrity_preserved":
        for policy in policies:
            findings.append(_finding("evidence_policy_over_integrity_drift", "critical", policy.policy_id, integrity_review.review_status))

    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_ready":
            for policy in policies:
                findings.append(_finding("evidence_policy_over_action_review_blocker", "high", policy.policy_id, bundle.action_posture))

    return tuple(findings)


def build_control_plane_evidence_policy_review(
    policy_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    evidence_record_payloads: Iterable[Mapping[str, object]] = (),
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneEvidencePolicyReview:
    _parse_date(review_as_of, "review_as_of")
    raw_policies = tuple(policy_payloads)
    if not raw_policies:
        raise ControlPlaneEvidencePolicyReviewError("at least one evidence-policy candidate is required")
    policies = tuple(_normalize_policy(payload) for payload in raw_policies)
    ids = [policy.policy_id for policy in policies]
    if len(set(ids)) != len(ids):
        raise ControlPlaneEvidencePolicyReviewError("duplicate policy ids are not allowed")
    records = tuple(_normalize_record(payload) for payload in evidence_record_payloads)
    record_ids = [record.evidence_id for record in records]
    if len(set(record_ids)) != len(record_ids):
        raise ControlPlaneEvidencePolicyReviewError("duplicate evidence record ids are not allowed")
    bundles = _check_supplied_review_guardrails(
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=action_review_bundles,
    )
    findings = _review_policies(
        policies,
        records,
        review_as_of=review_as_of,
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=bundles,
    )
    latest_ids, non_latest_ids = _latest_and_non_latest(policies)
    high_or_critical = {finding.subject_id for finding in findings if finding.severity in {"critical", "high"}}
    blocked_policy_ids = tuple(sorted(policy.policy_id for policy in policies if policy.policy_id in high_or_critical))
    review_status = "evidence_policy_candidate_observed"
    if any(finding.severity in {"critical", "high"} for finding in findings):
        review_status = "evidence_policy_review_blocked"
    elif findings:
        review_status = "evidence_policy_review_attention_required"

    evidence_ids = tuple(sorted({item for policy in policies for item in policy.evidence_ids} | set(record_ids)))
    return ControlPlaneEvidencePolicyReview(
        schema_version="1",
        review_role="reviews_evidence_policy_candidates_without_evidence_store_authority",
        review_status=review_status,
        review_as_of=review_as_of,
        policy_count=len(policies),
        policy_thread_count=len({policy.policy_thread_id for policy in policies}),
        policy_ids=tuple(sorted(ids)),
        policy_thread_ids=tuple(sorted({policy.policy_thread_id for policy in policies})),
        latest_policy_ids=latest_ids,
        non_latest_policy_ids=non_latest_ids,
        active_policy_ids=tuple(sorted(policy.policy_id for policy in policies if policy.lifecycle_status == "active_candidate")),
        blocked_policy_ids=blocked_policy_ids,
        evidence_record_count=len(records),
        evidence_ids=evidence_ids,
        accepted_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.status == "accepted")),
        rejected_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.status == "rejected")),
        quarantined_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.status == "quarantined")),
        insufficient_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.status == "insufficient")),
        expired_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.status == "expired")),
        raw_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.contains_raw_evidence or record.evidence_kind == "raw_dump")),
        sensitive_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.data_sensitivity == "sensitive")),
        secret_evidence_ids=tuple(sorted(record.evidence_id for record in records if record.data_sensitivity == "secret" or record.contains_secret_material)),
        referenced_decision_ids=tuple(
            sorted(
                {item for policy in policies for item in policy.depends_on_decision_ids}
                | {record.human_decision_id for record in records if record.human_decision_id}
            )
        ),
        referenced_rule_ids=tuple(sorted({item for policy in policies for item in policy.referenced_rule_ids})),
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )


def _validate_review(review: ControlPlaneEvidencePolicyReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneEvidencePolicyReviewError("evidence-policy review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneEvidencePolicyReviewError("evidence-policy review must remain non-authoritative")
    if (
        not review.evidence_policy_review_is_not_permission
        or not review.accepted_evidence_is_not_truth
        or not review.evidence_record_is_not_truth
        or not review.evidence_record_is_not_runtime_state
        or not review.evidence_policy_review_is_not_evidence_store
        or not review.evidence_status_is_not_execution_approval
        or not review.evidence_sufficiency_is_not_execution_approval
        or not review.approval_presence_is_not_sufficient_evidence
        or not review.silence_is_not_negative_evidence
        or not review.secret_material_must_not_be_retained
        or not review.raw_tool_output_must_not_be_retained
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneEvidencePolicyReviewError("evidence-policy review guardrails drifted")
    if review.finding_count != len(review.findings):
        raise ControlPlaneEvidencePolicyReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneEvidencePolicyReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneEvidencePolicyReviewError("severity_counts do not match findings")
    if set(review.latest_policy_ids) & set(review.non_latest_policy_ids):
        raise ControlPlaneEvidencePolicyReviewError("latest and non-latest policy ids must be disjoint")
    if any(not _is_path_segment_safe(policy_id) for policy_id in review.policy_ids):
        raise ControlPlaneEvidencePolicyReviewError("policy ids must be path-segment safe")


def render_control_plane_evidence_policy_review_json(review: ControlPlaneEvidencePolicyReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True)


def render_control_plane_evidence_policy_review_markdown(review: ControlPlaneEvidencePolicyReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Evidence Policy Review",
        "",
        f"- review_status: {review.review_status}",
        f"- policy_count: {review.policy_count}",
        f"- evidence_record_count: {review.evidence_record_count}",
        f"- active_policy_ids: {', '.join(review.active_policy_ids) if review.active_policy_ids else 'none'}",
        f"- blocked_policy_ids: {', '.join(review.blocked_policy_ids) if review.blocked_policy_ids else 'none'}",
        f"- accepted_evidence_ids: {', '.join(review.accepted_evidence_ids) if review.accepted_evidence_ids else 'none'}",
        f"- raw_evidence_ids: {', '.join(review.raw_evidence_ids) if review.raw_evidence_ids else 'none'}",
        f"- secret_evidence_ids: {', '.join(review.secret_evidence_ids) if review.secret_evidence_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "- state_change: none",
        "- evidence_policy_review_is_not_permission: true",
        "- accepted_evidence_is_not_truth: true",
        "- evidence_record_is_not_truth: true",
        "- evidence_record_is_not_runtime_state: true",
        "- evidence_policy_review_is_not_evidence_store: true",
        "- evidence_status_is_not_execution_approval: true",
        "- evidence_sufficiency_is_not_execution_approval: true",
        "- approval_presence_is_not_sufficient_evidence: true",
        "- silence_is_not_negative_evidence: true",
        "- secret_material_must_not_be_retained: true",
        "- raw_tool_output_must_not_be_retained: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Findings",
    ]
    if not review.findings:
        lines.append("- none")
    for finding in review.findings:
        lines.append(f"- {finding.severity} `{finding.code}` on `{finding.subject_id}`: {finding.detail}")
    return "\n".join(lines) + "\n"
