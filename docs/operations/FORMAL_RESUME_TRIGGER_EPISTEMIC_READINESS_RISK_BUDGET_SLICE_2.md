# Formal Resume Trigger — Epistemic Readiness Risk Budget Slice 2

status: consumed
created_at: 2026-04-24
consumed_at: 2026-04-24
state_change: none

## Objective

Implement a bounded advisory risk-budget and blast-radius evaluator inside
`experiments/epistemic_readiness/`.

The evaluator must turn the policy from
`docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md` into repeatable derived
evidence for advisory reports:

- declared action profile;
- declared blast radius;
- declared risk budget;
- computed required gate;
- computed action readiness;
- human approval requirement;
- stop conditions.

This is derived evidence only. It is not runtime permission.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_RISK_BUDGET_SLICE_2.md`
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
- Do not create a canonical claim graph.
- Do not create a runtime gate.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` to authority.
- Do not treat advisory readiness as permission.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- Add deterministic risk-budget / blast-radius contract objects.
- Add a deterministic evaluator with no filesystem writes.
- Integrate risk assessment into readiness reports without changing
  `state_change: none`.
- Render risk budget evidence in Markdown.
- Cover at least:
  - reversible derived experiment;
  - docs-only historical rewrite risk;
  - canonical runtime/schema change requiring G4;
  - high uncertainty plus broad blast radius blocking action;
  - budget overrun;
  - missing rollback evidence.
- Focused `experiments.epistemic_readiness` tests pass.
- `tests.test_architecture` and `tests.test_doc_governance` pass.
- Full AGENTS-equivalent gate passes.

## Stop Conditions

Stop immediately if:

- the implementation needs `core/`, `cli/`, `extensions/`, `.cerebro/`, state,
  or schema edits;
- risk assessment is used as runtime permission;
- any report claims authority beyond advisory evidence;
- full gate fails for a reason not corrected inside this whitelist.

## Closure Evidence

Closed on 2026-04-24 after implementing advisory risk-budget and blast-radius
evaluation inside `experiments/epistemic_readiness/`.

Delivered:

- `ActionProposal`, `BlastRadiusDeclaration`, `RiskBudget`, and
  `RiskAssessment` contract objects.
- `evaluate_risk_budget(...)` deterministic evaluator.
- Optional risk assessment integration in `generate_readiness_report(...)`.
- Markdown rendering section `Risk Budget Assessment`.
- README boundary update preserving advisory-only/non-authoritative posture.

Validation:

- `experiments.epistemic_readiness.tests.test_epistemic_readiness`: `14/0`.
- `experiments.claim_extraction` + `experiments.claim_evaluation` +
  `experiments.epistemic_readiness`: `30/0`.
- `tests.test_architecture` + `tests.test_doc_governance`: `64/0`.
- Full AGENTS-equivalent gate: `923/0/0/6`.

Boundary:

- No `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema edits.
- No runtime gate.
- No canonical claim graph.
- No authority promotion.
- `state_change: none` preserved.
