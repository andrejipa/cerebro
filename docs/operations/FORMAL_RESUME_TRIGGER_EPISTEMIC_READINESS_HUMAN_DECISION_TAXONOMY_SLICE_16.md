# Formal Resume Trigger — Epistemic Readiness Human Decision Taxonomy Slice 16

## Status

- status: consumed
- opened_at: 2026-04-24
- owner: Orchestrator
- level: 2
- mode: EXECUTION

## Human Approval

- source: user message on 2026-04-24: "mature sua ideia"
- interpreted_as: continue the Risk-Adaptive Epistemic Runtime lane by hardening the handoff decision vocabulary.
- scope_limit: approval applies only to an advisory human-decision taxonomy under `experiments/epistemic_readiness/` and `docs/operations/`.

## Objective

Implement a deterministic, local, read-only, non-authoritative taxonomy that maps metacognitive handoff `recommended_human_decision` values to:

- compatible `action_readiness` values
- allowed next actions
- forbidden interpretations
- required evidence
- escalation level

The goal is to prevent agents from misreading a handoff recommendation as permission. A decision can request human review, approval, adjudication, missing evidence, or blocker review; it cannot grant runtime authority, mutate state, write memory, create a claim graph, or bypass future triggers.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_HUMAN_DECISION_TAXONOMY_SLICE_16.md`
- `experiments/epistemic_readiness/human_decision_taxonomy.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Read-only inputs:

- `experiments/epistemic_readiness/metacognitive_handoff.py`
- `experiments/epistemic_readiness/handoff_stress_matrix.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_HANDOFF_STRESS_MATRIX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_HANDOFF_STRESS_MATRIX.md`

## Explicit Prohibitions

- Do not touch `core/`.
- Do not touch `cli/`.
- Do not touch `extensions/`.
- Do not touch `core/schema.py`.
- Do not mutate `.cerebro/` or canonical state.
- Do not update the replay baseline.
- Do not integrate the taxonomy into runtime or the replay bundle in this slice.
- Do not create a runtime gate.
- Do not create a canonical claim graph.
- Do not write memory automatically.
- Do not promote or demote authority.
- Do not treat a human decision, approval label, or compatible decision/readiness pair as permission.
- Do not infer negative evidence from silence.

## Stop Conditions

- Any taxonomy entry has `state_change` other than `none`.
- Any taxonomy entry can mutate state or grant permission.
- Any handoff decision is missing from the closed taxonomy.
- Any compatible pair implies automatic action.
- Any incompatible pair is silently accepted.
- The taxonomy requires runtime, schema, CLI, extension, baseline, or canonical state mutation.
- Focused tests fail.
- Architecture/doc governance fails.
- Full AGENTS-equivalent gate fails.

## Acceptance Criteria

- `experiments/epistemic_readiness/human_decision_taxonomy.py` exposes deterministic advisory contract objects and renderers.
- The taxonomy covers exactly: `none`, `acknowledge`, `approve_baseline_refresh`, `adjudicate_conflict`, `provide_missing_evidence`, and `review_blockers`.
- Each entry records compatible readiness values, allowed next actions, forbidden interpretations, required evidence, and escalation level.
- The taxonomy can interpret a handoff decision/readiness pair and flag incompatible pairs without mutating state.
- The taxonomy emits `state_change: none`.
- The taxonomy explicitly preserves:
  - `registered != true`
  - `retrieved != relevant`
  - `remembered != trusted`
  - `silence != negative evidence`
  - human decision labels are not permission
- Tests cover the closed decision set, boundary guarantees, compatible and incompatible interpretation, renderer shape, and duplicate/partial taxonomy rejection.
- Real artifacts are generated at `CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.{json,md}`.
- `observation_center.toml`, `SYSTEM_STATE.md`, and `OPPORTUNITY_MAP.md` record the closure and next candidate.
- Full AGENTS-equivalent gate remains green.

## What This Does Not Authorize

This trigger does not authorize runtime implementation, runtime gating, baseline refresh, canonical authority changes, schema changes, third-party project mutation, automatic learning, memory writes, source registration, state import, replay-bundle integration, or claim-graph persistence.

## Closure

- closed_at: 2026-04-24
- result: consumed
- implementation: `HumanDecisionTaxonomyEntry`, `HumanDecisionTaxonomyReport`, `HumanDecisionInterpretation`, `build_human_decision_taxonomy(...)`, `interpret_handoff_decision(...)`, `render_human_decision_taxonomy_json(...)`, and `render_human_decision_taxonomy_markdown(...)`
- real_artifacts: `CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.json`; `CEREBRO_SELF_EPISTEMIC_HUMAN_DECISION_TAXONOMY.md`
- real_output: `6` decisions, stable order `none`, `acknowledge`, `approve_baseline_refresh`, `adjudicate_conflict`, `provide_missing_evidence`, `review_blockers`; all entries `can_mutate_state=false`; all entries `can_grant_permission=false`
- compatibility: `none -> no_action`; `acknowledge -> advisory_report_allowed|observe_only`; `approve_baseline_refresh -> human_approval_required`; `adjudicate_conflict -> human_approval_required`; `provide_missing_evidence -> human_approval_required`; `review_blockers -> blocked`
- state_change: none
- focused_validation: `experiments.epistemic_readiness 56/0`
- governance_validation: `tests.test_architecture tests.test_doc_governance 64/0`
- final_gate: full AGENTS-equivalent `923/0/0/6`
- next_candidate: `epistemic-readiness-decision-taxonomy-conformance-slice-17`
