# External Validation — `detect_supersedes_mechanical_metadata`

- date: `2026-04-21`
- rule: `detect_supersedes_mechanical_metadata`
- curated verdict: `accept_for_staged_promotion`
- external classification: `narrow-Cerebro-specific`
- scope implemented in v1: operator-facing `.md` / `.txt` artifacts only; `.json` deferred until structured object-level evaluation exists

## Method

- ran the rule directly against `docs/operations/`
- ran the rule directly against four previously used real corpora:
  - `estoque_pioneira`
  - `rpg_caminhada`
  - `IRPF e Caixa Rural`
  - `Resolução Humaita Codex`
- attempted live `status-export` validation in this workspace via `python -m cli.main status-export` and `python -m cli.main status-export --format json`

## Findings

### `docs/operations/`

- files scanned: `29`
- `out_of_scope`: `0`
- `in_scope_contextualized`: `29`
- `in_scope_mechanical_only`: `0`
- emissions: `0`

Documentary token hits do exist, but only as prose or code-form examples:

- `PROJECT_OS_BACKLOG.md:147` / `:189` mention `supersedes_consolidation_id`
- `PROJECT_OS_BACKLOG.md:792` mentions `stale_parallel_approach_consolidation_record`
- `SUPERSEDES_TRIPWIRE_MANUAL.md` documents the tokens explicitly

The rule stayed silent because v1 strips inline code and fenced code blocks
before scanning, so manuals and backlog notes do not self-trigger.

### External corpora

- `estoque_pioneira`: `692` files scanned, `0` emissions
- `rpg_caminhada`: `1341` files scanned, `0` emissions
- `IRPF e Caixa Rural`: `213` files scanned, `0` emissions
- `Resolução Humaita Codex`: `2899` files scanned, `0` emissions
- aggregate external scan: `5145` files scanned, `0` emissions

No direct token hits were found in those four corpora for:

- `supersedes=`
- `stale_parallel_approach_consolidation_record`
- `supersedes_consolidation_id`

### Live `status-export`

- markdown export attempt: failed
- JSON export attempt: failed
- reason: `state file not found: .cerebro/state.json`

So this workspace could not provide a live, non-curated operator-facing export
artifact for direct confirmation.

## Interpretation

The slice is still defensible, but only narrowly:

- the target syntax is real inside Cerebro's `status-export` implementation and tests
- the rule is conservative enough not to fire on documentary examples or external corpora
- no non-curated emitted case was observed in this workspace or in the four external corpora

That keeps the rule useful as a measured Cerebro-specific guardrail candidate,
not as evidence of broader corpus coverage.

## Decision

- keep `detect_supersedes_mechanical_metadata` advisory-only
- keep the external label `narrow-Cerebro-specific`
- do not widen to `.json` until the harness can evaluate structured objects instead of raw serialized text
- do not treat this result as justification to expand the suggestion layer further
