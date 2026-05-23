# Formal Resume Trigger — Epistemic Readiness Protocol Self-Audit Slice 6

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Create a bounded advisory protocol self-audit layer for
`experiments/epistemic_readiness/`.

This slice consumes derived evidence already produced by the epistemic-readiness
track:

- self-readiness report;
- structured decision trace;
- advisory trace diff;
- risk/readiness summary;
- guardrails and boundary assertions.

It must emit review candidates about degraded protocol behavior, weak
guardrails, replay drift, excessive evidence churn, or human-review needs. It
must not write memory, apply learning, promote/demote authority, or act as a
runtime gate.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_PROTOCOL_SELF_AUDIT_SLICE_6.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_BASELINE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_TRACE_DIFF.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md`
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
- Do not treat self-audit candidates as permission.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- Add deterministic protocol self-audit under `experiments/epistemic_readiness/`.
- The self-audit consumes trace-diff/report-shaped evidence and emits advisory
  review candidates only.
- Candidates include stable ids, categories, severity, evidence, recommendation,
  and explicit `state_change: none`.
- The self-audit detects at least:
  - readiness/regression evidence;
  - guardrail weakening;
  - risk-budget degradation;
  - excessive candidate/finding churn without regression;
  - missing or malformed anti-permission boundary.
- The generated Markdown/JSON self-audit artifacts preserve
  non-authoritative/advisory boundary and anti-noise language.
- Focused `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or
  schema edits;
- self-audit writes memory or learned facts automatically;
- self-audit findings become permission, authority, telemetry, or runtime gates;
- self-audit applies promotion, demotion, deprecation, or quarantine instead of
  recommending review;
- checked-in evidence loading accepts mutating state or unsafe authority;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after implementing advisory protocol self-audit candidates
inside `experiments/epistemic_readiness/`.

Delivered:

- `ProtocolAuditCandidate` contract object for review-only protocol findings.
- `ProtocolSelfAuditReport` contract object with anti-noise guardrails.
- `load_trace_diff_json(...)` for loading checked-in trace-diff JSON while
  rejecting non-object payloads, unsupported schema versions, unsupported
  authority, and any `state_change` other than `none`.
- `audit_protocol_from_trace_diff(...)` for deriving self-audit candidates from
  trace-diff evidence.
- `render_protocol_self_audit_json(...)` and
  `render_protocol_self_audit_markdown(...)` stable renderers.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.json` and
  `docs/operations/CEREBRO_SELF_EPISTEMIC_PROTOCOL_SELF_AUDIT.md` generated
  from the self-readiness trace diff.

Generated self-audit summary:

- `candidate_count`: `2`.
- `high_or_blocking_count`: `0`.
- `action_readiness`: `advisory_report_allowed`.
- `state_change`: `none`.
- candidate categories:
  - `evidence_identity_churn`;
  - `source_surface_drift`.

Validation:

- `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `27/0`.
- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `43/0`.
- `tests.test_architecture` + `tests.test_doc_governance`: `64/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No hidden telemetry.
- No runtime gate.
- No canonical claim graph.
- No authority promotion or demotion.
- No automatic memory write or learned-rule application.
- `state_change: none` preserved.
