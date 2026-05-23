# Formal Resume Trigger — Epistemic Readiness Identity Stability Slice 7

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Reduce epistemic-readiness replay noise by separating stable semantic claim
identity from volatile evidence traceability.

Slice 6 protocol self-audit identified `evidence_identity_churn`: many
candidate/finding entries changed only because generated `claim_id` and
`evidence_span` moved while the underlying claim stayed the same. This slice
must preserve that evidence drift, but stop treating it as semantic claim churn.

The intended model is:

- stable semantic identity answers: "is this the same claim?"
- evidence traceability answers: "did the proof location or generated evidence
  id move?"
- replay regression answers: "did readiness, authority, sufficiency, risk, or
  guardrails degrade?"

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_IDENTITY_STABILITY_SLICE_7.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md`
- `experiments/claim_extraction/**`
- `experiments/claim_evaluation/**`
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
- Do not apply promotion, demotion, deprecation, or quarantine.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to authority.
- Do not treat identity stability as permission.
- Do not infer negative evidence from silence.
- Do not hide evidence-span drift; separate it from semantic churn.

## Acceptance Criteria

- `ClaimCandidate` exposes a stable semantic identity that excludes
  `claim_id` and `evidence_span`.
- `ClaimCandidate` exposes a separate evidence identity that preserves the
  source/evidence location for traceability.
- Decision traces include semantic/evidence identity fields without changing
  `state_change: none`.
- Trace diff compares candidates/findings by stable semantic identity and
  separates traceability-only changes from semantic changes.
- Markdown/JSON trace diff output exposes traceability changes explicitly.
- Protocol self-audit no longer classifies line/id movement as semantic identity
  churn, while still surfacing large evidence-traceability drift for review.
- Focused tests prove:
  - semantic identity survives line-span movement;
  - traceability drift remains visible;
  - semantic claim changes still appear as real changes or add/remove;
  - advisory/non-authoritative/state-change boundaries hold.
- `experiments.claim_extraction`, `experiments.claim_evaluation`, and
  `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or
  schema edits;
- identity stability hides evidence-span drift rather than reclassifying it;
- trace diffs become permission, authority, telemetry, runtime gates, or memory;
- stable identity is treated as truth, registration, or claim-graph authority;
- checked-in evidence loading accepts mutating state or unsafe authority;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after separating stable semantic identity from evidence
traceability in the derived epistemic-readiness lane.

Delivered:

- `ClaimCandidate.semantic_id`, derived from semantic claim fields and excluding
  `claim_id` / `evidence_span`.
- `ClaimCandidate.evidence_id`, derived from semantic identity plus
  source/evidence location.
- Decision trace JSON now includes `semantic_id` and `evidence_id` for
  candidates and findings.
- Trace diff now uses `candidate_semantic_identity` as identity basis and
  reports `traceability_changed` separately from semantic `changed`.
- Protocol self-audit now distinguishes semantic `evidence_identity_churn` from
  evidence-only `evidence_traceability_drift`.
- Claim extraction and epistemic-readiness README boundaries updated to explain
  the split.

Generated self-readiness summary:

- `source_count`: `14`.
- `candidate_count`: `29`.
- `finding_count`: `29`.
- `ready_count`: `29`.
- `blocked_count`: `0`.
- `insufficient_count`: `0`.
- `state_change`: `none`.

Generated trace-diff summary:

- source reads: `3` added, `0` removed, `2` changed,
  `0` traceability-changed.
- candidates: `3` added, `0` removed, `0` semantically changed,
  `26` traceability-changed.
- findings: `3` added, `0` removed, `0` semantically changed,
  `26` traceability-changed.
- `has_regression`: `false`.
- `advisory_readiness`: `no_regression_observed`.

Generated protocol self-audit summary:

- `candidate_count`: `2`.
- `high_or_blocking_count`: `0`.
- `action_readiness`: `advisory_report_allowed`.
- candidate categories:
  - `evidence_traceability_drift`;
  - `source_surface_drift`.

Validation:

- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `45/0`.
- `tests.test_architecture` + `tests.test_doc_governance` plus focused derived
  checks: `109/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No hidden telemetry.
- No runtime gate.
- No canonical claim graph.
- No authority promotion or demotion.
- No automatic memory write or learned-rule application.
- `state_change: none` preserved.
