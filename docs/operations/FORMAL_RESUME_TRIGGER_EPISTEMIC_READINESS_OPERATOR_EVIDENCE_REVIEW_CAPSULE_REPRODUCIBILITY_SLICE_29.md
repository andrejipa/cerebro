# Formal Resume Trigger — Epistemic Readiness Operator Evidence Review Capsule Reproducibility — Slice 29

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Create a bounded, deterministic, advisory reproducibility checker for the
operator evidence review capsule artifacts created in slice 27.

The checker exists to prove that the checked-in review capsule JSON and
Markdown still match the capsule regenerated from declared current inputs. It
must surface stale, missing, malformed, mutating, root-escaping, and
`.cerebro`-targeting checked artifacts as review blockers without refreshing
artifacts automatically, mutating state, or promoting any advisory evidence
into runtime authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_SLICE_29.md`
- `experiments/epistemic_readiness/operator_evidence_review_capsule_reproducibility.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_CHECK.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_CHECK.md`
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
  evidence artifacts to make the reproducibility check pass.
- Do not infer truth from digest equality.
- Do not infer negative evidence from missing declarations or silence.
- Do not treat the review capsule, reproducibility check, stress matrix,
  decision packet, intake reproducibility, provenance index, or provenance
  stress matrix as permission.

## Acceptance Criteria

- A deterministic advisory reproducibility checker module exists under
  `experiments/epistemic_readiness/`.
- The checker regenerates the operator evidence review capsule from declared
  current inputs and compares both checked JSON and checked Markdown artifacts.
- Clean current checked artifacts remain `none/advisory_report_allowed`.
- Stale, missing, malformed, mutating, root-escaping, and `.cerebro`-targeting
  checked artifacts become `review_blockers/blocked`.
- The checker exposes:
  - `state_change: none`
  - `authority: non-authoritative`
  - artifact count
  - blocker count
  - mismatch count
  - missing artifact count
  - JSON and Markdown digest match status
  - explicit must-not-apply guardrails
- Focused tests cover clean current artifacts, stale checked artifacts,
  missing/malformed artifacts, blocked paths, JSON/Markdown guardrails, and
  incoherent report rejection.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused epistemic readiness tests after implementation.
- Architecture and doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any attempt to touch prohibited paths.
- Any failing required gate.
- Any need to mutate prior evidence artifacts to make the checker pass.
- Any pressure to treat the capsule or reproducibility check as truth,
  permission, memory, source registration, runtime authority, or a canonical
  graph.
- Any stale, malformed, missing, or path-blocked checked artifact that becomes
  invisible, advisory-clear, or non-blocking.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Implemented
  `experiments/epistemic_readiness/operator_evidence_review_capsule_reproducibility.py`.
- Generated
  `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_CHECK.json`.
- Generated
  `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_REVIEW_CAPSULE_REPRODUCIBILITY_CHECK.md`.
- Real output: `reproducibility_status=reproducible`,
  `recommended_human_decision=none`,
  `action_readiness=advisory_report_allowed`, `artifact_count=2`,
  `blocker_count=0`, `mismatch_count=0`, `missing_artifact_count=0`,
  `json_digest_match=true`, and `markdown_digest_match=true`.
- Focused validation: `experiments.epistemic_readiness` `126/0`.
- Architecture/doc-governance validation: `64/0`.
- Full AGENTS-equivalent gate before consumption: `923` tests, `0`
  failures, `0` errors, `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`,
  `core/schema.py`, `tests/test_architecture.py`, or `.cerebro/state.json`
  changes.
