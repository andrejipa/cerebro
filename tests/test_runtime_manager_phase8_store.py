"""Phase 8 store tests: classify_runtime_action, autonomy metadata, policy counters, max_autonomy_level."""
from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from core.runtime_manager_store import RuntimeManagerStore, RuntimeManagerStoreError


def _write_observation_center(root: Path, observations: str) -> Path:
    operations = root / "docs" / "operations"
    operations.mkdir(parents=True, exist_ok=True)
    path = operations / "observation_center.toml"
    path.write_text(
        f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "projection only"
opportunity_map = "projection only"

{observations}
""",
        encoding="utf-8",
    )
    return path


def _obs(oid: str) -> str:
    return f"""[[observations]]
id = "{oid}"
title = "{oid} title"
status = "open"
kind = "slice"
priority = "medium"
boundary = "core/read-model only"
trigger = "FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_1.md"
dependencies = []
dependencies_satisfied = true
next_action = "do {oid}"
done_when = "done"
halt_if = "halt"
"""


def _cmd(
    cid: str,
    *,
    side_effect_class: str = "read-only",
    network_allowed: bool = False,
    approval_requirement: str = "none",
    data_sensitivity: str = "none",
    target_scope: str = "local",
    requires_human_decision: bool = False,
    risk_level_override: str = "",
) -> str:
    argv = f'["python", "-m", "{cid}"]'
    rhd = "true" if requires_human_decision else "false"
    na = "true" if network_allowed else "false"
    return f"""[[command_registry]]
id = "{cid}"
argv_prefix = {argv}
path_scope = "."
side_effect_class = "{side_effect_class}"
network_allowed = {na}
timeout_seconds = 60
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "{approval_requirement}"
rollback_class = "reversible"
status = "enabled"
data_sensitivity = "{data_sensitivity}"
target_scope = "{target_scope}"
requires_human_decision = {rhd}
risk_level_override = "{risk_level_override}"
"""


class TestClassifyRuntimeAction(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = _write_observation_center(self.root, _obs("obs-a") + _cmd("cmd-read"))
        store = RuntimeManagerStore(self.root)
        store.sync_observation_center(observation_center_path=path)
        self.store = store

    def tearDown(self):
        self.tmp.cleanup()

    def test_classify_read_only_is_l0(self):
        result = self.store.classify_runtime_action("cmd-read")
        assert result.autonomy_level == "L0_observe"

    def test_classify_unknown_command_raises(self):
        with self.assertRaises(RuntimeManagerStoreError):
            self.store.classify_runtime_action("no-such-cmd")

    def test_classify_result_is_not_permission(self):
        result = self.store.classify_runtime_action("cmd-read")
        assert result.classification_is_not_permission is True

    def test_classify_network_allowed_raises_to_l4(self):
        path = _write_observation_center(
            self.root, _obs("obs-net") + _cmd("cmd-net", side_effect_class="read-only", network_allowed=True)
        )
        self.store.sync_observation_center(observation_center_path=path)
        result = self.store.classify_runtime_action("cmd-net")
        assert result.autonomy_level == "L4_external_high_risk"

    def test_classify_runtime_mutation_is_l3(self):
        path = _write_observation_center(
            self.root, _obs("obs-b") + _cmd("cmd-mut", side_effect_class="runtime-mutation")
        )
        self.store.sync_observation_center(observation_center_path=path)
        result = self.store.classify_runtime_action("cmd-mut")
        assert result.autonomy_level == "L3_runtime_mutation"


class TestCheckCommandEligibilityAutonomyMetadata(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)

    def tearDown(self):
        self.tmp.cleanup()

    def _setup(self, entries: str) -> RuntimeManagerStore:
        path = _write_observation_center(self.root, _obs("obs-a") + entries)
        store = RuntimeManagerStore(self.root)
        store.sync_observation_center(observation_center_path=path)
        return store

    def test_eligibility_includes_autonomy_level(self):
        store = self._setup(_cmd("cmd-read"))
        result = store.check_command_eligibility("cmd-read")
        assert hasattr(result, "autonomy_level")
        assert result.autonomy_level == "L0_observe"

    def test_eligibility_includes_friction_budget(self):
        store = self._setup(_cmd("cmd-read"))
        result = store.check_command_eligibility("cmd-read")
        assert result.friction_budget == 0

    def test_l4_command_is_ineligible(self):
        store = self._setup(_cmd("cmd-l4", side_effect_class="external"))
        result = store.check_command_eligibility("cmd-l4")
        assert not result.eligible
        assert "l4_external_high_risk_blocked" in result.blockers

    def test_l3_command_eligible_when_approval_present(self):
        store = self._setup(_cmd("cmd-l3", side_effect_class="runtime-mutation", approval_requirement="none"))
        result = store.check_command_eligibility("cmd-l3")
        assert result.eligible
        assert result.autonomy_level == "L3_runtime_mutation"


class TestPolicyCounters(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = _write_observation_center(self.root, _obs("obs-a"))
        store = RuntimeManagerStore(self.root)
        store.sync_observation_center(observation_center_path=path)
        self.store = store

    def tearDown(self):
        self.tmp.cleanup()

    def test_read_counter_starts_at_zero(self):
        assert self.store.read_policy_counter("mcp_level_blocked") == 0

    def test_increment_counter(self):
        self.store.increment_policy_counter("mcp_level_blocked")
        assert self.store.read_policy_counter("mcp_level_blocked") == 1

    def test_increment_counter_twice(self):
        self.store.increment_policy_counter("mcp_level_blocked")
        self.store.increment_policy_counter("mcp_level_blocked")
        assert self.store.read_policy_counter("mcp_level_blocked") == 2

    def test_different_counters_independent(self):
        self.store.increment_policy_counter("mcp_level_blocked")
        self.store.increment_policy_counter("other_counter")
        assert self.store.read_policy_counter("mcp_level_blocked") == 1
        assert self.store.read_policy_counter("other_counter") == 1


class TestMaxAutonomyLevelOnToken(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = _write_observation_center(self.root, _obs("obs-a"))
        store = RuntimeManagerStore(self.root)
        store.sync_observation_center(observation_center_path=path)
        self.store = store

    def tearDown(self):
        self.tmp.cleanup()

    def test_issue_token_default_max_autonomy_level(self):
        record, _raw = self.store.issue_adapter_token(
            agent_id="agent-1", agent_role="runner",
            scopes=["runtime:read"],
        )
        assert record.max_autonomy_level == "L3_runtime_mutation"

    def test_issue_token_explicit_max_autonomy_level(self):
        record, _raw = self.store.issue_adapter_token(
            agent_id="agent-2", agent_role="observer",
            scopes=["runtime:read"],
            max_autonomy_level="L0_observe",
        )
        assert record.max_autonomy_level == "L0_observe"

    def test_authenticate_token_returns_max_autonomy_level(self):
        _record, raw = self.store.issue_adapter_token(
            agent_id="agent-3", agent_role="runner",
            scopes=["runtime:read"],
            max_autonomy_level="L1_derived",
        )
        authed = self.store.authenticate_adapter_token(raw)
        assert authed is not None
        assert authed.max_autonomy_level == "L1_derived"

    def test_issue_token_l4_raises(self):
        with self.assertRaises(RuntimeManagerStoreError):
            self.store.issue_adapter_token(
                agent_id="agent-4", agent_role="runner",
                scopes=["runtime:read"],
                max_autonomy_level="L4_external_high_risk",
            )

    def test_issue_token_unknown_max_autonomy_level_raises(self):
        with self.assertRaises(RuntimeManagerStoreError):
            self.store.issue_adapter_token(
                agent_id="agent-5", agent_role="runner",
                scopes=["runtime:read"],
                max_autonomy_level="L99_unknown",
            )


class TestMetricsAutonomyFields(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.root = Path(self.tmp.name)
        path = _write_observation_center(self.root, _obs("obs-a"))
        store = RuntimeManagerStore(self.root)
        store.sync_observation_center(observation_center_path=path)
        self.store = store

    def tearDown(self):
        self.tmp.cleanup()

    def test_metrics_has_actions_l0_field(self):
        metrics = self.store.read_metrics()
        assert hasattr(metrics, "actions_l0")

    def test_metrics_has_mcp_level_blocked_field(self):
        metrics = self.store.read_metrics()
        assert hasattr(metrics, "mcp_level_blocked")

    def test_mcp_level_blocked_reflects_counter(self):
        self.store.increment_policy_counter("mcp_level_blocked")
        self.store.increment_policy_counter("mcp_level_blocked")
        metrics = self.store.read_metrics()
        assert metrics.mcp_level_blocked >= 2


if __name__ == "__main__":
    unittest.main()
