# Formal Resume Trigger — Epistemic Readiness Operator Evidence Bundle, Slice 20

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- accepted_by_operator: explicit continuation request, "mature sua ideia"
- mode: execution
- level: 2

## Objective

Package the current advisory operator decision surface into one reproducible
operator evidence bundle. The bundle makes handoff cheaper by carrying the
operator decision packet, operator packet stress matrix, source artifact
digests, guardrails, and must-not-apply boundaries in one stable JSON/Markdown
pair.

This slice is intentionally aggressive inside the derived layer: it improves
operator usability and cross-agent handoff without changing the runtime
authority model.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_BUNDLE_SLICE_20.md`
- `experiments/epistemic_readiness/operator_evidence_bundle.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.md`
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
- Do not promote claim extraction, claim evaluation, metacognitive handoff,
  decision taxonomy conformance, drift policy, baseline lifecycle, operator
  packet, stress matrix, or evidence bundle output into authority.
- Do not treat the evidence bundle as permission.
- Do not treat artifact digests as truth.
- Do not update replay baselines.
- Do not write memory automatically.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- A deterministic advisory bundle helper exists under
  `experiments/epistemic_readiness/`.
- The helper accepts already-materialized advisory payload mappings rather than
  reading files internally.
- The bundle validates:
  - operator packet schema, authority, `state_change: none`, and guardrails
  - operator packet stress matrix schema, authority, `state_change: none`, and
    guardrails
  - optional source artifacts as digest-only inputs
- The bundle records:
  - current operator packet decision and readiness
  - current operator packet conformance result
  - stress scenario/pass/fail coverage
  - boundary error count
  - stable SHA-256 digests for included inputs
  - guardrails and must-not-apply boundaries
- JSON and Markdown renderers expose that the bundle is not permission, not
  memory, not authority, not a runtime gate, and not a claim graph.
- Focused tests prove clean bundle construction, source artifact digest
  inclusion, malformed input rejection, renderer boundary text, and report
  constructor rejection of duplicate or mutating inputs.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.{json,md}`
  are generated from the implemented helper.

## Required Gates

- Initial full AGENTS-equivalent gate before implementation.
- Focused `experiments.epistemic_readiness` tests after implementation.
- `tests.test_architecture` and `tests.test_doc_governance` after docs updates.
- Final full AGENTS-equivalent gate before marking this trigger consumed.

## Stop Conditions

- Any bundle output grants permission, hides stress failures, hides boundary
  errors, updates baselines, writes memory, mutates state, creates a claim graph,
  or becomes runtime authority.
- Any digest is treated as truth instead of reproducibility evidence.
- Any edit outside the whitelist is required.
- Any gate turns red and cannot be fixed inside the whitelist.

## Closure

- result: consumed
- implementation: `OperatorEvidenceBundleReport`, `OperatorEvidenceBundleInput`, `build_operator_evidence_bundle(...)`, `render_operator_evidence_bundle_json(...)`, and `render_operator_evidence_bundle_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.json`; `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE.md`
- real_output: `packet_recommended_human_decision=none`; `packet_action_readiness=no_action`; `packet_conformance_passed=true`; stress matrix `6` scenarios, `6` pass, `0` fail, `all_scenarios_passed=true`; `boundary_error_count=1`; `input_count=6`; `source_artifact_count=4`; `state_change: none`
- focused_validation: `experiments.epistemic_readiness` `74` tests, `0` failures, `0` errors
- governance_validation: `tests.test_architecture` + `tests.test_doc_governance` `64` tests, `0` failures, `0` errors
- final_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- next_candidate: `epistemic-readiness-operator-evidence-bundle-stress-slice-21`
