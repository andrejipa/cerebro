# Formal Resume Trigger - Replay Snapshot Slice 1

## Status

- state: `consumed`
- drafted on: `2026-04-23`
- authority note: `operator direction accepted the reviewed foundation package for canonical commit`
- consumed on: `2026-04-23`

## Classification

- `corrective-maintenance / isolated replay-digest and snapshot-acceptance foundation`

## Why This Trigger Exists

- The transition journal and canonical state digest now exist only as isolated
  primitives.
- Replay and snapshot policy still need an isolated, testable bridge that can
  verify digest continuity from an initial state through committed transition
  records and decide whether a snapshot is acceptable, stale, or invalid.
- This slice deliberately does not apply transition events or reconstruct full
  state. It verifies only the digest chain and snapshot metadata/digest
  equivalence required before a later reducer-based replay slice can be trusted.

## Allowed Scope

- create `core/replay_model.py`
- create `tests/test_replay_model.py`
- update only:
  - `docs/operations/FORMAL_RESUME_TRIGGER_REPLAY_SNAPSHOT_SLICE_1.md`
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
- any integration of replay or snapshot behavior into live load/save/apply paths
- any reducer, event application, state mutation, migration, or filesystem commit protocol

## Required Invariants

- replay starts from the canonical digest of the supplied initial state and schema version
- every event sequence is contiguous and starts at `1`
- every event `previous_event_id` links to the prior event id
- every event id is recomputed from canonical transition-journal rules
- every event `pre_state_digest` equals the current replay digest
- replay result is the final event `post_state_digest`, or the initial digest for an empty journal
- a snapshot is accepted only when its metadata and canonical state digest match the replay head exactly
- stale snapshots are discarded, not accepted
- snapshots ahead of replay, digest-mismatched snapshots, malformed metadata, and schema-version mismatches fail closed

## Stop Conditions

- implementation requires touching any prohibited file
- existing tests fail
- architecture gate rejects the new module boundary
- destructive tests cannot distinguish accepted, stale, and fail-closed snapshots
- the module needs to know `.cerebro` or `state.json` paths directly
- the module claims full state reconstruction without a reducer contract

## Verification

- `python -m unittest tests.test_replay_model -v`
- `python -m unittest tests.test_architecture -v`
- AGENTS-equivalent suite gate

## Active Outcome

- added `core/replay_model.py` as an isolated replay-digest and snapshot-acceptance primitive
- added `tests/test_replay_model.py` with destructive coverage for contiguous digest replay, event-id recomputation, previous-event linkage, schema-version mismatch, pre-state digest mismatch, malformed event payloads, accepted snapshots, stale snapshot discard, ahead-of-replay snapshots, digest mismatches, and malformed metadata
- adversarial critique found and closed one slice-local weakness: digest fields and event payloads are now validated fail-closed instead of accepting arbitrary digest-shaped strings or non-finite JSON values
- this trigger did not integrate replay into live state persistence, transition journal storage paths, snapshot files, apply, rollback, verify, schema, validation, or migration paths
- this trigger did not implement reducer-based state reconstruction; replay is limited to verified digest-chain continuity
- continuation requires a new formal resume trigger with its own whitelist, stop conditions, destructive tests, and full gate
