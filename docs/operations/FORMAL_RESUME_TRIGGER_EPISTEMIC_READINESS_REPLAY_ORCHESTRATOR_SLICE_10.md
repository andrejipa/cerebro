# Formal Resume Trigger — Epistemic Readiness Replay Orchestrator Slice 10

status: consumed
created_at: 2026-04-24
state_change: none

## Objective

Replace the repeated operator-side replay script for the self-epistemic
readiness lane with a tested derived helper under
`experiments/epistemic_readiness/`.

The helper must build the complete advisory replay bundle:

- readiness report;
- decision trace;
- trace diff against the checked-in baseline;
- protocol self-audit;
- baseline lifecycle recommendation.

This slice intentionally does not refresh
`CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`. Baseline refresh remains
a separate human-approved operation.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_REPLAY_ORCHESTRATOR_SLICE_10.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
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
- Do not write `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`.
- Do not treat replay success as authority, truth, memory, or permission.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to runtime authority.
- Do not hide source, semantic, risk, guardrail, or traceability drift.

## Acceptance Criteria

- Add a deterministic replay-bundle helper under
  `experiments/epistemic_readiness/`.
- The helper builds readiness report, decision trace, trace diff, protocol
  self-audit, and baseline lifecycle evidence in memory.
- The helper has an explicit writer that writes only declared derived outputs.
- The writer rejects:
  - root-escape output paths;
  - `.cerebro/` targets;
  - `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json` targets.
- The bundle exposes explicit `state_change: none` and advisory-only authority.
- Focused tests prove:
  - bundle construction does not write project files;
  - writer emits only declared derived outputs;
  - baseline targets and `.cerebro/` targets are rejected;
  - bundle summary is stable and non-authoritative.
- Regenerate real self-readiness derived artifacts through the helper.
- Keep final baseline refresh as a separate human-approved operation if drift
  appears.
- `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or
  schema edits;
- helper writes the checked-in baseline;
- helper becomes a runtime gate, permission layer, authority layer, telemetry
  layer, memory writer, or claim graph;
- replay evidence hides drift or converts drift into automatic correction;
- generated output is treated as permission to act;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Consumed on 2026-04-24.

- Implementation:
  - `experiments/epistemic_readiness/replay_bundle.py`
  - `ReplayBundle`
  - `ReplayBundlePaths`
  - `ReplayBundleWriteResult`
  - `build_replay_bundle(...)`
  - `write_replay_bundle(...)`
- Generated evidence, written through the helper:
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json`
  - `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.md`
- Real self-readiness replay through the helper:
  - sources: `17`
  - candidates: `32`
  - findings: `32`
  - ready: `32`
  - blocked: `0`
  - insufficient: `0`
  - baseline_updated: `false`
  - state_change: `none`
- Lifecycle after helper:
  - recommendation: `refresh_candidate_requires_human_approval`
  - required_human_action: `approve_baseline_refresh`
  - action_readiness: `human_approval_required`
  - drift_total: `74`
  - has_regression: `false`
  - self_audit_high_or_blocking_count: `0`
- Boundary proof:
  - helper rejects `.cerebro/` output targets
  - helper rejects root-escape output targets
  - helper rejects `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
    output targets
  - helper does not update the baseline automatically
  - no runtime gate, claim graph, memory write, authority promotion, or
    canonical state mutation was introduced
- Validation:
  - `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `37/0`
  - `tests.test_architecture`: `51/0`
  - `tests.test_doc_governance`: `13/0`
  - Full AGENTS-equivalent gate: `923/0/0/6`
