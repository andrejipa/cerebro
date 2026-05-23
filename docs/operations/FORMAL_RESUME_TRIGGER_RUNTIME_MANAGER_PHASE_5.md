# FORMAL RESUME TRIGGER -- Runtime Manager Phase 5

**Status:** consumed
**Consumed at:** 2026-05-08
**Authorized by:** human selection (Local forte) in session 2026-05-08

---

## What This Trigger Authorized

Phase 5: Local-forte runtime -- native traces, local metrics, deterministic replay,
and a pure-policy seam. No MCP, no Temporal, no LangGraph, no external adapters.

## Scope

1. Native trace table (runtime_traces) -- every store operation creates a
   sanitized trace row (no stdout/stderr, no raw argv, no secrets).
2. Local metrics (read_metrics()) -- counts for runs, evidence, leases,
   stop conditions, validations, traces.
3. Deterministic replay (replay_scenario()) -- JSON scenario file with
   trace_exists, metric_at_least, trace_forbids_text, and command_blocker checks.
4. Pure policy seam (core/runtime_manager_policy.py) -- decide_runtime_state
   is the first pure helper extracted from the store.
5. CLI surfaces: runtime-manager trace list/show/export,
   runtime-manager metrics, runtime-manager replay --scenario.
6. Experiments: experiments/runtime_manager_evals/ -- 18 tests passing.
7. Test fixtures: tests/fixtures/runtime_manager_scenarios/ -- 3 scenario files.

## Not In Scope

- MCP server or tool registration
- OpenAI Agents SDK / LangGraph / Temporal integration
- Any adapter that reads from or writes to external systems
- Live agent loop (Phase 6 territory)
- Cloud or network I/O

## Acceptance Criteria (met)

- [x] schema v13 with runtime_traces table
- [x] read_metrics(), list_traces(), read_trace(), export_trace()
- [x] replay_scenario() with 4 check types
- [x] CLI: trace/metrics/replay subcommands
- [x] core/runtime_manager_policy.py with decide_runtime_state
- [x] experiments/runtime_manager_evals/ -- 18 tests passing
- [x] tests/fixtures/runtime_manager_scenarios/ -- 3 fixture files
- [x] Full gate green (see CLAUDE.md for count)
- [x] RUNTIME_MANAGER_CONTRACT.md updated with Phase 5 section
- [x] RUNTIME_MANAGER_ADAPTER_CONTRACT.md written
- [x] RUNTIME_MANAGER_MCP_THREAT_MODEL.md written
