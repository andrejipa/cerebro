# Formal Resume Trigger - Event Reducer Slice 1

## Status

- state: `consumed`
- drafted on: `2026-04-23`
- authority note: `operator direction accepted the reviewed foundation package for canonical commit`
- consumed on: `2026-04-23`

## Classification

- `corrective-maintenance / isolated versioned event reducer foundation`

## Why This Trigger Exists

- The current replay foundation verifies only digest-chain continuity.
- A later full replay path needs versioned event reducer contracts before it can
  reconstruct state rather than only compare digests.
- This slice creates one isolated reducer contract for one state transition:
  `checkpoint.replaced` version `1`.
- This slice must remain in-memory only and must not connect to live state
  persistence, CLI commands, snapshot files, or journal storage.

## Allowed Scope

- create `core/event_reducer.py`
- create `tests/test_event_reducer.py`
- update only:
  - `docs/operations/FORMAL_RESUME_TRIGGER_EVENT_REDUCER_SLICE_1.md`
  - `docs/operations/observation_center.toml`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`

## Prohibited Scope

- any change in `cli/`
- any change in `core/schema.py`
- any change in `core/state_store.py`
- any change in `core/action_runtime.py`
- any change in `core/validation.py`
- any change in `core/transition_journal.py`
- any change in `core/state_digest.py`
- any change in `core/replay_model.py`
- any integration of reducer replay into live load/save/apply paths
- any filesystem commit protocol, migration, snapshot persistence, or journal persistence change

## Required Invariants

- event type and event version are explicit and fail closed when unsupported
- deterministic reducer input has an exact schema; unknown fields fail closed
- observational reducer input has an exact schema and cannot alter canonical digest
- event `pre_state_digest` must match the current state before reduction
- reducer output must pass existing state validation
- event `post_state_digest` must match the canonical digest of the reduced state
- applying committed events in order reconstructs the deterministic state in memory
- state `revision` advances to the committed event `sequence_number`
- reducer cannot mutate the caller's input state

## Stop Conditions

- implementation requires touching any prohibited file
- existing tests fail
- architecture gate rejects the new module boundary
- destructive tests cannot prove fail-closed behavior for unsupported versions or digest mismatch
- the reducer needs to know `.cerebro`, `state.json`, or snapshot paths directly
- the module claims full event-sourcing coverage beyond the one supported event type

## Verification

- `python -m unittest tests.test_event_reducer -v`
- `python -m unittest tests.test_architecture -v`
- AGENTS-equivalent suite gate

## Active Outcome

- added `core/event_reducer.py` as an isolated in-memory reducer foundation
- added `tests/test_event_reducer.py` with destructive coverage for `checkpoint.replaced` version `1`, multi-event in-memory replay, exact deterministic and observational field contracts, unsupported type/version rejection, post-digest mismatch, invalid reduced state, caller-state immutability, uncommitted event rejection, event-id tampering, revision-sequence mismatch, and observational timestamp digest neutrality
- adversarial critique found and closed one slice-local weakness: direct `apply_event()` no longer trusts callers to provide a committed event or revision-aligned state
- this trigger did not integrate reducer replay into live state persistence, transition journal storage paths, snapshot files, apply, rollback, verify, schema, validation, migration, or commit recovery paths
- this trigger supports only `checkpoint.replaced` version `1`; broader event coverage requires future triggers and tests
- continuation requires a new formal resume trigger with its own whitelist, stop conditions, destructive tests, and full gate
