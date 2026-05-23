# Formal Resume Trigger — Verification Output Budget Hardening

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Close the audit finding that verification commands can persist unbounded stdout
or stderr artifacts. Verification evidence must remain useful and inspectable
without allowing one noisy command to flood local storage, slow review, or make
the runtime evidence surface hard to audit.

This is corrective reliability/performance hardening. It does not change
command execution semantics, approval policy, verification pass/fail semantics,
or canonical schema.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_VERIFICATION_OUTPUT_BUDGET_HARDENING.md`
- `core/verification_runtime.py`
- `tests/test_verification_runtime.py`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Readable:

- `AGENTS.md`
- live operational docs
- `core/verification_runtime.py`
- `tests/test_verification_runtime.py`
- verification and architecture tests

## Explicit Non-Authorization

This trigger does not authorize:

- edits to `core/schema.py`;
- edits to `cli/`;
- edits to `extensions/`;
- edits to `.cerebro/` or canonical state outside normal tests;
- changing command execution policy, command selection, approval policy,
  command timeout behavior, or verification pass/fail semantics;
- adding new canonical state fields for truncation metadata;
- changing how command ids, artifact refs, or verification coverage work.

## Acceptance Criteria

- Persisted verification stdout artifacts are bounded by an explicit byte
  budget and end with a stable truncation marker when truncated.
- Persisted verification stderr artifacts are bounded by the same policy.
- Small stdout/stderr artifacts remain byte-for-byte unchanged.
- A command that exits non-zero with huge output still records a failed check.
- `artifact_sha256` matches the persisted stdout artifact text, not the
  unbounded original stream.
- No new schema fields are required.
- Focused verification tests cover stdout truncation, stderr truncation, small
  output preservation, and failed-command semantics.
- `tests.test_architecture` remains green.
- Full AGENTS-equivalent gate remains green.

## Stop Conditions

- Any need to change `core/schema.py`.
- Any need to change command execution semantics, approval policy, selected
  command coverage, or timeout behavior.
- Any test shows truncation changes pass/fail outcome.
- Any gate failure not directly explained by this slice.

## Closure Evidence

Result: consumed on 2026-04-25.

Implemented:

- `core/verification_runtime.py` now bounds persisted verification stdout and
  stderr artifacts to `65536` UTF-8 bytes.
- Truncated artifacts end with the stable marker
  `... [truncated after 65536 bytes]`.
- Redaction still runs before output limiting.
- `artifact_sha256` is computed over the persisted stdout artifact text.
- Verification command exit code and pass/fail semantics are unchanged.
- No canonical schema fields were added.

Validation:

- Focused verification tests: `13/0`.
- Command sandbox regression tests: `4/0`.
- Validation tests: `78/0/3`.
- Architecture/doc-governance gate: `64/0`.
- Full AGENTS-equivalent gate after implementation: `931/0/0/6`.

Non-authorization preserved: no `core/schema.py`, `cli/`, `extensions/`,
`.cerebro/`, command execution policy, approval policy, timeout behavior,
command selection, or verification coverage semantics changed.
