"""Deterministic replay result invariants evaluator.

Evaluates a caller-supplied replay result dict for structural invariants.

Guardrails:
  eval_is_not_permission = True
  replay_pass_is_not_truth = True
  replay_pass_is_not_execution_approval = True
  must_not_execute_automatically = True
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class ReplayInvariantFinding:
    code: str
    detail: str


@dataclass(frozen=True)
class ReplayInvariantEvalResult:
    eval_is_not_permission: bool = True
    replay_pass_is_not_truth: bool = True
    replay_pass_is_not_execution_approval: bool = True
    must_not_execute_automatically: bool = True
    passed: bool = False
    findings: tuple[ReplayInvariantFinding, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "findings", tuple(self.findings))


def eval_replay_invariants(replay: dict) -> ReplayInvariantEvalResult:
    """Evaluate structural invariants on a caller-supplied replay result dict.

    Does not read files, run subprocesses, or mutate state.
    Returns an advisory-only result.
    """
    findings: list[ReplayInvariantFinding] = []

    required = ("scenario_id", "passed", "replay_digest", "checks", "authority")
    for field_name in required:
        if field_name not in replay:
            findings.append(ReplayInvariantFinding(
                code="missing_required_field",
                detail=f"field '{field_name}' missing from replay result",
            ))

    authority = replay.get("authority", "")
    if "permission" not in authority.lower() and authority:
        findings.append(ReplayInvariantFinding(
            code="authority_missing_non_permission_marker",
            detail=f"authority field must reference non-permission semantics; got {authority!r}",
        ))

    digest = replay.get("replay_digest", "")
    if digest and not digest.startswith("sha256:"):
        findings.append(ReplayInvariantFinding(
            code="invalid_digest_format",
            detail=f"replay_digest must start with 'sha256:'; got {digest!r}",
        ))

    checks = replay.get("checks", [])
    check_ids = [c.get("check_id", "") for c in checks if isinstance(c, dict)]
    if len(check_ids) != len(set(check_ids)):
        findings.append(ReplayInvariantFinding(
            code="duplicate_check_id",
            detail="replay checks contain duplicate check_id values",
        ))

    for check in checks:
        if not isinstance(check, dict):
            continue
        if "passed" not in check:
            findings.append(ReplayInvariantFinding(
                code="check_missing_passed",
                detail=f"check {check.get('check_id', '?')} missing 'passed' field",
            ))

    return ReplayInvariantEvalResult(
        passed=len(findings) == 0,
        findings=tuple(findings),
    )
