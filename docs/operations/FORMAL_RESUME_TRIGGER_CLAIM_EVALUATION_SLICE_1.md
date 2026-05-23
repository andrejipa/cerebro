# Formal Resume Trigger — Claim Evaluation Slice 1

## Status

consumed

## Decision

Open a narrow derived-experiment boundary for bounded advisory evaluation of
`ClaimCandidate` objects emitted by `experiments/claim_extraction/`.

The evaluator may assign provisional advisory findings about:

- authority
- confidence
- sufficiency
- conflict
- supersession
- staleness-by-conflict
- operational readiness

It must not create a claim graph, decide canonical truth, gate runtime actions,
write `.cerebro/`, or mutate third-party projects.

## Whitelist

- `experiments/claim_evaluation/`
- `experiments/lifecycle.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- this trigger document

## Forbidden

- no `core/` edits
- no `cli/` edits
- no `extensions/` edits
- no `tests/` edits outside the experiment package
- no `.cerebro/` mutation
- no target-project mutation
- no network calls or model downloads
- no claim graph storage
- no runtime authority or validation gate behavior
- no final truth resolution

## Stop Conditions

- any canonical architecture gate failure
- any full AGENTS-equivalent gate failure
- any code path treating `registered`, `retrieved`, or `remembered` as sufficient
  proof by itself
- any evaluator output that converts silence into negative evidence
- any evaluator output that upgrades citation authority automatically
- any implementation that requires changing `core/`, `cli/`, `extensions/`, or
  `tests/test_architecture.py`

## Acceptance Evidence

- focused `experiments.claim_evaluation` tests pass
- existing `experiments.claim_extraction` tests remain green
- `tests.test_architecture` passes
- full AGENTS-equivalent gate passes
- rendered report includes `state_change: none`
- rendered report marks unresolved/silence/citation cases as insufficient or
  unknown instead of true/false

## Closeout

Consumed on 2026-04-24.

Implemented `experiments/claim_evaluation/` as a local-only, read-only,
non-authoritative evaluator over `ClaimCandidate` inputs. The first slice emits
`EvaluationFinding` and `EvaluationReport` artifacts with bounded advisory
status for authority, confidence, sufficiency, conflict, supersession,
staleness-by-conflict, and operational readiness.
