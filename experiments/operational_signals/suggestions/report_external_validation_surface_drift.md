# Operational Insufficiency Suggestions — External Validation (`surface drift`)

- authority: `derived-advisory-only`
- non_authoritative: `true`
- read_only: `true`
- validation_mode: `real artifacts, narrow Cerebro-specific surface`
- date: `2026-04-21`

## Result

- overall: `narrow-Cerebro-specific`
- rule: `detect_current_surface_drift`
- curated verdict remains: `accept_for_staged_promotion`

## Scope

This rule is intentionally narrow:

- it compares the current surface only across:
  - `README.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/PHASE_CLOSURE.md`
- it extracts only the first `Last suite result: N tests` match from each doc
- it emits only when at least two docs expose extractable counts and those counts drift by `>= 5`

## Real Cerebro Cases Checked

- working tree on `2026-04-21`
- commit `47802bf`
- commit `65b16e5`
- commit `2e9e95f`
- commit `942756f`

Observed state in all five cases:

- docs present: `4/4`
- docs with extractable `Last suite result`: `1/4`
- emissions: `0`

Interpretation:

- the current real docs do not currently expose the cross-doc pattern that the rule needs
- only `SYSTEM_STATE.md` carries an extractable `Last suite result:` line in those real cases
- the other three docs remain part of the canonical surface, but they do not yet provide the comparable field needed by this v1 detector

## External Corpora

- `IRPF e Caixa Rural` → `0` comparable docs, `0` extractable counts, `0` emissions
- `estoque_pioneira` → `1` comparable doc, `0` extractable counts, `0` emissions
- `rpg_caminhada` → `1` comparable doc, `0` extractable counts, `0` emissions
- `Resolução Humaita Codex` → `0` comparable docs, `0` extractable counts, `0` emissions

These corpora do not maintain the same four-file canonical surface, so they were suitable only for confirming silence under pattern absence.

## Interpretation

- the rule stayed silent in every real case because the required cross-doc pattern is currently absent
- that is not a precision failure
- it means the rule is structurally tied to a Cerebro-specific documentation pattern that is only partially present in live docs today

## Decision

- keep `detect_current_surface_drift` as `narrow-Cerebro-specific`
- do not generalize it beyond the declared four-doc canonical surface
- if future docs do not converge on a comparable `Last suite result` field, keep the rule as a measured but niche guardrail

## Reminder

This report is derived and non-authoritative. It records the external validation of the `surface drift` slice and must not be consumed as canonical runtime state.
