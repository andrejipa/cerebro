# Deliberate Freeze Policy

## Current State

- The core runtime is complete under the v1 contract.
- The low-risk read-only export slice is exhausted under the current contract.
- External-analysis preparation reached the safe conceptual limit without implementing analysis behavior.
- `alignment-export` remains blocked because the contract still has no canonical alignment artifact.
- The project is deliberately frozen for new capability growth until an explicit resume trigger is met.

This freeze applies to growth, not to corrective maintenance. Bug fixes, proportional regression coverage, and factual documentation updates may continue when needed.

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
- operate only on the canonical snapshot or persisted validation metadata already exposed by the public API
- never revalidate the runtime independently
- never write inside `.cerebro/`
- never introduce a new canonical artifact
- never alter `analyze`, `validate`, `state.json`, the schema, or session policy
- stay small enough to be tested end-to-end with proportional adversarial coverage
- be validated in a clean environment before it is treated as accepted growth

If a proposal cannot fit inside one such increment, it is not a minimum safe advance and must stop for explicit architecture review.

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
3. Classify the proposal as `export`, `analysis`, or another external shape.
4. Check whether it requires a new canonical concept, a new source of truth, or core changes.
5. Check whether it touches `validate`, `analyze`, `state.json`, session policy, or runtime authority.
6. Authorize only if it stays external, derived, read-only where expected, and proportional adversarial coverage can be added.
7. Otherwise block it explicitly and record the stop condition before any implementation starts.

## Pilot Status

- No pilot is currently authorized.

Reason:

- no candidate is currently both clearly valuable and clearly justified by a concrete repeated unmet use case
- the remaining plausible next steps now sit in either external analysis or medium-risk graph-style derivation
- opening either one without a documented case would be continuation by momentum rather than minimum safe advance

## Out Of Scope While Frozen

- heuristic context reconstruction
- pseudo-alignment without a canonical artifact
- core expansion or schema growth
- unapproved CLI aliases or synonyms
- external agents or integrations with authority over runtime state
- any second source of truth
