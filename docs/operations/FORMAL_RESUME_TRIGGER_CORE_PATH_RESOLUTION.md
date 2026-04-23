# Formal Resume Trigger — Core Path Resolution Refactor

## Status

- `consumed / completed on 2026-04-23`
- objective result:
  - `core/workspace_paths.py` was created as the shared leaf helper
  - `_resolve_workspace_path` was adjusted in `core/action_runtime.py` and `core/discipline_runtime.py`
  - proportional regression was added in `tests/test_action_runtime.py` and `tests/test_discipline_runtime.py`
  - final verification stayed green at `825` tests, `0` failures, `6` skips via the AGENTS-equivalent runner, plus `51` architecture tests and `0` failures
- boundary after closeout:
  - `core/`: closed
  - `tests/`: closed
  - `cli/`: closed

## Classification

- `corrective-maintenance / core-only narrow refactor with proportional regression`

## Why This Trigger Exists

- A docs-only analysis confirmed structural duplication and drift between `core/action_runtime.py` and `core/discipline_runtime.py` around workspace-path resolution.
- Keeping the current state increases the chance of future contract drift and inconsistent guard placement across runtime-critical paths.
- The goal of this trigger is to remove that drift with the smallest possible core change, without reopening broader runtime growth.

## Allowed Scope

- create `core/workspace_paths.py`
- adjust only `_resolve_workspace_path` in `core/action_runtime.py`
- adjust only `_resolve_workspace_path` in `core/discipline_runtime.py`
- add or adjust proportional regression coverage in `tests/`
- update `SYSTEM_STATE.md` and `OPPORTUNITY_MAP.md` during closeout

## Prohibited Scope

- any change in `cli/`
- any change in `core/schema.py`
- any change in `core/validation.py`
- any broad refactor in `apply_action`, `rollback_action`, `_collect_apply_surface`, `evaluate_action_effectiveness`, or `evaluate_retry_discipline`
- any removal of downstream guards already present in `action_runtime`
- any intentional external behavior change

## Required Invariants

- `action_runtime` must continue surfacing workspace-path failures as `ActionRuntimeError`
- `discipline_runtime` must continue surfacing workspace-path failures as `ValueError`
- absolute paths remain invalid
- paths containing `..` remain invalid
- resolved containment within the workspace remains mandatory
- the existing non-empty string policy stays where it is today:
  - `action_runtime` keeps it
  - `discipline_runtime` does not gain it in this slice

## Stop Conditions

- any need to touch `cli/`
- any need to expand beyond the `_resolve_workspace_path` boundary
- any new test failing because runtime behavior diverges from the current contract
- any attempt to weaken tests or adjust expectations to make the slice pass

## Verification

- focused `action_runtime` tests
- focused `discipline_runtime` tests
- `tests/test_runtime_units.py` when needed for retry-discipline proof
- AGENTS-equivalent suite gate
- `python -m unittest tests.test_architecture -v`
