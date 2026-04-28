from __future__ import annotations

from dataclasses import dataclass, field


GUARDRAILS: tuple[str, ...] = (
    "registered_is_not_true",
    "retrieved_is_not_relevant",
    "remembered_is_not_trusted",
    "silence_is_not_negative_evidence",
    "permission_is_not_sufficient_evidence",
    "advisory_is_not_authority",
    "approval_presence_is_not_permission",
    "state_change_none",
)


@dataclass(frozen=True)
class EvidenceSource:
    source_id: str
    path: str
    authority_state: str = "advisory"
    freshness: str = "current"
    role: str = "primary"


@dataclass(frozen=True)
class EvidenceClaim:
    claim_id: str
    subject: str
    predicate: str
    value: str
    source_id: str
    status: str = "current"
    confidence: str = "bounded"
    staleness: str = "not_detected"
    depends_on: tuple[str, ...] = ()


@dataclass(frozen=True)
class EvidenceRequirement:
    requirement_id: str
    subject: str
    predicate: str
    description: str
    required_for: str


@dataclass(frozen=True)
class PathDigest:
    path: str
    digest: str


@dataclass(frozen=True)
class PrewriteGuard:
    read_digests: tuple[PathDigest, ...] = ()
    current_digests: tuple[PathDigest, ...] = ()


@dataclass(frozen=True)
class ApprovalContext:
    status: str = "not_required"
    approval_id: str = ""
    approved_reads: tuple[str, ...] = ()
    approved_writes: tuple[str, ...] = ()


@dataclass(frozen=True)
class ActionProfile:
    zone: str
    reads: tuple[str, ...] = ()
    writes: tuple[str, ...] = ()
    authority_impact: str = "none"
    runtime_impact: str = "none"
    reversibility: str = "high"
    active_trigger: bool = False
    existing_state_policy: str = "not_applicable"


@dataclass(frozen=True)
class DecisionScenario:
    scenario_id: str
    intent: str
    action_profile: ActionProfile
    sources: tuple[EvidenceSource, ...]
    claims: tuple[EvidenceClaim, ...]
    requirements: tuple[EvidenceRequirement, ...] = ()
    approval: ApprovalContext = field(default_factory=ApprovalContext)
    prewrite_guard: PrewriteGuard = field(default_factory=PrewriteGuard)
    protocol_notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class DecisionEnvelope:
    scenario_id: str
    intent: str
    action_profile: ActionProfile
    read_set: tuple[str, ...]
    claim_summary: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    stale_claims: tuple[str, ...]
    conflicts: tuple[str, ...]
    approval_status: str
    prewrite_guard_status: str
    sufficiency: str
    action_readiness: str
    recommended_human_decision: str
    blockers: tuple[str, ...]
    warnings: tuple[str, ...]
    guardrails: tuple[str, ...] = GUARDRAILS
    state_change: str = "none"
    authority: str = "non-authoritative; advisory decision envelope only"

    @property
    def blocked(self) -> bool:
        return self.action_readiness in {
            "blocked",
            "canonical_change_requires_trigger",
            "human_approval_required",
        }
