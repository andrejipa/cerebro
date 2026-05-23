# Formal Resume Trigger - Epistemic Guard Decision Manifest - Slice 2

Status: consumed
Opened: 2026-04-24
Consumed: 2026-04-24
Level: 2

## Objective

Make the `epistemic_guard` decision-envelope oracle re-executable from an
explicit checked-in TOML manifest.

Slice 1 proved the envelope model with in-code fixtures. Slice 2 matures that
idea into an operator-ready evidence packet:

```text
Given a declared action question, declared reads/writes, declared evidence
claims, declared requirements, declared approval context, and declared
prewrite digests, emit the same advisory DecisionEnvelope deterministically.
```

This remains derived evidence only. A manifest is not permission, not human
approval, not source registration, not memory, not a canonical claim graph, not
a runtime gate, and not authority.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_DECISION_MANIFEST_SLICE_2.md`
- `experiments/epistemic_guard/**`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_MANIFEST.toml`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_MANIFEST_REPORT.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_MANIFEST_REPORT.md`
- `experiments/lifecycle.toml`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or
  `.cerebro/state.json`.
- Do not mutate target projects or the Cerebro runtime state.
- Do not create a runtime gate, canonical claim graph, source registry, memory
  writer, permission layer, automatic learning layer, or authority promotion.
- Do not treat manifest presence as permission.
- Do not infer negative evidence from omitted claims or omitted sources.
- Do not read arbitrary project files from the manifest. The manifest declares
  evidence; it does not authorize filesystem discovery.

## Acceptance Criteria

- `experiments/epistemic_guard` can load a bounded TOML manifest into
  `DecisionScenario` inputs.
- Manifest path handling rejects root escape and `.cerebro/` manifest paths.
- Manifest content rejects unknown/missing schema versions, duplicate scenario
  ids, duplicate source ids inside a scenario, duplicate claim ids inside a
  scenario, and claims pointing at undeclared sources.
- The loader preserves optional requirements, approval context, prewrite
  digests, and protocol notes.
- A checked-in self-manifest produces checked-in JSON and Markdown reports with
  `state_change: none`.
- Focused tests cover clean and degraded manifest behavior.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused `experiments.epistemic_guard` tests after implementation.
- Architecture/doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any required gate fails.
- The slice needs runtime, schema, core, CLI, extension, test-architecture, or
  `.cerebro/` mutation.
- The manifest loader starts reading arbitrary source files instead of declared
  TOML evidence.
- Any output frames manifest pass as permission, truth, memory, authority, or
  human approval.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Added `experiments/epistemic_guard/manifest.py` with a bounded TOML manifest
  loader and evaluator entry point.
- The loader rejects root escape, `.cerebro/` manifest paths, missing or wrong
  `schema_version`, duplicate scenario ids, duplicate source ids, duplicate
  claim ids, duplicate requirement ids, and claims pointing at undeclared
  sources.
- Manifest support preserves action profile, declared reads/writes, source
  declarations, claim declarations, evidence requirements, approval context,
  prewrite digests, and protocol notes.
- Added checked-in self-manifest:
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_MANIFEST.toml`.
- Generated checked-in reports:
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_DECISION_MANIFEST_REPORT.{json,md}`.
- Manifest report summary: `scenario_count=3`, `blocked_or_human_count=2`,
  `advisory_allowed_count=0`, `derived_experiment_allowed_count=1`.
- Focused validation after implementation: `experiments.epistemic_guard`
  `15/0`.
- Architecture/doc-governance validation after implementation:
  `tests.test_architecture + tests.test_doc_governance` `64/0`.
- Final AGENTS-equivalent gate before closure update: `923` tests, `0`
  failures, `0` errors, `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `tests/`,
  `core/schema.py`, `.cerebro/state.json`, or third-party project mutation.
