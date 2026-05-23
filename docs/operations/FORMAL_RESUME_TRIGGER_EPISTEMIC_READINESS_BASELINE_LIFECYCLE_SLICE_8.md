# Formal Resume Trigger — Epistemic Readiness Baseline Lifecycle Slice 8

status: consumed
created_at: 2026-04-24
state_change: none

## Objective

Define a safe derived replay-baseline lifecycle for
`experiments/epistemic_readiness/`.

Slice 7 made replay diffs more honest by separating semantic changes from
traceability changes. The next gap is baseline lifecycle: the lane still
compares against an older trace format forever unless an operator manually
decides when a current advisory trace is eligible to become the next comparison
baseline.

This slice must produce a reviewable baseline-refresh proposal. It must not
overwrite `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
automatically. A baseline refresh remains a human-approved derived artifact
operation, not truth, permission, memory, or canonical authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_BASELINE_LIFECYCLE_SLICE_8.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.md`
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
- Do not create hidden telemetry.
- Do not write learned memory automatically.
- Do not apply baseline refresh automatically.
- Do not treat baseline freshness as authority, truth, or permission.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to authority.
- Do not infer negative evidence from silence.
- Do not hide semantic, source, risk, guardrail, or traceability drift.

## Acceptance Criteria

- Add a deterministic baseline lifecycle evaluator under
  `experiments/epistemic_readiness/`.
- The evaluator consumes checked-in trace, trace-diff, and protocol self-audit
  shaped payloads.
- The evaluator emits a stable advisory JSON/Markdown report with:
  - baseline/current labels and digests;
  - semantic/source/traceability drift counts;
  - regression and self-audit high/blocking state;
  - recommendation;
  - required human action;
  - explicit `state_change: none`;
  - explicit no-auto-refresh boundary.
- A no-regression current trace can become a `refresh_candidate`, but only with
  human approval and never by automatic overwrite.
- Regressions or high/blocking self-audit candidates block refresh.
- Focused tests prove:
  - refresh candidate is emitted for clean advisory traces with drift;
  - blocked lifecycle is emitted for regression/high-risk evidence;
  - already-current baseline is detected when no drift exists;
  - mutating or malformed payloads are rejected;
  - no function writes baseline automatically.
- `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or
  schema edits;
- baseline refresh is applied automatically;
- baseline freshness becomes permission, authority, memory, telemetry, or a
  runtime gate;
- lifecycle output hides drift instead of recording it;
- checked-in evidence loading accepts mutating state or unsafe authority;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Consumed on 2026-04-24.

- Implementation:
  - `experiments/epistemic_readiness/baseline_lifecycle.py`
  - `BaselineLifecycleReport`
  - `DriftCounts`
  - `evaluate_baseline_lifecycle(...)`
  - `render_baseline_lifecycle_json(...)`
  - `render_baseline_lifecycle_markdown(...)`
- Generated evidence:
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.md`
- Real self-readiness replay after this slice:
  - candidates: `30`
  - findings: `30`
  - ready: `30`
  - recommendation: `refresh_candidate_requires_human_approval`
  - required_human_action: `approve_baseline_refresh`
  - action_readiness: `human_approval_required`
  - drift_total: `73`
  - has_regression: `false`
  - self_audit_high_or_blocking_count: `0`
  - state_change: `none`
- Boundary proof:
  - `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json` was not
    overwritten by the lifecycle evaluator.
  - Baseline refresh remains a separate human-approved operation.
  - No runtime gate, claim graph, memory write, authority promotion, or
    canonical state mutation was introduced.
- Validation:
  - `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `33/0`
  - `tests.test_architecture`: `51/0`
  - `tests.test_doc_governance`: `13/0`
  - Full AGENTS-equivalent gate: `923/0/0/6`
