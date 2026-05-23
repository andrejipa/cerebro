from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_handoff_review import ControlPlaneHandoffReview
from experiments.control_plane_observation_transition_review import ControlPlaneObservationTransitionReview


class ControlPlaneDecisionVersionReviewError(ValueError):
    """Raised when decision-version-review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneDecisionRecord:
    decision_id: str
    decision_thread_id: str
    observation_id: str
    revision: int
    decision_kind: str
    status: str
    decided_by: str
    decided_at: str
    valid_until: str
    supersedes_decision_id: str
    human_decision_id: str
    referenced_evidence_ids: tuple[str, ...]
    auto_continue: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneDecisionVersionFinding:
    code: str
    severity: str
    decision_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneDecisionVersionReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    decision_count: int
    decision_thread_count: int
    current_decision_ids: tuple[str, ...]
    non_current_decision_ids: tuple[str, ...]
    decision_ids: tuple[str, ...]
    decision_thread_ids: tuple[str, ...]
    handoff_status: str
    transition_status: str
    action_bundle_count: int
    referenced_evidence_count: int
    referenced_evidence_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneDecisionVersionFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane decision version review only"
    decision_review_is_not_permission: bool = True
    decision_current_is_not_execution_approval: bool = True
    decision_record_is_not_truth: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_DECISION_KINDS = {
    "approval",
    "rejection",
    "human_checkpoint",
    "scope_change",
    "evidence_acceptance",
    "evidence_rejection",
    "blocker",
    "supersession",
    "review_note",
}
_STATUSES = {"draft", "current", "superseded", "expired", "rejected", "revoked"}
_HUMAN_REQUIRED_KINDS = {
    "approval",
    "rejection",
    "human_checkpoint",
    "scope_change",
    "evidence_acceptance",
    "evidence_rejection",
}
_FORBIDDEN_AUTHORITY_TOKENS = (
    "grants permission",
    "permission to execute",
    "execution approval",
    "execution approved",
    "permission_granted",
    "scheduler",
    "schedules work",
    "runtime authority",
    "runtime_authority",
    "canonical gate",
    "truth signal",
    "ready to execute",
    "approved to run",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not a scheduler",
    "non-authoritative",
    "must not execute",
    "does not grant",
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
        raise ControlPlaneDecisionVersionReviewError(f"missing required decision field: {field}")
    return value


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneDecisionVersionReviewError(f"{field} must be a string")
    return value.strip()


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneDecisionVersionReviewError(f"{field} must be an ISO date") from exc


def _as_evidence_ids(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneDecisionVersionReviewError("referenced_evidence_ids must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneDecisionVersionReviewError("referenced_evidence_ids must contain only non-empty strings")
    ids = tuple(value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneDecisionVersionReviewError("referenced evidence ids must be path-segment safe")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ControlPlaneDecisionVersionReviewError(f"duplicate referenced evidence ids: {', '.join(duplicates)}")
    return ids


def _decision_from_payload(payload: Mapping[str, object]) -> ControlPlaneDecisionRecord:
    if not isinstance(payload, Mapping):
        raise ControlPlaneDecisionVersionReviewError("decision payload must be a mapping")
    decision_id = _required_str(payload, "decision_id")
    thread_id = _required_str(payload, "decision_thread_id")
    observation_id = _required_str(payload, "observation_id")
    for field, value in (
        ("decision_id", decision_id),
        ("decision_thread_id", thread_id),
        ("observation_id", observation_id),
    ):
        if not _is_path_segment_safe(value):
            raise ControlPlaneDecisionVersionReviewError(f"{field} must be path-segment safe")
    revision = payload.get("revision")
    if not isinstance(revision, int) or revision < 1:
        raise ControlPlaneDecisionVersionReviewError("revision must be a positive integer")
    decision_kind = _required_str(payload, "decision_kind")
    if decision_kind not in _DECISION_KINDS:
        raise ControlPlaneDecisionVersionReviewError(f"unknown decision_kind: {decision_kind}")
    status = _required_str(payload, "status")
    if status not in _STATUSES:
        raise ControlPlaneDecisionVersionReviewError(f"unknown decision status: {status}")
    decided_at = _required_str(payload, "decided_at")
    _parse_date(decided_at, "decided_at")
    valid_until = _optional_str(payload, "valid_until")
    if valid_until:
        _parse_date(valid_until, "valid_until")
    supersedes = _optional_str(payload, "supersedes_decision_id")
    if supersedes and not _is_path_segment_safe(supersedes):
        raise ControlPlaneDecisionVersionReviewError("supersedes_decision_id must be path-segment safe")
    human_decision_id = _optional_str(payload, "human_decision_id")
    if human_decision_id and not _is_path_segment_safe(human_decision_id):
        raise ControlPlaneDecisionVersionReviewError("human_decision_id must be path-segment safe")
    auto_continue = payload.get("auto_continue")
    if not isinstance(auto_continue, bool):
        raise ControlPlaneDecisionVersionReviewError("auto_continue must be boolean")
    return ControlPlaneDecisionRecord(
        decision_id=decision_id,
        decision_thread_id=thread_id,
        observation_id=observation_id,
        revision=revision,
        decision_kind=decision_kind,
        status=status,
        decided_by=_required_str(payload, "decided_by").strip(),
        decided_at=decided_at,
        valid_until=valid_until,
        supersedes_decision_id=supersedes,
        human_decision_id=human_decision_id,
        referenced_evidence_ids=_as_evidence_ids(payload.get("referenced_evidence_ids")),
        auto_continue=auto_continue,
        summary=_required_str(payload, "summary"),
        rationale=_required_str(payload, "rationale"),
    )


def _decision_records_from_payloads(payloads: Iterable[Mapping[str, object]]) -> tuple[ControlPlaneDecisionRecord, ...]:
    records = tuple(_decision_from_payload(payload) for payload in payloads)
    ids = [record.decision_id for record in records]
    duplicates = sorted({decision_id for decision_id in ids if ids.count(decision_id) > 1})
    if duplicates:
        raise ControlPlaneDecisionVersionReviewError(f"duplicate decision ids: {', '.join(duplicates)}")
    thread_revisions = [(record.decision_thread_id, record.revision) for record in records]
    duplicate_revisions = sorted({item for item in thread_revisions if thread_revisions.count(item) > 1})
    if duplicate_revisions:
        formatted = ", ".join(f"{thread}:{revision}" for thread, revision in duplicate_revisions)
        raise ControlPlaneDecisionVersionReviewError(f"duplicate decision thread revisions: {formatted}")
    return records


def _finding(code: str, severity: str, decision_id: str, detail: str) -> ControlPlaneDecisionVersionFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneDecisionVersionReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneDecisionVersionFinding(code=code, severity=severity, decision_id=decision_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneDecisionVersionReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneDecisionVersionReviewError(f"{label} authority contains forbidden claim: {token}")


def _validate_handoff_review(review: ControlPlaneHandoffReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneDecisionVersionReviewError("handoff review must have state_change none")
    _validate_authority_text(review.authority, "handoff review")
    if (
        not review.handoff_review_is_not_permission
        or not review.handoff_is_not_scheduler
        or not review.handoff_is_not_execution_approval
        or not review.observed_frontier_is_not_scheduler
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneDecisionVersionReviewError("handoff review guardrails must remain true")
    if review.finding_count != len(review.findings):
        raise ControlPlaneDecisionVersionReviewError("handoff review finding_count must match findings")


def _validate_transition_review(review: ControlPlaneObservationTransitionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneDecisionVersionReviewError("transition review must have state_change none")
    _validate_authority_text(review.authority, "transition review")
    if (
        not review.transition_review_is_not_permission
        or not review.observed_transition_is_not_truth
        or not review.observed_frontier_is_not_scheduler
        or not review.transition_pass_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneDecisionVersionReviewError("transition review guardrails must remain true")
    if review.finding_count != len(review.findings):
        raise ControlPlaneDecisionVersionReviewError("transition review finding_count must match findings")


def _validate_action_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneDecisionVersionReviewError("action-review bundle must have state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneDecisionVersionReviewError("action-review bundle guardrails must remain true")


def _thread_findings(records: tuple[ControlPlaneDecisionRecord, ...]) -> list[ControlPlaneDecisionVersionFinding]:
    findings: list[ControlPlaneDecisionVersionFinding] = []
    by_thread: dict[str, list[ControlPlaneDecisionRecord]] = {}
    for record in records:
        by_thread.setdefault(record.decision_thread_id, []).append(record)
    by_id = {record.decision_id: record for record in records}
    for thread_records in by_thread.values():
        ordered = sorted(thread_records, key=lambda item: item.revision)
        expected = list(range(1, max(item.revision for item in ordered) + 1))
        actual = [item.revision for item in ordered]
        if actual != expected:
            findings.append(
                _finding(
                    "decision_revision_gap",
                    "high",
                    ordered[-1].decision_id,
                    f"decision thread {ordered[-1].decision_thread_id} revisions are {actual}, expected contiguous {expected}",
                )
            )
        current = [item for item in ordered if item.status == "current"]
        if len(current) > 1:
            findings.append(
                _finding(
                    "multiple_current_decisions_in_thread",
                    "high",
                    current[-1].decision_id,
                    f"decision thread {current[-1].decision_thread_id} has multiple current revisions",
                )
            )
        if current and current[0].revision != max(item.revision for item in ordered):
            findings.append(
                _finding(
                    "current_decision_not_latest_revision",
                    "high",
                    current[0].decision_id,
                    "current decision is not the latest revision in its decision thread",
                )
            )
        for record in ordered:
            if record.revision > 1 and not record.supersedes_decision_id:
                findings.append(
                    _finding(
                        "decision_revision_missing_supersedes",
                        "medium",
                        record.decision_id,
                        "revision greater than one does not identify the prior decision it supersedes",
                    )
                )
            if record.supersedes_decision_id and record.supersedes_decision_id not in by_id:
                findings.append(
                    _finding(
                        "decision_supersedes_unknown_id",
                        "high",
                        record.decision_id,
                        f"decision supersedes unknown id {record.supersedes_decision_id}",
                    )
                )
            if record.supersedes_decision_id:
                superseded = by_id.get(record.supersedes_decision_id)
                if superseded is not None and superseded.decision_thread_id != record.decision_thread_id:
                    findings.append(
                        _finding(
                            "decision_supersedes_cross_thread",
                            "high",
                            record.decision_id,
                            "decision supersedes an id from a different decision thread",
                        )
                    )
    return findings


def _record_findings(records: tuple[ControlPlaneDecisionRecord, ...], review_as_of: str) -> list[ControlPlaneDecisionVersionFinding]:
    findings: list[ControlPlaneDecisionVersionFinding] = []
    as_of = _parse_date(review_as_of, "review_as_of")
    for record in records:
        if record.status == "current" and record.valid_until and _parse_date(record.valid_until, "valid_until") < as_of:
            findings.append(
                _finding(
                    "current_decision_expired",
                    "high",
                    record.decision_id,
                    f"current decision expired at {record.valid_until} before review_as_of {review_as_of}",
                )
            )
        if record.decision_kind in _HUMAN_REQUIRED_KINDS and record.status == "current":
            if record.human_decision_id.strip().lower() in {"", "none", "automatic", "auto"}:
                findings.append(
                    _finding(
                        "current_decision_missing_human_decision",
                        "high",
                        record.decision_id,
                        f"current {record.decision_kind} decision lacks a human_decision_id",
                    )
                )
        if record.auto_continue:
            findings.append(
                _finding(
                    "decision_requests_auto_continue",
                    "high",
                    record.decision_id,
                    "decision record requested automatic continuation",
                )
            )
        for field_name, text in (("summary", record.summary), ("rationale", record.rationale)):
            lowered = text.lower()
            has_negative_marker = any(marker in lowered for marker in _NEGATIVE_TEXT_MARKERS)
            for token in _FORBIDDEN_AUTHORITY_TOKENS:
                if token in lowered and not has_negative_marker:
                    findings.append(
                        _finding(
                            "decision_text_launders_authority",
                            "high",
                            record.decision_id,
                            f"{field_name} contains forbidden decision wording: {token}",
                        )
                    )
    return findings


def _integration_findings(
    records: tuple[ControlPlaneDecisionRecord, ...],
    handoff_review: ControlPlaneHandoffReview | None,
    transition_review: ControlPlaneObservationTransitionReview | None,
    action_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> list[ControlPlaneDecisionVersionFinding]:
    findings: list[ControlPlaneDecisionVersionFinding] = []
    by_id = {record.decision_id: record for record in records}
    current_by_observation = {
        record.observation_id: record
        for record in records
        if record.status == "current" and record.decision_kind in _HUMAN_REQUIRED_KINDS
    }
    current_approvals = [record for record in records if record.status == "current" and record.decision_kind == "approval"]

    if handoff_review is not None:
        referenced = set(handoff_review.referenced_evidence_ids)
        stale_references = sorted(decision_id for decision_id in referenced if decision_id in by_id and by_id[decision_id].status != "current")
        for decision_id in stale_references:
            findings.append(
                _finding(
                    "handoff_references_non_current_decision",
                    "high",
                    decision_id,
                    "handoff references a decision id that is not current",
                )
            )
        readyish_handoff = (
            handoff_review.handoff.handoff_status != "context_only"
            or handoff_review.handoff.claimed_next_posture not in {"no_action", "blocked"}
        )
        if readyish_handoff and handoff_review.handoff.required_human_decision not in {"", "none"}:
            current = current_by_observation.get(handoff_review.handoff.observation_id)
            if current is None or (current.decision_id not in referenced and current.human_decision_id not in referenced):
                findings.append(
                    _finding(
                        "handoff_missing_current_decision_reference",
                        "medium",
                        handoff_review.handoff.handoff_id,
                        "handoff requires a human decision but does not reference the current decision id or human_decision_id",
                    )
                )
        if handoff_review.review_status == "handoff_drift_observed":
            for record in current_approvals:
                findings.append(
                    _finding(
                        "current_approval_over_handoff_drift",
                        "high",
                        record.decision_id,
                        "current approval exists while handoff review reports drift",
                    )
                )

    if transition_review is not None and transition_review.review_status == "observation_transition_drift_observed":
        for record in current_approvals:
            findings.append(
                _finding(
                    "current_approval_over_transition_drift",
                    "high",
                    record.decision_id,
                    "current approval exists while observation-transition review reports drift",
                )
            )

    for bundle in action_bundles:
        if bundle.recommended_human_decision != "none" and bundle.observation.observation_id not in current_by_observation:
            findings.append(
                _finding(
                    "action_required_human_decision_unresolved",
                    "high",
                    bundle.observation.observation_id,
                    f"action bundle requires {bundle.recommended_human_decision} without a current human decision record",
                )
            )
    return findings


def _review_status(findings: tuple[ControlPlaneDecisionVersionFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "decision_version_drift_observed"
    if findings:
        return "decision_version_review_required"
    return "decision_version_contract_observed"


def _validate_review(review: ControlPlaneDecisionVersionReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneDecisionVersionReviewError("decision-version review must have state_change none")
    _validate_authority_text(review.authority, "decision-version review")
    if (
        not review.decision_review_is_not_permission
        or not review.decision_current_is_not_execution_approval
        or not review.decision_record_is_not_truth
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneDecisionVersionReviewError("decision-version review guardrails must remain true")
    if review.decision_count != len(review.decision_ids):
        raise ControlPlaneDecisionVersionReviewError("decision_count must match decision_ids")
    if review.decision_thread_count != len(review.decision_thread_ids):
        raise ControlPlaneDecisionVersionReviewError("decision_thread_count must match decision_thread_ids")
    if review.referenced_evidence_count != len(review.referenced_evidence_ids):
        raise ControlPlaneDecisionVersionReviewError("referenced_evidence_count must match referenced_evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneDecisionVersionReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneDecisionVersionReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneDecisionVersionReviewError("severity_counts must match findings")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneDecisionVersionReviewError("review_status must match findings")
    if any(item not in review.decision_ids for item in review.current_decision_ids):
        raise ControlPlaneDecisionVersionReviewError("current_decision_ids must be a subset of decision_ids")
    if any(item not in review.decision_ids for item in review.non_current_decision_ids):
        raise ControlPlaneDecisionVersionReviewError("non_current_decision_ids must be a subset of decision_ids")


def build_control_plane_decision_version_review(
    decision_payloads: Iterable[Mapping[str, object]],
    *,
    review_as_of: str,
    handoff_review: ControlPlaneHandoffReview | None = None,
    transition_review: ControlPlaneObservationTransitionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneDecisionVersionReview:
    """Review caller-supplied decision versions without storing or applying them."""

    _parse_date(review_as_of, "review_as_of")
    records = _decision_records_from_payloads(decision_payloads)
    _validate_handoff_review(handoff_review)
    _validate_transition_review(transition_review)
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        _validate_action_bundle(bundle)
    findings = tuple(
        _thread_findings(records)
        + _record_findings(records, review_as_of)
        + _integration_findings(records, handoff_review, transition_review, bundles)
    )
    referenced_evidence_ids = tuple(
        sorted({evidence_id for record in records for evidence_id in record.referenced_evidence_ids})
    )
    review = ControlPlaneDecisionVersionReview(
        schema_version="1",
        review_role="reviews_caller_supplied_decision_versions_without_storing_or_applying_them",
        review_status=_review_status(findings),
        review_as_of=review_as_of,
        decision_count=len(records),
        decision_thread_count=len({record.decision_thread_id for record in records}),
        current_decision_ids=tuple(record.decision_id for record in records if record.status == "current"),
        non_current_decision_ids=tuple(record.decision_id for record in records if record.status != "current"),
        decision_ids=tuple(record.decision_id for record in records),
        decision_thread_ids=tuple(sorted({record.decision_thread_id for record in records})),
        handoff_status=handoff_review.review_status if handoff_review is not None else "not_supplied",
        transition_status=transition_review.review_status if transition_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        referenced_evidence_count=len(referenced_evidence_ids),
        referenced_evidence_ids=referenced_evidence_ids,
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_decision_version_review_json(review: ControlPlaneDecisionVersionReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_decision_version_review_markdown(review: ControlPlaneDecisionVersionReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Decision Version Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane decision version review only",
        "- decision_review_is_not_permission: true",
        "- decision_current_is_not_execution_approval: true",
        "- decision_record_is_not_truth: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- review_as_of: {review.review_as_of}",
        f"- decision_count: {review.decision_count}",
        f"- decision_thread_count: {review.decision_thread_count}",
        f"- current_decision_ids: {', '.join(review.current_decision_ids) if review.current_decision_ids else 'none'}",
        f"- non_current_decision_ids: {', '.join(review.non_current_decision_ids) if review.non_current_decision_ids else 'none'}",
        f"- handoff_status: {review.handoff_status}",
        f"- transition_status: {review.transition_status}",
        f"- action_bundle_count: {review.action_bundle_count}",
        f"- referenced_evidence_ids: {', '.join(review.referenced_evidence_ids) if review.referenced_evidence_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
        "",
    ]
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(f"- {finding.severity}: {finding.code} [{finding.decision_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
