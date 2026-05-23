# Formal Resume Trigger — Context Vectors Cerebro Self Eval

## Status

- `opened on 2026-04-24 by explicit human direction to continue the new-tech lane`
- `consumed on 2026-04-24 after Cerebro self-oracle evaluation and full gate`
- final gate: `923` tests, `0` failures, `0` errors, `6` skipped via the AGENTS-equivalent runner on Windows

## Objective

Validate the hybrid `context_vectors` scoring against a second real,
non-sensitive project: the Cerebro repository itself. This is cross-project
evidence for whether vector + bounded metadata cues can locate live operational
documents without mutating canonical runtime state.

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_CEREBRO_SELF_EVAL.md`
- `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_CEREBRO_SELF.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/context_vectors/**`

Read-only target:

- `D:\projetos_cli\cerebro\**`

Explicitly closed:

- `core/**`
- `cli/**`
- `tests/**`
- `extensions/**`
- `.cerebro/**`
- any runtime mutation

## Required Properties

- Uses the existing bounded `context_vectors` indexer.
- Produces advisory Markdown evidence only.
- Validates against explicit expected paths for live operational questions.
- Does not write `.cerebro/` or call runtime mutators.
- Includes focused tests for the generic oracle renderer and self-project cases.

## Stop Conditions

Stop and revert if:

- runtime authority files must be touched
- the evaluator needs network/model downloads/external dependencies
- the self oracle cannot distinguish live operational snapshots from historical ledgers
- the full AGENTS-equivalent gate turns red

## Acceptance Criteria

- `CEREBRO_SELF_ORACLE_CASES` exists under `experiments/context_vectors/`.
- A real `CONTEXT_VECTORS_ORACLE_EVAL_CEREBRO_SELF.md` report exists.
- Focused context-vector tests pass.
- Architecture gate passes.
- Full AGENTS-equivalent gate passes.
- This trigger records final status and evidence.

## Final Evidence

- Implementation: `experiments/context_vectors/oracle.py`
- Real report: `docs/operations/CONTEXT_VECTORS_ORACLE_EVAL_CEREBRO_SELF.md`
- Self-oracle result: `recall_at_1=0.500`, `recall_at_3=1.000`, `all_cases_passed_at_3=true`
- Key correction: `_local/` is now skipped as local/archival material after the first self-run showed legacy archives dominating live-document retrieval
- Focused tests: `experiments.context_vectors.tests.test_context_vectors` — `14` tests, `0` failures
- Architecture gate: `tests.test_architecture` — `51` tests, `0` failures
- Full gate: AGENTS-equivalent runner — `923` tests, `0` failures, `0` errors, `6` skipped
- State change: none; no `.cerebro/` or runtime authority mutation
