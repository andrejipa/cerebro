from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview


class ControlPlaneRulePromotionReviewError(ValueError):
    """Raised when rule-promotion review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneRulePromotionCandidate:
    rule_id: str
    rule_thread_id: str
    revision: int
    rule_family: str
    current_status: str
    proposed_change: str
    risk_level: str
    supersedes_rule_id: str
    evidence_ids: tuple[str, ...]
    depends_on_decision_ids: tuple[str, ...]
    human_decision_required: bool
    human_decision_id: str
    auto_apply: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneRulePromotionFinding:
    code: str
    severity: str
    rule_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRulePromotionReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    rule_count: int
    rule_thread_count: int
    rule_ids: tuple[str, ...]
    rule_thread_ids: tuple[str, ...]
    active_rule_ids: tuple[str, ...]
    non_active_rule_ids: tuple[str, ...]
    promotion_candidate_ids: tuple[str, ...]
    refresh_candidate_ids: tuple[str, ...]
    blocked_rule_ids: tuple[str, ...]
    evidence_count: int
    evidence_ids: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    decision_review_status: str
    integrity_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneRulePromotionFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane rule promotion review only"
    rule_review_is_not_permission: bool = True
    promotion_candidate_is_not_runtime_authority: bool = True
    rule_record_is_not_truth: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_RULE_FAMILIES = {
    "agent_protocol",
    "boundary_policy",
    "evidence_policy",
    "guardrail",
    "queue_contract",
    "runtime_contract",
    "tool_manifest",
}
_CURRENT_STATUSES = {"active", "draft", "blocked", "obsolete", "conflicting"}
_PROPOSED_CHANGES = {"keep", "refresh", "replace", "retire", "promote_to_runtime", "open_runtime_boundary"}
_RISK_LEVELS = {"critical", "high", "medium", "low"}
_SEVERITIES = {"critical", "high", "medium", "low"}
_PROMOTION_CHANGES = {"promote_to_runtime", "open_runtime_boundary"}
_REFRESH_CHANGES = {"refresh", "replace", "retire"}
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
    "scheduler",
    "schedules work",
    "auto apply",
    "automatically applies",
    "rule is promoted",
    "rule promoted",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not apply",
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
        raise ControlPlaneRulePromotionReviewError(f"missing required rule field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneRulePromotionReviewError(f"{field} must be a string")
    return value.strip()


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneRulePromotionReviewError(f"{field} must be an ISO date") from exc


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneRulePromotionReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneRulePromotionReviewError(f"{field} must contain only non-empty strings")
    ids = tuple(value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneRulePromotionReviewError(f"{field} ids must be path-segment safe")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ControlPlaneRulePromotionReviewError(f"duplicate {field} ids: {', '.join(duplicates)}")
    return ids


def _candidate_from_payload(payload: Mapping[str, object]) -> ControlPlaneRulePromotionCandidate:
    if not isinstance(payload, Mapping):
        raise ControlPlaneRulePromotionReviewError("rule payload must be a mapping")
    rule_id = _required_str(payload, "rule_id")
    if not _is_path_segment_safe(rule_id):
        raise ControlPlaneRulePromotionReviewError("rule_id must be path-segment safe")
    rule_thread_id = _required_str(payload, "rule_thread_id")
    if not _is_path_segment_safe(rule_thread_id):
        raise ControlPlaneRulePromotionReviewError("rule_thread_id must be path-segment safe")
    revision = payload.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ControlPlaneRulePromotionReviewError("revision must be a positive integer")
    rule_family = _required_str(payload, "rule_family")
    if rule_family not in _RULE_FAMILIES:
        raise ControlPlaneRulePromotionReviewError(f"unknown rule_family: {rule_family}")
    current_status = _required_str(payload, "current_status")
    if current_status not in _CURRENT_STATUSES:
        raise ControlPlaneRulePromotionReviewError(f"unknown current_status: {current_status}")
    proposed_change = _required_str(payload, "proposed_change")
    if proposed_change not in _PROPOSED_CHANGES:
        raise ControlPlaneRulePromotionReviewError(f"unknown proposed_change: {proposed_change}")
    risk_level = _required_str(payload, "risk_level")
    if risk_level not in _RISK_LEVELS:
        raise ControlPlaneRulePromotionReviewError(f"unknown risk_level: {risk_level}")
    human_decision_required = payload.get("human_decision_required")
    if not isinstance(human_decision_required, bool):
        raise ControlPlaneRulePromotionReviewError("human_decision_required must be boolean")
    auto_apply = payload.get("auto_apply")
    if not isinstance(auto_apply, bool):
        raise ControlPlaneRulePromotionReviewError("auto_apply must be boolean")
    human_decision_id = _optional_str(payload, "human_decision_id")
    if human_decision_id and not _is_path_segment_safe(human_decision_id):
        raise ControlPlaneRulePromotionReviewError("human_decision_id must be path-segment safe")
    supersedes_rule_id = _optional_str(payload, "supersedes_rule_id")
    if supersedes_rule_id and not _is_path_segment_safe(supersedes_rule_id):
        raise ControlPlaneRulePromotionReviewError("supersedes_rule_id must be path-segment safe")
    return ControlPlaneRulePromotionCandidate(
        rule_id=rule_id,
        rule_thread_id=rule_thread_id,
        revision=revision,
        rule_family=rule_family,
        current_status=current_status,
        proposed_change=proposed_change,
        risk_level=risk_level,
        supersedes_rule_id=supersedes_rule_id,
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence"),
        depends_on_decision_ids=_as_id_tuple(payload.get("depends_on_decision_ids"), "depends_on_decision"),
        human_decision_required=human_decision_required,
        human_decision_id=human_decision_id,
        auto_apply=auto_apply,
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _candidates_from_payloads(payloads: Iterable[Mapping[str, object]]) -> tuple[ControlPlaneRulePromotionCandidate, ...]:
    candidates = tuple(_candidate_from_payload(payload) for payload in payloads)
    ids = [candidate.rule_id for candidate in candidates]
    duplicates = sorted({rule_id for rule_id in ids if ids.count(rule_id) > 1})
    if duplicates:
        raise ControlPlaneRulePromotionReviewError(f"duplicate rule ids: {', '.join(duplicates)}")
    thread_revisions = [(candidate.rule_thread_id, candidate.revision) for candidate in candidates]
    duplicate_revisions = sorted({item for item in thread_revisions if thread_revisions.count(item) > 1})
    if duplicate_revisions:
        formatted = ", ".join(f"{thread}:{revision}" for thread, revision in duplicate_revisions)
        raise ControlPlaneRulePromotionReviewError(f"duplicate rule thread revisions: {formatted}")
    return candidates


def _finding(code: str, severity: str, rule_id: str, detail: str) -> ControlPlaneRulePromotionFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneRulePromotionReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneRulePromotionFinding(code=code, severity=severity, rule_id=rule_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneRulePromotionReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneRulePromotionReviewError(f"{label} authority contains forbidden claim: {token}")


def _validate_decision_review(review: ControlPlaneDecisionVersionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRulePromotionReviewError("decision-version review must have state_change none")
    _validate_authority_text(review.authority, "decision-version review")
    if (
        not review.decision_review_is_not_permission
        or not review.decision_current_is_not_execution_approval
        or not review.decision_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRulePromotionReviewError("decision-version review guardrails must remain true")


def _validate_integrity_review(review: ControlPlaneIntegrityReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRulePromotionReviewError("integrity review must have state_change none")
    _validate_authority_text(review.authority, "integrity review")
    if (
        not review.review_is_not_permission
        or not review.integrity_pass_is_not_truth
        or not review.finding_is_not_execution_approval
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRulePromotionReviewError("integrity review guardrails must remain true")


def _validate_action_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneRulePromotionReviewError("action-review bundle must have state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneRulePromotionReviewError("action-review bundle guardrails must remain true")


def _thread_findings(candidates: tuple[ControlPlaneRulePromotionCandidate, ...]) -> list[ControlPlaneRulePromotionFinding]:
    findings: list[ControlPlaneRulePromotionFinding] = []
    by_id = {candidate.rule_id: candidate for candidate in candidates}
    by_thread: dict[str, list[ControlPlaneRulePromotionCandidate]] = {}
    for candidate in candidates:
        by_thread.setdefault(candidate.rule_thread_id, []).append(candidate)
        if candidate.supersedes_rule_id == candidate.rule_id:
            findings.append(
                _finding(
                    "rule_supersedes_self",
                    "high",
                    candidate.rule_id,
                    "rule candidate cannot supersede itself",
                )
            )
        if candidate.revision > 1 and not candidate.supersedes_rule_id:
            findings.append(
                _finding(
                    "rule_revision_missing_supersedes",
                    "medium",
                    candidate.rule_id,
                    "rule revision greater than 1 does not declare supersedes_rule_id",
                )
            )
        if candidate.supersedes_rule_id and candidate.supersedes_rule_id not in by_id:
            findings.append(
                _finding(
                    "rule_supersedes_unknown_id",
                    "high",
                    candidate.rule_id,
                    f"supersedes_rule_id is unknown: {candidate.supersedes_rule_id}",
                )
            )

    for thread_id, thread_candidates in by_thread.items():
        revisions = sorted(candidate.revision for candidate in thread_candidates)
        expected = list(range(1, max(revisions) + 1)) if revisions else []
        if revisions != expected:
            missing = sorted(set(expected) - set(revisions))
            findings.append(
                _finding(
                    "rule_revision_gap",
                    "high",
                    thread_candidates[-1].rule_id,
                    f"rule thread {thread_id} has missing revisions: {', '.join(str(item) for item in missing)}",
                )
            )
        active_candidates = [candidate for candidate in thread_candidates if candidate.current_status == "active"]
        if len(active_candidates) > 1:
            findings.append(
                _finding(
                    "multiple_active_rules_in_thread",
                    "high",
                    active_candidates[-1].rule_id,
                    f"rule thread {thread_id} has multiple active rule versions",
                )
            )
        latest_revision = max(revisions)
        for candidate in active_candidates:
            if candidate.revision != latest_revision:
                findings.append(
                    _finding(
                        "active_rule_not_latest_revision",
                        "high",
                        candidate.rule_id,
                        f"active rule revision {candidate.revision} is not latest revision {latest_revision}",
                    )
                )
        for candidate in thread_candidates:
            if candidate.proposed_change in _PROMOTION_CHANGES | _REFRESH_CHANGES and candidate.revision != latest_revision:
                findings.append(
                    _finding(
                        "rule_change_over_stale_candidate",
                        "high",
                        candidate.rule_id,
                        f"rule change targets revision {candidate.revision}, not latest revision {latest_revision}",
                    )
                )

    for candidate in candidates:
        superseded = by_id.get(candidate.supersedes_rule_id)
        if superseded is not None and superseded.rule_thread_id != candidate.rule_thread_id:
            findings.append(
                _finding(
                    "rule_supersedes_cross_thread",
                    "high",
                    candidate.rule_id,
                    f"candidate supersedes {superseded.rule_id} from thread {superseded.rule_thread_id}",
                )
            )
        if (
            superseded is not None
            and superseded.rule_thread_id == candidate.rule_thread_id
            and superseded.revision != candidate.revision - 1
        ):
            findings.append(
                _finding(
                    "rule_supersedes_non_previous_revision",
                    "high",
                    candidate.rule_id,
                    f"candidate revision {candidate.revision} supersedes revision {superseded.revision}",
                )
            )
    return findings


def _candidate_findings(candidates: tuple[ControlPlaneRulePromotionCandidate, ...]) -> list[ControlPlaneRulePromotionFinding]:
    findings: list[ControlPlaneRulePromotionFinding] = []
    for candidate in candidates:
        if candidate.auto_apply:
            findings.append(
                _finding(
                    "rule_candidate_requests_auto_apply",
                    "high",
                    candidate.rule_id,
                    "rule candidate requested automatic application",
                )
            )
        if candidate.proposed_change in _PROMOTION_CHANGES and not candidate.human_decision_required:
            findings.append(
                _finding(
                    "runtime_promotion_without_human_decision_requirement",
                    "high",
                    candidate.rule_id,
                    "runtime-boundary promotion candidates must require an explicit human decision",
                )
            )
        if candidate.proposed_change in _PROMOTION_CHANGES and candidate.human_decision_id.strip().lower() in {"", "none", "auto", "automatic"}:
            findings.append(
                _finding(
                    "runtime_promotion_missing_human_decision_id",
                    "high",
                    candidate.rule_id,
                    "runtime-boundary promotion candidate lacks human_decision_id",
                )
            )
        if candidate.proposed_change in _REFRESH_CHANGES and not candidate.evidence_ids:
            findings.append(
                _finding(
                    "rule_refresh_missing_evidence",
                    "medium",
                    candidate.rule_id,
                    f"{candidate.proposed_change} candidate has no evidence ids",
                )
            )
        if candidate.current_status == "conflicting" and not candidate.human_decision_required:
            findings.append(
                _finding(
                    "conflicting_rule_without_human_decision_requirement",
                    "medium",
                    candidate.rule_id,
                    "conflicting rule candidate must require human review",
                )
            )
        if candidate.current_status == "blocked" and candidate.proposed_change in {"keep", "promote_to_runtime", "open_runtime_boundary"}:
            findings.append(
                _finding(
                    "blocked_rule_promoted_or_kept",
                    "high",
                    candidate.rule_id,
                    f"blocked rule cannot be treated as {candidate.proposed_change}",
                )
            )
        if candidate.risk_level in {"critical", "high"} and not candidate.evidence_ids:
            findings.append(
                _finding(
                    "high_risk_rule_missing_evidence",
                    "high",
                    candidate.rule_id,
                    "high-risk rule candidate lacks evidence ids",
                )
            )
        for field_name, text in (("summary", candidate.summary), ("rationale", candidate.rationale)):
            lowered = text.lower()
            has_negative_marker = any(marker in lowered for marker in _NEGATIVE_TEXT_MARKERS)
            for token in _FORBIDDEN_AUTHORITY_TOKENS:
                if token in lowered and not has_negative_marker:
                    findings.append(
                        _finding(
                            "rule_text_launders_authority",
                            "high",
                            candidate.rule_id,
                            f"{field_name} contains forbidden rule-promotion wording: {token}",
                        )
                    )
    return findings


def _integration_findings(
    candidates: tuple[ControlPlaneRulePromotionCandidate, ...],
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    action_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> list[ControlPlaneRulePromotionFinding]:
    findings: list[ControlPlaneRulePromotionFinding] = []
    current_decisions = set(decision_review.current_decision_ids) if decision_review is not None else set()
    all_decisions = set(decision_review.decision_ids) if decision_review is not None else set()

    for candidate in candidates:
        if candidate.proposed_change in _PROMOTION_CHANGES and decision_review is None:
            findings.append(
                _finding(
                    "runtime_promotion_missing_decision_review",
                    "high",
                    candidate.rule_id,
                    "runtime-boundary promotion candidate has no supplied decision-version review",
                )
            )
        if decision_review is not None:
            for decision_id in candidate.depends_on_decision_ids:
                if decision_id not in all_decisions:
                    findings.append(
                        _finding(
                            "rule_references_unknown_decision",
                            "high",
                            candidate.rule_id,
                            f"candidate references unknown decision id: {decision_id}",
                        )
                    )
                elif decision_id not in current_decisions:
                    findings.append(
                        _finding(
                            "rule_references_non_current_decision",
                            "high",
                            candidate.rule_id,
                            f"candidate references non-current decision id: {decision_id}",
                        )
                    )
            if candidate.proposed_change in _PROMOTION_CHANGES:
                if not any(decision_id in current_decisions for decision_id in candidate.depends_on_decision_ids):
                    findings.append(
                        _finding(
                            "runtime_promotion_missing_current_decision_reference",
                            "high",
                            candidate.rule_id,
                            "runtime-boundary promotion candidate does not reference a current decision id",
                        )
                    )
                if decision_review.review_status != "decision_version_contract_observed":
                    findings.append(
                        _finding(
                            "runtime_promotion_over_decision_drift",
                            "critical",
                            candidate.rule_id,
                            f"decision-version review status is {decision_review.review_status}",
                        )
                    )

        if integrity_review is None and candidate.proposed_change in _PROMOTION_CHANGES:
            findings.append(
                _finding(
                    "runtime_promotion_missing_integrity_review",
                    "high",
                    candidate.rule_id,
                    "runtime-boundary promotion candidate has no supplied integrity review",
                )
            )
        if integrity_review is not None and integrity_review.review_status != "control_plane_integrity_preserved":
            if candidate.proposed_change in _PROMOTION_CHANGES:
                findings.append(
                    _finding(
                        "runtime_promotion_over_integrity_drift",
                        "critical",
                        candidate.rule_id,
                        f"integrity review status is {integrity_review.review_status}",
                    )
                )
            elif candidate.proposed_change in _REFRESH_CHANGES:
                findings.append(
                    _finding(
                        "rule_refresh_over_integrity_drift",
                        "high",
                        candidate.rule_id,
                        f"integrity review status is {integrity_review.review_status}",
                    )
                )

        for bundle in action_bundles:
            if bundle.action_posture not in {"advisory_review_only", "human_review_required"}:
                findings.append(
                    _finding(
                        "rule_change_over_blocked_action_posture",
                        "high",
                        candidate.rule_id,
                        f"action bundle {bundle.observation.observation_id} posture is {bundle.action_posture}",
                    )
                )
            if candidate.proposed_change in _PROMOTION_CHANGES and bundle.recommended_human_decision != "none":
                findings.append(
                    _finding(
                        "runtime_promotion_over_unresolved_action_decision",
                        "high",
                        candidate.rule_id,
                        f"action bundle requires {bundle.recommended_human_decision}",
                    )
                )
    return findings


def _review_status(
    findings: tuple[ControlPlaneRulePromotionFinding, ...],
    candidates: tuple[ControlPlaneRulePromotionCandidate, ...],
) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "rule_promotion_blocked"
    if findings:
        return "rule_promotion_human_review_required"
    if any(candidate.proposed_change in _PROMOTION_CHANGES for candidate in candidates):
        return "rule_promotion_candidate_observed"
    if any(candidate.proposed_change in _REFRESH_CHANGES for candidate in candidates):
        return "rule_refresh_candidate_observed"
    return "rule_contract_observed"


def _validate_review(review: ControlPlaneRulePromotionReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneRulePromotionReviewError("rule-promotion review must have state_change none")
    _validate_authority_text(review.authority, "rule-promotion review")
    if (
        not review.rule_review_is_not_permission
        or not review.promotion_candidate_is_not_runtime_authority
        or not review.rule_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRulePromotionReviewError("rule-promotion review guardrails must remain true")
    if review.rule_count != len(review.rule_ids):
        raise ControlPlaneRulePromotionReviewError("rule_count must match rule_ids")
    if review.rule_thread_count != len(review.rule_thread_ids):
        raise ControlPlaneRulePromotionReviewError("rule_thread_count must match rule_thread_ids")
    if review.evidence_count != len(review.evidence_ids):
        raise ControlPlaneRulePromotionReviewError("evidence_count must match evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneRulePromotionReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneRulePromotionReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneRulePromotionReviewError("severity_counts must match findings")
    if any(item not in review.rule_ids for item in review.promotion_candidate_ids):
        raise ControlPlaneRulePromotionReviewError("promotion_candidate_ids must be a subset of rule_ids")
    if any(item not in review.rule_ids for item in review.refresh_candidate_ids):
        raise ControlPlaneRulePromotionReviewError("refresh_candidate_ids must be a subset of rule_ids")
    if any(item not in review.rule_ids for item in review.blocked_rule_ids):
        raise ControlPlaneRulePromotionReviewError("blocked_rule_ids must be a subset of rule_ids")
    if any(item not in review.rule_ids for item in review.active_rule_ids):
        raise ControlPlaneRulePromotionReviewError("active_rule_ids must be a subset of rule_ids")
    if any(item not in review.rule_ids for item in review.non_active_rule_ids):
        raise ControlPlaneRulePromotionReviewError("non_active_rule_ids must be a subset of rule_ids")
    active_ids = set(review.active_rule_ids)
    non_active_ids = set(review.non_active_rule_ids)
    if active_ids & non_active_ids:
        raise ControlPlaneRulePromotionReviewError("active_rule_ids and non_active_rule_ids must be disjoint")
    if active_ids | non_active_ids != set(review.rule_ids):
        raise ControlPlaneRulePromotionReviewError("active_rule_ids and non_active_rule_ids must cover rule_ids")
    synthetic_candidates = tuple(
        ControlPlaneRulePromotionCandidate(
            rule_id=rule_id,
            rule_thread_id=rule_id,
            revision=1,
            rule_family="guardrail",
            current_status="active",
            proposed_change="promote_to_runtime" if rule_id in review.promotion_candidate_ids else "refresh",
            risk_level="low",
            supersedes_rule_id="",
            evidence_ids=(),
            depends_on_decision_ids=(),
            human_decision_required=True,
            human_decision_id="synthetic",
            auto_apply=False,
            summary="synthetic validation candidate",
            rationale="synthetic validation candidate",
        )
        for rule_id in review.rule_ids
    )
    if review.review_status != _review_status(review.findings, synthetic_candidates):
        expected = _review_status(review.findings, synthetic_candidates)
        if review.findings or review.review_status not in {
            "rule_promotion_candidate_observed",
            "rule_refresh_candidate_observed",
            "rule_contract_observed",
        }:
            raise ControlPlaneRulePromotionReviewError(f"review_status must match findings: expected {expected}")


def build_control_plane_rule_promotion_review(
    rule_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneRulePromotionReview:
    """Review caller-supplied rule-change candidates without promoting or applying them."""

    _parse_date(review_as_of, "review_as_of")
    candidates = _candidates_from_payloads(rule_payloads)
    _validate_decision_review(decision_review)
    _validate_integrity_review(integrity_review)
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        _validate_action_bundle(bundle)
    findings = tuple(
        _thread_findings(candidates)
        + _candidate_findings(candidates)
        + _integration_findings(candidates, decision_review, integrity_review, bundles)
    )
    evidence_ids = tuple(sorted({evidence_id for candidate in candidates for evidence_id in candidate.evidence_ids}))
    referenced_decision_ids = tuple(
        sorted({decision_id for candidate in candidates for decision_id in candidate.depends_on_decision_ids})
    )
    blocked_rule_ids = tuple(sorted({finding.rule_id for finding in findings if finding.severity in {"critical", "high"}}))
    review = ControlPlaneRulePromotionReview(
        schema_version="1",
        review_role="reviews_caller_supplied_rule_change_candidates_without_promoting_or_applying_them",
        review_status=_review_status(findings, candidates),
        review_as_of=review_as_of,
        rule_count=len(candidates),
        rule_thread_count=len({candidate.rule_thread_id for candidate in candidates}),
        rule_ids=tuple(candidate.rule_id for candidate in candidates),
        rule_thread_ids=tuple(sorted({candidate.rule_thread_id for candidate in candidates})),
        active_rule_ids=tuple(candidate.rule_id for candidate in candidates if candidate.current_status == "active"),
        non_active_rule_ids=tuple(candidate.rule_id for candidate in candidates if candidate.current_status != "active"),
        promotion_candidate_ids=tuple(candidate.rule_id for candidate in candidates if candidate.proposed_change in _PROMOTION_CHANGES),
        refresh_candidate_ids=tuple(candidate.rule_id for candidate in candidates if candidate.proposed_change in _REFRESH_CHANGES),
        blocked_rule_ids=blocked_rule_ids,
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        referenced_decision_ids=referenced_decision_ids,
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_rule_promotion_review_json(review: ControlPlaneRulePromotionReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_rule_promotion_review_markdown(review: ControlPlaneRulePromotionReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Rule Promotion Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane rule promotion review only",
        "- rule_review_is_not_permission: true",
        "- promotion_candidate_is_not_runtime_authority: true",
        "- rule_record_is_not_truth: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- review_as_of: {review.review_as_of}",
        f"- rule_count: {review.rule_count}",
        f"- rule_thread_count: {review.rule_thread_count}",
        f"- active_rule_ids: {', '.join(review.active_rule_ids) if review.active_rule_ids else 'none'}",
        f"- non_active_rule_ids: {', '.join(review.non_active_rule_ids) if review.non_active_rule_ids else 'none'}",
        f"- promotion_candidate_ids: {', '.join(review.promotion_candidate_ids) if review.promotion_candidate_ids else 'none'}",
        f"- refresh_candidate_ids: {', '.join(review.refresh_candidate_ids) if review.refresh_candidate_ids else 'none'}",
        f"- blocked_rule_ids: {', '.join(review.blocked_rule_ids) if review.blocked_rule_ids else 'none'}",
        f"- evidence_ids: {', '.join(review.evidence_ids) if review.evidence_ids else 'none'}",
        f"- referenced_decision_ids: {', '.join(review.referenced_decision_ids) if review.referenced_decision_ids else 'none'}",
        f"- decision_review_status: {review.decision_review_status}",
        f"- integrity_review_status: {review.integrity_review_status}",
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
            lines.append(f"- {finding.severity}: {finding.code} [{finding.rule_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
