# Formal Resume Trigger - Runtime Manager Phase 2

## Status

- status: consumed
- date: 2026-05-08
- opened: 2026-05-08
- closed: 2026-05-08
- authority: human approved continuation in chat on 2026-05-08; implementation may begin
- queue item: `runtime-manager-phase-2`
- predecessor: `runtime-manager-phase-1` (resolved 2026-05-08)
- primary decision: add constrained command executor behind core APIs only after Phase 1 gates are stable

## Decision

Phase 1 delivered the read-only local control plane: `runtime.db` schema v6,
`sync_observation_center()`, `read_status()`, `read_next()`, CLI
`runtime-manager sync/status/next`, gate diagnostics with severity/blocking,
selection audit, lease expiry classification, replay diagnostics, event
vocabulary ordering, and a test suite at 1887 passed / 0 failures / 6 skipped.

Phase 2 adds constrained command execution behind a `command_registry` surface
in `core/`. Execution must be gate-controlled, fingerprinted, time-bounded,
output-bounded, evidence-capturing, and rollback-aware. Free execution is still
prohibited; every command must pass the full readiness check from Phase 1 before
being eligible to run.

## Authority Order

```text
AGENTS.md
-> FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_2.md (when approved)
-> docs/operations/observation_center.toml
-> docs/operations/RUNTIME_MANAGER_CONTRACT.md
-> core-owned runtime.db APIs
-> SYSTEM_STATE.md and OPPORTUNITY_MAP.md as projections
```

## Allowed Scope (when trigger is approved)

Phase 2 may proceed in explicit slices, each requiring gate-green before the
next:

1. `command_registry` schema and core API: register commands with id, argv
   prefix, path scope, side effect class, network flag, timeout, output budget,
   sensitive output policy, approval requirement, rollback expectation;
2. enforcement layer: `core/` gate that verifies command_registry policy before
   any execution path is reached;
3. approval fingerprint: an approval record must carry an action fingerprint
   matching the command being executed; stale or drifted fingerprints are
   rejected;
4. evidence capture: every execution attempt emits an event and, on completion,
   captures stdout/stderr artifacts within the output budget;
5. rollback policy: each command declares its rollback class; rollback records
   are stored for post-hoc audit;
6. CLI surface: `runtime-manager run` (or equivalent) that routes through the
   full enforcement chain, never bypassing core gates;
7. tests proving that free execution without registry, approval fingerprint, path
   scope, timeout, or output budget is rejected before any subprocess is started.

Allowed implementation areas only when the slice says so:

- `core/`
- `cli/`
- `tests/`
- `docs/reference/`
- `docs/operations/`

## Explicit Non-Scope

Phase 2 must not:

- allow free arbitrary commands without `command_registry` registration;
- import Temporal, LangGraph, MCP, OpenTelemetry, OpenAI Agents SDK, or
  Cloudflare Agents SDK;
- expose external adapters or cloud APIs;
- mutate third-party targets;
- bypass the Phase 1 gate (readiness check still runs before execution);
- let Markdown or generated reports become live authority;
- create a second canonical runtime store;
- reuse approval records across different action fingerprints.

## Execution Policy

Every execution path in Phase 2 must be gated by:

- **Path scope**: the command's working directory and allowed file access must
  be declared in `command_registry` and enforced before subprocess creation;
- **Timeout**: a declared maximum wall-clock time; the subprocess is killed on
  expiry with a visible `command timed out` status;
- **Output budget**: stdout/stderr artifact text is bounded to `65536` UTF-8
  bytes with a truncation marker; unbounded output is not persisted;
- **Approval fingerprint**: an approval record must match the specific command
  id, argv hash, and target scope; stale fingerprints are rejected;
- **Evidence artifact retention**: execution creates a bounded artifact entry
  linked to the work item and approval record;
- **Rollback expectation**: every command declares whether it is reversible,
  partially reversible, or irreversible; irreversible commands require a
  stronger approval class.

## Adapter Policy

External orchestration stays deferred:

- Temporal: only after long-running durable worker need is proven.
- LangGraph: only after local graph/checkpoint need is proven.
- MCP: only after local tool policy and sanitization are canonical.
- OpenTelemetry: only after local event semantics are stable.
- OpenAI/Cloudflare Agents SDK: only after worker handoff, lease, and trace
  contracts are stable.

## Acceptance Criteria

This trigger can open (and implementation can begin) only when:

- a human explicitly approves this trigger document in chat;
- `RUNTIME_MANAGER_CONTRACT.md` is updated to reflect Phase 2 scope;
- Phase 1 test suite remains green (no regressions from Phase 2 changes);
- the first Phase 2 slice is scoped to `command_registry` schema only
  (no subprocess, no execution, no adapter).

This trigger can close only when:

- `command_registry` is stable behind core APIs with all policy fields;
- the enforcement layer rejects execution without a valid registry entry;
- approval fingerprint matching is implemented and tested;
- evidence capture is bounded and linked to work items;
- rollback class is recorded for every executed command;
- CLI execution surface routes through the full enforcement chain;
- tests prove that no path bypasses the registry or approval check;
- full AGENTS-equivalent gate is green.

## Stop Conditions

Stop if:

- free execution is added before `command_registry` enforcement;
- adapter libraries enter the dependency surface;
- a target project is mutated from this repo without human approval;
- the approval fingerprint check is bypassed for any execution path;
- tests fail twice for the same enforcement contract issue;
- the trigger scope needs to expand beyond local Phase 2 executor.
