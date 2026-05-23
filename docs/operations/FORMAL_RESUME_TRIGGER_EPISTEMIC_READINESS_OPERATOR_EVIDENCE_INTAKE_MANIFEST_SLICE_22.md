# Formal Resume Trigger - Epistemic Readiness Operator Evidence Intake Manifest, Slice 22

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- accepted_by_operator: explicit continuation request, "mature sua ideia"
- mode: execution
- level: 2

## Objective

Add a manifest-driven intake layer for the current advisory operator evidence
surface. The layer reads only declared advisory JSON artifacts, recomputes
stable SHA-256 digests, validates non-mutating boundaries, blocks stale,
missing, mutating, root-escaping, duplicate, or undeclared critical inputs, and
builds an operator evidence bundle report from the declared inputs.

This slice is intentionally aggressive inside `experiments/`: it turns the
manual handoff bundle into a reproducible intake protocol without granting
permission, changing runtime authority, registering sources, writing memory,
updating baselines, mutating state, or creating a canonical claim graph.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_INTAKE_MANIFEST_SLICE_22.md`
- `experiments/epistemic_readiness/operator_evidence_intake_manifest.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.md`
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
- Do not promote claim extraction, claim evaluation, readiness reports,
  metacognitive handoff, decision taxonomy conformance, drift policy, baseline
  lifecycle, operator packet, stress matrix, evidence bundle, bundle stress
  matrix, or intake manifest output into authority.
- Do not treat the intake report as permission.
- Do not treat digest equality as truth.
- Do not update replay baselines.
- Do not register sources.
- Do not write memory automatically.
- Do not infer negative evidence from silence.

## Acceptance Criteria

- A deterministic advisory intake helper exists under
  `experiments/epistemic_readiness/`.
- The helper loads a TOML manifest with `schema_version = "1"`,
  `state_change = "none"`, and authority
  `non-authoritative; advisory operator evidence intake manifest only`.
- The manifest declares a root, generated report paths, and a closed set of
  `[[artifacts]]` entries with `artifact_id`, `path`, `role`, and optional
  `expected_digest`.
- The helper reads only manifest-declared JSON files under the declared root.
- The helper blocks:
  - missing artifacts
  - root escape attempts
  - non-JSON artifact paths
  - malformed JSON roots
  - mutating payloads
  - duplicate artifact ids
  - missing required operator packet or packet stress matrix inputs
  - digest mismatches when an expected digest is declared
- A clean manifest builds an advisory operator evidence bundle from:
  - `operator_decision_packet`
  - `operator_packet_stress_matrix`
  - source advisory artifacts
- The clean real report exposes `input_count = 6`,
  `source_artifact_count = 4`, packet readiness `no_action`, packet decision
  `none`, stress matrix `6` scenarios, `6` pass, `0` fail, and
  `state_change = none`.
- JSON and Markdown renderers expose that the intake report is not permission,
  not memory, not authority, not a runtime gate, not a claim graph, and that
  digest equality is not truth.
- Focused tests prove clean manifest intake, missing artifact blocking, stale
  digest blocking, root escape blocking, mutating payload blocking, duplicate
  artifact id rejection, renderer boundary text, and constructor rejection of
  mutating reports.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.{json,md}`
  are generated from the implemented helper and manifest.

## Required Gates

- Initial full AGENTS-equivalent gate before implementation.
- Focused `experiments.epistemic_readiness` tests after implementation.
- `tests.test_architecture` and `tests.test_doc_governance` after docs updates.
- Final full AGENTS-equivalent gate before marking this trigger consumed.

## Stop Conditions

- Any intake output grants permission, hides blockers, hides stale input,
  hides malformed input, hides boundary errors, updates baselines, writes
  memory, registers sources, mutates state, creates a claim graph, or becomes
  runtime authority.
- Any digest equality is treated as truth instead of reproducibility evidence.
- Any edit outside the whitelist is required.
- Any gate turns red and cannot be fixed inside the whitelist.

## Closure

- result: consumed
- implementation: `OperatorEvidenceIntakeArtifact`, `OperatorEvidenceIntakeManifest`, `OperatorEvidenceIntakeInput`, `OperatorEvidenceIntakeReport`, `load_operator_evidence_intake_manifest(...)`, `build_operator_evidence_intake_report(...)`, `build_operator_evidence_intake_report_from_manifest(...)`, `render_operator_evidence_intake_report_json(...)`, and `render_operator_evidence_intake_report_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_MANIFEST.toml`; `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.json`; `CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_INTAKE_REPORT.md`
- real_output: `recommended_human_decision=none`; `action_readiness=advisory_report_allowed`; `blocked=false`; `blocker_count=0`; `input_count=6`; `source_artifact_count=4`; all six declared input digests match expected values; generated bundle summary reports packet `none/no_action`, packet conformance passed, stress matrix `6` scenarios, `6` pass, `0` fail, `all_scenarios_passed=true`, `boundary_error_count=1`; `state_change: none`
- focused_validation: `experiments.epistemic_readiness` `86` tests, `0` failures, `0` errors
- governance_validation: `tests.test_architecture` + `tests.test_doc_governance` `64` tests, `0` failures, `0` errors
- final_gate: full AGENTS-equivalent `923` tests, `0` failures, `0` errors, `6` skipped
- next_candidate: `epistemic-readiness-operator-evidence-intake-stress-slice-23`
