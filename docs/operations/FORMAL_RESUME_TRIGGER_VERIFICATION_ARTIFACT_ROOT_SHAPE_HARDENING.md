---
status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: Codex
level: 2
---

# Formal Resume Trigger: Verification Artifact Root Shape Hardening

## Objective

Harden the verification artifact retention dry-run report so an existing
`artifacts/verification` surface with an invalid shape is reported explicitly
instead of being indistinguishable from an empty healthy directory.

## Whitelist

- `core/verification_runtime.py`
- `tests/test_verification_runtime.py`
- `docs/operations/FORMAL_RESUME_TRIGGER_VERIFICATION_ARTIFACT_ROOT_SHAPE_HARDENING.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not delete, move, archive, truncate, or rewrite artifacts.
- Do not add apply-retention behavior.
- Do not touch `cli/`, `extensions/`, `core/schema.py`, `.cerebro/state.json`,
  command policy, approval policy, timeout behavior, or canonical state shape.
- Do not treat retention dry-run output as permission.

## Stop Conditions

- Any architecture/doc-governance or full AGENTS-equivalent gate failure.
- Any mutation outside the whitelist.
- Any behavior that hides an existing non-directory verification root as an
  empty healthy report.

## Acceptance Criteria

- Missing `artifacts/verification` still reports `missing_artifact_root`.
- Existing directory `artifacts/verification` still reports `ok`.
- Existing non-directory `artifacts/verification` reports a distinct invalid
  status with one ambiguous do-not-touch entry.
- No artifact is mutated.
- Focused verification runtime tests, architecture/doc-governance, and full
  AGENTS-equivalent gate pass.

## Closure Evidence

Consumed on 2026-04-25.

Implementation:

- `build_verification_artifact_retention_report(...)` now checks the shape of
  the supplied verification artifact root before enumerating run entries.
- Missing roots still produce `missing_artifact_root`.
- Existing non-directory roots now produce `invalid_artifact_root` with one
  `ambiguous_do_not_touch` entry and zero cleanup-eligible bytes.

Validation:

- `python -m unittest tests.test_verification_runtime -v` — `23/0`.
- `python -m unittest tests.test_architecture tests.test_doc_governance -v`
  — `64/0`.
- Full AGENTS-equivalent gate — `941/0/0/6`.

Non-authorizations preserved:

- No artifact deletion, move, archive, truncation, or rewrite occurred.
- No apply-retention path was added.
- No `cli/`, `extensions/`, `core/schema.py`, `.cerebro/state.json`, command
  policy, approval policy, timeout behavior, or canonical state shape changed.
