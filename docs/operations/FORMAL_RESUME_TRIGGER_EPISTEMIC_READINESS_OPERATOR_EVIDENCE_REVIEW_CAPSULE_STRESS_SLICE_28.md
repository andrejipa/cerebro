# Formal Resume Trigger — Epistemic Readiness Operator Evidence Review Capsule Stress — Slice 28

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Create a bounded, deterministic, advisory stress matrix for the operator
evidence review capsule created in slice 27.

The matrix exists to prove that degraded capsule inputs remain visible as
review blockers. It must test missing, malformed, mutating, root-escaping,
`.cerebro`-targeting, stale-reproducibility, failed-stress, and
provenance-blocker inputs without granting permission, refreshing artifacts,
mutating state, or promoting any advisory evidence into runtime authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_SLICE_28.md`
- `experiments/epistemic_readiness/operator_evidence_review_capsule_stress_matrix.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/test_architecture.py`,
  `core/schema.py`, or `.cerebro/state.json`.
- Do not create a runtime gate, canonical evidence graph, claim graph, source
  registry, memory store, promotion mechanism, demotion mechanism, or second
  source of truth.
- Do not mutate, refresh, rewrite, regenerate, or normalize prior operator
  evidence artifacts to make the stress matrix pass.
- Do not infer truth from digest equality.
- Do not infer negative evidence from missing declarations or silence.
- Do not treat the review capsule, stress matrix, passing scenarios, decision
  packet, reproducibility check, provenance index, or provenance stress matrix
  as permission.

## Acceptance Criteria

- A deterministic advisory stress matrix module exists under
  `experiments/epistemic_readiness/`.
- The scenario set is closed, ordered, and rejects duplicates or partial
  matrices.
- Clean capsule evidence remains `none/advisory_report_allowed`.
- Every degraded scenario becomes `review_blockers/blocked`.
- Boundary violations for root escapes and `.cerebro/` targets remain visible
  as review blockers, not exceptions hidden from the operator.
- The matrix exposes:
  - `state_change: none`
  - `authority: non-authoritative`
  - scenario counts
  - pass/fail counts
  - degraded blocker counts
  - boundary error counts
  - per-scenario observed capsule readiness
  - explicit must-not-apply guardrails
- Focused tests cover the clean scenario, all degraded scenarios, boundary
  blocker visibility, JSON/Markdown guardrails, and incoherent matrix
  rejection.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused epistemic readiness tests after implementation.
- Architecture and doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any attempt to touch prohibited paths.
- Any failing required gate.
- Any need to mutate prior evidence artifacts to make the matrix pass.
- Any pressure to treat the capsule or matrix as truth, permission, memory,
  source registration, runtime authority, or a canonical graph.
- Any degraded scenario that becomes invisible, advisory-clear, or
  non-blocking.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Implemented
  `experiments/epistemic_readiness/operator_evidence_review_capsule_stress_matrix.py`.
- Generated
  `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX.json`.
- Generated
  `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_STRESS_MATRIX.md`.
- Real output: `scenario_count=9`, `pass_count=9`, `fail_count=0`,
  `all_scenarios_passed=true`, `blocker_count=15`,
  `degraded_blocker_count=15`, `input_blocker_count=5`,
  `missing_review_evidence_count=4`, `boundary_error_count=2`.
  `clean_review_capsule` remains `none/advisory_report_allowed`; missing
  packet, malformed reproducibility, mutating provenance, root escape,
  `.cerebro` target, stale reproducibility, failed upstream stress, and
  provenance blocker inputs all become `review_blockers/blocked` with visible
  review blockers.
- Focused validation: `experiments.epistemic_readiness` `120/0`.
- Architecture/doc-governance validation: `64/0`.
- Full AGENTS-equivalent gate before consumption: `923` tests, `0` failures,
  `0` errors, `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `core/schema.py`,
  `tests/test_architecture.py`, or `.cerebro/state.json` changes.
