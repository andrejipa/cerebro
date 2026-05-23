"""Deterministic metrics invariants evaluator.

Evaluates a caller-supplied metrics dict for sanity invariants.

Guardrails:
  eval_is_not_permission = True
  eval_pass_is_not_execution_approval = True
  must_not_execute_automatically = True
"""
from __future__ import annotations

from dataclasses import dataclass, field


REQUIRED_METRIC_FIELDS = frozenset({
    "runs_total",
    "runs_passed",
    "runs_failed",
    "execution_evidence_total",
    "traces_total",
    "leases_active",
    "stop_conditions_active",
    "validations_green",
})


@dataclass(frozen=True)
class MetricsInvariantFinding:
    code: str
    detail: str


@dataclass(frozen=True)
class MetricsInvariantEvalResult:
    eval_is_not_permission: bool = True
    eval_pass_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True
    passed: bool = False
    findings: tuple[MetricsInvariantFinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))


def eval_metrics_invariants(metrics: dict) -> MetricsInvariantEvalResult:
    """Evaluate sanity invariants on caller-supplied metrics dict.

    Does not read files, run subprocesses, or mutate state.
    Returns an advisory-only result.
    """
    findings: list[MetricsInvariantFinding] = []

    for field_name in REQUIRED_METRIC_FIELDS:
        if field_name not in metrics:
            findings.append(MetricsInvariantFinding(
                code="missing_required_metric",
                detail=f"metric '{field_name}' not found in payload",
            ))

    runs_total = metrics.get("runs_total", 0)
    runs_passed = metrics.get("runs_passed", 0)
    runs_failed = metrics.get("runs_failed", 0)

    if isinstance(runs_total, int) and isinstance(runs_passed, int) and isinstance(runs_failed, int):
        if runs_passed + runs_failed > runs_total:
            findings.append(MetricsInvariantFinding(
                code="runs_sum_exceeds_total",
                detail=f"runs_passed ({runs_passed}) + runs_failed ({runs_failed}) > runs_total ({runs_total})",
            ))

    for key, val in metrics.items():
        if isinstance(val, int) and val < 0:
            findings.append(MetricsInvariantFinding(
                code="negative_metric",
                detail=f"metric '{key}' has negative value {val}",
            ))

    return MetricsInvariantEvalResult(
        passed=len(findings) == 0,
        findings=tuple(findings),
    )
