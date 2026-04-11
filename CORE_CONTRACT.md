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
- `resume` only succeeds after `validate OK`
- `session.local.json` never changes business validity
- only `StateStore` may read or write runtime JSON files

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

## Invariants

- `state.json` is always schema-valid when persisted by the core
- `sources` are relative, lexical, deduplicated, inside root, and hash-shaped
- checkpoint fields remain bounded
- session state remains local and optional
- unsupported schema versions fail explicitly
