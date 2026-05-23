# Formal Resume Trigger — Epistemic Readiness Drift Policy Slice 12

status: consumed
created_at: 2026-04-24
state_change: none

## Objective

Add a bounded advisory drift-policy layer to `experiments/epistemic_readiness/`
so future replay drift is classified explicitly before any human decides whether
to acknowledge it, inspect it, approve a baseline refresh, or block the lane.

The policy must mature the replay loop from "drift exists" to "drift has a
proportionate operational disposition" while preserving the boundary:

- replay drift is evidence, not truth;
- replay freshness is not permission;
- baseline refresh is never automatic;
- protocol self-audit candidates are not memory writes;
- policy output is not a runtime gate.

## Human Approval

Approval source: user message on 2026-04-24: "mature sua ideia".

Interpretation: approval to execute the next queued epistemic-readiness slice
aggressively inside `experiments/` and derived docs, with no runtime authority
promotion.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_DRIFT_POLICY_SLICE_12.md`
- `experiments/epistemic_readiness/drift_policy.py`
- `experiments/epistemic_readiness/replay_bundle.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/README.md`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_BASELINE_LIFECYCLE.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.md`
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
- Do not update `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`.
- Do not auto-refresh any replay baseline.
- Do not hide semantic, source, risk, guardrail, or traceability drift.
- Do not treat drift-policy output as permission, truth, memory, or authority.
- Do not automatically promote or demote any protocol rule.

## Acceptance Criteria

- Add a deterministic advisory drift-policy evaluator that consumes trace-diff,
  protocol self-audit, and baseline-lifecycle payloads.
- The evaluator must emit explicit classifications for:
  - no drift;
  - traceability-only drift;
  - source/semantic/metadata drift that is refresh-candidate evidence;
  - regression or high/blocking self-audit drift that blocks refresh.
- The evaluator must emit:
  - `state_change: none`;
  - non-authoritative authority wording;
  - action readiness;
  - required human action;
  - drift disposition reasons;
  - explicit guardrails.
- Integrate the policy into the replay bundle writer as an additional derived
  output pair:
  - `CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.json`
  - `CEREBRO_SELF_EPISTEMIC_DRIFT_POLICY.md`
- Preserve baseline-refresh separation: the policy may propose review or
  approval, but must not update the baseline.
- Focused tests must cover no-drift, traceability-only drift, semantic/source
  drift, blocked regression/high self-audit, malformed/mutating payloads, and
  replay-bundle integration.
- `experiments.epistemic_readiness`, `tests.test_architecture`,
  `tests.test_doc_governance`, and the full AGENTS-equivalent gate must pass.

## Stop Conditions

Stop immediately if:

- the policy requires runtime, schema, state, `core/`, `cli/`, or `extensions/`
  changes;
- policy output is treated as a permission gate;
- baseline refresh becomes automatic;
- `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json` needs to be rewritten;
- semantic drift is hidden as traceability drift;
- self-audit candidates become memory or authority;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Consumed on 2026-04-24.

- Approval source:
  - user message: "mature sua ideia"
  - interpreted as approval to execute the queued drift-policy slice inside
    `experiments/epistemic_readiness/` and derived docs only
- Implemented operation:
  - added `DriftPolicyReport`
  - added `evaluate_drift_policy(...)`
  - added `render_drift_policy_json(...)`
  - added `render_drift_policy_markdown(...)`
  - integrated drift policy into `ReplayBundle`
  - integrated drift policy outputs into `ReplayBundlePaths`
  - regenerated self-readiness report, trace, trace diff, protocol self-audit,
    baseline lifecycle, and drift-policy artifacts through the replay bundle
- Final replay evidence:
  - sources: `18`
  - candidates: `34`
  - findings: `34`
  - ready: `34`
  - blocked: `0`
  - insufficient: `0`
  - lifecycle recommendation: `refresh_candidate_requires_human_approval`
  - lifecycle required_human_action: `approve_baseline_refresh`
  - lifecycle drift_total: `75`
  - has_regression: `false`
  - self_audit_high_or_blocking_count: `0`
  - drift_policy classification: `material_refresh_candidate`
  - drift_policy recommendation: `refresh_candidate_requires_human_approval`
  - drift_policy action_readiness: `human_approval_required`
  - drift_policy required_human_action: `approve_baseline_refresh`
  - state_change: `none`
- Boundary proof:
  - no `.cerebro/` write
  - no canonical state mutation
  - no runtime gate
  - no claim graph
  - no authority promotion or demotion
  - no automatic memory write
  - no automatic baseline refresh
  - `CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json` was not rewritten
- Validation:
  - `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `42/0`
  - `tests.test_architecture`: `51/0`
  - `tests.test_doc_governance`: `13/0`
  - Full AGENTS-equivalent gate: `923/0/0/6`
