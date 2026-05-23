from __future__ import annotations

from dataclasses import dataclass


VALID_ZONES = {"zone_0", "zone_1", "zone_2", "zone_3"}
VALID_GATE_LEVELS = {"G0", "G1", "G2", "G3", "G4"}
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
VALID_AUTHORITY_IMPACTS = {"none", "advisory", "provisional", "canonical"}
VALID_RUNTIME_IMPACTS = {"none", "indirect", "direct"}
VALID_STATE_IMPACTS = {"none", "read-only", "derived-output", "canonical-mutation"}
VALID_THIRD_PARTY_IMPACTS = {"none", "read-only", "derived-output", "mutation"}
VALID_REVERSIBILITY = {"high", "medium", "low", "none"}
VALID_ROLLBACK = {"delete-folder", "git-revert", "manual-reconstruction", "not-reversible"}
VALID_PROMOTION_PATHS = {"none", "requires-trigger", "requires-human-approval"}
VALID_SCOPE = {"local", "project", "multi_project", "external"}
VALID_UNCERTAINTY = {"low", "medium", "high", "unknown"}
VALID_ROLLBACK_EVIDENCE = {"none", "delete-folder", "git-revert", "manual-proof", "test-proof"}

_GATE_RANK = {"G0": 0, "G1": 1, "G2": 2, "G3": 3, "G4": 4}
_GATE_BY_RANK = {rank: gate for gate, rank in _GATE_RANK.items()}
_ZONE_FLOOR = {"zone_0": "G0", "zone_1": "G2", "zone_2": "G3", "zone_3": "G4"}
_AUTHORITY_RISK = {"none": 0, "advisory": 1, "provisional": 2, "canonical": 4}
_SCOPE_RISK = {"local": 1, "project": 2, "multi_project": 3, "external": 4}
_REVERSIBILITY_RISK = {"high": 1, "medium": 2, "low": 3, "none": 4}
_UNCERTAINTY_RISK = {"low": 1, "medium": 2, "high": 3, "unknown": 4}
_RUNTIME_RANK = {"none": 0, "indirect": 1, "direct": 2}
_AUTHORITY_RANK = {"none": 0, "advisory": 1, "provisional": 2, "canonical": 3}
_ACTUAL_IRREVERSIBILITY = {"high": "low", "medium": "medium", "low": "high", "none": "none"}
_IRREVERSIBILITY_LIMIT_RANK = {"low": 1, "medium": 2, "high": 3, "none": 4}


def _require(value: str, allowed: set[str], field_name: str) -> None:
    if value not in allowed:
        raise ValueError(f"invalid {field_name}: {value}")


def _as_tuple(values: tuple[str, ...] | list[str]) -> tuple[str, ...]:
    return tuple(str(value).replace("\\", "/") for value in values)


@dataclass(frozen=True)
class BlastRadiusDeclaration:
    writes: tuple[str, ...] = ()
    reads: tuple[str, ...] = ()
    authority_impact: str = "none"
    runtime_impact: str = "none"
    state_impact: str = "none"
    third_party_impact: str = "none"
    scope: str = "local"
    reversibility: str = "high"
    rollback: str = "git-revert"
    gate_level: str = "G0"
    promotion_path: str = "none"
    stop_conditions: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "writes", _as_tuple(self.writes))
        object.__setattr__(self, "reads", _as_tuple(self.reads))
        object.__setattr__(self, "stop_conditions", _as_tuple(self.stop_conditions))
        _require(self.authority_impact, VALID_AUTHORITY_IMPACTS, "authority_impact")
        _require(self.runtime_impact, VALID_RUNTIME_IMPACTS, "runtime_impact")
        _require(self.state_impact, VALID_STATE_IMPACTS, "state_impact")
        _require(self.third_party_impact, VALID_THIRD_PARTY_IMPACTS, "third_party_impact")
        _require(self.scope, VALID_SCOPE, "scope")
        _require(self.reversibility, VALID_REVERSIBILITY, "reversibility")
        _require(self.rollback, VALID_ROLLBACK, "rollback")
        _require(self.gate_level, VALID_GATE_LEVELS, "gate_level")
        _require(self.promotion_path, VALID_PROMOTION_PATHS, "promotion_path")


