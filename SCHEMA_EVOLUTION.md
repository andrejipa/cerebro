# Schema Evolution

## Current Policy

- current schema version: `1`
- supported schema versions are defined by the runtime
- the runtime rejects unsupported schema versions explicitly

## Compatibility Strategy

- backward compatibility is opt-in and explicit
- new schema versions must be added to runtime policy deliberately
- migration logic, when it exists, must be isolated from the core persistence path

## Current Runtime Behavior

- if `state.json` contains an unsupported version, validation fails
- no automatic migration is attempted
- no silent fallback is allowed

## Future Rule

Any future migration must:

- preserve the single source of truth
- be explicit and one-way unless a reverse migration is deliberately designed
- run outside the steady-state read/write path
