# Formal Resume Trigger — Runtime Manager Phase 10

**Status:** active
**Authorized boundary:** `D:\projetos_cli\ambiente_cerebro\cerebro\`
**Issued:** 2026-05-09
**Gate required before close:** python -m pytest -q passes with 0 failures

---

## Scope

Phase 10 is **local-only hardening**.  It does NOT introduce HTTP, OAuth, TLS,
Streamable HTTP, SSE, Temporal, LangGraph, OpenAI Agents SDK, cloud transport,
or the observation-center SQLite ledger migration.  T20–T22 (HTTP/OAuth/TLS)
remain open threats for a future external-transport phase.

---

## Authorized deliverables

### 1 — Local Stress Lab

- `experiments/runtime_manager_stress_lab/` — deterministic, short scenarios:
  lease race, rate limit concurrency, token revoke/expire mid-session,
  expired-lease reclaim, replay path guard, reads under load, DB busy contention.
- Results carry `stress_pass_is_not_permission = True` and
  `authority = "advisory/local stress only"`.
- All scenarios run inside the normal pytest gate (no long sleeps).

### 2 — Integrity Check Local

- `RuntimeIntegrityReport` dataclass and `check_integrity()` method in the store.
- CLI: `runtime-manager integrity check [--format text|json]`.
- Checks: orphan trace events, incomplete old traces, expired-but-active leases,
  expired-but-active tokens, stale rate buckets, evidence without expected trace,
  policy-counter plausibility, not-permission markers on relevant rows.
- The integrity report is diagnostic only; it is not permission.

### 3 — Known Polish

- Remove dead code `_max_level()` from `core/runtime_manager_policy.py`.
- Fix `mcp_level_blocked` counter: increment for ALL MCP tools blocked by the
  token ceiling, not just `runtime_run_command`.
- Standardize stable error codes in CLI/MCP error outputs:
  `lease_contention`, `lease_owner_mismatch`, `token_revoked_mid_session`,
  `rate_limited`, `autonomy_level_blocked`, `replay_path_out_of_scope`.

### 4 — Architecture and Packaging

- Add `adapters.runtime_manager_mcp_stdio` and `adapters.runtime_manager_local_agent`
  to `[tool.setuptools].packages` in `pyproject.toml`.
- Add architecture tests verifying no HTTP/socket/listener in adapters, MCP STDIO
  does not write SQLite directly, adapters only call public store API, and
  `record_approval` remains unexposed via MCP.

### 5 — Phase 10 Evals

- `experiments/runtime_manager_evals/eval_phase10_hardening.py` with evaluators:
  stress-pass not-permission, integrity-pass not-permission, metrics not authority,
  trace retains no token/stdout/stderr, replay path guard, L4 still blocked,
  token-revoked blocks next call, level-block counter covers all tools.
- Update `experiments/runtime_manager_evals/tests/test_evals.py`.

---

## Prohibited in this trigger

- HTTP MCP, OAuth server, TLS, SSE, Streamable HTTP, remote transport.
- Temporal, LangGraph, OpenAI Agents SDK, cloud.
- SQLite ledger migration for the observation center.
- Schema changes unless a genuine bug requires one (stop and report first).
- `--no-verify` or bypassing existing safety checks.
- Any output that leaks token, stdout, stderr, argv, secret, or out-of-scope path.

---

## Done when

All deliverables above are complete, `python -m pytest -q` passes with 0
failures, and Phase 10 observation is archived as resolved.
