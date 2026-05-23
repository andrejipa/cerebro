# Formal Resume Trigger — Validation Slice 14 Exception

## Status

- state: `consumed / completed on 2026-04-23`
- drafted on: `2026-04-23`
- authority note: `within AGENTS.md, this trigger is a narrow child override for slice 14 only; it does not reopen any broader validation-decomposition scope`
- parent trigger: `FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md`
- active boundary:
  - `docs/`: authorized
  - `tests/`: authorized for `tests/test_validate_error_ordering.py` only
  - `core/`: authorized for `core/validation.py` only
  - `cli/`: closed

## Classification

- `structural-maintenance / final high-fan-out same-file helper extraction under explicit exception`

## Why This Trigger Exists

- `_validate_action_relations_block` is the only remaining unextracted block in
  `_validate_agent_runtime_block`.
- The parent trigger halted correctly when the final block exceeded the generic
  `~6` primitive-or-collection fan-out guidance.
- That halt was governance-correct, but the remaining hotspot is still the most
  valuable seam to isolate if it can be done without changing observable
  behavior.

## Narrow Exception

For slice `14/14` only:

- a private helper in `core/validation.py` may accept more than about `6`
  primitive or collection arguments
- those arguments must be passed verbatim; no new container, context object,
  dataclass, accumulator, or abstraction layer may be introduced
- the helper must preserve the current control flow, append order, fallback
  semantics, and local names exactly

This exception does not authorize any broader relaxation elsewhere in
`core/validation.py`.

## Allowed Scope

- modify only `core/validation.py`
- modify only `tests/test_validate_error_ordering.py`
- update only:
  - `docs/operations/FORMAL_RESUME_TRIGGER_VALIDATION_SLICE_14_EXCEPTION.md`
  - `docs/operations/FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md`
  - `docs/operations/VALIDATION_DECOMPOSITION_PLAN.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/observation_center.toml`

## Prohibited Scope

- any change in `cli/`
- any change in any `core/` file other than `core/validation.py`
- any change in any test file other than `tests/test_validate_error_ordering.py`
- any new module, helper package, sidecar fixture file, or new data carrier
- any dataclass, `NamedTuple`, `TypedDict`, `Protocol`, `ABC`, context object,
  or accumulator object
- any rename of existing locals inside the extracted `action_relations` logic
- any change to public signatures
- any behavior cleanup, message cleanup, or duplicate-validation cleanup

## Preconditions Before Extraction

Before the extraction commit, strengthen the action-relations oracle in
`tests/test_validate_error_ordering.py` with explicit exact-order `(code,
message)` coverage for these paths:

1. unknown `task_id`
2. task/action membership mismatch against `action_ids_by_task`
3. unknown `approval_id`
4. `pending_approval` paired with resolved approval
5. `applied` paired with rejected approval
6. `required_action_approval_error(...)` on the legacy single-task fallback path
7. unknown `batch_id`

If these reinforcements cannot pin the current behavior clearly, halt and do
not extract.

## Commit Discipline

- preparatory commit:
  - `tests(validate): strengthen action_relations ordering oracle`
- final slice commit:
  - `refactor(validate): extract _validate_action_relations_block (slice 14/14)`

Do not batch both steps into one commit.

## Required Invariants

- `_validate_agent_runtime_block` keeps the same public signature
- `_validate_action_relations_block` remains in `core/validation.py`
- error append order remains identical
- error codes remain identical
- error messages remain identical
- the legacy single-task fallback remains identical
- no new abstraction layer is introduced to hide the fan-out

## Stop Conditions

Stop immediately if any one of these becomes true:

- the strengthened oracle still leaves validation shape or append order
  confidence ambiguous
- the helper requires any new abstraction beyond direct arguments
- the helper requires reordering checks
- the helper requires changing error text or error codes
- any gate turns red
- any file outside the allowed scope becomes necessary

## Verification

Every commit under this trigger must clear all of:

- AGENTS-equivalent suite gate
- `python -m unittest tests.test_architecture -v`
- `python -m unittest tests.test_validate -v`
- `python -m unittest tests.test_validate_error_ordering -v`

## Active Outcome

- approved state today: `consumed`
- target slice: `_validate_action_relations_block`
- preparatory oracle status:
  - `satisfied on 2026-04-23`
  - `tests/test_validate_error_ordering.py` now covers `21` tests total (`14` original per-block payloads + `1` mixed aggregate-order case + `6` reinforced action_relations edge-path cases)
- final slice result:
  - `_validate_action_relations_block` landed cleanly in `core/validation.py` on `2026-04-23`
  - exact ordering/message coverage stayed green under `tests.test_validate_error_ordering`
  - no new abstraction layer, context object, or scope widening was introduced
- current next required step:
  - `none; this narrow child trigger is fully consumed`
