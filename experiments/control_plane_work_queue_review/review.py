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


class ControlPlaneWorkQueueReviewError(ValueError):
    """Raised when work-queue review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneWorkQueueCandidate:
    item_id: str
    queue_id: str
    item_thread_id: str
    revision: int
    lifecycle_status: str
    queue_scope: str
    item_kind: str
    priority: str
    status: str
    supersedes_item_id: str
    depends_on_item_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    expected_evidence_kinds: tuple[str, ...]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    owner: str
    acceptance_criteria: tuple[str, ...]
    dependencies_satisfied: bool
    human_decision_required: bool
    approval_id: str
    ready_for_execution: bool
    auto_dispatch: bool
    claims_queue_authority: bool
    claims_scheduler_authority: bool
    claims_priority_truth: bool
    grants_execution_permission: bool
    reads_live_queue: bool
    mutates_state: bool
    registers_queue_reader: bool
    contains_secret_material: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneWorkQueueFinding:
    code: str
    severity: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneWorkQueueReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    item_count: int
    queue_count: int
    item_ids: tuple[str, ...]
    queue_ids: tuple[str, ...]
    item_thread_ids: tuple[str, ...]
    latest_item_ids: tuple[str, ...]
    non_latest_item_ids: tuple[str, ...]
    ready_candidate_ids: tuple[str, ...]
    blocked_item_ids: tuple[str, ...]
    waiting_item_ids: tuple[str, ...]
    archived_item_ids: tuple[str, ...]
    priority_counts: dict[str, int]
    status_counts: dict[str, int]
    referenced_decision_ids: tuple[str, ...]
    referenced_rule_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    decision_review_status: str
    evidence_policy_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneWorkQueueFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane work queue review only"
    work_queue_review_is_not_permission: bool = True
    work_queue_review_is_not_scheduler: bool = True
    queue_item_is_not_execution_approval: bool = True
    queue_priority_is_not_truth: bool = True
    dependency_status_is_not_truth: bool = True
    ready_status_is_not_execution_approval: bool = True
    work_queue_review_is_not_queue_reader: bool = True
    work_queue_review_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_LIFECYCLE_STATUSES = {"draft", "proposed", "ready_candidate", "blocked", "waiting", "superseded", "archived"}
_QUEUE_SCOPES = {"control_plane", "runtime_manager", "target_project", "docs", "qa", "security", "unknown"}
_ITEM_KINDS = {"qa", "implementation", "documentation", "runtime", "target", "security", "observability", "unknown"}
_PRIORITIES = {"P0", "P1", "P2", "P3", "P4", "unknown"}
_ITEM_STATUSES = {"draft", "open", "waiting", "blocked", "ready_candidate", "in_review", "done", "superseded", "archived"}
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
    "queue is truth",
    "queue_is_truth",
    "queue grants permission",
    "queue_grants_permission",
    "queue item approved",
    "queue item grants permission",
    "queue selected next action",
    "queue selected work",
    "queue is scheduler",
    "work queue is scheduler",
    "scheduler selected item",
    "priority is truth",
    "priority_is_truth",
    "p0 grants permission",
    "ready status grants permission",
    "ready status is execution approval",
    "dependencies satisfied is truth",
    "dependency status is truth",
    "owner assignment grants permission",
    "owner is executor",
    "auto dispatch",
    "auto-dispatch",
    "dispatch automatically",
    "queue reader",
    "canonical queue",
    "canonical work queue",
    "canonical qa queue",
    "queue state store",
    "queue store is truth",
    "next action selected",
    "execution approval",
    "permission to execute",
    "runtime authority",
    "source of truth",
)
_NEGATIVE_TEXT_MARKERS = (
    "not truth",
    "is not truth",
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not queue reader",
    "not state store",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not dispatch",
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
        raise ControlPlaneWorkQueueReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneWorkQueueReviewError(f"missing required work-queue field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneWorkQueueReviewError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneWorkQueueReviewError(f"{field} must be a positive integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field, False)
    if not isinstance(value, bool):
        raise ControlPlaneWorkQueueReviewError(f"{field} must be a boolean")
    return value


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneWorkQueueReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item.strip() for item in value):
        raise ControlPlaneWorkQueueReviewError(f"{field} must contain non-empty strings")
    ids = tuple(str(item).strip() for item in value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneWorkQueueReviewError(f"{field} items must be path-segment safe")
    if len(set(ids)) != len(ids):
        raise ControlPlaneWorkQueueReviewError(f"{field} must not contain duplicates")
    return ids


def _as_vocab_tuple(value: object, field: str, vocabulary: set[str]) -> tuple[str, ...]:
    ids = _as_id_tuple(value, field)
    unknown = sorted(item for item in ids if item not in vocabulary)
    if unknown:
        raise ControlPlaneWorkQueueReviewError(f"{field} contains unknown values: {', '.join(unknown)}")
    return ids


def _finding(code: str, severity: str, subject_id: str, detail: str) -> ControlPlaneWorkQueueFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneWorkQueueReviewError(f"unknown severity: {severity}")
    return ControlPlaneWorkQueueFinding(code=code, severity=severity, subject_id=subject_id, detail=detail)


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ").replace("-", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _normalize_candidate(payload: Mapping[str, object]) -> ControlPlaneWorkQueueCandidate:
    item_id = _required_str(payload, "item_id")
    queue_id = _required_str(payload, "queue_id")
    item_thread_id = _required_str(payload, "item_thread_id")
    if not all(_is_path_segment_safe(value) for value in (item_id, queue_id, item_thread_id)):
        raise ControlPlaneWorkQueueReviewError("work queue identifiers must be path-segment safe")
    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneWorkQueueReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    queue_scope = _required_str(payload, "queue_scope")
    if queue_scope not in _QUEUE_SCOPES:
        raise ControlPlaneWorkQueueReviewError(f"unknown queue_scope: {queue_scope}")
    item_kind = _required_str(payload, "item_kind")
    if item_kind not in _ITEM_KINDS:
        raise ControlPlaneWorkQueueReviewError(f"unknown item_kind: {item_kind}")
    priority = _required_str(payload, "priority")
    if priority not in _PRIORITIES:
        raise ControlPlaneWorkQueueReviewError(f"unknown priority: {priority}")
    status = _required_str(payload, "status")
    if status not in _ITEM_STATUSES:
        raise ControlPlaneWorkQueueReviewError(f"unknown item status: {status}")
    owner = _optional_str(payload, "owner")
    if owner and not _is_path_segment_safe(owner):
        raise ControlPlaneWorkQueueReviewError("owner must be path-segment safe")
    approval_id = _optional_str(payload, "approval_id")
    if approval_id and not _is_path_segment_safe(approval_id):
        raise ControlPlaneWorkQueueReviewError("approval_id must be path-segment safe")
    return ControlPlaneWorkQueueCandidate(
        item_id=item_id,
        queue_id=queue_id,
        item_thread_id=item_thread_id,
        revision=_required_int(payload, "revision"),
        lifecycle_status=lifecycle_status,
        queue_scope=queue_scope,
        item_kind=item_kind,
        priority=priority,
        status=status,
        supersedes_item_id=_optional_str(payload, "supersedes_item_id"),
        depends_on_item_ids=_as_id_tuple(payload.get("depends_on_item_ids"), "depends_on_item_ids"),
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence_ids"),
        expected_evidence_kinds=_as_vocab_tuple(payload.get("expected_evidence_kinds"), "expected_evidence_kinds", _EVIDENCE_KINDS),
        referenced_decision_ids=_as_id_tuple(payload.get("referenced_decision_ids"), "referenced_decision_ids"),
        referenced_rule_ids=_as_id_tuple(payload.get("referenced_rule_ids"), "referenced_rule_ids"),
        owner=owner,
        acceptance_criteria=_as_id_tuple(payload.get("acceptance_criteria"), "acceptance_criteria"),
        dependencies_satisfied=_required_bool(payload, "dependencies_satisfied"),
        human_decision_required=_required_bool(payload, "human_decision_required"),
        approval_id=approval_id,
        ready_for_execution=_required_bool(payload, "ready_for_execution"),
        auto_dispatch=_required_bool(payload, "auto_dispatch"),
        claims_queue_authority=_required_bool(payload, "claims_queue_authority"),
        claims_scheduler_authority=_required_bool(payload, "claims_scheduler_authority"),
        claims_priority_truth=_required_bool(payload, "claims_priority_truth"),
        grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
        reads_live_queue=_required_bool(payload, "reads_live_queue"),
        mutates_state=_required_bool(payload, "mutates_state"),
        registers_queue_reader=_required_bool(payload, "registers_queue_reader"),
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _latest_and_non_latest(
    items: tuple[ControlPlaneWorkQueueCandidate, ...],
) -> tuple[tuple[str, ...], tuple[str, ...]]:
    latest_by_thread: dict[str, ControlPlaneWorkQueueCandidate] = {}
    for item in sorted(items, key=lambda value: (value.item_thread_id, value.revision, value.item_id)):
        current = latest_by_thread.get(item.item_thread_id)
        if current is None or item.revision > current.revision:
            latest_by_thread[item.item_thread_id] = item
    latest_ids = tuple(sorted(item.item_id for item in latest_by_thread.values()))
    non_latest_ids = tuple(sorted(item.item_id for item in items if item.item_id not in latest_ids))
    return latest_ids, non_latest_ids


def _check_supplied_review_guardrails(
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle],
) -> tuple[ControlPlaneActionReviewBundle, ...]:
    for name, review in (
        ("decision_review", decision_review),
        ("evidence_policy_review", evidence_policy_review),
        ("integrity_review", integrity_review),
        ("rule_promotion_review", rule_promotion_review),
    ):
        if review is not None and getattr(review, "state_change", "none") != "none":
            raise ControlPlaneWorkQueueReviewError(f"{name} must not mutate state")
        if review is not None and "non-authoritative" not in getattr(review, "authority", ""):
            raise ControlPlaneWorkQueueReviewError(f"{name} must remain non-authoritative")
        if review is not None and not getattr(review, "must_not_execute_automatically", True):
            raise ControlPlaneWorkQueueReviewError(f"{name} must not execute automatically")
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if bundle.state_change != "none" or not bundle.must_not_execute_automatically:
            raise ControlPlaneWorkQueueReviewError("action review bundles must remain advisory")
    return bundles


def _review_items(
    items: tuple[ControlPlaneWorkQueueCandidate, ...],
    *,
    decision_review: ControlPlaneDecisionVersionReview | None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneWorkQueueFinding, ...]:
    findings: list[ControlPlaneWorkQueueFinding] = []
    by_id = {item.item_id: item for item in items}
    by_thread: dict[str, list[ControlPlaneWorkQueueCandidate]] = {}
    for item in items:
        by_thread.setdefault(item.item_thread_id, []).append(item)

    for thread_items in by_thread.values():
        revisions = sorted(item.revision for item in thread_items)
        if len(set(revisions)) != len(revisions):
            duplicated = next(revision for revision in revisions if revisions.count(revision) > 1)
            for item in thread_items:
                if item.revision == duplicated:
                    findings.append(_finding("work_queue_duplicate_thread_revision", "high", item.item_id, str(duplicated)))
        expected = list(range(min(revisions), max(revisions) + 1))
        if revisions and revisions != expected:
            findings.append(_finding("work_queue_revision_gap", "high", thread_items[-1].item_id, "item revisions are not contiguous"))

    latest_ids, _ = _latest_and_non_latest(items)
    ready_ids = [item.item_id for item in items if item.lifecycle_status == "ready_candidate" or item.status == "ready_candidate"]
    if len(ready_ids) > 1:
        for item_id in ready_ids:
            findings.append(_finding("multiple_ready_work_queue_candidates", "high", item_id, "more than one ready candidate observed"))

    for item in items:
        if item.supersedes_item_id:
            if item.supersedes_item_id == item.item_id:
                findings.append(_finding("work_queue_supersedes_self", "high", item.item_id, "item supersedes itself"))
            superseded = by_id.get(item.supersedes_item_id)
            if superseded is None:
                findings.append(_finding("work_queue_supersedes_unknown_id", "high", item.item_id, "superseded item id is unknown"))
            elif superseded.item_thread_id != item.item_thread_id:
                findings.append(_finding("work_queue_supersedes_cross_thread", "high", item.item_id, "item supersedes another thread"))
            elif superseded.revision != item.revision - 1:
                findings.append(_finding("work_queue_supersedes_non_previous_revision", "medium", item.item_id, "item skips supersession chain"))
        elif item.revision > 1:
            findings.append(_finding("work_queue_missing_supersession", "high", item.item_id, "item revision lacks supersedes_item_id"))

        if item.item_id not in latest_ids and (item.lifecycle_status == "ready_candidate" or item.status == "ready_candidate"):
            findings.append(_finding("ready_work_queue_candidate_not_latest", "high", item.item_id, "ready candidate is not latest revision"))
        if item.item_id in item.depends_on_item_ids:
            findings.append(_finding("work_queue_self_dependency", "high", item.item_id, "item depends on itself"))
        unknown_dependencies = sorted(set(item.depends_on_item_ids) - set(by_id))
        for dependency_id in unknown_dependencies:
            findings.append(_finding("work_queue_unknown_dependency", "high", item.item_id, dependency_id))
        blocked_dependencies = sorted(
            dependency_id
            for dependency_id in item.depends_on_item_ids
            if dependency_id in by_id and by_id[dependency_id].status in {"blocked", "waiting"}
        )
        for dependency_id in blocked_dependencies:
            findings.append(_finding("work_queue_depends_on_blocked_item", "high", item.item_id, dependency_id))
        if not item.evidence_ids:
            findings.append(_finding("work_queue_missing_evidence", "high", item.item_id, "work item has no evidence ids"))
        if not item.expected_evidence_kinds:
            findings.append(_finding("work_queue_missing_expected_evidence_kinds", "medium", item.item_id, "expected evidence kinds are empty"))
        if not item.acceptance_criteria:
            findings.append(_finding("work_queue_missing_acceptance_criteria", "high", item.item_id, "acceptance criteria are empty"))
        if not item.owner:
            findings.append(_finding("work_queue_missing_owner", "medium", item.item_id, "owner is empty"))
        if item.priority in {"P0", "P1"} and not item.referenced_decision_ids:
            findings.append(_finding("high_priority_work_queue_item_missing_decision", "high", item.item_id, item.priority))
        if item.ready_for_execution or item.status == "ready_candidate" or item.lifecycle_status == "ready_candidate":
            if not item.dependencies_satisfied:
                findings.append(_finding("ready_work_queue_item_dependencies_unsatisfied", "high", item.item_id, "ready item has unsatisfied dependencies"))
            if item.human_decision_required and not item.approval_id:
                findings.append(_finding("ready_work_queue_item_missing_human_approval", "high", item.item_id, "human approval required"))

        boundary_checks = (
            ("work_queue_item_claims_queue_authority", "critical", item.claims_queue_authority),
            ("work_queue_item_claims_scheduler_authority", "critical", item.claims_scheduler_authority),
            ("work_queue_item_claims_priority_truth", "high", item.claims_priority_truth),
            ("work_queue_item_grants_execution_permission", "critical", item.grants_execution_permission),
            ("work_queue_item_reads_live_queue", "high", item.reads_live_queue),
            ("work_queue_item_mutates_state", "critical", item.mutates_state),
            ("work_queue_item_registers_queue_reader", "high", item.registers_queue_reader),
            ("work_queue_item_auto_dispatch", "critical", item.auto_dispatch),
            ("work_queue_item_contains_secret_material", "high", item.contains_secret_material),
        )
        for code, severity, present in boundary_checks:
            if present:
                findings.append(_finding(code, severity, item.item_id, f"{code} observed in candidate flags"))
        if _has_unqualified_authority_text(item.summary) or _has_unqualified_authority_text(item.rationale):
            findings.append(_finding("work_queue_item_text_launders_authority", "high", item.item_id, "summary or rationale contains authority wording"))

    referenced_decisions = {decision_id for item in items for decision_id in item.referenced_decision_ids}
    if referenced_decisions and decision_review is None:
        for decision_id in sorted(referenced_decisions):
            findings.append(_finding("work_queue_missing_decision_review", "high", decision_id, "decision reference lacks review"))
    elif decision_review is not None:
        current_decisions = set(decision_review.current_decision_ids)
        for decision_id in sorted(referenced_decisions - current_decisions):
            findings.append(_finding("work_queue_references_non_current_decision", "high", decision_id, "decision is not current"))

    referenced_rules = {rule_id for item in items for rule_id in item.referenced_rule_ids}
    if referenced_rules:
        if rule_promotion_review is None:
            for rule_id in sorted(referenced_rules):
                findings.append(_finding("work_queue_missing_rule_promotion_review", "high", rule_id, "rule reference lacks review"))
        else:
            active_rules = set(rule_promotion_review.active_rule_ids)
            for rule_id in sorted(referenced_rules - active_rules):
                findings.append(_finding("work_queue_references_non_active_rule", "high", rule_id, "rule is not active"))

    if integrity_review is None:
        for item in items:
            findings.append(_finding("work_queue_missing_integrity_review", "high", item.item_id, "integrity review is required"))
    elif integrity_review.review_status != "control_plane_integrity_preserved":
        for item in items:
            findings.append(_finding("work_queue_over_integrity_drift", "critical", item.item_id, integrity_review.review_status))

    if evidence_policy_review is None:
        for item in items:
            findings.append(_finding("work_queue_missing_evidence_policy_review", "high", item.item_id, "evidence policy review is required"))
    elif evidence_policy_review.review_status != "evidence_policy_candidate_observed":
        for item in items:
            findings.append(_finding("work_queue_over_evidence_policy_drift", "high", item.item_id, evidence_policy_review.review_status))

    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_ready":
            for item in items:
                findings.append(_finding("work_queue_over_action_review_blocker", "high", item.item_id, bundle.action_posture))

    return tuple(findings)


def build_control_plane_work_queue_review(
    item_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    evidence_policy_review: ControlPlaneEvidencePolicyReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneWorkQueueReview:
    _parse_date(review_as_of, "review_as_of")
    raw_items = tuple(item_payloads)
    if not raw_items:
        raise ControlPlaneWorkQueueReviewError("at least one work-queue candidate is required")
    items = tuple(_normalize_candidate(payload) for payload in raw_items)
    item_ids = [item.item_id for item in items]
    if len(set(item_ids)) != len(item_ids):
        raise ControlPlaneWorkQueueReviewError("duplicate item ids are not allowed")
    bundles = _check_supplied_review_guardrails(
        decision_review=decision_review,
        evidence_policy_review=evidence_policy_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=action_review_bundles,
    )
    findings = _review_items(
        items,
        decision_review=decision_review,
        evidence_policy_review=evidence_policy_review,
        integrity_review=integrity_review,
        rule_promotion_review=rule_promotion_review,
        action_review_bundles=bundles,
    )
    latest_ids, non_latest_ids = _latest_and_non_latest(items)
    high_or_critical = {finding.subject_id for finding in findings if finding.severity in {"critical", "high"}}
    blocked_item_ids = tuple(sorted(item.item_id for item in items if item.item_id in high_or_critical))
    review_status = "work_queue_candidates_observed"
    if any(finding.severity in {"critical", "high"} for finding in findings):
        review_status = "work_queue_review_blocked"
    elif findings:
        review_status = "work_queue_review_attention_required"

    return ControlPlaneWorkQueueReview(
        schema_version="1",
        review_role="reviews_work_queue_candidates_without_scheduler_or_queue_reader_authority",
        review_status=review_status,
        review_as_of=review_as_of,
        item_count=len(items),
        queue_count=len({item.queue_id for item in items}),
        item_ids=tuple(sorted(item_ids)),
        queue_ids=tuple(sorted({item.queue_id for item in items})),
        item_thread_ids=tuple(sorted({item.item_thread_id for item in items})),
        latest_item_ids=latest_ids,
        non_latest_item_ids=non_latest_ids,
        ready_candidate_ids=tuple(
            sorted(item.item_id for item in items if item.lifecycle_status == "ready_candidate" or item.status == "ready_candidate")
        ),
        blocked_item_ids=blocked_item_ids,
        waiting_item_ids=tuple(sorted(item.item_id for item in items if item.status == "waiting" or item.lifecycle_status == "waiting")),
        archived_item_ids=tuple(sorted(item.item_id for item in items if item.status == "archived" or item.lifecycle_status == "archived")),
        priority_counts=_count(item.priority for item in items),
        status_counts=_count(item.status for item in items),
        referenced_decision_ids=tuple(sorted({decision_id for item in items for decision_id in item.referenced_decision_ids})),
        referenced_rule_ids=tuple(sorted({rule_id for item in items for rule_id in item.referenced_rule_ids})),
        evidence_ids=tuple(sorted({evidence_id for item in items for evidence_id in item.evidence_ids})),
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        evidence_policy_review_status=evidence_policy_review.review_status if evidence_policy_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )


def _validate_review(review: ControlPlaneWorkQueueReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneWorkQueueReviewError("work-queue review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneWorkQueueReviewError("work-queue review must remain non-authoritative")
    if (
        not review.work_queue_review_is_not_permission
        or not review.work_queue_review_is_not_scheduler
        or not review.queue_item_is_not_execution_approval
        or not review.queue_priority_is_not_truth
        or not review.dependency_status_is_not_truth
        or not review.ready_status_is_not_execution_approval
        or not review.work_queue_review_is_not_queue_reader
        or not review.work_queue_review_is_not_state_store
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneWorkQueueReviewError("work-queue review guardrails drifted")
    if review.finding_count != len(review.findings):
        raise ControlPlaneWorkQueueReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneWorkQueueReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneWorkQueueReviewError("severity_counts do not match findings")
    if set(review.latest_item_ids) & set(review.non_latest_item_ids):
        raise ControlPlaneWorkQueueReviewError("latest and non-latest item ids must be disjoint")
    if any(not _is_path_segment_safe(item_id) for item_id in review.item_ids):
        raise ControlPlaneWorkQueueReviewError("item ids must be path-segment safe")


def render_control_plane_work_queue_review_json(review: ControlPlaneWorkQueueReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True)


def render_control_plane_work_queue_review_markdown(review: ControlPlaneWorkQueueReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Work Queue Review",
        "",
        f"- review_status: {review.review_status}",
        f"- item_count: {review.item_count}",
        f"- queue_count: {review.queue_count}",
        f"- ready_candidate_ids: {', '.join(review.ready_candidate_ids) if review.ready_candidate_ids else 'none'}",
        f"- blocked_item_ids: {', '.join(review.blocked_item_ids) if review.blocked_item_ids else 'none'}",
        f"- waiting_item_ids: {', '.join(review.waiting_item_ids) if review.waiting_item_ids else 'none'}",
        f"- priority_counts: {review.priority_counts}",
        f"- finding_count: {review.finding_count}",
        "- state_change: none",
        "- work_queue_review_is_not_permission: true",
        "- work_queue_review_is_not_scheduler: true",
        "- queue_item_is_not_execution_approval: true",
        "- queue_priority_is_not_truth: true",
        "- dependency_status_is_not_truth: true",
        "- ready_status_is_not_execution_approval: true",
        "- work_queue_review_is_not_queue_reader: true",
        "- work_queue_review_is_not_state_store: true",
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
