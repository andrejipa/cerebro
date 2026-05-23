# FORMAL RESUME TRIGGER -- Runtime Manager Phase 7

**Status:** consumed
**Consumed at:** 2026-05-08
**Authorized by:** human instruction 2026-05-08

---

## What This Trigger Authorized

Phase 7: MCP STDIO real + token identity persistente + rate limit persistente.

Activate the first real MCP server (STDIO-only, no HTTP) backed by the
LocalAgentAdapter from Phase 6.  Token identity is derived from store-persisted
credentials, not self-reported by the client.  Rate limits are persisted in
SQLite, surviving process restarts.

## Scope

1. **Schema v14** -- two new tables:
   - `adapter_tokens` -- hashed credentials: `token_id`, `agent_id`,
     `agent_role`, `scopes_json`, `token_hash` (SHA-256), `status`,
     `issued_at`, `expires_at`, `revoked_at`.
   - `adapter_rate_buckets` -- persistent sliding window counts:
     `bucket_key` (PK = `agent_id:op:window_minute`), `count`,
     `window_start`.

2. **Store token APIs** --
   - `issue_adapter_token(agent_id, agent_role, scopes, ttl_seconds)`
     → `(AdapterToken, raw_token_str)` -- raw token visible once only.
   - `revoke_adapter_token(token_id)` → bool.
   - `authenticate_adapter_token(raw_token)` → `AdapterToken | None`.

3. **Persistent rate limit** -- `check_and_increment_rate_limit(agent_id,
   operation)` in store; adapters use `PersistentRateLimiter` wrapper;
   `LocalRateLimiter` retained for tests that need clock injection.

4. **MCP STDIO server** -- `adapters/runtime_manager_mcp_stdio/`:
   - `FastMCP` server using `mcp>=1.27,<2`.
   - Token from env var `CEREBRO_RUNTIME_MCP_TOKEN` (never CLI arg).
   - `AgentContext` derived from authenticated token, never from client input.
   - Scopes enforced per tool: `runtime:read`, `runtime:lease`,
     `runtime:execute`, `runtime:trace`, `runtime:metrics`,
     `runtime:replay`.
   - No HTTP, no listener, no socket, no network.
   - Tools: `runtime_status`, `runtime_next`, `runtime_check_command`,
     `runtime_acquire_lease`, `runtime_heartbeat_lease`,
     `runtime_release_lease`, `runtime_run_command`,
     `runtime_trace_list`, `runtime_trace_show`, `runtime_trace_export`,
     `runtime_metrics`, `runtime_replay_scenario`.
   - `record_approval` NOT exposed via MCP (approval remains CLI/human).
   - All tools reject extra fields.
   - No tool accepts `argv`, `command`, `shell`, `cwd`, `env`, `token`,
     `password`, `secret`, `stdout`, `stderr`.
   - Tool outputs never include raw stdout/stderr.
   - Trace/replay/metrics always carry `not_permission=true`.
   - Read tools annotated `readOnlyHint=True`.
   - `runtime_run_command` annotated `destructiveHint=True`.

5. **CLI entrypoint** -- `cerebro runtime-manager mcp-stdio` starts the
   STDIO server; server exits if `CEREBRO_RUNTIME_MCP_TOKEN` is absent
   or token does not authenticate.

6. **MCP safety evals** -- `experiments/runtime_manager_evals/eval_mcp_safety.py`
   covering: no HTTP/socket, no SQL direct, no token in trace, no raw argv,
   no approval tool, scopes enforced, only `mcp` added as external SDK.

## Boundary

- STDIO-only transport; no Streamable HTTP, no OAuth server, no TLS.
- `mcp>=1.27,<2` is the only new external dependency.
- HTTP/OAuth/SSRF hardening deferred to Phase 8 (requires new trigger).
- No OpenAI Agents SDK, Temporal, LangGraph, Cloudflare Agents SDK.
- Raw token never stored; never appears in traces, metrics, logs, or test output.
- `record_approval` not exposed via MCP tool.

## Evidence of Completion

- Gate: 2175 → ≥ 2240 passed (new token + MCP + eval tests).
- `adapters/runtime_manager_mcp_stdio/` importable and in-process tested.
- `eval_mcp_safety` passes in `experiments/runtime_manager_evals/tests/test_evals.py`.
- `runtime-manager-phase-7` archived in `observation_center_archive.toml`.
