# Integration Surface

This document defines the safe boundary for future integrations.

## Purpose

An integration is an external consumer that connects the core to another tool, interface, or transport without gaining authority over state.

## Behavior Taxonomy

Use the same three external shapes everywhere else in the project:

- `export`: read-only rendering of canonical state
- `analysis`: read-only processing of canonical state into a derived output
- `integration`: orchestration outside the runtime that consumes public commands or exports

Separately, the current project also allows a narrower assistive-discovery shape for initial bootstrap only:

- `assistive discovery`: heuristic shortlist generation over project-tree paths and filenames with no authority over runtime state or canonical context

These are consumer shapes only. None of them may change core authority or become a new source of truth.

## Allowed Inputs

Future integrations may consume only:

- CLI commands that already exist
- public `core` API exports
- read-only `StateStore` methods such as `read_snapshot()` and `has_active_session()`
- read models returned by the public API

Current assistive discovery such as `bootstrap-scan` may additionally inspect project-tree paths and filenames outside the canonical snapshot, but only to suggest candidates for explicit human review.

## Forbidden Influence

Future integrations may not:

- write inside `.cerebro/`
- read runtime JSON directly
- change validation semantics
- alter `analyze` behavior
- redefine session policy
- infer missing context
- create a second source of truth

## Safe Shapes

Safe integration shapes include:

- exporters to external files or transports
- dashboards derived from canonical state
- synchronization of derived outputs to external systems
- local bridges that remain disposable and non-authoritative

## Automation Bridges

An automation bridge is a narrow `integration` shape that reduces mechanical handoff between a human coordinator and an external executor such as Codex.

Safe automation bridges may:

- package an explicit task, context list, and approval mode into a disposable run directory
- invoke external execution through supported public surfaces such as `codex exec`
- capture JSONL events, structured final outputs, and human-readable logs outside `.cerebro/`
- require explicit human approval before any write-capable or core-sensitive step continues

Automation bridges must not:

- persist hidden project memory as a second source of truth
- register `sources` automatically
- call `import-context` automatically
- treat executor logs as canonical project state
- bypass `analyze`, `validate`, or the existing runtime entrypoints

Daily-use rule for automation bridges:

- use them only for mechanical execution, repeated audit runs, and explicit external task packaging
- do not use them to decide canonical context, select `sources`, interpret project truth, or reopen runtime decisions
- after every meaningful round, return to Cerebro through the normal `checkpoint` and `analyze` flow before treating anything as operational continuity
- treat every bridge output as disposable, non-canonical execution residue

Disposable automation-bridge implementations should stay outside tracked product code while the workflow is still evolving. `_local/` is the default incubation area for that kind of bridge.

Allowed future `analysis` outside the runtime may:

- summarize, count, group, compare, or reformat canonical fields
- report on persisted validation metadata
- combine existing public outputs without becoming authority

Forbidden future `analysis` may not:

- infer missing context, intent, or alignment
- inspect source bodies or arbitrary project files
- recommend or decide on behalf of the runtime
- reopen validation or reinterpret canonical failure states

`has_active_session()` reports session-file presence only. It does not validate session contents and must not be treated as a second runtime gate.

Current repository convention:

- tracked code under `extensions/` stays limited to Python modules and Markdown documentation
- wrappers, launchers, and executable helpers stay outside `extensions/` unless the architecture changes explicitly
- CLI command names stay canonical unless an explicit architecture decision authorizes aliases

## Unsafe Shapes

Unsafe integration shapes include:

- webhooks or daemons that mutate runtime state outside `StateStore`
- adapters that treat external acknowledgements as core truth
- tools that reopen validation logic or checkpoint semantics
- integrations that read arbitrary project files outside registered sources

## Failsafe

If an integration design needs new authority over state, validation, `analyze`, session policy, or schema, stop and resolve that at the architecture level before implementation.

Any new or changed integration must add proportional adversarial and regression coverage for the public behavior it introduces.
