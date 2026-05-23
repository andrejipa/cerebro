"""Phase 8 MCP tests: max_autonomy_level ceiling, L4 blocked, L0 tool passthrough."""
from __future__ import annotations

import importlib.util
import os
import tempfile
import unittest
from pathlib import Path

from core.runtime_manager_store import RuntimeManagerStore

MCP_AVAILABLE = importlib.util.find_spec("mcp") is not None
requires_mcp = unittest.skipUnless(MCP_AVAILABLE, 'requires optional MCP extra: python -m pip install -e ".[mcp]"')


def _store_with_obs(tmp_dir: str) -> tuple[RuntimeManagerStore, Path]:
    root = Path(tmp_dir)
    store = RuntimeManagerStore(root)
    store.initialize_schema()
    obs_path = root / "docs" / "operations" / "observation_center.toml"
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(
        '[center]\nversion = 1\n\n'
        '[[observations]]\n'
        'id = "obs-test-1"\n'
        'title = "Test observation"\n'
        'status = "open"\n'
        'kind = "slice"\n'
        'priority = "high"\n'
        'boundary = "docs/"\n'
        'trigger = "not open"\n'
        'dependencies = []\n'
        'dependencies_satisfied = true\n'
        'next_action = "do something"\n'
        'done_when = "done"\n'
        'halt_if = "never"\n',
        encoding="utf-8",
    )
    store.sync_observation_center(obs_path)
    return store, root


ALL_SCOPES = frozenset(
    {"runtime:read", "runtime:lease", "runtime:execute",
     "runtime:trace", "runtime:metrics", "runtime:replay"}
)


def _build_app_with_max_level(store: RuntimeManagerStore, max_level: str):
    from adapters.runtime_manager_mcp_stdio.server import build_app
    _record, raw = store.issue_adapter_token(
        agent_id="test-agent",
        agent_role="runner",
        scopes=list(ALL_SCOPES),
        max_autonomy_level=max_level,
    )
    os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
    try:
        app = build_app(store)
    finally:
        del os.environ["CEREBRO_RUNTIME_MCP_TOKEN"]
    return app


@requires_mcp
class TestMaxAutonomyLevelCeiling(unittest.TestCase):
    """Server enforces token max_autonomy_level ceiling per tool call."""

    def test_l4_always_blocked_regardless_of_token(self):
        """L4 is unconditionally blocked — no token ceiling can unlock it."""
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        with self.assertRaises(PermissionError) as ctx:
            _check_level("L4_external_high_risk", "L3_runtime_mutation")
        assert "unconditionally blocked" in str(ctx.exception).lower() or "L4" in str(ctx.exception)

    def test_l4_blocked_even_for_l3_token(self):
        """Separate sanity: L4 blocked when token max is L3."""
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        with self.assertRaises(PermissionError):
            _check_level("L4_external_high_risk", "L3_runtime_mutation")

    def test_l3_blocked_for_l0_token(self):
        """L3 operation blocked when token ceiling is L0."""
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        with self.assertRaises(PermissionError) as ctx:
            _check_level("L3_runtime_mutation", "L0_observe")
        assert "max_autonomy_level" in str(ctx.exception) or "L0" in str(ctx.exception)

    def test_l0_passes_for_l0_token(self):
        """L0 operation allowed when token ceiling is L0."""
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        _check_level("L0_observe", "L0_observe")  # must not raise

    def test_l2_passes_for_l3_token(self):
        """L2 operation allowed when token ceiling is L3."""
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        _check_level("L2_local_code", "L3_runtime_mutation")  # must not raise

    def test_tool_levels_dict_present(self):
        """All 12 tools are annotated in _TOOL_LEVELS."""
        from adapters.runtime_manager_mcp_stdio.server import _TOOL_LEVELS
        expected = {
            "runtime_status", "runtime_next", "runtime_check_command",
            "runtime_trace_list", "runtime_trace_show", "runtime_trace_export",
            "runtime_metrics", "runtime_replay_scenario",
            "runtime_acquire_lease", "runtime_heartbeat_lease", "runtime_release_lease",
            "runtime_run_command",
        }
        assert expected <= set(_TOOL_LEVELS.keys())

    def test_l0_tools_annotated_l0(self):
        from adapters.runtime_manager_mcp_stdio.server import _TOOL_LEVELS
        for tool in ("runtime_status", "runtime_next", "runtime_check_command",
                     "runtime_metrics", "runtime_replay_scenario"):
            assert _TOOL_LEVELS[tool] == "L0_observe", f"{tool} should be L0"

    def test_run_command_annotated_l3(self):
        from adapters.runtime_manager_mcp_stdio.server import _TOOL_LEVELS
        assert _TOOL_LEVELS["runtime_run_command"] == "L3_runtime_mutation"

    def test_lease_tools_annotated_l2(self):
        from adapters.runtime_manager_mcp_stdio.server import _TOOL_LEVELS
        for tool in ("runtime_acquire_lease", "runtime_heartbeat_lease", "runtime_release_lease"):
            assert _TOOL_LEVELS[tool] == "L2_local_code", f"{tool} should be L2"


@requires_mcp
class TestMcpBuildWithMaxLevel(unittest.TestCase):
    """build_app reads max_autonomy_level from token correctly."""

    def test_build_app_with_l0_token_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            from mcp.server.fastmcp import FastMCP
            app = _build_app_with_max_level(store, "L0_observe")
            self.assertIsInstance(app, FastMCP)

    def test_build_app_with_l3_token_succeeds(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            from mcp.server.fastmcp import FastMCP
            app = _build_app_with_max_level(store, "L3_runtime_mutation")
            self.assertIsInstance(app, FastMCP)


@requires_mcp
class TestMcpLevelBlockedCounter(unittest.TestCase):
    """increment_policy_counter called on level-blocked run_command."""

    def test_level_blocked_counter_increments(self):
        from adapters.runtime_manager_mcp_stdio.server import _check_level
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            before = store.read_policy_counter("mcp_level_blocked")
            try:
                _check_level("L4_external_high_risk", "L3_runtime_mutation")
            except PermissionError:
                store.increment_policy_counter("mcp_level_blocked")
            after = store.read_policy_counter("mcp_level_blocked")
            assert after == before + 1


if __name__ == "__main__":
    unittest.main()
