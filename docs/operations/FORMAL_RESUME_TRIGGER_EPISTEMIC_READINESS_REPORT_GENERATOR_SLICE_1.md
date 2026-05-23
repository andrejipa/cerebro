# FORMAL RESUME TRIGGER - EPISTEMIC READINESS REPORT GENERATOR SLICE 1

status: consumed
created_at: 2026-04-24
accepted_by: operator direction to advance Risk-Adaptive Epistemic Runtime without waiting on further conceptual work
state_change: none
consumed_at: 2026-04-24
result: derived advisory report generator implemented

## Objective

Implement a bounded, tested, advisory-only epistemic-readiness report generator
under `experiments/epistemic_readiness/`.

The generator replaces one-off operator scripts with repeatable code that:

- accepts a source manifest;
- reads bounded text heads only;
- runs `experiments.claim_extraction.extract_candidates`;
- runs `experiments.claim_evaluation.evaluate_claims`;
- emits a stable Markdown report with `state_change: none`;
- includes baseline comparison hooks;
- exposes action-readiness as advisory evidence only.

## Blast Radius

```toml
[blast_radius]
writes = [
  "docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_REPORT_GENERATOR_SLICE_1.md",
  "docs/operations/observation_center.toml",
  "docs/operations/SYSTEM_STATE.md",
  "docs/operations/OPPORTUNITY_MAP.md",
  "experiments/epistemic_readiness/**",
  "experiments/lifecycle.toml",
]
reads = [
  "AGENTS.md",
  "docs/operations/FREEZE_POLICY.md",
  "docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md",
  "docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md",
  "experiments/claim_extraction/**",
  "experiments/claim_evaluation/**",
]
authority_impact = "advisory"
runtime_impact = "none"
state_impact = "none"
third_party_impact = "none"
reversibility = "high"
rollback = "git-revert"
gate_level = "G2"
promotion_path = "requires-trigger"
demotion_path = "archive-derived-experiment"
stop_conditions = [
  "any runtime authority is implied",
  "any write under .cerebro is attempted",
  "any mutation outside whitelist is needed",
  "focused tests or full gate fail",
]
```

## Risk Budget

```toml
[risk_budget]
max_writes = 10
allowed_paths = [
  "docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_REPORT_GENERATOR_SLICE_1.md",
  "docs/operations/observation_center.toml",
  "docs/operations/SYSTEM_STATE.md",
  "docs/operations/OPPORTUNITY_MAP.md",
  "experiments/epistemic_readiness/**",
  "experiments/lifecycle.toml",
]
allowed_authority_impact = "advisory"
allowed_runtime_impact = "none"
max_irreversibility = "high"
required_rollback_evidence = "git-revert"
human_approval_required = false
```

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_REPORT_GENERATOR_SLICE_1.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `experiments/epistemic_readiness/**`
- `experiments/lifecycle.toml`

Read-only:

- `AGENTS.md`
- `docs/operations/FREEZE_POLICY.md`
- `docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `experiments/claim_extraction/**`
- `experiments/claim_evaluation/**`

## Prohibitions

- Do not edit `core/`.
- Do not edit `cli/`.
- Do not edit `extensions/`.
- Do not edit root `tests/`.
- Do not edit `.cerebro/`.
- Do not edit `core/schema.py`.
- Do not create a runtime gate.
- Do not create a canonical claim graph.
- Do not treat report readiness as permission.
- Do not mutate third-party projects.
- Do not call network/model services.

## Acceptance Criteria

- Package `experiments/epistemic_readiness/` exists with README, contracts,
  generator, renderer, and focused tests.
- Generator accepts a manifest and reads only bounded heads.
- Generator rejects unsafe manifest paths such as `.cerebro/` and paths outside
  the requested root.
- Generator runs claim extraction and claim evaluation.
- Report exposes:
  - source set;
  - candidate count;
  - finding count;
  - ready count;
  - blocked count;
  - insufficient count;
  - baseline comparison when supplied;
  - action readiness;
  - epistemic guardrails;
  - `state_change: none`.
- Report remains advisory/read-only/non-authoritative.
- Focused tests pass.
- Architecture/doc-governance checks pass.
- Full AGENTS-equivalent gate passes before closure.

## Stop Conditions

Stop immediately if:

- any implementation wants to write under `.cerebro/`;
- report output is treated as runtime permission;
- claim extraction/evaluation are promoted into authority;
- a canonical claim graph is introduced;
- a root test, `core/`, `cli/`, `extensions/`, state, or schema edit becomes
  necessary;
- a gate turns red.

## Closure Evidence

- Implemented package: `experiments/epistemic_readiness/`
- Focused tests: `experiments.epistemic_readiness.tests.test_epistemic_readiness`
- Integration checks: `experiments.claim_extraction.tests.test_claim_extraction`
  and `experiments.claim_evaluation.tests.test_claim_evaluation`
- Lifecycle entry added: `experiments/lifecycle.toml`
- Boundary preserved: derived, read-only, advisory-only, non-authoritative.
- Runtime implementation remains unauthorized.
