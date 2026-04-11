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
  - keep this front blocked unless a future architecture decision adds a canonical alignment artifact to the contract
