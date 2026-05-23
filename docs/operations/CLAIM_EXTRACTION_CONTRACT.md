# Claim Extraction Contract

## Status

Conceptual specification only. This document does not open a runtime boundary
and does not authorize implementation in `core/`, `cli/`, or `extensions/`.

It matures Slice 2 from `EPISTEMIC_RUNTIME_MATURITY_PLAN.md`: deterministic
claim extraction. The contract exists because the claim graph is only as good
as the units it stores. If extraction is ambiguous, the whole epistemic runtime
becomes a black box with rigorous-looking metadata.

## Purpose

Claim extraction converts bounded source text into auditable, source-anchored
statements that can support or block operational action.

The extractor must not infer intent, summarize tone, or create interpretations.
It extracts only statements that can be traced to evidence spans and challenged
against other sources.

Core rule:

```text
Extract verifiable source-anchored assertions, not interpretations.
```

## Claim Definition

A claim is a bounded assertion with all of the following properties:

1. It states that something is true, required, forbidden, completed, blocked,
   authorized, deprecated, superseded, or currently unknown.
2. It can be anchored to a specific source span.
3. It can affect a future operational decision, validation, or conflict check.
4. It can be contradicted, confirmed, superseded, or marked insufficient by
   another source.

Valid examples:

```text
The current runtime is under deliberate freeze.
The context vectors experiment is read-only and non-authoritative.
The third-party pilot is waiting for explicit human go/no-go.
SYSTEM_STATE.md is the current human-readable state projection.
```

Invalid examples:

```text
The project is mature.
The protocol is elegant.
The design feels robust.
This probably means the schema is done.
```

Those are interpretations. They may be useful prose, but they are not claims.

## Claim Shape

Each extracted claim must be representable as:

```text
claim_id: stable deterministic id
subject: entity or operational object
predicate: asserted relationship or state
object: value, target, status, or referenced object
polarity: positive | negative | unknown | prohibited | required
modality: factual | normative | procedural | temporal | meta
criticality_hint: unknown | low | medium | high | critical
source_path: file path
evidence_span: line range or bounded text span
source_role: primary | projection | citation | derived | historical
authority_hint: source-local authority before conflict resolution
extraction_basis: explicit | structured_absence | supersession_absence
```

The extractor may generate `authority_hint`, but final authority resolution is
not part of extraction. Authority belongs to the epistemic evaluation layer.

## Explicit Claims By Default

The default rule is strict:

```text
Silence is not a claim.
```

If a file does not mention that a schema exists, the extractor must not create:

```text
claim: "the schema does not exist"
```

Absence becomes operationally meaningful only in two narrow cases.

## Structured Absence

Structured absence may become a claim when the document format explicitly
requires a field, section, or checklist item and the source omits it.

Example:

```text
required_section: "Known schema status"
observed: missing
claim: "source does not declare known schema status"
extraction_basis: structured_absence
polarity: unknown
```

This is not a claim that the schema does not exist. It is a claim that the
source does not provide required evidence about schema status.

Structured absence supports sufficiency gates. It must not be treated as factual
negation.

## Supersession Absence

Supersession absence may become a claim when a more authoritative or newer
source explicitly records that a prior source no longer covers a changed state.

Example:

```text
primary_source_claim: "schema exists"
older_source_observation: "schema status not mentioned"
derived_claim: "older source is insufficient for schema-existence decisions"
extraction_basis: supersession_absence
polarity: unknown
```

Again, this does not mean the older source asserted the opposite. It means the
older source cannot safely support the action anymore.

This distinction is mandatory for the rpg_caminhada failure class: the dangerous
state was not an explicit false claim, but an apparently current file that did
not carry the decisive newer fact.

## Authority And Citation

Claim authority is inherited from the primary source of the assertion, not from
the document that quotes it.

If `SYSTEM_STATE.md` quotes `OPPORTUNITY_MAP.md`, extraction must produce:

```text
assertion_source: OPPORTUNITY_MAP.md
citation_source: SYSTEM_STATE.md
source_role: citation
```

The citation proves the claim was propagated or seen. It does not upgrade the
claim's authority unless the citing document explicitly reasserts responsibility
for the claim.

Valid authority upgrade:

```text
SYSTEM_STATE.md says: "Current canonical state: X."
```

Invalid authority upgrade:

```text
SYSTEM_STATE.md includes a quoted paragraph from OPPORTUNITY_MAP.md.
```

The extractor must preserve this distinction so the evaluator can later ask:

```text
Who originally asserted this?
Who merely repeated it?
Who has authority to decide it?
```

## Granularity

Claims must be specific enough to change an operational decision and no more
specific than the decision requires.

Preferred rule:

```text
Extract the smallest assertion that can change the next action.
```

Examples:

```text
"The schema exists" -> claim if the next action is create or reuse schema.
"The schema has 18 tables" -> claim only if table count affects the decision.
"Table X has column Y" -> claim only if column Y affects validation or action.
```

Over-extraction is a failure mode. A claim graph filled with harmless details is
harder to audit and easier to trust incorrectly.

Under-extraction is also a failure mode. If a statement would change whether the
agent acts, pauses, asks for approval, or chooses rollback, it must be extracted.

## Meta-Claims

