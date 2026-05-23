from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview
from experiments.control_plane_runtime_adoption_review import ControlPlaneRuntimeAdoptionReview
from experiments.control_plane_runtime_state_review import ControlPlaneRuntimeStateReview


class ControlPlaneRuntimeContractReviewError(ValueError):
    """Raised when runtime-contract review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneRuntimeContractCandidate:
    contract_id: str
    contract_thread_id: str
    revision: int
    lifecycle_status: str
    contract_scope: str
    authority_boundary: str
    supersedes_contract_id: str
    declared_sections: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    runtime_adoption_candidate_ids: tuple[str, ...]
    runtime_state_snapshot_ids: tuple[str, ...]
    state_model_proposed: bool
    machine_readable_state: bool
    queue_model_proposed: bool
    tool_manifest_proposed: bool
    approval_policy_defined: bool
    evidence_policy_defined: bool
    rollback_policy_defined: bool
    retry_policy_defined: bool
    observability_defined: bool
    decision_versioning_defined: bool
    handoff_protocol_defined: bool
    security_limits_defined: bool
    stop_rules_defined: bool
    claims_runtime_authority: bool
    claims_canonical_contract: bool
    grants_execution_permission: bool
    enables_scheduler: bool
    reads_live_state: bool
    mutates_state: bool
    imports_adapters: bool
    auto_apply: bool
    contains_secret_material: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneRuntimeContractFinding:
    code: str
    severity: str
    contract_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRuntimeContractReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    contract_count: int
    contract_thread_count: int
    contract_ids: tuple[str, ...]
    contract_thread_ids: tuple[str, ...]
    latest_contract_ids: tuple[str, ...]
    non_latest_contract_ids: tuple[str, ...]
    active_contract_ids: tuple[str, ...]
    blocked_contract_ids: tuple[str, ...]
    declared_section_ids: tuple[str, ...]
    missing_required_sections: tuple[str, ...]
    evidence_count: int
    evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    runtime_adoption_candidate_ids: tuple[str, ...]
    runtime_state_snapshot_ids: tuple[str, ...]
    decision_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    runtime_adoption_review_status: str
    runtime_state_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneRuntimeContractFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane runtime contract review only"
    contract_review_is_not_permission: bool = True
    contract_candidate_is_not_canonical_runtime_contract: bool = True
    contract_status_is_not_execution_approval: bool = True
    contract_review_is_not_scheduler: bool = True
    contract_review_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_LIFECYCLE_STATUSES = {"draft", "active_candidate", "blocked", "superseded", "archived"}
_CONTRACT_SCOPES = {"runtime_manager", "control_plane", "tooling", "observability", "security", "unknown"}
_AUTHORITY_BOUNDARIES = {"advisory_spec", "candidate_contract", "runtime_boundary_request", "unknown"}
_SEVERITIES = {"critical", "high", "medium", "low"}
_REQUIRED_SECTIONS = {
    "mission",
    "non_goals",
    "states",
    "transitions",
    "gates",
    "permissions",
    "evidence_policy",
    "task_queue",
    "dependencies",
    "retry_policy",
    "rollback_policy",
    "observability",
    "decision_versioning",
    "handoff",
    "tool_manifest",
    "security_limits",
    "memory_policy",
    "stop_rules",
}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "canonical runtime contract",
    "canonical_contract",
    "contract is truth",
    "contract_is_truth",
    "contract grants permission",
    "permission to execute",
    "execution approval",
    "execution approved",
    "ready to execute",
    "approved to run",
    "runtime authority",
    "runtime_authority",
    "scheduler",
    "schedules work",
    "selected next action",
    "next action selected",
    "source of truth",
    "state store",
    "queue reader",
    "permission layer",
    "auto apply",
    "automatically applies",
    "adapter approved",
    "runtime enabled",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not a state store",
    "not authority",
    "is not truth",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not apply",
    "does not enable",
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
        raise ControlPlaneRuntimeContractReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneRuntimeContractReviewError(f"missing required runtime-contract field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneRuntimeContractReviewError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneRuntimeContractReviewError(f"{field} must be a positive integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field, False)
    if not isinstance(value, bool):
        raise ControlPlaneRuntimeContractReviewError(f"{field} must be a boolean")
    return value


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneRuntimeContractReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneRuntimeContractReviewError(f"{field} must contain non-empty strings")
    ids = tuple(str(item).strip() for item in value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneRuntimeContractReviewError(f"{field} items must be path-segment safe")
    if len(set(ids)) != len(ids):
        raise ControlPlaneRuntimeContractReviewError(f"{field} must not contain duplicates")
    return ids


def _finding(
    code: str,
    severity: str,
    contract_id: str,
    detail: str,
) -> ControlPlaneRuntimeContractFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneRuntimeContractReviewError(f"unknown severity: {severity}")
    return ControlPlaneRuntimeContractFinding(code=code, severity=severity, contract_id=contract_id, detail=detail)


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _normalize_candidate(payload: Mapping[str, object]) -> ControlPlaneRuntimeContractCandidate:
    contract_id = _required_str(payload, "contract_id")
    if not _is_path_segment_safe(contract_id):
        raise ControlPlaneRuntimeContractReviewError("contract_id must be path-segment safe")
    contract_thread_id = _required_str(payload, "contract_thread_id")
    if not _is_path_segment_safe(contract_thread_id):
        raise ControlPlaneRuntimeContractReviewError("contract_thread_id must be path-segment safe")

    declared_sections = _as_id_tuple(payload.get("declared_sections", []), "declared_sections")
    unknown_sections = set(declared_sections) - _REQUIRED_SECTIONS
    if unknown_sections:
        raise ControlPlaneRuntimeContractReviewError(f"unknown declared section: {sorted(unknown_sections)[0]}")

    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneRuntimeContractReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    contract_scope = _required_str(payload, "contract_scope")
    if contract_scope not in _CONTRACT_SCOPES:
        raise ControlPlaneRuntimeContractReviewError(f"unknown contract_scope: {contract_scope}")
    authority_boundary = _required_str(payload, "authority_boundary")
    if authority_boundary not in _AUTHORITY_BOUNDARIES:
        raise ControlPlaneRuntimeContractReviewError(f"unknown authority_boundary: {authority_boundary}")

    return ControlPlaneRuntimeContractCandidate(
        contract_id=contract_id,
        contract_thread_id=contract_thread_id,
        revision=_required_int(payload, "revision"),
        lifecycle_status=lifecycle_status,
        contract_scope=contract_scope,
        authority_boundary=authority_boundary,
        supersedes_contract_id=_optional_str(payload, "supersedes_contract_id"),
        declared_sections=declared_sections,
        evidence_ids=_as_id_tuple(payload.get("evidence_ids", []), "evidence_ids"),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids", []), "depends_on_decision_ids"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids", []), "referenced_rule_ids"),
        runtime_adoption_candidate_ids=_as_id_tuple(
            payload.get("runtime_adoption_candidate_ids", []), "runtime_adoption_candidate_ids"
        ),
        runtime_state_snapshot_ids=_as_id_tuple(payload.get("runtime_state_snapshot_ids", []), "runtime_state_snapshot_ids"),
        state_model_proposed=_required_bool(payload, "state_model_proposed"),
        machine_readable_state=_required_bool(payload, "machine_readable_state"),
        queue_model_proposed=_required_bool(payload, "queue_model_proposed"),
        tool_manifest_proposed=_required_bool(payload, "tool_manifest_proposed"),
        approval_policy_defined=_required_bool(payload, "approval_policy_defined"),
        evidence_policy_defined=_required_bool(payload, "evidence_policy_defined"),
        rollback_policy_defined=_required_bool(payload, "rollback_policy_defined"),
        retry_policy_defined=_required_bool(payload, "retry_policy_defined"),
        observability_defined=_required_bool(payload, "observability_defined"),
        decision_versioning_defined=_required_bool(payload, "decision_versioning_defined"),
        handoff_protocol_defined=_required_bool(payload, "handoff_protocol_defined"),
        security_limits_defined=_required_bool(payload, "security_limits_defined"),
        stop_rules_defined=_required_bool(payload, "stop_rules_defined"),
        claims_runtime_authority=_required_bool(payload, "claims_runtime_authority"),
        claims_canonical_contract=_required_bool(payload, "claims_canonical_contract"),
        grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
        enables_scheduler=_required_bool(payload, "enables_scheduler"),
        reads_live_state=_required_bool(payload, "reads_live_state"),
        mutates_state=_required_bool(payload, "mutates_state"),
        imports_adapters=_required_bool(payload, "imports_adapters"),
        auto_apply=_required_bool(payload, "auto_apply"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        summary=_optional_str(payload, "summary"),
        rationale=_optional_str(payload, "rationale"),
    )


def _validate_review_guardrails(
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None,
    runtime_state_review: ControlPlaneRuntimeStateReview | None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle],
) -> tuple[ControlPlaneActionReviewBundle, ...]:
    if decision_review is not None and (
        not decision_review.decision_review_is_not_permission
        or not decision_review.finding_is_not_truth
        or not decision_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("decision review guardrails drifted")
    if integrity_review is not None and (
        not integrity_review.review_is_not_permission
        or not integrity_review.integrity_pass_is_not_truth
        or not integrity_review.finding_is_not_execution_approval
        or not integrity_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("integrity review guardrails drifted")
    if rule_promotion_review is not None and (
        not rule_promotion_review.rule_review_is_not_permission
        or not rule_promotion_review.rule_record_is_not_truth
        or not rule_promotion_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("rule promotion review guardrails drifted")
    if runtime_adoption_review is not None and (
        not runtime_adoption_review.adoption_review_is_not_permission
        or not runtime_adoption_review.technology_selection_is_not_authority
        or not runtime_adoption_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("runtime adoption review guardrails drifted")
    if runtime_state_review is not None and (
        not runtime_state_review.state_review_is_not_permission
        or not runtime_state_review.snapshot_is_not_canonical_state
        or not runtime_state_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("runtime state review guardrails drifted")

    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if (
            not bundle.bundle_is_not_permission
            or not bundle.action_posture_is_not_execution_approval
            or not bundle.must_not_execute_automatically
        ):
            raise ControlPlaneRuntimeContractReviewError("action review bundle guardrails drifted")
    return bundles


def _latest_and_non_latest(
    candidates: tuple[ControlPlaneRuntimeContractCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    latest_by_thread: dict[str, int] = {}
    for candidate in candidates:
        latest_by_thread[candidate.contract_thread_id] = max(
            latest_by_thread.get(candidate.contract_thread_id, 0), candidate.revision
        )
    latest_ids = tuple(
        sorted(
            candidate.contract_id
            for candidate in candidates
            if candidate.revision == latest_by_thread[candidate.contract_thread_id]
        )
    )
    non_latest_ids = tuple(sorted(candidate.contract_id for candidate in candidates if candidate.contract_id not in latest_ids))
    return latest_ids, non_latest_ids


def _review_candidates(
    candidates: tuple[ControlPlaneRuntimeContractCandidate, ...],
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None,
    runtime_state_review: ControlPlaneRuntimeStateReview | None,
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneRuntimeContractFinding, ...]:
    findings: list[ControlPlaneRuntimeContractFinding] = []
    by_id = {candidate.contract_id: candidate for candidate in candidates}
    by_thread: dict[str, list[ControlPlaneRuntimeContractCandidate]] = {}
    for candidate in candidates:
        by_thread.setdefault(candidate.contract_thread_id, []).append(candidate)

    for thread_candidates in by_thread.values():
        revisions = sorted(candidate.revision for candidate in thread_candidates)
        if len(set(revisions)) != len(revisions):
            duplicated = next(revision for revision in revisions if revisions.count(revision) > 1)
            for candidate in thread_candidates:
                if candidate.revision == duplicated:
                    findings.append(
                        _finding(
                            "contract_duplicate_thread_revision",
                            "high",
                            candidate.contract_id,
                            f"contract thread {candidate.contract_thread_id} has duplicate revision {duplicated}",
                        )
                    )
        expected = list(range(min(revisions), max(revisions) + 1))
        if revisions and revisions != expected:
            findings.append(
                _finding(
                    "contract_revision_gap",
                    "high",
                    thread_candidates[-1].contract_id,
                    f"contract thread {thread_candidates[-1].contract_thread_id} revisions are not contiguous",
                )
            )

    latest_ids, _ = _latest_and_non_latest(candidates)
    active_ids = [candidate.contract_id for candidate in candidates if candidate.lifecycle_status == "active_candidate"]
    if len(active_ids) > 1:
        for candidate_id in active_ids:
            findings.append(_finding("multiple_active_runtime_contract_candidates", "high", candidate_id, "more than one active candidate observed"))

    for candidate in candidates:
        missing_sections = sorted(_REQUIRED_SECTIONS - set(candidate.declared_sections))
        for section in missing_sections:
            severity = "high" if section in {"permissions", "evidence_policy", "task_queue", "stop_rules"} else "medium"
            findings.append(
                _finding(
                    "contract_missing_required_section",
                    severity,
                    candidate.contract_id,
                    f"contract is missing required section: {section}",
                )
            )
        if not candidate.evidence_ids:
            findings.append(_finding("contract_missing_evidence", "high", candidate.contract_id, "contract has no evidence ids"))
        if candidate.lifecycle_status == "active_candidate" and candidate.contract_id not in latest_ids:
            findings.append(
                _finding("active_contract_not_latest_revision", "high", candidate.contract_id, "active candidate is not latest revision")
            )
        if candidate.supersedes_contract_id:
            superseded = by_id.get(candidate.supersedes_contract_id)
            if candidate.supersedes_contract_id == candidate.contract_id:
                findings.append(_finding("contract_supersedes_self", "high", candidate.contract_id, "contract supersedes itself"))
            elif superseded is None:
                findings.append(
                    _finding("contract_supersedes_unknown_id", "high", candidate.contract_id, "superseded contract id is unknown")
                )
            elif superseded.contract_thread_id != candidate.contract_thread_id:
                findings.append(
                    _finding("contract_supersedes_cross_thread", "high", candidate.contract_id, "contract supersedes another thread")
                )
            elif superseded.revision != candidate.revision - 1:
                findings.append(
                    _finding("contract_supersedes_non_previous_revision", "medium", candidate.contract_id, "contract skips supersession chain")
                )
        elif candidate.revision > 1:
            findings.append(
                _finding("contract_missing_supersession", "high", candidate.contract_id, "contract revision lacks supersedes_contract_id")
            )

        boolean_checks = (
            ("contract_claims_runtime_authority", "critical", candidate.claims_runtime_authority),
            ("contract_claims_canonical_contract", "high", candidate.claims_canonical_contract),
            ("contract_grants_execution_permission", "critical", candidate.grants_execution_permission),
            ("contract_enables_scheduler", "critical", candidate.enables_scheduler),
            ("contract_requests_live_state_read", "high", candidate.reads_live_state),
            ("contract_requests_state_mutation", "critical", candidate.mutates_state),
            ("contract_requests_adapter_import", "high", candidate.imports_adapters),
            ("contract_requests_auto_apply", "critical", candidate.auto_apply),
            ("contract_contains_secret_material", "high", candidate.contains_secret_material),
        )
        for code, severity, present in boolean_checks:
            if present:
                findings.append(_finding(code, severity, candidate.contract_id, f"{code} observed in candidate flags"))

        capability_checks = (
            ("contract_missing_state_model", "high", candidate.state_model_proposed),
            ("contract_missing_machine_readable_state", "high", candidate.machine_readable_state),
            ("contract_missing_queue_model", "high", candidate.queue_model_proposed),
            ("contract_missing_tool_manifest", "medium", candidate.tool_manifest_proposed),
            ("contract_missing_approval_policy", "high", candidate.approval_policy_defined),
            ("contract_missing_evidence_policy", "high", candidate.evidence_policy_defined),
            ("contract_missing_rollback_policy", "medium", candidate.rollback_policy_defined),
            ("contract_missing_retry_policy", "medium", candidate.retry_policy_defined),
            ("contract_missing_observability", "medium", candidate.observability_defined),
            ("contract_missing_decision_versioning", "medium", candidate.decision_versioning_defined),
            ("contract_missing_handoff_protocol", "medium", candidate.handoff_protocol_defined),
            ("contract_missing_security_limits", "high", candidate.security_limits_defined),
            ("contract_missing_stop_rules", "high", candidate.stop_rules_defined),
        )
        for code, severity, present in capability_checks:
            if not present:
                findings.append(_finding(code, severity, candidate.contract_id, f"{code} in candidate contract"))

        if candidate.authority_boundary == "runtime_boundary_request":
            findings.append(
                _finding(
                    "contract_requests_runtime_boundary",
                    "high",
                    candidate.contract_id,
                    "contract requests a runtime boundary but this review is advisory only",
                )
            )
        if _has_unqualified_authority_text(candidate.summary) or _has_unqualified_authority_text(candidate.rationale):
            findings.append(
                _finding(
                    "contract_text_launders_runtime_authority",
                    "high",
                    candidate.contract_id,
                    "summary or rationale contains authority wording without a local negative marker",
                )
            )

    referenced_decisions = {decision_id for candidate in candidates for decision_id in candidate.depends_on_decision_ids}
    if referenced_decisions:
        if decision_review is None:
            for contract_id in (candidate.contract_id for candidate in candidates if candidate.depends_on_decision_ids):
                findings.append(_finding("contract_missing_decision_review", "high", contract_id, "contract references decisions without review"))
        else:
            current_decisions = set(decision_review.current_decision_ids)
            for candidate in candidates:
                for decision_id in candidate.depends_on_decision_ids:
                    if decision_id not in current_decisions:
                        findings.append(
                            _finding("contract_references_non_current_decision", "high", candidate.contract_id, decision_id)
                        )
    if referenced_rules := {rule_id for candidate in candidates for rule_id in candidate.referenced_rule_ids}:
        if rule_promotion_review is None:
            for contract_id in (candidate.contract_id for candidate in candidates if candidate.referenced_rule_ids):
                findings.append(_finding("contract_missing_rule_promotion_review", "high", contract_id, "contract references rules without review"))
        else:
            active_rules = set(rule_promotion_review.active_rule_ids)
            for candidate in candidates:
                for rule_id in candidate.referenced_rule_ids:
                    if rule_id not in active_rules:
                        findings.append(_finding("contract_references_non_active_rule", "high", candidate.contract_id, rule_id))
    if referenced_rules and rule_promotion_review is not None and rule_promotion_review.review_status != "rule_promotion_contract_observed":
        for candidate in candidates:
            if candidate.referenced_rule_ids:
                findings.append(_finding("contract_over_rule_promotion_drift", "high", candidate.contract_id, rule_promotion_review.review_status))
    if integrity_review is None:
        for candidate in candidates:
            findings.append(_finding("contract_missing_integrity_review", "high", candidate.contract_id, "integrity review is required"))
    elif integrity_review.review_status != "control_plane_integrity_preserved":
        for candidate in candidates:
            findings.append(_finding("contract_over_integrity_drift", "critical", candidate.contract_id, integrity_review.review_status))

    if any(candidate.runtime_adoption_candidate_ids for candidate in candidates):
        if runtime_adoption_review is None:
            for candidate in candidates:
                if candidate.runtime_adoption_candidate_ids:
                    findings.append(
                        _finding(
                            "contract_missing_runtime_adoption_review",
                            "high",
                            candidate.contract_id,
                            "runtime adoption candidates require supplied adoption review",
                        )
                    )
        else:
            for candidate in candidates:
                for proposal_id in candidate.runtime_adoption_candidate_ids:
                    if proposal_id not in runtime_adoption_review.proposal_ids:
                        findings.append(
                            _finding("contract_references_unknown_runtime_adoption_candidate", "high", candidate.contract_id, proposal_id)
                        )
                    if proposal_id in runtime_adoption_review.blocked_proposal_ids:
                        findings.append(
                            _finding("contract_references_blocked_runtime_adoption_candidate", "high", candidate.contract_id, proposal_id)
                        )
    if any(candidate.runtime_state_snapshot_ids for candidate in candidates):
        if runtime_state_review is None:
            for candidate in candidates:
                if candidate.runtime_state_snapshot_ids:
                    findings.append(
                        _finding(
                            "contract_missing_runtime_state_review",
                            "high",
                            candidate.contract_id,
                            "runtime state snapshots require supplied state review",
                        )
                    )
        elif runtime_state_review.review_status not in {"runtime_state_snapshot_observed", "runtime_state_contract_blocked"}:
            for candidate in candidates:
                if candidate.runtime_state_snapshot_ids:
                    findings.append(_finding("contract_over_runtime_state_drift", "high", candidate.contract_id, runtime_state_review.review_status))
        else:
            for candidate in candidates:
                for snapshot_id in candidate.runtime_state_snapshot_ids:
                    if snapshot_id not in runtime_state_review.snapshot_ids:
                        findings.append(_finding("contract_references_unknown_runtime_state_snapshot", "high", candidate.contract_id, snapshot_id))
                    if snapshot_id in runtime_state_review.blocked_snapshot_ids:
                        findings.append(_finding("contract_references_blocked_runtime_state_snapshot", "high", candidate.contract_id, snapshot_id))

    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_ready":
            for candidate in candidates:
                findings.append(_finding("contract_over_action_review_blocker", "high", candidate.contract_id, bundle.action_posture))

    return tuple(findings)


def build_control_plane_runtime_contract_review(
    contract_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None = None,
    runtime_state_review: ControlPlaneRuntimeStateReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneRuntimeContractReview:
    _parse_date(review_as_of, "review_as_of")
    payloads = tuple(contract_payloads)
    if not payloads:
        raise ControlPlaneRuntimeContractReviewError("at least one runtime-contract candidate is required")
    candidates = tuple(_normalize_candidate(payload) for payload in payloads)
    ids = [candidate.contract_id for candidate in candidates]
    if len(set(ids)) != len(ids):
        raise ControlPlaneRuntimeContractReviewError("duplicate contract ids are not allowed")
    bundles = _validate_review_guardrails(
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        runtime_adoption_review=runtime_adoption_review,
        runtime_state_review=runtime_state_review,
        action_review_bundles=action_review_bundles,
    )
    findings = _review_candidates(
        candidates,
        decision_review=decision_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        runtime_adoption_review=runtime_adoption_review,
        runtime_state_review=runtime_state_review,
        action_review_bundles=bundles,
    )
    latest_ids, non_latest_ids = _latest_and_non_latest(candidates)
    high_or_critical = {finding.contract_id for finding in findings if finding.severity in {"critical", "high"}}
    blocked_contract_ids = tuple(sorted(high_or_critical))
    missing_required_sections = tuple(sorted(_REQUIRED_SECTIONS - {section for candidate in candidates for section in candidate.declared_sections}))
    review_status = "runtime_contract_candidate_observed"
    if high_or_critical:
        review_status = "runtime_contract_review_blocked"
    elif findings:
        review_status = "runtime_contract_review_attention_required"

    evidence_ids = tuple(sorted({evidence_id for candidate in candidates for evidence_id in candidate.evidence_ids}))
    return ControlPlaneRuntimeContractReview(
        schema_version="1",
        review_role="reviews_runtime_manager_contract_candidates_without_runtime_authority",
        review_status=review_status,
        review_as_of=review_as_of,
        contract_count=len(candidates),
        contract_thread_count=len({candidate.contract_thread_id for candidate in candidates}),
        contract_ids=tuple(sorted(ids)),
        contract_thread_ids=tuple(sorted({candidate.contract_thread_id for candidate in candidates})),
        latest_contract_ids=latest_ids,
        non_latest_contract_ids=non_latest_ids,
        active_contract_ids=tuple(sorted(candidate.contract_id for candidate in candidates if candidate.lifecycle_status == "active_candidate")),
        blocked_contract_ids=blocked_contract_ids,
        declared_section_ids=tuple(sorted({section for candidate in candidates for section in candidate.declared_sections})),
        missing_required_sections=missing_required_sections,
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        referenced_decision_ids=tuple(sorted({item for candidate in candidates for item in candidate.depends_on_decision_ids})),
        referenced_rule_ids=tuple(sorted({item for candidate in candidates for item in candidate.referenced_rule_ids})),
        runtime_adoption_candidate_ids=tuple(sorted({item for candidate in candidates for item in candidate.runtime_adoption_candidate_ids})),
        runtime_state_snapshot_ids=tuple(sorted({item for candidate in candidates for item in candidate.runtime_state_snapshot_ids})),
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        runtime_adoption_review_status=runtime_adoption_review.review_status if runtime_adoption_review is not None else "not_supplied",
        runtime_state_review_status=runtime_state_review.review_status if runtime_state_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )


def _validate_review(review: ControlPlaneRuntimeContractReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneRuntimeContractReviewError("runtime-contract review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneRuntimeContractReviewError("runtime-contract review must remain non-authoritative")
    if (
        not review.contract_review_is_not_permission
        or not review.contract_candidate_is_not_canonical_runtime_contract
        or not review.contract_status_is_not_execution_approval
        or not review.contract_review_is_not_scheduler
        or not review.contract_review_is_not_state_store
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeContractReviewError("runtime-contract review guardrails drifted")
    if review.finding_count != len(review.findings):
        raise ControlPlaneRuntimeContractReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneRuntimeContractReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneRuntimeContractReviewError("severity_counts do not match findings")
    if set(review.latest_contract_ids) & set(review.non_latest_contract_ids):
        raise ControlPlaneRuntimeContractReviewError("latest and non-latest contract ids must be disjoint")
    if any(not _is_path_segment_safe(contract_id) for contract_id in review.contract_ids):
        raise ControlPlaneRuntimeContractReviewError("contract ids must be path-segment safe")


def render_control_plane_runtime_contract_review_json(review: ControlPlaneRuntimeContractReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True)


def render_control_plane_runtime_contract_review_markdown(review: ControlPlaneRuntimeContractReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Runtime Contract Review",
        "",
        f"- review_status: {review.review_status}",
        f"- contract_count: {review.contract_count}",
        f"- active_contract_ids: {', '.join(review.active_contract_ids) if review.active_contract_ids else 'none'}",
        f"- blocked_contract_ids: {', '.join(review.blocked_contract_ids) if review.blocked_contract_ids else 'none'}",
        f"- missing_required_sections: {', '.join(review.missing_required_sections) if review.missing_required_sections else 'none'}",
        f"- finding_count: {review.finding_count}",
        "- state_change: none",
        "- contract_review_is_not_permission: true",
        "- contract_candidate_is_not_canonical_runtime_contract: true",
        "- contract_status_is_not_execution_approval: true",
        "- contract_review_is_not_scheduler: true",
        "- contract_review_is_not_state_store: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Findings",
    ]
    if not review.findings:
        lines.append("- none")
    for finding in review.findings:
        lines.append(f"- {finding.severity} `{finding.code}` on `{finding.contract_id}`: {finding.detail}")
    return "\n".join(lines) + "\n"
