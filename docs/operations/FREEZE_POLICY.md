# Deliberate Freeze Policy

## Current State

- The core runtime is complete under the v1 contract.
- The low-risk read-only export slice is exhausted under the current contract.
- External-analysis preparation reached the safe conceptual limit without implementing analysis behavior.
- `alignment-export` remains blocked because the contract still has no canonical alignment artifact.
- The project is deliberately frozen for new capability growth until an explicit resume trigger is met.
- The current layer is considered complete until a formal next-layer decision says otherwise.

This freeze applies to growth, not to corrective maintenance. Bug fixes, proportional regression coverage, and factual documentation updates may continue when needed.

Operational rule:

- when there is no concrete repeated unmet use case, do not evolve the system
- operate it through the approved daily protocol instead

## Conservatism Assessment

- Current classification: healthy conservatism, not excessive conservatism.

This classification is based on the current facts:

- adversarial revalidation found no critical or moderate failures
- the low-risk read-only export slice was exhausted explicitly, not prematurely
- the boundary between core and external consumers is clear, tested, and documented
- no concrete repeated unmet use case is currently recorded against `cerebro analyze` plus the existing exports

The classification must change only if a real repeated unmet use case is documented and shown to be unsatisfied by the current runtime and export surface.

## Minimum Safe Advance Policy

When the freeze is broken, growth may proceed only through one minimum safe increment at a time.

That increment must:

- remain fully external to the core
- either operate only on the canonical snapshot or persisted validation metadata already exposed by the public API, or stay in the narrower assistive-discovery slice
- never revalidate the runtime independently
- never write inside `.cerebro/`
- never introduce a new canonical artifact
- never alter `analyze`, `validate`, `state.json`, the schema, or session policy
- stay small enough to be tested end-to-end with proportional adversarial coverage
- be validated in a clean environment before it is treated as accepted growth

If a proposal cannot fit inside one such increment, it is not a minimum safe advance and must stop for explicit architecture review.

## Assistive Discovery Carve-Out

An assistive-discovery increment may scan project-tree paths and filenames outside the canonical snapshot only when it remains fully non-authoritative.

It must:

- suggest candidates only
- avoid reading file contents for classification
- avoid creating or modifying `.cerebro/`
- avoid calling `import-context`
- avoid registering `sources`
- present heuristics as assistance, never as project truth

If assistive discovery starts deciding canonical context or acting as a gate, it leaves the safe carve-out and must stop.

## Formal Resume Trigger

The deliberate freeze may be broken only when at least one of the following is true:

- a concrete and repeated use case exists that the current `cerebro analyze` flow plus current exports cannot satisfy cleanly
- a real operational need is documented and shown to be unmet by the current runtime and export surface
- an explicit architecture decision authorizes opening one narrowly defined external-analysis read-only use case

The following do not break the freeze:

- curiosity
- aesthetic improvement or a desire to make the system look richer
- an abstract desire to get "closer to the ideal"
- speculative feature growth without a recurring use case
- pressure to invent alignment, semantic understanding, or a new authority surface

## Review Cadence

The freeze posture is re-evaluated on a documented cadence so that staleness cannot silently harden into permanence, without turning the evaluation itself into a growth driver.

Operational state for this cadence lives in `docs/operations/freeze_review.toml`. That TOML is a derived operational-discipline artifact. It is not canonical runtime authority, must not be read or written by `core/` or by any runtime mutator, and must never be treated as a second source of truth about state.

The cadence tracks four fields in `[review]`:

- `mandatory_review_after_rounds` — maximum operational rounds since `last_review_date` before a review becomes mandatory
- `mandatory_review_after_days` — maximum calendar days since `last_review_date` before a review becomes mandatory
- `trigger_count_since_review` — count of Formal Resume Trigger candidates observed since `last_review_date`
- `round_count_since_review` — count of completed operational rounds since `last_review_date`

A review is mandatory when any one of these is true:

- `round_count_since_review >= mandatory_review_after_rounds`
- the elapsed days since `last_review_date` reach `mandatory_review_after_days`
- `trigger_count_since_review` is non-zero

