# Formal Resume Trigger — Verification Process Containment Hardening

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Close the audit finding that verification command timeouts are bounded at the
direct subprocess call but do not make process-group/tree containment explicit.
Verification commands must have bounded lifetime evidence: when timeout expires,
the verification result must fail closed and the runtime must make a best-effort
attempt to terminate the spawned process boundary before recording evidence.

This is corrective reliability hardening. It does not change command selection,
approval policy, command allow/deny policy, canonical schema, or the meaning of
successful verification.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_VERIFICATION_PROCESS_CONTAINMENT_HARDENING.md`
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
- verification, validation, architecture, and doc-governance tests

## Explicit Non-Authorization

This trigger does not authorize:

- edits to `core/schema.py`;
- edits to `cli/`;
- edits to `extensions/`;
- edits to `.cerebro/` or canonical state outside normal tests;
- changing command selection, command registry shape, approval policy, command
  allow/deny policy, timeout configuration source, or verification coverage;
- promising container-level isolation or perfect cross-platform orphan cleanup;
- adding a daemon, supervisor service, or external dependency.

## Acceptance Criteria

- Verification command execution uses an internal helper that creates an
  explicit process boundary where supported.
- Timeout returns a failed command check with a clear timeout message rather
  than an uncaught/internal verification error.
- Timeout persists bounded stdout/stderr artifacts through the existing output
  budget path.
- Normal command stdout/stderr/exit-code semantics remain unchanged.
- Best-effort process-boundary termination is covered by focused tests through
  mocks, without relying on real orphan processes.
- Kill/containment failures remain visible in the check message instead of
  being silently ignored.
- No schema fields are added.
- `tests.test_architecture` remains green.
- Full AGENTS-equivalent gate remains green.

## Stop Conditions

- Any need to change `core/schema.py`.
- Any need to change command registry shape, approval policy, command allow/deny
  policy, selected command coverage, or timeout configuration source.
- Any test shows timeout can be recorded as a passed check.
- Any implementation requires a daemon, external dependency, or container
  runtime.
- Any gate failure not directly explained by this slice.

## Closure Evidence

Implemented on 2026-04-25.

- `core/verification_runtime.py` now runs verify commands through an internal
  subprocess helper with an explicit process boundary where supported.
- On timeout, verification fails closed with `command timed out`, persists
  bounded stdout/stderr artifacts through the existing output budget path, and
  records best-effort containment failures in the check message instead of
  hiding them.
- Windows termination uses `taskkill /T /F /PID ...` followed by process kill
  fallback; POSIX termination uses process-group kill followed by process kill
  fallback.
- Normal command stdout/stderr/exit-code semantics remain covered.
- No schema, CLI, extensions, `.cerebro/`, command registry shape, approval
  policy, command allow/deny policy, selected verification coverage, daemon,
  external dependency, or container runtime change occurred.

Validation:

- Focused verification runtime tests: `18/0`.
- Related focused tests (`command_sandbox`, `validate`, `architecture`,
  `doc_governance`): `146/0/3`.
- Full AGENTS-equivalent gate: `936/0/0/6`.
