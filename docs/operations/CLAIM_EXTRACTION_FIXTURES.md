# Claim Extraction Fixtures

## Status

Planning-only oracle artifact. This file is not an implementation and does not
authorize runtime, test, or experiment changes.

It is intentionally close to executable fixture form. A future
`experiments/claim_extraction` slice should be able to translate these cases
into fixture files with minimal interpretation.

## Fixture Contract

Each fixture has:

```text
id
purpose
inputs
expected_candidates
forbidden_candidates
failure_if
```

The future runner must compare exact normalized candidates. Extra candidates are
failures unless the fixture explicitly allows them.

## Candidate Normalization

For fixture comparison, candidates should normalize to:

```text
subject
predicate
object
polarity
modality
criticality_hint
source_path
source_role
extraction_basis
```

`claim_id` and `evidence_span` are still required in implementation, but fixture
text below uses semantic fields so the human oracle stays readable.

## F1 Explicit Runtime Freeze

purpose:

```text
Extract explicit operational boundary claims.
```

input:

```text
docs/operations/SYSTEM_STATE.md

Current posture: deliberate freeze for canonical-runtime growth remains active.
Current boundary: no Cerebro runtime boundary is open.
tests/, core/, cli/, extensions/, and runtime implementation remain closed.
```

expected_candidates:

```text
- subject: canonical-runtime growth
  predicate: remains
  object: deliberate freeze active
  polarity: positive
  modality: procedural
  criticality_hint: high
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: primary
  extraction_basis: explicit

- subject: Cerebro runtime boundary
  predicate: is
  object: not open
  polarity: negative
  modality: procedural
  criticality_hint: high
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: primary
  extraction_basis: explicit

- subject: tests core cli extensions runtime implementation
  predicate: remain
  object: closed
  polarity: negative
  modality: procedural
  criticality_hint: high
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: experiments
  predicate: are
  object: closed
```

failure_if:

```text
The extractor generalizes closed runtime areas into a broader claim that all
experiments are closed.
```

## F2 Silence Is Not Negative

purpose:

```text
Prove that omission does not create a negative factual claim.
```

input:

```text
docs/operations/DIAGNOSTIC.md

Current diagnostic:
- Edge Functions still need implementation.
- Supabase validation is the next operational step.
```

expected_candidates:

```text
- subject: Edge Functions
  predicate: need
  object: implementation
  polarity: positive
  modality: factual
  criticality_hint: unknown
  source_path: docs/operations/DIAGNOSTIC.md
  source_role: primary
  extraction_basis: explicit

- subject: Supabase validation
  predicate: is
  object: next operational step
  polarity: positive
  modality: procedural
  criticality_hint: unknown
  source_path: docs/operations/DIAGNOSTIC.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: Supabase schema
  predicate: exists
  object: false

- subject: Supabase schema
  predicate: does not exist
  object: true
```

failure_if:

```text
The extractor converts missing schema text into a negative schema claim.
```

## F3 Structured Absence Is Unknown

purpose:

```text
Allow required-section absence without turning it into factual negation.
```

input:

```text
docs/operations/DIAGNOSTIC.md

Required sections:
- Current objective
- Known schema status
- Next action

Current objective:
- Validate Edge Functions.

Next action:
- Inspect Supabase functions.
```

expected_candidates:

```text
- subject: diagnostic source
  predicate: does not declare
  object: known schema status
  polarity: unknown
  modality: factual
  criticality_hint: unknown
  source_path: docs/operations/DIAGNOSTIC.md
  source_role: primary
  extraction_basis: structured_absence
```

forbidden_candidates:

```text
- subject: schema
  predicate: does not exist
  object: true
```

failure_if:

```text
The extractor treats missing required schema section as proof that no schema
exists.
```

## F4 Supersession Absence Is Unknown

purpose:

```text
Represent insufficiency caused by a more decisive source without fabricating
opposition.
```

inputs:

```text
docs/operations/OLD_DIAGNOSTIC.md

Current diagnostic:
- Edge Functions still need implementation.

docs/operations/MEMORIA_CONTINUIDADE_ATUAL.md

Current continuity:
- The Supabase schema already exists.
- Edge Functions must be validated against the existing schema.
```

expected_candidates:

```text
- subject: Supabase schema
  predicate: already exists
  object: true
  polarity: positive
  modality: factual
  criticality_hint: unknown
  source_path: docs/operations/MEMORIA_CONTINUIDADE_ATUAL.md
  source_role: primary
  extraction_basis: explicit

- subject: OLD_DIAGNOSTIC.md
  predicate: is insufficient for
  object: schema-creation decisions
  polarity: unknown
  modality: meta
  criticality_hint: unknown
  source_path: docs/operations/OLD_DIAGNOSTIC.md
  source_role: derived
  extraction_basis: supersession_absence
```

