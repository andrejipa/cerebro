# Agent Protocol

This document defines the operational protocol for external agent work around the Cerebro project.

It prepares the next layer of engineering coordination.
It does not open the next product layer, does not change the freeze policy, and does not authorize new runtime semantics.
The role and protocol shape below is the official stable baseline for continuous use until a formal team-layer trigger says otherwise.

## Fixed Role Set

Core roles:
- Estressador
- Guardião de Contrato
- Corretor
- Auditor
- Visionário

Auxiliary roles:
- Triador de Casos
- Avaliador de Evidencia
- Explorador de Superficie
- Validador de Fluxo
- Coordenador de Rodada

No additional permanent role should be introduced unless `AGENT_ROLES.md` is revised explicitly.
No auxiliary role should be added, promoted, or kept by default unless repeated real rounds demonstrate a concrete unresolved bottleneck.
Treat the current role roster as closed for ordinary operation.

## Round States

Each round must move through these states in order:

1. `opened`
2. `mapped` or `skipped-mapping`
3. `stressed`
4. `triaged` or `skipped-triage`
5. `evidenced` or `skipped-evidence`
6. `guarded`
7. `correcting` or `no-safe-fix`
8. `validated`
9. `classified`
10. `closed`

No round may skip `guarded`, `validated`, or `closed`.

## Base Round Protocol

1. Coordenador de Rodada opens the round, records the front, and assigns temporary ownership.
2. Explorador de Superficie enters only if the surface is broad, unclear, or collision-prone.
3. Estressador produces a concrete, prioritized list of executable gaps or real friction.
4. Triador de Casos enters only if the finding set is noisy, duplicated, or spread across multiple fronts.
5. Avaliador de Evidencia enters only if a finding is not yet clearly demonstrated.
6. Guardião de Contrato marks each item as `approved`, `blocked`, or `decision-required`.
7. Corretor acts only on `approved` items and closes each local block fully before switching fronts.
8. Validador de Fluxo enters only if the approved slice changes public behavior, subprocess flow, real-use flow, or bug reproduction.
9. Auditor validates the affected suites, checks contract drift, and confirms that the approved slice is actually closed.
10. Visionário classifies the remainder as `point-fix`, `architecture-block`, or `next-layer-decision`.
11. Coordenador de Rodada records the outcome in board and handoffs, releases ownership, and closes the round.

If `approved` is empty after Guardião review, Corretor does nothing and the round moves directly to validation and classification.

## Ownership And Collision Rules

Each active block must declare:
- front
- role currently acting
- target files or modules
- target problem or scenario
- state

Ownership rules:
- one active editor per file at a time
- one active role owner per front at a time
- exploration may overlap with stress only when it does not edit
- validation may overlap with documentation review only when neither changes files

Temporary reservation rules:
- a file or front becomes reserved when Coordenador records an active owner
- reservation ends when the local block is validated or explicitly abandoned
- if a second role needs the same area, it must wait or switch fronts

No role may silently take over an area already reserved to another role.

## Handoff Format

Every handoff must include:
- `where_stopped`
- `what_is_safe_now`
- `what_was_validated`
- `blocking_risk`
- `decision_needed`
- `first_exact_action_after_release`

### Estressador Handoff

Required fields:
- concrete gap or adversarial scenario
- reproduction path
- expected risk level
- whether the gap appears external-safe or likely blocked

### Triador de Casos Handoff

Required fields:
- grouped findings
- deduplicated queue order
- affected fronts
- what was merged as the same case

### Avaliador de Evidencia Handoff

Required fields:
- evidence status: `demonstrated`, `needs-repro`, or `insufficient-evidence`
- exact proof used
- whether a finding is safe to send to Guardião
- what remains unproven

### Guardião Handoff

Required fields:
- item status: `approved`, `blocked`, or `decision-required`
- exact contract reason
- stop line if blocked
- allowed slice if approved

### Corretor Handoff

Required fields:
- files changed
- exact scope closed
- tests run locally
- anything intentionally left untouched

### Auditor Handoff

Required fields:
- suites executed
- result
- residual risk
- whether the fix really closed the approved gap

### Visionário Handoff

Required fields:
- repeated pattern, if any
- whether the remainder is only `point-fix`, `architecture-block`, or `next-layer-decision`
- whether there is false incompleteness without executable work

### Auxiliary Handoffs

Use only when they add clarity.

Explorador de Superficie:
- mapped fronts
- ownership hints
- collision risks

Triador de Casos:
- merged or split findings
- queue order
- duplicate clusters

Avaliador de Evidencia:
- proof status per finding
- reproduction quality
- missing evidence, if any

Validador de Fluxo:
- exact public flow exercised
- environment used
- observed behavior
- reproducible friction, if any

Coordenador de Rodada:
- round state transitions
- ownership assignments
- handoff completeness
- closure confirmation

## Auxiliary Activation Policy

Explorador de Superficie:
- activate only before edits in an uncertain or broad surface
- do not activate for a single clear local fix

Triador de Casos:
- activate only when the finding set is noisy, duplicated, or cross-front
- do not activate for a single clear issue

Avaliador de Evidencia:
- activate only when the evidence behind a finding is incomplete, indirect, or disputed
- do not activate when the issue is already reproducible and well demonstrated

Validador de Fluxo:
- activate only for subprocess behavior, real-use flow, clean-environment flow, or bug reproduction
- do not activate for purely local static documentary edits

Coordenador de Rodada:
- activate whenever more than one role or front is active
- may remain lightweight in a trivial one-block round, but the round sequence still applies

Auxiliary roles never create work on their own.
They support the core cycle and then leave.

## Role Creation And Removal Criteria

Add a new auxiliary role only when all of the following are true:
- a concrete execution bottleneck recurs across rounds
- the bottleneck cannot be resolved by tightening an existing role
- the new role has one clear responsibility and one clear stop condition
- the new role improves closure, collision control, or observability more than it increases coordination cost

Remove or merge a role when:
- its outputs duplicate another role's outputs
- it mostly restates board or handoff data without improving decisions
- it starts to look like a hidden owner of truth, priority, or semantics

In the absence of a repeated demonstrated bottleneck, the current team remains frozen as the operational baseline.

## Stop Rules

Stop a local block immediately when it would require:
- changing the core
- changing `analyze`, `validate`, `state.json`, schema, or session policy
- creating a canonical artifact
- promoting heuristics to authority
- creating a second source of truth
- opening analysis behavior without explicit next-layer authorization

Stop a round when:
- no approved work remains
- only blocked or decision-required items remain
- the remaining work is cosmetic and not structurally useful

## Process Guardrails

- The core cycle remains mandatory.
- Auxiliary roles cannot replace Estressador, Guardião, Corretor, Auditor, or Visionário.
- A role may not act outside its stage.
- Validation is mandatory for every approved change.
- Board and handoffs must be updated before the round is considered closed.

If the protocol becomes implicit again, documentation and tests should fail until the explicit flow is restored.

## Relationship To The Freeze

This protocol does not break the freeze.

It only defines how external work must be coordinated when:
- corrective maintenance is legitimate
- proportional regression work is needed
- a future next-layer decision is explicitly approved

Until such a decision exists, the protocol prepares the next layer but does not initiate it.
