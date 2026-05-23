# Formal Resume Trigger — Context Vectors Escritorio Eval

Status: consumed
Created: 2026-04-24
Human approval: explicit operator direction to continue the new-technology lane aggressively and test against `D:\projetos_cli\escritorio`.
Consumed: 2026-04-24 after Escritorio IRPF/Caixa Rural oracle passed with `recall_at_1=1.000`, `recall_at_3=1.000`, `all_cases_passed_at_3=true`, and final AGENTS-equivalent gate `923/0/0/6`.

## Goal

Evaluate and harden `experiments/context_vectors/` against a dense office corpus where many unsupported binary/XML/PDF/source files can appear before the actual operational markdown surfaces.

The slice must answer whether the derived vector layer can still find the master organization, official documentary structure, contributor management, IRPF system, and client registry surfaces without mutating the target.

## Whitelist

- `experiments/context_vectors/**`
- `experiments/lifecycle.toml`
- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_ESCRITORIO_EVAL.md`
- `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_ESCRITORIO_IRPF_CAIXA_RURAL.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

Read-only target:

- `D:\projetos_cli\escritorio\**`

## Closed Boundaries

- `core/`
- `cli/`
- `extensions/`
- canonical `.cerebro/` mutation in this repo
- any mutation inside `D:\projetos_cli\escritorio`
- network calls, uploads, model downloads, or cloud vector stores

## Acceptance Gate

- Escritorio oracle report exists and records `state_change: none`.
- Target project remains read-only.
- Focused `experiments.context_vectors.tests.test_context_vectors` passes.
- `tests.test_architecture` passes.
- `tests.test_doc_governance` passes.
- Full AGENTS-equivalent gate passes before marking this trigger consumed.

## Stop Conditions

- Any write attempt against `D:\projetos_cli\escritorio`.
- Any runtime/canonical mutation attempt.
- Any network/cloud behavior.
- Any gate failure.
