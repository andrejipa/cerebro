# Formal Resume Trigger — Epistemic Readiness Operator Evidence Provenance Stress — Slice 26

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Create a bounded, deterministic, advisory stress matrix for the operator
evidence provenance index introduced in slice 25.

The matrix exists to prove degraded provenance evidence remains visible as
advisory blockers instead of being coerced into permission, truth, memory,
authority, source registration, runtime gate, or canonical graph semantics.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_PROVENANCE_STRESS_SLICE_26.md`
- `experiments/epistemic_readiness/operator_evidence_provenance_stress_matrix.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/test_architecture.py`,
  `core/schema.py`, or `.cerebro/state.json`.
- Do not create a runtime gate, canonical graph, source registry, memory store,
  promotion mechanism, demotion mechanism, or second source of truth.
- Do not mutate, refresh, or rewrite prior operator evidence artifacts to make
  the stress matrix pass.
- Do not infer truth from digest equality.
- Do not infer negative evidence from missing declarations or silence.
- Do not promote the provenance index, evidence bundles, reproducibility
  checks, claim extraction, or claim evaluation to runtime authority.

## Acceptance Criteria

- A deterministic advisory stress module exists under
  `experiments/epistemic_readiness/`.
- The scenario set is closed and ordered.
- Required scenarios:
  - clean provenance chain
  - missing artifact
  - malformed JSON artifact
  - mutating artifact
  - root escape
  - `.cerebro/` target
  - duplicate artifact id
  - missing upstream dependency
  - markdown/text-only digest artifact remains advisory and non-blocking
- Clean scenario reports `none/advisory_report_allowed`.
- Degraded scenarios report `review_blockers/blocked` or visible boundary
  errors as appropriate.
- Real generated JSON/Markdown artifacts explicitly declare:
  - `state_change: none`
  - `authority: non-authoritative`
  - scenario count, pass count, fail count, blocker count, and boundary error
    count
  - guardrails that the stress matrix is not permission, truth, memory,
    authority, source registration, runtime gate, canonical graph, claim graph,
    automatic refresh, or automatic learning.
- Focused tests cover the clean matrix, degraded scenarios, closed scenario
  ordering, duplicate scenario rejection, and boundary language in JSON/Markdown.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused epistemic readiness tests after implementation.
- Architecture and doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any attempt to touch prohibited paths.
- Any failing required gate.
- Any pressure to treat the stress matrix as canonical truth, runtime
  authority, source registration, memory, or action permission.
- Any need to mutate prior evidence artifacts to make the stress matrix pass.

## Closure Evidence

- Implemented `experiments/epistemic_readiness/operator_evidence_provenance_stress_matrix.py`.
- Generated `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX.json`.
- Generated `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_STRESS_MATRIX.md`.
- Real output: `scenario_count=9`, `pass_count=9`, `fail_count=0`,
  `all_scenarios_passed=true`, `blocker_count=7`,
  `boundary_error_count=4`, `text_digest_only_count=1`.
- Clean scenarios: `clean_provenance_chain=none/advisory_report_allowed`,
  `text_digest_only_report=none/advisory_report_allowed`.
- Degraded scenarios: `missing_artifact`, `malformed_json`,
  `mutating_artifact`, `root_escape`, `cerebro_state_target`,
  `duplicate_artifact_id`, and `missing_upstream_dependency` all become
  `review_blockers/blocked` with visible blockers or boundary errors.
- Focused validation: `experiments.epistemic_readiness` `111/0`.
- Architecture/doc-governance validation: `64/0`.
- Full AGENTS-equivalent gate: `923` tests, `0` failures, `0` errors,
  `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `core/schema.py`,
  `tests/test_architecture.py`, or `.cerebro/state.json` changes.
