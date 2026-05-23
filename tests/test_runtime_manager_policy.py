"""Tests for core/runtime_manager_policy.py — Phase 8."""
from __future__ import annotations

import pytest

from core.runtime_manager_policy import (
    ActionClassification,
    ActionInput,
    LEVEL_ORDER,
    classify_action,
    explain_levels,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _classify(**kwargs) -> ActionClassification:
    return classify_action(ActionInput(**kwargs))


# ---------------------------------------------------------------------------
# L0 — read-only
# ---------------------------------------------------------------------------

class TestL0Observe:
    def test_read_only_is_l0(self):
        result = _classify(side_effect_class="read-only")
        assert result.autonomy_level == "L0_observe"

    def test_l0_friction_budget_zero(self):
        assert _classify(side_effect_class="read-only").friction_budget == 0

    def test_l0_no_required_controls(self):
        assert _classify(side_effect_class="read-only").required_controls == ()

    def test_l0_not_blocked(self):
        assert _classify(side_effect_class="read-only").blocked_reason == ""


# ---------------------------------------------------------------------------
# L1 — derived write
# ---------------------------------------------------------------------------

class TestL1Derived:
    @pytest.mark.parametrize("sec", ["derived-write", "docs-write"])
    def test_l1_side_effects(self, sec):
        result = _classify(side_effect_class=sec)
        assert result.autonomy_level == "L1_derived"

    def test_l1_friction_budget_one(self):
        assert _classify(side_effect_class="derived-write").friction_budget == 1

    def test_l1_ops_path_requires_diff_check(self):
        result = _classify(side_effect_class="derived-write", path_scope="docs/operations/foo.md")
        assert "diff_check" in result.required_controls

    def test_l1_non_ops_path_no_controls(self):
        result = _classify(side_effect_class="derived-write", path_scope="src/")
        assert result.required_controls == ()


# ---------------------------------------------------------------------------
# L2 — local code
# ---------------------------------------------------------------------------

class TestL2LocalCode:
    @pytest.mark.parametrize("sec", ["local-mutation", "test-run"])
    def test_l2_side_effects(self, sec):
        result = _classify(side_effect_class=sec)
        assert result.autonomy_level == "L2_local_code"

    def test_l2_friction_budget_two(self):
        assert _classify(side_effect_class="local-mutation").friction_budget == 2

    def test_l2_controls_include_lease_and_registry(self):
        result = _classify(side_effect_class="local-mutation")
        assert "lease_required" in result.required_controls
        assert "command_registry" in result.required_controls

    def test_l2_approval_required_when_not_none(self):
        result = _classify(side_effect_class="local-mutation", approval_requirement="required")
        assert "approval_required" in result.required_controls

    def test_l2_no_approval_when_none(self):
        result = _classify(side_effect_class="local-mutation", approval_requirement="none")
        assert "approval_required" not in result.required_controls


# ---------------------------------------------------------------------------
# L3 — runtime mutation
# ---------------------------------------------------------------------------

class TestL3RuntimeMutation:
    @pytest.mark.parametrize("sec", ["runtime-mutation", "system-mutation", "destructive"])
    def test_l3_side_effects(self, sec):
        result = _classify(side_effect_class=sec)
        assert result.autonomy_level == "L3_runtime_mutation"

    def test_l3_friction_budget_four(self):
        assert _classify(side_effect_class="runtime-mutation").friction_budget == 4

    def test_l3_controls_include_evidence_and_trace(self):
        result = _classify(side_effect_class="runtime-mutation")
        assert "evidence_required" in result.required_controls
        assert "trace_required" in result.required_controls

    def test_l3_data_sensitivity_sensitive_raises_to_l3(self):
        result = _classify(side_effect_class="read-only", data_sensitivity="sensitive")
        assert result.autonomy_level == "L3_runtime_mutation"

    def test_l3_data_sensitivity_sensitive_does_not_raise_past_l3(self):
        result = _classify(side_effect_class="runtime-mutation", data_sensitivity="sensitive")
        assert result.autonomy_level == "L3_runtime_mutation"


# ---------------------------------------------------------------------------
# L4 — external high risk elevators
# ---------------------------------------------------------------------------

class TestL4ExternalHighRisk:
    def test_l4_external_side_effect(self):
        result = _classify(side_effect_class="external")
        assert result.autonomy_level == "L4_external_high_risk"

    def test_l4_network_allowed_raises(self):
        result = _classify(side_effect_class="read-only", network_allowed=True)
        assert result.autonomy_level == "L4_external_high_risk"

    def test_l4_data_sensitivity_high(self):
        result = _classify(side_effect_class="read-only", data_sensitivity="high")
        assert result.autonomy_level == "L4_external_high_risk"

    def test_l4_data_sensitivity_critical(self):
        result = _classify(side_effect_class="read-only", data_sensitivity="critical")
        assert result.autonomy_level == "L4_external_high_risk"

    def test_l4_requires_human_decision(self):
        result = _classify(side_effect_class="read-only", requires_human_decision=True)
        assert result.autonomy_level == "L4_external_high_risk"

    @pytest.mark.parametrize("scope", ["external", "cloud", "production", "release", "remote"])
    def test_l4_target_scope_external(self, scope):
        result = _classify(side_effect_class="read-only", target_scope=scope)
        assert result.autonomy_level == "L4_external_high_risk"

    def test_l4_friction_budget_nine(self):
        result = _classify(side_effect_class="external")
        assert result.friction_budget == 9

    def test_l4_carries_blocked_reason(self):
        result = _classify(side_effect_class="external")
        assert result.blocked_reason != ""

    def test_l4_controls_include_human_decision_required(self):
        result = _classify(side_effect_class="external")
        assert "human_decision_required" in result.required_controls


# ---------------------------------------------------------------------------
# Override only raises
# ---------------------------------------------------------------------------

class TestRiskLevelOverride:
    def test_override_raises_level(self):
        result = _classify(side_effect_class="read-only", risk_level_override="L2_local_code")
        assert result.autonomy_level == "L2_local_code"

    def test_override_cannot_lower_level(self):
        result = _classify(side_effect_class="runtime-mutation", risk_level_override="L0_observe")
        assert result.autonomy_level == "L3_runtime_mutation"

    def test_override_rationale_notes_ignored_lower(self):
        result = _classify(side_effect_class="runtime-mutation", risk_level_override="L0_observe")
        assert "ignored" in result.rationale

    def test_override_unknown_level_ignored(self):
        result = _classify(side_effect_class="read-only", risk_level_override="L99_unknown")
        assert result.autonomy_level == "L0_observe"


# ---------------------------------------------------------------------------
# classification_is_not_permission invariant
# ---------------------------------------------------------------------------

class TestClassificationIsNotPermission:
    @pytest.mark.parametrize("sec", [
        "read-only", "derived-write", "local-mutation", "runtime-mutation", "external"
    ])
    def test_always_true(self, sec):
        result = _classify(side_effect_class=sec)
        assert result.classification_is_not_permission is True


# ---------------------------------------------------------------------------
# Unknown side_effect_class defaults to L3
# ---------------------------------------------------------------------------

class TestUnknownSideEffectClass:
    def test_unknown_defaults_to_l3(self):
        result = _classify(side_effect_class="totally-unknown")
        assert result.autonomy_level == "L3_runtime_mutation"


# ---------------------------------------------------------------------------
# explain_levels
# ---------------------------------------------------------------------------

class TestExplainLevels:
    def test_all_levels_present(self):
        levels = explain_levels()
        names = [lv["level"] for lv in levels]
        for expected in LEVEL_ORDER:
            assert expected in names

    def test_l4_not_mcp_executable(self):
        levels = explain_levels()
        l4 = next(lv for lv in levels if lv["level"] == "L4_external_high_risk")
        assert l4["mcp_executable"] is False

    def test_l0_mcp_executable(self):
        levels = explain_levels()
        l0 = next(lv for lv in levels if lv["level"] == "L0_observe")
        assert l0["mcp_executable"] is True

    def test_friction_budgets_correct(self):
        levels = explain_levels()
        budgets = {lv["level"]: lv["friction_budget"] for lv in levels}
        assert budgets["L0_observe"] == 0
        assert budgets["L1_derived"] == 1
        assert budgets["L2_local_code"] == 2
        assert budgets["L3_runtime_mutation"] == 4
        assert budgets["L4_external_high_risk"] == 9
