"""Pure policy helpers for the Runtime Manager.

This module must stay free of filesystem, SQLite, subprocess, and clock I/O.
The store owns persistence; policy helpers own deterministic decisions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Tuple


# ---------------------------------------------------------------------------
# State decision (pre-Phase 8, kept for backward compat)
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class RuntimeStateDecision:
    """Pure state decision derived from an already-built scheduler snapshot."""

    state: str


def decide_runtime_state(*, stale_source: bool, selected_id: str, has_observations: bool) -> RuntimeStateDecision:
    """Return the public runtime state without reading or mutating external state."""
    if stale_source:
        return RuntimeStateDecision(state="blocked")
    if selected_id:
        return RuntimeStateDecision(state="ready")
    if has_observations:
        return RuntimeStateDecision(state="idle")
    return RuntimeStateDecision(state="idle")


# ---------------------------------------------------------------------------
# Autonomy levels (Phase 8)
# ---------------------------------------------------------------------------

LEVEL_ORDER: Tuple[str, ...] = (
    "L0_observe",
    "L1_derived",
    "L2_local_code",
    "L3_runtime_mutation",
    "L4_external_high_risk",
)

# side_effect_class → base autonomy level
_SIDE_EFFECT_BASE: dict[str, str] = {
    "read-only":         "L0_observe",
    "derived-write":     "L1_derived",
    "docs-write":        "L1_derived",
    "local-mutation":    "L2_local_code",
    "test-run":          "L2_local_code",
    "runtime-mutation":  "L3_runtime_mutation",
    "system-mutation":   "L3_runtime_mutation",
    "destructive":       "L3_runtime_mutation",
    "external":          "L4_external_high_risk",
}

# Required controls and friction budget per level
_LEVEL_FRICTION: dict[str, int] = {
    "L0_observe":              0,
    "L1_derived":              1,
    "L2_local_code":           2,
    "L3_runtime_mutation":     4,
    "L4_external_high_risk":   9,
}

_L4_BLOCKED_REASON = (
    "L4_external_high_risk requires explicit human decision per action; "
    "not executable via MCP in this phase"
)


def _level_rank(level: str) -> int:
    """Return the ordinal rank of a level (higher = more restrictive)."""
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return len(LEVEL_ORDER)  # unknown levels treated as maximally restrictive


# ---------------------------------------------------------------------------
# ActionInput — all policy inputs needed for classification
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionInput:
    """Inputs to classify_action().  All fields correspond to command_registry columns
    or token/context fields.  Caller supplies defaults for absent columns."""

    side_effect_class: str = "runtime-mutation"
    network_allowed: bool = False
    approval_requirement: str = "required"
    path_scope: str = "."
    sensitive_output_policy: str = "none"
    rollback_class: str = "irreversible"
    target_scope: str = "local"
    data_sensitivity: str = "none"
    risk_level_override: str = ""
    requires_human_decision: bool = False


# ---------------------------------------------------------------------------
# ActionClassification — classification result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class ActionClassification:
    """Result of classify_action().

    classification_is_not_permission = True always: this result does not grant
    approval, does not authorize execution, and is not a runtime gate.
    """

    autonomy_level: str
    required_controls: tuple[str, ...]
    blocked_reason: str   # non-empty only for unconditionally blocked actions
    friction_budget: int
    rationale: str
    classification_is_not_permission: bool = True


# ---------------------------------------------------------------------------
# Core classifier
# ---------------------------------------------------------------------------

def classify_action(inp: ActionInput) -> ActionClassification:
    """Classify an action and return its autonomy level, controls, and rationale.

    Rules (applied in order; each can only raise the level):
      1. Base level from side_effect_class (unknown → L3).
      2. network_allowed=True → L4.
      3. data_sensitivity in ("high","critical") → L4.
      4. data_sensitivity == "sensitive" → min L3.
      5. requires_human_decision=True → L4.
      6. target_scope in external set → L4.
      7. risk_level_override accepted only if it raises the level.
    """
    rationale_parts: list[str] = []

    # Step 1: base
    base = _SIDE_EFFECT_BASE.get(inp.side_effect_class, "L3_runtime_mutation")
    effective = base
    rationale_parts.append(f"side_effect_class={inp.side_effect_class!r} → {base}")

    # Step 2: network
    if inp.network_allowed:
        if _level_rank("L4_external_high_risk") > _level_rank(effective):
            effective = "L4_external_high_risk"
        rationale_parts.append("network_allowed=True → L4")

    # Step 3: data_sensitivity high/critical
    if inp.data_sensitivity in ("high", "critical"):
        if _level_rank("L4_external_high_risk") > _level_rank(effective):
            effective = "L4_external_high_risk"
        rationale_parts.append(f"data_sensitivity={inp.data_sensitivity!r} → L4")
    elif inp.data_sensitivity == "sensitive":
        if _level_rank("L3_runtime_mutation") > _level_rank(effective):
            effective = "L3_runtime_mutation"
        rationale_parts.append("data_sensitivity=sensitive → min L3")

    # Step 4: requires_human_decision
    if inp.requires_human_decision:
        if _level_rank("L4_external_high_risk") > _level_rank(effective):
            effective = "L4_external_high_risk"
        rationale_parts.append("requires_human_decision=True → L4")

    # Step 5: target_scope external
    _EXTERNAL_SCOPES = frozenset({"external", "cloud", "release", "production", "remote"})
    if inp.target_scope in _EXTERNAL_SCOPES:
        if _level_rank("L4_external_high_risk") > _level_rank(effective):
            effective = "L4_external_high_risk"
        rationale_parts.append(f"target_scope={inp.target_scope!r} → L4")

    # Step 6: risk_level_override (only raises)
    if inp.risk_level_override and inp.risk_level_override in LEVEL_ORDER:
        if _level_rank(inp.risk_level_override) > _level_rank(effective):
            effective = inp.risk_level_override
            rationale_parts.append(
                f"risk_level_override={inp.risk_level_override!r} → {effective}"
            )
        else:
            rationale_parts.append(
                f"risk_level_override={inp.risk_level_override!r} ignored (would lower level)"
            )

    # Derive controls
    controls = _required_controls(effective, inp)
    friction = _LEVEL_FRICTION.get(effective, 9)
    blocked_reason = _L4_BLOCKED_REASON if effective == "L4_external_high_risk" else ""

    return ActionClassification(
        autonomy_level=effective,
        required_controls=controls,
        blocked_reason=blocked_reason,
        friction_budget=friction,
        rationale="; ".join(rationale_parts),
    )


def _required_controls(level: str, inp: ActionInput) -> tuple[str, ...]:
    """Return the set of controls required for the given level."""
    if level == "L0_observe":
        return ()

    if level == "L1_derived":
        ops_path = "docs/operations"
        if inp.path_scope.startswith(ops_path) or ops_path in inp.path_scope:
            return ("diff_check",)
        return ()

    if level == "L2_local_code":
        base: list[str] = ["lease_required", "command_registry"]
        if inp.approval_requirement != "none":
            base.append("approval_required")
        return tuple(base)

    if level == "L3_runtime_mutation":
        base = ["lease_required", "command_registry", "evidence_required", "trace_required"]
        if inp.approval_requirement != "none":
            base.insert(2, "approval_required")
        return tuple(base)

    # L4
    return (
        "human_decision_required",
        "lease_required",
        "approval_required",
        "evidence_required",
        "trace_required",
        "ttl_check",
        "full_gate",
    )


# ---------------------------------------------------------------------------
# Level explanation helper (used by CLI explain-levels)
# ---------------------------------------------------------------------------

def explain_levels() -> list[dict]:
    """Return a structured description of all autonomy levels."""
    return [
        {
            "level": "L0_observe",
            "friction_budget": 0,
            "required_controls": [],
            "mcp_executable": True,
            "description": "Read-only observe: status, traces, metrics, replay. No lease, no approval.",
        },
        {
            "level": "L1_derived",
            "friction_budget": 1,
            "required_controls": ["diff_check (when touching docs/operations)"],
            "mcp_executable": True,
            "description": "Derived writes: docs, projections, evals. No runtime authority touched.",
        },
        {
            "level": "L2_local_code",
            "friction_budget": 2,
            "required_controls": ["lease_required", "command_registry", "approval_required (conditional)"],
            "mcp_executable": True,
            "description": "Local code and tests: no network, no secrets, no external adapter.",
        },
        {
            "level": "L3_runtime_mutation",
            "friction_budget": 4,
            "required_controls": [
                "lease_required",
                "command_registry",
                "approval_required (when policy demands)",
                "evidence_required",
                "trace_required",
            ],
            "mcp_executable": True,
            "description": "Runtime mutations: run_command, approvals, rollback, tokens, MCP writes.",
        },
        {
            "level": "L4_external_high_risk",
            "friction_budget": 9,
            "required_controls": [
                "human_decision_required",
                "lease_required",
                "approval_required",
                "evidence_required",
                "trace_required",
                "ttl_check",
                "full_gate",
            ],
            "mcp_executable": False,
            "description": (
                "External / high-risk: network, cloud, OAuth, sensitive data, "
                "release, production target, destructive-wide. "
                "NOT executable via MCP in this phase."
            ),
        },
    ]
