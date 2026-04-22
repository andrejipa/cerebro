# Operational Signals Suggestions Closure

## Date

- `2026-04-20`

## Scope Closed

- `experiments/operational_signals/suggestions/`

This closure applies to expansion of the current advisory tripwire sub-layer. It does not deprecate the parent derived layer `experiments/operational_signals/`, which remains valid as a manual, non-authoritative observability surface.

## Final Judgement

- overall classification: `marginal`
- safety/noise profile: `acceptable`
- broad utility on real corpus: `not validated`

The current state is:

- `detect_stale_system_state` is kept as a narrow advisory rule
- `detect_export_surface_gap` remains non-validated on the real corpus
- no third rule should be added by default from this evidence state

## Evidence

### Author-curated evaluation

- `detect_stale_system_state` cleared the local labelled dataset
- `detect_export_surface_gap` also cleared its local labelled dataset

These results proved only that conservative tripwires could be implemented and measured. They did not prove real-corpus utility.

### External non-curated validation

- real-artifact validation later classified the sub-layer as `marginal`
- one narrow true positive remained on Cerebro's own stale snapshot pattern
- `detect_export_surface_gap` did not validate on the real corpus

See:

- [OPERATIONAL_INSUFFICIENCY_SIGNALS.md](/d:/projetos_cli/cerebro/docs/operations/OPERATIONAL_INSUFFICIENCY_SIGNALS.md)

### Directory-wide read-only scan

A wider scan across the four previously used real-project corpora inspected `6163` text-like files and produced:

- `0` `STALE_INFORMATION` hits
- `0` `INSUFFICIENT_EXPORT_SURFACE` hits

Project breakdown:

- `IRPF e Caixa Rural`: `213` files, `0` hits
- `estoque_pioneira`: `664` files, `0` hits
- `rpg_caminhada`: `2242` files, `0` hits
- `Resolução Humaita Codex`: `3044` files, `0` hits

This did not falsify the narrow stale-snapshot rule. It did show that the current suggestion layer has negligible coverage on the external corpora already used by this repository.

## Decision

- keep `detect_stale_system_state`
- keep `detect_export_surface_gap` documented as non-validated
- stop expansion of `suggestions/` by default
- wait for new operational evidence before revisiting this sub-layer

## What This Does Not Mean

- it does not reject `experiments/operational_signals/` as a whole
- it does not authorize removal of the existing narrow rule
- it does not authorize promoting the sub-layer
- it does not authorize a third rule without fresh evidence

## Reopen Condition

Reopen this sub-layer only if at least one of the following becomes true:

- a new tripwire can be defined from a pattern already observed in non-curated real artifacts
- manual operational-signals records start showing a repeated failure shape that maps cleanly to a conservative advisory rule
- a future real-corpus validation demonstrates useful, low-noise coverage beyond the current narrow stale-snapshot case
