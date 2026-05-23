from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import date
from typing import Iterable, Mapping


class ControlPlaneLoopStopEvalError(ValueError):
    """Raised when loop-stop eval inputs cross the advisory boundary."""


@dataclass(frozen=True)
class ControlPlaneLoopStopStep:
    loop_id: str
    iteration_id: str
    sequence_index: int
    review_as_of: str
    subject_id: str
    subject_kind: str
    continuation_claim: str
    validation_status: str
    validation_revision: str
    expected_revision: str
    queue_head_id: str
    queue_head_status: str
    queue_head_latest: bool
    dependencies_satisfied: bool
    trigger_status: str
    stop_condition_id: str
    stop_condition_status: str
    human_decision_ids: tuple[str, ...]
    evidence_ids: tuple[str, ...]
    evidence_digest: str
    referenced_review_ids: tuple[str, ...]
    referenced_review_statuses: tuple[str, ...]
    blocked_ids: tuple[str, ...]
    missing_evidence_ids: tuple[str, ...]
    ready_ids: tuple[str, ...]
    observed_frontier_ids: tuple[str, ...]
    active_agent_ids: tuple[str, ...]
    agent_focus_id: str
    auto_continue_requested: bool
    claims_scheduler_authority: bool
    grants_execution_permission: bool
    mutates_state: bool
    reads_live_queue: bool
    summary: str
    rationale: str


@dataclass(frozen=True)
class ControlPlaneLoopStopEvalFinding:
    code: str
    severity: str
    step_ids: tuple[str, ...]
    detail: str