forbidden_candidates:

```text
- subject: OLD_DIAGNOSTIC.md
  predicate: says
  object: schema does not exist
```

failure_if:

```text
The extractor converts supersession into contradiction.
```

## F5 Citation Does Not Upgrade Authority

purpose:

```text
Keep assertion source and citation source separate.
```

inputs:

```text
docs/operations/OPPORTUNITY_MAP.md

Next item: build a combined context report.

docs/operations/SYSTEM_STATE.md

The current snapshot quotes OPPORTUNITY_MAP.md:
"Next item: build a combined context report."
```

expected_candidates:

```text
- subject: next item
  predicate: is
  object: build a combined context report
  polarity: positive
  modality: procedural
  criticality_hint: unknown
  source_path: docs/operations/OPPORTUNITY_MAP.md
  source_role: primary
  extraction_basis: explicit

- subject: SYSTEM_STATE.md
  predicate: cites
  object: OPPORTUNITY_MAP.md next item
  polarity: positive
  modality: meta
  criticality_hint: unknown
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: citation
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: next item
  predicate: is authoritatively set by
  object: SYSTEM_STATE.md quote
```

failure_if:

```text
The quote upgrades authority from OPPORTUNITY_MAP.md to SYSTEM_STATE.md without
explicit reassertion.
```

## F6 Meta-Claim Is First Class

purpose:

```text
Extract claims that govern interpretation of other claims.
```

input:

```text
AGENTS.md

Authority order: AGENTS.md -> active triggers -> observation_center.toml ->
SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests.
Divergence forces docs-only reconciliation before implementation.
```

expected_candidates:

```text
- subject: authority order
  predicate: is
  object: AGENTS.md -> active triggers -> observation_center.toml -> SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests
  polarity: positive
  modality: meta
  criticality_hint: unknown
  source_path: AGENTS.md
  source_role: primary
  extraction_basis: explicit

- subject: divergence
  predicate: forces
  object: docs-only reconciliation before implementation
  polarity: required
  modality: meta
  criticality_hint: high
  source_path: AGENTS.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: code/tests
  predicate: have highest authority
  object: true
```

failure_if:

```text
The extractor treats the authority chain as prose instead of a first-class
meta-claim, or reverses the order.
```

## F7 Temporal Status Preserved

purpose:

```text
Preserve consumed, waiting, blocked, and current-status terms.
```

input:

```text
docs/operations/SYSTEM_STATE.md

Formal resume trigger consumed on 2026-04-24:
FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_SLICE_1.
Third-party pilot remains waiting for explicit human go/no-go.
```

expected_candidates:

```text
- subject: FORMAL_RESUME_TRIGGER_CONTEXT_VECTORS_SLICE_1
  predicate: consumed_on
  object: 2026-04-24
  polarity: positive
  modality: temporal
  criticality_hint: unknown
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: primary
  extraction_basis: explicit

- subject: third-party pilot
  predicate: remains
  object: waiting for explicit human go/no-go
  polarity: unknown
  modality: temporal
  criticality_hint: high
  source_path: docs/operations/SYSTEM_STATE.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: context vectors trigger
  predicate: is active
  object: true

- subject: third-party pilot
  predicate: is approved
  object: true
```

failure_if:

```text
The extractor drops temporal state and turns consumed/waiting into active or
approved.
```

## F8 Criticality Unknown By Default

purpose:

```text
Prove criticality is not inferred from apparent importance.
```

input:

```text
docs/operations/PLAN.md

The schema status determines whether the agent should create a database schema
or validate Edge Functions against an existing schema.
```

expected_candidates:

```text
- subject: schema status
  predicate: determines
  object: whether to create schema or validate Edge Functions against existing schema
  polarity: positive
  modality: procedural
  criticality_hint: unknown
  source_path: docs/operations/PLAN.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: schema status
  predicate: has criticality
  object: critical
```

failure_if:

```text
The extractor infers criticality from implementation impact instead of explicit
operational markers.
```

## F9 Criticality Marker Promotion

purpose:

```text
Allow criticality promotion only from explicit operational markers.
```

input:

```text
docs/operations/TRIGGER.md

Stop condition: any negative claim inferred from silence must halt the slice.
Approval required before third-party mutation.
```

expected_candidates:

