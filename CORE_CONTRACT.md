# Core Contract

This document defines the stable public contract of the v1 core.

## What The Core Guarantees

- one canonical state file at `.cerebro/state.json`
- one local session file at `.cerebro/session.local.json`
- explicit source registration only
- deterministic validation through `validate`
- atomic writes for runtime JSON files
- monotonic `revision`
- stable read access through `StateStore` read methods and read models

## What The Core Does Not Do

- repository scanning
- context inference
- semantic interpretation of registered files
- direct extension writes to core state
- shared multi-user coordination
- automatic state mutation based on external files

## Immutable Behaviors

- `validate` never increments `revision`
- `checkpoint` never changes `sources`
- `analyze` is the standard operational entrypoint for continuity
- `analyze` only succeeds after `validate OK`
- `resume` only succeeds after `validate OK`
- `session.local.json` never changes business validity
- only `StateStore` may read or write runtime JSON files
- consumers outside the core stay subordinate to persisted validation state and do not open a second validation gate

## Stable Public API

The stable core API is:

- `StateStore`
- `StateStoreError`
- `StateValidationError`
- `StateSnapshot`
- `CheckpointRecord`
- `SourceRecord`
- `ValidationRecord`

Consumers must use read methods and read models, not raw JSON shape.

Read-only helpers on `StateStore` such as `has_active_session()` are part of the supported extension boundary when they do not mutate runtime state. `has_active_session()` reports local session-file presence only; it is not a second session-validity gate.

CLI command names are canonical. Do not add aliases or synonyms without an explicit architecture decision.

## Invariants

- `state.json` is always schema-valid when persisted by the core
- `sources` are relative, lexical, deduplicated, inside root, and hash-shaped
- checkpoint fields remain bounded
- session state remains local and optional
- unsupported schema versions fail explicitly
