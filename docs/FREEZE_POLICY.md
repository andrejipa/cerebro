# Deliberate Freeze Policy

## Current State

- The core runtime is complete under the v1 contract.
- The low-risk read-only export slice is exhausted under the current contract.
- External-analysis preparation reached the safe conceptual limit without implementing analysis behavior.
- `alignment-export` remains blocked because the contract still has no canonical alignment artifact.
- The project is deliberately frozen for new capability growth until an explicit resume trigger is met.

This freeze applies to growth, not to corrective maintenance. Bug fixes, proportional regression coverage, and factual documentation updates may continue when needed.

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

## Resume Protocol

1. Write one concrete use case in operational terms.
2. Record why the current `analyze` flow plus current exports do not satisfy it cleanly.
3. Classify the proposal as `export`, `analysis`, or another external shape.
4. Check whether it requires a new canonical concept, a new source of truth, or core changes.
5. Check whether it touches `validate`, `analyze`, `state.json`, session policy, or runtime authority.
6. Authorize only if it stays external, derived, read-only where expected, and proportional adversarial coverage can be added.
7. Otherwise block it explicitly and record the stop condition before any implementation starts.

## Out Of Scope While Frozen

- heuristic context reconstruction
- pseudo-alignment without a canonical artifact
- core expansion or schema growth
- unapproved CLI aliases or synonyms
- external agents or integrations with authority over runtime state
- any second source of truth
