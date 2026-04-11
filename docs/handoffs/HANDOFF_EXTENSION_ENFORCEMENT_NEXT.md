# Handoff: extension enforcement next slice

- Front: regression protection
- State: diagnostic stop
- Stop point: current tests now cover package drift, extension READMEs, shared runtime-path rejection, main dynamic evasions, and tracked-file allowlisting for `extensions/`
- Reason: the next safe slice is test-only hardening, not runtime changes
- Risk of continuing without decision:
  - adding a generic extension framework would exceed the current contract
  - adding runtime hooks for enforcement would move policy into product behavior
- Safe next action after release:
  - keep hardening outside the runtime and decide whether executable-mode or symlink-specific checks add enough value beyond the current tracked-file enforcement and documentation
