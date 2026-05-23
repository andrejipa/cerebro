from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from typing import Any

from experiments.control_plane_event_ledger import (
    ControlPlaneEventLedgerError,
    parse_control_plane_event_ledger_jsonl,
)


_AUTHORITY = "non-authoritative; advisory control-plane replay evaluation only"
_SCHEMA_VERSION = "1"


@dataclass(frozen=True)
class ControlPlaneReplayEvaluationIssue:
    code: str
    severity: str
    detail: str


@dataclass(frozen=True)
class ControlPlaneReplayEvaluation:
    schema_version: str
    verdict: str
    trace_id: str
    replay_digest: str
    replay_status: str
    event_count: int
    event_types: tuple[str, ...]
    issues: tuple[ControlPlaneReplayEvaluationIssue, ...]
    required_human_decision: str
    state_change: str = "none"
    authority: str = _AUTHORITY
    evaluation_is_not_permission: bool = True
    replay_pass_is_not_truth: bool = True
    must_not_execute_automatically: bool = True


def _issue(code: str, severity: str, detail: str) -> ControlPlaneReplayEvaluationIssue:
    return ControlPlaneReplayEvaluationIssue(code=code, severity=severity, detail=detail)


def _evaluation(
    *,
    verdict: str,
    issues: tuple[ControlPlaneReplayEvaluationIssue, ...],
    trace_id: str = "unknown",
    replay_digest: str = "unknown",
    replay_status: str = "unknown",
    event_types: tuple[str, ...] = (),
) -> ControlPlaneReplayEvaluation:
    required = "none" if verdict == "replay_contract_passed" else "review_replay_contract"
    return ControlPlaneReplayEvaluation(
        schema_version=_SCHEMA_VERSION,
        verdict=verdict,
        trace_id=trace_id,
        replay_digest=replay_digest,
        replay_status=replay_status,
        event_count=len(event_types),
        event_types=event_types,
        issues=issues,
        required_human_decision=required,
    )


def _raw_rows(text: str) -> tuple[dict[str, Any], ...] | ControlPlaneReplayEvaluation:
    if not text.strip():
        return _evaluation(
            verdict="replay_incomplete",
            issues=(_issue("empty_jsonl", "high", "replay JSONL is empty"),),
        )
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(text.splitlines(), start=1):
        if not line.strip():
            continue
        try:
            raw = json.loads(line)
        except json.JSONDecodeError:
            return _evaluation(
                verdict="replay_contract_failed",
                issues=(_issue("invalid_jsonl", "high", f"line {line_no} is not valid JSON"),),
            )
        if not isinstance(raw, dict):
            return _evaluation(
                verdict="replay_contract_failed",
                issues=(_issue("non_object_row", "high", f"line {line_no} is not a JSON object"),),
            )
        rows.append(raw)
    if not rows:
        return _evaluation(
            verdict="replay_incomplete",
            issues=(_issue("empty_jsonl", "high", "replay JSONL has no object rows"),),
        )
    return tuple(rows)


def _row_event_types(rows: tuple[dict[str, Any], ...]) -> tuple[str, ...]:
    return tuple(str(row.get("event_type", "unknown")) for row in rows)


def _authority_drift_issues(rows: tuple[dict[str, Any], ...]) -> tuple[ControlPlaneReplayEvaluationIssue, ...]:
    issues: list[ControlPlaneReplayEvaluationIssue] = []
    for index, row in enumerate(rows):
        prefix = f"row {index}"
        if row.get("state_change") != "none":
            issues.append(_issue("state_change_drift", "critical", f"{prefix} changes state"))
        if "non-authoritative" not in str(row.get("authority", "")):
            issues.append(_issue("authority_drift", "critical", f"{prefix} does not declare non-authoritative authority"))
        if row.get("ledger_is_not_permission") is not True:
            issues.append(_issue("permission_guardrail_drift", "critical", f"{prefix} weakens ledger_is_not_permission"))
        if row.get("must_not_execute_automatically") is not True:
            issues.append(_issue("automatic_execution_guardrail_drift", "critical", f"{prefix} weakens automatic execution guardrail"))
        if row.get("replay_digest_is_not_truth") is not True:
            issues.append(_issue("truth_guardrail_drift", "critical", f"{prefix} weakens replay_digest_is_not_truth"))
    return tuple(issues)


