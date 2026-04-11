# Architecture Boundaries

## Core Responsibilities

The core is responsible for:

- creating and maintaining the `.cerebro/` runtime directory
- reading and writing the canonical state file
- reading and writing the local session file
- validating the structural integrity of state, sources, and session
- enforcing invariants for revision, sources, and checkpoint limits

The core authority is `StateStore`.

## Core Non-Responsibilities

The core never:

- scans the repository
- discovers files automatically
- interprets the semantic meaning of external files
- updates state from external changes without an explicit command
- treats logs as a source of truth
- shares mutable runtime state across multiple operators

## State Boundary

Only these runtime files influence behavior:

- `.cerebro/state.json`
- `.cerebro/session.local.json`

Logs are operational artifacts only:

- `.cerebro/logs/events.jsonl`

No other file may change runtime behavior unless it is explicitly registered in `sources` and only for integrity checks.

## Extension Boundary

Extensions may:

- read canonical state through the public `core` API
- render derived outputs from `read_snapshot()`, `read_checkpoint()`, or `read_sources()`
- use read-only helpers such as `has_active_session()` when exposed by `StateStore`
- consume validation results already present in the canonical snapshot
- expose disposable export, analysis, or integration interfaces on top of the core

Extensions may not:

- read runtime JSON directly
- write anywhere inside `.cerebro/`
- mutate state behind the back of `StateStore`
- create a second source of truth
- infer sources automatically
- execute business decisions on behalf of the core

Extensions are consumers. The core remains the only authority.

Permitted flow:

```text
core -> extension (read)
```

Forbidden flow:

```text
extension -> core (implicit write)
```

## Isolation Rules

- Runtime path literals belong in `StateStore`.
- JSON serialization for runtime files belongs in `StateStore`.
- CLI commands may orchestrate calls, but may not manage state files directly.
- Tests may manipulate files directly only to simulate corruption and failure conditions.
- When an extension design is ambiguous, the correct fallback is to not implement it until the boundary is explicit.
