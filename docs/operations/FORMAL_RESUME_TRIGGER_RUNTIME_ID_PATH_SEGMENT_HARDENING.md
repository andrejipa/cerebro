# Formal Resume Trigger — Runtime ID Path Segment Hardening

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Close the audit finding that runtime identifiers can be used as filesystem path
segments before being constrained to a path-segment-safe vocabulary.

The concrete risk is narrow:

- `action.id` is used under `.cerebro/artifacts/actions/` and `.cerebro/trash/`.
- `command_registry[].id` is used in verification stdout/stderr artifact names.

This trigger is corrective maintenance, not runtime growth.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_RUNTIME_ID_PATH_SEGMENT_HARDENING.md`
- `core/runtime_ids.py`
- `core/action_runtime.py`
- `core/validation.py`
- `tests/test_action_runtime.py`
- `tests/test_validate.py`
- `tests/test_verification_runtime.py`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Readable:

- `AGENTS.md`
- live operational docs
- `core/action_runtime.py`
- `core/validation.py`
- `core/verification_runtime.py`
- existing runtime tests

## Explicit Non-Authorization

This trigger does not authorize:

- edits to `core/schema.py`;
- edits to `cli/`;
- edits to `extensions/`;
- edits to `.cerebro/` or canonical state;
- changing action semantics, verification semantics, approval semantics, or
  command execution policy;
- adding a runtime feature, claim graph, advisory layer, or third-party target
  behavior;
- weakening existing tests or broadening accepted path forms.

## Acceptance Criteria

- Runtime ids that become filesystem path segments must reject path separators,
  `..`, empty values, whitespace-only values, and absolute/path-looking input.
- Existing normal ids such as `act-create`, `cmd-001`, `verify.fast`, and
  `task_01` remain accepted.
- A malicious `action.id` cannot create action artifacts or trash outside the
  intended runtime directories.
- A malicious `command_registry[].id` cannot create verification artifacts
  outside the intended run directory.
- Focused tests cover both action id and command id traversal attempts.
- `tests.test_architecture` remains green.
- Full AGENTS-equivalent gate remains green.

## Stop Conditions

- Any need to touch `core/schema.py`, `cli/`, `extensions/`, or `.cerebro/`.
- Any existing legitimate checked-in fixture requires path separators in action
  ids or command ids.
- Any correction requires changing command execution behavior rather than id
  validation.
- Any gate failure not directly explained by this slice.

## Closure Evidence

- Added `core/runtime_ids.py` as a shared runtime-id path-segment policy.
- `core/action_runtime.py` now rejects unsafe `action.id` values before action
  artifact, stdout/stderr, preimage, or trash paths can be composed.
- `core/validation.py` now rejects unsafe persisted action ids and command
  registry ids, preventing verification artifact filenames from being built
  from path-looking ids.
- Regression coverage:
  - `tests.test_action_runtime`: malicious `action.id = "../escape"` is rejected
    before target mutation or artifact directory creation.
  - `tests.test_validate`: malicious `command_registry[].id = "../escape"` is
    rejected, while safe ids such as `cmd.fast_01` stay valid.
- Focused validation: `tests.test_action_runtime`, `tests.test_validate`, and
  `tests.test_verification_runtime` passed `99` tests, `0` failures, `3` skips.
- Architecture gate: `51` tests, `0` failures.
- Full AGENTS-equivalent gate after closeout: `926` tests, `0` failures,
  `0` errors, `6` skips.
