# Runtime Manager MCP Threat Model

**Status:** Phase 9 -- Per-operation auth and cross-process concurrency hardening delivered
**Authority:** docs-only; not a runtime gate

---

## Purpose

This document captures the threat model that any MCP adapter for the
Runtime Manager must address before it is activated. It is written in
advance to make the threat surface explicit before code exists.

## Threat Surface

### T1 -- Tool call injection
An LLM agent receiving malicious content from the environment might call
runtime-manager tools (run_command, record_approval, raise_stop_condition)
on behalf of an attacker.

Mitigation: approval_requirement=required for all sensitive commands.
Human approval must be recorded before run_command succeeds.
The MCP adapter must NOT auto-approve based on LLM output.

### T2 -- argv injection
An attacker might supply crafted argv through an MCP tool call.

Mitigation: argv is ALWAYS sourced from command_registry in TOML,
never from tool call inputs. MCP tool inputs may only supply
command_id (looked up in registry) and subject_id.

### T3 -- Secret exfiltration via traces
An attacker might use the trace/export surfaces to extract
stdout/stderr containing secrets from previous runs.

Mitigation: Traces are sanitized at write time. No stdout, stderr,
or raw argv is stored in runtime_traces. export_trace never
returns execution output.

### T4 -- Replay result misuse
An agent might treat replay_pass as execution approval.

Mitigation: Every replay result carries replay_pass_is_not_truth=True
and authority field. MCP adapter must not convert replay pass to approval.

### T5 -- Stop condition bypass
An agent might resolve stop conditions without human authorization.

Mitigation: resolve_stop_condition requires a valid condition_id.
The MCP adapter must require approval_requirement=required for any
stop-condition resolution that affects safety-critical observations.

### T6 -- Lease escalation
An agent might acquire leases for observations it should not own.

Mitigation: acquire_lease is scoped per observation_id. The MCP adapter
must validate that the requesting agent owns the observation scope.

## Phase 6 -- Tested Mitigations (LocalAgentAdapter Pilot)

The following mitigations were implemented and tested in Phase 6:

### Rate Limiting (T1, T6)

- `LocalRateLimiter`: sliding-window per `(agent_id, operation)`.
  Mutate ops ≤ 10/min; read ops ≤ 60/min.
- On excess: adapter raises `AdapterError(code="rate_limited")` before
  calling the store. `adapter_rate_limited` counter incremented.
- Tested: `test_rate_limit_blocks_excess_mutations`,
  `test_rate_limit_allows_read_ops`.

### Agent Identity (T1, T6)

- `AgentContext(agent_id, agent_role, session_id)` required on every call.
- `agent_id` and `session_id` validated: 1–128 chars of `[a-zA-Z0-9_:.-]`.
- Lease owner derived as `f"adapter:{agent_id}:{session_id}"`.
  Owner is bound to the session; cannot be forged by a different session.
- Tested: `test_agent_context_validates_id`, `test_lease_owner_is_derived`.

### Lease Ownership (T5, T6)

- `release_lease` / `heartbeat_lease` verify owner matches before calling store.
- Mutating operations (`run`, `record_approval`, etc.) verify active lease
  held by this adapter session before calling store.
- On failure: `AdapterError(code="lease_owner_mismatch")` or
  `AdapterError(code="lease_required")` raised; store not reached.
- Tested: `test_wrong_owner_cannot_release_lease`,
  `test_mutation_without_lease_is_blocked`.

### Prompt/Tool Injection (T1)

- Adapter never passes LLM-supplied argv to store; only `command_id`.
- `eval_adapter_no_argv_acceptance` checks source for forbidden `argv` references.
- `approval_requirement=required` in `command_registry` enforces pre-approval.

### Replay Laundering (T4)

- Adapter never reads replay result to authorize `run_command`.
- Every replay result carries `authority` field disclaiming permission.
- `eval_replay_result_is_not_permission` checks authority field.
- Tested: `test_replay_result_authority_field`.

### Trace Exfiltration (T3)

- Store sanitizes traces at write time; no stdout/stderr/argv in traces.
- `eval_no_secret_in_trace_export` checks exported trace for secret tokens.
- Tested: `test_trace_export_no_secrets`.

## Phase 7 -- Delivered Mitigations (STDIO server)

### T7 -- Token credential leak
Raw token never persisted; only its SHA-256 hash is stored in `adapter_tokens`.
`AdapterToken` dataclass has no `token_hash` field -- hash cannot leak via
tool output or `_safe_dc`. Token never appears in operation traces, metrics,
or trace exports.

### T8 -- Identity spoofing via client input
`AgentContext` is derived exclusively from the authenticated `AdapterToken`
at startup. No tool accepts `agent_id`, `token`, `password`, `secret`, or
`identity` parameters. MCP client cannot override identity.

### T9 -- Lease hijacking across agents
`runtime_run_command` performs an adapter-layer ownership check
(`l.owner == ctx.lease_owner`) before calling the store. A client with
`runtime:execute` scope cannot run commands under a lease it does not own,
even if it learns another agent's `lease_id`.

### T10 -- Replay path traversal
`runtime_replay_scenario` resolves the caller-supplied path against
`store.root` and rejects any result that escapes that directory.
Absolute paths and `..` traversal are blocked before `store.replay_scenario`
is called.

### T11 -- Unlimited rate abuse across restarts
Rate buckets persisted in `adapter_rate_buckets` (SQLite). `PersistentRateLimiter`
enforces the same 10 mutate / 60 read per minute across process restarts.

