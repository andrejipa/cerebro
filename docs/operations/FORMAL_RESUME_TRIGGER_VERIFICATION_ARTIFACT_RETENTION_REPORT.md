# Formal Resume Trigger — Verification Artifact Retention Report

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Close the next verification hardening gap: verification artifacts are now safer
per run, but the runtime does not expose a bounded dry-run view of artifact
retention pressure under `.cerebro/artifacts/verification/`.

This slice creates a read-only retention report that classifies verification
artifact run directories without deleting, archiving, or mutating anything.
The report is evidence for a future apply slice; it is not cleanup permission.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_VERIFICATION_ARTIFACT_RETENTION_REPORT.md`
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
- validation, architecture, and doc-governance tests

## Explicit Non-Authorization

This trigger does not authorize:

- deleting, moving, archiving, truncating, or rewriting any artifact;
- editing `.cerebro/` or canonical state outside normal tests;
- changing `core/schema.py`;
- editing `cli/`;
- editing `extensions/`;
- changing verify command execution, approval policy, command registry shape,
  artifact hash semantics, timeout behavior, or verification coverage;
- adding a retention apply command, daemon, scheduled cleanup, external
  dependency, database, or background service.

## Acceptance Criteria

- A deterministic dry-run helper classifies verification artifact run
  directories.
- Live-referenced verification run directories are never classified as eligible
  for cleanup.
- Recent unreferenced runs are kept separately from cleanup-eligible runs.
- Ambiguous entries remain visible and are never classified as eligible.
- The report includes counts and byte totals sufficient to estimate retention
  pressure.
- Tests prove the report does not mutate artifact files.
- Tests cover live-referenced, recent-unreferenced, cleanup-eligible, missing
  artifact root, and ambiguous non-directory entries.
- No schema fields are added.
- `tests.test_architecture` remains green.
- Full AGENTS-equivalent gate remains green.

## Stop Conditions

- Any need to delete, move, archive, truncate, or rewrite artifact files.
- Any need to change `.cerebro/state.json`, `core/schema.py`, `cli/`,
  `extensions/`, command registry shape, approval policy, command allow/deny
  policy, timeout behavior, or verification coverage.
- Any classification can mark a live-referenced verification artifact run as
  cleanup-eligible.
- Any implementation requires a daemon, scheduler, external dependency,
  database, or background service.
- Any gate failure not directly explained by this slice.

## Closure Evidence

Implemented on 2026-04-25.

- `core/verification_runtime.py` now exposes
  `build_verification_artifact_retention_report(...)` and typed report entries
  for a deterministic dry-run over verification artifact run directories.
- The report classifies entries as `live_referenced`,
  `recent_unreferenced`, `cleanup_eligible`, or `ambiguous_do_not_touch`.
- Live references are derived from current
  `agent_runtime.verification.checks[].artifact_ref` and are never cleanup
  eligible.
- The helper receives the already resolved verification artifact root from the
  caller; it does not declare `.cerebro` runtime paths itself.
- No artifact deletion, move, archive, truncation, rewrite, schema change, CLI
  edit, extension edit, command policy change, timeout behavior change, daemon,
  scheduler, database, external dependency, or canonical state mutation
  occurred.

Validation:

- Focused verification runtime tests: `21/0`.
- Architecture/doc-governance: `64/0`.
- Related validation/sandbox/verification tests: `103/0/3`.
- Full AGENTS-equivalent gate: `939/0/0/6`.