def _boundary_issues(rows: tuple[dict[str, Any], ...]) -> tuple[ControlPlaneReplayEvaluationIssue, ...]:
    event_types = _row_event_types(rows)
    issues: list[ControlPlaneReplayEvaluationIssue] = []
    if event_types[0] != "decision_opened":
        issues.append(_issue("missing_decision_opened", "high", "replay must start with decision_opened"))
    if event_types[-1] != "decision_closed":
        issues.append(_issue("missing_decision_closed", "high", "replay must end with decision_closed"))
    return tuple(issues)


def _verdict_for_parse_error(message: str) -> str:
    incomplete_markers = (
        "contiguous",
        "one trace_id",
        "one replay_digest",
        "start with decision_opened",
        "end with decision_closed",
        "must contain",
    )
    if any(marker in message for marker in incomplete_markers):
        return "replay_incomplete"
    return "replay_contract_failed"


def evaluate_control_plane_replay_jsonl(text: str) -> ControlPlaneReplayEvaluation:
    """Evaluate replay JSONL without granting permission or mutating state."""

    rows_or_eval = _raw_rows(text)
    if isinstance(rows_or_eval, ControlPlaneReplayEvaluation):
        return rows_or_eval
    rows = rows_or_eval
    event_types = _row_event_types(rows)

    authority_issues = _authority_drift_issues(rows)
    if authority_issues:
        return _evaluation(
            verdict="replay_contains_authority_drift",
            issues=authority_issues,
            trace_id=str(rows[0].get("trace_id", "unknown")),
            replay_digest=str(rows[0].get("replay_digest", "unknown")),
            event_types=event_types,
        )

    boundary_issues = _boundary_issues(rows)
    if boundary_issues:
        return _evaluation(
            verdict="replay_incomplete",
            issues=boundary_issues,
            trace_id=str(rows[0].get("trace_id", "unknown")),
            replay_digest=str(rows[0].get("replay_digest", "unknown")),
            event_types=event_types,
        )

    try:
        ledger = parse_control_plane_event_ledger_jsonl(text)
    except ControlPlaneEventLedgerError as exc:
        message = str(exc)
        return _evaluation(
            verdict=_verdict_for_parse_error(message),
            issues=(_issue("ledger_parse_failed", "high", message),),
            trace_id=str(rows[0].get("trace_id", "unknown")),
            replay_digest=str(rows[0].get("replay_digest", "unknown")),
            event_types=event_types,
        )

    return _evaluation(
        verdict="replay_contract_passed",
        issues=(),
        trace_id=ledger.trace_id,
        replay_digest=ledger.replay_digest,
        replay_status=ledger.replay_status,
        event_types=tuple(record.event_type for record in ledger.records),
    )


def render_control_plane_replay_evaluation_json(evaluation: ControlPlaneReplayEvaluation) -> str:
    payload = asdict(evaluation)
    payload["state_change"] = "none"
    payload["authority"] = evaluation.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_control_plane_replay_evaluation_markdown(evaluation: ControlPlaneReplayEvaluation) -> str:
    lines = [
        "# Control Plane Replay Evaluation",
        "",
        "- state_change: none",
        f"- authority: {evaluation.authority}",
        "- evaluation_is_not_permission: true",
        "- replay_pass_is_not_truth: true",
        "- must_not_execute_automatically: true",
        "",
        "## Verdict",
        "",
        f"- verdict: {evaluation.verdict}",
        f"- required_human_decision: {evaluation.required_human_decision}",
        f"- trace_id: {evaluation.trace_id}",
        f"- replay_digest: {evaluation.replay_digest}",
        f"- replay_status: {evaluation.replay_status}",
        f"- event_count: {evaluation.event_count}",
        f"- event_types: {', '.join(evaluation.event_types) if evaluation.event_types else 'none'}",
        "",
        "## Issues",
        "",
    ]
    if evaluation.issues:
        lines.extend(f"- {issue.severity}:{issue.code}: {issue.detail}" for issue in evaluation.issues)
    else:
        lines.append("- none")
    return "\n".join(lines).rstrip() + "\n"
