# Handoff: Revised Operational Model Baselined

- State: revised protocol baselined in a documented round
- Note: historical handoff; the role names below are non-canonical labels from that external round.
- This handoff records a closed external round only; team-shape and approval wording below do not define current canonical roles or baseline authority.

## Where This Round Stopped

- Orquestrador made the context explicit as `cerebro`, not a live `caso`
- the revised external protocol was synchronized across roles, protocol, board, report, and documentary architecture tests
- the round closed with documentation and test changes only

## What Is Safe Now

- The statements in this section describe the closed external round only and are for reference, not current canonical role authority.
- the historical operational baseline for that round was `Orquestrador -> Mapeador -> Quebrador -> Organizador -> Comprovador -> Explorador de Solucoes -> Avaliador de Risco -> Guardião -> Executor -> Testador -> Auditor -> Planejador`
- `Avaliador de Risco` is now treated as a conditional role, not default bureaucracy
- `Guardião` now has the explicit states `permitido`, `permitido com aprovacao humana`, and `bloqueado`
- the revised team still remains fully external to runtime authority

## What Was Validated

- protocol drift around context gating, evidence classes, approval states, and tracing was documented as repository-proven
- a minimum safe documentary slice was executed without touching runtime code
- board, report, handoff, and tests now record the revised model explicitly
- the focused documentation suite remained green after the update

## Blocking Risk

- any future round that skips the `cerebro` versus `caso` gate risks unauthorized work
- any future role or tool that tries to decide canonical context or compete with `analyze` would violate the runtime boundary
- treating `Avaliador de Risco` as mandatory in every round would create ornamental process weight

## Decision Needed

- The approval wording below is preserved as historical handoff context from that round and is non-canonical for current operation.
- none for the revised documentation baseline
- future sensitive actions may proceed only when Guardião explicitly returns `permitido com aprovacao humana` and that approval is actually granted
- fiscal cases like `Portal` still require explicit human approval before materially altering EFD behavior
- for that closed round, the team shape remained frozen unless a repeated real bottleneck appeared

## First Exact Action After Release

- start future external rounds by asking whether the work is in `cerebro` or in a `caso`
- record Checkpoint A, Checkpoint B, and Checkpoint C explicitly whenever the round reaches them
- keep `analyze` as the only canonical operational entrypoint and keep external tools subordinate to it