@dataclass(frozen=True)
class RiskBudget:
    max_writes: int = 0
    allowed_paths: tuple[str, ...] = ()
    allowed_authority_impact: str = "none"
    allowed_runtime_impact: str = "none"
    max_irreversibility: str = "low"
    required_rollback_evidence: str = "none"
    human_approval_required: bool = False

    def __post_init__(self) -> None:
        if self.max_writes < 0:
            raise ValueError("max_writes must be >= 0")
        object.__setattr__(self, "allowed_paths", _as_tuple(self.allowed_paths))
        _require(self.allowed_authority_impact, VALID_AUTHORITY_IMPACTS, "allowed_authority_impact")
        _require(self.allowed_runtime_impact, VALID_RUNTIME_IMPACTS, "allowed_runtime_impact")
        _require(self.max_irreversibility, VALID_REVERSIBILITY, "max_irreversibility")
        _require(self.required_rollback_evidence, VALID_ROLLBACK_EVIDENCE, "required_rollback_evidence")


@dataclass(frozen=True)
class ActionProposal:
    action_id: str
    purpose: str
    zone: str
    blast_radius: BlastRadiusDeclaration
    risk_budget: RiskBudget
    uncertainty: str = "medium"

    def __post_init__(self) -> None:
        if not self.action_id:
            raise ValueError("action_id is required")
        if not self.purpose:
            raise ValueError("purpose is required")
        _require(self.zone, VALID_ZONES, "zone")
        _require(self.uncertainty, VALID_UNCERTAINTY, "uncertainty")


@dataclass(frozen=True)
class RiskAssessment:
    action_id: str
    purpose: str
    zone: str
    risk_score: int
    declared_gate_level: str
    required_gate_level: str
    budget_status: str
    budget_violations: tuple[str, ...]
    human_approval_required: bool
    action_readiness: str
    stop_conditions: tuple[str, ...]
    state_change: str = "none"
    authority: str = "non-authoritative; advisory risk evidence only"

    def __post_init__(self) -> None:
        _require(self.required_gate_level, VALID_GATE_LEVELS, "required_gate_level")
        _require(self.declared_gate_level, VALID_GATE_LEVELS, "declared_gate_level")
        _require(self.action_readiness, VALID_ACTION_READINESS, "action_readiness")
        if self.budget_status not in {"within_budget", "exceeded"}:
            raise ValueError(f"invalid budget_status: {self.budget_status}")
        if self.state_change != "none":
            raise ValueError("risk assessments must not change state")


def _risk_gate(score: int) -> str:
    if score <= 0:
        return "G0"
    if score <= 3:
        return "G1"
    if score <= 8:
        return "G2"
    if score <= 18:
        return "G3"
    return "G4"


def _max_gate(*gates: str) -> str:
    return _GATE_BY_RANK[max(_GATE_RANK[gate] for gate in gates)]


def _path_allowed(path: str, allowed_paths: tuple[str, ...]) -> bool:
    if not allowed_paths:
        return True
    normalized = path.strip("/").replace("\\", "/")
    for allowed in allowed_paths:
        prefix = allowed.strip("/").replace("\\", "/")
        if normalized == prefix or normalized.startswith(prefix.rstrip("/") + "/"):
            return True
    return False


def _rollback_satisfies(required: str, declared: str) -> bool:
    if required == "none":
        return True
    if required == "manual-proof":
        return declared in {"delete-folder", "git-revert", "manual-reconstruction"}
    if required == "test-proof":
        return declared in {"delete-folder", "git-revert"}
    return declared == required