@dataclass(frozen=True)
class ControlPlaneLoopStopEvalReport:
    schema_version: str
    eval_role: str
    eval_status: str
    review_as_of: str
    loop_count: int
    step_count: int
    loop_ids: tuple[str, ...]
    step_ids: tuple[str, ...]
    continued_step_ids: tuple[str, ...]
    stopped_step_ids: tuple[str, ...]
    unsafe_continuation_step_ids: tuple[str, ...]
    met_stop_step_ids: tuple[str, ...]
    missing_human_override_step_ids: tuple[str, ...]
    repeated_evidence_step_ids: tuple[str, ...]
    single_flight_drift_step_ids: tuple[str, ...]
    finding_count: int
    severity_counts: dict[str, int]
    finding_codes: tuple[str, ...]
    steps: tuple[ControlPlaneLoopStopStep, ...]
    findings: tuple[ControlPlaneLoopStopEvalFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory control-plane loop stop eval only"
    loop_stop_eval_is_not_permission: bool = True
    loop_stop_status_is_not_truth: bool = True
    loop_stop_eval_is_not_execution_approval: bool = True
    loop_stop_eval_is_not_scheduler: bool = True
    loop_stop_eval_is_not_runtime_gate: bool = True
    loop_stop_eval_is_not_state_store: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


_SEVERITIES = {"critical", "high", "medium", "low"}
_CONTINUATION_CLAIMS = {"continue", "stop", "pause", "blocked", "human_checkpoint", "closed"}
_VALIDATION_STATUSES = {"passed", "failed", "missing", "stale", "unknown"}
_QUEUE_STATUSES = {"open", "waiting", "blocked", "resolved", "superseded", "unknown"}
_TRIGGER_STATUSES = {"active", "missing", "closed", "not_required", "unknown"}
_STOP_STATUSES = {"not_met", "met", "unknown"}
_REVIEW_BLOCKING_TOKENS = ("blocked", "drift", "invalid", "attention_required", "human_review", "failed")
_FORBIDDEN_TEXT_TOKENS = (
    "permission to continue",
    "permission to execute",
    "execution approval",
    "approved to continue",
    "approved to execute",
    "grants permission",
    "permission_granted",
    "scheduler selected",
    "selected next action",
    "dispatch automatically",
    "source of truth",
    "canonical gate",
    "runtime authority",
)
_NEGATIVE_TEXT_MARKERS = (
    "not permission",
    "not execution approval",
    "not runtime authority",
    "not a scheduler",
    "not a runtime gate",
    "not truth",
    "does not grant",
    "does not approve",
    "must not execute",
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
        raise ControlPlaneLoopStopEvalError(f"{field} must be an ISO date") from exc


def _is_path_segment_safe(value: str) -> bool:
    return bool(value) and all(char in "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789._-" for char in value)


def _safe_tuple(values: Iterable[str], field: str) -> tuple[str, ...]:
    items = tuple(values)
    if any(not _is_path_segment_safe(item) for item in items):
        raise ControlPlaneLoopStopEvalError(f"{field} values must be path-segment safe")
    return items


def _as_str_tuple(value: object, field: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, (tuple, list)):
        raise ControlPlaneLoopStopEvalError(f"{field} must be a list or tuple")
    items = tuple(str(item).strip() for item in value if str(item).strip())
    return _safe_tuple(items, field)


def _required_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field)
    if not isinstance(value, str) or not value.strip():
        raise ControlPlaneLoopStopEvalError(f"missing required loop-stop field: {field}")
    return value.strip()


def _optional_str(payload: Mapping[str, object], field: str) -> str:
    value = payload.get(field, "")
    if value is None:
        return ""
    if not isinstance(value, str):
        raise ControlPlaneLoopStopEvalError(f"{field} must be a string")
    return value.strip()


def _required_int(payload: Mapping[str, object], field: str) -> int:
    value = payload.get(field)
    if not isinstance(value, int) or value < 1:
        raise ControlPlaneLoopStopEvalError(f"{field} must be a positive integer")
    return value


def _required_bool(payload: Mapping[str, object], field: str) -> bool:
    value = payload.get(field)
    if not isinstance(value, bool):
        raise ControlPlaneLoopStopEvalError(f"{field} must be boolean")
    return value


def _step_from_payload(payload: ControlPlaneLoopStopStep | Mapping[str, object]) -> ControlPlaneLoopStopStep:
    if isinstance(payload, ControlPlaneLoopStopStep):
        step = payload
    elif isinstance(payload, Mapping):
        step = ControlPlaneLoopStopStep(
            loop_id=_required_str(payload, "loop_id"),
            iteration_id=_required_str(payload, "iteration_id"),
            sequence_index=_required_int(payload, "sequence_index"),
            review_as_of=_required_str(payload, "review_as_of"),
            subject_id=_required_str(payload, "subject_id"),
            subject_kind=_required_str(payload, "subject_kind"),
            continuation_claim=_required_str(payload, "continuation_claim"),
            validation_status=_required_str(payload, "validation_status"),
            validation_revision=_optional_str(payload, "validation_revision"),
            expected_revision=_optional_str(payload, "expected_revision"),
            queue_head_id=_optional_str(payload, "queue_head_id"),
            queue_head_status=_required_str(payload, "queue_head_status"),
            queue_head_latest=_required_bool(payload, "queue_head_latest"),
            dependencies_satisfied=_required_bool(payload, "dependencies_satisfied"),
            trigger_status=_required_str(payload, "trigger_status"),
            stop_condition_id=_optional_str(payload, "stop_condition_id"),
            stop_condition_status=_required_str(payload, "stop_condition_status"),
            human_decision_ids=_as_str_tuple(payload.get("human_decision_ids"), "human_decision_ids"),
            evidence_ids=_as_str_tuple(payload.get("evidence_ids"), "evidence_ids"),
            evidence_digest=_optional_str(payload, "evidence_digest"),
            referenced_review_ids=_as_str_tuple(payload.get("referenced_review_ids"), "referenced_review_ids"),
            referenced_review_statuses=_as_str_tuple(
                payload.get("referenced_review_statuses"),
                "referenced_review_statuses",
            ),
            blocked_ids=_as_str_tuple(payload.get("blocked_ids"), "blocked_ids"),
            missing_evidence_ids=_as_str_tuple(payload.get("missing_evidence_ids"), "missing_evidence_ids"),
            ready_ids=_as_str_tuple(payload.get("ready_ids"), "ready_ids"),
            observed_frontier_ids=_as_str_tuple(payload.get("observed_frontier_ids"), "observed_frontier_ids"),
            active_agent_ids=_as_str_tuple(payload.get("active_agent_ids"), "active_agent_ids"),
            agent_focus_id=_optional_str(payload, "agent_focus_id"),
            auto_continue_requested=_required_bool(payload, "auto_continue_requested"),
            claims_scheduler_authority=_required_bool(payload, "claims_scheduler_authority"),
            grants_execution_permission=_required_bool(payload, "grants_execution_permission"),
            mutates_state=_required_bool(payload, "mutates_state"),
            reads_live_queue=_required_bool(payload, "reads_live_queue"),
            summary=_optional_str(payload, "summary"),
            rationale=_optional_str(payload, "rationale"),
        )
    else:
        raise ControlPlaneLoopStopEvalError("loop-stop steps must be dataclasses or mappings")

    _parse_date(step.review_as_of, "step.review_as_of")
    for field, value in (
        ("loop_id", step.loop_id),
        ("iteration_id", step.iteration_id),
        ("subject_id", step.subject_id),
    ):
        if not _is_path_segment_safe(value):
            raise ControlPlaneLoopStopEvalError(f"{field} must be path-segment safe")
    if step.continuation_claim not in _CONTINUATION_CLAIMS:
        raise ControlPlaneLoopStopEvalError(f"unknown continuation_claim: {step.continuation_claim}")
    if step.validation_status not in _VALIDATION_STATUSES:
        raise ControlPlaneLoopStopEvalError(f"unknown validation_status: {step.validation_status}")
    if step.queue_head_status not in _QUEUE_STATUSES:
        raise ControlPlaneLoopStopEvalError(f"unknown queue_head_status: {step.queue_head_status}")
    if step.trigger_status not in _TRIGGER_STATUSES:
        raise ControlPlaneLoopStopEvalError(f"unknown trigger_status: {step.trigger_status}")
    if step.stop_condition_status not in _STOP_STATUSES:
        raise ControlPlaneLoopStopEvalError(f"unknown stop_condition_status: {step.stop_condition_status}")
    return step


def _finding(code: str, severity: str, step_ids: Iterable[str], detail: str) -> ControlPlaneLoopStopEvalFinding:
    if severity not in _SEVERITIES:
        raise ControlPlaneLoopStopEvalError(f"unknown severity: {severity}")
    return ControlPlaneLoopStopEvalFinding(code, severity, tuple(step_ids), detail)


def _is_continue(step: ControlPlaneLoopStopStep) -> bool:
    return step.continuation_claim == "continue"


def _has_human_override(step: ControlPlaneLoopStopStep) -> bool:
    return bool(step.human_decision_ids and step.evidence_ids)


def _has_blocking_review_status(step: ControlPlaneLoopStopStep) -> bool:
    return any(any(token in status for token in _REVIEW_BLOCKING_TOKENS) for status in step.referenced_review_statuses)


def _has_unqualified_authority_text(step: ControlPlaneLoopStopStep) -> bool:
    text = f"{step.summary} {step.rationale}".lower().replace("_", " ").replace("-", " ")
    normalized = " ".join(text.split())
    if not normalized:
        return False
    if any(marker in normalized for marker in _NEGATIVE_TEXT_MARKERS):
        return False
    return any(token in normalized for token in _FORBIDDEN_TEXT_TOKENS)


def _stop_condition_drift(prev: ControlPlaneLoopStopStep, current: ControlPlaneLoopStopStep) -> bool:
    if prev.loop_id != current.loop_id:
        return False
    if not prev.stop_condition_id:
        return False
    if prev.stop_condition_status != "met":
        return False
    if current.stop_condition_id == prev.stop_condition_id and current.stop_condition_status == "met":
        return False
    return not _has_human_override(current)


def _same_digest(prev: ControlPlaneLoopStopStep, current: ControlPlaneLoopStopStep) -> bool:
    return (
        prev.loop_id == current.loop_id
        and prev.subject_id == current.subject_id
        and bool(prev.evidence_digest)
        and prev.evidence_digest == current.evidence_digest
    )


def _report_status(findings: tuple[ControlPlaneLoopStopEvalFinding, ...]) -> str:
    severities = {finding.severity for finding in findings}
    if "critical" in severities or "high" in severities:
        return "loop_frame_blocked"
    if findings:
        return "loop_frame_attention_required"
    return "loop_frame_observed"


def evaluate_control_plane_loop_stop(
    steps: Iterable[ControlPlaneLoopStopStep | Mapping[str, object]],
    *,
    review_as_of: str,
    single_flight: bool = True,
) -> ControlPlaneLoopStopEvalReport:
    _parse_date(review_as_of, "review_as_of")
    normalized_steps = tuple(_step_from_payload(step) for step in steps)
    if not normalized_steps:
        raise ControlPlaneLoopStopEvalError("at least one loop-stop step is required")

    sorted_steps = tuple(sorted(normalized_steps, key=lambda step: (step.loop_id, step.sequence_index, step.iteration_id)))
    step_ids = tuple(step.iteration_id for step in sorted_steps)
    if len(set(step_ids)) != len(step_ids):
        raise ControlPlaneLoopStopEvalError("iteration_id values must be unique")

    findings: list[ControlPlaneLoopStopEvalFinding] = []
    unsafe: set[str] = set()
    missing_human_override: set[str] = set()
    repeated_evidence: set[str] = set()
    single_flight_drift: set[str] = set()
    met_stop_ids = {step.iteration_id for step in sorted_steps if step.stop_condition_status == "met"}

    continued = {step.iteration_id for step in sorted_steps if _is_continue(step)}
    stopped = {step.iteration_id for step in sorted_steps if not _is_continue(step)}

    for step in sorted_steps:
        if step.mutates_state:
            findings.append(_finding("loop_step_mutates_state", "critical", (step.iteration_id,), "loop-stop eval input claims state mutation"))
        if step.reads_live_queue:
            findings.append(_finding("loop_step_reads_live_queue", "critical", (step.iteration_id,), "loop-stop eval input claims live queue read"))
        if step.claims_scheduler_authority:
            findings.append(_finding("loop_step_claims_scheduler_authority", "critical", (step.iteration_id,), "loop-stop eval input claims scheduler authority"))
        if step.grants_execution_permission:
            findings.append(_finding("loop_step_grants_execution_permission", "critical", (step.iteration_id,), "loop-stop eval input grants execution permission"))
        if step.auto_continue_requested:
            findings.append(_finding("auto_continue_requested", "critical", (step.iteration_id,), "loop frame requests automatic continuation"))
            unsafe.add(step.iteration_id)
        if _has_unqualified_authority_text(step):
            findings.append(_finding("loop_authority_text_laundering", "high", (step.iteration_id,), "summary or rationale launders permission/scheduler/runtime authority"))

        if not _is_continue(step):
            continue

        if step.validation_status != "passed":
            findings.append(_finding("continue_with_invalid_validation", "critical", (step.iteration_id,), f"continuation claimed with validation_status={step.validation_status}"))
            unsafe.add(step.iteration_id)
        if step.expected_revision and step.validation_revision and step.expected_revision != step.validation_revision:
            findings.append(_finding("continue_with_validation_revision_drift", "high", (step.iteration_id,), "validation revision does not match expected revision"))
            unsafe.add(step.iteration_id)
        if step.stop_condition_status == "met":
            findings.append(_finding("continue_after_stop_condition_met", "critical", (step.iteration_id,), "continuation claimed after supplied stop condition was met"))
            unsafe.add(step.iteration_id)
            if not _has_human_override(step):
                missing_human_override.add(step.iteration_id)
        if step.trigger_status in {"missing", "closed", "unknown"} and step.subject_kind not in {"docs_only", "proof"}:
            findings.append(_finding("continue_without_active_trigger", "high", (step.iteration_id,), f"continuation claimed with trigger_status={step.trigger_status}"))
            unsafe.add(step.iteration_id)
        if step.queue_head_status != "open":
            findings.append(_finding("continue_over_non_open_queue_head", "high", (step.iteration_id,), f"queue head status is {step.queue_head_status}"))
            unsafe.add(step.iteration_id)
        if not step.queue_head_latest:
            findings.append(_finding("continue_over_non_latest_queue_head", "high", (step.iteration_id,), "queue head is not latest"))
            unsafe.add(step.iteration_id)
        if not step.dependencies_satisfied:
            findings.append(_finding("continue_with_unsatisfied_dependencies", "high", (step.iteration_id,), "dependencies are not satisfied"))
            unsafe.add(step.iteration_id)
        if step.blocked_ids:
            findings.append(_finding("continue_with_blocked_ids", "high", (step.iteration_id,), "continuation carries blocked ids"))
            unsafe.add(step.iteration_id)
        if step.missing_evidence_ids:
            findings.append(_finding("continue_with_missing_evidence", "medium", (step.iteration_id,), "continuation carries missing evidence ids"))
            unsafe.add(step.iteration_id)
        if _has_blocking_review_status(step):
            findings.append(_finding("continue_over_blocking_review_status", "high", (step.iteration_id,), "referenced review statuses contain blocking evidence"))
            unsafe.add(step.iteration_id)
        if step.agent_focus_id and step.queue_head_id and step.agent_focus_id != step.queue_head_id:
            findings.append(_finding("agent_focus_queue_head_drift", "medium", (step.iteration_id,), "agent focus does not match supplied queue head"))
        if single_flight and len(step.observed_frontier_ids) > 1:
            findings.append(_finding("single_flight_frontier_drift", "high", (step.iteration_id,), "multiple frontier ids supplied while single_flight is true"))
            unsafe.add(step.iteration_id)
            single_flight_drift.add(step.iteration_id)
        if single_flight and len(step.ready_ids) > 1:
            findings.append(_finding("single_flight_ready_drift", "high", (step.iteration_id,), "multiple ready ids supplied while single_flight is true"))
            unsafe.add(step.iteration_id)
            single_flight_drift.add(step.iteration_id)

    by_loop: dict[str, list[ControlPlaneLoopStopStep]] = {}
    for step in sorted_steps:
        by_loop.setdefault(step.loop_id, []).append(step)

    for loop_steps in by_loop.values():
        for prev, current in zip(loop_steps, loop_steps[1:]):
            if _stop_condition_drift(prev, current):
                findings.append(_finding("stop_condition_drift_without_evidence", "critical", (prev.iteration_id, current.iteration_id), "met stop condition disappeared without human/evidence override"))
                unsafe.add(current.iteration_id)
                missing_human_override.add(current.iteration_id)
            if _is_continue(current) and _same_digest(prev, current) and not _has_human_override(current):
                findings.append(_finding("continue_without_new_evidence", "medium", (prev.iteration_id, current.iteration_id), "continuation repeats the same evidence digest without human/evidence override"))
                unsafe.add(current.iteration_id)
                repeated_evidence.add(current.iteration_id)

    severity_counts = _count(finding.severity for finding in findings)
    report = ControlPlaneLoopStopEvalReport(
        schema_version="1",
        eval_role="control_plane_loop_stop_eval",
        eval_status=_report_status(tuple(findings)),
        review_as_of=review_as_of,
        loop_count=len({step.loop_id for step in sorted_steps}),
        step_count=len(sorted_steps),
        loop_ids=tuple(sorted({step.loop_id for step in sorted_steps})),
        step_ids=step_ids,
        continued_step_ids=tuple(sorted(continued)),
        stopped_step_ids=tuple(sorted(stopped)),
        unsafe_continuation_step_ids=tuple(sorted(unsafe)),
        met_stop_step_ids=tuple(sorted(met_stop_ids)),
        missing_human_override_step_ids=tuple(sorted(missing_human_override)),
        repeated_evidence_step_ids=tuple(sorted(repeated_evidence)),
        single_flight_drift_step_ids=tuple(sorted(single_flight_drift)),
        finding_count=len(findings),
        severity_counts=severity_counts,
        finding_codes=tuple(finding.code for finding in findings),
        steps=sorted_steps,
        findings=tuple(findings),
    )
    _assert_report_integrity(report)
    return report


def _assert_report_integrity(report: ControlPlaneLoopStopEvalReport) -> None:
    if report.state_change != "none" or "non-authoritative" not in report.authority:
        raise ControlPlaneLoopStopEvalError("loop-stop report must remain non-authoritative with state_change none")
    guardrails = (
        report.loop_stop_eval_is_not_permission,
        report.loop_stop_status_is_not_truth,
        report.loop_stop_eval_is_not_execution_approval,
        report.loop_stop_eval_is_not_scheduler,
        report.loop_stop_eval_is_not_runtime_gate,
        report.loop_stop_eval_is_not_state_store,
        report.finding_is_not_truth,
        report.must_not_execute_automatically,
    )
    if not all(guardrails):
        raise ControlPlaneLoopStopEvalError("loop-stop guardrails must remain true")
    if report.finding_count != len(report.findings):
        raise ControlPlaneLoopStopEvalError("finding_count does not match findings")
    if report.severity_counts != _count(finding.severity for finding in report.findings):
        raise ControlPlaneLoopStopEvalError("severity_counts does not match findings")
    if report.finding_codes != tuple(finding.code for finding in report.findings):
        raise ControlPlaneLoopStopEvalError("finding_codes does not match findings")
    if report.step_count != len(report.steps):
        raise ControlPlaneLoopStopEvalError("step_count does not match steps")
    if report.step_ids != tuple(step.iteration_id for step in report.steps):
        raise ControlPlaneLoopStopEvalError("step_ids does not match steps")


def render_control_plane_loop_stop_json(report: ControlPlaneLoopStopEvalReport) -> str:
    _assert_report_integrity(report)
    return json.dumps(asdict(report), indent=2, sort_keys=True)


def render_control_plane_loop_stop_markdown(report: ControlPlaneLoopStopEvalReport) -> str:
    _assert_report_integrity(report)
    lines = [
        "# Control Plane Loop Stop Eval",
        "",
        f"- schema_version: {report.schema_version}",
        f"- eval_role: {report.eval_role}",
        f"- eval_status: {report.eval_status}",
        f"- review_as_of: {report.review_as_of}",
        f"- loop_count: {report.loop_count}",
        f"- step_count: {report.step_count}",
        f"- finding_count: {report.finding_count}",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- loop_stop_eval_is_not_permission: {str(report.loop_stop_eval_is_not_permission).lower()}",
        f"- loop_stop_status_is_not_truth: {str(report.loop_stop_status_is_not_truth).lower()}",
        f"- loop_stop_eval_is_not_execution_approval: {str(report.loop_stop_eval_is_not_execution_approval).lower()}",
        f"- loop_stop_eval_is_not_scheduler: {str(report.loop_stop_eval_is_not_scheduler).lower()}",
        f"- loop_stop_eval_is_not_runtime_gate: {str(report.loop_stop_eval_is_not_runtime_gate).lower()}",
        f"- loop_stop_eval_is_not_state_store: {str(report.loop_stop_eval_is_not_state_store).lower()}",
        f"- finding_is_not_truth: {str(report.finding_is_not_truth).lower()}",
        f"- must_not_execute_automatically: {str(report.must_not_execute_automatically).lower()}",
        "",
        "## Findings",
    ]
    if not report.findings:
        lines.append("- none")
    else:
        for finding in report.findings:
            lines.append(f"- {finding.severity}: {finding.code} ({', '.join(finding.step_ids)}) - {finding.detail}")
    return "\n".join(lines)
