# Formal Resume Trigger - Epistemic Guard Decision Envelope Oracle - Slice 1

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Build a derived, deterministic, read-only advisory decision-envelope oracle for
concrete action questions.

The slice moves the epistemic-runtime lane from recursive self-closeout toward
applied action evaluation:

```text
Can Cerebro catch a stale, insufficient, ambiguous, or unauthorized action
before an agent treats it as safe to perform?
```

The output is evidence only. It is not permission, truth, runtime authority,
human approval, source registration, memory, a canonical claim graph, or a
runtime gate.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE_SLICE_1.md`
- `experiments/epistemic_guard/**`
- `experiments/lifecycle.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or
  `.cerebro/state.json`.
- Do not mutate any third-party project.
- Do not create a runtime gate, canonical claim graph, source registry, memory
  writer, permission layer, automatic learning layer, or authority promotion
  mechanism.
- Do not promote `claim_extraction`, `claim_evaluation`, or
  `epistemic_readiness` into runtime authority.
- Do not infer negative evidence from silence.
- Do not treat advisory pass, digest equality, approval presence, closeout, or
  no-action as permission.

## Required Output

The experiment must emit a `DecisionEnvelope` with these fields:

- `intent`
- `action_profile`
- `read_set`
- `claim_summary`
- `missing_evidence`
- `stale_claims`
- `conflicts`
- `approval_status`
- `prewrite_guard_status`
- `sufficiency`
- `action_readiness`
- `recommended_human_decision`
- `state_change: none`

## Minimum Fixtures

- stale next action: old diagnostic says create schema, continuity says schema
  exists and Edge Functions are next;
- silence is not negative evidence: source omission produces missing evidence,
  not a fabricated negative claim;
- existing state ambiguity: target has prior `.cerebro/state.json` with no
  handling decision;
- missing trigger for runtime mutation: action touches canonical runtime
  authority without an active trigger;
- approval expired by source-set change: approval read set no longer matches
  the current action read set;
- read/write drift: a planned write target changed after it was read;
- protocol-induced stale source route: protocol points the agent at a stale
  source when newer continuity evidence exists;
- clean advisory report: reversible derived evidence with sufficient support is
  allowed only as an advisory report.

## Acceptance Criteria

- The experiment is local, deterministic, read-only, and non-authoritative.
- Focused tests prove all minimum fixtures.
- Rendered JSON and Markdown surfaces preserve `state_change: none` and the
  non-negotiable distinctions:
  - `registered != true`
  - `retrieved != relevant`
  - `remembered != trusted`
  - `silence != negative evidence`
  - `permission != sufficient evidence`
- A checked-in self-oracle report records the fixture outcomes for audit.
- `experiments/lifecycle.toml`, `observation_center.toml`, `SYSTEM_STATE.md`,
  and `OPPORTUNITY_MAP.md` are updated only after implementation gates pass.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused `experiments.epistemic_guard` tests after implementation.
- Architecture/doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any required gate fails.
- The slice needs edits outside the whitelist.
- The evaluator needs filesystem mutation, runtime authority, source
  registration, canonical claim graph semantics, or `.cerebro/` writes.
- Advisory evidence is framed as permission, truth, memory, or human approval.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Created `experiments/epistemic_guard/` as a deterministic advisory
  decision-envelope oracle over caller-supplied action evidence.
- The oracle emits `DecisionEnvelope` with `intent`, `action_profile`,
  `read_set`, `claim_summary`, `missing_evidence`, `stale_claims`,
  `conflicts`, `approval_status`, `prewrite_guard_status`, `sufficiency`,
  `action_readiness`, `recommended_human_decision`, and `state_change: none`.
- Minimum fixtures are covered: stale next action, silence as missing evidence,
  existing state ambiguity, missing runtime trigger, approval expiry after
  source-set change, read/write drift, protocol-induced stale source route, and
  clean advisory report.
- Checked-in audit output:
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE.{json,md}`.
- Self-oracle summary: `scenario_count=8`, `blocked_or_human_count=7`,
  `advisory_allowed_count=1`.
- Focused validation: `experiments.epistemic_guard` `10/0`.
- Architecture/doc-governance validation after implementation:
  `tests.test_architecture + tests.test_doc_governance` `64/0`.
- Final AGENTS-equivalent gate after closure docs: `923` tests, `0`
  failures, `0` errors, `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `tests/`,
  `core/schema.py`, `.cerebro/state.json`, or third-party project mutation.
