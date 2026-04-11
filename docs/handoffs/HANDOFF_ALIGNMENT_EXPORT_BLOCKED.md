# Handoff: alignment-export blocked

- Front: extensions read-only
- State: blocked
- Stop point: no implementation started
- Reason: the current contract exposes canonical state, validation metadata, session presence, and checkpoint data, but it does not define a canonical `alignment` artifact or lineage model
- Risk of continuing without decision:
  - inventing alignment fields would create new semantics outside the core
  - reusing legacy terminology directly would reintroduce ambiguous authority
  - duplicating validation logic would weaken the boundary between core and extension
- Safe next action after release:
  - define `alignment-export` strictly as a derived consistency view over already-canonical fields, or reject it if that definition still depends on inferred semantics
