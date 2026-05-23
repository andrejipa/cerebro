from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date
from typing import Iterable


class ControlPlaneAdversarialPostureReviewError(ValueError):
    """Raised when adversarial posture review inputs are malformed."""


@dataclass(frozen=True)
class ControlPlaneAdversarialSubject:
    subject_id: str
    subject_kind: str
    subject_role: str
    subject_status: str
    finding_count: int
    finding_codes: tuple[str, ...]
    severity_counts: dict[str, int]
    blocker_count: int
    blockers: tuple[str, ...]
    guardrail_names: tuple[str, ...]
    false_guardrail_names: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneAdversarialPostureFinding:
    code: str
    severity: str
    subject_id: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneAdversarialPostureReview:
    schema_version: str
    review_role: str
    review_status: str
    review_as_of: str
    subject_count: int
    subject_ids: tuple[str, ...]
    subject_kind_counts: dict[str, int]
    subject_status_counts: dict[str, int]
    clean_subject_ids: tuple[str, ...]
    blocked_subject_ids: tuple[str, ...]
    expected_blocked_subject_ids: tuple[str, ...]
    missing_expected_blocker_ids: tuple[str, ...]
    required_guardrail_names: tuple[str, ...]
    missing_required_guardrail_subject_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    subjects: tuple[ControlPlaneAdversarialSubject, ...]
    findings: tuple[ControlPlaneAdversarialPostureFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane adversarial posture review only"
    posture_review_is_not_permission: bool = True
    posture_review_is_not_runtime_gate: bool = True
    posture_status_is_not_truth: bool = True
    posture_review_is_not_scheduler: bool = True
    posture_review_is_not_state_store: bool = True
    posture_review_is_not_approval: bool = True
    finding_is_not_truth: bool = True
    finding_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_STATUS_FIELDS = (
    "review_status",
    "audit_status",
    "eval_status",
    "action_posture",
    "packet_verdict",
    "combined_review_status",
)
_ROLE_FIELDS = ("review_role", "audit_role", "eval_role", "bundle_role", "packet_role", "projection_role")
_ID_FIELDS = (
    "trace_id",
    "selected_task_id",
    "review_as_of",
    "replay_digest",
    "source_projection_role",
)
_CLEAN_STATUSES = {
    "advisory_review_only",
    "boundary_markers_preserved",
    "control_plane_integrity_preserved",
    "guardrails_preserved",
    "lineage_invariants_preserved",
    "approval_policy_candidate_observed",
    "evidence_policy_candidate_observed",
    "runtime_contract_candidate_observed",
    "runtime_state_snapshot_observed",
    "runtime_state_transition_observed",
    "tool_manifest_candidate_observed",
    "work_queue_candidates_observed",
    "decision_version_review_observed",
    "rule_promotion_contract_observed",
}
_BLOCKING_STATUS_TOKENS = (
    "blocked",
    "drift",
    "human_review",
    "attention_required",
    "invalid",
    "required",
)
_FORBIDDEN_STATUS_TOKENS = (
    "approved",
    "authorized",
    "executed",
    "execution_approved",
    "permission",
    "ready_to_execute",
    "success",
)
_FORBIDDEN_AUTHORITY_TOKENS = (
    "canonical truth",
    "canonical_truth",
    "execution approval",
    "execution_approved",
    "grants permission",
    "permission granted",
    "permission_granted",
    "ready to execute",
    "runtime authority",
    "runtime_authority",
    "scheduler",
    "schedules work",
    "selected next action",
    "source of truth",
    "truth signal",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not a state store",
    "not a runtime gate",
    "not truth",
    "must not execute",
    "does not grant",
    "does not approve",
)


def _count(values: Iterable[str]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for value in values:
        counts[value] = counts.get(value, 0) + 1
    return dict(sorted(counts.items()))


def _parse_date(value: str, field: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise ControlPlaneAdversarialPostureReviewError(f"{field} must be an ISO date") from exc


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _subject_kind(value: object) -> str:
    name = value.__class__.__name__
    if name.startswith("ControlPlane"):
        name = name[len("ControlPlane") :]
    parts: list[str] = []
    current = ""
    for char in name:
        if char.isupper() and current:
            parts.append(current.lower())
            current = char
        else:
            current += char
    if current:
        parts.append(current.lower())
    return "_".join(parts) or "unknown"


def _field_names(value: object) -> tuple[str, ...]:
    if is_dataclass(value):
        return tuple(field.name for field in fields(value))
    return tuple(name for name in vars(value) if not name.startswith("_"))


def _attr(value: object, names: Iterable[str], default: object = "") -> object:
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value)
    if isinstance(value, list):
        return tuple(str(item) for item in value)
    return (str(value),)


def _finding(code: str, severity: str, subject_id: str, detail: str) -> ControlPlaneAdversarialPostureFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneAdversarialPostureReviewError(f"unknown severity: {severity}")
    return ControlPlaneAdversarialPostureFinding(code=code, severity=severity, subject_id=subject_id, detail=detail)


def _has_unqualified_authority_text(text: object) -> bool:
    normalized = " ".join(str(text).lower().replace("_", " ").replace("-", " ").split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token.replace("_", " ") in normalized for token in _FORBIDDEN_AUTHORITY_TOKENS)


def _guardrail_names(value: object) -> tuple[str, ...]:
    names: list[str] = []
    for name in _field_names(value):
        if (
            "_is_not_" in name
            or name.endswith("_is_not_truth")
            or name.endswith("_is_not_permission")
            or name.startswith("must_not_")
            or "must_not_execute" in name
            or "not_execution_approval" in name
            or "not_scheduler" in name
            or "not_state_store" in name
            or "not_runtime_gate" in name
        ):
            names.append(name)
    return tuple(sorted(set(names)))


def _false_guardrails(value: object, names: tuple[str, ...]) -> tuple[str, ...]:
    return tuple(name for name in names if getattr(value, name, None) is not True)


def _subject_id(value: object, index: int, subject_kind: str) -> str:
    candidate = _attr(value, _ID_FIELDS, "")
    if isinstance(candidate, str) and candidate and _is_path_segment_safe(candidate):
        return candidate
    return f"{subject_kind}.{index + 1}"


def _normalize_subject(value: object, index: int) -> tuple[ControlPlaneAdversarialSubject, tuple[ControlPlaneAdversarialPostureFinding, ...]]:
    names = _field_names(value)
    if not names:
        raise ControlPlaneAdversarialPostureReviewError("review subjects must expose fields")
    subject_kind = _subject_kind(value)
    subject_id = _subject_id(value, index, subject_kind)
    subject_status = str(_attr(value, _STATUS_FIELDS, "unknown"))
    subject_role = str(_attr(value, _ROLE_FIELDS, "unknown"))
    findings_obj = getattr(value, "findings", ())
    findings_tuple = tuple(findings_obj or ())
    finding_count = getattr(value, "finding_count", 0)
    if not isinstance(finding_count, int) or finding_count < 0:
        raise ControlPlaneAdversarialPostureReviewError("subject finding_count must be a non-negative integer")
    finding_codes = _as_str_tuple(getattr(value, "finding_codes", ()))
    severity_counts = getattr(value, "severity_counts", {})
    if not isinstance(severity_counts, dict):
        raise ControlPlaneAdversarialPostureReviewError("subject severity_counts must be a dictionary")
    blockers = _as_str_tuple(getattr(value, "blockers", ()))
    guardrails = _guardrail_names(value)
    false_guardrails = _false_guardrails(value, guardrails)
    subject = ControlPlaneAdversarialSubject(
        subject_id=subject_id,
        subject_kind=subject_kind,
        subject_role=subject_role,
        subject_status=subject_status,
        finding_count=finding_count,
        finding_codes=finding_codes,
        severity_counts=dict(sorted((str(key), int(value)) for key, value in severity_counts.items())),
        blocker_count=len(blockers),
        blockers=blockers,
        guardrail_names=guardrails,
        false_guardrail_names=false_guardrails,
    )
    local_findings: list[ControlPlaneAdversarialPostureFinding] = []
    if getattr(value, "state_change", "none") != "none":
        local_findings.append(_finding("subject_mutates_state", "critical", subject_id, "state_change is not none"))
    if "non-authoritative" not in str(getattr(value, "authority", "")):
        local_findings.append(_finding("subject_lacks_non_authority", "critical", subject_id, "authority is not non-authoritative"))
    if getattr(value, "must_not_execute_automatically", True) is not True:
        local_findings.append(_finding("subject_allows_auto_execution", "critical", subject_id, "must_not_execute_automatically is false"))
    for guardrail_name in false_guardrails:
        local_findings.append(_finding("subject_guardrail_false", "critical", subject_id, guardrail_name))
    if finding_count != len(findings_tuple):
        local_findings.append(_finding("subject_forged_finding_count", "critical", subject_id, "finding_count does not match findings"))
    if findings_tuple:
        actual_codes = tuple(str(getattr(finding, "code", "")) for finding in findings_tuple)
        if finding_codes != actual_codes:
            local_findings.append(_finding("subject_forged_finding_codes", "critical", subject_id, "finding_codes do not match findings"))
        actual_severity_counts = _count(str(getattr(finding, "severity", "unknown")) for finding in findings_tuple)
        if subject.severity_counts != actual_severity_counts:
            local_findings.append(_finding("subject_forged_severity_counts", "critical", subject_id, "severity_counts do not match findings"))
    if subject_status in _CLEAN_STATUSES and finding_count:
        local_findings.append(_finding("clean_status_with_findings", "high", subject_id, subject_status))
    if subject_status in _CLEAN_STATUSES and blockers:
        local_findings.append(_finding("clean_status_with_blockers", "high", subject_id, subject_status))
    if any(token in subject_status for token in _BLOCKING_STATUS_TOKENS) and finding_count == 0 and not blockers:
        local_findings.append(_finding("blocking_status_without_evidence", "medium", subject_id, subject_status))
    if any(token in subject_status.lower() for token in _FORBIDDEN_STATUS_TOKENS):
        local_findings.append(_finding("subject_status_launders_authority", "high", subject_id, subject_status))
    text_values = [subject_status, subject_role, getattr(value, "authority", "")]
    for optional_name in ("summary", "rationale", "recommended_human_decision", "next_action"):
        if hasattr(value, optional_name):
            text_values.append(getattr(value, optional_name))
    if any(_has_unqualified_authority_text(item) for item in text_values):
        local_findings.append(_finding("subject_text_launders_authority", "high", subject_id, "authority wording without local negation"))
    return subject, tuple(local_findings)


def _validate_review(review: ControlPlaneAdversarialPostureReview) -> None:
    if review.state_change != "none":
        raise ControlPlaneAdversarialPostureReviewError("posture review must not mutate state")
    if "non-authoritative" not in review.authority:
        raise ControlPlaneAdversarialPostureReviewError("posture review must remain non-authoritative")
    if (
        not review.posture_review_is_not_permission
        or not review.posture_review_is_not_runtime_gate
        or not review.posture_status_is_not_truth
        or not review.posture_review_is_not_scheduler
        or not review.posture_review_is_not_state_store
        or not review.posture_review_is_not_approval
        or not review.finding_is_not_truth
        or not review.finding_is_not_execution_approval
        or not review.must_not_execute_automatically
    ):
        raise ControlPlaneAdversarialPostureReviewError("posture review guardrails drifted")
    if review.subject_count != len(review.subjects):
        raise ControlPlaneAdversarialPostureReviewError("subject_count does not match subjects")
    if review.subject_ids != tuple(subject.subject_id for subject in review.subjects):
        raise ControlPlaneAdversarialPostureReviewError("subject_ids do not match subjects")
    if len(set(review.subject_ids)) != len(review.subject_ids):
        raise ControlPlaneAdversarialPostureReviewError("subject_ids must be unique")
    if any(not _is_path_segment_safe(subject_id) for subject_id in review.subject_ids):
        raise ControlPlaneAdversarialPostureReviewError("subject_ids must be path-segment safe")
    if review.subject_kind_counts != _count(subject.subject_kind for subject in review.subjects):
        raise ControlPlaneAdversarialPostureReviewError("subject_kind_counts do not match subjects")
    if review.subject_status_counts != _count(subject.subject_status for subject in review.subjects):
        raise ControlPlaneAdversarialPostureReviewError("subject_status_counts do not match subjects")
    if review.finding_count != len(review.findings):
        raise ControlPlaneAdversarialPostureReviewError("finding_count does not match findings")
    if review.finding_codes != tuple(finding.code for finding in review.findings):
        raise ControlPlaneAdversarialPostureReviewError("finding_codes do not match findings")
    if review.severity_counts != _count(finding.severity for finding in review.findings):
        raise ControlPlaneAdversarialPostureReviewError("severity_counts do not match findings")
    expected_status = "adversarial_posture_preserved"
    if any(finding.severity in {"critical", "high"} for finding in review.findings):
        expected_status = "adversarial_posture_blocked"
    elif review.findings:
        expected_status = "adversarial_posture_attention_required"
    if review.review_status != expected_status:
        raise ControlPlaneAdversarialPostureReviewError("review_status does not match findings")


def build_control_plane_adversarial_posture_review(
    review_subjects: Iterable[object],
    *,
    review_as_of: str,
    expected_blocked_subject_ids: Iterable[str] = (),
    required_guardrail_names: Iterable[str] = (),
) -> ControlPlaneAdversarialPostureReview:
    """Review caller-supplied advisory reports for adversarial posture drift."""

    _parse_date(review_as_of, "review_as_of")
    raw_subjects = tuple(review_subjects)
    if not raw_subjects:
        raise ControlPlaneAdversarialPostureReviewError("at least one review subject is required")
    expected_blocked = tuple(sorted(set(expected_blocked_subject_ids)))
    required_guardrails = tuple(sorted(set(required_guardrail_names)))
    for subject_id in expected_blocked:
        if not _is_path_segment_safe(subject_id):
            raise ControlPlaneAdversarialPostureReviewError("expected blocked subject ids must be path-segment safe")
    for guardrail_name in required_guardrails:
        if not guardrail_name or not guardrail_name.replace("_", "").isalnum():
            raise ControlPlaneAdversarialPostureReviewError("required guardrail names must be simple identifiers")

    subjects: list[ControlPlaneAdversarialSubject] = []
    findings: list[ControlPlaneAdversarialPostureFinding] = []
    for index, subject_obj in enumerate(raw_subjects):
        subject, subject_findings = _normalize_subject(subject_obj, index)
        subjects.append(subject)
        findings.extend(subject_findings)

    subject_by_id = {subject.subject_id: subject for subject in subjects}
    if len(subject_by_id) != len(subjects):
        duplicated = next(subject.subject_id for subject in subjects if [item.subject_id for item in subjects].count(subject.subject_id) > 1)
        findings.append(_finding("duplicate_subject_id", "critical", duplicated, "subject ids must be unique"))

    missing_expected_blockers: list[str] = []
    for subject_id in expected_blocked:
        subject = subject_by_id.get(subject_id)
        if subject is None:
            findings.append(_finding("expected_blocked_subject_missing", "high", subject_id, "expected blocked subject was not supplied"))
            missing_expected_blockers.append(subject_id)
            continue
        is_clean = subject.subject_status in _CLEAN_STATUSES and subject.finding_count == 0 and subject.blocker_count == 0
        if is_clean:
            findings.append(_finding("expected_blocker_disappeared", "high", subject_id, "subject is clean but was expected blocked"))
            missing_expected_blockers.append(subject_id)

    missing_required_guardrail_subjects: list[str] = []
    for subject in subjects:
        missing = tuple(name for name in required_guardrails if name not in subject.guardrail_names)
        if missing:
            missing_required_guardrail_subjects.append(subject.subject_id)
            findings.append(_finding("subject_missing_required_guardrail", "high", subject.subject_id, ", ".join(missing)))

    clean_subject_ids = tuple(
        subject.subject_id
        for subject in subjects
        if subject.subject_status in _CLEAN_STATUSES and subject.finding_count == 0 and subject.blocker_count == 0
    )
    blocked_subject_ids = tuple(
        subject.subject_id
        for subject in subjects
        if subject.subject_status not in _CLEAN_STATUSES or subject.finding_count > 0 or subject.blocker_count > 0
    )
    finding_items = tuple(findings)
    review_status = "adversarial_posture_preserved"
    if any(finding.severity in {"critical", "high"} for finding in finding_items):
        review_status = "adversarial_posture_blocked"
    elif finding_items:
        review_status = "adversarial_posture_attention_required"
    review = ControlPlaneAdversarialPostureReview(
        schema_version="1",
        review_role="reviews_control_plane_advisory_artifacts_for_adversarial_posture_drift",
        review_status=review_status,
        review_as_of=review_as_of,
        subject_count=len(subjects),
        subject_ids=tuple(subject.subject_id for subject in subjects),
        subject_kind_counts=_count(subject.subject_kind for subject in subjects),
        subject_status_counts=_count(subject.subject_status for subject in subjects),
        clean_subject_ids=clean_subject_ids,
        blocked_subject_ids=blocked_subject_ids,
        expected_blocked_subject_ids=expected_blocked,
        missing_expected_blocker_ids=tuple(sorted(set(missing_expected_blockers))),
        required_guardrail_names=required_guardrails,
        missing_required_guardrail_subject_ids=tuple(sorted(set(missing_required_guardrail_subjects))),
        finding_count=len(finding_items),
        severity_counts=_count(finding.severity for finding in finding_items),
        finding_codes=tuple(finding.code for finding in finding_items),
        subjects=tuple(subjects),
        findings=finding_items,
    )
    _validate_review(review)
    return review


def render_control_plane_adversarial_posture_review_json(review: ControlPlaneAdversarialPostureReview) -> str:
    _validate_review(review)
    return json.dumps(asdict(review), indent=2, sort_keys=True) + "\n"


def render_control_plane_adversarial_posture_review_markdown(review: ControlPlaneAdversarialPostureReview) -> str:
    _validate_review(review)
    lines = [
        "# Control Plane Adversarial Posture Review",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane adversarial posture review only",
        "- posture_review_is_not_permission: true",
        "- posture_review_is_not_runtime_gate: true",
        "- posture_status_is_not_truth: true",
        "- posture_review_is_not_scheduler: true",
        "- posture_review_is_not_state_store: true",
        "- posture_review_is_not_approval: true",
        "- finding_is_not_truth: true",
        "- finding_is_not_execution_approval: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- review_status: {review.review_status}",
        f"- subject_count: {review.subject_count}",
        f"- clean_subject_ids: {', '.join(review.clean_subject_ids) if review.clean_subject_ids else 'none'}",
        f"- blocked_subject_ids: {', '.join(review.blocked_subject_ids) if review.blocked_subject_ids else 'none'}",
        f"- missing_expected_blocker_ids: {', '.join(review.missing_expected_blocker_ids) if review.missing_expected_blocker_ids else 'none'}",
        f"- finding_count: {review.finding_count}",
        "",
        "## Findings",
    ]
    if not review.findings:
        lines.append("- none")
    for finding in review.findings:
        lines.append(f"- {finding.severity}: {finding.code} ({finding.subject_id}) - {finding.detail}")
    return "\n".join(lines) + "\n"
