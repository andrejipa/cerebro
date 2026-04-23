# Formal Resume Trigger — Validation Decomposition

## Status

- state: `approved / active on 2026-04-23`
- drafted on: `2026-04-23`
- active boundary:
  - `docs/`: authorized
  - `tests/`: authorized for `tests/test_validate_error_ordering.py` only
  - `core/`: authorized for `core/validation.py` only
  - `cli/`: closed

## Classification

- `structural-maintenance / core-validation same-file decomposition with characterization backstop`

## Why This Trigger Exists

- `_validate_agent_runtime_block` in `core/validation.py:192-1057` remains the
  highest-density single function in the canonical runtime.
- The current function mixes nine primary shape-validation sections with five
  relational tail sections, all inside one append-order-sensitive body.
- The proposed work does not add behavior. It exists only to lower cognitive
  load for future maintenance while preserving exact observable validation
  output.

## Why The Current Surface Is Not Enough

- The current runtime behavior is already covered, but the validator boundary is
  structurally concentrated enough that small corrective changes pay a high
  cognitive tax.
- The function is large enough that future behavior-preserving edits will be
  riskier unless the sub-block seams are made explicit.
- This need cannot be satisfied by docs alone because the structural density is
  located inside `core/validation.py`.

## Allowed Scope

- modify only `core/validation.py`
- create only `tests/test_validate_error_ordering.py`
- update only:
  - `docs/operations/VALIDATION_DECOMPOSITION_PLAN.md`
  - `docs/operations/FORMAL_RESUME_TRIGGER_VALIDATION_DECOMPOSITION.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`

## Prohibited Scope

- any change in `cli/`
- any change in any `core/` file other than `core/validation.py`
- any change in `core/schema.py`
- any change in any test file other than `tests/test_validate_error_ordering.py`
- any new module, helper package, or sidecar fixture file
- any dataclass, `NamedTuple`, `TypedDict`, `Protocol`, `ABC`, context object,
  or accumulator object
- any rename of existing locals inside `_validate_agent_runtime_block`
- any change to public signatures
- any message cleanup, duplicate-validation cleanup, or behavior cleanup

## Required Invariants

- `_validate_agent_runtime_block` keeps the same public signature
- error append order remains identical
- error codes remain identical
- error messages remain identical
- later relational checks remain in the same effective order
- no external behavior change is introduced through the decomposition

## Characterization Preconditions

No extraction may begin until one preparatory commit adds
`tests/test_validate_error_ordering.py` and pins exact `(code, message)` output
ordering for one malformed payload per planned sub-block.

Current status:

- satisfied on `2026-04-23`
- current oracle file: `tests/test_validate_error_ordering.py`
- current oracle coverage: `15` tests (`14` per-block cases + `1` mixed-order case)

Required sub-block coverage before slice 1:

- `plan_core`
- `execution_policy_core`
- `command_registry_core`
- `approvals_core`
- `actions_core`
- `batch_registry_core`
- `verification_core`
- `memory_core`
- `audit_core`
- `plan_dependency_relations`
- `audit_last_action_ref`
- `task_action_ref_relations`
- `action_relations`
- `verification_relations`

## Planned Slice Order

1. `_validate_memory_block`
2. `_validate_execution_policy_block`
3. `_validate_batch_registry_block`
4. `_validate_command_registry_block`
5. `_validate_audit_block`
6. `_validate_actions_block`
7. `_validate_approvals_block`
8. `_validate_verification_block`
9. `_validate_plan_block`
10. `_validate_audit_last_action_ref_block`
11. `_validate_task_action_ref_relations_block`
12. `_validate_plan_dependency_relations_block`
13. `_validate_verification_relations_block`
14. `_validate_action_relations_block`

## Commit Discipline

- commit 1:
  - `tests(validate): pin aggregate error ordering for _validate_agent_runtime_block`
- subsequent commits:
  - one extracted helper per commit
  - title form: `refactor(validate): extract _validate_<block>_block (slice N/M)`
- continue automatically at one slice per heartbeat round through slice `11/14`
  while the whitelist is unchanged and all required gates stay green
- reintroduce a mandatory operator checkpoint before slice `12/14`

## Stop Conditions

Stop immediately if any one of these becomes true:

- characterization tests expose pre-existing behavior that is too entangled to
  isolate safely
- a slice requires touching a file outside the allowed scope
- a slice requires a new module or a new abstraction layer
- a slice requires renaming locals
- a slice requires reordering validations
- a slice requires changing error text or error codes
- a slice requires more than about `6` primitive or collection inputs
- any gate turns red

## Failure Handling

If a stop condition is hit:

- do not force the slice
- record the blocker in `docs/operations/VALIDATION_DECOMPOSITION_PLAN.md`
- leave the trigger in a non-consumed state
- return to the operator for a new decision before any further mutation

## Verification

Every approved slice must clear all of:

- AGENTS-equivalent suite gate
- `python -m unittest tests.test_architecture -v`
- `python -m unittest tests.test_validate -v`
- `python -m unittest tests.test_validate_error_ordering -v`

## Active Outcome

- continuation requires trigger approval: `yes`
- candidate first slice: `_validate_memory_block`
- approved state today: `yes`
- characterization precondition status: `satisfied`
- completed slice count: `3/14`
- observation-center routing:
  - `validation-slice-4-command-registry` is the current open queue head in `docs/operations/observation_center.toml`
- next required step:
  - `execute slice 4 (_validate_command_registry_block); autonomous continuation is pre-approved through slice 11 while gates stay green`
