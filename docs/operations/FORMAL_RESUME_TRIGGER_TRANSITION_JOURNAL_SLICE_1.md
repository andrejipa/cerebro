# Formal Resume Trigger - Transition Journal Slice 1

## Status

- state: `consumed / completed on 2026-04-23`
- drafted on: `2026-04-23`
- authority note: `operator direction accepted the reviewed foundation package for canonical commit`

## Classification

- `corrective-maintenance / canonical-journal foundation with destructive ordering tests`

## Why This Trigger Exists

- The current runtime has trace events, but no canonical transition journal with
  strong sequence ordering, event-id chaining, and gap detection.
- The executable specification requires ordering guarantees before any later
  apply/state integration can be made auditable.
- This slice creates the isolated journal primitive only. It must not alter
  apply, rollback, verify, schema, or existing state persistence behavior.

## Allowed Scope

- create `core/transition_journal.py`
- create `tests/test_transition_journal.py`
- update only:
  - `docs/operations/FORMAL_RESUME_TRIGGER_TRANSITION_JOURNAL_SLICE_1.md`
  - `docs/operations/observation_center.toml`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`

## Prohibited Scope

- any change in `cli/`
- any change in `core/schema.py`
- any change in `core/state_store.py`
- any change in `core/action_runtime.py`
- any change in `core/validation.py`
- any integration of the new journal into live apply/rollback/verify paths
- any behavior change to existing trace events

## Required Invariants

- journal event files have contiguous `sequence_number` values starting at `1`
- event `N` records `previous_event_id` equal to event `N-1`
- `event_id` is derived from canonical JSON excluding only `event_id`
- stale `HEAD` is recoverable and never authoritative
- sequence gaps, duplicate sequence files, corrupt event ids, and broken chains
  fail closed
- abandoned temporary files do not become committed events

## Stop Conditions

- implementation requires touching any prohibited file
- existing tests fail
- architecture gate rejects the new module boundary
- destructive tests cannot prove gap, chain, stale-HEAD, and temp-file behavior
- the module needs to know `.cerebro` or `state.json` paths directly

## Verification

- `python -m unittest tests.test_transition_journal -v`
- `python -m unittest tests.test_architecture -v`
- AGENTS-equivalent suite gate

## Active Outcome

- created `core/transition_journal.py`
- created `tests/test_transition_journal.py`
- destructive journal tests cover:
  - monotonic sequence assignment
  - previous-event chaining
  - stale `HEAD` recovery
  - sequence-gap fail-closed behavior
  - event-id corruption detection
  - previous-event mismatch detection
  - abandoned temp-file cleanup
  - invalid journal `.json` file-name fail-closed behavior
  - `HEAD` cache-write failure not reclassifying an already committed event
  - rejection of caller-supplied ordering fields
  - rejection of incomplete transition records
  - rejection of malformed pre/post state digest fields
  - same-sequence concurrent write conflict without overwriting the existing event file
- focused verification:
  - `python -m unittest tests.test_transition_journal -v`: `12` tests, `0` failures
  - `python -m unittest tests.test_architecture -v`: `51` tests, `0` failures
- continuation requires a new formal resume trigger; this slice did not connect
  the journal to live apply, rollback, verify, state, or schema paths.
