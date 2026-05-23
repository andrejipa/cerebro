from __future__ import annotations

import json
from dataclasses import asdict, dataclass, fields, is_dataclass
from datetime import date
from typing import Iterable


class ControlPlaneCrossReviewConsistencyError(ValueError):
    """Raised when cross-review consistency inputs are malformed."""


@dataclass(frozen=True)
class ControlPlaneCrossReviewSubject:
    subject_id: str
    subject_kind: str
    subject_status: str
    trace_id: str
    replay_digest: str
    finding_count: int
    blocker_count: int
    missing_evidence_count: int
    blocked_ids: tuple[str, ...]
    ready_ids: tuple[str, ...]
    allowed_ids: tuple[str, ...]
    active_ids: tuple[str, ...]
    identity_keys: tuple[str, ...]


@dataclass(frozen=True)
class ControlPlaneCrossReviewConsistencyFinding:
    code: str
    severity: str
    subject_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ControlPlaneCrossReviewConsistencyReport:
    schema_version: str
    eval_role: str
    eval_status: str
    review_as_of: str
    subject_count: int
    subject_ids: tuple[str, ...]
    subject_kind_counts: dict[str, int]
    subject_status_counts: dict[str, int]
    shared_identity_count: int
    blocked_dependency_subject_ids: tuple[str, ...]
    ready_subject_ids: tuple[str, ...]
    allowed_subject_ids: tuple[str, ...]
    active_subject_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    subjects: tuple[ControlPlaneCrossReviewSubject, ...]
    findings: tuple[ControlPlaneCrossReviewConsistencyFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane cross-review consistency eval only"
    consistency_eval_is_not_permission: bool = True
    consistency_status_is_not_truth: bool = True
    consistency_eval_is_not_execution_approval: bool = True
    consistency_eval_is_not_scheduler: bool = True
    consistency_eval_is_not_runtime_gate: bool = True
    consistency_eval_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_CLEAN_STATUSES = {
    "advisory_review_only",
    "approval_policy_candidate_observed",
    "boundary_markers_preserved",
    "control_plane_integrity_preserved",
    "cross_review_consistency_preserved",
    "evidence_policy_candidate_observed",
    "guardrails_preserved",
    "lineage_invariants_preserved",
    "runtime_contract_candidate_observed",
    "runtime_state_snapshot_observed",
    "runtime_state_transition_observed",
    "tool_manifest_candidate_observed",
    "work_queue_candidates_observed",
}
_BLOCKING_STATUS_TOKENS = (
    "blocked",
    "drift",
    "invalid",
    "attention_required",
    "human_review",
)
_STATUS_FIELDS = (
    "review_status",
    "eval_status",
    "audit_status",
    "action_posture",
    "packet_verdict",
    "combined_review_status",
)
_ID_FIELDS = (
    "subject_id",
    "trace_id",
    "selected_task_id",
    "review_id",
    "packet_id",
    "source_id",
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
        raise ControlPlaneCrossReviewConsistencyError(f"{field} must be an ISO date") from exc


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _field_names(value: object) -> tuple[str, ...]:
    if is_dataclass(value):
        return tuple(field.name for field in fields(value))
    return tuple(name for name in vars(value) if not name.startswith("_"))


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


def _first_attr(value: object, names: Iterable[str], default: object = "") -> object:
    for name in names:
        if hasattr(value, name):
            return getattr(value, name)
    return default


def _as_str_tuple(value: object) -> tuple[str, ...]:
    if value is None:
        return ()
    if isinstance(value, tuple):
        return tuple(str(item) for item in value if str(item))
    if isinstance(value, list):
        return tuple(str(item) for item in value if str(item))
    if isinstance(value, set):
        return tuple(sorted(str(item) for item in value if str(item)))
    if isinstance(value, dict):
        return tuple(sorted(str(key) for key in value if str(key)))
    text = str(value)
    return (text,) if text else ()


def _safe_tuple(values: Iterable[str], field: str) -> tuple[str, ...]:
    items = tuple(values)
    if any(not _is_path_segment_safe(item) for item in items):
        raise ControlPlaneCrossReviewConsistencyError(f"{field} values must be path-segment safe")
    return items


def _nested_observation_id(value: object) -> str:
    observation = getattr(value, "observation", None)
    observation_id = getattr(observation, "observation_id", "")
    return observation_id if isinstance(observation_id, str) else ""


def _subject_id(value: object, index: int, subject_kind: str) -> str:
    nested = _nested_observation_id(value)
    if nested:
        if not _is_path_segment_safe(nested):
            raise ControlPlaneCrossReviewConsistencyError("subject ids must be path-segment safe")
        return nested
    candidate = _first_attr(value, _ID_FIELDS, "")
    if isinstance(candidate, str) and candidate:
        if not _is_path_segment_safe(candidate):
            raise ControlPlaneCrossReviewConsistencyError("subject ids must be path-segment safe")
        return candidate
    return f"{subject_kind}.{index + 1}"


def _status(value: object) -> str:
    status = _first_attr(value, _STATUS_FIELDS, "unknown")
    if isinstance(status, str) and status:
        return status
    return "unknown"


def _blocked_ids(value: object) -> tuple[str, ...]:
    fields_to_collect = (
        "blocked_subject_ids",
        "blocked_item_ids",
        "blocked_policy_ids",
        "blocked_manifest_ids",
        "blocked_contract_ids",
        "blocked_snapshot_ids",
        "blocked_proposal_ids",
    )
    items: list[str] = []
    for field in fields_to_collect:
        items.extend(_as_str_tuple(getattr(value, field, ())))
    return tuple(sorted(set(items)))


def _ready_ids(value: object) -> tuple[str, ...]:
    fields_to_collect = ("ready_candidate_ids", "ready_item_ids", "open_ready_observation_ids")
    items: list[str] = []
    for field in fields_to_collect:
        items.extend(_as_str_tuple(getattr(value, field, ())))
    return tuple(sorted(set(items)))


def _allowed_ids(value: object) -> tuple[str, ...]:
    fields_to_collect = ("allowed_tool_ids", "approved_tool_ids")
    items: list[str] = []
    for field in fields_to_collect:
        items.extend(_as_str_tuple(getattr(value, field, ())))
    return tuple(sorted(set(items)))


def _active_ids(value: object) -> tuple[str, ...]:
    fields_to_collect = ("active_policy_ids", "active_contract_ids", "active_manifest_ids", "active_rule_ids")
    items: list[str] = []
    for field in fields_to_collect:
        items.extend(_as_str_tuple(getattr(value, field, ())))
    return tuple(sorted(set(items)))


def _trace_id(value: object, subject_id: str) -> str:
    trace_id = getattr(value, "trace_id", "")
    if isinstance(trace_id, str) and trace_id:
        return trace_id
    packet = getattr(value, "packet", None)
    packet_trace_id = getattr(packet, "trace_id", "")
    if isinstance(packet_trace_id, str) and packet_trace_id:
        return packet_trace_id
    if _nested_observation_id(value):
        return subject_id
    return ""


def _identity_keys(value: object, subject: ControlPlaneCrossReviewSubject) -> tuple[str, ...]:
    keys = [f"subject:{subject.subject_id}"]
    if subject.trace_id:
        keys.append(f"trace:{subject.trace_id}")
    for field in (
        "referenced_decision_ids",
        "referenced_rule_ids",
        "referenced_tool_manifest_ids",
        "referenced_work_item_ids",
        "runtime_state_snapshot_ids",
        "manifest_ids",
        "policy_ids",
        "item_ids",
    ):
        for item in _as_str_tuple(getattr(value, field, ())):
            keys.append(f"{field}:{item}")
    return tuple(sorted(set(keys)))


def _finding(
    code: str,
    severity: str,
    subject_ids: Iterable[str],
    detail: str,
) -> ControlPlaneCrossReviewConsistencyFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneCrossReviewConsistencyError(f"unknown severity: {severity}")
    return ControlPlaneCrossReviewConsistencyFinding(
        code=code,
        severity=severity,
        subject_ids=tuple(subject_ids),
        detail=detail,
    )


def _normalize_subject(value: object, index: int) -> tuple[ControlPlaneCrossReviewSubject, tuple[ControlPlaneCrossReviewConsistencyFinding, ...]]:
    if not _field_names(value):
        raise ControlPlaneCrossReviewConsistencyError("review subjects must expose fields")
    subject_kind = _subject_kind(value)
    subject_id = _subject_id(value, index, subject_kind)
    if not _is_path_segment_safe(subject_id):
        raise ControlPlaneCrossReviewConsistencyError("subject ids must be path-segment safe")
    finding_count = getattr(value, "finding_count", 0)
    if not isinstance(finding_count, int) or finding_count < 0:
        raise ControlPlaneCrossReviewConsistencyError("finding_count must be a non-negative integer")
    findings_tuple = tuple(getattr(value, "findings", ()) or ())
    finding_codes = _as_str_tuple(getattr(value, "finding_codes", ()))
    severity_counts = getattr(value, "severity_counts", {})
    if not isinstance(severity_counts, dict):
        raise ControlPlaneCrossReviewConsistencyError("severity_counts must be a dictionary")
    blockers = _as_str_tuple(getattr(value, "blockers", ()))
    missing_evidence = _as_str_tuple(getattr(value, "missing_evidence", ()))
    blocked_ids = _blocked_ids(value)
    ready_ids = _ready_ids(value)
    allowed_ids = _allowed_ids(value)
    active_ids = _active_ids(value)
    trace_id = _trace_id(value, subject_id)
    replay_digest = str(getattr(value, "replay_digest", "") or getattr(getattr(value, "packet", None), "replay_digest", "") or "")
    subject = ControlPlaneCrossReviewSubject(
        subject_id=subject_id,
        subject_kind=subject_kind,
        subject_status=_status(value),
        trace_id=trace_id,
        replay_digest=replay_digest,
        finding_count=finding_count,
        blocker_count=len(blockers),
        missing_evidence_count=len(missing_evidence),
        blocked_ids=_safe_tuple(blocked_ids, "blocked_ids"),
        ready_ids=_safe_tuple(ready_ids, "ready_ids"),
        allowed_ids=_safe_tuple(allowed_ids, "allowed_ids"),
        active_ids=_safe_tuple(active_ids, "active_ids"),
        identity_keys=(),
    )
    subject = ControlPlaneCrossReviewSubject(
        **{**asdict(subject), "identity_keys": _identity_keys(value, subject)}
    )
    local_findings: list[ControlPlaneCrossReviewConsistencyFinding] = []
    if getattr(value, "state_change", "none") != "none":
        local_findings.append(_finding("subject_mutates_state", "critical", (subject_id,), "state_change is not none"))
    if "non-authoritative" not in str(getattr(value, "authority", "")):
        local_findings.append(_finding("subject_lacks_non_authority", "critical", (subject_id,), "authority is not non-authoritative"))
    if getattr(value, "must_not_execute_automatically", True) is not True:
        local_findings.append(_finding("subject_allows_auto_execution", "critical", (subject_id,), "must_not_execute_automatically is false"))
    if finding_count != len(findings_tuple):
        local_findings.append(_finding("subject_forged_finding_count", "critical", (subject_id,), "finding_count does not match findings"))
    if findings_tuple:
        actual_codes = tuple(str(getattr(finding, "code", "")) for finding in findings_tuple)
        if finding_codes != actual_codes:
            local_findings.append(_finding("subject_forged_finding_codes", "critical", (subject_id,), "finding_codes do not match findings"))
        actual_severity_counts = _count(str(getattr(finding, "severity", "unknown")) for finding in findings_tuple)
        normalized_severity_counts = dict(sorted((str(key), int(item)) for key, item in severity_counts.items()))
        if normalized_severity_counts != actual_severity_counts:
            local_findings.append(
                _finding("subject_forged_severity_counts", "critical", (subject_id,), "severity_counts do not match findings")
            )
    if subject.subject_status in _CLEAN_STATUSES and blocked_ids:
        local_findings.append(_finding("clean_status_with_blocked_ids", "high", (subject_id,), ",".join(blocked_ids)))
    if subject.subject_status in _CLEAN_STATUSES and blockers:
        local_findings.append(_finding("clean_status_with_blockers", "high", (subject_id,), ",".join(blockers)))
    if subject.subject_status in _CLEAN_STATUSES and missing_evidence:
        local_findings.append(_finding("clean_status_with_missing_evidence", "high", (subject_id,), ",".join(missing_evidence)))
    if subject.subject_status == "unknown":
        local_findings.append(_finding("unknown_subject_status", "medium", (subject_id,), "subject status was not supplied"))
    if any(token in subject.subject_status for token in _BLOCKING_STATUS_TOKENS) and not (
        finding_count or blockers or missing_evidence or blocked_ids
    ):
        local_findings.append(_finding("blocked_status_without_structured_evidence", "medium", (subject_id,), subject.subject_status))
    if hasattr(value, "action_posture") and getattr(value, "action_posture") == "advisory_review_only":
        if getattr(value, "integrity_status", "control_plane_integrity_preserved") != "control_plane_integrity_preserved":
            local_findings.append(_finding("action_clean_over_integrity_drift", "critical", (subject_id,), str(getattr(value, "integrity_status"))))
        if getattr(value, "packet_verdict", "packet_advisory_review_only") != "packet_advisory_review_only":
            local_findings.append(_finding("action_clean_over_packet_blocker", "high", (subject_id,), str(getattr(value, "packet_verdict"))))
        if blockers:
            local_findings.append(_finding("action_clean_with_blockers", "high", (subject_id,), ",".join(blockers)))
    return subject, tuple(local_findings)


def _is_blocked_dependency(subject: ControlPlaneCrossReviewSubject) -> bool:
    return (
        subject.finding_count > 0
        or subject.blocker_count > 0
        or subject.missing_evidence_count > 0
        or bool(subject.blocked_ids)
        or subject.subject_status not in _CLEAN_STATUSES
    )


def _cross_findings(subjects: tuple[ControlPlaneCrossReviewSubject, ...]) -> tuple[ControlPlaneCrossReviewConsistencyFinding, ...]:
    findings: list[ControlPlaneCrossReviewConsistencyFinding] = []
    ids = [subject.subject_id for subject in subjects]
    for subject_id in sorted({item for item in ids if ids.count(item) > 1}):
        findings.append(_finding("duplicate_subject_id", "critical", (subject_id,), "same subject id appears more than once"))

    by_identity: dict[str, list[ControlPlaneCrossReviewSubject]] = {}
    for subject in subjects:
        for key in subject.identity_keys:
            by_identity.setdefault(key, []).append(subject)

    for key, grouped in sorted(by_identity.items()):
        if len(grouped) < 2:
            continue
        statuses = {item.subject_status for item in grouped}
        has_clean = any(item.subject_status in _CLEAN_STATUSES for item in grouped)
        has_blocked = any(_is_blocked_dependency(item) for item in grouped)
        if has_clean and has_blocked and len(statuses) > 1:
            findings.append(
                _finding(
                    "shared_identity_status_conflict",
                    "high",
                    (item.subject_id for item in grouped),
                    key,
                )
            )
        digests = {item.replay_digest for item in grouped if item.replay_digest}
        if len(digests) > 1:
            findings.append(
                _finding(
                    "shared_identity_replay_digest_conflict",
                    "critical",
                    (item.subject_id for item in grouped),
                    key,
                )
            )

    blocked_dependencies = tuple(subject for subject in subjects if _is_blocked_dependency(subject))
    if blocked_dependencies:
        blocked_ids = tuple(subject.subject_id for subject in blocked_dependencies)
        for subject in subjects:
            if subject.ready_ids and subject not in blocked_dependencies:
                findings.append(_finding("ready_subject_over_blocked_dependency", "high", (subject.subject_id, *blocked_ids), ",".join(subject.ready_ids)))
            if subject.allowed_ids and subject not in blocked_dependencies:
                findings.append(_finding("allowed_tool_over_blocked_dependency", "high", (subject.subject_id, *blocked_ids), ",".join(subject.allowed_ids)))
            if subject.active_ids and subject not in blocked_dependencies:
                findings.append(_finding("active_candidate_over_blocked_dependency", "high", (subject.subject_id, *blocked_ids), ",".join(subject.active_ids)))
    return tuple(findings)


def _validate_report(report: ControlPlaneCrossReviewConsistencyReport) -> None:
    if report.state_change != "none":
        raise ControlPlaneCrossReviewConsistencyError("consistency eval must not mutate state")
    if "non-authoritative" not in report.authority:
        raise ControlPlaneCrossReviewConsistencyError("consistency eval must remain non-authoritative")
    if (
        not report.consistency_eval_is_not_permission
        or not report.consistency_status_is_not_truth
        or not report.consistency_eval_is_not_execution_approval
        or not report.consistency_eval_is_not_scheduler
        or not report.consistency_eval_is_not_runtime_gate
        or not report.consistency_eval_is_not_state_store
        or not report.finding_is_not_truth
        or not report.must_not_execute_automatically
    ):
        raise ControlPlaneCrossReviewConsistencyError("consistency eval guardrails drifted")
    if report.subject_count != len(report.subjects):
        raise ControlPlaneCrossReviewConsistencyError("subject_count does not match subjects")
    if report.subject_ids != tuple(subject.subject_id for subject in report.subjects):
        raise ControlPlaneCrossReviewConsistencyError("subject_ids do not match subjects")
    if report.finding_count != len(report.findings):
        raise ControlPlaneCrossReviewConsistencyError("finding_count does not match findings")
    if report.finding_codes != tuple(finding.code for finding in report.findings):
        raise ControlPlaneCrossReviewConsistencyError("finding_codes do not match findings")
    if report.severity_counts != _count(finding.severity for finding in report.findings):
        raise ControlPlaneCrossReviewConsistencyError("severity_counts do not match findings")
    expected = "cross_review_consistency_preserved"
    if any(finding.severity in {"critical", "high"} for finding in report.findings):
        expected = "cross_review_consistency_drift_observed"
    elif report.findings:
        expected = "cross_review_consistency_attention_required"
    if report.eval_status != expected:
        raise ControlPlaneCrossReviewConsistencyError("eval_status does not match findings")


def evaluate_control_plane_cross_review_consistency(
    review_subjects: Iterable[object],
    *,
    review_as_of: str,
) -> ControlPlaneCrossReviewConsistencyReport:
    """Detect contradictions between caller-supplied advisory review artifacts."""

    _parse_date(review_as_of, "review_as_of")
    raw_subjects = tuple(review_subjects)
    if not raw_subjects:
        raise ControlPlaneCrossReviewConsistencyError("at least one review subject is required")

    subjects: list[ControlPlaneCrossReviewSubject] = []
    findings: list[ControlPlaneCrossReviewConsistencyFinding] = []
    for index, subject_obj in enumerate(raw_subjects):
        subject, local_findings = _normalize_subject(subject_obj, index)
        subjects.append(subject)
        findings.extend(local_findings)
    subjects_tuple = tuple(subjects)
    findings.extend(_cross_findings(subjects_tuple))
    finding_items = tuple(findings)
    blocked_dependency_ids = tuple(subject.subject_id for subject in subjects_tuple if _is_blocked_dependency(subject))
    eval_status = "cross_review_consistency_preserved"
    if any(finding.severity in {"critical", "high"} for finding in finding_items):
        eval_status = "cross_review_consistency_drift_observed"
    elif finding_items:
        eval_status = "cross_review_consistency_attention_required"
    shared_identities = {
        key
        for subject in subjects_tuple
        for key in subject.identity_keys
        if sum(1 for item in subjects_tuple if key in item.identity_keys) > 1
    }
    report = ControlPlaneCrossReviewConsistencyReport(
        schema_version="1",
        eval_role="detects_contradictions_between_control_plane_advisory_reviews",
        eval_status=eval_status,
        review_as_of=review_as_of,
        subject_count=len(subjects_tuple),
        subject_ids=tuple(subject.subject_id for subject in subjects_tuple),
        subject_kind_counts=_count(subject.subject_kind for subject in subjects_tuple),
        subject_status_counts=_count(subject.subject_status for subject in subjects_tuple),
        shared_identity_count=len(shared_identities),
        blocked_dependency_subject_ids=blocked_dependency_ids,
        ready_subject_ids=tuple(subject.subject_id for subject in subjects_tuple if subject.ready_ids),
        allowed_subject_ids=tuple(subject.subject_id for subject in subjects_tuple if subject.allowed_ids),
        active_subject_ids=tuple(subject.subject_id for subject in subjects_tuple if subject.active_ids),
        finding_count=len(finding_items),
        severity_counts=_count(finding.severity for finding in finding_items),
        finding_codes=tuple(finding.code for finding in finding_items),
        subjects=subjects_tuple,
        findings=finding_items,
    )
    _validate_report(report)
    return report


def render_control_plane_cross_review_consistency_json(report: ControlPlaneCrossReviewConsistencyReport) -> str:
    _validate_report(report)
    return json.dumps(asdict(report), indent=2, sort_keys=True) + "\n"


def render_control_plane_cross_review_consistency_markdown(report: ControlPlaneCrossReviewConsistencyReport) -> str:
    _validate_report(report)
    lines = [
        "# Control Plane Cross-Review Consistency Eval",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory control-plane cross-review consistency eval only",
        "- consistency_eval_is_not_permission: true",
        "- consistency_status_is_not_truth: true",
        "- consistency_eval_is_not_execution_approval: true",
        "- consistency_eval_is_not_scheduler: true",
        "- consistency_eval_is_not_runtime_gate: true",
        "- consistency_eval_is_not_state_store: true",
        "- finding_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Summary",
        "",
        f"- eval_status: {report.eval_status}",
        f"- subject_count: {report.subject_count}",
        f"- shared_identity_count: {report.shared_identity_count}",
        f"- blocked_dependency_subject_ids: {', '.join(report.blocked_dependency_subject_ids) if report.blocked_dependency_subject_ids else 'none'}",
        f"- ready_subject_ids: {', '.join(report.ready_subject_ids) if report.ready_subject_ids else 'none'}",
        f"- allowed_subject_ids: {', '.join(report.allowed_subject_ids) if report.allowed_subject_ids else 'none'}",
        f"- active_subject_ids: {', '.join(report.active_subject_ids) if report.active_subject_ids else 'none'}",
        f"- finding_count: {report.finding_count}",
        "",
        "## Findings",
    ]
    if not report.findings:
        lines.append("- none")
    for finding in report.findings:
        lines.append(
            f"- {finding.severity}: {finding.code} ({', '.join(finding.subject_ids)}) - {finding.detail}"
        )
    return "\n".join(lines) + "\n"
