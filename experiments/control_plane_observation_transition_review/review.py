from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from experiments.control_plane_observation_set_review import (
    ControlPlaneObservationSetReview,
    build_control_plane_observation_set_review,
)


class ControlPlaneObservationTransitionReviewError(ValueError):
    """Raised when transition-review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneObservationTransitionEvidence:
    observation_id: str
    evidence_id: str
    evidence_kind: str
    human_decision: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneObservationTransitionFinding:
    code: str
    severity: str
    observation_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneObservationTransitionReview:
    schema_version: str
    review_role: str
    review_status: str
    before_observation_count: int
    after_observation_count: int
    transition_evidence_count: int
    before_observation_ids: tuple[str, ...]
    after_observation_ids: tuple[str, ...]
    added_observation_ids: tuple[str, ...]
    removed_observation_ids: tuple[str, ...]
    shared_observation_ids: tuple[str, ...]
    transitioned_observation_ids: tuple[str, ...]
    after_open_ready_observation_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneObservationTransitionFinding, ...]
    before_review: ControlPlaneObservationSetReview
    after_review: ControlPlaneObservationSetReview
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane observation transition review only"
    transition_review_is_not_permission: bool = True
    observed_transition_is_not_truth: bool = True
    observed_frontier_is_not_scheduler: bool = True
    transition_pass_is_not_execution_approval: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_EVIDENCE_KINDS = {
    "dependency_satisfaction",
    "formal_trigger_opened",
    "human_checkpoint",
    "resolution",
    "removal",
}
_OBSERVATION_FIELDS = (
    "id",
    "title",
    "status",
    "kind",
    "priority",
    "boundary",
    "trigger",
    "dependencies",
    "dependencies_satisfied",
    "auto_continuation",
    "next_action",
    "halt_if",
)
_CONTRACT_FIELDS = ("queue_authority", "single_flight", "overlap_policy")
_DRIFT_FIELDS = ("title", "kind", "priority", "boundary", "trigger", "dependencies", "next_action", "halt_if")
_FORBIDDEN_AUTHORITY_TOKENS = (
    "grants permission",
    "permission to execute",
    "execution approval",
    "scheduler",
    "schedules work",
    "runtime authority",
    "canonical gate",
    "truth signal",
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
        raise ControlPlaneObservationTransitionReviewError(f"missing required field: {field}")
    return value


def _as_str_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneObservationTransitionReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneObservationTransitionReviewError(f"{field} must contain only non-empty strings")
    return tuple(value)


def _observations_by_id(center_payload: Mapping[str, object]) -> dict[str, Mapping[str, object]]:
    observations = center_payload.get("observations")
    if not isinstance(observations, list):
        raise ControlPlaneObservationTransitionReviewError("center payload must include observations list")
    result: dict[str, Mapping[str, object]] = {}
    for payload in observations:
        if not isinstance(payload, Mapping):
            raise ControlPlaneObservationTransitionReviewError("observation payload must be a mapping")
        observation_id = _required_str(payload, "id")
        if not _is_path_segment_safe(observation_id):
            raise ControlPlaneObservationTransitionReviewError("observation id must be path-segment safe")
        if observation_id in result:
            raise ControlPlaneObservationTransitionReviewError(f"duplicate observation id: {observation_id}")
        for field in _OBSERVATION_FIELDS:
            if field not in payload:
                raise ControlPlaneObservationTransitionReviewError(f"missing observation field: {field}")
        if not isinstance(payload.get("dependencies_satisfied"), bool):
            raise ControlPlaneObservationTransitionReviewError("dependencies_satisfied must be boolean")
        if not isinstance(payload.get("auto_continuation"), bool):
            raise ControlPlaneObservationTransitionReviewError("auto_continuation must be boolean")
        _as_str_tuple(payload.get("dependencies"), "dependencies")
        result[observation_id] = payload
    return result


def _evidence_from_payload(payload: Mapping[str, object]) -> ControlPlaneObservationTransitionEvidence:
    if not isinstance(payload, Mapping):
        raise ControlPlaneObservationTransitionReviewError("transition evidence payload must be a mapping")
    observation_id = _required_str(payload, "observation_id")
    evidence_id = _required_str(payload, "evidence_id")
    if not _is_path_segment_safe(observation_id) or not _is_path_segment_safe(evidence_id):
        raise ControlPlaneObservationTransitionReviewError("transition evidence ids must be path-segment safe")
    evidence_kind = _required_str(payload, "evidence_kind")
    if evidence_kind not in _EVIDENCE_KINDS:
        raise ControlPlaneObservationTransitionReviewError(f"unknown transition evidence kind: {evidence_kind}")
    human_decision = _required_str(payload, "human_decision").strip()
    if not human_decision:
        raise ControlPlaneObservationTransitionReviewError("human_decision must be non-empty after trimming")
    return ControlPlaneObservationTransitionEvidence(
        observation_id=observation_id,
        evidence_id=evidence_id,
        evidence_kind=evidence_kind,
        human_decision=human_decision,
        detail=_required_str(payload, "detail"),
    )


def _evidence_from_payloads(payloads: Iterable[Mapping[str, object]]) -> tuple[ControlPlaneObservationTransitionEvidence, ...]:
    evidence = tuple(_evidence_from_payload(payload) for payload in payloads)
    ids = [item.evidence_id for item in evidence]
    duplicates = sorted({evidence_id for evidence_id in ids if ids.count(evidence_id) > 1})
    if duplicates:
        raise ControlPlaneObservationTransitionReviewError(f"duplicate transition evidence ids: {', '.join(duplicates)}")
    return evidence


def _has_evidence(
    evidence: tuple[ControlPlaneObservationTransitionEvidence, ...],
    observation_id: str,
    kinds: set[str],
) -> bool:
    for item in evidence:
        if item.observation_id != observation_id or item.evidence_kind not in kinds:
            continue
        if item.human_decision.strip().lower() in {"none", "automatic", "auto"}:
            continue
        return True
    return False


def _finding(
    code: str,
    severity: str,
    observation_id: str,
    detail: str,
) -> ControlPlaneObservationTransitionFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneObservationTransitionReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneObservationTransitionFinding(
        code=code,
        severity=severity,
        observation_id=observation_id,
        detail=detail,
    )


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneObservationTransitionReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneObservationTransitionReviewError(f"{label} authority contains forbidden claim: {token}")


def _validate_set_review(
    review: ControlPlaneObservationSetReview,
    label: str,
    expected_ids: tuple[str, ...],
    expected_review: ControlPlaneObservationSetReview,
) -> None:
    if review.state_change != "none":
        raise ControlPlaneObservationTransitionReviewError(f"{label} review must have state_change none")
    _validate_authority_text(review.authority, f"{label} review")
    if (
        not review.review_is_not_permission
        or not review.observation_frontier_is_not_scheduler
        or not review.advisory_posture_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneObservationTransitionReviewError(f"{label} review guardrails must remain true")
    if review.observation_ids != expected_ids:
        raise ControlPlaneObservationTransitionReviewError(f"{label} review observation ids must match payload")
    if asdict(review) != asdict(expected_review):
        raise ControlPlaneObservationTransitionReviewError(f"{label} review must be derived from the supplied payload")


def _review_findings(
    before_review: ControlPlaneObservationSetReview,
    after_review: ControlPlaneObservationSetReview,
) -> list[ControlPlaneObservationTransitionFinding]:
    findings: list[ControlPlaneObservationTransitionFinding] = []
    if before_review.review_status == "observation_set_contract_drift_observed":
        findings.append(
            _finding(
                "before_snapshot_contract_drift",
                "high",
                "before",
                "before observation-set review already reports high-severity contract drift",
            )
        )
    elif before_review.finding_count:
        findings.append(
            _finding(
                "before_snapshot_review_required",
                "medium",
                "before",
                "before observation-set review carries findings that must remain visible",
            )
        )
    if after_review.review_status == "observation_set_contract_drift_observed":
        findings.append(
            _finding(
                "after_snapshot_contract_drift",
                "high",
                "after",
                "after observation-set review reports high-severity contract drift",
            )
        )
    elif after_review.finding_count:
        findings.append(
            _finding(
                "after_snapshot_review_required",
                "medium",
                "after",
                "after observation-set review carries findings that must remain visible",
            )
        )
    return findings


def _contract_findings(
    before_center_payload: Mapping[str, object],
    after_center_payload: Mapping[str, object],
) -> list[ControlPlaneObservationTransitionFinding]:
    findings: list[ControlPlaneObservationTransitionFinding] = []
    for field in _CONTRACT_FIELDS:
        if before_center_payload.get(field) != after_center_payload.get(field):
            findings.append(
                _finding(
                    "queue_contract_field_changed",
                    "high",
                    "center",
                    f"{field} changed across supplied snapshots",
                )
            )
    return findings


def _is_open_ready(payload: Mapping[str, object]) -> bool:
    return (
        payload.get("status") == "open"
        and payload.get("dependencies_satisfied") is True
        and payload.get("auto_continuation") is False
        and "not open" not in str(payload.get("trigger", "")).lower()
    )


def _transition_findings(
    before_by_id: Mapping[str, Mapping[str, object]],
    after_by_id: Mapping[str, Mapping[str, object]],
    evidence: tuple[ControlPlaneObservationTransitionEvidence, ...],
    single_flight: bool,
) -> list[ControlPlaneObservationTransitionFinding]:
    findings: list[ControlPlaneObservationTransitionFinding] = []
    before_ids = set(before_by_id)
    after_ids = set(after_by_id)

    for observation_id in sorted(before_ids - after_ids):
        before = before_by_id[observation_id]
        if before.get("status") != "resolved" and not _has_evidence(evidence, observation_id, {"removal", "resolution"}):
            findings.append(
                _finding(
                    "unresolved_observation_disappeared",
                    "high",
                    observation_id,
                    "unresolved observation disappeared without caller-supplied removal or resolution evidence",
                )
            )

    for observation_id in sorted(after_ids - before_ids):
        after = after_by_id[observation_id]
        if _is_open_ready(after) and not _has_evidence(evidence, observation_id, {"formal_trigger_opened", "human_checkpoint"}):
            findings.append(
                _finding(
                    "new_open_ready_observation_without_evidence",
                    "high",
                    observation_id,
                    "new open-ready observation appeared without caller-supplied trigger or human checkpoint evidence",
                )
            )

    for observation_id in sorted(before_ids & after_ids):
        before = before_by_id[observation_id]
        after = after_by_id[observation_id]
        drifted_fields = tuple(field for field in _DRIFT_FIELDS if before.get(field) != after.get(field))
        if drifted_fields:
            findings.append(
                _finding(
                    "observation_payload_drift_across_transition",
                    "high" if any(field in drifted_fields for field in ("boundary", "trigger", "dependencies", "halt_if")) else "medium",
                    observation_id,
                    f"observation fields changed across snapshots: {', '.join(drifted_fields)}",
                )
            )
        if before.get("auto_continuation") is False and after.get("auto_continuation") is True:
            findings.append(
                _finding(
                    "auto_continuation_introduced",
                    "high",
                    observation_id,
                    "auto_continuation became true across supplied snapshots",
                )
            )
        if before.get("dependencies_satisfied") is False and after.get("dependencies_satisfied") is True:
            if not _has_evidence(evidence, observation_id, {"dependency_satisfaction", "human_checkpoint"}):
                findings.append(
                    _finding(
                        "silent_dependency_satisfaction",
                        "high",
                        observation_id,
                        "dependencies_satisfied changed from false to true without caller-supplied evidence",
                    )
                )
        before_status = str(before.get("status"))
        after_status = str(after.get("status"))
        if before_status in {"waiting", "blocked"} and after_status == "open":
            if not _has_evidence(evidence, observation_id, {"formal_trigger_opened", "dependency_satisfaction", "human_checkpoint"}):
                findings.append(
                    _finding(
                        "silent_readiness_promotion",
                        "high",
                        observation_id,
                        f"status changed from {before_status} to open without caller-supplied transition evidence",
                    )
                )
        if before_status != "resolved" and after_status == "resolved":
            if not _has_evidence(evidence, observation_id, {"resolution", "human_checkpoint"}):
                findings.append(
                    _finding(
                        "resolved_without_transition_evidence",
                        "high",
                        observation_id,
                        "observation became resolved without caller-supplied resolution evidence",
                    )
                )
        if before_status == "resolved" and after_status != "resolved":
            findings.append(
                _finding(
                    "resolved_observation_reopened",
                    "high",
                    observation_id,
                    "resolved observation reappeared as unresolved across supplied snapshots",
                )
            )

    after_open_ready = tuple(observation_id for observation_id, payload in after_by_id.items() if _is_open_ready(payload))
    if single_flight and len(after_open_ready) > 1:
        findings.append(
            _finding(
                "multiple_open_ready_after_transition_under_single_flight",
                "high",
                "center",
                f"after snapshot has multiple open-ready observations under single_flight: {', '.join(after_open_ready)}",
            )
        )
    return findings


def _transitioned_ids(
    before_by_id: Mapping[str, Mapping[str, object]],
    after_by_id: Mapping[str, Mapping[str, object]],
) -> tuple[str, ...]:
    ids: list[str] = []
    for observation_id in sorted(set(before_by_id) & set(after_by_id)):
        before = before_by_id[observation_id]
        after = after_by_id[observation_id]
        if any(before.get(field) != after.get(field) for field in _OBSERVATION_FIELDS if field != "id"):
            ids.append(observation_id)
    return tuple(ids)


def _review_status(findings: tuple[ControlPlaneObservationTransitionFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "observation_transition_drift_observed"
    if findings:
        return "observation_transition_review_required"
    return "observation_transition_contract_observed"


def _validate_review(review: ControlPlaneObservationTransitionReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneObservationTransitionReviewError("transition review must have state_change none")
    _validate_authority_text(review.authority, "transition review")
    if (
        not review.transition_review_is_not_permission
        or not review.observed_transition_is_not_truth
        or not review.observed_frontier_is_not_scheduler
        or not review.transition_pass_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneObservationTransitionReviewError("transition review guardrails must remain true")
    if review.before_observation_count != len(review.before_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("before_observation_count must match before_observation_ids")
    if review.after_observation_count != len(review.after_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("after_observation_count must match after_observation_ids")
    if review.transition_evidence_count != len(review.evidence_ids):
        raise ControlPlaneObservationTransitionReviewError("transition_evidence_count must match evidence_ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneObservationTransitionReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneObservationTransitionReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneObservationTransitionReviewError("severity_counts must match findings")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneObservationTransitionReviewError("review_status must match findings")
    expected_added = tuple(sorted(set(review.after_observation_ids) - set(review.before_observation_ids)))
    expected_removed = tuple(sorted(set(review.before_observation_ids) - set(review.after_observation_ids)))
    expected_shared = tuple(sorted(set(review.before_observation_ids) & set(review.after_observation_ids)))
    if review.added_observation_ids != expected_added:
        raise ControlPlaneObservationTransitionReviewError("added_observation_ids must match before/after ids")
    if review.removed_observation_ids != expected_removed:
        raise ControlPlaneObservationTransitionReviewError("removed_observation_ids must match before/after ids")
    if review.shared_observation_ids != expected_shared:
        raise ControlPlaneObservationTransitionReviewError("shared_observation_ids must match before/after ids")
    if any(item not in review.before_observation_ids for item in review.removed_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("removed observations must come from before ids")
    if any(item not in review.after_observation_ids for item in review.added_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("added observations must come from after ids")
    if any(item not in review.shared_observation_ids for item in review.transitioned_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("transitioned observations must be shared before/after ids")
    if len(set(review.transitioned_observation_ids)) != len(review.transitioned_observation_ids):
        raise ControlPlaneObservationTransitionReviewError("transitioned_observation_ids must be unique")
    if review.after_open_ready_observation_ids != review.after_review.open_ready_observation_ids:
        raise ControlPlaneObservationTransitionReviewError("after_open_ready_observation_ids must match after review")


def build_control_plane_observation_transition_review(
    before_center_payload: Mapping[str, object],
    after_center_payload: Mapping[str, object],
    *,
    transition_evidence: Iterable[Mapping[str, object]] = (),
    before_review: ControlPlaneObservationSetReview | None = None,
    after_review: ControlPlaneObservationSetReview | None = None,
) -> ControlPlaneObservationTransitionReview:
    """Compare two caller-supplied observation-center snapshots without scheduling work."""

    before_by_id = _observations_by_id(before_center_payload)
    after_by_id = _observations_by_id(after_center_payload)
    evidence = _evidence_from_payloads(transition_evidence)
    before_ids = tuple(before_by_id)
    after_ids = tuple(after_by_id)
    expected_before_review = build_control_plane_observation_set_review(before_center_payload)
    expected_after_review = build_control_plane_observation_set_review(after_center_payload)
    built_before_review = before_review or expected_before_review
    built_after_review = after_review or expected_after_review
    _validate_set_review(built_before_review, "before", before_ids, expected_before_review)
    _validate_set_review(built_after_review, "after", after_ids, expected_after_review)
    findings = tuple(
        _review_findings(built_before_review, built_after_review)
        + _contract_findings(before_center_payload, after_center_payload)
        + _transition_findings(
            before_by_id,
            after_by_id,
            evidence,
            after_center_payload.get("single_flight") is True,
        )
    )
    review = ControlPlaneObservationTransitionReview(
        schema_version="1",
        review_role="reviews_caller_supplied_observation_center_transitions_without_scheduling",
        review_status=_review_status(findings),
        before_observation_count=len(before_ids),
        after_observation_count=len(after_ids),
        transition_evidence_count=len(evidence),
        before_observation_ids=before_ids,
        after_observation_ids=after_ids,
        added_observation_ids=tuple(sorted(set(after_ids) - set(before_ids))),
        removed_observation_ids=tuple(sorted(set(before_ids) - set(after_ids))),
        shared_observation_ids=tuple(sorted(set(before_ids) & set(after_ids))),
        transitioned_observation_ids=_transitioned_ids(before_by_id, after_by_id),
        after_open_ready_observation_ids=tuple(
            observation_id for observation_id, payload in after_by_id.items() if _is_open_ready(payload)
        ),
        evidence_ids=tuple(item.evidence_id for item in evidence),
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
        before_review=built_before_review,
        after_review=built_after_review,
    )
    _validate_review(review)
    return review


def render_control_plane_observation_transition_review_json(review: ControlPlaneObservationTransitionReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_observation_transition_review_markdown(review: ControlPlaneObservationTransitionReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Observation Transition Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane observation transition review only",
        "- transition_review_is_not_permission: true",
        "- observed_transition_is_not_truth: true",
        "- observed_frontier_is_not_scheduler: true",
        "- transition_pass_is_not_execution_approval: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- before_observation_count: {review.before_observation_count}",
        f"- after_observation_count: {review.after_observation_count}",
        f"- transition_evidence_count: {review.transition_evidence_count}",
        f"- added_observation_ids: {', '.join(review.added_observation_ids) if review.added_observation_ids else 'none'}",
        f"- removed_observation_ids: {', '.join(review.removed_observation_ids) if review.removed_observation_ids else 'none'}",
        f"- transitioned_observation_ids: {', '.join(review.transitioned_observation_ids) if review.transitioned_observation_ids else 'none'}",
        f"- after_open_ready_observation_ids: {', '.join(review.after_open_ready_observation_ids) if review.after_open_ready_observation_ids else 'none'}",
        f"- evidence_ids: {', '.join(review.evidence_ids) if review.evidence_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
        "",
    ]
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(f"- {finding.severity}: {finding.code} [{finding.observation_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
