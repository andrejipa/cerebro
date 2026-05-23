"""In-process tests for the MCP STDIO server (Phase 7).

Uses create_connected_server_and_client_session for transport-free testing.
Token is issued via the store and set in os.environ before build_app().
"""
from __future__ import annotations

import asyncio
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
        'source_plan = "none"\n'
        'source_snapshot = "test"\n'
        'auto_continuation = false\n'
        'dependencies = []\n'
        'dependencies_satisfied = true\n'
        'next_action = "do something"\n'
        'done_when = "done"\n'
        'halt_if = "never"\n',
        encoding="utf-8",
    )
    store.sync_observation_center(obs_path)
    return store, root


def _issue_token(store: RuntimeManagerStore, scopes: frozenset[str]) -> str:
    """Issue a token and return the raw string."""
    _, raw = store.issue_adapter_token(
        agent_id="test-agent",
        agent_role="test-worker",
        scopes=scopes,
        ttl_seconds=3600,
    )
    return raw


ALL_SCOPES = frozenset(
    {"runtime:read", "runtime:lease", "runtime:execute",
     "runtime:trace", "runtime:metrics", "runtime:replay"}
)


@requires_mcp
class McpServerBuildTests(unittest.TestCase):
    """Tests that build_app() produces a valid FastMCP app."""

    def test_build_app_returns_fastmcp(self):
        from mcp.server.fastmcp import FastMCP
        from adapters.runtime_manager_mcp_stdio.server import build_app
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                app = build_app(store)
                self.assertIsInstance(app, FastMCP)
            finally:
                del os.environ["CEREBRO_RUNTIME_MCP_TOKEN"]

    def test_build_app_fails_without_token_env(self):
        from adapters.runtime_manager_mcp_stdio.auth import AuthError
        from adapters.runtime_manager_mcp_stdio.server import build_app
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)
            with self.assertRaises(AuthError):
                build_app(store)

    def test_build_app_fails_with_revoked_token(self):
        from adapters.runtime_manager_mcp_stdio.auth import AuthError
        from adapters.runtime_manager_mcp_stdio.server import build_app
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            tok, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            store.revoke_adapter_token(tok.token_id)
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                with self.assertRaises(AuthError):
                    build_app(store)
            finally:
                del os.environ["CEREBRO_RUNTIME_MCP_TOKEN"]


