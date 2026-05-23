# Formal Resume Trigger — Context Vectors Portal Eval

Status: consumed
Created: 2026-04-24
Human approval: explicit operator direction to continue the new-technology lane aggressively and test against `D:\projetos_cli\Portal\Resolução Humaita Codex`.
Consumed: 2026-04-24 after Portal Humaita oracle passed at top 3 with `recall_at_1=0.500`, `recall_at_3=1.000`, `critical_continuity_result=pass`, and final AGENTS-equivalent gate `923/0/0/6`.

## Goal

Evaluate `experiments/context_vectors/` against a dense, real third-party project with live, historical, archival, and nested legacy-Cerebro material.

The slice must answer whether the derived vector layer can rank the current operational surfaces of the Portal ahead of older memories, historical reports, backups, and embedded methodology folders.

## Whitelist

- `experiments/context_vectors/**`
- `experiments/lifecycle.toml`
- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_PORTAL_EVAL.md`
- `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_PORTAL_HUMAITA.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

Read-only target:

- `D:\projetos_cli\Portal\Resolução Humaita Codex\**`

## Closed Boundaries

- `core/`
- `cli/`
- `extensions/`
- canonical `.cerebro/` mutation in this repo
- any mutation inside `D:\projetos_cli\Portal\Resolução Humaita Codex`
- network calls, uploads, model downloads, or cloud vector stores

## Acceptance Gate

- Portal oracle report exists and records `state_change: none`.
- Portal project remains read-only.
- Focused `experiments.context_vectors.tests.test_context_vectors` passes.
- `tests.test_architecture` passes.
- `tests.test_doc_governance` passes.
- Full AGENTS-equivalent gate passes before marking this trigger consumed.

## Stop Conditions

- Any write attempt against the Portal project.
- Any runtime/canonical mutation attempt.
- Any need to read beyond bounded local file heads for ranking.
- Any change that makes vector retrieval authoritative instead of advisory.
- Any gate failure.
