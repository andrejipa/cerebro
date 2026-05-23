---
status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: Codex
level: 2
---

# Formal Resume Trigger: Verification Artifact Retention Race Hardening

## Objective

Harden the verification artifact retention dry-run report so transient filesystem
race conditions or unreadable entries remain visible as non-cleanup evidence
instead of crashing the report or silently treating degraded evidence as safe.

## Whitelist

- `core/verification_runtime.py`
- `tests/test_verification_runtime.py`
- `docs/operations/FORMAL_RESUME_TRIGGER_VERIFICATION_ARTIFACT_RETENTION_RACE_HARDENING.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not delete, move, archive, truncate, or rewrite verification artifacts.
- Do not add an apply-retention path.
- Do not change command execution, timeout behavior, approval policy, command
  allow/deny policy, or selected verification coverage.
- Do not touch `core/schema.py`, `cli/`, `extensions/`, `.cerebro/state.json`,
  or canonical state shape.
- Do not treat this advisory dry-run report as permission to clean artifacts.

## Stop Conditions

- Any architecture gate failure.
- Any full AGENTS-equivalent gate failure.
- Any mutation outside the whitelist.
- Any report behavior that marks unreadable, disappearing, or non-directory
  entries cleanup eligible.

## Acceptance Criteria

- Disappearing entries during scan are reported as `ambiguous_do_not_touch`.
- Entries whose metadata cannot be read are reported as
  `ambiguous_do_not_touch`.
- Live-referenced entries remain never cleanup eligible.
- Existing retention report behavior remains stable for normal directories.
- Focused verification runtime tests, architecture/doc-governance, and full
  AGENTS-equivalent gate pass.

## Closure Evidence

Consumed on 2026-04-25.

Implementation:

- `core/verification_runtime.py` now reads verification artifact entry metadata
  through a guarded helper before classifying entries.
- Metadata failures are classified as `ambiguous_do_not_touch` with a visible
  reason instead of crashing the dry-run or being treated as cleanup eligible.
- Entry size calculation now catches filesystem errors while traversing child
  files and preserves the advisory `state_change: none` boundary.

Validation:

- `python -m unittest tests.test_verification_runtime -v` — `22/0`.
- `python -m unittest tests.test_architecture tests.test_doc_governance -v`
  — `64/0`.
- Full AGENTS-equivalent gate — `940/0/0/6`.

Non-authorizations preserved:

- No artifact deletion, move, archive, truncation, or rewrite occurred.
- No apply-retention path was added.
- No `cli/`, `extensions/`, `core/schema.py`, `.cerebro/state.json`, command
  policy, approval policy, timeout behavior, or canonical state shape changed.
