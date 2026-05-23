# Formal Resume Trigger — Epistemic Readiness Operator Evidence Bundle Stress, Slice 21

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- accepted_by_operator: explicit continuation request, "sem ser conservador, avance"
- mode: execution
- level: 2

## Objective

Stress the Slice 20 operator evidence bundle under degraded and malformed
inputs. The goal is to prove that a clean bundle remains advisory and that
missing, mutating, malformed, stale, duplicate, or digest-mismatched evidence is
blocked or exposed instead of hidden.

This slice is intentionally aggressive inside the derived layer: it hardens the
operator handoff surface without changing runtime authority, source registry,
memory, schema, or canonical state.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_BUNDLE_STRESS_SLICE_21.md`
- `experiments/epistemic_readiness/operator_evidence_bundle_stress_matrix.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.md`
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
  packet, stress matrix, evidence bundle, or evidence bundle stress output into
  authority.
- Do not treat stress pass as permission.
- Do not treat artifact digests as truth.
- Do not update replay baselines.
- Do not write memory automatically.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- A deterministic advisory stress matrix helper exists under
  `experiments/epistemic_readiness/`.
- The helper does not read files internally and accepts already-materialized
  advisory payload mappings.
- The stress matrix covers this closed scenario set in stable order:
  - `clean_bundle`
  - `missing_operator_packet`
  - `mutating_operator_packet`
  - `malformed_stress_matrix`
  - `mutating_source_artifact`
  - `duplicate_input_id`
  - `digest_summary_mismatch`
- Clean input remains `recommended_human_decision=none` and
  `action_readiness=no_action`.
- Degraded scenarios become `recommended_human_decision=review_blockers` and
  `action_readiness=blocked`, with visible blocker or boundary-error text.
- JSON and Markdown renderers expose that the stress matrix is not permission,
  not memory, not authority, not a runtime gate, not a claim graph, and not
  proof of truth.
- Focused tests prove closed scenario coverage, malformed input visibility,
  duplicate input rejection, digest mismatch visibility, renderer boundary text,
  and constructor rejection of duplicate or mutating scenarios.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.{json,md}`
  are generated from the implemented helper.

## Required Gates

- Initial full AGENTS-equivalent gate before implementation.
- Focused `experiments.epistemic_readiness` tests after implementation.
- `tests.test_architecture` and `tests.test_doc_governance` after docs updates.
- Final full AGENTS-equivalent gate before marking this trigger consumed.

## Stop Conditions

- Any stress output grants permission, hides malformed input, hides stale input,
  hides boundary errors, updates baselines, writes memory, mutates state,
  creates a claim graph, or becomes runtime authority.
- Any digest is treated as truth instead of reproducibility evidence.
- Any edit outside the whitelist is required.
- Any gate turns red and cannot be fixed inside the whitelist.

## Closure

- result: consumed
- implementation: `OperatorEvidenceBundleStressScenario`, `OperatorEvidenceBundleStressMatrixReport`, `build_operator_evidence_bundle_stress_matrix(...)`, `render_operator_evidence_bundle_stress_matrix_json(...)`, and `render_operator_evidence_bundle_stress_matrix_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.json`; `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_BUNDLE_STRESS_MATRIX.md`
- real_output: `7` scenarios, `7` pass, `0` fail, `all_scenarios_passed=true`, `blocker_count=6`, `boundary_error_count=6`; `clean_bundle=none/no_action`; `missing_operator_packet`, `mutating_operator_packet`, `malformed_stress_matrix`, `mutating_source_artifact`, `duplicate_input_id`, and `digest_summary_mismatch` all become `review_blockers/blocked` with visible errors; `state_change: none`
- focused_validation: `experiments.epistemic_readiness` `78` tests, `0` failures, `0` errors
- governance_validation: `tests.test_architecture` + `tests.test_doc_governance` `64` tests, `0` failures, `0` errors
- final_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- next_candidate: `epistemic-readiness-operator-evidence-intake-manifest-slice-22`