A mandatory review only requires that the freeze posture be re-assessed and re-recorded. It does not authorize growth. Growth still requires a Formal Resume Trigger and the Resume Protocol.

The review exists to re-check whether the current approved operational surface still remains sufficient, not to broaden authority by default. If a review records a candidate opening, it must preserve the same gate language already used elsewhere in this policy: `a concrete and repeated use case exists that the current approved operational surface cannot satisfy cleanly`.

The same review record must also preserve the Resume Protocol wording when documenting why a candidate opening is still blocked: `Record why the current approved operational surface does not satisfy it cleanly.`

If a review escalates beyond confirmation, the only growth shape it may point at is `one narrowly defined additional external-analysis read-only increment beyond the current classifier`, and that still remains subject to the Formal Resume Trigger and Resume Protocol.

Each completed review records its outcome in `[last_outcome]` using a closed vocabulary for `verdict`:

- `freeze_confirmed` — freeze posture remains; no resume trigger accepted
- `freeze_confirmed_with_carveout` — freeze posture remains; an existing approved carve-out was re-affirmed or narrowed
- `resume_authorized` — a Formal Resume Trigger was accepted and the Resume Protocol applies
- `resume_pending_evidence` — a candidate trigger was recorded but evidence is insufficient; review must re-occur within half the normal cadence

After each review, `last_review_date`, `next_review_due`, `trigger_count_since_review`, and `round_count_since_review` must be reset consistently with the recorded verdict.

## Rejection Criteria

Reject a proposed advance immediately when it is based on:

- aesthetics or surface polish alone
- vague convenience without repeated operational cost
- a desire for the system to appear more intelligent than it is
- aliases or wording that suggest behavior the runtime does not have
- any new authority outside the core
- any second source of truth
- any attempt to treat read-only exports or external analysis as corrective runtime behavior

## Resume Protocol

1. Write one concrete use case in operational terms.
2. Record why the current `analyze` flow plus current exports do not satisfy it cleanly.
3. Classify the proposal as `export`, `analysis`, `integration`, or the already-approved `assistive discovery` carve-out.
4. Check whether it requires a new canonical concept, a new source of truth, or core changes.
5. Check whether it touches `validate`, `analyze`, `state.json`, session policy, or runtime authority.
6. Authorize only if it stays external, derived, read-only where expected, and proportional adversarial coverage can be added.
7. Otherwise block it explicitly and record the stop condition before any implementation starts.

## Pilot Status

- Approved minimum safe advance:
  - `bootstrap-scan` as assistive discovery only
  - local automation bridge MVP as `integration` only

The approved pilot remains inside the freeze policy because it:

- does not create `.cerebro`
- does not register `sources`
- does not call `import-context`
- does not alter the runtime contract
- reduces bootstrap friction without gaining authority over state

The approved automation bridge remains inside the freeze policy because it:

- stays outside tracked runtime code and outside `.cerebro/`
- packages explicit task and context handoff without deciding canonical context
- uses disposable structured logs instead of project memory
- does not register `sources`, call `import-context`, or alter `state.json`
- keeps write-capable or core-sensitive work behind explicit human approval

Daily-use discipline for the approved automation bridge:

- use it only for mechanical execution, repeated audit work, and structured external logging
- do not use it to choose context, classify project importance, or substitute any canonical runtime step
- always return to Cerebro through `checkpoint` and `analyze` for real continuity decisions
- treat accumulated run directories as disposable operational residue, not as project memory
- if bridge logs start being consulted as the state of the project, stop and treat that as a regression

If that bridge starts acting as hidden memory, hidden routing authority, or automatic runtime control, it leaves the minimum safe slice and must stop.

## Infrastructure Posture

The default posture is now infrastructure use, not ongoing construction.

The system should be treated as:

- stable for daily operation
- frozen for automatic growth
- open only to corrective maintenance or formally approved next-layer work

## Out Of Scope While Frozen

- heuristic context reconstruction
- pseudo-alignment without a canonical artifact
- core expansion or schema growth
- unapproved CLI aliases or synonyms
- external agents or integrations with authority over runtime state
- any second source of truth
