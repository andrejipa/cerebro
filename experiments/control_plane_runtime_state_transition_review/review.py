from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_runtime_adoption_review import ControlPlaneRuntimeAdoptionReview
from experiments.control_plane_runtime_state_review import ControlPlaneRuntimeStateReview


class ControlPlaneRuntimeStateTransitionReviewError(ValueError):
    """Raised when runtime-state transition inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneRuntimeStateTransitionEvidence:
    evidence_id: str
    subject_kind: str
    subject_id: str
    evidence_kind: str
    human_decision_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRuntimeStateTransitionFinding:
    code: str
    severity: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneRuntimeStateTransitionReview:
    schema_version: str
    review_role: str
    review_status: str
    before_review_as_of: str
    after_review_as_of: str
    transition_evidence_count: int
    evidence_ids: tuple[str, ...]
    before_latest_snapshot_ids: tuple[str, ...]
    after_latest_snapshot_ids: tuple[str, ...]
    added_latest_snapshot_ids: tuple[str, ...]
    removed_latest_snapshot_ids: tuple[str, ...]
    added_open_ready_observation_ids: tuple[str, ...]
    removed_open_ready_observation_ids: tuple[str, ...]
    added_active_observation_ids: tuple[str, ...]
    removed_active_observation_ids: tuple[str, ...]
    added_current_decision_ids: tuple[str, ...]
    removed_current_decision_ids: tuple[str, ...]
    added_active_rule_ids: tuple[str, ...]
    removed_active_rule_ids: tuple[str, ...]
    added_runtime_adoption_candidate_ids: tuple[str, ...]
    removed_runtime_adoption_candidate_ids: tuple[str, ...]
    before_review_status: str
    after_review_status: str
    runtime_adoption_review_status: str
    action_bundle_count: int
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneRuntimeStateTransitionFinding, ...]
    before_review: ControlPlaneRuntimeStateReview
    after_review: ControlPlaneRuntimeStateReview
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane runtime state transition review only"
    transition_review_is_not_permission: bool = True
    observed_transition_is_not_truth: bool = True
    observed_transition_is_not_scheduler: bool = True
    transition_pass_is_not_execution_approval: bool = True
    transition_review_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_SUBJECT_KINDS = {
    "snapshot",
    "observation",
    "decision",
    "rule",
    "runtime_adoption",
    "action",
    "verification",
    "session",
    "lock",
    "state_scope",
}
_EVIDENCE_KINDS = {
    "human_decision",
    "supersession",
    "adoption_review",
    "approval_review",
    "verification_review",
    "rollback",
    "resolution",
    "removal",
    "event_continuity",
    "lock_observation",
    "state_scope_change",
    "rule_review",
}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "grants permission",
    "permission to execute",
    "execution approval",
    "execution approved",
    "permission_granted",
    "runtime authority",
    "runtime_authority",
    "canonical state",
    "canonical_state",
    "state is truth",
    "state_is_truth",
    "transition is truth",
    "truth signal",
    "scheduler",
    "schedules work",
    "selected next action",
    "next action selected",
    "approved to run",
    "ready to execute",
    "recovery authority",
    "lock recovered",
    "session recovered",
    "auto apply",
    "automatically applies",
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
    "does not recover",
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
        raise ControlPlaneRuntimeStateTransitionReviewError(f"{field} must be an ISO date") from exc


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneRuntimeStateTransitionReviewError(f"missing required transition evidence field: {field}")
    return value.strip()


def _has_unqualified_authority_text(text: str) -> bool:
    normalized = " ".join(text.lower().replace("_", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _evidence_from_payload(payload: Mapping[str, object]) -> ControlPlaneRuntimeStateTransitionEvidence:
    evidence_id = _required_str(payload, "evidence_id")
    subject_kind = _required_str(payload, "subject_kind")
    subject_id = _required_str(payload, "subject_id")
    evidence_kind = _required_str(payload, "evidence_kind")
    if not all(_is_path_segment_safe(value) for value in (evidence_id, subject_id)):
        raise ControlPlaneRuntimeStateTransitionReviewError("transition evidence ids must be path-segment safe")
    if subject_kind not in _SUBJECT_KINDS:
        raise ControlPlaneRuntimeStateTransitionReviewError(f"unknown transition subject_kind: {subject_kind}")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise ControlPlaneRuntimeStateTransitionReviewError(f"unknown transition evidence_kind: {evidence_kind}")
    human_decision_id = _required_str(payload, "human_decision_id")
    if not _is_path_segment_safe(human_decision_id):
        raise ControlPlaneRuntimeStateTransitionReviewError("human_decision_id must be path-segment safe")
    return ControlPlaneRuntimeStateTransitionEvidence(
        evidence_id=evidence_id,
        subject_kind=subject_kind,
        subject_id=subject_id,
        evidence_kind=evidence_kind,
        human_decision_id=human_decision_id,
        detail=_required_str(payload, "detail"),
    )


def _evidence_from_payloads(
    payloads: Iterable[Mapping[str, object]],
) -> tuple[ControlPlaneRuntimeStateTransitionEvidence, ...]:
    evidence = tuple(_evidence_from_payload(payload) for payload in payloads)
    ids = [item.evidence_id for item in evidence]
    if len(set(ids)) != len(ids):
        raise ControlPlaneRuntimeStateTransitionReviewError("duplicate transition evidence ids are not allowed")
    unique_subject_evidence = {(item.subject_kind, item.subject_id, item.evidence_kind) for item in evidence}
    if len(unique_subject_evidence) != len(evidence):
        raise ControlPlaneRuntimeStateTransitionReviewError("duplicate transition evidence subject/kind tuple is not allowed")
    return evidence


def _has_evidence(
    evidence: tuple[ControlPlaneRuntimeStateTransitionEvidence, ...],
    *,
    subject_kind: str,
    subject_id: str,
    evidence_kinds: set[str],
) -> bool:
    for item in evidence:
        if item.subject_kind != subject_kind or item.subject_id != subject_id or item.evidence_kind not in evidence_kinds:
            continue
        if item.human_decision_id.lower() in {"none", "automatic", "auto"}:
            continue
        return True
    return False


def _finding(
    code: str,
    severity: str,
    subject_id: str,
    detail: str,
) -> ControlPlaneRuntimeStateTransitionFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneRuntimeStateTransitionReviewError(f"unknown severity: {severity}")
    return ControlPlaneRuntimeStateTransitionFinding(code=code, severity=severity, subject_id=subject_id, detail=detail)


def _check_runtime_state_review_guardrails(review: ControlPlaneRuntimeStateReview, label: str) -> None:
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateTransitionReviewError(f"{label} runtime-state review must have state_change none")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneRuntimeStateTransitionReviewError(f"{label} runtime-state review must remain non-authoritative")
    if (
        not review.state_review_is_not_permission
        or not review.snapshot_is_not_canonical_state
        or not review.observed_state_is_not_scheduler
        or not review.state_status_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateTransitionReviewError(f"{label} runtime-state review guardrails drifted")


def _validate_supplied_review_guardrails(
    *,
    before_review: ControlPlaneRuntimeStateReview,
    after_review: ControlPlaneRuntimeStateReview,
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle],
) -> tuple[ControlPlaneActionReviewBundle, ...]:
    _check_runtime_state_review_guardrails(before_review, "before")
    _check_runtime_state_review_guardrails(after_review, "after")
    if runtime_adoption_review is not None and (
        not runtime_adoption_review.adoption_review_is_not_permission
        or not runtime_adoption_review.technology_selection_is_not_authority
        or not runtime_adoption_review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateTransitionReviewError("runtime adoption review guardrails drifted")
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        if (
            not bundle.bundle_is_not_permission
            or not bundle.action_posture_is_not_execution_approval
            or not bundle.must_not_execute_automatically
        ):
            raise ControlPlaneRuntimeStateTransitionReviewError("action review bundle guardrails drifted")
    return bundles


def _set_delta(before: tuple[str, ...], after: tuple[str, ...]) -> tuple[tuple[str, ...], tuple[str, ...]]:
    before_set = set(before)
    after_set = set(after)
    return tuple(sorted(after_set - before_set)), tuple(sorted(before_set - after_set))


def _review_findings(
    before_review: ControlPlaneRuntimeStateReview,
    after_review: ControlPlaneRuntimeStateReview,
) -> list[ControlPlaneRuntimeStateTransitionFinding]:
    findings: list[ControlPlaneRuntimeStateTransitionFinding] = []
    if before_review.blocked_snapshot_ids:
        findings.append(
            _finding(
                "runtime_transition_over_blocked_before_state",
                "high",
                "before",
                "before runtime-state review has blocked snapshots",
            )
        )
    if after_review.blocked_snapshot_ids:
        findings.append(
            _finding(
                "runtime_transition_over_blocked_after_state",
                "critical",
                "after",
                "after runtime-state review has blocked snapshots",
            )
        )
    if _parse_date(after_review.review_as_of, "after_review_as_of") < _parse_date(
        before_review.review_as_of, "before_review_as_of"
    ):
        findings.append(
            _finding(
                "runtime_transition_review_date_regressed",
                "high",
                "review_as_of",
                "after review date predates before review date",
            )
        )
    return findings


def _transition_findings(
    before_review: ControlPlaneRuntimeStateReview,
    after_review: ControlPlaneRuntimeStateReview,
    evidence: tuple[ControlPlaneRuntimeStateTransitionEvidence, ...],
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None,
    action_review_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> list[ControlPlaneRuntimeStateTransitionFinding]:
    findings: list[ControlPlaneRuntimeStateTransitionFinding] = []
    added_open_ready, _ = _set_delta(before_review.open_ready_observation_ids, after_review.open_ready_observation_ids)
    added_active, removed_active = _set_delta(before_review.active_observation_ids, after_review.active_observation_ids)
    added_decisions, removed_decisions = _set_delta(before_review.current_decision_ids, after_review.current_decision_ids)
    added_rules, removed_rules = _set_delta(before_review.active_rule_ids, after_review.active_rule_ids)
    added_candidates, removed_candidates = _set_delta(
        before_review.runtime_adoption_candidate_ids,
        after_review.runtime_adoption_candidate_ids,
    )
    added_snapshots, removed_snapshots = _set_delta(before_review.latest_snapshot_ids, after_review.latest_snapshot_ids)

    for observation_id in added_open_ready:
        if not _has_evidence(
            evidence,
            subject_kind="observation",
            subject_id=observation_id,
            evidence_kinds={"human_decision", "approval_review", "event_continuity"},
        ):
            findings.append(
                _finding(
                    "open_ready_observation_introduced_without_evidence",
                    "high",
                    observation_id,
                    "open-ready observation appeared after transition without caller-supplied evidence",
                )
            )
    for observation_id in removed_active:
        if not _has_evidence(
            evidence,
            subject_kind="observation",
            subject_id=observation_id,
            evidence_kinds={"resolution", "removal", "human_decision"},
        ):
            findings.append(
                _finding(
                    "active_observation_removed_without_resolution",
                    "high",
                    observation_id,
                    "active observation disappeared without resolution/removal evidence",
                )
            )
    for candidate_id in added_candidates:
        has_local_evidence = _has_evidence(
            evidence,
            subject_kind="runtime_adoption",
            subject_id=candidate_id,
            evidence_kinds={"adoption_review", "human_decision"},
        )
        has_review_reference = runtime_adoption_review is not None and candidate_id in runtime_adoption_review.proposal_ids
        if not has_local_evidence and not has_review_reference:
            findings.append(
                _finding(
                    "runtime_candidate_introduced_without_adoption_review",
                    "high",
                    candidate_id,
                    "runtime adoption candidate appeared without transition evidence or supplied adoption review",
                )
            )
    for candidate_id in removed_candidates:
        if not _has_evidence(
            evidence,
            subject_kind="runtime_adoption",
            subject_id=candidate_id,
            evidence_kinds={"resolution", "removal", "human_decision"},
        ):
            findings.append(
                _finding(
                    "runtime_candidate_removed_without_resolution_evidence",
                    "high",
                    candidate_id,
                    "runtime adoption candidate disappeared without resolution/removal evidence",
                )
            )
    for decision_id in sorted(set(added_decisions + removed_decisions)):
        if not _has_evidence(
            evidence,
            subject_kind="decision",
            subject_id=decision_id,
            evidence_kinds={"human_decision", "approval_review"},
        ):
            findings.append(
                _finding(
                    "current_decision_changed_without_human_evidence",
                    "high",
                    decision_id,
                    "current decision set changed without human decision evidence",
                )
            )
    for rule_id in sorted(set(added_rules + removed_rules)):
        if not _has_evidence(
            evidence,
            subject_kind="rule",
            subject_id=rule_id,
            evidence_kinds={"rule_review", "human_decision"},
        ):
            findings.append(
                _finding(
                    "active_rule_changed_without_rule_evidence",
                    "high",
                    rule_id,
                    "active rule set changed without rule review evidence",
                )
            )
    if set(before_review.observed_state_scopes) != set(after_review.observed_state_scopes):
        if not _has_evidence(
            evidence,
            subject_kind="state_scope",
            subject_id="state_scope",
            evidence_kinds={"state_scope_change", "human_decision"},
        ):
            findings.append(
                _finding(
                    "state_scope_changed_without_transition_evidence",
                    "high",
                    "state_scope",
                    "observed state scopes changed without transition evidence",
                )
            )
    for snapshot_id in added_snapshots:
        if not _has_evidence(
            evidence,
            subject_kind="snapshot",
            subject_id=snapshot_id,
            evidence_kinds={"supersession", "event_continuity", "human_decision"},
        ):
            findings.append(
                _finding(
                    "latest_snapshot_changed_without_supersession_evidence",
                    "high",
                    snapshot_id,
                    "latest snapshot appeared without supersession or continuity evidence",
                )
            )
    for snapshot_id in removed_snapshots:
        if snapshot_id in after_review.snapshot_ids:
            findings.append(
                _finding(
                    "latest_snapshot_regressed",
                    "high",
                    snapshot_id,
                    "before latest snapshot is present after transition but no longer latest",
                )
            )
    if set(before_review.snapshot_thread_ids) != set(after_review.snapshot_thread_ids):
        findings.append(
            _finding(
                "snapshot_thread_regressed_or_forked",
                "high",
                "snapshot_thread",
                "snapshot thread set changed across transition",
            )
        )
    if runtime_adoption_review is not None and runtime_adoption_review.blocked_proposal_ids:
        for candidate_id in set(added_candidates) & set(runtime_adoption_review.blocked_proposal_ids):
            findings.append(
                _finding(
                    "transition_over_runtime_adoption_blocked",
                    "high",
                    candidate_id,
                    "transition introduced a candidate blocked by runtime adoption review",
                )
            )
    for bundle in action_review_bundles:
        if bundle.action_posture != "advisory_ready":
            findings.append(
                _finding(
                    "action_bundle_unresolved_during_transition",
                    "high",
                    bundle.observation.observation_id,
                    bundle.action_posture,
                )
            )
    for item in evidence:
        if _has_unqualified_authority_text(item.detail):
            findings.append(
                _finding(
                    "transition_evidence_claims_permission",
                    "high",
                    item.subject_id,
                    "transition evidence contains authority wording without a local negative marker",
                )
            )
        if item.subject_kind in {"session", "lock"} and any(
            token in item.detail.lower() for token in ("recovery authority", "lock recovered", "session recovered")
        ):
            findings.append(
                _finding(
                    "session_or_lock_transition_claims_recovery_authority",
                    "high",
                    item.subject_id,
                    "session or lock evidence claims recovery authority",
                )
            )
    return findings


def _review_status(findings: tuple[ControlPlaneRuntimeStateTransitionFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "runtime_state_transition_drift_observed"
    if findings:
        return "runtime_state_transition_review_required"
    return "runtime_state_transition_observed"


def build_control_plane_runtime_state_transition_review(
    before_review: ControlPlaneRuntimeStateReview,
    after_review: ControlPlaneRuntimeStateReview,
    *,
    transition_evidence_payloads: Iterable[Mapping[str, object]] = (),
    runtime_adoption_review: ControlPlaneRuntimeAdoptionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneRuntimeStateTransitionReview:
    """Review caller-supplied runtime-state review deltas without reconciling or scheduling."""

    evidence = _evidence_from_payloads(transition_evidence_payloads)
    bundles = _validate_supplied_review_guardrails(
        before_review=before_review,
        after_review=after_review,
        runtime_adoption_review=runtime_adoption_review,
        action_review_bundles=action_review_bundles,
    )
    added_latest, removed_latest = _set_delta(before_review.latest_snapshot_ids, after_review.latest_snapshot_ids)
    added_open_ready, removed_open_ready = _set_delta(
        before_review.open_ready_observation_ids,
        after_review.open_ready_observation_ids,
    )
    added_active, removed_active = _set_delta(before_review.active_observation_ids, after_review.active_observation_ids)
    added_decisions, removed_decisions = _set_delta(before_review.current_decision_ids, after_review.current_decision_ids)
    added_rules, removed_rules = _set_delta(before_review.active_rule_ids, after_review.active_rule_ids)
    added_candidates, removed_candidates = _set_delta(
        before_review.runtime_adoption_candidate_ids,
        after_review.runtime_adoption_candidate_ids,
    )
    findings = tuple(
        _review_findings(before_review, after_review)
        + _transition_findings(before_review, after_review, evidence, runtime_adoption_review, bundles)
    )
    review = ControlPlaneRuntimeStateTransitionReview(
        schema_version="1",
        review_role="reviews_caller_supplied_runtime_state_transitions_without_runtime_authority",
        review_status=_review_status(findings),
        before_review_as_of=before_review.review_as_of,
        after_review_as_of=after_review.review_as_of,
        transition_evidence_count=len(evidence),
        evidence_ids=tuple(item.evidence_id for item in evidence),
        before_latest_snapshot_ids=before_review.latest_snapshot_ids,
        after_latest_snapshot_ids=after_review.latest_snapshot_ids,
        added_latest_snapshot_ids=added_latest,
        removed_latest_snapshot_ids=removed_latest,
        added_open_ready_observation_ids=added_open_ready,
        removed_open_ready_observation_ids=removed_open_ready,
        added_active_observation_ids=added_active,
        removed_active_observation_ids=removed_active,
        added_current_decision_ids=added_decisions,
        removed_current_decision_ids=removed_decisions,
        added_active_rule_ids=added_rules,
        removed_active_rule_ids=removed_rules,
        added_runtime_adoption_candidate_ids=added_candidates,
        removed_runtime_adoption_candidate_ids=removed_candidates,
        before_review_status=before_review.review_status,
        after_review_status=after_review.review_status,
        runtime_adoption_review_status=runtime_adoption_review.review_status if runtime_adoption_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
        before_review=before_review,
        after_review=after_review,
    )
    _validate_review(review)
    return review


def _validate_review(review: ControlPlaneRuntimeStateTransitionReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneRuntimeStateTransitionReviewError("runtime-state transition review must have state_change none")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneRuntimeStateTransitionReviewError("runtime-state transition review must remain non-authoritative")
    if (
        not review.transition_review_is_not_permission
        or not review.observed_transition_is_not_truth
        or not review.observed_transition_is_not_scheduler
        or not review.transition_pass_is_not_execution_approval
        or not review.transition_review_is_not_state_store
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneRuntimeStateTransitionReviewError("runtime-state transition review guardrails drifted")
    if review.transition_evidence_count != len(review.evidence_ids):
        raise ControlPlaneRuntimeStateTransitionReviewError("transition_evidence_count must match evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneRuntimeStateTransitionReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneRuntimeStateTransitionReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneRuntimeStateTransitionReviewError("severity_counts must match findings")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneRuntimeStateTransitionReviewError("review_status must match findings")
    expected_added_latest, expected_removed_latest = _set_delta(
        review.before_latest_snapshot_ids,
        review.after_latest_snapshot_ids,
    )
    if review.added_latest_snapshot_ids != expected_added_latest:
        raise ControlPlaneRuntimeStateTransitionReviewError("added_latest_snapshot_ids must match before/after ids")
    if review.removed_latest_snapshot_ids != expected_removed_latest:
        raise ControlPlaneRuntimeStateTransitionReviewError("removed_latest_snapshot_ids must match before/after ids")
    if review.added_open_ready_observation_ids != _set_delta(
        review.before_review.open_ready_observation_ids,
        review.after_review.open_ready_observation_ids,
    )[0]:
        raise ControlPlaneRuntimeStateTransitionReviewError("added_open_ready_observation_ids must match before/after reviews")


def render_control_plane_runtime_state_transition_review_json(
    review: ControlPlaneRuntimeStateTransitionReview,
) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True) + "\n"


def render_control_plane_runtime_state_transition_review_markdown(
    review: ControlPlaneRuntimeStateTransitionReview,
) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Runtime State Transition Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane runtime state transition review only",
        "- transition_review_is_not_permission: true",
        "- observed_transition_is_not_truth: true",
        "- observed_transition_is_not_scheduler: true",
        "- transition_pass_is_not_execution_approval: true",
        "- transition_review_is_not_state_store: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- transition_evidence_count: {review.transition_evidence_count}",
        f"- added_latest_snapshot_ids: {', '.join(review.added_latest_snapshot_ids) if review.added_latest_snapshot_ids else 'none'}",
        f"- added_open_ready_observation_ids: {', '.join(review.added_open_ready_observation_ids) if review.added_open_ready_observation_ids else 'none'}",
        f"- added_runtime_adoption_candidate_ids: {', '.join(review.added_runtime_adoption_candidate_ids) if review.added_runtime_adoption_candidate_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
        "",
    ]
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(f"- {finding.severity}: {finding.code} [{finding.subject_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
