"""eval_autonomy_levels -- advisory-only invariant checks for Phase 8 autonomy calibration.

Evaluators verify:
  - L0/L1/L2/L3/L4 classification correctness from known inputs
  - risk_level_override only raises the effective level
  - MCP never executes L4 (server source check)
  - token max_autonomy_level ceiling enforced in server source
  - classification_is_not_permission invariant present on all results
  - L4 always blocked in check_command_eligibility source

NOT a runtime gate, NOT permission, NOT execution approval.
All evaluator functions return a list of finding dicts.

eval_autonomy_levels_is_not_permission = True (always)
"""
from __future__ import annotations

import inspect
from typing import Any

from core.runtime_manager_policy import (
    ActionInput,
    ActionClassification,
    classify_action,
    LEVEL_ORDER,
    explain_levels,
)

EVAL_AUTHORITY = "autonomy levels eval only; not permission, not a runtime gate"
eval_autonomy_levels_is_not_permission = True


def _finding(check: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "check": check,
        "passed": passed,
        "detail": detail,
        "eval_is_not_permission": True,
    }


# ---------------------------------------------------------------------------
# L0 classification
# ---------------------------------------------------------------------------

def eval_l0_read_only() -> list[dict]:
    findings = []
    inp = ActionInput(side_effect_class="read-only")
    result = classify_action(inp)
    findings.append(_finding(
        "l0_read_only_classification",
        result.autonomy_level == "L0_observe",
        f"expected L0_observe, got {result.autonomy_level!r}",
    ))
    findings.append(_finding(
        "l0_friction_budget_zero",
        result.friction_budget == 0,
        f"expected 0, got {result.friction_budget}",
    ))
    findings.append(_finding(
        "l0_not_blocked",
        result.blocked_reason == "",
        f"unexpected blocked_reason: {result.blocked_reason!r}",
    ))
    return findings


# ---------------------------------------------------------------------------
# L1 classification
# ---------------------------------------------------------------------------

def eval_l1_derived_write() -> list[dict]:
    findings = []
    for sec in ("derived-write", "docs-write"):
        inp = ActionInput(side_effect_class=sec)
        result = classify_action(inp)
        findings.append(_finding(
            f"l1_{sec.replace('-', '_')}_classification",
            result.autonomy_level == "L1_derived",
            f"expected L1_derived, got {result.autonomy_level!r}",
        ))
    return findings


# ---------------------------------------------------------------------------
# L2 classification
# ---------------------------------------------------------------------------

def eval_l2_local_code() -> list[dict]:
    findings = []
    for sec in ("local-mutation", "test-run"):
        inp = ActionInput(side_effect_class=sec)
        result = classify_action(inp)
        findings.append(_finding(
            f"l2_{sec.replace('-', '_')}_classification",
            result.autonomy_level == "L2_local_code",
            f"expected L2_local_code, got {result.autonomy_level!r}",
        ))
    return findings


# ---------------------------------------------------------------------------
# L3 classification
# ---------------------------------------------------------------------------

def eval_l3_runtime_mutation() -> list[dict]:
    findings = []
    for sec in ("runtime-mutation", "system-mutation", "destructive"):
        inp = ActionInput(side_effect_class=sec)
        result = classify_action(inp)
        findings.append(_finding(
            f"l3_{sec.replace('-', '_')}_classification",
            result.autonomy_level == "L3_runtime_mutation",
            f"expected L3_runtime_mutation, got {result.autonomy_level!r}",
        ))
    findings.append(_finding(
        "l3_friction_budget_four",
        classify_action(ActionInput(side_effect_class="runtime-mutation")).friction_budget == 4,
        "expected friction_budget=4",
    ))
    return findings


# ---------------------------------------------------------------------------
# L4 classification
# ---------------------------------------------------------------------------

def eval_l4_external_elevators() -> list[dict]:
    findings = []
    # network_allowed=True → L4
    inp = ActionInput(side_effect_class="read-only", network_allowed=True)
    result = classify_action(inp)
    findings.append(_finding(
        "l4_network_allowed_raises_to_l4",
        result.autonomy_level == "L4_external_high_risk",
        f"expected L4, got {result.autonomy_level!r}",
    ))
    # data_sensitivity high → L4
    inp2 = ActionInput(side_effect_class="read-only", data_sensitivity="high")
    result2 = classify_action(inp2)
    findings.append(_finding(
        "l4_data_sensitivity_high_raises",
        result2.autonomy_level == "L4_external_high_risk",
        f"expected L4, got {result2.autonomy_level!r}",
    ))
    # data_sensitivity critical → L4
    inp3 = ActionInput(side_effect_class="read-only", data_sensitivity="critical")
    result3 = classify_action(inp3)
    findings.append(_finding(
        "l4_data_sensitivity_critical_raises",
        result3.autonomy_level == "L4_external_high_risk",
        f"expected L4, got {result3.autonomy_level!r}",
    ))
    # requires_human_decision → L4
    inp4 = ActionInput(side_effect_class="read-only", requires_human_decision=True)
    result4 = classify_action(inp4)
    findings.append(_finding(
        "l4_requires_human_decision_raises",
        result4.autonomy_level == "L4_external_high_risk",
        f"expected L4, got {result4.autonomy_level!r}",
    ))
    # target_scope external → L4
    for scope in ("external", "cloud", "production"):
        inp5 = ActionInput(side_effect_class="read-only", target_scope=scope)
        result5 = classify_action(inp5)
        findings.append(_finding(
            f"l4_target_scope_{scope}_raises",
            result5.autonomy_level == "L4_external_high_risk",
            f"expected L4, got {result5.autonomy_level!r}",
        ))
    # L4 carries blocked_reason
    inp6 = ActionInput(side_effect_class="external")
    result6 = classify_action(inp6)
    findings.append(_finding(
        "l4_carries_blocked_reason",
        bool(result6.blocked_reason),
        f"expected non-empty blocked_reason; got {result6.blocked_reason!r}",
    ))
    findings.append(_finding(
        "l4_friction_budget_nine",
        result6.friction_budget == 9,
        f"expected 9, got {result6.friction_budget}",
    ))
    return findings


