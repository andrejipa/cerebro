# Robustness Baseline

This document records the permanent robustness baseline confirmed by the adversarial revalidation completed on April 11, 2026.

No critical or moderate failures were found in that cycle.
The baseline below is now part of the expected contract for future evolution.

## Covered Corruption Classes

### State

- invalid JSON in `.cerebro/state.json`
- missing required root or checkpoint keys
- unexpected extra root keys
- invalid scalar types such as boolean `revision`
- bounded-value overflow such as oversized checkpoint fields
- unsupported schema versions

### Sources

- registered file removed after registration
- registered file content changed after registration
- absolute paths and parent traversal attempts
- duplicate or unordered registered paths
- source count above the schema limit
- symlink resolution outside project root

### Session

- invalid JSON in `.cerebro/session.local.json`
- missing required keys
- unexpected extra keys
- invalid scalar types such as boolean `based_on_revision`
- `based_on_revision` greater than `state.revision`

### Runtime And CLI

- `analyze` blocks when `validate` fails
- blocked `analyze` does not open a local session
- repeated `checkpoint -> analyze` cycles preserve checkpoint, sources, and revision semantics
- runtime failures remain explicit and predictable under corruption

### Extensions

- current exports fail explicitly on invalid runtime JSON
- current exports fail explicitly on schema-invalid runtime state
- current exports reject writes inside `.cerebro/`
- current exports do not leak source file contents
- current exports remain read-only when executed in sequence
- current exports reflect the canonical failed validation state after a real `analyze` block
- tracked extensions do not read runtime JSON directly
- tracked extensions do not read arbitrary files or enumerate directories directly

## Confirmed Invariants

- the core remains the only authority over runtime state
- `validate` preserves `revision`
- `analyze` remains orchestration over the same deterministic validation gate
- sources remain explicit, bounded, lexical, and rooted under the project
- local session corruption never mutates canonical state
- extensions remain consumers and do not acquire authority through outputs

## Accepted Limits

- exports and derived views consume the canonical snapshot and the last persisted validation result
- exports do not revalidate the runtime by themselves
- exports do not open a second validation gate and do not attempt runtime repair
- hardening remains external to the core unless a future concrete gap cannot be stopped by tests and governance

## Permanent Defense Layers

- `tests/test_adversarial_revalidation.py`: adversarial corruption and repeated-runtime stress
- `tests/test_extension_contracts.py`: shared read-only export contract
- `tests/test_architecture.py`: structural and documentary boundary enforcement

## Evolution Rule

Any change that expands or changes the public surface must add proportional adversarial and regression coverage.

This applies to:

- new or changed CLI commands
- new or changed extensions
- new or changed external integrations

If a proposed change needs new authority over state, validation, `analyze`, session policy, or schema, resolve that at the architecture level before implementation.
