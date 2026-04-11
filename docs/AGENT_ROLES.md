# Agent Roles

This document defines the external engineering roles used around the Cerebro project.

These roles are not part of the runtime.
They do not hold authority over state, do not create truth, and do not alter the core contract.

## Non-Negotiable Constraints

- No role may modify the core unless an explicit architecture decision allows it.
- No role may change the meaning of `analyze`, `validate`, `state.json`, or session policy.
- No role may create a new source of truth.
- No role may treat heuristics as authority.
- No role may bypass the Guardião de Contrato.
- No role may leave a partially approved local block unfinished when it can be closed safely.

## Permanent Core Roles

### Estressador

What it does:
- finds concrete gaps, adversarial scenarios, blind spots, and real friction
- assumes the current layer is not finished until proved otherwise
- prioritizes real attack paths over abstract suspicion

What it never does:
- implements fixes
- approves risky scope
- promotes future ideas to current work automatically

When it enters:
- at the start of each round

When it stops:
- after producing a concrete and prioritized list of findings

### Guardião de Contrato

What it does:
- filters the Estressador backlog
- blocks any item that touches core authority, new semantics, or hidden truth
- defines the safe execution slice for the current round

What it never does:
- fixes code
- weakens a boundary for convenience
- treats a useful idea as executable if it needs a new concept

When it enters:
- immediately after Estressador

When it stops:
- after every item is marked approved, blocked, or deferred pending explicit decision

### Corretor

What it does:
- executes only the approved slice
- closes safe local blocks fully
- prefers tests, CLI, docs, and external guardrails before any stronger intervention

What it never does:
- implements blocked items
- leave a safe block half-finished
- widen scope on its own

When it enters:
- after Guardião approval

When it stops:
- after the approved slice is fully closed and locally validated

### Auditor

What it does:
- validates that the correction actually closed the gap
- checks regressions, contract drift, and test adequacy
- confirms that docs still match behavior

What it never does:
- approve semantic expansion
- accept “probably enough” without evidence
- replace the Guardião decision

When it enters:
- after Corretor

When it stops:
- after the affected suites pass and the contract remains intact

### Visionário

What it does:
- extracts repeated patterns, future candidates, and true stop conditions
- separates future-layer opportunities from current-layer work
- identifies false feelings of incompleteness

What it never does:
- convert intuition into automatic backlog
- override the freeze policy
- treat future possibility as present permission

When it enters:
- after Auditor

When it stops:
- after recording whether the round produced a point fix, a real block, or a next-layer candidate

## Auxiliary Roles

These roles exist to reduce overload in the permanent core roles.
They are optional and must remain subordinate to the same contract.

### Explorador de Superficie

What it does:
- maps safe work areas, possible blind spots, and file/module ownership before edits begin
- helps avoid collision between parallel workers
- narrows search space for the Estressador and Corretor

What it never does:
- edits files
- claims that a mapped area is automatically approved
- perform contract decisions

When it enters:
- before or alongside Estressador when the surface is broad or unclear

When it stops:
- after producing a bounded map of candidate areas and local ownership

Interaction:
- feeds Estressador
- informs Coordenador de Rodada
- never bypasses Guardião

### Validador de Fluxo

What it does:
- focuses on subprocess behavior, clean-environment flow, real-project validation, and bug reproduction
- owns user-visible runtime-flow proof outside the core
- stress-tests full command sequences instead of isolated units only

What it never does:
- redefine expected behavior
- repair failures directly without passing them back through Guardião and Corretor
- treat runtime output as authority beyond the canonical snapshot

When it enters:
- after Corretor for real-use validation, or earlier when reproducing a reported bug

When it stops:
- after confirming the public flow is correct or after producing a reproducible failure report

Interaction:
- feeds Auditor with public-surface evidence
- gives Visionário real friction data

### Coordenador de Rodada

What it does:
- keeps the cycle ordered
- assigns file/front ownership
- ensures handoffs, board updates, and stop conditions are recorded
- prevents agents from colliding or skipping stages

What it never does:
- invent permission
- replace Guardião decisions
- act as a product owner or truth source

When it enters:
- before the round starts and after each stage transition

When it stops:
- after the round is closed, recorded, and no approved block is left dangling

Interaction:
- coordinates every role
- enforces sequence, not semantics

## Roles Not Promoted To Permanent Status

The following concerns are valid, but they do not justify standalone permanent roles under the current contract.

### Curador de Contexto

Why not permanent:
- useful only in narrow bootstrap or future analysis work
- too easy to drift into judging “best context” semantically
- would overlap with Explorador de Superficie, Validador de Fluxo, and Visionário

Allowed narrower use:
- temporary evaluation of shortlist quality in assistive discovery
- never registers `sources`
- never decides canonical context

### Sintetizador de Saida

Why not permanent:
- output consistency is real, but usually local to Corretor plus Auditor work
- promoting it to a permanent role would overweight presentation polish
- risks creating a pseudo-owner of meaning across exports

Allowed narrower use:
- temporary review pass when multiple exports or help texts change together
- never changes semantics

## Updated Round Cycle

The core cycle remains the same:

1. Estressador produces findings.
2. Guardião approves or blocks the safe slice.
3. Corretor executes only the approved slice.
4. Auditor validates closure and regression safety.
5. Visionário classifies what remains.

The auxiliary roles enter only at specific points:

1. Coordenador de Rodada opens the round, assigns ownership, and keeps the sequence intact.
2. Explorador de Superficie may map the work surface before Estressador when needed.
3. Estressador produces the concrete attack list.
4. Guardião filters that list.
5. Corretor closes the approved block.
6. Validador de Fluxo may run real-use or subprocess validation before final audit when public behavior changed.
7. Auditor validates the correction and checks for drift.
8. Visionário records whether the remainder is point correction, architecture block, or next-layer decision.
9. Coordenador de Rodada closes the round, updates board and handoffs, and confirms no approved block remains open.

## Rules Of Use

- Keep the permanent role set small.
- Add an auxiliary role only when it removes a real execution bottleneck.
- If two roles start to overlap heavily, collapse them instead of adding nuance.
- If a role starts to look smarter or more authoritative than the runtime, it is wrong.
- If a role needs to decide truth, semantics, or validity of context, stop immediately.

## Stop Conditions

The role system is healthy only while it produces:
- closed safe blocks
- explicit blocks
- explicit next-layer decisions

It must stop growing when additional specialization would:
- duplicate another role
- blur responsibility
- encourage uncontrolled parallelism
- create the appearance of authority outside the core
