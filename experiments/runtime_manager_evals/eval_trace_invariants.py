"""Deterministic trace structure invariants evaluator.

Evaluates a caller-supplied list of runtime trace dicts for structural
invariants WITHOUT reading any runtime state or granting any permission.

Guardrails:
  eval_is_not_permission = True
  eval_pass_is_not_execution_approval = True
  finding_is_not_truth = True
  must_not_execute_automatically = True
"""
from __future__ import annotations

from dataclasses import dataclass, field


REQUIRED_TRACE_FIELDS = frozenset({
    "trace_id",
    "operation",
    "started_at",
    "duration_ms",
    "outcome",
    "trace_is_not_permission",
})

REQUIRED_PERMISSION_MARKERS = frozenset({
    "trace_is_not_permission",
})


@dataclass(frozen=True)
class TraceInvariantFinding:
    trace_id: str
    code: str
    detail: str


@dataclass(frozen=True)
class TraceInvariantEvalResult:
    eval_is_not_permission: bool = True
    eval_pass_is_not_execution_approval: bool = True
    finding_is_not_truth: bool = True
    must_not_execute_automatically: bool = True
    passed: bool = False
    findings: tuple[TraceInvariantFinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))


def eval_trace_invariants(traces: list[dict]) -> TraceInvariantEvalResult:
    """Evaluate structural invariants on caller-supplied trace dicts.

    Does not read files, run subprocesses, or mutate state.
    Returns an advisory-only result.
    """
    findings: list[TraceInvariantFinding] = []

    seen_ids: set[str] = set()
    for trace in traces:
        trace_id = trace.get("trace_id", "<missing>")

        if trace_id in seen_ids:
            findings.append(TraceInvariantFinding(
                trace_id=trace_id,
                code="duplicate_trace_id",
                detail=f"trace_id appears more than once: {trace_id}",
            ))
        seen_ids.add(trace_id)

        for field_name in REQUIRED_TRACE_FIELDS:
            if field_name not in trace:
                findings.append(TraceInvariantFinding(
                    trace_id=trace_id,
                    code="missing_required_field",
                    detail=f"field '{field_name}' missing from trace",
                ))

        for marker in REQUIRED_PERMISSION_MARKERS:
            if trace.get(marker) is not True:
                findings.append(TraceInvariantFinding(
                    trace_id=trace_id,
                    code="missing_non_permission_marker",
                    detail=f"marker '{marker}' must be True; got {trace.get(marker)!r}",
                ))

        outcome = trace.get("outcome", "")
        if outcome not in ("ok", "ineligible", "error", "blocked"):
            findings.append(TraceInvariantFinding(
                trace_id=trace_id,
                code="invalid_outcome",
                detail=f"outcome must be ok|ineligible|error|blocked; got {outcome!r}",
            ))

    return TraceInvariantEvalResult(
        passed=len(findings) == 0,
        findings=tuple(findings),
    )
