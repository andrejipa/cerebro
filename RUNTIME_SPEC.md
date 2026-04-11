# Cerebro Runtime Specification v1

## 1. Purpose

Cerebro is a local context continuity runtime that exists to:

- register explicit operational state
- validate context integrity
- reconstruct the working point
- allow consistent resume across sessions

It exists to solve one problem:

`loss of context during agent-assisted execution`

## 2. Fundamental Principle

Context must be:

- explicit
- validatable
- versioned
- reproducible

It must never be:

- inferred implicitly
- reconstructed by heuristics
- dependent on external memory such as chat history

## 3. Architectural Position

```text
project/
  ...
  .cerebro/
    state.json
    session.local.json
    logs/
```

Cerebro is a cognitive layer attached to the project.

It is not:

- the project filesystem
- a documentation tool
- a substitute for Git
- a semantic analysis engine

## 4. Operational Model

Default entrypoint:

```text
cerebro analyze
```

Required flow:

1. load state from `state.json`
2. run `validate`
3. if invalid, block
4. if valid:
   reconstruct the checkpoint
   open the local session in `session.local.json`
   return the current context

## 5. Execution Contract

### `validate`

Responsibilities:

- verify structural integrity
- verify source existence
- verify source hashes
- verify session consistency

Output:

- `OK` means the runtime is usable
- `FAIL` means the runtime is blocked

### `checkpoint`

Responsibilities:

- update the operational state
- record the current goal
- record the next step
- close the local session

### `resume`

Responsibilities:

- execute `validate`
- reconstruct context
- open a new local session

## 6. Canonical State

Single canonical file:

```text
.cerebro/state.json
```

It contains:

- `sources`
- `checkpoint`
- `revision`
- `last_validation`

Rule:

`the only source of truth`

## 7. Local Session

Session file:

```text
.cerebro/session.local.json
```

Function:

- local continuity control
- not part of business authority

Rule:

`disposable and isolated`

## 8. Sources

Sources are:

- explicitly registered files
- validated by hash

Sources are not:

- interpreted
- analyzed automatically

Rule:

`the system knows only what was declared`

## 9. Invariants

These must always remain true:

- state is valid under the schema
- `revision` is monotonic
- sources are consistent and inside root
- no runtime write happens outside `StateStore`
- `validate` does not change structural state
- absence of a local session is not an error

## 10. Extensions

Extensions are:

- external to the core
- consumers of canonical state

They may:

- read through the public API
- generate derived outputs such as Markdown

They may not:

- alter state directly
- infer context
- create a second source of truth

## 11. Critical Separation

```text
CORE -> truth, validation, continuity
EXTENSIONS -> consumption, visualization, support
```

Permitted flow:

```text
core -> extension
```

Forbidden flow:

```text
extension -> core (implicit write)
```

## 12. Failure Behavior

If any validation fails:

- the runtime blocks execution
- it does not attempt automatic repair
- it does not infer missing state

Rule:

`explicit failure is correct`

## 13. Non-Goals

The system must not:

- understand project semantics
- infer absent context
- replace human communication
- automate decisions
- grow in complexity without need

## 14. Philosophy

The system does not try to be intelligent.

It guarantees one thing:

`the context in use is correct`

## 15. Final Definition

Cerebro is:

`a deterministic context runtime for agent-assisted execution`

## 16. Success Criteria

The system is successful if it:

- allows resume without chat history
- prevents use of invalid context
- maintains consistency over time
- stays simple while it grows

## 17. Evolution

The system must grow through:

- external extensions
- not by core expansion

Any change to the core requires:

- structural justification
- contract updates
- full validation

## 18. Final Rule

If there is doubt:

`preserve consistency over added capability`
