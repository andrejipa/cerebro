# Formal Resume Trigger - Runtime Manager Phase 1

## Status

- status: consumed
- date: 2026-05-08
- closed: 2026-05-08
- authority: formal boundary for local runtime-manager growth
- queue item: `runtime-manager-phase-1`
- primary decision: SQLite-backed local runtime manager, not external orchestration
- closure: All Phase 1 acceptance criteria satisfied. Contract explicit, runtime.db schema v6 implemented, CLI sync/status/next read-only, projection exports safe, all required tables structured, gate diagnostics with severity/blocking, selection audit, lease expiry, replay diagnostics, event vocabulary ordering, and test suite green (1887/0/6). Phase 2 trigger written at FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_2.md.

## Decision

Cerebro will move toward a real runtime manager through a local-first control
plane. The future canonical operational store for runtime-manager state is a
SQLite file named `runtime.db`, owned by `core/` APIs. TOML, Markdown, JSON,
and advisory experiment outputs may configure, document, export, replay, or
project runtime state, but they must not become competing live authorities.

Phase 1 implements scheduler, gates, status, and explanation before execution.
It must answer:

- what is the current runtime state;
- what work item is eligible;
- why an item is blocked;
- what evidence, approval, dependency, tool policy, or validation is missing;
- which source is canonical for the answer.

## Authority Order

The effective order for this front is:

```text
AGENTS.md
-> FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_1.md
-> docs/operations/observation_center.toml
-> docs/operations/RUNTIME_MANAGER_CONTRACT.md
-> core-owned runtime.db APIs, when implemented
-> SYSTEM_STATE.md and OPPORTUNITY_MAP.md as projections
```

Until a SQLite-backed runtime store exists, `observation_center.toml` remains
the machine-primary queue. After promotion, Markdown remains projection and
TOML remains migration/config evidence unless a later trigger says otherwise.

## Allowed Scope

Phase 1 may proceed in explicit slices:

1. docs-only contract and trigger opening;
2. schema/read-model design for `runtime.db`;
3. minimal SQLite store behind `core/` APIs;
4. import/projection from the current observation center;
5. read-only scheduler/status commands such as `runtime-status` and `next`;
6. tests proving single authority, blocking behavior, replay, and projection.

Allowed implementation areas only when the slice says so:

- `core/`
- `cli/`
- `tests/`
- `docs/reference/`
- `docs/operations/`

## Explicit Non-Scope

Phase 1 must not:

- execute arbitrary commands;
- add free agent dispatch;
- import Temporal, LangGraph, MCP, OpenTelemetry, OpenAI Agents SDK, or
  Cloudflare Agents SDK;
- expose external adapters;
- mutate third-party targets;
- perform schema/migration/cloud work in target projects;
- treat advisory experiment output as permission;
- let Markdown or generated reports become live authority;
- create more than one canonical runtime store.

## Runtime Store Direction

`runtime.db` should eventually contain:

- observations;
- observation dependencies;
- decisions and decision revisions;
- approvals;
- evidence records;
- tool/command manifest entries;
- round runs;
- round events;
- leases/single-flight records;
- projections/export metadata.

The first implementation may be intentionally smaller, but it must not paint
the project into a second-source-of-truth corner.

## Execution Policy

Phase 1 starts read-only for runtime actions. It can compute and explain
eligibility but cannot run mutating work. A later phase may add constrained
execution only through registered commands with:

- path scope;
- declared side effect;
- timeout;
- output budget;
- approval fingerprint;
- evidence artifact retention;
- rollback expectation.

## Adapter Policy

External orchestration stays deferred:

- Temporal: only after long-running durable worker need is proven.
- LangGraph: only after local graph/checkpoint need is proven.
- MCP: only after local tool policy and sanitization are canonical.
- OpenTelemetry: only after local event semantics are stable.
- OpenAI/Cloudflare Agents SDK: only after worker handoff, lease, and trace
  contracts are stable.

## Acceptance Criteria

This trigger can close only when:

- `RUNTIME_MANAGER_CONTRACT.md` is explicit and aligned with the queue item;
- a first scoped implementation decision exists for `runtime.db`;
- tests prove no authority split between DB/TOML/Markdown/projections;
- read-only runtime status/next behavior is either implemented or queued as the
  immediate next scoped slice;
- full AGENTS-equivalent gate is green;
- `SYSTEM_STATE.md` and `OPPORTUNITY_MAP.md` mirror the result without gaining
  authority.

## Stop Conditions

Stop if:

- a second source of truth appears;
- execution is added before scheduler/gates/status;
- adapter libraries enter the dependency surface;
- a target project is mutated from this repo;
- tests fail twice for the same runtime contract issue;
- the trigger scope needs to expand beyond local runtime-manager Phase 1.
