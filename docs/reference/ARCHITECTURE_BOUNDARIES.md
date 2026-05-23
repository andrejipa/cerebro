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

These persisted runtime files define business continuity:

- `.cerebro/state.json`
- `.cerebro/session.local.json`

That persisted pair defines the repo-local continuity surface, but the live proof of session ownership is no longer fully contained in those repo-local files. Active session authority also depends on one external per-user session claim outside the project root.

A transient coordination artifact may appear during runtime operations:

- `.cerebro/runtime.lock`

Logs are operational artifacts only:

- `.cerebro/logs/events.jsonl`

No other persisted file may define runtime business validity unless it is explicitly registered in `sources` and only for integrity checks.
`runtime.lock` only serializes concurrent operations and does not become a second source of truth.
The core may remove a stale `runtime.lock` automatically when the prior owner appears inactive; that is coordination recovery only and does not certify semantic continuity of the interrupted round.

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

When exposed to extensions, `has_active_session()` reports local session-file presence only. It does not validate the session file and does not create a second session gate.

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
- Assistive bootstrap discovery such as `bootstrap-scan` may suggest candidates, but it may not define truth, register `sources`, or bypass `import-context`.
- Tests may manipulate files directly only to simulate corruption and failure conditions.
- When an extension design is ambiguous, the correct fallback is to not implement it until the boundary is explicit.

## Evolution Guard

- Public-surface changes must add proportional adversarial and regression coverage.
- Exports and integrations consume canonical state and persisted validation results; they do not become a second validation gate.
- Additional hardening should stop unless a concrete new evasion path appears or the public surface actually changes.
- CLI command names stay canonical unless an explicit architecture decision authorizes aliases.
- After the low-risk export slice was exhausted and the minimum approved external increments were closed, further capability growth stays deliberately frozen until a concrete repeated use case is recorded and classified.
- Curiosity, aesthetic polish, or abstract pressure to "get closer to the ideal" do not justify opening the next layer.
