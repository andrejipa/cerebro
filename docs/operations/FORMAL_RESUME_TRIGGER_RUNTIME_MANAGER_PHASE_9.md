# Formal Resume Trigger — Runtime Manager Phase 9

**Status:** active
**Authorized boundary:** `D:\projetos_cli\ambiente_cerebro\cerebro\`
**Issued:** 2026-05-09
**Gate required before close:** python -m pytest -q passes with 0 failures

---

## Scope

Phase 9 delivers **multiagent cross-process concurrency hardening** and
**per-operation auth readiness** for the STDIO transport.  It does NOT
introduce HTTP, OAuth, TLS, Streamable HTTP, SSE, Temporal, LangGraph, or
OpenAI Agents SDK.  Those belong to Phase 10.

---

## Authorized deliverables

### 1 — Per-operation token re-authentication (STDIO)

- `adapters/runtime_manager_mcp_stdio/auth.py`: expose `load_raw_token_from_env()`.
- `adapters/runtime_manager_mcp_stdio/server.py`: refactor `build_app` so that
  every tool call re-authenticates via `store.authenticate_adapter_token(raw_env_token)`.
- A revoked or expired token blocks the next tool call even if the server process
  is already running.
- Scopes and `max_autonomy_level` are read from the freshly-authenticated token,
  not from a stale cached record.
- The raw token is never accepted from tool inputs or CLI args.
- The raw token never appears in trace, event, or tool output payloads.

### 2 — Stable lease contention diagnostic codes

- `core/runtime_manager_store.py`: `RuntimeManagerStoreError` gains optional `code`
  attribute.
- `acquire_lease` raises with `code="lease_contention"` on UNIQUE constraint violation.
- `release_lease` and `heartbeat_lease` trace with owner-mismatch reason when
  the operation is a noop due to wrong owner.
- Stable codes: `lease_contention`, `lease_owner_mismatch`, `lease_expired_reclaimed`,
  `token_revoked_mid_session`.

### 3 — Rate limit atomic hardening

- `check_and_increment_rate_limit` uses `BEGIN IMMEDIATE` to make the
  increment-then-read atomic under concurrent write pressure.
- Tests verify that concurrent writers cannot collectively bypass the limit.

### 4 — Cross-process concurrency tests

- `tests/test_runtime_manager_concurrency.py` with multiprocessing workers.
- Scenarios: 8-process lease race (exactly 1 success), wrong-owner lease ops,
  persistent rate limit under concurrency, token revoked mid-session,
  token expired mid-session, reclaim leaves ≤ 1 active lease.

### 5 — MCP STDIO hardening helper

- `_require_current_token(required_scope, operation_level)` closure in `build_app`
  centralizes token re-authentication + scope check + level check.
- `runtime_run_command` uses the freshly-read `max_autonomy_level` for the
  command classification check.
- `record_approval` remains NOT exposed via MCP.
- L4 remains blocked unconditionally.

### 6 — Phase 9 evals

- `experiments/runtime_manager_evals/eval_phase9_concurrency_auth.py` with 6
  evaluators: per-call auth existence, no-HTTP Phase 9 invariant, persistent
  rate limit not in-memory, lease contention SQLite-backed, token revocation
  mid-session, no raw token in outputs.

---

## Prohibited in this trigger

- HTTP MCP, OAuth server, TLS, SSE, Streamable HTTP.
- Temporal, LangGraph, OpenAI Agents SDK.
- `record_approval` exposed via MCP.
- Raw argv accepted from any input.
- Raw token persisted or emitted in any output.
- `--no-verify` or bypassing existing safety checks.

---

## Done when

All items above are delivered and `python -m pytest -q` passes with 0 failures
from the authorized boundary.  Phase 9 observation is archived as resolved.
