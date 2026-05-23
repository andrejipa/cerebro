# Formal Resume Trigger — Context Vectors Slice 1

## Status

- `opened on 2026-04-24 by explicit human direction to advance new context technologies`
- `consumed on 2026-04-24 after implementation and full gate`
- final gate: `923` tests, `0` failures, `0` errors, `6` skipped via the AGENTS-equivalent runner on Windows

## Objective

Add one aggressive but bounded derived technology slice: a deterministic local
vector-search experiment for project context. The slice must deliver useful
semantic-ish retrieval, an evaluation hook, and an observability trace without
touching canonical runtime authority.

## Why This Is Allowed

The operator explicitly authorized moving beyond conservative pilot-only work.
This trigger keeps the advance inside the freeze policy's minimum-safe shape:

- external to `core/`, `cli/`, and `.cerebro/state.json`
- derived and read-only
- no new canonical artifact
- no automatic import or source mutation
- proportional tests

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_SLICE_1.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/lifecycle.toml`
- `experiments/context_vectors/**`

Explicitly closed:

- `core/**`
- `cli/**`
- `tests/**`
- `extensions/**`
- `.cerebro/**`
- any third-party project path

## Required Properties

- Reads project files only through bounded textual heads.
- Skips binary files, symlinks, directories, hidden/generated/vendor paths, and
  oversized tails.
- Uses a deterministic local vectorizer; no network calls and no model
  downloads.
- Produces query results and trace data only; never mutates the target project
  or `.cerebro/`.
- Can include registered-source awareness only by reading through public
  `StateStore` APIs.
- Includes direct tests for ranking, caps, immutability, eval scoring, and
  legacy/invalid state fallback.

## Stop Conditions

Stop and revert if:

- any runtime authority file must be touched
- any target project file must be modified
- the experiment needs external dependencies or network
- the full AGENTS-equivalent gate turns red
- the implementation cannot prove `state_change: none`

## Acceptance Criteria

- `experiments/context_vectors/` exists with README, implementation, and tests.
- Focused context-vector tests pass.
- Architecture gate passes.
- Full AGENTS-equivalent gate passes.
- `experiments/lifecycle.toml` records the experiment as active.
- This trigger records final status and evidence.

## Final Evidence

- Implementation: `experiments/context_vectors/`
- Focused tests: `experiments.context_vectors.tests.test_context_vectors` — `10` tests, `0` failures
- Architecture gate: `tests.test_architecture` — `51` tests, `0` failures
- Doc governance gate: `tests.test_doc_governance` — `13` tests, `0` failures
- Full gate: AGENTS-equivalent runner — `923` tests, `0` failures, `0` errors, `6` skipped
- State change: none; the experiment is derived/read-only, uses bounded textual heads, skips hidden text files, exposes immutable cached vectors, and never writes target projects or `.cerebro/`
