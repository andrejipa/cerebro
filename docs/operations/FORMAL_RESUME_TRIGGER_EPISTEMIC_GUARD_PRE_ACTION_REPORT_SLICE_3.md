# Formal Resume Trigger — Epistemic Guard Pre-Action Report Slice 3

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Accepted-by: operator instruction "sem ser conservador, avance"

## Objective

Turn the manifest-driven decision envelope from slice 2 into a concrete
pre-action guard report for one proposed operator action. The report must
consume a bounded declared action manifest, aggregate the resulting advisory
`DecisionEnvelope` evidence, and produce a stable JSON/Markdown pre-action
summary before work is treated as ready to execute.

This slice advances the epistemic-runtime lane aggressively, but it does not
create runtime authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_PRE_ACTION_REPORT_SLICE_3.md`
- `experiments/epistemic_guard/**`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_REPORT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_REPORT.md`
- `experiments/lifecycle.toml`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or
  `.cerebro/state.json`.
- Do not mutate target projects or canonical runtime state.
- Do not create a runtime gate, permission layer, canonical claim graph, source
  registry, automatic memory writer, automatic learning layer, or authority
  promotion.
- Do not treat a pre-action report as approval or permission.
- Do not infer negative evidence from omitted claims or sources.
- Do not read arbitrary project files from the manifest. The manifest declares
  evidence; it does not authorize filesystem discovery.

## Acceptance Criteria

- `experiments/epistemic_guard` can load a bounded pre-action TOML manifest
  with a required `[proposed_action]` table and at least one `[[scenario]]`.
- The pre-action loader reuses the slice-2 decision manifest safety boundary:
  root escape and `.cerebro/` manifest paths are rejected.
- The report aggregates envelope readiness into one advisory disposition while
  preserving blockers, missing evidence, stale claims, conflicts, warnings, and
  guardrail text.
- Missing `[proposed_action]`, duplicate scenario ids, unsafe paths, and
  non-`none` expected state changes fail closed in focused tests.
- A checked-in self pre-action manifest produces checked-in JSON and Markdown
  reports with `state_change: none`.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused `experiments.epistemic_guard` tests after implementation.
- Architecture/doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any required gate fails.
- The slice needs runtime, schema, core, CLI, extension, test-architecture, or
  `.cerebro/` mutation.
- The report output frames guard pass as permission, approval, truth, memory,
  authority, source registration, runtime gate, or claim graph.
- The implementation reads arbitrary source files listed by the manifest
  instead of evaluating declared TOML evidence.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Added `experiments/epistemic_guard/pre_action.py` with
  `ProposedAction`, `PreActionGuardReport`,
  `build_pre_action_guard_report_from_manifest`, and JSON/Markdown renderers.
- The pre-action loader requires `[proposed_action]`, rejects root escape,
  rejects `.cerebro/` manifest paths, preserves the slice-2 manifest safety
  boundary, and fails closed when `expected_state_change` is not `none`.
- Added checked-in self pre-action manifest:
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_MANIFEST.toml`.
- Generated checked-in reports:
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_REPORT.{json,md}`.
- Self pre-action report summary: `envelope_count=1`,
  `blocked_or_human_count=0`, `action_readiness=derived_experiment_allowed`,
  `recommended_human_decision=none`, `state_change=none`.
- Focused validation after implementation: `experiments.epistemic_guard`
  `19/0`.
- Architecture/doc-governance validation after documentation updates:
  `tests.test_architecture + tests.test_doc_governance` `64/0`.
- Final AGENTS-equivalent gate before closure update: `923` tests, `0`
  failures, `0` errors, `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `tests/`,
  `core/schema.py`, `.cerebro/state.json`, or third-party project mutation.