# ---------------------------------------------------------------------------
# Override only raises
# ---------------------------------------------------------------------------

def eval_override_only_increases_level() -> list[dict]:
    findings = []
    # Override to a higher level: should be accepted
    inp = ActionInput(side_effect_class="read-only", risk_level_override="L2_local_code")
    result = classify_action(inp)
    findings.append(_finding(
        "override_raises_level",
        result.autonomy_level == "L2_local_code",
        f"expected L2_local_code, got {result.autonomy_level!r}",
    ))
    # Override to a lower level: should be ignored
    inp2 = ActionInput(side_effect_class="runtime-mutation", risk_level_override="L0_observe")
    result2 = classify_action(inp2)
    findings.append(_finding(
        "override_cannot_lower_level",
        result2.autonomy_level == "L3_runtime_mutation",
        f"expected L3_runtime_mutation (override ignored), got {result2.autonomy_level!r}",
    ))
    return findings


# ---------------------------------------------------------------------------
# classification_is_not_permission invariant
# ---------------------------------------------------------------------------

def eval_classification_is_not_permission() -> list[dict]:
    findings = []
    for sec in ("read-only", "derived-write", "local-mutation", "runtime-mutation", "external"):
        result = classify_action(ActionInput(side_effect_class=sec))
        findings.append(_finding(
            f"classification_is_not_permission_{sec.replace('-', '_')}",
            result.classification_is_not_permission is True,
            f"classification_is_not_permission must always be True; got {result.classification_is_not_permission!r}",
        ))
    return findings


# ---------------------------------------------------------------------------
# MCP server source: L4 always blocked
# ---------------------------------------------------------------------------

def eval_mcp_never_executes_l4() -> list[dict]:
    findings = []
    try:
        import adapters.runtime_manager_mcp_stdio.server as srv_mod
        src = inspect.getsource(srv_mod)
    except Exception as exc:
        findings.append(_finding("mcp_server_source_readable", False, str(exc)))
        return findings

    has_l4_block = "L4_external_high_risk" in src and "unconditionally blocked" in src
    findings.append(_finding(
        "mcp_server_blocks_l4_unconditionally",
        has_l4_block,
        "server source must mention L4_external_high_risk and unconditionally blocked",
    ))
    has_token_max = "token_max" in src and "max_autonomy_level" in src
    findings.append(_finding(
        "mcp_server_enforces_token_max_autonomy_level",
        has_token_max,
        "server source must enforce token_max / max_autonomy_level",
    ))
    has_counter = "increment_policy_counter" in src and "mcp_level_blocked" in src
    findings.append(_finding(
        "mcp_server_increments_mcp_level_blocked_counter",
        has_counter,
        "server source must call increment_policy_counter('mcp_level_blocked') on block",
    ))
    return findings


# ---------------------------------------------------------------------------
# explain_levels completeness
# ---------------------------------------------------------------------------

def eval_explain_levels_completeness() -> list[dict]:
    findings = []
    levels = explain_levels()
    level_names = [lv["level"] for lv in levels]
    for expected in LEVEL_ORDER:
        findings.append(_finding(
            f"explain_levels_includes_{expected}",
            expected in level_names,
            f"expected {expected!r} in explain_levels()",
        ))
    l4 = next((lv for lv in levels if lv["level"] == "L4_external_high_risk"), None)
    if l4 is not None:
        findings.append(_finding(
            "l4_not_mcp_executable",
            l4.get("mcp_executable") is False,
            f"L4 mcp_executable must be False; got {l4.get('mcp_executable')!r}",
        ))
    return findings


# ---------------------------------------------------------------------------
# Top-level runner
# ---------------------------------------------------------------------------

def run_all() -> dict[str, Any]:
    all_findings: list[dict] = []
    for fn in (
        eval_l0_read_only,
        eval_l1_derived_write,
        eval_l2_local_code,
        eval_l3_runtime_mutation,
        eval_l4_external_elevators,
        eval_override_only_increases_level,
        eval_classification_is_not_permission,
        eval_mcp_never_executes_l4,
        eval_explain_levels_completeness,
    ):
        all_findings.extend(fn())
    passed = sum(1 for f in all_findings if f["passed"])
    failed = sum(1 for f in all_findings if not f["passed"])
    return {
        "eval": "eval_autonomy_levels",
        "authority": EVAL_AUTHORITY,
        "eval_is_not_permission": True,
        "total": len(all_findings),
        "passed": passed,
        "failed": failed,
        "findings": all_findings,
    }
