# Operational Insufficiency Suggestions — External Validation

- authority: `derived-advisory-only`
- non_authoritative: `true`
- read_only: `true`
- validation_mode: `real artifacts, non-curated`
- date: `2026-04-20`

## Result

- overall: `marginal`
- `detect_stale_system_state`: `valid but narrow`
- `detect_export_surface_gap`: `not validated on the real corpus`

## Corpus Used

- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `estoque_pioneira/README.md`
- `estoque_pioneira/controle/CONTEXTO_MESTRE.md`
- `rpg_caminhada/README.md`
- `Resolução Humaita Codex/Entrada - Inicio do Projeto.md`
- `Resolução Humaita Codex/Memoria - Retomada 2026-04-06.md`
- `IRPF e Caixa Rural/README_ESTRUTURA_GERAL.md`
- `IRPF e Caixa Rural/IRPF/_SISTEMA/01_METODOLOGIA/PROTOCOLO_DE_ABERTURA_DE_CASO.md`

## Observed Suggestions

- `STALE_INFORMATION`
  - one true positive on `docs/operations/SYSTEM_STATE.md`
  - trigger reason: `Current Snapshot` reports `730` tests while `Gate Status` still reports `550`

- `INSUFFICIENT_EXPORT_SURFACE`
  - zero useful suggestions on the real corpus
  - no false positives observed, but no real coverage either

## Follow-Up Directory Scan

A later read-only directory-wide scan across the same four real-project roots inspected `6163` text-like files and produced:

- `0` `STALE_INFORMATION` hits
- `0` `INSUFFICIENT_EXPORT_SURFACE` hits

Breakdown:

- `IRPF e Caixa Rural`: `213` files scanned, `0` hits
- `estoque_pioneira`: `664` files scanned, `0` hits
- `rpg_caminhada`: `2242` files scanned, `0` hits
- `Resolução Humaita Codex`: `3044` files scanned, `0` hits

## Failure Analysis

- `detect_stale_system_state` works only for a narrow structural pattern: two canonical sections plus divergent suite counts
- `detect_export_surface_gap` depends on a structured `## Required Export Anchors` section that does not exist in the real corpus outside the layer's own documentation
- the current rules do not detect the more common real-world insufficiency shapes:
  - multiple plausible entrypoints
  - historical material competing with the current path
  - archaeology/manual search across several files
  - ambiguity without numeric drift

## Decision

- keep `detect_stale_system_state`
- do not promote `detect_export_surface_gap`
- stop tripwire expansion until a rule can be validated against non-curated real artifacts without depending on an artificial author-defined structure

## Reminder

This report is derived and non-authoritative. It records external validation of the suggestion layer; it is not runtime state and does not authorize growth.
