# Operational Insufficiency Suggestions — External Validation (`broken refs`)

- authority: `derived-advisory-only`
- non_authoritative: `true`
- read_only: `true`
- validation_mode: `real artifacts, narrow canonical scope`
- date: `2026-04-21`

## Result

- overall: `narrow-scope-validated`
- rule: `detect_broken_canonical_refs`
- curated verdict remains: `accept_for_staged_promotion`

## Scope

This rule is intentionally narrow:

- it inspects markdown links only
- it emits only for source artifacts under `docs/operations/`
- external corpora are used mainly to confirm absence of out-of-scope emissions

## Corpus Used

- `docs/operations/` (`28` markdown files)
- `IRPF e Caixa Rural` (`202` markdown files)
- `estoque_pioneira` (`579` markdown files)
- `rpg_caminhada` (`1203` markdown files)
- `Resolução Humaita Codex` (`2494` markdown files)

## Observed Suggestions

- in-scope hits: `1`
- out-of-scope hits: `0`

### In-Scope True Positive

- `docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md`
  - confidence: `low`
  - signal: `broken_ref=docs/operations/path`
  - interpretation: the manual currently contains a literal markdown example (`[text](path)`) that resolves as a broken local link inside canonical scope

## Interpretation

- the rule stayed silent across all four external real-project corpora because they are intentionally out of scope
- within canonical scope, the rule found one real broken markdown reference and did not emit spurious suggestions for the many absolute `</d:/...>` file links already used by the docs
- that makes the slice suitable as a narrow `docs/operations/` guardrail, not as a general project-wide broken-link detector

## Decision

- keep `detect_broken_canonical_refs` as `narrow-scope-validated`
- do not generalize the rule beyond `docs/operations/` without a new manual, dataset, and external validation round

## Reminder

This report is derived and non-authoritative. It records the external validation of the `broken refs` slice and must not be consumed as canonical runtime state.
