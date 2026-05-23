# Formal Resume Trigger: Observation Center SQLite Ledger

## Status
- Trigger id: `FORMAL_RESUME_TRIGGER_OBSERVATION_CENTER_SQLITE_LEDGER_2026-05-23`
- Opened: 2026-05-23
- Operator decision: implement the five-point publication follow-up with a controlled SQLite migration.

## Scope
- Reconcile post-merge operational docs for PR #1 / merge `71d8be3f`.
- Clarify `runtime-manager status` and `next` output when the runtime gate is blocked or stale.
- Split CI into base and optional MCP gates.
- Add a short operational navigation index.
- Promote the local observation center from TOML import authority to `runtime.db` SQLite primary authority with deterministic TOML export/bootstrap compatibility.

## Boundaries
- Local repository only.
- No target-project mutation.
- No HTTP/OAuth/TLS, cloud runtime, external scheduler, automatic execution loop, Temporal, LangGraph, OpenAI Agents SDK, or Cloudflare Agents SDK.
- MCP remains optional and is validated only through its explicit gate.
- `runtime.db` remains local and ignored; no live database file is committed.

## Stop Conditions
- Stop if `python -m tests.gate_runner --profile base` fails and the cause is not understood.
- Stop if SQLite promotion would require destructive migration, opaque data loss, or external service authority.
- Stop if repeated promotion cannot fail closed.
- Stop if implementation pressure expands beyond the five scoped points.

## Completion Evidence
- `python -m tests.gate_runner --profile base`
- `python -m tests.gate_runner --profile mcp`
- `python -m cli.main runtime-manager status`
- `python -m cli.main runtime-manager integrity check`
- `git diff --check`