Meta-claims are first-class claims about how other claims should be interpreted.

Examples:

```text
SYSTEM_STATE.md is the current human-readable projection.
observation_center.toml is the canonical machine-readable observation queue.
Extensions must remain read-only.
Without formal trigger, mutations are limited to docs and AGENTS.md.
```

Meta-claims require a separate modality:

```text
modality: meta
```

They are not optional annotations. They govern conflict resolution, authority,
boundaries, and stop conditions. Missing a meta-claim can be more dangerous than
missing a factual claim because it corrupts how the system weighs evidence.

## Temporal Claims

Temporal claims must preserve their time condition.

Bad extraction:

```text
claim: "context vectors are authorized"
```

Better extraction:

```text
claim: "context vectors trigger was consumed on 2026-04-24"
claim: "context vectors experiment remains read-only and non-authoritative"
```

Dates, statuses, and phase words such as `waiting`, `active`, `consumed`,
`closed`, `blocked`, and `superseded` are part of the claim, not decoration.

## Negative Claims

Negative claims are allowed only when explicit.

Valid:

```text
The runtime boundary is not open.
No new runtime boundary is authorized.
```

Invalid:

```text
The file does not mention a runtime boundary.
therefore: "No runtime boundary is authorized."
```

The second example is structured absence at most. It can support an
insufficiency finding, not a factual negative claim.

## Unknown Claims

Unknown claims are valid when the source explicitly records uncertainty,
waiting state, missing evidence, or unresolved decision.

Examples:

```text
The third-party pilot is waiting for explicit go/no-go.
The exact source list is not confirmed.
The correct boundary is unresolved.
```

Unknown claims are useful because they prevent the agent from filling gaps with
plausible assumptions.

## Conflict-Relevant Claims

Extraction must prefer claims that can participate in conflict checks:

```text
status changed
authority changed
boundary changed
approval changed
source superseded another source
verification result changed
```

Claims that cannot affect action, sufficiency, conflict, authority, or
traceability should normally remain prose context.

## Criticality Hint

`criticality_hint` is not final risk classification. It is a conservative hint
for the evaluator.

Default rule:

```text
criticality_hint: unknown
```

The extractor may assign `high` or `critical` only when the source explicitly
uses operational markers such as:

```text
critical
high
blocked
stop condition
approval required
rollback
freeze
forbidden
must not
```

The extractor must not infer criticality from prose intensity, apparent
importance, or its own estimate of business impact. If no explicit marker is
present, the evaluator resolves criticality later using action type, boundary,
authority, and sufficiency.

## Non-Claims

Do not extract:

1. Stylistic evaluations.
2. Motivational prose.
3. Explanatory analogies.
4. Speculative statements without operational consequence.
5. Repeated citations with no new assertion.
6. Implementation ideas not tied to authorization, boundary, or acceptance.
7. Chain-of-thought style reasoning.

The extractor may preserve rationale summaries as evidence metadata, but it must
not store private reasoning traces as claims.

## Required Fixture Pressure

This contract is not mature unless it resolves at least these fixture classes
from `EPISTEMIC_RUNTIME_MATURITY_PLAN.md`:

1. A source explicitly asserts a state and a newer authoritative source
   contradicts it.
2. A source appears current but omits the decisive state recorded elsewhere.
3. A cited claim is repeated by a higher-level projection without being
   revalidated.
4. A meta-claim determines which source has authority.
5. A high-impact action depends on a claim with insufficient evidence.
6. A previous protocol document is correlated with bad downstream decisions.

Any future implementation of claim extraction must ship with fixture tests for
these classes before it can feed a claim graph.

## Fixture 9 Requirement

Fixture 9 is mandatory because it captures the hardest observed failure class:

```text
An apparently current diagnostic file omits the schema's real status, while a
more relevant continuity or operational-state source records that the schema
already exists.
```

Expected extraction:

```text
claim A: "schema exists"
  extraction_basis: explicit
  source_role: primary

claim B: "diagnostic source does not declare schema status"
  extraction_basis: structured_absence, only if schema status is required
  polarity: unknown

claim C: "diagnostic source is insufficient for schema-creation decisions"
  extraction_basis: supersession_absence
  polarity: unknown
```

Forbidden extraction:

```text
claim: "diagnostic says schema does not exist"
```

The forbidden extraction would fabricate a contradiction. The correct result is
insufficiency plus supersession, not false opposition.

## Acceptance Criteria

Before this contract can graduate into implementation:

1. At least three existing oracle fixtures must be mapped to expected extracted
   claims.
2. Fixture 9 must pass with no fabricated negative claim.
3. Meta-claims must be extracted and distinguishable from factual claims.
4. Citation must not upgrade authority by default.
5. Structured absence must produce `unknown`, not `negative`.
6. Over-extraction must be measured by a maximum claims-per-source threshold for
   bounded heads.
7. Every claim must preserve evidence span.
8. Every claim must be deterministic across repeated runs.

## Design Consequence

The first implementation should be boring on purpose:

```text
bounded text heads -> deterministic rules -> conservative claim candidates
```

It should prefer missing a marginal claim over inventing one. A later
human-assisted or model-assisted extractor can propose candidates, but the
canonical claim graph should only accept claims that satisfy this contract.
