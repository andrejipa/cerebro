# Handoff: External Analysis Boundary

- State: stopped at the safe conceptual boundary
- Where it stopped:
  - the project now documents what future external `analysis` may and may not do, but no analysis module was implemented
- What is already safe:
  - `export`, `analysis`, and `integration` are distinct consumer shapes
  - allowed `analysis` is limited to read-only transformations of canonical fields and persisted validation metadata
  - forbidden `analysis` includes inference, inspection of source bodies, reopening validation, and any decision on behalf of the runtime
- What was validated:
  - documentation now converges on the same boundary across extension and integration guidance
- Risk that blocks further progress:
  - the next step would require selecting a specific analysis use case and output scope, which would be a new public behavior rather than boundary work
- Decision still required:
  - choose the first concrete external analysis use case or keep the project in the current export-only stage
- First action after release:
  - take one candidate analysis use case from the roadmap and test it against the documented allowed and forbidden analysis boundary before implementation
