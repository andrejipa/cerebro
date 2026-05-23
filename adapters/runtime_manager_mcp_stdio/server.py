"""MCP STDIO server for RuntimeManagerStore — Phase 9.

Transport: STDIO only (FastMCP default).
Auth:      CEREBRO_RUNTIME_MCP_TOKEN env var authenticated at startup AND
           re-authenticated on every tool call (per-operation auth, Phase 9).
Security:
  - AgentContext derived from token at startup, never from client input.
  - Per-operation auth: token re-read from DB on every tool call; a revoked or
    expired token raises PermissionError(token_revoked_mid_session) before any
    store access.
  - record_approval NOT exposed; approval is CLI/human only.
  - No tool accepts argv, command, shell, cwd, env, token, password, secret,
    stdout, stderr.
  - Tool outputs never include raw stdout/stderr.
  - Trace/replay/metrics results carry not_permission=True.
  - Read tools: readOnlyHint=True.
  - runtime_run_command: destructiveHint=True.
  - Each tool carries an operation autonomy level; token.max_autonomy_level
    (read fresh on each call) is the ceiling. L4 is always blocked regardless
    of token ceiling.
"""
from __future__ import annotations

import dataclasses
import sys
from pathlib import Path
from typing import Any

from mcp.server.fastmcp import FastMCP
from mcp.types import ToolAnnotations

from adapters.runtime_manager_mcp_stdio.auth import AuthError, load_raw_token_from_env
from adapters.runtime_manager_mcp_stdio.scopes import (
    SCOPE_EXECUTE,
    SCOPE_LEASE,
    SCOPE_METRICS,
    SCOPE_READ,
    SCOPE_REPLAY,
    SCOPE_TRACE,
    require_scope,
)
from adapters.runtime_manager_local_agent.agent_context import AgentContext
from adapters.runtime_manager_local_agent.persistent_rate_limiter import PersistentRateLimiter
from core.runtime_manager_policy import LEVEL_ORDER
from core.runtime_manager_store import RuntimeManagerStore

# Operation-level annotations per tool.  These are the MINIMUM levels; the
# actual level for runtime_run_command is raised further by classify_runtime_action.
_TOOL_LEVELS: dict[str, str] = {
    "runtime_status":           "L0_observe",
    "runtime_next":             "L0_observe",
    "runtime_check_command":    "L0_observe",
    "runtime_trace_list":       "L0_observe",
    "runtime_trace_show":       "L0_observe",
    "runtime_trace_export":     "L0_observe",
    "runtime_metrics":          "L0_observe",
    "runtime_replay_scenario":  "L0_observe",
    "runtime_acquire_lease":    "L2_local_code",
    "runtime_heartbeat_lease":  "L2_local_code",
    "runtime_release_lease":    "L2_local_code",
    "runtime_run_command":      "L3_runtime_mutation",
}


def _level_rank(level: str) -> int:
    try:
        return LEVEL_ORDER.index(level)
    except ValueError:
        return len(LEVEL_ORDER)


def _check_level(effective_level: str, token_max: str) -> None:
    """Raise PermissionError if the effective level exceeds the token ceiling or is L4."""
    if effective_level == "L4_external_high_risk":
        raise PermissionError(
            "autonomy_level_blocked: L4_external_high_risk actions are unconditionally blocked via MCP; this action requires an explicit human decision outside this channel"
        )
    if _level_rank(effective_level) > _level_rank(token_max):
        raise PermissionError(
            f"autonomy_level_blocked: operation requires autonomy level {effective_level!r} "
            f"but token max_autonomy_level is {token_max!r}"
        )


def _safe_dc(obj: Any) -> dict:
    """Dataclass → plain dict, filtering raw output fields."""
    if obj is None:
        return {}
    d = dataclasses.asdict(obj)
    for key in ("stdout", "stderr"):
        d.pop(key, None)
    return d


def _require_current_token_factory(store: RuntimeManagerStore, raw_env_token: str):
    """Return a per-operation auth function bound to the given store and raw token.

    The returned function re-authenticates on every call.  A revoked or expired
    token raises PermissionError(token_revoked_mid_session).

    This factory is exposed at module level so it can be tested independently of
    the full FastMCP build_app lifecycle.
    """
    def _require(required_scope: str, operation_level: str):
        current = store.authenticate_adapter_token(raw_env_token)
        if current is None:
            raise PermissionError(
                "token_revoked_mid_session: adapter token has been revoked or expired; "
                "re-issue a token to continue"
            )
        require_scope(current.scopes, required_scope)
        try:
            _check_level(operation_level, current.max_autonomy_level)
        except PermissionError:
            store.increment_policy_counter("mcp_level_blocked")
            raise
        return current
    return _require


