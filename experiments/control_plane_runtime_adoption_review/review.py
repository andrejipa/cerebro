from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview


class ControlPlaneRuntimeAdoptionReviewError(ValueError):
    """Raised when runtime-adoption review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneRuntimeAdoptionProposal:
    proposal_id: str
    proposal_thread_id: str
    revision: int
    runtime_family: str
    adoption_stage: str
    target_boundary: str
    current_status: str
    risk_level: str
    supersedes_proposal_id: str
    evidence_ids: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    requires_human_decision: bool
    human_decision_id: str
    requests_runtime_enablement: bool
    requests_adapter_import: bool
    requests_io_or_network: bool
    requests_scheduler_authority: bool
    auto_apply: bool
    rollback_plan: str
    observability_plan: str
    security_plan: str
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneRuntimeAdoptionFinding:
    code: str
    severity: str
    proposal_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRuntimeAdoptionReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    proposal_count: int
    proposal_thread_count: int
    proposal_ids: tuple[str, ...]
    proposal_thread_ids: tuple[str, ...]
    active_candidate_ids: tuple[str, ...]
    non_active_candidate_ids: tuple[str, ...]
    runtime_candidate_ids: tuple[str, ...]
    research_candidate_ids: tuple[str, ...]
    blocked_proposal_ids: tuple[str, ...]
    runtime_families: tuple[str, ...]
    target_boundaries: tuple[str, ...]
    evidence_count: int
    evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    decision_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneRuntimeAdoptionFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane runtime adoption review only"
    adoption_review_is_not_permission: bool = True
    adoption_status_is_not_execution_approval: bool = True
    technology_selection_is_not_authority: bool = True
    proposal_record_is_not_truth: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_RUNTIME_FAMILIES = {
    "temporal",
    "mcp",
    "opentelemetry",
    "langgraph",
    "openai_agents_sdk",
    "cloudflare_agents_sdk",
    "custom_runtime",
    "other",
}
_ADOPTION_STAGES = {
    "research",
    "design_note",
    "spike_plan",
    "adapter_proposal",
    "runtime_boundary_request",
    "pilot",
    "production",
    "rejected",
    "deferred",
}
_TARGET_BOUNDARIES = {
    "observability",
    "workflow_orchestration",
    "tool_bridge",
    "agent_runtime",
    "policy_surface",
    "sandbox",
    "scheduler",
    "runtime_core",
    "unknown",
}
_CURRENT_STATUSES = {"draft", "active_candidate", "blocked", "superseded", "rejected", "conflicting"}
_RISK_LEVELS = {"critical", "high", "medium", "low"}
_SEVERITIES = {"critical", "high", "medium", "low"}
_RUNTIME_STAGES = {"adapter_proposal", "runtime_boundary_request", "pilot", "production"}
_RUNTIME_BOUNDARIES = {"workflow_orchestration", "tool_bridge", "agent_runtime", "sandbox", "scheduler", "runtime_core"}
_HIGH_CONTROL_SURFACES = {"temporal", "mcp", "langgraph", "openai_agents_sdk", "cloudflare_agents_sdk", "custom_runtime"}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "grants permission",
    "permission to execute",
    "execution approval",
    "execution approved",
    "permission_granted",
    "runtime authority",
    "runtime_authority",
    "canonical gate",
    "canonical_truth",
    "truth signal",
    "ready to execute",
    "approved to run",
    "selected next action",
    "scheduler",
    "schedules work",
    "auto apply",
    "automatically applies",
    "auto_continue",
    "auto_continuation",
    "adoption approved",
    "runtime enabled",
    "runtime adoption approved",
    "technology selected next action",
    "adapter approved",
    "adapter grants permission",
    "mcp server is authority",
    "mcp grants permission",
    "temporal workflow is truth",
    "langgraph graph is truth",
    "opentelemetry exporter is truth",
    "otel trace is truth",
    "agent handoff grants permission",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not authority",
    "is not truth",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not apply",
    "does not enable",
    "never grants",
)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ControlPlaneRuntimeAdoptionReviewError(f"missing required runtime-adoption field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} must be a string")
    return value.strip()


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} must be an ISO date") from exc


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} must contain only non-empty strings")
    ids = tuple(value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} ids must be path-segment safe")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ControlPlaneRuntimeAdoptionReviewError(f"duplicate {field} ids: {', '.join(duplicates)}")
    return ids


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ControlPlaneRuntimeAdoptionReviewError(f"{field} must be boolean")
    return value


def _proposal_from_payload(payload: Mapping[str, object]) -> ControlPlaneRuntimeAdoptionProposal:
    if not isinstance(payload, Mapping):
        raise ControlPlaneRuntimeAdoptionReviewError("runtime-adoption payload must be a mapping")
    proposal_id = _required_str(payload, "proposal_id")
    if not _is_path_segment_safe(proposal_id):
        raise ControlPlaneRuntimeAdoptionReviewError("proposal_id must be path-segment safe")
    proposal_thread_id = _required_str(payload, "proposal_thread_id")
    if not _is_path_segment_safe(proposal_thread_id):
        raise ControlPlaneRuntimeAdoptionReviewError("proposal_thread_id must be path-segment safe")
    revision = payload.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ControlPlaneRuntimeAdoptionReviewError("revision must be a positive integer")
    runtime_family = _required_str(payload, "runtime_family")
    if runtime_family not in _RUNTIME_FAMILIES:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown runtime_family: {runtime_family}")
    adoption_stage = _required_str(payload, "adoption_stage")
    if adoption_stage not in _ADOPTION_STAGES:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown adoption_stage: {adoption_stage}")
    target_boundary = _required_str(payload, "target_boundary")
    if target_boundary not in _TARGET_BOUNDARIES:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown target_boundary: {target_boundary}")
    current_status = _required_str(payload, "current_status")
    if current_status not in _CURRENT_STATUSES:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown current_status: {current_status}")
    risk_level = _required_str(payload, "risk_level")
    if risk_level not in _RISK_LEVELS:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown risk_level: {risk_level}")
    human_decision_id = _optional_str(payload, "human_decision_id")
    if human_decision_id and not _is_path_segment_safe(human_decision_id):
        raise ControlPlaneRuntimeAdoptionReviewError("human_decision_id must be path-segment safe")
    supersedes_proposal_id = _optional_str(payload, "supersedes_proposal_id")
    if supersedes_proposal_id and not _is_path_segment_safe(supersedes_proposal_id):
        raise ControlPlaneRuntimeAdoptionReviewError("supersedes_proposal_id must be path-segment safe")
    return ControlPlaneRuntimeAdoptionProposal(
        proposal_id=proposal_id,
        proposal_thread_id=proposal_thread_id,
        revision=revision,
        runtime_family=runtime_family,
        adoption_stage=adoption_stage,
        target_boundary=target_boundary,
        current_status=current_status,
        risk_level=risk_level,
        supersedes_proposal_id=supersedes_proposal_id,
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence"),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids"), "depends_on_decision"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids"), "referenced_rule"),
        requires_human_decision=_required_bool(payload, "requires_human_decision"),
        human_decision_id=human_decision_id,
        requests_runtime_enablement=_required_bool(payload, "requests_runtime_enablement"),
        requests_adapter_import=_required_bool(payload, "requests_adapter_import"),
        requests_io_or_network=_required_bool(payload, "requests_io_or_network"),
        requests_scheduler_authority=_required_bool(payload, "requests_scheduler_authority"),
        auto_apply=_required_bool(payload, "auto_apply"),
        rollback_plan=_optional_str(payload, "rollback_plan"),
        observability_plan=_optional_str(payload, "observability_plan"),
        security_plan=_optional_str(payload, "security_plan"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _proposals_from_payloads(payloads: Iterable[Mapping[str, object]]) -> tuple[ControlPlaneRuntimeAdoptionProposal, ...]:
    proposals = tuple(_proposal_from_payload(payload) for payload in payloads)
    ids = [proposal.proposal_id for proposal in proposals]
    duplicates = sorted({proposal_id for proposal_id in ids if ids.count(proposal_id) > 1})
    if duplicates:
        raise ControlPlaneRuntimeAdoptionReviewError(f"duplicate proposal ids: {', '.join(duplicates)}")
    thread_revisions = [(proposal.proposal_thread_id, proposal.revision) for proposal in proposals]
    duplicate_revisions = sorted({item for item in thread_revisions if thread_revisions.count(item) > 1})
    if duplicate_revisions:
        formatted = ", ".join(f"{thread}:{revision}" for thread, revision in duplicate_revisions)
        raise ControlPlaneRuntimeAdoptionReviewError(f"duplicate proposal thread revisions: {formatted}")
    return proposals


def _finding(code: str, severity: str, proposal_id: str, detail: str) -> ControlPlaneRuntimeAdoptionFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneRuntimeAdoptionReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneRuntimeAdoptionFinding(code=code, severity=severity, proposal_id=proposal_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneRuntimeAdoptionReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneRuntimeAdoptionReviewError(f"{label} authority contains forbidden claim: {token}")


def _validate_decision_review(review: ControlPlaneDecisionVersionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeAdoptionReviewError("decision-version review must have state_change none")
    _validate_authority_text(review.authority, "decision-version review")
    if (
        not review.decision_review_is_not_permission
        or not review.decision_current_is_not_execution_approval
        or not review.decision_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeAdoptionReviewError("decision-version review guardrails must remain true")


def _validate_integrity_review(review: ControlPlaneIntegrityReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeAdoptionReviewError("integrity review must have state_change none")
    _validate_authority_text(review.authority, "integrity review")
    if (
        not review.review_is_not_permission
        or not review.integrity_pass_is_not_truth
        or not review.finding_is_not_execution_approval
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeAdoptionReviewError("integrity review guardrails must remain true")


def _validate_rule_promotion_review(review: ControlPlaneRulePromotionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeAdoptionReviewError("rule-promotion review must have state_change none")
    _validate_authority_text(review.authority, "rule-promotion review")
    if (
        not review.rule_review_is_not_permission
        or not review.promotion_candidate_is_not_runtime_authority
        or not review.rule_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeAdoptionReviewError("rule-promotion review guardrails must remain true")


def _validate_action_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneRuntimeAdoptionReviewError("action-review bundle must have state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeAdoptionReviewError("action-review bundle guardrails must remain true")


def _is_runtime_candidate(proposal: ControlPlaneRuntimeAdoptionProposal) -> bool:
    return (
        proposal.requests_runtime_enablement
        or proposal.requests_adapter_import
        or proposal.requests_io_or_network
        or proposal.requests_scheduler_authority
        or proposal.adoption_stage in _RUNTIME_STAGES
        or proposal.target_boundary in _RUNTIME_BOUNDARIES
    )


def _thread_findings(proposals: tuple[ControlPlaneRuntimeAdoptionProposal, ...]) -> list[ControlPlaneRuntimeAdoptionFinding]:
    findings: list[ControlPlaneRuntimeAdoptionFinding] = []
    by_id = {proposal.proposal_id: proposal for proposal in proposals}
    by_thread: dict[str, list[ControlPlaneRuntimeAdoptionProposal]] = {}
    for proposal in proposals:
        by_thread.setdefault(proposal.proposal_thread_id, []).append(proposal)
        if proposal.supersedes_proposal_id == proposal.proposal_id:
            findings.append(
                _finding(
                    "proposal_supersedes_self",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption proposal cannot supersede itself",
                )
            )
        if proposal.revision > 1 and not proposal.supersedes_proposal_id:
            findings.append(
                _finding(
                    "proposal_revision_missing_supersedes",
                    "medium",
                    proposal.proposal_id,
                    "proposal revision greater than 1 does not declare supersedes_proposal_id",
                )
            )
        if proposal.supersedes_proposal_id and proposal.supersedes_proposal_id not in by_id:
            findings.append(
                _finding(
                    "proposal_supersedes_unknown_id",
                    "high",
                    proposal.proposal_id,
                    f"supersedes_proposal_id is unknown: {proposal.supersedes_proposal_id}",
                )
            )

    for thread_id, thread_proposals in by_thread.items():
        revisions = sorted(proposal.revision for proposal in thread_proposals)
        expected = list(range(1, max(revisions) + 1)) if revisions else []
        if revisions != expected:
            missing = sorted(set(expected) - set(revisions))
            findings.append(
                _finding(
                    "proposal_revision_gap",
                    "high",
                    thread_proposals[-1].proposal_id,
                    f"proposal thread {thread_id} has missing revisions: {', '.join(str(item) for item in missing)}",
                )
            )
        active_candidates = [proposal for proposal in thread_proposals if proposal.current_status == "active_candidate"]
        if len(active_candidates) > 1:
            findings.append(
                _finding(
                    "multiple_active_runtime_proposals_in_thread",
                    "high",
                    active_candidates[-1].proposal_id,
                    f"proposal thread {thread_id} has multiple active runtime proposals",
                )
            )
        latest_revision = max(revisions)
        for proposal in active_candidates:
            if proposal.revision != latest_revision:
                findings.append(
                    _finding(
                        "active_runtime_proposal_not_latest_revision",
                        "high",
                        proposal.proposal_id,
                        f"active proposal revision {proposal.revision} is not latest revision {latest_revision}",
                    )
                )
        for proposal in thread_proposals:
            if _is_runtime_candidate(proposal) and proposal.revision != latest_revision:
                findings.append(
                    _finding(
                        "runtime_change_over_stale_candidate",
                        "high",
                        proposal.proposal_id,
                        f"runtime adoption candidate targets revision {proposal.revision}, not latest revision {latest_revision}",
                    )
                )

    for proposal in proposals:
        superseded = by_id.get(proposal.supersedes_proposal_id)
        if superseded is not None and superseded.proposal_thread_id != proposal.proposal_thread_id:
            findings.append(
                _finding(
                    "proposal_supersedes_cross_thread",
                    "high",
                    proposal.proposal_id,
                    f"candidate supersedes {superseded.proposal_id} from thread {superseded.proposal_thread_id}",
                )
            )
        if (
            superseded is not None
            and superseded.proposal_thread_id == proposal.proposal_thread_id
            and superseded.revision != proposal.revision - 1
        ):
            findings.append(
                _finding(
                    "proposal_supersedes_non_previous_revision",
                    "high",
                    proposal.proposal_id,
                    f"candidate revision {proposal.revision} supersedes revision {superseded.revision}",
                )
            )
    return findings


def _proposal_findings(
    proposals: tuple[ControlPlaneRuntimeAdoptionProposal, ...],
) -> list[ControlPlaneRuntimeAdoptionFinding]:
    findings: list[ControlPlaneRuntimeAdoptionFinding] = []
    for proposal in proposals:
        runtime_candidate = _is_runtime_candidate(proposal)
        if proposal.auto_apply:
            findings.append(
                _finding(
                    "proposal_requests_auto_apply",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption proposal requested automatic application",
                )
            )
        if proposal.requests_adapter_import:
            findings.append(
                _finding(
                    "proposal_requests_adapter_import",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption proposal requested importing or enabling an adapter",
                )
            )
        if proposal.requests_io_or_network:
            findings.append(
                _finding(
                    "proposal_requests_io_or_network",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption proposal requested I/O, network, token, or config access",
                )
            )
        if proposal.requests_scheduler_authority:
            findings.append(
                _finding(
                    "proposal_requests_scheduler_authority",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption proposal requested scheduler authority",
                )
            )
        if proposal.requests_runtime_enablement and not proposal.requires_human_decision:
            findings.append(
                _finding(
                    "runtime_enablement_without_human_decision",
                    "high",
                    proposal.proposal_id,
                    "runtime enablement must require an explicit human decision",
                )
            )
        if proposal.requests_runtime_enablement and proposal.human_decision_id.strip().lower() in {"", "none", "auto", "automatic"}:
            findings.append(
                _finding(
                    "runtime_enablement_missing_human_decision_id",
                    "high",
                    proposal.proposal_id,
                    "runtime enablement lacks human_decision_id",
                )
            )
        if proposal.risk_level in {"critical", "high"} and not proposal.evidence_ids:
            findings.append(
                _finding(
                    "high_risk_runtime_proposal_missing_evidence",
                    "high",
                    proposal.proposal_id,
                    "high-risk runtime proposal lacks evidence ids",
                )
            )
        if proposal.risk_level in {"critical", "high"} and not proposal.depends_on_decision_ids:
            findings.append(
                _finding(
                    "high_risk_runtime_proposal_missing_decision_reference",
                    "high",
                    proposal.proposal_id,
                    "high-risk runtime proposal lacks decision references",
                )
            )
        if runtime_candidate and proposal.adoption_stage in {"pilot", "production"} and not proposal.rollback_plan:
            findings.append(
                _finding(
                    "runtime_adoption_missing_rollback_plan",
                    "high",
                    proposal.proposal_id,
                    "pilot or production runtime adoption lacks rollback plan",
                )
            )
        if runtime_candidate and (
            proposal.adoption_stage in {"pilot", "production"} or proposal.target_boundary == "observability"
        ) and not proposal.observability_plan:
            findings.append(
                _finding(
                    "runtime_adoption_missing_observability_plan",
                    "medium",
                    proposal.proposal_id,
                    "runtime adoption lacks observability plan",
                )
            )
        if (
            proposal.runtime_family in {"mcp", "openai_agents_sdk", "cloudflare_agents_sdk"}
            or proposal.requests_io_or_network
            or proposal.target_boundary in {"tool_bridge", "agent_runtime", "sandbox"}
        ) and not proposal.security_plan:
            findings.append(
                _finding(
                    "runtime_adoption_missing_security_plan",
                    "high",
                    proposal.proposal_id,
                    "tool, agent, sandbox, network, or MCP adoption lacks security plan",
                )
            )
        if proposal.current_status in {"blocked", "rejected", "conflicting"} and runtime_candidate:
            findings.append(
                _finding(
                    "blocked_runtime_proposal_kept_or_enabled",
                    "high",
                    proposal.proposal_id,
                    f"{proposal.current_status} runtime proposal cannot be treated as an adoption candidate",
                )
            )
        if proposal.runtime_family == "opentelemetry" and proposal.requests_runtime_enablement:
            findings.append(
                _finding(
                    "opentelemetry_export_must_not_be_authority",
                    "medium",
                    proposal.proposal_id,
                    "OpenTelemetry adoption may expose observability only, not authority or readiness",
                )
            )
        if proposal.runtime_family in _HIGH_CONTROL_SURFACES and runtime_candidate and not proposal.referenced_rule_ids:
            findings.append(
                _finding(
                    "runtime_adoption_missing_rule_reference",
                    "high",
                    proposal.proposal_id,
                    "control-surface runtime proposal lacks referenced rule ids",
                )
            )
        for field_name, text in (("summary", proposal.summary), ("rationale", proposal.rationale)):
            lowered = text.lower()
            has_negative_marker = any(marker in lowered for marker in _NEGATIVE_TEXT_MARKERS)
            for token in _FORBIDDEN_AUTHORITY_TOKENS:
                if token in lowered and not has_negative_marker:
                    findings.append(
                        _finding(
                            "proposal_text_launders_runtime_authority",
                            "high",
                            proposal.proposal_id,
                            f"{field_name} contains forbidden runtime-adoption wording: {token}",
                        )
                    )
    return findings


def _integration_findings(
    proposals: tuple[ControlPlaneRuntimeAdoptionProposal, ...],
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> list[ControlPlaneRuntimeAdoptionFinding]:
    findings: list[ControlPlaneRuntimeAdoptionFinding] = []
    current_decisions = set(decision_review.current_decision_ids) if decision_review is not None else set()
    all_decisions = set(decision_review.decision_ids) if decision_review is not None else set()
    all_rules = set(rule_promotion_review.rule_ids) if rule_promotion_review is not None else set()
    active_rules = set(rule_promotion_review.active_rule_ids) if rule_promotion_review is not None else set()
    blocked_rules = set(rule_promotion_review.blocked_rule_ids) if rule_promotion_review is not None else set()

    for proposal in proposals:
        runtime_candidate = _is_runtime_candidate(proposal)
        if runtime_candidate and decision_review is None:
            findings.append(
                _finding(
                    "runtime_enablement_missing_decision_review",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption candidate has no supplied decision-version review",
                )
            )
        if decision_review is not None:
            for decision_id in proposal.depends_on_decision_ids:
                if decision_id not in all_decisions:
                    findings.append(
                        _finding(
                            "runtime_proposal_references_unknown_decision",
                            "high",
                            proposal.proposal_id,
                            f"proposal references unknown decision id: {decision_id}",
                        )
                    )
                elif decision_id not in current_decisions:
                    findings.append(
                        _finding(
                            "runtime_proposal_references_non_current_decision",
                            "high",
                            proposal.proposal_id,
                            f"proposal references non-current decision id: {decision_id}",
                        )
                    )
            if runtime_candidate:
                if not any(decision_id in current_decisions for decision_id in proposal.depends_on_decision_ids):
                    findings.append(
                        _finding(
                            "runtime_enablement_missing_current_decision_reference",
                            "high",
                            proposal.proposal_id,
                            "runtime adoption candidate does not reference a current decision id",
                        )
                    )
                if decision_review.review_status != "decision_version_contract_observed":
                    findings.append(
                        _finding(
                            "runtime_enablement_over_decision_drift",
                            "critical",
                            proposal.proposal_id,
                            f"decision-version review status is {decision_review.review_status}",
                        )
                    )

        if runtime_candidate and integrity_review is None:
            findings.append(
                _finding(
                    "runtime_enablement_missing_integrity_review",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption candidate has no supplied integrity review",
                )
            )
        if integrity_review is not None and integrity_review.review_status != "control_plane_integrity_preserved" and runtime_candidate:
            findings.append(
                _finding(
                    "runtime_enablement_over_integrity_drift",
                    "critical",
                    proposal.proposal_id,
                    f"integrity review status is {integrity_review.review_status}",
                )
            )

        if runtime_candidate and proposal.referenced_rule_ids and rule_promotion_review is None:
            findings.append(
                _finding(
                    "runtime_enablement_missing_rule_promotion_review",
                    "high",
                    proposal.proposal_id,
                    "runtime adoption candidate references rules without a supplied rule-promotion review",
                )
            )
        if rule_promotion_review is not None:
            for rule_id in proposal.referenced_rule_ids:
                if rule_id not in all_rules:
                    findings.append(
                        _finding(
                            "proposal_references_unknown_rule",
                            "high",
                            proposal.proposal_id,
                            f"proposal references unknown rule id: {rule_id}",
                        )
                    )
                elif rule_id not in active_rules:
                    findings.append(
                        _finding(
                            "proposal_references_non_active_rule",
                            "high",
                            proposal.proposal_id,
                            f"proposal references non-active rule id: {rule_id}",
                        )
                    )
                if rule_id in blocked_rules:
                    findings.append(
                        _finding(
                            "proposal_references_rule_promotion_blocked",
                            "high",
                            proposal.proposal_id,
                            f"proposal references blocked rule id: {rule_id}",
                        )
                    )
            if runtime_candidate and rule_promotion_review.review_status == "rule_promotion_blocked":
                findings.append(
                    _finding(
                        "runtime_enablement_over_rule_promotion_drift",
                        "critical",
                        proposal.proposal_id,
                        "rule-promotion review is blocked",
                    )
                )

        for bundle in action_bundles:
            if bundle.action_posture not in {"advisory_review_only", "human_review_required"}:
                findings.append(
                    _finding(
                        "runtime_adoption_over_blocked_action_posture",
                        "high",
                        proposal.proposal_id,
                        f"action bundle {bundle.observation.observation_id} posture is {bundle.action_posture}",
                    )
                )
            if runtime_candidate and bundle.recommended_human_decision != "none":
                findings.append(
                    _finding(
                        "runtime_adoption_over_unresolved_action_decision",
                        "high",
                        proposal.proposal_id,
                        f"action bundle requires {bundle.recommended_human_decision}",
                    )
                )
    return findings


def _review_status(
    findings: tuple[ControlPlaneRuntimeAdoptionFinding, ...],
    proposals: tuple[ControlPlaneRuntimeAdoptionProposal, ...],
) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "runtime_adoption_blocked"
    if findings:
        return "runtime_adoption_human_review_required"
    if any(_is_runtime_candidate(proposal) for proposal in proposals):
        return "runtime_adoption_candidate_observed"
    return "runtime_adoption_contract_observed"


def _validate_review(review: ControlPlaneRuntimeAdoptionReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneRuntimeAdoptionReviewError("runtime-adoption review must have state_change none")
    _validate_authority_text(review.authority, "runtime-adoption review")
    if (
        not review.adoption_review_is_not_permission
        or not review.adoption_status_is_not_execution_approval
        or not review.technology_selection_is_not_authority
        or not review.proposal_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeAdoptionReviewError("runtime-adoption review guardrails must remain true")
    if review.proposal_count != len(review.proposal_ids):
        raise ControlPlaneRuntimeAdoptionReviewError("proposal_count must match proposal_ids")
    if review.proposal_thread_count != len(review.proposal_thread_ids):
        raise ControlPlaneRuntimeAdoptionReviewError("proposal_thread_count must match proposal_thread_ids")
    if review.evidence_count != len(review.evidence_ids):
        raise ControlPlaneRuntimeAdoptionReviewError("evidence_count must match evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneRuntimeAdoptionReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneRuntimeAdoptionReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneRuntimeAdoptionReviewError("severity_counts must match findings")
    for field_name, ids in (
        ("active_candidate_ids", review.active_candidate_ids),
        ("non_active_candidate_ids", review.non_active_candidate_ids),
        ("runtime_candidate_ids", review.runtime_candidate_ids),
        ("research_candidate_ids", review.research_candidate_ids),
        ("blocked_proposal_ids", review.blocked_proposal_ids),
    ):
        if any(item not in review.proposal_ids for item in ids):
            raise ControlPlaneRuntimeAdoptionReviewError(f"{field_name} must be a subset of proposal_ids")
    active_ids = set(review.active_candidate_ids)
    non_active_ids = set(review.non_active_candidate_ids)
    if active_ids & non_active_ids:
        raise ControlPlaneRuntimeAdoptionReviewError("active_candidate_ids and non_active_candidate_ids must be disjoint")
    if active_ids | non_active_ids != set(review.proposal_ids):
        raise ControlPlaneRuntimeAdoptionReviewError("active_candidate_ids and non_active_candidate_ids must cover proposal_ids")
    research_ids = set(review.research_candidate_ids)
    runtime_ids = set(review.runtime_candidate_ids)
    if research_ids & runtime_ids:
        raise ControlPlaneRuntimeAdoptionReviewError("research_candidate_ids and runtime_candidate_ids must be disjoint")
    if research_ids | runtime_ids != set(review.proposal_ids):
        raise ControlPlaneRuntimeAdoptionReviewError("research_candidate_ids and runtime_candidate_ids must cover proposal_ids")
    synthetic = tuple(
        ControlPlaneRuntimeAdoptionProposal(
            proposal_id=proposal_id,
            proposal_thread_id=proposal_id,
            revision=1,
            runtime_family="other",
            adoption_stage="runtime_boundary_request" if proposal_id in review.runtime_candidate_ids else "research",
            target_boundary="runtime_core" if proposal_id in review.runtime_candidate_ids else "policy_surface",
            current_status="active_candidate" if proposal_id in review.active_candidate_ids else "draft",
            risk_level="low",
            supersedes_proposal_id="",
            evidence_ids=(),
            depends_on_decision_ids=(),
            referenced_rule_ids=(),
            requires_human_decision=False,
            human_decision_id="",
            requests_runtime_enablement=proposal_id in review.runtime_candidate_ids,
            requests_adapter_import=False,
            requests_io_or_network=False,
            requests_scheduler_authority=False,
            auto_apply=False,
            rollback_plan="",
            observability_plan="",
            security_plan="",
            summary="synthetic validation proposal",
            rationale="synthetic validation proposal",
        )
        for proposal_id in review.proposal_ids
    )
    expected = _review_status(review.findings, synthetic)
    if review.review_status != expected:
        if review.findings or review.review_status not in {
            "runtime_adoption_contract_observed",
            "runtime_adoption_candidate_observed",
            "runtime_adoption_human_review_required",
            "runtime_adoption_blocked",
        }:
            raise ControlPlaneRuntimeAdoptionReviewError(f"review_status must match findings: expected {expected}")


def build_control_plane_runtime_adoption_review(
    proposal_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneRuntimeAdoptionReview:
    """Review caller-supplied runtime adoption proposals without adopting or enabling them."""

    _parse_date(review_as_of, "review_as_of")
    proposals = _proposals_from_payloads(proposal_payloads)
    _validate_decision_review(decision_review)
    _validate_integrity_review(integrity_review)
    _validate_rule_promotion_review(rule_promotion_review)
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        _validate_action_bundle(bundle)
    findings = tuple(
        _thread_findings(proposals)
        + _proposal_findings(proposals)
        + _integration_findings(proposals, decision_review, integrity_review, rule_promotion_review, bundles)
    )
    evidence_ids = tuple(sorted({evidence_id for proposal in proposals for evidence_id in proposal.evidence_ids}))
    referenced_decision_ids = tuple(
        sorted({decision_id for proposal in proposals for decision_id in proposal.depends_on_decision_ids})
    )
    referenced_rule_ids = tuple(sorted({rule_id for proposal in proposals for rule_id in proposal.referenced_rule_ids}))
    blocked_proposal_ids = tuple(sorted({finding.proposal_id for finding in findings if finding.severity in {"critical", "high"}}))
    runtime_candidate_ids = tuple(proposal.proposal_id for proposal in proposals if _is_runtime_candidate(proposal))
    research_candidate_ids = tuple(proposal.proposal_id for proposal in proposals if not _is_runtime_candidate(proposal))
    review = ControlPlaneRuntimeAdoptionReview(
        schema_version="1",
        review_role="reviews_caller_supplied_runtime_adoption_proposals_without_adopting_or_enabling_them",
        review_status=_review_status(findings, proposals),
        review_as_of=review_as_of,
        proposal_count=len(proposals),
        proposal_thread_count=len({proposal.proposal_thread_id for proposal in proposals}),
        proposal_ids=tuple(proposal.proposal_id for proposal in proposals),
        proposal_thread_ids=tuple(sorted({proposal.proposal_thread_id for proposal in proposals})),
        active_candidate_ids=tuple(proposal.proposal_id for proposal in proposals if proposal.current_status == "active_candidate"),
        non_active_candidate_ids=tuple(proposal.proposal_id for proposal in proposals if proposal.current_status != "active_candidate"),
        runtime_candidate_ids=runtime_candidate_ids,
        research_candidate_ids=research_candidate_ids,
        blocked_proposal_ids=blocked_proposal_ids,
        runtime_families=tuple(sorted({proposal.runtime_family for proposal in proposals})),
        target_boundaries=tuple(sorted({proposal.target_boundary for proposal in proposals})),
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        referenced_decision_ids=referenced_decision_ids,
        referenced_rule_ids=referenced_rule_ids,
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_runtime_adoption_review_json(review: ControlPlaneRuntimeAdoptionReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_runtime_adoption_review_markdown(review: ControlPlaneRuntimeAdoptionReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Runtime Adoption Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane runtime adoption review only",
        "- adoption_review_is_not_permission: true",
        "- adoption_status_is_not_execution_approval: true",
        "- technology_selection_is_not_authority: true",
        "- proposal_record_is_not_truth: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- review_as_of: {review.review_as_of}",
        f"- proposal_count: {review.proposal_count}",
        f"- proposal_thread_count: {review.proposal_thread_count}",
        f"- active_candidate_ids: {', '.join(review.active_candidate_ids) if review.active_candidate_ids else 'none'}",
        f"- non_active_candidate_ids: {', '.join(review.non_active_candidate_ids) if review.non_active_candidate_ids else 'none'}",
        f"- runtime_candidate_ids: {', '.join(review.runtime_candidate_ids) if review.runtime_candidate_ids else 'none'}",
        f"- research_candidate_ids: {', '.join(review.research_candidate_ids) if review.research_candidate_ids else 'none'}",
        f"- blocked_proposal_ids: {', '.join(review.blocked_proposal_ids) if review.blocked_proposal_ids else 'none'}",
        f"- runtime_families: {', '.join(review.runtime_families) if review.runtime_families else 'none'}",
        f"- target_boundaries: {', '.join(review.target_boundaries) if review.target_boundaries else 'none'}",
        f"- evidence_ids: {', '.join(review.evidence_ids) if review.evidence_ids else 'none'}",
        f"- referenced_decision_ids: {', '.join(review.referenced_decision_ids) if review.referenced_decision_ids else 'none'}",
        f"- referenced_rule_ids: {', '.join(review.referenced_rule_ids) if review.referenced_rule_ids else 'none'}",
        f"- decision_review_status: {review.decision_review_status}",
        f"- integrity_review_status: {review.integrity_review_status}",
        f"- rule_promotion_review_status: {review.rule_promotion_review_status}",
        f"- action_bundle_count: {review.action_bundle_count}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
        "",
    ]
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(f"- {finding.severity}: {finding.code} [{finding.proposal_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