## Phase 8 -- Delivered Mitigations (Autonomy Calibration)

### T12 -- Level escalation via low-friction MCP tool call
An agent with a read-only token might call `runtime_run_command` (L3) and
elevate its effective autonomy beyond what the token permits.

Mitigation: each adapter token carries `max_autonomy_level`
(default: `L3_runtime_mutation`).  Every MCP tool checks the operation level
before any store call; a level exceeding the token ceiling raises `PermissionError`.
`issue_adapter_token` accepts `max_autonomy_level`; tokens can only be issued at or
below L3 (L4 is not executable via MCP).

### T13 -- L4 action executed through MCP
An agent or attacker might attempt to run a command classified as
`L4_external_high_risk` through the STDIO MCP server.

Mitigation: L4 is unconditionally blocked in `runtime_run_command` before any
lease, approval, or store check.  No token `max_autonomy_level` value unlocks L4.
The `eval_mcp_safety` and `eval_autonomy_levels` evaluators verify this invariant.

### T14 -- Risk level downgrade via field omission
A command registered without the new Phase 8 fields (`risk_level_override`,
`data_sensitivity`, `requires_human_decision`, `target_scope`) might be treated
as low-risk when it is not.

Mitigation: schema v15 adds these columns with safe defaults (`''`, `'none'`,
`0`, `'local'`).  Unregistered commands default to L3 (unknown side-effect class
falls back to L3_runtime_mutation), not L0.  Classification is based on what is
present, not what is absent; absence escalates, not de-escalates.

### T15 -- Override reduces effective level
A policy consumer supplies `risk_level_override` pointing to a lower level than
the base classification, reducing friction for a dangerous action.

Mitigation: `classify_action()` takes `max(base, elevators, override)`.
The override value is compared against the already-computed effective level; it
is accepted only if it is strictly higher.  The policy module tests this with
`test_override_only_increases_level`.

---

## Phase 9 -- Delivered Mitigations (Concurrency and Per-Operation Auth)

### T16 -- Stale token grants access after revocation (T8 extension)

STDIO Phase 7 authenticated the token once at server startup.  A revoked token
could not stop an active session; the cached `AdapterToken` stayed valid for the
process lifetime.

Mitigation (Phase 9): `build_app` captures the raw env token and passes it to a
`_require_current_token(scope, level)` closure that calls
`store.authenticate_adapter_token(raw_env_token)` on **every tool call**.
A token revoked or expired between calls is rejected with `PermissionError`
(code: `token_revoked_mid_session`) before any store mutation.
Scopes and `max_autonomy_level` are read from the freshly-authenticated record,
not a startup snapshot.
Tested by `TestTokenRevokedMidSession` (cross-process, real DB).

### T17 -- Concurrent lease acquisition race

Two or more agents/processes race to acquire the same observation lease,
potentially both succeeding and issuing conflicting mutations.

Mitigation (Phase 9): `acquire_lease` already used a SQLite UNIQUE partial index
on `(observation_id, status='active')` to enforce single-flight.  Phase 9 adds
`code="lease_contention"` to the raised `RuntimeManagerStoreError` for stable
diagnostics and tests with 8 concurrent processes on the same observation ID
(exactly 1 succeeds; all others receive `lease_contention`).
Tested by `TestConcurrentLeaseAcquisition`.

### T18 -- Rate limit bypass under concurrent write pressure

Multiple concurrent writers could collectively bypass the per-minute rate limit
if the increment and read are not atomic.

Mitigation (Phase 9): `check_and_increment_rate_limit` uses `BEGIN IMMEDIATE`
(write lock claimed before first read) so the increment and count-read happen
within a single exclusive transaction.  SQLite's serialized write model prevents
two processes from both observing a count under the limit simultaneously.
Tested by `TestPersistentRateLimitConcurrency`.

### T19 -- Wrong-owner lease release or heartbeat succeeds

A concurrent agent learns a `lease_id` and releases or heartbeats a lease it
does not own.

Mitigation (Phase 9): `release_lease` and `heartbeat_lease` continue to return
`False` (no-op) when the owner does not match; Phase 9 adds
`code="lease_owner_mismatch"` to the trace event for stable diagnostics.
Cross-process tests verify that wrong-owner operations always return False and
leave the original lease active.
Tested by `TestWrongOwnerLeaseOps`.

---

## Future External Transport Open Threats (T20–T22)

These threats are out of scope for Phase 10 (local-only hardening) and MUST be
addressed before any HTTP or multi-connection transport is introduced.

### T20 -- TLS absent on HTTP transport
Any HTTP/WebSocket transport must add TLS termination before accepting remote
connections.  Plaintext HTTP exposes credentials and payloads in transit.

### T21 -- No OAuth server for multi-client auth
HTTP transport requires an OAuth token endpoint so clients can issue, rotate,
and revoke tokens without direct DB access.

### T22 -- Multi-client connection fan-out without session isolation
HTTP connections from different clients sharing the same agent_id can interfere
with each other's leases, rate buckets, and audit trails.  Session isolation
and per-connection `session_id` scoping must be specified before HTTP is active.

## Activation Requirement for Future External Transport Phase (T20–T22)

These requirements must be satisfied before any HTTP/OAuth transport is activated.
They are explicitly out of scope for Phase 10 (local-only hardening).

1. Per-request `authenticate_adapter_token` in request middleware.
2. TLS termination and OAuth token endpoint.
3. Lease contention policy for concurrent sessions.
4. JSON-RPC input schemas rejecting extra keys and validating types.
5. Formal human trigger required for the external-transport phase.
