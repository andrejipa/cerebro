# Formal Resume Trigger — Tests-Only Coverage Tranche

## Status

- State: approved, executed, and closed
- Classification: corrective maintenance / `tests/` only
- Opened on: 2026-04-23
- Closed on: 2026-04-23

## Use Case

The latest P4/P5 proof-of-stop scout found direct coverage gaps in canonical
runtime behavior that cannot be closed through docs or derived experiments.
The gaps are limited to regression and direct-coverage additions in `tests/`.

## Why The Current Surface Is Not Enough

- The current approved surface still leaves direct runtime invariants uncovered
  in `decision_runtime`, `action_identity`, and the
  extracted `StateStore` helper services.
- `discipline_runtime` was initially included in the scout intake but was later
  satisfied by the proportional regression added during the P4
  workspace-path-resolution slice (`a80cddc`), so this trigger only had to land
  the remaining five `tests/` targets directly.
- Those gaps are observable in the current repository and cannot be reduced by
  documentary work alone.

## Boundary

- Authorized:
  - `tests/`
  - `docs/operations/`
- Closed:
  - `core/`
  - `cli/`
- Explicitly prohibited:
  - any helper, seam, flag, or production edit in `core/` or `cli/`
  - any behavior change disguised as a test update
  - any weakening of assertions to fit current runtime behavior

## Objective

Add direct coverage and regression coverage for the already-observed P5
findings, in ordered slices, without changing canonical runtime behavior.

## Stop Conditions

Stop the tranche immediately when any one of these becomes true:

- a test requires touching `core/`
- a test requires touching `cli/`
- a new assertion fails because runtime behavior is unexpectedly different from
  the documented invariant
- a target branch depends on host-specific setup and cannot be exercised
  portably

## Failure Handling

If a new test fails because of unexpected runtime behavior:

- classify it as a bug in `core/`
- do not weaken the test
- do not patch `core/`
- stop the tranche immediately
- register the blocking item in `OPPORTUNITY_MAP.md`

If a target branch depends on host-specific setup:

- classify it as `DEFER_NO_ACTION`
- do not add a workaround

## Active Execution Order

1. `decision_runtime`
2. `action_identity`
3. `state_runtime_lock_service`
4. `state_session_artifacts_service`
5. `state_retention_service`

## Previously Satisfied Target

- `discipline_runtime` — closed later by the proportional regression added in
  the P4 workspace-path-resolution slice (`a80cddc`), not by this tests-only
  tranche

## Execution Result

- All five planned slices in this trigger completed in `tests/` only.
- No `core/` or `cli/` files were modified.
- No unexpected runtime-behavior failure was uncovered.
- The boundary is now closed again; any future `tests/` mutation requires a new trigger.
