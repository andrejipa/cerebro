# FORMAL RESUME TRIGGER - Third-Party Trigger Template Conformance Slice 4

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25

## Objective

Add a derived advisory conformance check for third-party triggers created from
`THIRD_PARTY_TRIGGER_TEMPLATE.md`.

The check should make missing required fields, invalid enum values, missing
required narrative sections, and missing reviewer evidence visible before a
third-party trigger is treated as review-ready.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_TRIGGER_TEMPLATE_CONFORMANCE_SLICE_4.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/third_party_trigger_review/__init__.py`
- `experiments/third_party_trigger_review/template_conformance.py`
- `experiments/third_party_trigger_review/tests/test_third_party_trigger_review.py`

Read-only evidence:

- `docs/operations/THIRD_PARTY_TRIGGER_TEMPLATE.md`
- `docs/operations/THIRD_PARTY_TRIGGER_REVIEW_RPG_CAMINHADA_RETROSPECTIVE.md`
- `docs/operations/THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md`

## Explicitly Not Authorized

- Any `core/`, `cli/`, `extensions/`, canonical `tests/`, `core/schema.py`,
  `.cerebro/`, source registration, memory, claim graph, or runtime gate
  change.
- Any third-party target project edit.
- Any browser, Supabase, Docker, Expo, cloud, or network proof.
- Treating template conformance as permission to execute a target trigger.
- Rewriting historical third-party triggers to satisfy the new template.

## Stop Conditions

Stop immediately if:

- the AGENTS-equivalent full gate is red before writes;
- the conformance check needs to inspect target project files;
- implementation needs runtime integration;
- tests require real target project fixtures outside checked-in Python strings;
- the check cannot keep `state_change: none`;
- any whitelist expansion becomes necessary.

## Acceptance Criteria

- `experiments/third_party_trigger_review/template_conformance.py` exists and
  evaluates caller-supplied trigger text only.
- The check reports missing required structured fields.
- The check reports invalid enum values for bounded template fields.
- The check reports missing required narrative sections.
- The check requires reviewer evidence declaring
  `ready_for_human_review` and `state_change: none`.
- A conformant trigger returns `state_change: none`.
- Focused experiment tests pass.
- Architecture/doc-governance focused gate passes.
- Final AGENTS-equivalent full gate passes.

## Closure

Result: consumed on 2026-04-25.

Implemented a derived advisory conformance check:

- `experiments/third_party_trigger_review/template_conformance.py` defines
  `ThirdPartyTriggerTemplateConformance`, finding objects, and
  `check_third_party_trigger_template_conformance(...)`;
- the check evaluates caller-supplied trigger text only and reports missing
  required structured fields, invalid enum values, missing required narrative
  sections, and missing reviewer evidence;
- `experiments/third_party_trigger_review/__init__.py` exports the conformance
  API;
- `experiments/third_party_trigger_review/tests/test_third_party_trigger_review.py`
  covers conformant template shape, missing required fields, invalid enum
  values, missing sections, missing reviewer evidence, and `state_change:
  none`.

Validation:

- focused experiment tests passed `12/0`;
- architecture/doc-governance focused gate passed after implementation;
- final AGENTS-equivalent full gate passed after docs updates.

No target project file, target `.cerebro/`, Cerebro runtime, core, cli,
extension, canonical tests, schema, state, source registration, memory, claim
graph, runtime gate, browser, Supabase, Docker, Expo, cloud, or network surface
was changed.
