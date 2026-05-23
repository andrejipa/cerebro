# Formal Resume Trigger - State Digest Slice 1

## Status

- state: `consumed`
- drafted on: `2026-04-23`
- authority note: `operator direction accepted the reviewed foundation package for canonical commit`
- consumed on: `2026-04-23`

## Classification

- `corrective-maintenance / canonical-state-digest foundation with destructive equivalence tests`

## Why This Trigger Exists

- Replay and snapshot comparison need one deterministic state digest before any
  later journal/state integration can be trusted.
- The current runtime validates and persists `state.json`, but no isolated
  canonical digest contract exists for comparing deterministic state while
  excluding observational noise.
- This slice creates the isolated digest primitive only. It must not alter
  apply, rollback, verify, schema, validation, state persistence, or journal
  behavior.

## Allowed Scope

- create `core/state_digest.py`
- create `tests/test_state_digest.py`
- update only:
  - `docs/operations/FORMAL_RESUME_TRIGGER_STATE_DIGEST_SLICE_1.md`
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
- any integration of the new digest into live load/save/replay paths
- any behavior change to existing state validation or persistence

## Required Invariants

- equivalent states with different mapping insertion order produce the same digest
- schema version is part of the digest input
- decision-bearing state changes alter the digest
- observational fields are excluded by explicit rule, not convention
- list order remains semantic and is preserved
- absent optional fields and explicit `null` are different
- non-string object keys, non-finite floats, and unsupported object types fail closed

## Stop Conditions

- implementation requires touching any prohibited file
- existing tests fail
- architecture gate rejects the new module boundary
- destructive tests cannot prove deterministic equivalence and fail-closed behavior
- the module needs to know `.cerebro` or `state.json` paths directly

## Verification

- `python -m unittest tests.test_state_digest -v`
- `python -m unittest tests.test_architecture -v`
- AGENTS-equivalent suite gate

## Active Outcome

- added `core/state_digest.py` as an isolated canonical digest primitive
- added `tests/test_state_digest.py` with destructive coverage for canonical ordering, schema-version participation, decision-field drift, path-specific observational exclusions, list ordering, absent-vs-null distinction, and fail-closed unsupported values
- adversarial critique found and closed one slice-local weakness: generic field-name exclusions could have hidden future decision fields; the final implementation excludes only explicit canonical paths
- this trigger did not integrate digest behavior into live state persistence, transition journal replay, snapshot acceptance, apply, rollback, verify, schema, or validation paths
- continuation requires a new formal resume trigger with its own whitelist, stop conditions, destructive tests, and full gate
