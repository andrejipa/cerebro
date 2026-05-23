# FORMAL RESUME TRIGGER - Third-Party Dogfood Lessons Consolidation

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25

## Objective

Consolidate the `rpg_caminhada` third-party pilot into operational Cerebro
guidance before any further third-party product feature expansion.

The goal is to convert observed evidence into docs-only management rules:
how Cerebro should run third-party projects, when to stop target work, how to
separate target product value from Cerebro capability learning, and how to keep
third-party work auditable without treating target reports as canonical Cerebro
state.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_THIRD_PARTY_DOGFOOD_LESSONS_CONSOLIDATION.md`
- `docs/operations/THIRD_PARTY_DOGFOOD_LESSONS.md`
- `docs/operations/THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

## Explicitly Not Authorized

- Any `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or `.cerebro/`
  mutation.
- Any new runtime command, source registration behavior, claim graph, runtime
  gate, memory write, or authority promotion.
- Any edit to `D:\projetos_cli\pessoais\rpg_caminhada` or any other third-party
  project.
- Any browser, Supabase, Docker, Expo, cloud, or target-app proof.
- Treating dogfood lessons as automatic future permission.

## Stop Conditions

Stop immediately if:

- the AGENTS-equivalent full gate is red before writes;
- a lesson requires runtime implementation instead of documentation;
- a proposed rule would retroactively declare target project reports canonical
  Cerebro truth;
- any whitelist expansion becomes necessary;
- the docs imply further target product feature work is already authorized.

## Acceptance Criteria

- `THIRD_PARTY_DOGFOOD_LESSONS.md` records concrete lessons from the
  `rpg_caminhada` pilot.
- `THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md` defines an operational runbook for
  future third-party management.
- The runbook defines explicit stop lines between dogfood and product work.
- `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, and `observation_center.toml` point
  the next move toward Cerebro-side third-party management hardening, not more
  target product features.
- Architecture/doc-governance focused gate passes.
- Final AGENTS-equivalent full gate passes.

## Closure

Result: consumed on 2026-04-25.

Implemented docs-only consolidation:

- `THIRD_PARTY_DOGFOOD_LESSONS.md` records concrete lessons from the
  `rpg_caminhada` dogfood pilot;
- `THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md` defines the repeatable operating
  model for future third-party project management;
- `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, and `observation_center.toml` now
  point the next move to Cerebro-side third-party management hardening.

The consolidation explicitly stops further `rpg_caminhada` product-feature
expansion until Cerebro absorbs the dogfood lessons. No target project file,
target `.cerebro/`, Cerebro runtime, core, cli, extension, test, schema, state,
source registration, claim graph, memory, browser proof, Supabase, Docker, Expo,
or cloud surface was changed by this slice.

Validation:

- initial AGENTS-equivalent full gate passed `923/0/0/6`;
- architecture/doc-governance focused gate passed after docs changes;
- final AGENTS-equivalent full gate passed after docs changes.
