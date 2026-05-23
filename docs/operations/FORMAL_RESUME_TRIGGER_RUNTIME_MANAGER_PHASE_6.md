# FORMAL RESUME TRIGGER -- Runtime Manager Phase 6

**Status:** consumed
**Consumed at:** 2026-05-08
**Authorized by:** human instruction 2026-05-08

---

## What This Trigger Authorized

Phase 6: Adapter piloto local + segurança + evals.

Transform the Runtime Manager from "auditable local runtime" into
"runtime safe to be called by external agents", starting with a local
pilot adapter.  No MCP server, no network, no SDK dependencies.

## Scope

1. **Local adapter layer** (`adapters/runtime_manager_local_agent/`) --
   wraps every public store API; enforces rate limits, agent identity,
   and lease ownership before delegating to the store.
2. **Agent identity** -- `AgentContext(agent_id, agent_role, session_id)`
   threaded through every adapter call; lease owner derived from context.
3. **Rate limit** -- deterministic in-memory sliding window per
   `agent_id + operation`; mutations limited to 10/min, reads to 60/min;
   blocks and records diagnostic trace on excess.
4. **Adapter metrics** -- `AdapterMetrics` dataclass tracking
   `adapter_calls_total`, `adapter_calls_blocked`, `adapter_rate_limited`,
   `adapter_mutations_total`, `adapter_permission_laundering_blocked`,
   `active_agent_leases`; advisory diagnostic only, never authority.
5. **Adapter safety evals** --
   `experiments/runtime_manager_evals/eval_adapter_safety.py` covering
   no-SQL-direct, no-argv, no-replay-as-permission, lease ownership
   enforcement, rate limit, secret redaction, no external SDK.
6. **MCP readiness** -- updated `RUNTIME_MANAGER_MCP_THREAT_MODEL.md`
   with tested mitigations; `adapters/runtime_manager_local_agent/fixtures/
   mcp_tool_call_shape.json` documents expected call shape without running
   a real MCP server.
7. **CONTRACT.md Phase 6** section + Phase 5 schema inconsistency fix.

## Boundary

- No MCP server, no OpenAI Agents SDK, no Temporal, no LangGraph,
  no Cloudflare Agents SDK.
- No network calls.
- Adapter must pass all public store API calls; no raw SQLite in adapter.
- Traces, metrics, and replay results are diagnostic evidence only;
  never used as execution permission.
- No argv free-form acceptance; adapter only uses registered command IDs.

## Evidence of Completion

- Gate: 2092 → ≥ 2120 passed (new adapter + eval tests).
- `adapters/runtime_manager_local_agent/` importable and tested.
- `eval_adapter_safety` in `experiments/runtime_manager_evals/`.
- `runtime-manager-phase-6` archived in `observation_center_archive.toml`.
