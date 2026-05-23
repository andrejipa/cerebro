# Formal Resume Trigger — Epistemic Guard Pre-Action Stress Slice 4

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Accepted-by: operator instruction "mature sua ideia"

## Objective

Stress the slice-3 pre-action guard surface with degraded operator-facing cases.
The goal is to prove that the report does not become a happy-path-only artifact:
unsafe or underspecified pre-action evidence must remain visible and blocked.

This slice is aggressive maturity work inside the derived `epistemic_guard`
track. It does not create runtime authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_PRE_ACTION_STRESS_SLICE_4.md`
- `experiments/epistemic_guard/**`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_STRESS_MATRIX.md`
- `experiments/lifecycle.toml`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or
  `.cerebro/state.json`.
- Do not mutate target projects or canonical runtime state.
- Do not create a runtime gate, permission layer, canonical claim graph, source
  registry, memory writer, automatic execution path, or authority promotion.
- Do not treat stress pass as permission.
- Do not infer negative evidence from omitted claims or sources.

## Acceptance Criteria

- A deterministic stress matrix covers at least these degraded cases:
  missing `[proposed_action]`, non-`none` expected state change, runtime
  promotion without trigger, stale approval, and read/write drift.
- Each degraded case remains visible as `blocked`,
  `canonical_change_requires_trigger`, or `human_approval_required`.
- The clean case remains allowed only as advisory/derived evidence, not
  permission.
- JSON and Markdown renderers preserve `state_change: none`,
  `stress_pass_is_not_permission`, and `must_not_execute_automatically`.
- Focused tests cover clean pass, degraded blockers, renderer guardrails, and
  matrix all-pass semantics.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused `experiments.epistemic_guard` tests after implementation.
- Architecture/doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any required gate fails.
- The slice needs runtime, schema, core, CLI, extension, test-architecture, or
  `.cerebro/` mutation.
- The matrix output frames stress pass as permission, approval, truth, memory,
  authority, source registration, runtime gate, or claim graph.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Added `experiments/epistemic_guard/pre_action_stress.py` with deterministic
  stress matrix dataclasses, default matrix builder, and JSON/Markdown
  renderers.
- Matrix cases: clean pre-action report, missing `[proposed_action]`,
  mutating expected state, runtime promotion without trigger, stale approval,
  and read/write drift.
- Generated checked-in reports:
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_STRESS_MATRIX.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_STRESS_MATRIX.md`
- Stress summary: `case_count=6`, `pass_count=6`, `fail_count=0`,
  `blocked_or_human_count=5`, `boundary_error_count=2`,
  `state_change=none`.
- Focused validation: `experiments.epistemic_guard.tests.test_epistemic_guard`
  ran `21` tests, `0` failures, `0` errors.
- Architecture/doc-governance validation:
  `tests.test_architecture tests.test_doc_governance` ran `64` tests, `0`
  failures, `0` errors.
- Final AGENTS-equivalent gate before closure update: `923` tests, `0`
  failures, `0` errors, `6` skipped.
- Boundary preserved: no changes to `core/`, `cli/`, `extensions/`,
  `tests/`, `core/schema.py`, `.cerebro/state.json`, or third-party projects.
