# Formal Resume Trigger — Gate Flake: Session Refresh Timestamp

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Fix a red AGENTS-equivalent gate caused by a flaky assertion in
`test_validate_state_recovers_pending_session_refresh_after_crash_before_state_save`.
The test compared full `state.json` bytes after `validate_state()`, but
`validate_state()` legitimately refreshes `last_validation.validated_at`.
When the test crosses a one-second timestamp boundary, the recovery behavior is
correct but the byte-for-byte assertion fails.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_GATE_FLAKE_SESSION_REFRESH_TIMESTAMP.md`
- `tests/test_state_store.py`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Readable:

- `AGENTS.md`
- `core/state_store.py`
- `tests/test_state_store.py`
- live operational docs

## Explicit Non-Authorization

This trigger does not authorize:

- edits under `core/`, `cli/`, `extensions/`, `.cerebro/`, or `core/schema.py`;
- changing `validate_state()` semantics;
- weakening the session-refresh recovery assertion;
- starting the risk-budget/blast-radius slice before the gate is green.

## Acceptance Criteria

- The affected test forces a changed validation timestamp without sleeping.
- The test still proves revision stability, pending-journal cleanup, session
  restoration, claim restoration, and live-proof restoration.
- The test compares state after normalizing only
  `last_validation.validated_at`; any other state change still fails.
- Focused affected test passes repeatedly.
- `tests.test_state_store` passes.
- Full AGENTS-equivalent gate returns green.

## Closure Evidence

- Root cause: test flake, not runtime behavior. `validate_state()` refreshes
  `last_validation.validated_at`; the prior assertion compared raw
  `state.json` bytes and therefore failed when the test crossed a timestamp
  boundary.
- Correction: the test now forces a distinct validation timestamp with
  `_timestamp_now` mock, asserts the timestamp changed, normalizes only
  `last_validation.validated_at`, and then compares the full state object.
- Preserved assertions: revision stability, pending-journal cleanup,
  restored `session.local.json`, restored session claim bytes, and restored
  live-proof bytes.
- Focused validation: affected test `1/0`; 30-iteration repro loop `30/0`;
  `tests.test_state_store` `93/0`.
- Full AGENTS-equivalent gate after correction: `923` tests, `0` failures,
  `0` errors, `6` skips.