```text
- subject: negative claim inferred from silence
  predicate: must halt
  object: slice
  polarity: required
  modality: procedural
  criticality_hint: high
  source_path: docs/operations/TRIGGER.md
  source_role: primary
  extraction_basis: explicit

- subject: third-party mutation
  predicate: requires
  object: approval
  polarity: required
  modality: procedural
  criticality_hint: high
  source_path: docs/operations/TRIGGER.md
  source_role: primary
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: third-party mutation
  predicate: is approved
  object: true
```

failure_if:

```text
The extractor mistakes "approval required" for "approval granted".
```

## F10 Fixture 9 Full Schema Omission Oracle

purpose:

```text
Lock the rpg_caminhada failure class as the mandatory regression.
```

inputs:

```text
cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md

Current diagnostic:
- Edge Functions still need implementation.
- Supabase validation is the next operational step.

cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md

Current continuity:
- The Supabase schema already exists.
- The next step is validating Edge Functions against the existing schema.
```

expected_candidates:

```text
- subject: Edge Functions
  predicate: need
  object: implementation
  polarity: positive
  modality: factual
  criticality_hint: unknown
  source_path: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  source_role: primary
  extraction_basis: explicit

- subject: Supabase validation
  predicate: is
  object: next operational step
  polarity: positive
  modality: procedural
  criticality_hint: unknown
  source_path: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  source_role: primary
  extraction_basis: explicit

- subject: Supabase schema
  predicate: already exists
  object: true
  polarity: positive
  modality: factual
  criticality_hint: unknown
  source_path: cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md
  source_role: primary
  extraction_basis: explicit

- subject: Edge Functions
  predicate: should be validated against
  object: existing schema
  polarity: positive
  modality: procedural
  criticality_hint: unknown
  source_path: cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md
  source_role: primary
  extraction_basis: explicit

- subject: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  predicate: does not declare
  object: schema status
  polarity: unknown
  modality: factual
  criticality_hint: unknown
  source_path: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  source_role: primary
  extraction_basis: structured_absence

- subject: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  predicate: is insufficient for
  object: schema-creation decisions
  polarity: unknown
  modality: meta
  criticality_hint: unknown
  source_path: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  source_role: derived
  extraction_basis: supersession_absence
```

forbidden_candidates:

```text
- subject: cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
  predicate: says
  object: schema does not exist

- subject: Supabase schema
  predicate: does not exist
  object: true

- subject: schema creation
  predicate: is next action
  object: true
```

failure_if:

```text
The extractor fabricates contradiction, misses the explicit schema-exists claim,
or turns the diagnostic omission into permission to create schema.
```

## F11 Over-Extraction Guard

purpose:

```text
Prevent the first extractor from flooding the graph with low-value details.
```

input:

```text
docs/operations/NOTES.md

The operator said the document is solid, surprisingly precise, and likely
valuable when the moment arrives.
```

expected_candidates:

```text
[]
```

forbidden_candidates:

```text
- subject: document
  predicate: is
  object: solid

- subject: document
  predicate: is
  object: surprisingly precise

- subject: document
  predicate: is
  object: valuable
```

failure_if:

```text
The extractor treats evaluation prose as operational claim candidates.
```

## F12 Trigger Text Is Not Authorization

purpose:

```text
Future trigger drafts must not be treated as active authorization.
```

input:

```text
docs/operations/CLAIM_EXTRACTION_IMPLEMENTATION_READINESS.md

When implementation is authorized, the formal trigger should contain:
FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1
Boundary:
- experiments/claim_extraction/**
```

expected_candidates:

```text
- subject: FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1
  predicate: is
  object: proposed future trigger text
  polarity: unknown
  modality: meta
  criticality_hint: unknown
  source_path: docs/operations/CLAIM_EXTRACTION_IMPLEMENTATION_READINESS.md
  source_role: derived
  extraction_basis: explicit
```

forbidden_candidates:

```text
- subject: FORMAL_RESUME_TRIGGER_CLAIM_EXTRACTION_SLICE_1
  predicate: is active
  object: true

- subject: experiments/claim_extraction
  predicate: is authorized now
  object: true
```

failure_if:

```text
The extractor treats a drafted trigger template as an active formal trigger.
```

## Minimum Pass Bar

The first implementation must pass all fixtures exactly:

```text
fixtures: 12
expected fixture failures: 0
forbidden candidate emissions: 0
extra candidates allowed by default: false
```

No claim graph, confidence scoring, authority resolution, or runtime gate should
consume extraction output before this fixture set is executable and green.