def _budget_violations(proposal: ActionProposal) -> tuple[str, ...]:
    blast = proposal.blast_radius
    budget = proposal.risk_budget
    violations: list[str] = []

    if len(blast.writes) > budget.max_writes:
        violations.append(f"writes exceed budget: {len(blast.writes)} > {budget.max_writes}")
    for path in blast.writes:
        if not _path_allowed(path, budget.allowed_paths):
            violations.append(f"write outside allowed paths: {path}")
    if _AUTHORITY_RANK[blast.authority_impact] > _AUTHORITY_RANK[budget.allowed_authority_impact]:
        violations.append(
            "authority impact exceeds budget: "
            f"{blast.authority_impact} > {budget.allowed_authority_impact}"
        )
    if _RUNTIME_RANK[blast.runtime_impact] > _RUNTIME_RANK[budget.allowed_runtime_impact]:
        violations.append(
            "runtime impact exceeds budget: "
            f"{blast.runtime_impact} > {budget.allowed_runtime_impact}"
        )
    actual_irreversibility = _ACTUAL_IRREVERSIBILITY[blast.reversibility]
    if (
        _IRREVERSIBILITY_LIMIT_RANK[actual_irreversibility]
        > _IRREVERSIBILITY_LIMIT_RANK[budget.max_irreversibility]
    ):
        violations.append(
            "irreversibility exceeds budget: "
            f"{actual_irreversibility} > {budget.max_irreversibility}"
        )
    if not _rollback_satisfies(budget.required_rollback_evidence, blast.rollback):
        violations.append(
            "rollback evidence missing: "
            f"required {budget.required_rollback_evidence}, declared {blast.rollback}"
        )
    return tuple(violations)


def evaluate_risk_budget(proposal: ActionProposal) -> RiskAssessment:
    blast = proposal.blast_radius
    risk_score = (
        _AUTHORITY_RISK[blast.authority_impact]
        * _SCOPE_RISK[blast.scope]
        * _REVERSIBILITY_RISK[blast.reversibility]
        * _UNCERTAINTY_RISK[proposal.uncertainty]
    )
    floor_gate = _ZONE_FLOOR[proposal.zone]
    required_gate = _max_gate(floor_gate, blast.gate_level, _risk_gate(risk_score))
    violations = _budget_violations(proposal)
    stop_conditions = list(blast.stop_conditions)

    if violations:
        readiness = "blocked"
        budget_status = "exceeded"
        human_approval = True
        stop_conditions.extend(violations)
    elif (
        risk_score > 36
        and proposal.uncertainty in {"high", "unknown"}
        and blast.authority_impact != "canonical"
    ):
        readiness = "blocked"
        budget_status = "within_budget"
        human_approval = True
        stop_conditions.append("uncertainty too high for declared blast radius")
    elif required_gate == "G4":
        readiness = "canonical_change_requires_trigger"
        budget_status = "within_budget"
        human_approval = True
        stop_conditions.append("canonical change requires separate formal trigger")
    elif proposal.risk_budget.human_approval_required:
        readiness = "human_approval_required"
        budget_status = "within_budget"
        human_approval = True
    elif required_gate == "G3":
        readiness = "human_approval_required"
        budget_status = "within_budget"
        human_approval = True
    elif required_gate == "G2":
        readiness = "derived_experiment_allowed"
        budget_status = "within_budget"
        human_approval = False
    elif required_gate == "G1":
        readiness = "advisory_report_allowed"
        budget_status = "within_budget"
        human_approval = False
    else:
        readiness = "observe_only"
        budget_status = "within_budget"
        human_approval = False

    return RiskAssessment(
        action_id=proposal.action_id,
        purpose=proposal.purpose,
        zone=proposal.zone,
        risk_score=risk_score,
        declared_gate_level=blast.gate_level,
        required_gate_level=required_gate,
        budget_status=budget_status,
        budget_violations=violations,
        human_approval_required=human_approval,
        action_readiness=readiness,
        stop_conditions=tuple(stop_conditions),
    )
