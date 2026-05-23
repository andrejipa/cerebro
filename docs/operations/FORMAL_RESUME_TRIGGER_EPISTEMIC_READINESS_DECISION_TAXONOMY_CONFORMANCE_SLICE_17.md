# Formal Resume Trigger — Epistemic Readiness Decision Taxonomy Conformance, Slice 17

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- accepted_by_operator: explicit continuation request, "sem ser conservador, avance"
- mode: execution
- level: 2

## Objective

Add a bounded advisory conformance layer that compares the real
`HandoffStressMatrixReport` decision/readiness pairs against the
`HumanDecisionTaxonomyReport` compatibility contract.

The slice must prove that the stress-matrix outputs are covered by the
taxonomy and that incompatible pairs are surfaced instead of hidden.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_DECISION_TAXONOMY_CONFORMANCE_SLICE_17.md`
- `experiments/epistemic_readiness/decision_taxonomy_conformance.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`.
- Do not touch `cli/`.
- Do not touch `extensions/`.
- Do not touch `core/schema.py`.
- Do not alter `.cerebro/state.json`.
- Do not create a runtime gate.
- Do not create a canonical claim graph.
- Do not promote stress matrix, taxonomy, conformance, claim extraction, claim
  evaluation, or epistemic readiness output into authority.
- Do not treat conformance pass as permission.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- A deterministic advisory conformance report exists under
  `experiments/epistemic_readiness/`.
- The real stress matrix is evaluated against the real taxonomy.
- All real stress-matrix decision/readiness pairs are classified as covered.
- The report preserves `state_change: none`.
- JSON and Markdown renderers expose the non-authoritative boundary.
- Focused tests cover the real pass case, an incompatible pair, duplicate/partial
  case rejection, and renderer boundary text.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.{json,md}`
  are generated from the implemented helper.

## Required Gates

- Initial full AGENTS-equivalent gate before implementation.
- Focused `experiments.epistemic_readiness` tests after implementation.
- `tests.test_architecture` and `tests.test_doc_governance` after docs updates.
- Final full AGENTS-equivalent gate before marking this trigger consumed.

## Stop Conditions

- Any conformance output grants permission.
- Any incompatible pair is hidden or coerced to pass.
- Any output mutates state, writes memory, updates replay baselines, creates a
  claim graph, or becomes runtime authority.
- Any edit outside the whitelist is required.
- Any gate turns red and cannot be fixed inside the whitelist.

## Closure

- result: consumed
- implementation: `DecisionTaxonomyConformanceCase`, `DecisionTaxonomyConformanceReport`, `evaluate_decision_taxonomy_conformance(...)`, `render_decision_taxonomy_conformance_json(...)`, and `render_decision_taxonomy_conformance_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.json`; `CEREBRO_SELF_EPISTEMIC_DECISION_TAXONOMY_CONFORMANCE.md`
- real_output: `5` cases, `5` pass, `0` fail, `all_cases_passed=true`, `state_change: none`
- focused_validation: `experiments.epistemic_readiness` `60` tests, `0` failures, `0` errors
- governance_validation: `tests.test_architecture` + `tests.test_doc_governance` `64` tests, `0` failures, `0` errors
- final_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- next_candidate: `epistemic-readiness-operator-decision-packet-slice-18`
