# Claim Extraction Implementation Readiness

## Status

Planning-only artifact. This document does not open a runtime boundary and does
not authorize changes in `core/`, `cli/`, `extensions/`, or `tests/`.

It defines the edge of implementation for deterministic claim extraction. A
future implementation slice must treat this document and
`CLAIM_EXTRACTION_CONTRACT.md` as acceptance inputs, not as optional context.

## Readiness Goal

Reach a point where implementation starts with executable tests and fixed
contracts instead of design decisions made inside code.

The implementation should be allowed only when the next active trigger can state
all of the following without ambiguity:

```text
Implement a deterministic, conservative claim extractor over bounded text heads.
It must emit source-anchored explicit claims, structured absence, supersession
absence, and meta-claims according to CLAIM_EXTRACTION_CONTRACT.md.
It must not infer negative claims from silence.
It must not resolve final authority or final criticality.
It must pass the required fixtures before any claim graph consumes its output.
```

## Implementation Boundary

First implementation should be an experiment, not canonical runtime.

Allowed future boundary, if a formal trigger opens it:

```text
experiments/claim_extraction/**
docs/operations/CLAIM_EXTRACTION_*.md
```

Closed unless a stronger architecture decision explicitly says otherwise:

```text
core/**
cli/**
extensions/**
.cerebro/**
third-party project roots
```

The first slice must produce a library and test fixture runner, not a runtime
hook.

## Proposed Module Shape

Future files, if authorized:

```text
experiments/claim_extraction/
  __init__.py
  contract.py
  extractor.py
  fixtures.py
  render.py
  tests/
    test_claim_contract.py
    test_fixture_9.py
    test_citation_authority.py
    test_meta_claims.py
    test_criticality_hint.py
```

Responsibilities:

```text
contract.py   -> dataclasses/enums for claim candidates and extraction basis
extractor.py  -> deterministic rules over bounded text heads
fixtures.py   -> load fixture inputs and expected outputs
render.py     -> advisory markdown/json report for operator inspection
tests/        -> acceptance tests before any graph integration exists
```

No writer should touch canonical state. Reports, if any, must be derived and
read-only in posture.

## Data Model Edge

The first implementation should model claim candidates, not accepted knowledge.

Minimum shape:

```text
ClaimCandidate
- claim_id
- subject
- predicate
- object
- polarity
- modality
- criticality_hint
- source_path
- evidence_span
- source_role
- authority_hint
- extraction_basis
```

Important naming:

```text
ClaimCandidate, not Claim.
authority_hint, not authority.
criticality_hint, not criticality.
```

The names must keep the epistemic boundary visible in code. Extraction proposes
candidate units; evaluation decides whether those units are sufficient,
authoritative, stale, contradicted, superseded, or actionable.

## Determinism Rules

The extractor must be deterministic across repeated runs:

1. Same input text produces same candidates in same order.
2. Claim ids derive from normalized source path, evidence span, modality,
   subject, predicate, object, polarity, and extraction basis.
3. No wall-clock time, model output, filesystem mtime, or hash randomization may
   affect extraction.
4. Candidate ordering is source order, then stable claim id.
5. Bounded heads must be passed in by caller; the extractor does not choose a
   project scan policy.

This keeps scanning, retrieval, and extraction separated.

## First Fixture Set

Before implementation, create fixture files that encode expected extraction.

Minimum fixtures:

```text
F1_explicit_runtime_freeze
F2_silence_is_not_negative
F3_structured_absence_is_unknown
F4_supersession_absence_is_unknown
F5_citation_does_not_upgrade_authority
F6_meta_claim_is_first_class
F7_temporal_status_preserved
F8_criticality_unknown_by_default
F9_schema_status_omission
F10_forbidden_negative_from_fixture_9
```

The fixture runner should fail if extra candidates appear unless the fixture
explicitly allows them. Over-extraction is a correctness failure, not harmless
noise.

## Fixture 9 Concrete Oracle

Input A:

```text
04_DIAGNOSTICO_INICIAL_ATUAL.md

Current diagnostic:
- Edge Functions still need implementation.
- Supabase validation is the next operational step.
```

Input B:

```text
04_MEMORIA_CONTINUIDADE_ATUAL.md

Current continuity:
- The Supabase schema already exists.
- The next step is validating Edge Functions against the existing schema.
```

Expected candidates:

```text
candidate: schema already exists
source: 04_MEMORIA_CONTINUIDADE_ATUAL.md
extraction_basis: explicit
polarity: positive

candidate: diagnostic source does not declare schema status
source: 04_DIAGNOSTICO_INICIAL_ATUAL.md
extraction_basis: structured_absence
polarity: unknown

candidate: diagnostic source is insufficient for schema-creation decisions
source: derived fixture expectation
extraction_basis: supersession_absence
polarity: unknown
```

Forbidden candidate:

```text
candidate: diagnostic says schema does not exist
```

The forbidden candidate must be asserted in a regression test. The test should
fail loudly if that candidate is emitted.

## Rule Families

The first extractor should have a small rule set:

```text
explicit_status_rule
explicit_boundary_rule
explicit_authority_rule
explicit_waiting_or_blocked_rule
explicit_forbidden_or_required_rule
structured_absence_rule
supersession_absence_rule
meta_claim_rule
temporal_status_rule
criticality_marker_rule
```

Every rule must declare:

```text
input pattern
emitted modality
emitted extraction_basis
allowed polarity
forbidden emissions
fixture coverage
```

No catch-all semantic rule in the first slice.

## Out Of Scope For First Slice

Do not implement:

1. Claim graph storage.
2. Authority resolution.
3. Confidence scoring.
4. Staleness scoring.
5. Cross-file contradiction resolution beyond fixture-local expected candidates.
6. Model-assisted extraction.
7. Obsidian graph traversal.
8. Runtime gating.
9. CLI mutation commands.
10. Third-party project writes.

These belong after extraction candidates are proven stable.

## Test-First Order

Implementation must start in this order:

1. Define fixture schema.
2. Write F9 forbidden-negative test.
3. Write silence/structured-absence tests.
4. Write citation-authority test.
5. Write meta-claim test.
6. Write criticality default/promotion tests.
7. Implement minimum data model.
8. Implement only enough extraction to pass the fixtures.
9. Add report rendering.
10. Run focused tests and full AGENTS-equivalent gate.

The first passing slice should be small enough that a reviewer can inspect every
emitted candidate by hand.

## Promotion Bar

The extractor is not ready to feed a claim graph until:

```text
fixture pass rate: 100%
forbidden candidate pass rate: 100%
deterministic rerun: identical output
over-extraction budget: enforced
all candidates carry evidence spans
all unknowns remain unknown
no citation upgrades authority by default
criticality defaults to unknown without explicit marker
```

Passing these does not make the output true. It only makes the output eligible
for epistemic evaluation.

## Trigger Text For Future Slice

When implementation is authorized, the formal trigger should contain a statement
close to:

```text
FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1

Boundary:
- experiments/claim_extraction/**
- docs/operations/CLAIM_EXTRACTION_*.md

Goal:
- Implement deterministic claim candidates from bounded text heads according to
  CLAIM_EXTRACTION_CONTRACT.md and
  CLAIM_EXTRACTION_IMPLEMENTATION_READINESS.md.

Stop conditions:
- Any mutation outside the boundary.
- Any attempt to make extraction authoritative runtime behavior.
- Any candidate emitted without evidence span.
- Any negative claim inferred from silence.
- Fixture 9 forbidden candidate appears.
- Full AGENTS-equivalent gate turns red.
```

## Edge Statement

After this readiness layer, the next useful artifact is not another concept doc.
It is either:

1. fixture files plus expected outputs, still docs/experiment-only; or
2. a formal implementation trigger for `experiments/claim_extraction`.

Anything broader would blur the boundary and make the first implementation less
deterministic.