def _check_replay_path_scope(store_root: Path, scenario_path: str) -> Path:
    """Resolve scenario_path and assert it's inside store_root. Returns resolved path."""
    resolved = (store_root / scenario_path).resolve()
    if not resolved.is_relative_to(store_root.resolve()):
        raise ValueError(
            "replay_path_out_of_scope: scenario_path must resolve inside the project root; "
            "absolute paths and path traversal are not permitted"
        )
    return resolved


def build_app(store: RuntimeManagerStore) -> FastMCP:
    """Build and return a configured FastMCP app (does NOT start STDIO loop).

    Phase 9: raw_env_token is captured at startup and re-authenticated on every
    tool call so that a revoked or expired token blocks the next call even after
    the server process is already running.
    """

    raw_env_token = load_raw_token_from_env()
    token_record = store.authenticate_adapter_token(raw_env_token)
    if token_record is None:
        raise AuthError(
            "token from CEREBRO_RUNTIME_MCP_TOKEN did not authenticate "
            "(unknown, revoked, or expired)"
        )

    ctx = AgentContext(
        agent_id=token_record.agent_id,
        agent_role=token_record.agent_role,
        session_id=token_record.token_id,
    )
    limiter = PersistentRateLimiter(store)

    _require_current_token = _require_current_token_factory(store, raw_env_token)

    def _rate(operation: str) -> None:
        allowed, retry = limiter.check(ctx.agent_id, operation)
        if not allowed:
            raise PermissionError(
                f"rate_limited: rate limit exceeded for {ctx.agent_id!r} on {operation!r}; "
                f"retry after {retry}s"
            )

    app = FastMCP("cerebro-runtime-manager")

    # ── Read tools ──────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_status() -> dict:
        """Return current queue status and runtime state."""
        _require_current_token(SCOPE_READ, _TOOL_LEVELS["runtime_status"])
        _rate("status")
        status = store.read_status()
        return {
            "state": status.state,
            "selected_id": status.selected_id or None,
            "reason": status.reason,
            "observations_total": status.observations_total,
            "observations_open": status.observations_open,
            "stale_source": status.stale_source,
            "source_sha256": status.source_sha256,
        }

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_next() -> dict:
        """Return the next selected observation ID from the queue."""
        _require_current_token(SCOPE_READ, _TOOL_LEVELS["runtime_next"])
        _rate("next")
        status = store.read_status()
        return {"selected_id": status.selected_id or None, "reason": status.reason}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_check_command(command_id: str) -> dict:
        """Check eligibility for a registered command without running it."""
        _require_current_token(SCOPE_READ, _TOOL_LEVELS["runtime_check_command"])
        _rate("check")
        result = store.check_command_eligibility(command_id)
        return _safe_dc(result)

    # ── Lease tools ──────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False))
    def runtime_acquire_lease(observation_id: str, reason: str, ttl_seconds: int = 300) -> dict:
        """Acquire a lease for an observation (required before mutations)."""
        _require_current_token(SCOPE_LEASE, _TOOL_LEVELS["runtime_acquire_lease"])
        _rate("acquire_lease")
        lease = store.acquire_lease(
            observation_id=observation_id,
            owner=ctx.lease_owner,
            ttl_seconds=ttl_seconds,
            reason=reason,
        )
        return _safe_dc(lease)

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    def runtime_heartbeat_lease(lease_id: str) -> dict:
        """Extend lease TTL to prevent expiry during long-running work."""
        _require_current_token(SCOPE_LEASE, _TOOL_LEVELS["runtime_heartbeat_lease"])
        _rate("heartbeat_lease")
        ok = store.heartbeat_lease(lease_id=lease_id, owner=ctx.lease_owner)
        return {"renewed": ok, "lease_id": lease_id}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=False, idempotentHint=True))
    def runtime_release_lease(lease_id: str) -> dict:
        """Release a previously acquired lease."""
        _require_current_token(SCOPE_LEASE, _TOOL_LEVELS["runtime_release_lease"])
        _rate("release_lease")
        ok = store.release_lease(lease_id=lease_id, owner=ctx.lease_owner)
        return {"released": ok, "lease_id": lease_id}

    # ── Execute tool ─────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(destructiveHint=True))
    def runtime_run_command(command_id: str, lease_id: str) -> dict:
        """Run a registered command under an active lease.

        Returns eligibility, return code, and truncated digest — never raw
        stdout or stderr.
        """
        # Per-operation auth: re-read token so max_autonomy_level is current.
        current_token = _require_current_token(SCOPE_EXECUTE, _TOOL_LEVELS["runtime_run_command"])
        # Classify the specific command and enforce the autonomy ceiling.
        # The effective level is max(tool base L3, command classification).
        try:
            classification = store.classify_runtime_action(command_id)
            effective_level = classification.autonomy_level
        except Exception:
            effective_level = _TOOL_LEVELS["runtime_run_command"]
        if _level_rank(effective_level) < _level_rank(_TOOL_LEVELS["runtime_run_command"]):
            effective_level = _TOOL_LEVELS["runtime_run_command"]
        try:
            _check_level(effective_level, current_token.max_autonomy_level)
        except PermissionError:
            store.increment_policy_counter("mcp_level_blocked")
            raise
        _rate("run")
        # Verify lease is owned by this agent before delegating to store.
        leases = store.list_leases(observation_id=None)
        owned = any(
            l.lease_id == lease_id and l.owner == ctx.lease_owner and l.status == "active"
            for l in leases
        )
        if not owned:
            raise PermissionError(
                f"lease {lease_id!r} is not active or not owned by {ctx.lease_owner!r}"
            )
        result = store.run_command(command_id=command_id, lease_id=lease_id)
        d = _safe_dc(result)
        return d

    # ── Trace tools ──────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_trace_list(operation: str | None = None, limit: int = 20) -> dict:
        """List runtime traces, optionally filtered by operation."""
        _require_current_token(SCOPE_TRACE, _TOOL_LEVELS["runtime_trace_list"])
        _rate("trace_list")
        traces = store.list_traces(operation=operation, limit=limit)
        return {
            "traces": [_safe_dc(t) for t in traces],
            "not_permission": True,
        }

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_trace_show(trace_id: str) -> dict:
        """Return full detail for one trace."""
        _require_current_token(SCOPE_TRACE, _TOOL_LEVELS["runtime_trace_show"])
        _rate("trace_show")
        trace = store.read_trace(trace_id)
        if trace is None:
            return {"trace": None, "not_permission": True}
        return {"trace": _safe_dc(trace), "not_permission": True}

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_trace_export(trace_id: str, format: str = "json") -> dict:
        """Export a trace in the specified format (json or text)."""
        _require_current_token(SCOPE_TRACE, _TOOL_LEVELS["runtime_trace_export"])
        _rate("trace_export")
        exported = store.export_trace(trace_id, format=format)
        return {"export": exported, "not_permission": True}

    # ── Metrics tool ─────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_metrics() -> dict:
        """Return aggregate runtime metrics."""
        _require_current_token(SCOPE_METRICS, _TOOL_LEVELS["runtime_metrics"])
        _rate("metrics")
        metrics = store.read_metrics()
        d = _safe_dc(metrics)
        d["not_permission"] = True
        return d

    # ── Replay tool ──────────────────────────────────────────────────────────

    @app.tool(annotations=ToolAnnotations(readOnlyHint=True))
    def runtime_replay_scenario(scenario_path: str) -> dict:
        """Replay a stored scenario file for diagnostics (read-only)."""
        _require_current_token(SCOPE_REPLAY, _TOOL_LEVELS["runtime_replay_scenario"])
        _rate("replay")
        resolved = _check_replay_path_scope(store.root, scenario_path)
        result = store.replay_scenario(resolved)
        d = _safe_dc(result)
        d["not_permission"] = True
        return d

    return app


def run_stdio(store: RuntimeManagerStore) -> None:
    """Authenticate, build app, and start STDIO loop. Exits on auth failure."""
    try:
        app = build_app(store)
    except AuthError as exc:
        print(f"[cerebro mcp-stdio] auth error: {exc}", file=sys.stderr)
        sys.exit(1)

    app.run(transport="stdio")
