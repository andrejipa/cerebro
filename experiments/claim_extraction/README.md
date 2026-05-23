# claim_extraction (experimental derived track)

Deterministic local claim-candidate extraction experiment.

This layer turns bounded text heads into `ClaimCandidate` units that can be
tested against the epistemic-runtime fixture pressure. It deliberately stops
before claim graph storage, authority resolution, confidence scoring, staleness
scoring, runtime gates, or source registration.

## Boundaries

- derived, non-authoritative, opt-in
- reads caller-supplied bounded text only
- no writes under `.cerebro/`
- no target-project mutation
- no imports from `cli/`
- no network calls, model downloads, or external services
- never creates accepted knowledge

## What It Provides

- immutable `ClaimCandidate` data model
- deterministic candidate ids
- stable semantic ids that exclude evidence spans
- evidence ids that preserve source/span traceability
- explicit/structured-absence/supersession-absence extraction basis
- fixture-backed conservative extraction rules
- advisory markdown rendering for human inspection

The output is candidate evidence for a later evaluator. It is not truth.