@requires_mcp
class McpToolListTests(unittest.TestCase):
    """Verify that the correct tools are registered (no approval tool)."""

    def _get_tool_names(self, store: RuntimeManagerStore, raw: str) -> list[str]:
        async def _run():
            from mcp.client.session import ClientSession
            from mcp.server.fastmcp import FastMCP
            from mcp.shared.memory import create_connected_server_and_client_session
            from adapters.runtime_manager_mcp_stdio.server import build_app
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                app = build_app(store)
                server = app._mcp_server
                async with create_connected_server_and_client_session(server) as client:
                    result = await client.list_tools()
                    return [t.name for t in result.tools]
            finally:
                os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)

        return asyncio.run(_run())

    def test_expected_tools_registered(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            names = self._get_tool_names(store, raw)

            expected = {
                "runtime_status",
                "runtime_next",
                "runtime_check_command",
                "runtime_acquire_lease",
                "runtime_heartbeat_lease",
                "runtime_release_lease",
                "runtime_run_command",
                "runtime_trace_list",
                "runtime_trace_show",
                "runtime_trace_export",
                "runtime_metrics",
                "runtime_replay_scenario",
            }
            for name in expected:
                self.assertIn(name, names, msg=f"Tool {name!r} not registered")

    def test_approval_tool_not_registered(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            names = self._get_tool_names(store, raw)
            self.assertNotIn("runtime_record_approval", names)
            self.assertNotIn("record_approval", names)


@requires_mcp
class McpToolCallTests(unittest.TestCase):
    """In-process tool call tests via create_connected_server_and_client_session."""

    def _run_tool(
        self,
        store: RuntimeManagerStore,
        raw: str,
        tool_name: str,
        args: dict,
    ) -> dict:
        async def _run():
            import json
            from mcp.shared.memory import create_connected_server_and_client_session
            from adapters.runtime_manager_mcp_stdio.server import build_app
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                app = build_app(store)
                server = app._mcp_server
                async with create_connected_server_and_client_session(server) as client:
                    result = await client.call_tool(tool_name, args)
                    if result.isError:
                        raise RuntimeError(
                            f"Tool {tool_name!r} returned error: "
                            + (result.content[0].text if result.content else "<no content>")
                        )
                    text = result.content[0].text if result.content else "{}"
                    if not text:
                        return {}
                    try:
                        return json.loads(text)
                    except json.JSONDecodeError:
                        # FastMCP may wrap dict in a JSON envelope
                        return {"raw": text}
            finally:
                os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)

        return asyncio.run(_run())

    def test_runtime_status_returns_dict(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            result = self._run_tool(store, raw, "runtime_status", {})
            self.assertIsInstance(result, dict)

    def test_runtime_status_no_stdout_stderr(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            result = self._run_tool(store, raw, "runtime_status", {})
            self.assertNotIn("stdout", result)
            self.assertNotIn("stderr", result)

    def test_runtime_next_returns_selected_or_none(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            result = self._run_tool(store, raw, "runtime_next", {})
            self.assertIn("reason", result)

    def test_runtime_metrics_has_not_permission(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            result = self._run_tool(store, raw, "runtime_metrics", {})
            self.assertIn("not_permission", result)
            self.assertTrue(result["not_permission"])

    def test_runtime_trace_list_has_not_permission(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            result = self._run_tool(store, raw, "runtime_trace_list", {})
            self.assertIn("not_permission", result)
            self.assertTrue(result["not_permission"])

    def test_scope_enforcement_read_scope_required(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            # Issue token with only metrics scope — status requires runtime:read
            raw = _issue_token(store, frozenset({"runtime:metrics"}))
            async def _run():
                from mcp.shared.memory import create_connected_server_and_client_session
                from adapters.runtime_manager_mcp_stdio.server import build_app
                os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
                try:
                    app = build_app(store)
                    server = app._mcp_server
                    async with create_connected_server_and_client_session(server) as client:
                        result = await client.call_tool("runtime_status", {})
                        return result.isError
                finally:
                    os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)
            is_error = asyncio.run(_run())
            self.assertTrue(is_error)

    def _call_replay(self, store, raw: str, path: str) -> bool:
        """Helper: returns isError."""
        async def _run():
            from mcp.shared.memory import create_connected_server_and_client_session
            from adapters.runtime_manager_mcp_stdio.server import build_app
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                app = build_app(store)
                server = app._mcp_server
                async with create_connected_server_and_client_session(server) as client:
                    result = await client.call_tool("runtime_replay_scenario", {"scenario_path": path})
                    return result.isError
            finally:
                os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)
        return asyncio.run(_run())

    def test_replay_scenario_dotdot_traversal_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            self.assertTrue(self._call_replay(store, raw, "../secret.json"))

    def test_replay_scenario_absolute_path_rejected(self):
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            self.assertTrue(self._call_replay(store, raw, "/etc/passwd"))

    def test_replay_scenario_inside_root_reaches_store(self):
        # Path inside root is allowed by the guard (store.replay_scenario will raise
        # its own error for a non-existent file, but the guard itself does not block).
        with tempfile.TemporaryDirectory() as td:
            store, root = _store_with_obs(td)
            raw = _issue_token(store, ALL_SCOPES)
            # isError=True because the file doesn't exist, but we confirm the error
            # is NOT the guard (guard raises ValueError, store raises RuntimeManagerStoreError).
            async def _run():
                from mcp.shared.memory import create_connected_server_and_client_session
                from adapters.runtime_manager_mcp_stdio.server import build_app
                os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
                try:
                    app = build_app(store)
                    server = app._mcp_server
                    async with create_connected_server_and_client_session(server) as client:
                        result = await client.call_tool("runtime_replay_scenario",
                                                        {"scenario_path": "scenarios/missing.json"})
                        return result.isError, result.content[0].text if result.content else ""
                finally:
                    os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)
            is_error, msg = asyncio.run(_run())
            self.assertTrue(is_error)
            # Guard message says "must resolve inside" — store error says "not found" or similar.
            self.assertNotIn("must resolve inside", msg)


class McpAuthTests(unittest.TestCase):
    """Tests for auth module (token from env var only)."""

    def test_auth_succeeds_with_valid_token(self):
        from adapters.runtime_manager_mcp_stdio.auth import load_token_from_env
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            _, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                tok = load_token_from_env(store)
                self.assertEqual(tok.agent_id, "a")
            finally:
                del os.environ["CEREBRO_RUNTIME_MCP_TOKEN"]

    def test_auth_fails_without_env_var(self):
        from adapters.runtime_manager_mcp_stdio.auth import AuthError, load_token_from_env
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)
            with self.assertRaises(AuthError):
                load_token_from_env(store)

    def test_auth_fails_with_wrong_token(self):
        from adapters.runtime_manager_mcp_stdio.auth import AuthError, load_token_from_env
        with tempfile.TemporaryDirectory() as td:
            store, _ = _store_with_obs(td)
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = "deadbeef" * 8
            try:
                with self.assertRaises(AuthError):
                    load_token_from_env(store)
            finally:
                del os.environ["CEREBRO_RUNTIME_MCP_TOKEN"]


class McpScopeModuleTests(unittest.TestCase):
    def test_require_scope_passes_when_present(self):
        from adapters.runtime_manager_mcp_stdio.scopes import require_scope
        require_scope(("runtime:read", "runtime:execute"), "runtime:read")  # no exception

    def test_require_scope_raises_when_absent(self):
        from adapters.runtime_manager_mcp_stdio.scopes import require_scope
        with self.assertRaises(PermissionError):
            require_scope(("runtime:read",), "runtime:execute")

    def test_all_scopes_constant(self):
        from adapters.runtime_manager_mcp_stdio.scopes import ALL_SCOPES
        self.assertIn("runtime:read", ALL_SCOPES)
        self.assertIn("runtime:lease", ALL_SCOPES)
        self.assertIn("runtime:execute", ALL_SCOPES)
        self.assertIn("runtime:trace", ALL_SCOPES)
        self.assertIn("runtime:metrics", ALL_SCOPES)
        self.assertIn("runtime:replay", ALL_SCOPES)


if __name__ == "__main__":
    unittest.main()
