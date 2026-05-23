# Formal Resume Trigger — Epistemic Readiness Operator Evidence Provenance Index — Slice 25

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Create a bounded, deterministic, advisory provenance index for checked-in
operator-facing epistemic evidence artifacts.

The index exists to help an operator see which advisory artifacts exist, which
digests they currently have, which upstream evidence they depend on, and whether
any artifact is missing, malformed, mutating, or dependency-incomplete.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_READINESS_OPERATOR_EVIDENCE_PROVENANCE_INDEX_SLICE_25.md`
- `experiments/epistemic_readiness/operator_evidence_provenance_index.py`
- `experiments/epistemic_readiness/__init__.py`
- `experiments/epistemic_readiness/tests/test_epistemic_readiness.py`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_INDEX.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_INDEX.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/test_architecture.py`,
  `core/schema.py`, or `.cerebro/state.json`.
- Do not create a runtime gate, canonical graph, source registry, memory store,
  promotion mechanism, demotion mechanism, or second source of truth.
- Do not auto-refresh prior artifacts.
- Do not infer truth from digest match.
- Do not infer negative evidence from missing declarations or silence.
- Do not promote claim extraction, claim evaluation, evidence bundles,
  reproducibility checks, or this provenance index to runtime authority.

## Acceptance Criteria

- A deterministic advisory module exists under `experiments/epistemic_readiness/`.
- The artifact set is closed and ordered.
- Each indexed artifact reports:
  - artifact id
  - relative path
  - artifact format
  - SHA-256 digest when present
  - parse status
  - schema version when declared
  - authority when declared
  - state_change when declared
  - upstream dependency ids
  - extracted summary fields
  - blockers when missing, malformed, mutating, root-escaping, duplicated, or
    dependency-incomplete
- Real generated JSON/Markdown artifacts explicitly declare:
  - `state_change: none`
  - `authority: non-authoritative`
  - `action_readiness: advisory_report_allowed` when no blockers exist
  - guardrails that the index is not a canonical graph, not a source registry,
    not a memory store, and not permission to act.
- Focused tests cover clean chains, missing artifacts, malformed JSON, mutating
  artifacts, root escape, `.cerebro/` exclusion, duplicate ids, missing
  dependencies, and boundary language in JSON/Markdown.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused epistemic readiness tests after implementation.
- Architecture and doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any attempt to touch prohibited paths.
- Any failing required gate.
- Any pressure to treat the provenance index as canonical truth, runtime
  authority, source registration, memory, or action permission.
- Any need to mutate prior evidence artifacts to make the index pass.

## Closure Evidence

- Implemented `experiments/epistemic_readiness/operator_evidence_provenance_index.py`.
- Generated `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_INDEX.json`.
- Generated `docs/operations/CEREBRO_SELF_EPISTEMIC_OPERATOR_EVIDENCE_PROVENANCE_INDEX.md`.
- Real output: `artifact_count=20`, `present_count=20`,
  `dependency_edge_count=39`, `blocker_count=0`,
  `recommended_human_decision=none`,
  `action_readiness=advisory_report_allowed`,
  `digest_manifest=d254a139135ddb7f46f29c8e28e3f8252894244ecb6bb2b74aee6eb9b99f4ef8`.
- Focused validation: `experiments.epistemic_readiness` `107/0`.
- Architecture/doc-governance validation: `64/0`.
- Full AGENTS-equivalent gate: `923` tests, `0` failures, `0` errors,
  `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `core/schema.py`,
  `tests/test_architecture.py`, or `.cerebro/state.json` changes.
