# Handoff: extension enforcement next slice

- Front: regression protection
- State: diagnostic stop
- Stop point: current tests now cover package drift, extension READMEs, shared runtime-path rejection, main dynamic evasions, direct filesystem-read bans in extensions, process-spawning bans, tracked-file allowlisting, and Git-mode checks for symlink/executable entries in `extensions/`
- Reason: the next safe slice is test-only hardening, not runtime changes
- Risk of continuing without decision:
  - adding a generic extension framework would exceed the current contract
  - adding runtime hooks for enforcement would move policy into product behavior
- Safe next action after release:
  - keep hardening outside the runtime and stop until a concrete new evasion path appears or the public surface actually changes
