# FORMAL RESUME TRIGGER - Third-Party Trigger Review Slice 1

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25

## Objective

Create a derived advisory experiment that reviews proposed third-party triggers
against the third-party dogfood runbook before execution.

The experiment should make role drift, missing dogfood value, missing proof cost,
missing target `.cerebro/` handling, missing rollback/cleanup, and required
consolidation visible before an agent starts more target work.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_TRIGGER_REVIEW_SLICE_1.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/lifecycle.toml`
- `experiments/third_party_trigger_review/__init__.py`
- `experiments/third_party_trigger_review/contract.py`
- `experiments/third_party_trigger_review/reviewer.py`
- `experiments/third_party_trigger_review/render.py`
- `experiments/third_party_trigger_review/README.md`
- `experiments/third_party_trigger_review/tests/test_third_party_trigger_review.py`

## Explicitly Not Authorized

- Any `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, `.cerebro/`,
  source registration, memory, claim graph, or runtime gate change.
- Any third-party target project edit.
- Any browser, Supabase, Docker, Expo, cloud, or network proof.
- Treating an advisory review pass as permission to execute a target trigger.

## Stop Conditions

Stop immediately if:

- the AGENTS-equivalent full gate is red before writes;
- the review needs to mutate or inspect third-party target files directly;
- the implementation needs runtime integration;
- tests require target project fixtures outside checked-in Python strings;
- the experiment cannot keep `state_change: none`;
- any whitelist expansion becomes necessary.

## Acceptance Criteria

- `experiments/third_party_trigger_review/` exists with README and explicit
  advisory-only boundaries.
- The reviewer accepts a complete third-party trigger text.
- The reviewer blocks or warns on missing `dogfood_value`.
- The reviewer blocks target `.cerebro/` ambiguity.
- The reviewer recommends consolidation after too many consecutive
  target-mutating slices.
- The reviewer blocks runtime/Cerebro authority boundary drift.
- Rendered output includes `state_change: none`.
- Focused experiment tests pass.
- Architecture/doc-governance focused gate passes.
- Final AGENTS-equivalent full gate passes.

## Closure

Result: consumed on 2026-04-25.

Implemented a derived advisory experiment:

- `experiments/third_party_trigger_review/contract.py` defines review input,
  findings, report shape, readiness states, and `state_change: none`;
- `experiments/third_party_trigger_review/reviewer.py` checks caller-supplied
  trigger text for `target_path`, `slice_kind`, `dogfood_value`, `proof_cost`,
  source roles, target `.cerebro/` handling, rollback, cleanup, stop conditions,
  forbidden paths, consecutive target-slice consolidation risk, and runtime
  boundary drift;
- `experiments/third_party_trigger_review/render.py` emits Markdown with the
  advisory boundary;
- `experiments/third_party_trigger_review/tests/test_third_party_trigger_review.py`
  covers complete trigger readiness, missing dogfood value, target `.cerebro/`
  ambiguity, consolidation requirement after three target-mutating slices,
  runtime boundary drift, and rendered `state_change: none`;
- `experiments/lifecycle.toml` now lists the experiment as active.

Validation:

- focused experiment tests passed `6/0`;
- architecture/doc-governance focused gate passed `64/0`;
- final AGENTS-equivalent full gate passed after docs updates.

No target project file, target `.cerebro/`, Cerebro runtime, core, cli,
extension, canonical tests, schema, state, source registration, memory, claim
graph, runtime gate, browser, Supabase, Docker, Expo, cloud, or network surface
was changed.
