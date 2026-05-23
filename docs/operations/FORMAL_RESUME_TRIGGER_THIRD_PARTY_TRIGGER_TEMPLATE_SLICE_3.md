# FORMAL RESUME TRIGGER - Third-Party Trigger Template Slice 3

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25

## Objective

Create a strict reusable template for future third-party project triggers.

The template must convert the runbook, dogfood lessons, and `rpg_caminhada`
retrospective into an operator-facing trigger shape that prevents the two main
failures observed in the pilot:

- product-work drift without explicit Cerebro learning value;
- long runs of target-mutating slices without consolidation.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_TRIGGER_TEMPLATE_SLICE_3.md`
- `docs/operations/THIRD_PARTY_TRIGGER_TEMPLATE.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

Read-only evidence may include:

- `docs/operations/THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md`
- `docs/operations/THIRD_PARTY_DOGFOOD_LESSONS.md`
- `docs/operations/THIRD_PARTY_TRIGGER_REVIEW_RPG_CAMINHADA_RETROSPECTIVE.md`
- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_TRIGGER_RETROSPECTIVE_SLICE_2.md`

## Explicitly Not Authorized

- Any `core/`, `cli/`, `extensions/`, canonical `tests/`, `core/schema.py`,
  `.cerebro/`, source registration, memory, claim graph, or runtime gate change.
- Any third-party target project edit.
- Any browser, Supabase, Docker, Expo, cloud, network, or target runtime proof.
- Any claim that the template itself grants permission to execute target work.
- Any rewrite of historical `rpg_caminhada` triggers.

## Stop Conditions

Stop immediately if:

- the AGENTS-equivalent full gate is red before writes;
- the template needs runtime integration;
- the template tries to become a canonical state/schema artifact;
- the template cannot preserve reviewer/advisory-only semantics;
- any whitelist expansion becomes necessary.

## Acceptance Criteria

- `THIRD_PARTY_TRIGGER_TEMPLATE.md` exists.
- The template includes mandatory structured fields for:
  `target_path`, `slice_kind`, `dogfood_value`, `proof_cost`,
  `cleanup_required`, `target_cerebro_handling`, source roles, allowed paths,
  forbidden paths, rollback, stop conditions, and consolidation counter.
- The template clearly separates target product value from Cerebro dogfood value.
- The template requires applying `experiments/third_party_trigger_review/`
  before execution, while stating that a pass is not permission.
- The template preserves the three-target-mutating-slices consolidation stop.
- Live projections point to the template as the next standard entry point for
  third-party trigger drafting.
- Architecture/doc-governance focused gate passes.
- Final AGENTS-equivalent full gate passes.

## Closure

Result: consumed on 2026-04-25.

Implemented `THIRD_PARTY_TRIGGER_TEMPLATE.md` as a strict reusable drafting
surface for future third-party triggers.

The template requires:

- structured `[third_party]`, `[source_roles]`, `[boundaries]`, and
  `[risk_budget]` blocks;
- explicit separation of target product value from Cerebro dogfood value;
- source-set sufficiency statements;
- target `.cerebro/` handling;
- allowed/forbidden Cerebro and target paths;
- proof cost, cleanup, rollback, stop conditions, and target report shape;
- reviewer evidence before execution;
- the three-target-mutating-slices consolidation stop.

Validation:

- architecture/doc-governance focused gate passed `64/0`;
- `observation_center.toml` parsed successfully;
- template content verification found `dogfood_value`, `proof_cost`,
  `target_cerebro_handling`, `ready_for_human_review`, consolidation language,
  and explicit non-authorization language;
- final AGENTS-equivalent full gate passed after docs updates.

No target project file, target `.cerebro/`, Cerebro runtime, core, cli,
extension, canonical tests, schema, state, source registration, memory, claim
graph, runtime gate, browser, Supabase, Docker, Expo, cloud, or network surface
was changed.
