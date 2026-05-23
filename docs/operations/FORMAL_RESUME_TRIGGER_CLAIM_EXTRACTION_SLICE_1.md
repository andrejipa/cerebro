# Formal Resume Trigger — Claim Extraction Slice 1

## Status

- `opened on 2026-04-24 by explicit human direction to advance the claim extraction lane aggressively`
- `consumed on 2026-04-24 after implementation and full gate`
- final gate: `923` tests, `0` failures, `0` errors, `6` skipped via the AGENTS-equivalent runner on Windows

## Objective

Implement the first deterministic claim-extraction experiment. The slice must
turn the documented contract and fixtures into executable candidate extraction
without creating a claim graph, runtime gate, or canonical authority surface.

## Why This Is Allowed

The operator explicitly directed the lane to move past conceptual planning. This
trigger keeps that advance inside the freeze policy's minimum-safe shape:

- external to `core/`, `cli/`, `extensions/`, and `.cerebro/state.json`
- derived and read-only
- no canonical runtime behavior
- no third-party project mutation
- no network calls, model downloads, or external services
- proportional tests against the documented fixture pressure

## Whitelist

Allowed files:

- `docs/operations/FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1.md`
- `docs/operations/CLAIM_EXTRACTION_*.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`
- `experiments/lifecycle.toml`
- `experiments/claim_extraction/**`

Explicitly closed:

- `core/**`
- `cli/**`
- `tests/**`
- `extensions/**`
- `.cerebro/**`
- any third-party project path

## Required Properties

- Reads bounded text heads supplied by the caller.
- Emits `ClaimCandidate` objects, not accepted knowledge.
- Preserves the naming boundary: `authority_hint`, `criticality_hint`, and
  `ClaimCandidate`.
- Does not infer negative claims from silence.
- Emits structured absence and supersession absence only as `unknown`.
- Keeps meta-claims first class.
- Does not upgrade authority through citation.
- Defaults criticality to `unknown` unless explicit operational markers appear.
- Produces deterministic candidate ids and deterministic ordering.
- Includes executable fixture coverage for the twelve documented fixtures.

## Stop Conditions

Stop and revert if:

- any runtime authority file must be touched
- any target project file must be modified
- the experiment needs external dependencies or network
- any emitted candidate lacks source path or evidence span
- any negative claim is inferred from silence
- Fixture 9 emits the forbidden diagnostic-schema negative
- the full AGENTS-equivalent gate turns red

## Acceptance Criteria

- `experiments/claim_extraction/` exists with README, implementation, fixtures,
  and tests.
- Focused claim-extraction tests pass.
- Architecture gate passes.
- Doc governance gate passes.
- Full AGENTS-equivalent gate passes.
- `experiments/lifecycle.toml` records the experiment as active.
- This trigger records final status and evidence.

## Final Evidence

- Implementation: `experiments/claim_extraction/`
- Focused tests: `experiments.claim_extraction.tests.test_claim_extraction` — `8` tests, `0` failures
- Architecture gate: `tests.test_architecture` — `51` tests, `0` failures
- Doc governance gate: `tests.test_doc_governance` — `13` tests, `0` failures
- Full gate: AGENTS-equivalent runner — `923` tests, `0` failures, `0` errors, `6` skipped
- State change: none; the experiment is derived/read-only, uses caller-supplied bounded text, emits `ClaimCandidate` units only, and does not write target projects or `.cerebro/`
