# Formal Resume Trigger — Context Advisor LLM Slice 1

## Status

consumed

## Decision

Open a narrow derived-experiment boundary for `experiments/context_advisor/`.

The layer may combine:

- `experiments/context_discovery` read-only source/candidate/drift evidence
- `experiments/context_vectors` deterministic local ranking evidence

The output is LLM-facing advisory context. It is meant to be consumed by another
agent or model as structured evidence for what to inspect next. It is not a
human approval screen, not runtime authority, and not an automatic import
mechanism.

## Whitelist

- `experiments/context_advisor/`
- `experiments/lifecycle.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `docs/operations/CONTEXT_VECTORS_ORACLE_SYNTHESIS.md`
- this trigger document

## Forbidden

- no `core/` edits
- no `cli/` edits
- no `extensions/` edits
- no `.cerebro/` mutation
- no target-project mutation
- no network calls or model downloads
- no automatic source registration
- no runtime authority or validation gate behavior

## Stop Conditions

- any canonical architecture gate failure
- any full AGENTS-equivalent gate failure
- any output implying it can apply changes, import sources, or mutate state
- any implementation that requires changing `core/`, `cli/`, or
  `tests/test_architecture.py`

## Acceptance Evidence

- focused `experiments.context_advisor` tests pass
- `tests.test_architecture` passes
- full AGENTS-equivalent gate passes
- rendered report includes `state_change: none`
- rendered report includes LLM action boundaries: `may_suggest`, `must_not_apply`

## Closeout

Consumed on 2026-04-24.

Implemented `experiments/context_advisor/` as a local-only, read-only,
LLM-facing report layer joining discovery findings with vector ranking
evidence. It emits structured Markdown with recommended inspection targets,
evidence, and explicit non-authority boundaries.
