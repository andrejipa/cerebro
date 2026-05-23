# FORMAL RESUME TRIGGER — CLAIM EXTRACTION TEMPORAL NORMALIZATION

status: consumed
created_at: 2026-04-24
accepted_by: operator request to advance without conservative delay
consumed_at: 2026-04-24
result: implementation complete

## Purpose

Fix the concrete granularity weakness exposed by
`CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`: temporal trigger-consumption
claims currently may use a full snapshot bullet as the claim subject.

Normalize lines that contain:

`Formal resume trigger consumed on YYYY-MM-DD: TRIGGER_ID`

into:

- subject: `TRIGGER_ID`
- predicate: `consumed_on`
- object: `YYYY-MM-DD`

The full line remains evidence only through `source_path:evidence_span`.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_TEMPORAL_NORMALIZATION.md`
- `experiments/claim_extraction/extractor.py`
- `experiments/claim_extraction/tests/test_claim_extraction.py`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

## Forbidden

- No edits to `core/`, `cli/`, `extensions/`, `tests/`, or `core/schema.py`.
- No edits to `.cerebro/`.
- No third-party project mutation.
- No claim graph.
- No runtime gate.
- No final truth assertion.
- No negative evidence from silence.
- No broad extraction redesign.

## Acceptance Criteria

- Long snapshot bullet with `Formal resume trigger consumed on YYYY-MM-DD: TRIGGER_ID` extracts a temporal claim whose subject is only `TRIGGER_ID`.
- Existing claim-extraction fixtures remain green.
- Claim-evaluation tests remain green.
- Architecture gate remains green.
- Full AGENTS-equivalent gate remains green before closure.

## Stop Conditions

Stop if the change requires schema changes, runtime authority, claim graph
construction, or any mutation outside the whitelist.

## Closure Evidence

- `experiments/claim_extraction/extractor.py` now parses inline trigger ids in `Formal resume trigger consumed on YYYY-MM-DD: TRIGGER_ID` lines.
- `experiments/claim_extraction/tests/test_claim_extraction.py` adds regression coverage for long `SYSTEM_STATE.md` snapshot bullets.
- Focused test result: `experiments.claim_extraction` `9/0`; `experiments.claim_evaluation` `7/0`.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, `tests/`, `.cerebro/`, or third-party mutation.
