# Formal Resume Trigger — Epistemic Readiness Action Manifest Slice 3

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Make the Cerebro self-readiness rerun consume a checked-in action proposal from
`docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml` instead of
requiring one-off Python construction.

The slice must dogfood the risk-budget and blast-radius evaluator added in
slice 2 by producing a code-generated self-readiness report that includes
repeatable advisory risk evidence.

This is derived evidence only. It is not runtime permission.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_ACTION_MANIFEST_SLICE_3.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `experiments/epistemic_readiness/**`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`.
- Do not touch `cli/`.
- Do not touch `extensions/`.
- Do not touch `core/schema.py`.
- Do not write `.cerebro/`.
- Do not mutate canonical state.
- Do not create a canonical claim graph.
- Do not create a runtime gate.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to authority.
- Do not treat advisory readiness, risk readiness, or manifest presence as
  permission.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- Add a deterministic TOML manifest loader for epistemic-readiness reports.
- The loader parses bounded source entries, baseline metrics, and an optional
  action proposal with blast radius plus risk budget.
- The loader rejects unsafe report paths, `.cerebro/` report targets,
  unsupported schema versions, and any `state_change` other than `none`.
- The existing self-readiness manifest declares a repeatable action proposal
  for regenerating the advisory report.
- The generated self-readiness report includes a `Risk Budget Assessment`
  section produced from the checked-in manifest.
- Focused `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- the implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state,
  or schema edits;
- manifest ingestion becomes permission, authority, or a runtime gate;
- the generated report claims canonical authority;
- path resolution allows root escape or `.cerebro/` writes;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after implementing checked-in TOML manifest ingestion for
`experiments/epistemic_readiness/`.

Delivered:

- `ReadinessManifest` loader for source entries, baseline metrics, and optional
  action proposals.
- `generate_readiness_report_from_manifest(...)` for report generation directly
  from the checked-in manifest.
- `resolve_generated_report_path(...)` guard against root escape and `.cerebro/`
  generated-report targets.
- Updated self-readiness manifest with a bounded action proposal for
  regenerating `CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`.
- Code-produced self-readiness report with `Risk Budget Assessment`.

Validation:

- `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `17/0`.
- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `33/0`.
- `tests.test_architecture` + `tests.test_doc_governance`: `64/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No runtime gate.
- No canonical claim graph.
- No authority promotion.
- `state_change: none` preserved.
