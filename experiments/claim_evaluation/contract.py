from __future__ import annotations

from dataclasses import dataclass

from experiments.claim_extraction import ClaimCandidate


@dataclass(frozen=True)
class EvaluationFinding:
    claim: ClaimCandidate
    authority: str
    confidence: str
    sufficiency: str
    conflict: str
    supersession: str
    staleness: str
    operational_readiness: str
    reasons: tuple[str, ...]


@dataclass(frozen=True)
class EvaluationReport:
    findings: tuple[EvaluationFinding, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory evidence only"

    @property
    def ready_count(self) -> int:
        return sum(1 for finding in self.findings if finding.operational_readiness == "ready")

    @property
    def blocked_count(self) -> int:
        return sum(1 for finding in self.findings if finding.operational_readiness == "blocked")

    @property
    def insufficient_count(self) -> int:
        return sum(1 for finding in self.findings if finding.sufficiency != "sufficient")
