# Formal Resume Trigger — Epistemic Readiness Trace Diff Slice 5

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Compare two advisory decision traces and produce deterministic replay evidence
about epistemic drift between them.

This slice extends the existing `experiments/epistemic_readiness/` track from
"produce a trace" to "compare traces". The comparator must identify changes in:

- bounded source reads;
- extracted claim candidates;
- evaluated findings;
- risk assessment;
- readiness summary;
- guardrails and boundary assertions.

The output is advisory replay evidence only. It may suggest human review or a
future trigger, but it is not permission, authority, telemetry, a runtime gate,
or a canonical claim graph.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_TRACE_DIFF_SLICE_5.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
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
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to authority.
- Do not treat trace presence, trace diff presence, readiness, or risk
  readiness as permission.
- Do not infer negative evidence from silence.
- Do not apply promotion or demotion automatically from a diff.

## Acceptance Criteria

- Add deterministic trace comparison under `experiments/epistemic_readiness/`.
- The comparator loads checked-in trace JSON safely and rejects non-object
  payloads, unsupported schema versions, and any `state_change` other than
  `none`.
- The diff reports added, removed, kept, and changed source reads, candidates,
  and findings.
- The diff reports readiness/risk movement and flags advisory regressions when
  blocked or insufficient counts increase, action readiness worsens, or risk
  budget status degrades.
- The diff output preserves `state_change: none` and explicit
  non-authoritative/advisory boundary.
- A Markdown diff and JSON diff are generated from the self-readiness traces.
- Focused `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or
  schema edits;
- trace comparison becomes permission, authority, hidden telemetry, or a runtime
  gate;
- the diff applies promotion/demotion instead of reporting it;
- checked-in trace loading allows mutation or accepts non-advisory state;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after implementing advisory trace diff and replay
comparison inside `experiments/epistemic_readiness/`.

Delivered:

- `TraceDiff` contract object for non-authoritative replay comparison.
- `load_decision_trace_json(...)` for loading checked-in trace JSON while
  rejecting non-object payloads, unsupported schema versions, and any
  `state_change` other than `none`.
- `compare_decision_traces(...)` for source-read, candidate, finding, summary,
  risk-assessment, and guardrail comparison.
- Candidate/finding comparison uses semantic signatures so line-shift changes
  surface as `claim_id` / `evidence_span` drift instead of false add/remove
  churn.
- `render_trace_diff_json(...)` and `render_trace_diff_markdown(...)` stable
  renderers.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
  preserved from the slice 4 trace.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json` and
  `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md` generated
  from baseline/current self-readiness traces.

Generated current trace summary:

- `source_count`: `12`.
- `candidates_extracted`: `27`.
- `findings_evaluated`: `27`.
- `ready_count`: `27`.
- `blocked_count`: `0`.
- `insufficient_count`: `0`.
- `action_readiness`: `derived_experiment_allowed`.
- `state_change`: `none`.

Generated trace diff summary:

- `added_source_reads`: `1`.
- `removed_source_reads`: `0`.
- `changed_source_reads`: `2`.
- `added_candidates`: `1`.
- `removed_candidates`: `0`.
- `changed_candidates`: `26`.
- `added_findings`: `1`.
- `removed_findings`: `0`.
- `changed_findings`: `26`.
- `guardrail_changes`: `0`.
- `has_regression`: `false`.
- `advisory_readiness`: `no_regression_observed`.
- `state_change`: `none`.

Validation:

- `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `24/0`.
- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `40/0`.
- `tests.test_architecture` + `tests.test_doc_governance`: `64/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No hidden telemetry.
- No runtime gate.
- No canonical claim graph.
- No authority promotion or demotion.
- `state_change: none` preserved.
