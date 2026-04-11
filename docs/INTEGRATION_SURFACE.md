# Integration Surface

This document defines the safe boundary for future integrations.

## Purpose

An integration is an external consumer that connects the core to another tool, interface, or transport without gaining authority over state.

## Behavior Taxonomy

Use the same three external shapes everywhere else in the project:

- `export`: read-only rendering of canonical state
- `analysis`: read-only processing of canonical state into a derived output
- `integration`: orchestration outside the runtime that consumes public commands or exports

These are consumer shapes only. None of them may change core authority or become a new source of truth.

## Allowed Inputs

Future integrations may consume only:

- CLI commands that already exist
- public `core` API exports
- read-only `StateStore` methods such as `read_snapshot()` and `has_active_session()`
- read models returned by the public API

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

Current repository convention:

- tracked code under `extensions/` stays limited to Python modules and Markdown documentation
- wrappers, launchers, and executable helpers stay outside `extensions/` unless the architecture changes explicitly

## Unsafe Shapes

Unsafe integration shapes include:

- webhooks or daemons that mutate runtime state outside `StateStore`
- adapters that treat external acknowledgements as core truth
- tools that reopen validation logic or checkpoint semantics
- integrations that read arbitrary project files outside registered sources

## Failsafe

If an integration design needs new authority over state, validation, `analyze`, session policy, or schema, stop and resolve that at the architecture level before implementation.
