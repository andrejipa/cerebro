from __future__ import annotations

from dataclasses import dataclass
from typing import Literal


FindingSeverity = Literal["blocker", "warning"]
Readiness = Literal[
    "ready_for_human_review",
    "needs_missing_fields",
    "blocked_role_drift",
    "blocked_target_cerebro_ambiguity",
    "blocked_runtime_boundary",
    "consolidation_required",
]


@dataclass(frozen=True)
class ThirdPartyTriggerReviewInput:
    trigger_id: str
    trigger_text: str
    consecutive_target_mutating_slices: int = 0
    target_has_cerebro: bool = False


@dataclass(frozen=True)
class ThirdPartyTriggerReviewFinding:
    code: str
    severity: FindingSeverity
    message: str


@dataclass(frozen=True)
class ThirdPartyTriggerReview:
    trigger_id: str
    target_path: str | None
    slice_kind: str | None
    dogfood_value_present: bool
    proof_cost_declared: bool
    source_roles_declared: bool
    target_cerebro_handling_declared: bool
    rollback_declared: bool
    cleanup_declared: bool
    stop_lines_declared: bool
    forbidden_paths_declared: bool
    consecutive_target_slice_risk: str
    readiness: Readiness
    findings: tuple[ThirdPartyTriggerReviewFinding, ...]
    state_change: str = "none"

    @property
    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    @property
    def warning_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "warning")
