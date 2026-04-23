# Formal Resume Trigger — Material Scope Slice 1

Date: 2026-04-23

## Status

- state: `consumed`
- authority note: `operator direction accepted the reviewed foundation package for canonical commit`

## Trigger

The operator requested continued execution of the executable hardening plan.
This trigger reopens one narrow corrective-maintenance boundary for the
material-scope/preimage foundation only.

## Authorized Boundary

- create `core/material_scope.py`
- create `tests/test_material_scope.py`
- update `docs/operations/observation_center.toml`
- update `docs/operations/OPPORTUNITY_MAP.md`
- update `docs/operations/SYSTEM_STATE.md`

## Stop Conditions

- any required pre-slice gate failure
- any mutation to live apply/state/rollback/CLI paths
- any integration with commit protocol, state store, action runtime, or replay
- any test failure after the slice
- any unresolved ambiguity about what the primitive proves

## Required Invariants

- material paths are relative, normalized, unique, and inside the declared root
- directory, absolute, traversal, duplicate, and symlink paths fail closed
- existing files are represented by canonical sha256 byte digests and sizes
- missing files are distinct from empty existing files
- create, delete, or content mutation after preimage capture is detected
- declared effects outside the captured scope fail closed

## Explicit Non-Goals

- no live filesystem instrumentation
- no commit protocol integration
- no rollback or recovery integration
- no state-store or CLI changes
- no claim that unreported external effects are detectable yet
