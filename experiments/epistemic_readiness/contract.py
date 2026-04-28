from __future__ import annotations

from dataclasses import dataclass

from experiments.claim_evaluation import EvaluationReport
from experiments.claim_extraction import ClaimCandidate

from .risk import RiskAssessment


VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "propose_only",
    "advisory_report_allowed",
    "derived_experiment_allowed",
    "canonical_change_requires_trigger",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class SourceManifestEntry:
    relative_path: str
    max_lines: int = 80
    source_role: str = "primary"

    def __post_init__(self) -> None:
        if not self.relative_path:
            raise ValueError("relative_path is required")
        if self.max_lines < 1:
            raise ValueError("max_lines must be positive")
        if self.max_lines > 200:
            raise ValueError("max_lines must be <= 200")


@dataclass(frozen=True)
class BoundedSourceRead:
    relative_path: str
    source_role: str
    requested_max_lines: int
    lines_read: int
    bytes_read: int
    truncated: bool


@dataclass(frozen=True)
class BaselineMetrics:
    candidates_extracted: int
    findings_evaluated: int
    ready_count: int
    blocked_count: int
    insufficient_count: int
    label: str = "baseline"


@dataclass(frozen=True)
class ReadinessReport:
    source_reads: tuple[BoundedSourceRead, ...]
    candidates: tuple[ClaimCandidate, ...]
    evaluation: EvaluationReport
    action_readiness: str
    risk_assessment: RiskAssessment | None = None
    baseline: BaselineMetrics | None = None
    state_change: str = "none"
    authority: str = "non-authoritative; advisory evidence only"

    def __post_init__(self) -> None:
        if self.action_readiness not in VALID_ACTION_READINESS:
            raise ValueError(f"invalid action_readiness: {self.action_readiness}")
        if self.state_change != "none":
            raise ValueError("epistemic readiness reports must not change state")
        if self.risk_assessment is not None and self.risk_assessment.state_change != "none":
            raise ValueError("risk assessments must not change state")

    @property
    def candidate_count(self) -> int:
        return len(self.candidates)

    @property
    def finding_count(self) -> int:
        return len(self.evaluation.findings)

    @property
    def ready_count(self) -> int:
        return self.evaluation.ready_count

    @property
    def blocked_count(self) -> int:
        return self.evaluation.blocked_count

    @property
    def insufficient_count(self) -> int:
        return self.evaluation.insufficient_count
