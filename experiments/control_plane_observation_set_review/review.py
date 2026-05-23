from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Iterable, Mapping

from experiments.control_plane_action_review import ControlPlaneActionReviewBundle


class ControlPlaneObservationSetReviewError(ValueError):
    """Raised when observation-set review inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneObservationSetItem:
    observation_id: str
    title: str
    status: str
    kind: str
    priority: str
    boundary: str
    trigger: str
    dependencies: tuple[str, ...]
    dependencies_satisfied: bool
    auto_continuation: bool
    next_action: str
    halt_if: str


@dataclass(frozen=True)
class ControlPlaneObservationSetFinding:
    code: str
    severity: str
    observation_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneObservationSetReview:
    schema_version: str
    review_role: str
    review_status: str
    observation_count: int
    bundle_count: int
    unresolved_count: int
    open_ready_count: int
    observation_ids: tuple[str, ...]
    unresolved_observation_ids: tuple[str, ...]
    open_ready_observation_ids: tuple[str, ...]
    observed_open_ready_frontier_ids: tuple[str, ...]
    bundled_observation_ids: tuple[str, ...]
    focus_observation_id: str
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    findings: tuple[ControlPlaneObservationSetFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane observation-set review only"
    review_is_not_permission: bool = True
    observation_frontier_is_not_scheduler: bool = True
    advisory_posture_is_not_execution_approval: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_OBSERVATION_STATUSES = {"open", "waiting", "blocked", "resolved"}
_OBSERVATION_KINDS = {"slice", "checkpoint", "blocker"}
_PRIORITY_ORDER = {"critical": 0, "high": 1, "medium": 2, "low": 3}
_SEVERITIES = {"critical", "high", "medium", "low"}
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


def _as_str_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ControlPlaneObservationSetReviewError(f"{field} must be a list")
    if not all(isinstance(item, str) and item for item in value):
        raise ControlPlaneObservationSetReviewError(f"{field} must contain only non-empty strings")
    return tuple(value)


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value:
        raise ControlPlaneObservationSetReviewError(f"missing required observation field: {field}")
    return value


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _observation_from_payload(payload: Mapping[str, object]) -> ControlPlaneObservationSetItem:
    if not isinstance(payload, Mapping):
        raise ControlPlaneObservationSetReviewError("observation payload must be a mapping")
    observation_id = _required_str(payload, "id")
    if not _is_path_segment_safe(observation_id):
        raise ControlPlaneObservationSetReviewError("observation id must be path-segment safe")
    status = _required_str(payload, "status")
    kind = _required_str(payload, "kind")
    priority = _required_str(payload, "priority")
    if status not in _OBSERVATION_STATUSES:
        raise ControlPlaneObservationSetReviewError(f"unknown observation status: {status}")
    if kind not in _OBSERVATION_KINDS:
        raise ControlPlaneObservationSetReviewError(f"unknown observation kind: {kind}")
    if priority not in _PRIORITY_ORDER:
        raise ControlPlaneObservationSetReviewError(f"unknown observation priority: {priority}")
    dependencies_satisfied = payload.get("dependencies_satisfied")
    if not isinstance(dependencies_satisfied, bool):
        raise ControlPlaneObservationSetReviewError("dependencies_satisfied must be boolean")
    auto_continuation = payload.get("auto_continuation", False)
    if not isinstance(auto_continuation, bool):
        raise ControlPlaneObservationSetReviewError("auto_continuation must be boolean")
    return ControlPlaneObservationSetItem(
        observation_id=observation_id,
        title=_required_str(payload, "title"),
        status=status,
        kind=kind,
        priority=priority,
        boundary=_required_str(payload, "boundary"),
        trigger=_required_str(payload, "trigger"),
        dependencies=_as_str_tuple(payload.get("dependencies"), "dependencies"),
        dependencies_satisfied=dependencies_satisfied,
        auto_continuation=auto_continuation,
        next_action=_required_str(payload, "next_action"),
        halt_if=_required_str(payload, "halt_if"),
    )


def _observations_from_center_payload(center_payload: Mapping[str, object]) -> tuple[ControlPlaneObservationSetItem, ...]:
    if not isinstance(center_payload, Mapping):
        raise ControlPlaneObservationSetReviewError("center payload must be a mapping")
    observations_payload = center_payload.get("observations")
    if not isinstance(observations_payload, list):
        raise ControlPlaneObservationSetReviewError("center payload must include observations list")
    observations = tuple(_observation_from_payload(item) for item in observations_payload)
    ids = [item.observation_id for item in observations]
    duplicates = sorted({item_id for item_id in ids if ids.count(item_id) > 1})
    if duplicates:
        raise ControlPlaneObservationSetReviewError(f"duplicate observation ids: {', '.join(duplicates)}")
    return observations


def _finding(code: str, severity: str, observation_id: str, detail: str) -> ControlPlaneObservationSetFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneObservationSetReviewError(f"unknown finding severity: {severity}")
    return ControlPlaneObservationSetFinding(code=code, severity=severity, observation_id=observation_id, detail=detail)


def _validate_authority_text(authority: str, label: str) -> None:
    authority_lower = authority.lower()
    if "non-authoritative" not in authority_lower:
        raise ControlPlaneObservationSetReviewError(f"{label} authority must be non-authoritative")
    for token in _FORBIDDEN_AUTHORITY_TOKENS:
        if token in authority_lower:
            raise ControlPlaneObservationSetReviewError(f"{label} authority contains forbidden claim: {token}")


def _is_open_ready(item: ControlPlaneObservationSetItem) -> bool:
    return (
        item.status == "open"
        and item.dependencies_satisfied
        and not item.auto_continuation
        and "not open" not in item.trigger.lower()
    )


def _frontier_ids(observations: tuple[ControlPlaneObservationSetItem, ...]) -> tuple[str, ...]:
    ready = [item for item in observations if _is_open_ready(item)]
    if not ready:
        return ()
    best_priority = min(_PRIORITY_ORDER[item.priority] for item in ready)
    return tuple(item.observation_id for item in ready if _PRIORITY_ORDER[item.priority] == best_priority)


def _validate_bundle_guardrails(bundle: ControlPlaneActionReviewBundle) -> None:
    if bundle.state_change != "none":
        raise ControlPlaneObservationSetReviewError("action-review bundle must be non-authoritative with state_change none")
    _validate_authority_text(bundle.authority, "action-review bundle")
    if (
        not bundle.bundle_is_not_permission
        or not bundle.action_posture_is_not_execution_approval
        or not bundle.replay_pass_is_not_truth
        or not bundle.must_not_execute_automatically
    ):
        raise ControlPlaneObservationSetReviewError("action-review bundle guardrails must remain true")


def _queue_contract_findings(center_payload: Mapping[str, object]) -> list[ControlPlaneObservationSetFinding]:
    findings: list[ControlPlaneObservationSetFinding] = []
    if center_payload.get("queue_authority") != "machine-primary":
        findings.append(
            _finding(
                "queue_authority_not_machine_primary",
                "high",
                "center",
                "queue_authority must remain machine-primary for this advisory review",
            )
        )
    if center_payload.get("single_flight") is not True:
        findings.append(
            _finding(
                "single_flight_not_enabled",
                "high",
                "center",
                "single_flight must be true before interpreting bundled observation evidence",
            )
        )
    overlap_policy = str(center_payload.get("overlap_policy", ""))
    if "wait" not in overlap_policy.lower():
        findings.append(
            _finding(
                "overlap_policy_not_wait",
                "medium",
                "center",
                "overlap_policy should remain wait so parallel work is not inferred from bundles",
            )
        )
    return findings


def _observation_findings(observations: tuple[ControlPlaneObservationSetItem, ...]) -> list[ControlPlaneObservationSetFinding]:
    findings: list[ControlPlaneObservationSetFinding] = []
    for item in observations:
        if item.status == "resolved":
            findings.append(
                _finding(
                    "resolved_observation_still_live",
                    "medium",
                    item.observation_id,
                    "resolved observations should be rotated out of the live observation set",
                )
            )
        if item.auto_continuation:
            findings.append(
                _finding(
                    "auto_continuation_requested",
                    "high",
                    item.observation_id,
                    "auto_continuation is incompatible with advisory observation-set review",
                )
            )
        if item.status == "open" and not item.dependencies_satisfied:
            findings.append(
                _finding(
                    "open_observation_dependencies_unsatisfied",
                    "medium",
                    item.observation_id,
                    "open observations with unsatisfied dependencies must remain review evidence, not runnable work",
                )
            )
        if item.status == "open" and "not open" in item.trigger.lower():
            findings.append(
                _finding(
                    "open_observation_trigger_not_open",
                    "high",
                    item.observation_id,
                    "open observation references a trigger that is not open",
                )
            )
    return findings


def _bundle_findings(
    observations: tuple[ControlPlaneObservationSetItem, ...],
    bundles: tuple[ControlPlaneActionReviewBundle, ...],
    frontier: tuple[str, ...],
    focus_observation_id: str,
    single_flight: bool,
) -> list[ControlPlaneObservationSetFinding]:
    findings: list[ControlPlaneObservationSetFinding] = []
    by_id = {item.observation_id: item for item in observations}
    bundled_ids: list[str] = []
    for bundle in bundles:
        _validate_bundle_guardrails(bundle)
        observation_id = bundle.observation.observation_id
        bundled_ids.append(observation_id)
        source = by_id.get(observation_id)
        if source is None:
            findings.append(
                _finding(
                    "bundle_observation_not_in_snapshot",
                    "high",
                    observation_id,
                    "action-review bundle refers to an observation absent from the supplied snapshot",
                )
            )
            continue
        if bundle.observation.status != source.status:
            findings.append(
                _finding(
                    "bundle_status_drift",
                    "high",
                    observation_id,
                    f"bundle status {bundle.observation.status} differs from snapshot status {source.status}",
                )
            )
        if bundle.observation.dependencies_satisfied != source.dependencies_satisfied:
            findings.append(
                _finding(
                    "bundle_dependency_status_drift",
                    "high",
                    observation_id,
                    "bundle dependency satisfaction differs from snapshot",
                )
            )
        if bundle.observation.auto_continuation != source.auto_continuation:
            findings.append(
                _finding(
                    "bundle_auto_continuation_drift",
                    "high",
                    observation_id,
                    "bundle auto_continuation differs from snapshot",
                )
            )
        compared_fields = (
            ("title", bundle.observation.title, source.title),
            ("kind", bundle.observation.kind, source.kind),
            ("priority", bundle.observation.priority, source.priority),
            ("boundary", bundle.observation.boundary, source.boundary),
            ("trigger", bundle.observation.trigger, source.trigger),
            ("dependencies", bundle.observation.dependencies, source.dependencies),
            ("next_action", bundle.observation.next_action, source.next_action),
            ("halt_if", bundle.observation.halt_if, source.halt_if),
        )
        drifted_fields = tuple(field for field, bundled, snapshotted in compared_fields if bundled != snapshotted)
        if drifted_fields:
            findings.append(
                _finding(
                    "bundle_observation_payload_drift",
                    "high",
                    observation_id,
                    f"bundle observation fields differ from snapshot: {', '.join(drifted_fields)}",
                )
            )
        if frontier and observation_id not in frontier and bundle.action_posture == "advisory_review_only":
            findings.append(
                _finding(
                    "advisory_bundle_outside_open_ready_frontier",
                    "high",
                    observation_id,
                    "advisory posture was bundled for an observation outside the observed open-ready frontier",
                )
            )
    if focus_observation_id:
        if focus_observation_id not in by_id:
            findings.append(
                _finding(
                    "focus_observation_not_in_snapshot",
                    "high",
                    focus_observation_id,
                    "declared focus observation is absent from the supplied snapshot",
                )
            )
        if bundles and focus_observation_id not in bundled_ids:
            findings.append(
                _finding(
                    "focus_observation_not_bundled",
                    "medium",
                    focus_observation_id,
                    "declared focus observation has no corresponding action-review bundle",
                )
            )
        if frontier and focus_observation_id not in frontier:
            findings.append(
                _finding(
                    "focus_outside_open_ready_frontier",
                    "high",
                    focus_observation_id,
                    "declared focus does not match the observed highest-priority open-ready frontier",
                )
            )
    advisory_ids = [bundle.observation.observation_id for bundle in bundles if bundle.action_posture == "advisory_review_only"]
    if single_flight and len(advisory_ids) > 1:
        findings.append(
            _finding(
                "multiple_advisory_bundles_under_single_flight",
                "high",
                "center",
                f"single_flight review received multiple advisory bundles: {', '.join(advisory_ids)}",
            )
        )
    return findings


def _review_status(findings: tuple[ControlPlaneObservationSetFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "observation_set_contract_drift_observed"
    if findings:
        return "observation_set_review_required"
    return "observation_set_contract_observed"


def _validate_review(review: ControlPlaneObservationSetReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneObservationSetReviewError("review must be non-authoritative with state_change none")
    _validate_authority_text(review.authority, "review")
    if (
        not review.review_is_not_permission
        or not review.observation_frontier_is_not_scheduler
        or not review.advisory_posture_is_not_execution_approval
        or not review.finding_is_not_truth
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneObservationSetReviewError("review guardrails must remain true")
    if review.finding_count != len(review.findings):
        raise ControlPlaneObservationSetReviewError("finding_count must match findings")
    if review.observation_count != len(review.observation_ids):
        raise ControlPlaneObservationSetReviewError("observation_count must match observation_ids")
    if review.bundle_count != len(review.bundled_observation_ids):
        raise ControlPlaneObservationSetReviewError("bundle_count must match bundled_observation_ids")
    if review.unresolved_count != len(review.unresolved_observation_ids):
        raise ControlPlaneObservationSetReviewError("unresolved_count must match unresolved_observation_ids")
    if review.open_ready_count != len(review.open_ready_observation_ids):
        raise ControlPlaneObservationSetReviewError("open_ready_count must match open_ready_observation_ids")
    open_ready = set(review.open_ready_observation_ids)
    if any(observation_id not in open_ready for observation_id in review.observed_open_ready_frontier_ids):
        raise ControlPlaneObservationSetReviewError("frontier ids must be a subset of open_ready_observation_ids")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneObservationSetReviewError("finding_codes must match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneObservationSetReviewError("severity_counts must match findings")
    if review.review_status != _review_status(review.findings):
        raise ControlPlaneObservationSetReviewError("review_status must match findings")


def build_control_plane_observation_set_review(
    center_payload: Mapping[str, object],
    *,
    action_review_bundles: Iterable[ControlPlaneActionReviewBundle] = (),
    focus_observation_id: str = "",
) -> ControlPlaneObservationSetReview:
    """Review a caller-supplied observation set without reading or mutating runtime state."""

    if focus_observation_id and not _is_path_segment_safe(focus_observation_id):
        raise ControlPlaneObservationSetReviewError("focus observation id must be path-segment safe")
    observations = _observations_from_center_payload(center_payload)
    bundles = tuple(action_review_bundles)
    frontier = _frontier_ids(observations)
    open_ready_ids = tuple(item.observation_id for item in observations if _is_open_ready(item))
    findings = tuple(
        _queue_contract_findings(center_payload)
        + _observation_findings(observations)
        + _bundle_findings(
            observations,
            bundles,
            frontier,
            focus_observation_id,
            center_payload.get("single_flight") is True,
        )
    )
    review = ControlPlaneObservationSetReview(
        schema_version="1",
        review_role="reviews_caller_supplied_observation_set_without_scheduling",
        review_status=_review_status(findings),
        observation_count=len(observations),
        bundle_count=len(bundles),
        unresolved_count=sum(1 for item in observations if item.status != "resolved"),
        open_ready_count=sum(1 for item in observations if _is_open_ready(item)),
        observation_ids=tuple(item.observation_id for item in observations),
        unresolved_observation_ids=tuple(item.observation_id for item in observations if item.status != "resolved"),
        open_ready_observation_ids=open_ready_ids,
        observed_open_ready_frontier_ids=frontier,
        bundled_observation_ids=tuple(bundle.observation.observation_id for bundle in bundles),
        focus_observation_id=focus_observation_id,
        finding_count=len(findings),
        severity_counts=_count(finding.severity for finding in findings),
        finding_codes=tuple(finding.code for finding in findings),
        findings=findings,
    )
    _validate_review(review)
    return review


def render_control_plane_observation_set_review_json(review: ControlPlaneObservationSetReview) -> str:
    _validate_review(review)
    payload = asdict(review)
    payload["state_change"] = "none"
    payload["authority"] = review.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_observation_set_review_markdown(review: ControlPlaneObservationSetReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Observation Set Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane observation-set review only",
        "- review_is_not_permission: true",
        "- observation_frontier_is_not_scheduler: true",
        "- advisory_posture_is_not_execution_approval: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- observation_count: {review.observation_count}",
        f"- bundle_count: {review.bundle_count}",
        f"- unresolved_count: {review.unresolved_count}",
        f"- open_ready_count: {review.open_ready_count}",
        f"- observation_ids: {', '.join(review.observation_ids) if review.observation_ids else 'none'}",
        f"- unresolved_observation_ids: {', '.join(review.unresolved_observation_ids) if review.unresolved_observation_ids else 'none'}",
        f"- open_ready_observation_ids: {', '.join(review.open_ready_observation_ids) if review.open_ready_observation_ids else 'none'}",
        f"- observed_open_ready_frontier_ids: {', '.join(review.observed_open_ready_frontier_ids) if review.observed_open_ready_frontier_ids else 'none'}",
        f"- bundled_observation_ids: {', '.join(review.bundled_observation_ids) if review.bundled_observation_ids else 'none'}",
        f"- focus_observation_id: {review.focus_observation_id if review.focus_observation_id else 'none'}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
        "",
    ]
    if not review.findings:
        lines.append("- none")
    else:
        for finding in review.findings:
            lines.append(f"- {finding.severity}: {finding.code} [{finding.observation_id}] — {finding.detail}")
    return "\n".join(lines).rstrip() + "\n"
