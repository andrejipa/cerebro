# Formal Resume Trigger — Epistemic Readiness Decision Trace Slice 4

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Generate a structured advisory decision trace from the same checked-in manifest
that produces `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`.

The trace must make epistemic self-audit and replay machine-readable:

- manifest metadata;
- bounded source reads;
- extracted candidate ids;
- evaluated finding ids;
- risk assessment;
- action readiness;
- explicit report/trace-is-not-permission guardrails.

This is derived evidence only. It is not runtime permission.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_DECISION_TRACE_SLICE_4.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
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
- Do not treat advisory readiness, risk readiness, trace presence, or manifest
  presence as permission.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- Add deterministic trace generation under `experiments/epistemic_readiness/`.
- Trace output is JSON, stable, machine-readable, and includes source reads,
  candidate ids, finding ids, risk assessment, action readiness, and guardrails.
- The manifest declares a generated trace path and the loader rejects unsafe
  trace paths, `.cerebro/` trace targets, unsupported schema versions, and any
  `state_change` other than `none`.
- The generated trace preserves `state_change: none` and explicit
  non-authoritative/advisory boundary.
- Focused `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- the implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state,
  or schema edits;
- trace generation becomes permission, authority, hidden telemetry, or a
  runtime gate;
- the trace claims canonical authority;
- path resolution allows root escape or `.cerebro/` writes;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after implementing structured advisory decision traces
inside `experiments/epistemic_readiness/`.

Delivered:

- `DecisionTrace` contract object for advisory replay evidence.
- `build_decision_trace(...)` for deriving trace payloads from the same manifest
  and readiness report used by Markdown output.
- `render_decision_trace_json(...)` stable JSON renderer.
- `generated_trace` support in `ReadinessManifest`.
- `resolve_generated_trace_path(...)` guard against root escape and `.cerebro/`
  generated-trace targets.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json` generated from
  `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`.

Generated trace summary:

- `source_count`: `11`.
- `candidates_extracted`: `26`.
- `findings_evaluated`: `26`.
- `ready_count`: `26`.
- `blocked_count`: `0`.
- `insufficient_count`: `0`.
- `action_readiness`: `derived_experiment_allowed`.
- `state_change`: `none`.

Validation:

- `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `20/0`.
- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `36/0`.
- `tests.test_architecture` + `tests.test_doc_governance`: `64/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No hidden telemetry.
- No runtime gate.
- No canonical claim graph.
- No authority promotion.
- `state_change: none` preserved.
