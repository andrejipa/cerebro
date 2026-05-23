from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle
from experiments.control_plane_observation_set_review import ControlPlaneObservationSetReview
from experiments.control_plane_observation_transition_review import ControlPlaneObservationTransitionReview


class ControlPlaneHandoffReviewError(ValueError):
    """Raised when handoff-review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneHandoffClaim:
    handoff_id: str
    source_role: str
    target_role: str
    observation_id: str
    handoff_status: str
    claimed_next_posture: str
    claimed_transition_status: str
    required_human_decision: str
    auto_continue: bool
    referenced_evidence_ids: tuple[str, ...]
    summary: str
    stop_condition: str


@dataclass(frozen=True)
class ControlPlaneHandoffFinding:
    code: str
    severity: str
    observation_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneHandoffReview:
    schema_version: str
    review_role: str
    review_status: str
    handoff: ControlPlaneHandoffClaim
    observation_set_status: str
    transition_status: str
    action_bundle_count: int
    matching_action_bundle_ids: tuple[str, ...]
    referenced_evidence_count: int
    referenced_evidence_ids: tuple[str, ...]
    observed_frontier_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneHandoffFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane handoff review only"
    handoff_review_is_not_permission: bool = True
    handoff_is_not_scheduler: bool = True
    handoff_is_not_execution_approval: bool = True
    observed_frontier_is_not_scheduler: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_HANDOFF_STATUSES = {
    "context_only",
    "blocked",
    "needs_human_checkpoint",
    "review_required",
    "ready_for_review",
    "claimed_ready",
}
_NEXT_POSTURES = {
    "no_action",
    "blocked",
    "human_checkpoint",
    "advisory_review_only",
    "implementation_ready",
}
_TRANSITION_CLAIMS = {"not_evaluated", "blocked", "review_required", "clean"}
_READY_STATUSES = {"ready_for_review", "claimed_ready"}
_READY_POSTURES = {"advisory_review_only", "implementation_ready"}
_BLOCKED_ACTION_POSTURES = {
    "waiting_checkpoint_blocked",
    "blocked_by_boundary",
    "blocked_by_integrity_drift",
    "blocked_by_review",
    "human_review_required",
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
    "not a permission",
    "not execution approval",
    "not a scheduler",
    "not scheduler",
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
        raise ControlPlaneHandoffReviewError(f"missing required handoff field: {field}")
    return value


def _as_evidence_ids(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneHandoffReviewError("referenced_evidence_ids must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneHandoffReviewError("referenced_evidence_ids must contain only non-empty strings")
    ids = tuple(value)
    if any(not _is_path_segment_safe(item) for item in ids):
        raise ControlPlaneHandoffReviewError("referenced evidence ids must be path-segment safe")
    duplicates = sorted({item for item in ids if ids.count(item) > 1})
    if duplicates:
        raise ControlPlaneHandoffReviewError(f"duplicate referenced evidence ids: {', '.join(duplicates)}")
    return ids


def _handoff_from_payload(payload: Mapping[str, object]) -> ControlPlaneHandoffClaim:
    if not isinstance(payload, Mapping):
        raise ControlPlaneHandoffReviewError("handoff payload must be a mapping")
    handoff_id = _required_str(payload, "handoff_id")
    source_role = _required_str(payload, "source_role")
    target_role = _required_str(payload, "target_role")
    observation_id = _required_str(payload, "observation_id")
    for field, value in (
        ("handoff_id", handoff_id),
        ("source_role", source_role),
        ("target_role", target_role),
        ("observation_id", observation_id),
    ):
        if not _is_path_segment_safe(value):
            raise ControlPlaneHandoffReviewError(f"{field} must be path-segment safe")
    handoff_status = _required_str(payload, "handoff_status")
    if handoff_status not in _HANDOFF_STATUSES:
        raise ControlPlaneHandoffReviewError(f"unknown handoff_status: {handoff_status}")
    claimed_next_posture = _required_str(payload, "claimed_next_posture")
    if claimed_next_posture not in _NEXT_POSTURES:
        raise ControlPlaneHandoffReviewError(f"unknown claimed_next_posture: {claimed_next_posture}")
    claimed_transition_status = _required_str(payload, "claimed_transition_status")
    if claimed_transition_status not in _TRANSITION_CLAIMS:
        raise ControlPlaneHandoffReviewError(f"unknown claimed_transition_status: {claimed_transition_status}")
    auto_continue = payload.get("auto_continue")
    if not isinstance(auto_continue, bool):
        raise ControlPlaneHandoffReviewError("auto_continue must be boolean")
    return ControlPlaneHandoffClaim(
        handoff_id=handoff_id,
        source_role=source_role,
        target_role=target_role,
        observation_id=observation_id,
        handoff_status=handoff_status,
        claimed_next_posture=claimed_next_posture,
        claimed_transition_status=claimed_transition_status,
        required_human_decision=_required_str(payload, "required_human_decision").strip(),
        auto_continue=auto_continue,
        referenced_evidence_ids=_as_evidence_ids(payload.get("referenced_evidence_ids")),
        summary=_required_str(payload, "summary"),
        stop_condition=_required_str(payload, "stop_condition"),
    )


def _finding(code: str, severity: str, observation_id: str, detail: str) -> ControlPlaneHandoffFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneHandoffReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneHandoffFinding(code=code, severity=severity, observation_id=observation_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneHandoffReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneHandoffReviewError(f"{label} authority contains forbidden claim: {token}")


def _review_status(findings: tuple[ControlPlaneHandoffFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "handoff_drift_observed"
    if findings:
        return "handoff_review_required"
    return "handoff_contract_observed"


def _validate_observation_set_review(review: ControlPlaneObservationSetReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneHandoffReviewError("observation-set review must have state_change none")
    _validate_authority_text(review.authority, "observation-set review")
    if (
        not review.review_is_not_permission
        or not review.observation_frontier_is_not_scheduler
        or not review.advisory_posture_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneHandoffReviewError("observation-set review guardrails must remain true")
    if review.observation_count != len(review.observation_ids):
        raise ControlPlaneHandoffReviewError("observation-set review observation_count must match ids")
    if review.open_ready_count != len(review.open_ready_observation_ids):
        raise ControlPlaneHandoffReviewError("observation-set review open_ready_count must match ids")
    if review.finding_count != len(review.findings):
        raise ControlPlaneHandoffReviewError("observation-set review finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneHandoffReviewError("observation-set review finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneHandoffReviewError("observation-set review severity_counts must match findings")
    if any(item not in review.open_ready_observation_ids for item in review.observed_open_ready_frontier_ids):
        raise ControlPlaneHandoffReviewError("observation-set frontier ids must be a subset of open-ready ids")


def _validate_transition_review(review: ControlPlaneObservationTransitionReview | None) -> None:
    if review is None:
        return
    if review.state_change != "none":
        raise ControlPlaneHandoffReviewError("transition review must have state_change none")
    _validate_authority_text(review.authority, "transition review")
    if (
        not review.transition_review_is_not_permission
        or not review.observed_transition_is_not_truth
        or not review.observed_frontier_is_not_scheduler
        or not review.transition_pass_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneHandoffReviewError("transition review guardrails must remain true")
    if review.finding_count != len(review.findings):
        raise ControlPlaneHandoffReviewError("transition review finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneHandoffReviewError("transition review finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneHandoffReviewError("transition review severity_counts must match findings")
    if review.after_open_ready_observation_ids != review.after_review.open_ready_observation_ids:
        raise ControlPlaneHandoffReviewError("transition review after frontier must match after review")


def _validate_action_bundle(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneHandoffReviewError("action-review bundle must have state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneHandoffReviewError("action-review bundle guardrails must remain true")


def _is_ready_claim(handoff: ControlPlaneHandoffClaim) -> bool:
    return handoff.handoff_status in _READY_STATUSES or handoff.claimed_next_posture in _READY_POSTURES


def _text_laundering_findings(handoff: ControlPlaneHandoffClaim) -> list[ControlPlaneHandoffFinding]:
    findings: list[ControlPlaneHandoffFinding] = []
    for field_name, text in (("summary", handoff.summary), ("stop_condition", handoff.stop_condition)):
        lowered = text.lower()
        has_negative_marker = any(marker in lowered for marker in _NEGATIVE_TEXT_MARKERS)
        for token in _FORBIDDEN_AUTHORITY_TOKENS:
            if token in lowered and not has_negative_marker:
                findings.append(
                    _finding(
                        "handoff_text_launders_authority",
                        "high",
                        handoff.observation_id,
                        f"{field_name} contains forbidden handoff wording: {token}",
                    )
                )
    return findings


def _handoff_findings(
    handoff: ControlPlaneHandoffClaim,
    observation_set_review: ControlPlaneObservationSetReview,
    transition_review: ControlPlaneObservationTransitionReview | None,
    action_bundles: tuple[ControlPlaneActionReviewBundle, ...],
) -> tuple[ControlPlaneHandoffFinding, ...]:
    findings: list[ControlPlaneHandoffFinding] = []
    ready_claim = _is_ready_claim(handoff)

    if handoff.observation_id not in observation_set_review.observation_ids:
        findings.append(
            _finding(
                "handoff_observation_not_in_snapshot",
                "high",
                handoff.observation_id,
                "handoff refers to an observation absent from the supplied observation-set review",
            )
        )
    if handoff.auto_continue:
        findings.append(
            _finding(
                "handoff_requests_auto_continue",
                "high",
                handoff.observation_id,
                "handoff payload requested automatic continuation",
            )
        )
    if ready_claim and handoff.observation_id not in observation_set_review.observed_open_ready_frontier_ids:
        findings.append(
            _finding(
                "handoff_claims_ready_outside_frontier",
                "high",
                handoff.observation_id,
                "handoff claims ready/review posture outside the observed open-ready frontier",
            )
        )
    if observation_set_review.review_status == "observation_set_contract_drift_observed" and ready_claim:
        findings.append(
            _finding(
                "handoff_claims_ready_over_observation_set_drift",
                "high",
                handoff.observation_id,
                "handoff claims ready/review posture while observation-set review reports contract drift",
            )
        )
    elif observation_set_review.finding_count and ready_claim:
        findings.append(
            _finding(
                "handoff_claims_ready_over_observation_set_findings",
                "medium",
                handoff.observation_id,
                "handoff claims ready/review posture while observation-set review still has findings",
            )
        )
    if transition_review is not None:
        if handoff.observation_id not in transition_review.after_observation_ids:
            findings.append(
                _finding(
                    "handoff_observation_not_in_after_transition",
                    "high",
                    handoff.observation_id,
                    "handoff observation is absent from the after-transition review ids",
                )
            )
        if transition_review.review_status == "observation_transition_drift_observed" and (
            ready_claim or handoff.claimed_transition_status == "clean"
        ):
            findings.append(
                _finding(
                    "handoff_claims_clean_over_transition_drift",
                    "high",
                    handoff.observation_id,
                    "handoff claims readiness or clean transition while transition review reports drift",
                )
            )
        elif transition_review.finding_count and handoff.claimed_transition_status == "clean":
            findings.append(
                _finding(
                    "handoff_claims_clean_over_transition_findings",
                    "medium",
                    handoff.observation_id,
                    "handoff claims clean transition while transition review still has findings",
                )
            )

    matching_bundles = tuple(bundle for bundle in action_bundles if bundle.observation.observation_id == handoff.observation_id)
    if handoff.claimed_next_posture == "implementation_ready" and not matching_bundles:
        findings.append(
            _finding(
                "handoff_missing_action_review_bundle",
                "high",
                handoff.observation_id,
                "implementation-ready handoff has no matching action-review bundle",
            )
        )
    for bundle in matching_bundles:
        if bundle.action_posture in _BLOCKED_ACTION_POSTURES and handoff.claimed_next_posture in _READY_POSTURES:
            findings.append(
                _finding(
                    "handoff_conflicts_with_action_posture",
                    "high",
                    handoff.observation_id,
                    f"handoff claims {handoff.claimed_next_posture} while action bundle posture is {bundle.action_posture}",
                )
            )
        if bundle.recommended_human_decision != "none" and handoff.required_human_decision in {"", "none"}:
            findings.append(
                _finding(
                    "handoff_drops_required_human_decision",
                    "high",
                    handoff.observation_id,
                    f"action bundle requires {bundle.recommended_human_decision} but handoff drops the decision",
                )
            )
    return tuple(findings + _text_laundering_findings(handoff))


def _validate_review(review: ControlPlaneHandoffReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneHandoffReviewError("handoff review must have state_change none")
    _validate_authority_text(review.authority, "handoff review")
    if (
        not review.handoff_review_is_not_permission
        or not review.handoff_is_not_scheduler
        or not review.handoff_is_not_execution_approval
        or not review.observed_frontier_is_not_scheduler
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneHandoffReviewError("handoff review guardrails must remain true")
    if review.action_bundle_count < len(review.matching_action_bundle_ids):
        raise ControlPlaneHandoffReviewError("matching action bundle ids cannot exceed action bundle count")
    if review.referenced_evidence_count != len(review.referenced_evidence_ids):
        raise ControlPlaneHandoffReviewError("referenced_evidence_count must match referenced_evidence_ids")
    if review.referenced_evidence_ids != review.handoff.referenced_evidence_ids:
        raise ControlPlaneHandoffReviewError("referenced_evidence_ids must match handoff")
    if review.finding_count != len(review.findings):
        raise ControlPlaneHandoffReviewError("finding_count must match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneHandoffReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneHandoffReviewError("severity_counts must match findings")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneHandoffReviewError("review_status must match findings")


def build_control_plane_handoff_review(
    handoff_payload: Mapping[str, object],
    *,
    observation_set_review: ControlPlaneObservationSetReview,
    transition_review: ControlPlaneObservationTransitionReview | None = None,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
) -> ControlPlaneHandoffReview:
    """Review a caller-supplied handoff claim without transferring control or scheduling work."""

    handoff = _handoff_from_payload(handoff_payload)
    _validate_observation_set_review(observation_set_review)
    _validate_transition_review(transition_review)
    bundles = tuple(action_review_bundles)
    for bundle in bundles:
        _validate_action_bundle(bundle)
    findings = _handoff_findings(handoff, observation_set_review, transition_review, bundles)
    matching_bundle_ids = tuple(bundle.observation.observation_id for bundle in bundles if bundle.observation.observation_id == handoff.observation_id)
    review = ControlPlaneHandoffReview(
        schema_version="1",
        review_role="reviews_caller_supplied_handoff_claim_without_transferring_control",
        review_status=_review_status(findings),
        handoff=handoff,
        observation_set_status=observation_set_review.review_status,
        transition_status=transition_review.review_status if transition_review is not None else "not_supplied",
        action_bundle_count=len(bundles),
        matching_action_bundle_ids=matching_bundle_ids,
        referenced_evidence_count=len(handoff.referenced_evidence_ids),
        referenced_evidence_ids=handoff.referenced_evidence_ids,
        observed_frontier_ids=observation_set_review.observed_open_ready_frontier_ids,
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_handoff_review_json(review: ControlPlaneHandoffReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_handoff_review_markdown(review: ControlPlaneHandoffReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Handoff Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane handoff review only",
        "- handoff_review_is_not_permission: true",
        "- handoff_is_not_scheduler: true",
        "- handoff_is_not_execution_approval: true",
        "- observed_frontier_is_not_scheduler: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- handoff_id: {review.handoff.handoff_id}",
        f"- observation_id: {review.handoff.observation_id}",
        f"- handoff_status: {review.handoff.handoff_status}",
        f"- claimed_next_posture: {review.handoff.claimed_next_posture}",
        f"- claimed_transition_status: {review.handoff.claimed_transition_status}",
        f"- required_human_decision: {review.handoff.required_human_decision or 'none'}",
        f"- observation_set_status: {review.observation_set_status}",
        f"- transition_status: {review.transition_status}",
        f"- action_bundle_count: {review.action_bundle_count}",
        f"- matching_action_bundle_ids: {', '.join(review.matching_action_bundle_ids) if review.matching_action_bundle_ids else 'none'}",
        f"- observed_frontier_ids: {', '.join(review.observed_frontier_ids) if review.observed_frontier_ids else 'none'}",
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
            lines.append(f"- {finding.severity}: {finding.code} [{finding.observation_id}] - {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
