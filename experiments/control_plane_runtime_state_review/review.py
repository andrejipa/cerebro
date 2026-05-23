from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_decision_version_review import ControlPlaneDecisionVersionReview
from experiments.control_plane_integrity_review import ControlPlaneIntegrityReview
from experiments.control_plane_observation_set_review import ControlPlaneObservationSetReview
from experiments.control_plane_rule_promotion_review import ControlPlaneRulePromotionReview
from experiments.control_plane_runtime_adoption_review import ControlPlaneRuntimeAdoptionReview


class ControlPlaneRuntimeStateReviewError(ValueError):
    """Raised when runtime-state review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneRuntimeStateSnapshot:
    snapshot_id: str
    snapshot_thread_id: str
    revision: int
    captured_at: str
    state_scope: str
    lifecycle_status: str
    queue_authority: str
    schema_version_claim: str
    active_observation_ids: tuple[str, ...]
    open_ready_observation_ids: tuple[str, ...]
    blocked_observation_ids: tuple[str, ...]
    current_decision_ids: tuple[str, ...]
    active_rule_ids: tuple[str, ...]
    runtime_adoption_candidate_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    supersedes_snapshot_id: str
    contains_secret_material: bool
    contains_raw_evidence: bool
    claims_canonical_state: bool
    claims_scheduler_authority: bool
    claims_execution_permission: bool
    auto_apply: bool
    generated_by: str
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneRuntimeStateFinding:
    code: str
    severity: str
    snapshot_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRuntimeStateReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    snapshot_count: int
    snapshot_thread_count: int
    snapshot_ids: tuple[str, ...]
    snapshot_thread_ids: tuple[str, ...]
    latest_snapshot_ids: tuple[str, ...]
    non_latest_snapshot_ids: tuple[str, ...]
    blocked_snapshot_ids: tuple[str, ...]
    observed_state_scopes: tuple[str, ...]
    lifecycle_statuses: tuple[str, ...]
    evidence_count: int
    evidence_ids: tuple[str, ...]
    active_observation_ids: tuple[str, ...]
    open_ready_observation_ids: tuple[str, ...]
    current_decision_ids: tuple[str, ...]
    active_rule_ids: tuple[str, ...]
    runtime_adoption_candidate_ids: tuple[str, ...]
    observation_set_review_status: str
    decision_review_status: str
    integrity_review_status: str
    rule_promotion_review_status: str
    runtime_adoption_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneRuntimeStateFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane runtime state review only"
    state_review_is_not_permission: bool = True
    snapshot_is_not_canonical_state: bool = True
    observed_state_is_not_scheduler: bool = True
    state_status_is_not_execution_approval: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_STATE_SCOPES = {"control_plane", "cerebro_runtime", "target_project", "cross_project", "unknown"}
_LIFECYCLE_STATUSES = {"draft", "observed", "stale", "blocked", "archived"}
_QUEUE_AUTHORITIES = {"machine-primary", "not_supplied", "unknown"}
_SEVERITIES = {"critical", "high", "medium", "low"}
_STATE_ROOT_KEYS = {"version", "revision", "sources", "checkpoint", "last_validation", "agent_runtime"}
_AGENT_RUNTIME_KEYS = {
    "plan",
    "execution_policy",
    "command_registry",
    "approvals",
    "actions",
    "batch_registry",
    "verification",
    "memory",
    "audit",
}
_PLAN_STATUSES = {"idle", "ready", "blocked", "running", "completed"}
_TASK_STATUSES = {"ready", "blocked", "running", "done", "failed"}
_ACTION_STATUSES = {"planned", "pending_approval", "applied", "rolled_back", "blocked", "failed"}
_APPROVAL_STATUSES = {"pending", "approved", "rejected"}
_VERIFICATION_STATUSES = {"idle", "passed", "failed"}
_TRACE_STATUSES = {"healthy", "degraded"}
_TRACE_INTEGRITIES = {"reliable", "partial"}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "canonical state",
    "canonical_state",
    "state is truth",
    "state_is_truth",
    "runtime state is truth",
    "state store is truth",
    "snapshot is truth",
    "snapshot selected next action",
    "selected next action",
    "next action selected",
    "scheduler",
    "schedules work",
    "execution approval",
    "execution approved",
    "approved to run",
    "grants permission",
    "permission to execute",
    "permission_granted",
    "runtime authority",
    "runtime_authority",
    "canonical gate",
    "canonical_truth",
    "truth signal",
    "auto apply",
    "automatically applies",
    "auto_continue",
    "auto_continuation",
)


def _as_mapping(value: object, label: str) -> Mapping[str, object]:
    if not isinstance(value, Mapping):
        raise ControlPlaneRuntimeStateReviewError(f"{label} must be a mapping")
    return value


def _as_list(value: object, label: str) -> list[object]:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ControlPlaneRuntimeStateReviewError(f"{label} must be a list")
    return value


def _mapping_list(value: object, label: str) -> list[Mapping[str, object]]:
    items = _as_list(value, label)
    mapped: list[Mapping[str, object]] = []
    for item in items:
        if isinstance(item, Mapping):
            mapped.append(item)
    return mapped


def _string_ids(items: Iterable[Mapping[str, object]], field: str) -> tuple[str, ...]:
    ids: list[str] = []
    for item in items:
        raw_id = item.get(field, "")
        if isinstance(raw_id, str) and raw_id:
            ids.append(raw_id)
    return tuple(ids)
_NEGATIVE_TEXT_MARKERS = (
    "not canonical",
    "not truth",
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not authority",
    "non-authoritative",
    "must not execute",
    "does not grant",
    "does not select",
    "does not apply",
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
        raise ControlPlaneRuntimeStateReviewError(f"missing required runtime-state field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneRuntimeStateReviewError(f"{field} must be a string")
    return value.strip()


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneRuntimeStateReviewError(f"{field} must be an ISO date") from exc


def _as_id_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneRuntimeStateReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneRuntimeStateReviewError(f"{field} must contain only non-empty strings")
    ids = tuple(value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneRuntimeStateReviewError(f"{field} ids must be path-segment safe")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ControlPlaneRuntimeStateReviewError(f"duplicate {field} ids: {', '.join(duplicates)}")
    return ids


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ControlPlaneRuntimeStateReviewError(f"{field} must be boolean")
    return value


def _snapshot_from_payload(payload: Mapping[str, object]) -> ControlPlaneRuntimeStateSnapshot:
    if not isinstance(payload, Mapping):
        raise ControlPlaneRuntimeStateReviewError("runtime-state payload must be a mapping")
    snapshot_id = _required_str(payload, "snapshot_id")
    if not _is_path_segment_safe(snapshot_id):
        raise ControlPlaneRuntimeStateReviewError("snapshot_id must be path-segment safe")
    snapshot_thread_id = _required_str(payload, "snapshot_thread_id")
    if not _is_path_segment_safe(snapshot_thread_id):
        raise ControlPlaneRuntimeStateReviewError("snapshot_thread_id must be path-segment safe")
    revision = payload.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ControlPlaneRuntimeStateReviewError("revision must be a positive integer")
    captured_at = _required_str(payload, "captured_at")
    _parse_date(captured_at, "captured_at")
    state_scope = _required_str(payload, "state_scope")
    if state_scope not in _STATE_SCOPES:
        raise ControlPlaneRuntimeStateReviewError(f"unknown state_scope: {state_scope}")
    lifecycle_status = _required_str(payload, "lifecycle_status")
    if lifecycle_status not in _LIFECYCLE_STATUSES:
        raise ControlPlaneRuntimeStateReviewError(f"unknown lifecycle_status: {lifecycle_status}")
    queue_authority = _required_str(payload, "queue_authority")
    if queue_authority not in _QUEUE_AUTHORITIES:
        raise ControlPlaneRuntimeStateReviewError(f"unknown queue_authority: {queue_authority}")
    supersedes_snapshot_id = _optional_str(payload, "supersedes_snapshot_id")
    if supersedes_snapshot_id and not _is_path_segment_safe(supersedes_snapshot_id):
        raise ControlPlaneRuntimeStateReviewError("supersedes_snapshot_id must be path-segment safe")
    return ControlPlaneRuntimeStateSnapshot(
        snapshot_id=snapshot_id,
        snapshot_thread_id=snapshot_thread_id,
        revision=revision,
        captured_at=captured_at,
        state_scope=state_scope,
        lifecycle_status=lifecycle_status,
        queue_authority=queue_authority,
        schema_version_claim=_required_str(payload, "schema_version_claim"),
        active_observation_ids=_as_id_tuple(payload.get("active_observation_ids"), "active_observation"),
        open_ready_observation_ids=_as_id_tuple(payload.get("open_ready_observation_ids"), "open_ready_observation"),
        blocked_observation_ids=_as_id_tuple(payload.get("blocked_observation_ids"), "blocked_observation"),
        current_decision_ids=_as_id_tuple(payload.get("current_decision_ids"), "current_decision"),
        active_rule_ids=_as_id_tuple(payload.get("active_rule_ids"), "active_rule"),
        runtime_adoption_candidate_ids=_as_id_tuple(
            payload.get("runtime_adoption_candidate_ids"),
            "runtime_adoption_candidate",
        ),
        evidence_ids=_as_id_tuple(payload.get("evidence_ids"), "evidence"),
        supersedes_snapshot_id=supersedes_snapshot_id,
        contains_secret_material=_required_bool(payload, "contains_secret_material"),
        contains_raw_evidence=_required_bool(payload, "contains_raw_evidence"),
        claims_canonical_state=_required_bool(payload, "claims_canonical_state"),
        claims_scheduler_authority=_required_bool(payload, "claims_scheduler_authority"),
        claims_execution_permission=_required_bool(payload, "claims_execution_permission"),
        auto_apply=_required_bool(payload, "auto_apply"),
        generated_by=_required_str(payload, "generated_by"),
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _snapshots_from_payloads(payloads: Iterable[Mapping[str, object]]) -> tuple[ControlPlaneRuntimeStateSnapshot, ...]:
    snapshots = tuple(_snapshot_from_payload(payload) for payload in payloads)
    ids = [snapshot.snapshot_id for snapshot in snapshots]
    duplicates = sorted({snapshot_id for snapshot_id in ids if ids.count(snapshot_id) > 1})
    if duplicates:
        raise ControlPlaneRuntimeStateReviewError(f"duplicate snapshot ids: {', '.join(duplicates)}")
    thread_revisions = [(snapshot.snapshot_thread_id, snapshot.revision) for snapshot in snapshots]
    duplicate_revisions = sorted({item for item in thread_revisions if thread_revisions.count(item) > 1})
    if duplicate_revisions:
        formatted = ", ".join(f"{thread}:{revision}" for thread, revision in duplicate_revisions)
        raise ControlPlaneRuntimeStateReviewError(f"duplicate snapshot thread revisions: {formatted}")
    return snapshots


def _finding(code: str, severity: str, snapshot_id: str, detail: str) -> ControlPlaneRuntimeStateFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneRuntimeStateReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneRuntimeStateFinding(code=code, severity=severity, snapshot_id=snapshot_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneRuntimeStateReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneRuntimeStateReviewError(f"{label} authority contains forbidden claim: {token}")


def _validate_observation_set_review(review: ControlPlaneObservationSetReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("observation-set review must have state_change none")
    _validate_authority_text(review.authority, "observation-set review")
    if (
        not review.review_is_not_permission
        or not review.observation_frontier_is_not_scheduler
        or not review.advisory_posture_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("observation-set review guardrails must remain true")


def _validate_decision_review(review: ControlPlaneDecisionVersionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("decision-version review must have state_change none")
    _validate_authority_text(review.authority, "decision-version review")
    if (
        not review.decision_review_is_not_permission
        or not review.decision_current_is_not_execution_approval
        or not review.decision_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("decision-version review guardrails must remain true")


def _validate_integrity_review(review: ControlPlaneIntegrityReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("integrity review must have state_change none")
    _validate_authority_text(review.authority, "integrity review")
    if (
        not review.review_is_not_permission
        or not review.integrity_pass_is_not_truth
        or not review.finding_is_not_execution_approval
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("integrity review guardrails must remain true")


def _validate_rule_promotion_review(review: ControlPlaneRulePromotionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("rule-promotion review must have state_change none")
    _validate_authority_text(review.authority, "rule-promotion review")
    if (
        not review.rule_review_is_not_permission
        or not review.promotion_candidate_is_not_runtime_authority
        or not review.rule_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("rule-promotion review guardrails must remain true")


def _validate_runtime_adoption_review(review: ControlPlaneRuntimeAdoptionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("runtime-adoption review must have state_change none")
    _validate_authority_text(review.authority, "runtime-adoption review")
    if (
        not review.adoption_review_is_not_permission
        or not review.adoption_status_is_not_execution_approval
        or not review.technology_selection_is_not_authority
        or not review.proposal_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("runtime-adoption review guardrails must remain true")


def _validate_action_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("action-review bundle must have state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("action-review bundle guardrails must remain true")


def _thread_findings(snapshots: tuple[ControlPlaneRuntimeStateSnapshot, ...]) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    by_id = {snapshot.snapshot_id: snapshot for snapshot in snapshots}
    by_thread: dict[str, list[ControlPlaneRuntimeStateSnapshot]] = {}
    for snapshot in snapshots:
        by_thread.setdefault(snapshot.snapshot_thread_id, []).append(snapshot)
        if snapshot.supersedes_snapshot_id == snapshot.snapshot_id:
            findings.append(
                _finding("snapshot_supersedes_self", "high", snapshot.snapshot_id, "snapshot cannot supersede itself")
            )
        if snapshot.revision > 1 and not snapshot.supersedes_snapshot_id:
            findings.append(
                _finding(
                    "snapshot_revision_missing_supersedes",
                    "medium",
                    snapshot.snapshot_id,
                    "snapshot revision greater than 1 does not declare supersedes_snapshot_id",
                )
            )
        if snapshot.supersedes_snapshot_id and snapshot.supersedes_snapshot_id not in by_id:
            findings.append(
                _finding(
                    "snapshot_supersedes_unknown_id",
                    "high",
                    snapshot.snapshot_id,
                    f"supersedes_snapshot_id is unknown: {snapshot.supersedes_snapshot_id}",
                )
            )

    for thread_id, thread_snapshots in by_thread.items():
        revisions = sorted(snapshot.revision for snapshot in thread_snapshots)
        expected = list(range(1, max(revisions) + 1)) if revisions else []
        if revisions != expected:
            missing = sorted(set(expected) - set(revisions))
            findings.append(
                _finding(
                    "snapshot_revision_gap",
                    "high",
                    thread_snapshots[-1].snapshot_id,
                    f"snapshot thread {thread_id} has missing revisions: {', '.join(str(item) for item in missing)}",
                )
            )
        latest_revision = max(revisions)
        observed_snapshots = [snapshot for snapshot in thread_snapshots if snapshot.lifecycle_status == "observed"]
        if len(observed_snapshots) > 1:
            findings.append(
                _finding(
                    "multiple_observed_snapshots_in_thread",
                    "high",
                    observed_snapshots[-1].snapshot_id,
                    f"snapshot thread {thread_id} has multiple observed snapshots",
                )
            )
        for snapshot in observed_snapshots:
            if snapshot.revision != latest_revision:
                findings.append(
                    _finding(
                        "observed_snapshot_not_latest_revision",
                        "high",
                        snapshot.snapshot_id,
                        f"observed snapshot revision {snapshot.revision} is not latest revision {latest_revision}",
                    )
                )

    for snapshot in snapshots:
        superseded = by_id.get(snapshot.supersedes_snapshot_id)
        if superseded is not None and superseded.snapshot_thread_id != snapshot.snapshot_thread_id:
            findings.append(
                _finding(
                    "snapshot_supersedes_cross_thread",
                    "high",
                    snapshot.snapshot_id,
                    f"snapshot supersedes {superseded.snapshot_id} from thread {superseded.snapshot_thread_id}",
                )
            )
        if (
            superseded is not None
            and superseded.snapshot_thread_id == snapshot.snapshot_thread_id
            and superseded.revision != snapshot.revision - 1
        ):
            findings.append(
                _finding(
                    "snapshot_supersedes_non_previous_revision",
                    "high",
                    snapshot.snapshot_id,
                    f"snapshot revision {snapshot.revision} supersedes revision {superseded.revision}",
                )
            )
    return findings


def _snapshot_findings(snapshots: tuple[ControlPlaneRuntimeStateSnapshot, ...]) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    for snapshot in snapshots:
        if snapshot.claims_canonical_state:
            findings.append(
                _finding(
                    "snapshot_claims_canonical_state",
                    "critical",
                    snapshot.snapshot_id,
                    "runtime-state snapshot claimed canonical state authority",
                )
            )
        if snapshot.claims_scheduler_authority:
            findings.append(
                _finding(
                    "snapshot_claims_scheduler_authority",
                    "critical",
                    snapshot.snapshot_id,
                    "runtime-state snapshot claimed scheduler authority",
                )
            )
        if snapshot.claims_execution_permission:
            findings.append(
                _finding(
                    "snapshot_claims_execution_permission",
                    "critical",
                    snapshot.snapshot_id,
                    "runtime-state snapshot claimed execution permission",
                )
            )
        if snapshot.auto_apply:
            findings.append(
                _finding("snapshot_requests_auto_apply", "high", snapshot.snapshot_id, "snapshot requested auto-apply")
            )
        if snapshot.contains_secret_material:
            findings.append(
                _finding(
                    "snapshot_contains_secret_material",
                    "critical",
                    snapshot.snapshot_id,
                    "snapshot says it contains secret material",
                )
            )
        if snapshot.contains_raw_evidence:
            findings.append(
                _finding(
                    "snapshot_contains_raw_evidence",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot says it contains raw evidence instead of sanitized references",
                )
            )
        if not snapshot.evidence_ids:
            findings.append(
                _finding(
                    "snapshot_missing_evidence_ids",
                    "medium",
                    snapshot.snapshot_id,
                    "snapshot has no evidence ids",
                )
            )
        if snapshot.lifecycle_status == "blocked" and (
            snapshot.open_ready_observation_ids
            or snapshot.runtime_adoption_candidate_ids
        ):
            findings.append(
                _finding(
                    "blocked_snapshot_launders_ready_work",
                    "high",
                    snapshot.snapshot_id,
                    "blocked snapshot still advertises open-ready work or runtime adoption candidates",
                )
            )
        if snapshot.queue_authority != "machine-primary" and (
            snapshot.active_observation_ids
            or snapshot.open_ready_observation_ids
            or snapshot.blocked_observation_ids
        ):
            findings.append(
                _finding(
                    "snapshot_queue_authority_not_machine_primary",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot includes queue ids without machine-primary queue authority",
                )
            )
        for observation_id in snapshot.open_ready_observation_ids:
            if observation_id not in snapshot.active_observation_ids:
                findings.append(
                    _finding(
                        "open_ready_observation_not_active",
                        "high",
                        snapshot.snapshot_id,
                        f"open-ready observation is absent from active_observation_ids: {observation_id}",
                    )
                )
        for observation_id in snapshot.blocked_observation_ids:
            if observation_id in snapshot.open_ready_observation_ids:
                findings.append(
                    _finding(
                        "blocked_observation_also_open_ready",
                        "high",
                        snapshot.snapshot_id,
                        f"blocked observation also appears open-ready: {observation_id}",
                    )
                )
        for field_name, text in (("summary", snapshot.summary), ("rationale", snapshot.rationale)):
            lowered = text.lower()
            has_negative_marker = any(marker in lowered for marker in _NEGATIVE_TEXT_MARKERS)
            for token in _FORBIDDEN_AUTHORITY_TOKENS:
                if token in lowered and not has_negative_marker:
                    findings.append(
                        _finding(
                            "snapshot_text_launders_runtime_state_authority",
                            "high",
                            snapshot.snapshot_id,
                            f"{field_name} contains forbidden runtime-state wording: {token}",
                        )
                    )
    return findings


def _integration_findings(
    snapshots: tuple[ControlPlaneRuntimeStateSnapshot, ...],
    observation_set_review: ControlPlaneObservationSetReview | None,
    decision_review: ControlPlaneDecisionVersionReview | None,
    integrity_review: ControlPlaneIntegrityReview | None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None,
    action_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    observed_observations = set(observation_set_review.observation_ids) if observation_set_review is not None else set()
    observed_open_ready = (
        set(observation_set_review.open_ready_observation_ids) if observation_set_review is not None else set()
    )
    current_decisions = set(decision_review.current_decision_ids) if decision_review is not None else set()
    active_rules = set(rule_promotion_review.active_rule_ids) if rule_promotion_review is not None else set()
    runtime_candidates = (
        set(runtime_adoption_review.runtime_candidate_ids) if runtime_adoption_review is not None else set()
    )

    for snapshot in snapshots:
        if (snapshot.active_observation_ids or snapshot.open_ready_observation_ids) and observation_set_review is None:
            findings.append(
                _finding(
                    "snapshot_missing_observation_set_review",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot includes observation ids without a supplied observation-set review",
                )
            )
        if observation_set_review is not None:
            for observation_id in snapshot.active_observation_ids:
                if observation_id not in observed_observations:
                    findings.append(
                        _finding(
                            "snapshot_references_unknown_observation",
                            "high",
                            snapshot.snapshot_id,
                            f"snapshot references unknown observation id: {observation_id}",
                        )
                    )
            if set(snapshot.open_ready_observation_ids) != observed_open_ready:
                findings.append(
                    _finding(
                        "snapshot_open_ready_frontier_drift",
                        "high",
                        snapshot.snapshot_id,
                        "snapshot open-ready observations differ from supplied observation-set review",
                    )
                )
            if observation_set_review.review_status != "observation_set_contract_observed":
                findings.append(
                    _finding(
                        "snapshot_over_observation_set_drift",
                        "high",
                        snapshot.snapshot_id,
                        f"observation-set review status is {observation_set_review.review_status}",
                    )
                )

        if snapshot.current_decision_ids and decision_review is None:
            findings.append(
                _finding(
                    "snapshot_missing_decision_review",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot includes current decisions without a supplied decision-version review",
                )
            )
        if decision_review is not None:
            if set(snapshot.current_decision_ids) != current_decisions:
                findings.append(
                    _finding(
                        "snapshot_current_decision_drift",
                        "high",
                        snapshot.snapshot_id,
                        "snapshot current decisions differ from supplied decision-version review",
                    )
                )
            if decision_review.review_status != "decision_version_contract_observed":
                findings.append(
                    _finding(
                        "snapshot_over_decision_drift",
                        "critical",
                        snapshot.snapshot_id,
                        f"decision-version review status is {decision_review.review_status}",
                    )
                )

        if integrity_review is None:
            findings.append(
                _finding(
                    "snapshot_missing_integrity_review",
                    "high",
                    snapshot.snapshot_id,
                    "runtime-state review requires a supplied integrity review",
                )
            )
        if integrity_review is not None and integrity_review.review_status != "control_plane_integrity_preserved":
            findings.append(
                _finding(
                    "snapshot_over_integrity_drift",
                    "critical",
                    snapshot.snapshot_id,
                    f"integrity review status is {integrity_review.review_status}",
                )
            )

        if snapshot.active_rule_ids and rule_promotion_review is None:
            findings.append(
                _finding(
                    "snapshot_missing_rule_promotion_review",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot includes active rules without a supplied rule-promotion review",
                )
            )
        if rule_promotion_review is not None:
            if set(snapshot.active_rule_ids) != active_rules:
                findings.append(
                    _finding(
                        "snapshot_active_rule_drift",
                        "high",
                        snapshot.snapshot_id,
                        "snapshot active rules differ from supplied rule-promotion review",
                    )
                )
            if rule_promotion_review.review_status == "rule_promotion_blocked":
                findings.append(
                    _finding(
                        "snapshot_over_rule_promotion_drift",
                        "critical",
                        snapshot.snapshot_id,
                        "rule-promotion review is blocked",
                    )
                )

        if snapshot.runtime_adoption_candidate_ids and runtime_adoption_review is None:
            findings.append(
                _finding(
                    "snapshot_missing_runtime_adoption_review",
                    "high",
                    snapshot.snapshot_id,
                    "snapshot includes runtime adoption candidates without a supplied runtime-adoption review",
                )
            )
        if runtime_adoption_review is not None:
            if set(snapshot.runtime_adoption_candidate_ids) != runtime_candidates:
                findings.append(
                    _finding(
                        "snapshot_runtime_adoption_candidate_drift",
                        "high",
                        snapshot.snapshot_id,
                        "snapshot runtime adoption candidates differ from supplied runtime-adoption review",
                    )
                )
            if runtime_adoption_review.review_status == "runtime_adoption_blocked":
                findings.append(
                    _finding(
                        "snapshot_over_runtime_adoption_drift",
                        "critical",
                        snapshot.snapshot_id,
                        "runtime-adoption review is blocked",
                    )
                )

        for bundle in action_bundles:
            if bundle.action_posture not in {"advisory_review_only", "human_review_required"}:
                findings.append(
                    _finding(
                        "snapshot_over_blocked_action_posture",
                        "high",
                        snapshot.snapshot_id,
                        f"action bundle {bundle.observation.observation_id} posture is {bundle.action_posture}",
                    )
                )
            if bundle.recommended_human_decision != "none":
                findings.append(
                    _finding(
                        "snapshot_over_unresolved_action_decision",
                        "high",
                        snapshot.snapshot_id,
                        f"action bundle requires {bundle.recommended_human_decision}",
                    )
                )
    return findings


def _has_cycle(graph: Mapping[str, tuple[str, ...]]) -> bool:
    visiting: set[str] = set()
    visited: set[str] = set()

    def visit(node: str) -> bool:
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for dependency in graph.get(node, ()):
            if dependency in graph and visit(dependency):
                return True
        visiting.discard(node)
        visited.add(node)
        return False

    return any(visit(node) for node in graph)


def _duplicate_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(sorted({value for value in values if values.count(value) > 1}))


def _state_payload_findings(state_payload: Mapping[str, object]) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    state_revision = state_payload.get("revision")
    root_keys = set(state_payload.keys())
    for key in sorted(_STATE_ROOT_KEYS - root_keys):
        findings.append(_finding("runtime_state_missing_required_key", "high", "state_payload", key))
    for key in sorted(root_keys - _STATE_ROOT_KEYS):
        findings.append(_finding("runtime_state_unexpected_key", "medium", "state_payload", key))
    if state_payload.get("version") not in {"1", 1}:
        findings.append(
            _finding(
                "runtime_state_invalid_schema_version",
                "high",
                "state_payload",
                f"unsupported version: {state_payload.get('version')}",
            )
        )
    if not isinstance(state_revision, int) or state_revision < 0:
        findings.append(
            _finding(
                "runtime_state_invalid_revision",
                "high",
                "state_payload",
                "state revision must be a non-negative integer",
            )
        )
    agent_runtime = state_payload.get("agent_runtime")
    if not isinstance(agent_runtime, Mapping):
        findings.append(
            _finding("runtime_state_missing_required_key", "high", "state_payload", "agent_runtime")
        )
        return findings
    runtime_keys = set(agent_runtime.keys())
    for key in sorted(_AGENT_RUNTIME_KEYS - runtime_keys):
        findings.append(_finding("runtime_agent_runtime_missing_key", "high", "state_payload", key))
    for key in sorted(runtime_keys - _AGENT_RUNTIME_KEYS):
        findings.append(_finding("runtime_agent_runtime_unexpected_key", "medium", "state_payload", key))
    findings.extend(_plan_payload_findings(agent_runtime))
    findings.extend(_action_approval_verification_findings(agent_runtime))
    return findings


def _plan_payload_findings(agent_runtime: Mapping[str, object]) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    plan = agent_runtime.get("plan")
    if not isinstance(plan, Mapping):
        return [_finding("runtime_state_missing_required_key", "high", "state_payload", "agent_runtime.plan")]
    status = plan.get("status")
    if status not in _PLAN_STATUSES:
        findings.append(_finding("runtime_plan_status_contradiction", "high", "state_payload", f"unknown plan status: {status}"))
    tasks = _mapping_list(plan.get("tasks"), "agent_runtime.plan.tasks")
    task_ids = _string_ids(tasks, "id")
    for duplicate_id in _duplicate_ids(task_ids):
        findings.append(_finding("runtime_duplicate_task_id", "high", "state_payload", duplicate_id))
    known_tasks = set(task_ids)
    current_task_id = plan.get("current_task_id", "")
    if isinstance(current_task_id, str) and current_task_id and current_task_id not in known_tasks:
        findings.append(
            _finding(
                "runtime_plan_current_task_unknown",
                "high",
                "state_payload",
                f"current_task_id is unknown: {current_task_id}",
            )
        )
    dependency_graph: dict[str, tuple[str, ...]] = {}
    done_count = 0
    for task in tasks:
        task_id = task.get("id", "")
        if not isinstance(task_id, str) or not task_id:
            continue
        task_status = task.get("status")
        if task_status == "done":
            done_count += 1
        if task_status not in _TASK_STATUSES:
            findings.append(
                _finding("runtime_plan_status_contradiction", "high", "state_payload", f"unknown task status: {task_status}")
            )
        depends_on = _as_id_tuple(task.get("depends_on"), f"task {task_id} depends_on")
        dependency_graph[task_id] = depends_on
        for dependency_id in depends_on:
            if dependency_id == task_id:
                findings.append(
                    _finding(
                        "runtime_plan_dependency_self_reference",
                        "high",
                        "state_payload",
                        f"task depends on itself: {task_id}",
                    )
                )
            elif dependency_id not in known_tasks:
                findings.append(
                    _finding(
                        "runtime_plan_dependency_unknown",
                        "high",
                        "state_payload",
                        f"task {task_id} depends on unknown task: {dependency_id}",
                    )
                )
    if _has_cycle(dependency_graph):
        findings.append(
            _finding("runtime_plan_dependency_cycle", "high", "state_payload", "task dependency graph contains a cycle")
        )
    if status == "idle" and tasks:
        findings.append(
            _finding("runtime_plan_status_contradiction", "high", "state_payload", "idle plan contains tasks")
        )
    if tasks and done_count == len(tasks) and status != "completed":
        findings.append(
            _finding("runtime_plan_status_contradiction", "medium", "state_payload", "all tasks are done but plan is not completed")
        )
    if status == "completed" and done_count != len(tasks):
        findings.append(
            _finding("runtime_plan_status_contradiction", "high", "state_payload", "completed plan has unfinished tasks")
        )
    return findings


def _action_approval_verification_findings(
    agent_runtime: Mapping[str, object],
) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    plan = agent_runtime.get("plan") if isinstance(agent_runtime.get("plan"), Mapping) else {}
    tasks = _mapping_list(plan.get("tasks") if isinstance(plan, Mapping) else [], "agent_runtime.plan.tasks")
    task_ids = set(_string_ids(tasks, "id"))
    task_action_ids: dict[str, set[str]] = {}
    for task in tasks:
        task_id = task.get("id", "")
        if isinstance(task_id, str) and task_id:
            task_action_ids[task_id] = set(_as_id_tuple(task.get("action_ids"), f"task {task_id} action_ids"))

    actions = _mapping_list(agent_runtime.get("actions"), "agent_runtime.actions")
    action_ids = _string_ids(actions, "id")
    for duplicate_id in _duplicate_ids(action_ids):
        findings.append(_finding("runtime_duplicate_action_id", "high", "state_payload", duplicate_id))
    known_actions = set(action_ids)

    approvals_payload = agent_runtime.get("approvals")
    approvals = _mapping_list(
        approvals_payload.get("items") if isinstance(approvals_payload, Mapping) else [],
        "agent_runtime.approvals.items",
    )
    approval_ids = _string_ids(approvals, "id")
    for duplicate_id in _duplicate_ids(approval_ids):
        findings.append(_finding("runtime_duplicate_approval_id", "high", "state_payload", duplicate_id))
    known_approvals = set(approval_ids)
    for approval in approvals:
        approval_id = approval.get("id", "")
        status = approval.get("status")
        resolved_at = approval.get("resolved_at", "")
        task_id = approval.get("task_id", "")
        if status not in _APPROVAL_STATUSES:
            findings.append(_finding("runtime_approval_status_contradiction", "high", "state_payload", f"unknown approval status: {status}"))
        if status == "pending" and resolved_at:
            findings.append(_finding("runtime_approval_status_contradiction", "high", "state_payload", f"pending approval has resolved_at: {approval_id}"))
        if status in {"approved", "rejected"} and not resolved_at:
            findings.append(_finding("runtime_approval_status_contradiction", "high", "state_payload", f"resolved approval lacks resolved_at: {approval_id}"))
        if isinstance(task_id, str) and task_id and task_id not in task_ids:
            findings.append(_finding("runtime_action_unknown_task", "high", "state_payload", f"approval references unknown task: {task_id}"))

    for action in actions:
        action_id = action.get("id", "")
        status = action.get("status")
        task_id = action.get("task_id", "")
        approval_id = action.get("approval_id", "")
        if status not in _ACTION_STATUSES:
            findings.append(_finding("runtime_action_status_contradiction", "high", "state_payload", f"unknown action status: {status}"))
        if isinstance(task_id, str) and task_id and task_id not in task_ids:
            findings.append(_finding("runtime_action_unknown_task", "high", "state_payload", f"action references unknown task: {task_id}"))
        if isinstance(task_id, str) and task_id in task_action_ids and action_id not in task_action_ids[task_id]:
            findings.append(_finding("runtime_action_missing_task_backref", "high", "state_payload", f"action missing from task action_ids: {action_id}"))
        if isinstance(approval_id, str) and approval_id and approval_id not in known_approvals:
            findings.append(_finding("runtime_action_unknown_approval", "high", "state_payload", f"action references unknown approval: {approval_id}"))

    command_registry = agent_runtime.get("command_registry")
    commands = _mapping_list(
        command_registry.get("commands") if isinstance(command_registry, Mapping) else [],
        "agent_runtime.command_registry.commands",
    )
    command_ids = _string_ids(commands, "id")
    command_by_id = {command_id: command for command_id, command in zip(command_ids, commands)}
    for duplicate_id in _duplicate_ids(command_ids):
        findings.append(_finding("runtime_duplicate_command_id", "high", "state_payload", duplicate_id))
    verification = agent_runtime.get("verification")
    if isinstance(verification, Mapping):
        verification_status = verification.get("status")
        if verification_status not in _VERIFICATION_STATUSES:
            findings.append(_finding("runtime_verification_status_contradiction", "high", "state_payload", f"unknown verification status: {verification_status}"))
        for command_id in _as_id_tuple(verification.get("required_command_ids"), "verification required_command_ids"):
            command = command_by_id.get(command_id)
            if command is None:
                findings.append(_finding("runtime_verification_unknown_command", "high", "state_payload", command_id))
            elif command.get("allow_in_verify") is False:
                findings.append(_finding("runtime_verification_disallowed_command", "high", "state_payload", command_id))
        pending_action_ids = _as_id_tuple(verification.get("pending_action_ids"), "verification pending_action_ids")
        action_by_id = {action_id: action for action_id, action in zip(action_ids, actions)}
        for action_id in pending_action_ids:
            action = action_by_id.get(action_id)
            if action is None:
                findings.append(_finding("runtime_verification_unknown_pending_action", "high", "state_payload", action_id))
            elif action.get("status") == "rolled_back":
                findings.append(_finding("runtime_verification_unknown_pending_action", "high", "state_payload", f"rolled back pending action: {action_id}"))
        if verification_status == "passed" and pending_action_ids:
            findings.append(_finding("runtime_verification_passed_with_pending_actions", "high", "state_payload", "passed verification has pending actions"))
        checks = _mapping_list(verification.get("checks"), "agent_runtime.verification.checks")
        if verification_status == "passed" and any(check.get("status") == "failed" for check in checks):
            findings.append(_finding("runtime_verification_status_contradiction", "high", "state_payload", "passed verification has failed checks"))
        for check in checks:
            command_id = check.get("command_id", "")
            if isinstance(command_id, str) and command_id and command_id not in command_by_id:
                findings.append(_finding("runtime_verification_unknown_command", "high", "state_payload", command_id))

    audit = agent_runtime.get("audit")
    if isinstance(audit, Mapping):
        last_action_id = audit.get("last_action_id", "")
        if isinstance(last_action_id, str) and last_action_id and last_action_id not in known_actions:
            findings.append(_finding("runtime_audit_last_action_unknown", "high", "state_payload", last_action_id))
        if not isinstance(audit.get("trace_thread_id"), str) or not audit.get("trace_thread_id"):
            findings.append(_finding("runtime_trace_event_thread_mismatch", "high", "state_payload", "trace_thread_id is missing"))
        if not isinstance(audit.get("next_event_id"), int) or audit.get("next_event_id") < 1:
            findings.append(_finding("runtime_trace_next_event_id_inconsistent", "high", "state_payload", "next_event_id must be positive"))
        if audit.get("trace_status") not in _TRACE_STATUSES:
            findings.append(_finding("runtime_trace_event_thread_mismatch", "high", "state_payload", f"unknown trace status: {audit.get('trace_status')}"))
        if audit.get("trace_integrity") not in _TRACE_INTEGRITIES:
            findings.append(_finding("runtime_trace_event_thread_mismatch", "high", "state_payload", f"unknown trace integrity: {audit.get('trace_integrity')}"))
    return findings


def _recent_event_findings(
    state_payload: Mapping[str, object] | None,
    recent_events_payload: Iterable[Mapping[str, object]],
) -> list[ControlPlaneRuntimeStateFinding]:
    events = tuple(recent_events_payload)
    if not events:
        return []
    findings: list[ControlPlaneRuntimeStateFinding] = []
    audit = {}
    if state_payload is not None:
        agent_runtime = state_payload.get("agent_runtime")
        if isinstance(agent_runtime, Mapping) and isinstance(agent_runtime.get("audit"), Mapping):
            audit = agent_runtime["audit"]
    expected_thread = audit.get("trace_thread_id", "")
    next_event_id = audit.get("next_event_id")
    previous_id = 0
    max_event_id = 0
    for event in events:
        event_id = event.get("event_id")
        if not isinstance(event_id, int) or event_id <= previous_id:
            findings.append(_finding("runtime_trace_event_id_not_monotonic", "high", "events", f"event_id={event_id}"))
            continue
        previous_id = event_id
        max_event_id = max(max_event_id, event_id)
        if expected_thread and event.get("trace_thread_id") != expected_thread:
            findings.append(
                _finding(
                    "runtime_trace_event_thread_mismatch",
                    "high",
                    "events",
                    f"event thread {event.get('trace_thread_id')} differs from {expected_thread}",
                )
            )
    if isinstance(next_event_id, int) and max_event_id >= next_event_id:
        findings.append(
            _finding(
                "runtime_trace_next_event_id_inconsistent",
                "high",
                "events",
                f"max event id {max_event_id} is not below next_event_id {next_event_id}",
            )
        )
    return findings


def _session_and_lock_findings(
    state_payload: Mapping[str, object] | None,
    session_payload: Mapping[str, object] | None,
    lock_snapshot_payload: Mapping[str, object] | None,
) -> list[ControlPlaneRuntimeStateFinding]:
    findings: list[ControlPlaneRuntimeStateFinding] = []
    state_revision = state_payload.get("revision") if state_payload is not None else None
    audit = {}
    if state_payload is not None:
        agent_runtime = state_payload.get("agent_runtime")
        if isinstance(agent_runtime, Mapping) and isinstance(agent_runtime.get("audit"), Mapping):
            audit = agent_runtime["audit"]
    if session_payload is not None:
        based_on_revision = session_payload.get("based_on_revision")
        if isinstance(state_revision, int) and isinstance(based_on_revision, int) and based_on_revision > state_revision:
            findings.append(
                _finding(
                    "runtime_session_revision_ahead_of_state",
                    "high",
                    "session",
                    f"session revision {based_on_revision} is ahead of state revision {state_revision}",
                )
            )
        owner_claim_id = session_payload.get("owner_claim_id", "")
        active_claim_id = audit.get("active_session_claim_id", "")
        if owner_claim_id and active_claim_id and owner_claim_id != active_claim_id:
            findings.append(
                _finding(
                    "runtime_session_claim_mismatch",
                    "high",
                    "session",
                    "session owner claim differs from runtime audit active_session_claim_id",
                )
            )
    if lock_snapshot_payload is not None:
        if lock_snapshot_payload.get("lock_present") is True and not isinstance(lock_snapshot_payload.get("lock_payload"), Mapping):
            findings.append(
                _finding("runtime_lock_payload_invalid", "medium", "lock", "lock is present but payload is not a mapping")
            )
        if lock_snapshot_payload.get("process_lock_held") is True:
            findings.append(
                _finding(
                    "runtime_lock_owner_observed_not_authority",
                    "low",
                    "lock",
                    "observed lock owner is evidence only, not permission or recovery authority",
                )
            )
    return findings


def _latest_snapshot_ids(snapshots: tuple[ControlPlaneRuntimeStateSnapshot, ...]) -> tuple[str, ...]:
    by_thread: dict[str, list[ControlPlaneRuntimeStateSnapshot]] = {}
    for snapshot in snapshots:
        by_thread.setdefault(snapshot.snapshot_thread_id, []).append(snapshot)
    return tuple(
        sorted(
            max(thread_snapshots, key=lambda item: item.revision).snapshot_id
            for thread_snapshots in by_thread.values()
        )
    )


def _review_status(findings: tuple[ControlPlaneRuntimeStateFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "runtime_state_contract_blocked"
    if findings:
        return "runtime_state_human_review_required"
    return "runtime_state_snapshot_observed"


def _validate_review(review: ControlPlaneRuntimeStateReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateReviewError("runtime-state review must have state_change none")
    _validate_authority_text(review.authority, "runtime-state review")
    if (
        not review.state_review_is_not_permission
        or not review.snapshot_is_not_canonical_state
        or not review.observed_state_is_not_scheduler
        or not review.state_status_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateReviewError("runtime-state review guardrails must remain true")
    if review.snapshot_count != len(review.snapshot_ids):
        raise ControlPlaneRuntimeStateReviewError("snapshot_count must match snapshot_ids")
    if review.snapshot_thread_count != len(review.snapshot_thread_ids):
        raise ControlPlaneRuntimeStateReviewError("snapshot_thread_count must match snapshot_thread_ids")
    if review.evidence_count != len(review.evidence_ids):
        raise ControlPlaneRuntimeStateReviewError("evidence_count must match evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneRuntimeStateReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneRuntimeStateReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneRuntimeStateReviewError("severity_counts must match findings")
    for field_name, ids in (
        ("latest_snapshot_ids", review.latest_snapshot_ids),
        ("non_latest_snapshot_ids", review.non_latest_snapshot_ids),
        ("blocked_snapshot_ids", review.blocked_snapshot_ids),
    ):
        if any(item not in review.snapshot_ids for item in ids):
            raise ControlPlaneRuntimeStateReviewError(f"{field_name} must be a subset of snapshot_ids")
    latest_ids = set(review.latest_snapshot_ids)
    non_latest_ids = set(review.non_latest_snapshot_ids)
    if latest_ids & non_latest_ids:
        raise ControlPlaneRuntimeStateReviewError("latest_snapshot_ids and non_latest_snapshot_ids must be disjoint")
    if latest_ids | non_latest_ids != set(review.snapshot_ids):
        raise ControlPlaneRuntimeStateReviewError("latest_snapshot_ids and non_latest_snapshot_ids must cover snapshot_ids")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneRuntimeStateReviewError("review_status must match findings")


def build_control_plane_runtime_state_review(
    snapshot_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    state_payload: Mapping[str, object] | None = None,
    session_payload: Mapping[str, object] | None = None,
    recent_events_payload: Iterable[Mapping[str, object]] = (),
    lock_snapshot_payload: Mapping[str, object] | None = None,
    observation_set_review: ControlPlaneObservationSetReview | None = None,
    decision_review: ControlPlaneDecisionVersionReview | None = None,
    integrity_review: ControlPlaneIntegrityReview | None = None,
    rule_promotion_review: ControlPlaneRulePromotionReview | None = None,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneRuntimeStateReview:
    """Review caller-supplied runtime-state snapshots without storing or applying them."""

    _parse_date(review_as_of, "review_as_of")
    snapshots = _snapshots_from_payloads(snapshot_payloads)
    _validate_observation_set_review(observation_set_review)
    _validate_decision_review(decision_review)
    _validate_integrity_review(integrity_review)
    _validate_rule_promotion_review(rule_promotion_review)
    _validate_runtime_adoption_review(runtime_adoption_review)
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        _validate_action_bundle(bundle)
    if state_payload is not None:
        _as_mapping(state_payload, "state_payload")
    if session_payload is not None:
        _as_mapping(session_payload, "session_payload")
    recent_events = tuple(recent_events_payload)
    for event in recent_events:
        _as_mapping(event, "recent_events_payload item")
    if lock_snapshot_payload is not None:
        _as_mapping(lock_snapshot_payload, "lock_snapshot_payload")
    findings = tuple(
        _thread_findings(snapshots)
        + _snapshot_findings(snapshots)
        + (_state_payload_findings(state_payload) if state_payload is not None else [])
        + _recent_event_findings(state_payload, recent_events)
        + _session_and_lock_findings(state_payload, session_payload, lock_snapshot_payload)
        + _integration_findings(
            snapshots,
            observation_set_review,
            decision_review,
            integrity_review,
            rule_promotion_review,
            runtime_adoption_review,
            bundles,
        )
    )
    latest_ids = _latest_snapshot_ids(snapshots)
    evidence_ids = tuple(sorted({evidence_id for snapshot in snapshots for evidence_id in snapshot.evidence_ids}))
    snapshot_id_set = {snapshot.snapshot_id for snapshot in snapshots}
    blocked_ids = {finding.snapshot_id for finding in findings if finding.severity in {"critical", "high"}}
    blocked_snapshot_ids = tuple(
        sorted((blocked_ids & snapshot_id_set) or (set(latest_ids) if blocked_ids else set()))
    )
    review = ControlPlaneRuntimeStateReview(
        schema_version="1",
        review_role="reviews_caller_supplied_runtime_state_snapshots_without_storing_or_applying_them",
        review_status=_review_status(findings),
        review_as_of=review_as_of,
        snapshot_count=len(snapshots),
        snapshot_thread_count=len({snapshot.snapshot_thread_id for snapshot in snapshots}),
        snapshot_ids=tuple(snapshot.snapshot_id for snapshot in snapshots),
        snapshot_thread_ids=tuple(sorted({snapshot.snapshot_thread_id for snapshot in snapshots})),
        latest_snapshot_ids=latest_ids,
        non_latest_snapshot_ids=tuple(snapshot.snapshot_id for snapshot in snapshots if snapshot.snapshot_id not in latest_ids),
        blocked_snapshot_ids=blocked_snapshot_ids,
        observed_state_scopes=tuple(sorted({snapshot.state_scope for snapshot in snapshots})),
        lifecycle_statuses=tuple(sorted({snapshot.lifecycle_status for snapshot in snapshots})),
        evidence_count=len(evidence_ids),
        evidence_ids=evidence_ids,
        active_observation_ids=tuple(
            sorted({item for snapshot in snapshots for item in snapshot.active_observation_ids})
        ),
        open_ready_observation_ids=tuple(
            sorted({item for snapshot in snapshots for item in snapshot.open_ready_observation_ids})
        ),
        current_decision_ids=tuple(sorted({item for snapshot in snapshots for item in snapshot.current_decision_ids})),
        active_rule_ids=tuple(sorted({item for snapshot in snapshots for item in snapshot.active_rule_ids})),
        runtime_adoption_candidate_ids=tuple(
            sorted({item for snapshot in snapshots for item in snapshot.runtime_adoption_candidate_ids})
        ),
        observation_set_review_status=observation_set_review.review_status if observation_set_review is not None else "not_supplied",
        decision_review_status=decision_review.review_status if decision_review is not None else "not_supplied",
        integrity_review_status=integrity_review.review_status if integrity_review is not None else "not_supplied",
        rule_promotion_review_status=rule_promotion_review.review_status if rule_promotion_review is not None else "not_supplied",
        runtime_adoption_review_status=runtime_adoption_review.review_status if runtime_adoption_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_runtime_state_review_json(review: ControlPlaneRuntimeStateReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_runtime_state_review_markdown(review: ControlPlaneRuntimeStateReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Runtime State Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane runtime state review only",
        "- state_review_is_not_permission: true",
        "- snapshot_is_not_canonical_state: true",
        "- observed_state_is_not_scheduler: true",
        "- state_status_is_not_execution_approval: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- review_as_of: {review.review_as_of}",
        f"- snapshot_count: {review.snapshot_count}",
        f"- snapshot_thread_count: {review.snapshot_thread_count}",
        f"- latest_snapshot_ids: {', '.join(review.latest_snapshot_ids) if review.latest_snapshot_ids else 'none'}",
        f"- non_latest_snapshot_ids: {', '.join(review.non_latest_snapshot_ids) if review.non_latest_snapshot_ids else 'none'}",
        f"- blocked_snapshot_ids: {', '.join(review.blocked_snapshot_ids) if review.blocked_snapshot_ids else 'none'}",
        f"- observed_state_scopes: {', '.join(review.observed_state_scopes) if review.observed_state_scopes else 'none'}",
        f"- lifecycle_statuses: {', '.join(review.lifecycle_statuses) if review.lifecycle_statuses else 'none'}",
        f"- evidence_ids: {', '.join(review.evidence_ids) if review.evidence_ids else 'none'}",
        f"- active_observation_ids: {', '.join(review.active_observation_ids) if review.active_observation_ids else 'none'}",
        f"- open_ready_observation_ids: {', '.join(review.open_ready_observation_ids) if review.open_ready_observation_ids else 'none'}",
        f"- current_decision_ids: {', '.join(review.current_decision_ids) if review.current_decision_ids else 'none'}",
        f"- active_rule_ids: {', '.join(review.active_rule_ids) if review.active_rule_ids else 'none'}",
        (
            "- runtime_adoption_candidate_ids: "
            f"{', '.join(review.runtime_adoption_candidate_ids) if review.runtime_adoption_candidate_ids else 'none'}"
        ),
        f"- observation_set_review_status: {review.observation_set_review_status}",
        f"- decision_review_status: {review.decision_review_status}",
        f"- integrity_review_status: {review.integrity_review_status}",
        f"- rule_promotion_review_status: {review.rule_promotion_review_status}",
        f"- runtime_adoption_review_status: {review.runtime_adoption_review_status}",
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
            lines.append(f"- {finding.severity}: {finding.code} [{finding.snapshot_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
