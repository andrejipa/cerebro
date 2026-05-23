# Formal Resume Trigger — Context Vectors Oracle Eval

## Status

- `opened on 2026-04-24 by explicit human direction to keep advancing context technologies`
- `consumed on 2026-04-24 after oracle evaluation, hybrid-score adjustment, and full gate`
- final gate: `923` tests, `0` failures, `0` errors, `6` skipped via the AGENTS-equivalent runner on Windows

## Objective

Evaluate `experiments/context_vectors/` against the real `rpg_caminhada`
oracle discovered during the third-party recon. The goal is to measure whether
the deterministic vector layer finds the human-known critical files before any
hybrid relevance or semantic-selection layer is proposed.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_ORACLE_EVAL.md`
- `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_RPG_CAMINHADA.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/context_vectors/**`

Read-only target:

- `D:\projetos_cli\pessoais\rpg_caminhada\**`

Explicitly closed:

- `core/**`
- `cli/**`
- `tests/**`
- `extensions/**`
- `.cerebro/**`
- any writes under `D:\projetos_cli\pessoais\rpg_caminhada\**`

## Required Properties

- Reads the target project only through the existing bounded `context_vectors`
  indexer.
- Produces advisory Markdown evidence in this repo only.
- Compares query results to explicit oracle expected paths.
- Reports misses and top hits without mutating the target project or canonical
  Cerebro state.
- Includes tests for report shape, pass/fail criteria, and state_change none.

## Stop Conditions

Stop and revert if:

- any target-project write is needed
- any runtime authority file must be touched
- the evaluator needs network/model downloads/external dependencies
- the oracle cannot distinguish the stale diagnosis file from current continuity
- the full AGENTS-equivalent gate turns red

## Acceptance Criteria

- Oracle evaluator and renderer exist under `experiments/context_vectors/`.
- Focused context-vector tests pass.
- A real `CONTEXT_VECTORS_ORACLE_EVAL_RPG_CAMINHADA.md` report exists.
- The report states whether `04_MEMORIA_CONTINUIDADE_ATUAL.md` is found for
  the "next real work" query.
- Architecture gate passes.
- Full AGENTS-equivalent gate passes.
- This trigger records final status and evidence.

## Final Evidence

- Implementation: `experiments/context_vectors/oracle.py`
- Real report: `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_RPG_CAMINHADA.md`
- Oracle result after hybrid scoring: `recall_at_1=1.000`, `recall_at_3=1.000`, `critical_continuity_result=pass`
- Critical file: `cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md` ranked `1` for the next-real-work query
- Focused tests: `experiments.context_vectors.tests.test_context_vectors` — `12` tests, `0` failures
- Architecture gate: `tests.test_architecture` — `51` tests, `0` failures
- Doc governance gate: `tests.test_doc_governance` — `13` tests, `0` failures
- Full gate: AGENTS-equivalent runner — `923` tests, `0` failures, `0` errors, `6` skipped
- State change: none; `D:\projetos_cli\pessoais\rpg_caminhada` was read-only and not modified
