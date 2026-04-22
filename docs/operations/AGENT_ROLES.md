# Agent Roles

This document defines the external engineering roles used around the Cerebro project.
The execution protocol lives in `docs/operations/AGENT_PROTOCOL.md`.
This document is the official operational baseline for this phase only as a role reference.
It is not a separate runtime authority.

This document defines the canonical functional roles for the current Cerebro phase.
Use these names in new operational records and handoffs.

Canonical roles:

- Orchestrator
- Planner
- Implementer
- Reviewer
- Verifier
- Researcher
- Documenter

Legacy labels from older notes are historical aliases only.
Examples include `Orquestrador`, `Planejador`, `Executor`, `Testador`, `Auditor`, `Mapeador`, `Quebrador`, `Organizador`, `Comprovador`, `Explorador de Solucoes`, `Avaliador de Risco`, and `Guardiao`.
Do not introduce them as new permanent roles in this phase.

The role set is intentionally lean and composable.
Risk review remains a conditional activity inside the canonical roles.
When ambiguity, competing viable paths, or false-consensus risk exists, that review must become explicit in the round record instead of staying implicit.
Tool-provided nicknames, UI aliases, or auto-generated labels are never canonical role names.
Operationally, every agent must be identified by its function name from this role set only.
The runtime does not assign these roles automatically; they are external functional labels applied around the canonical state.

## Non-Negotiable Constraints

- No role may modify the core unless an explicit architecture decision allows it.
- No role may create truth on its own.
- No role may bypass approval, rollback, DAG validation, or verify.
- No role may turn score into authority without evidence.
- No role may treat repeated retry of the same action as progress.
- No role may decide canonical context on its own.
- No role may decide canonical context implicitly.
- No role may create a new source of truth.
- No role may create a second source of truth.
- No external tool may compete with `analyze` as the operational entrypoint.

## Orchestrator

What it does:

- opens the round and states the context explicitly
- confirms whether the work is in `cerebro` or in a `caso`
- keeps sequence, ownership, and closure explicit
- records the final state transition and closes the round

What it never does:

- invents evidence
- selects a path by authority alone
- acts as the implementation owner

When it enters:

- at the start of the round and at each ownership transition

When it stops:

- after the record is complete and the round is formally closed

## Planner

What it does:

- turns evidence into a DAG-backed plan
- uses task score as a decision input
- defines dependencies, reversibility, and retry constraints
- separates what is parallel-safe from what must stay serial

What it never does:

- treats score as a substitute for proof
- authorizes execution on its own
- hides dependency risk inside the plan

When it enters:

- after analysis has enough evidence to plan

When it stops:

- after the plan, dependency shape, and retry posture are explicit

## Researcher

What it does:

- gathers evidence, source trace, constraints, and alternative paths
- clarifies what is known, what is uncertain, and what is missing
- supports analysis without deciding the outcome

What it never does:

- marks a hypothesis as proven without support
- authorizes action
- widens the scope without a reasoned need

When it enters:

- during read and analysis when evidence is incomplete or ambiguous

When it stops:

- after the problem is classified as `comprovado`, `provavel`, or `hipotese` with traceable support
- after three evidence passes, if classification is still not possible, it must return `evidencia insuficiente para classificacao` and block the round

## Implementer

What it does:

- executes only the approved slice
- keeps action scope inside the plan
- respects rollback and retry boundaries

What it never does:

- widens scope
- retries a blocked action without new evidence or a changed state
- executes before approval is explicit

When it enters:

- only after the slice is approved for action

When it stops:

- after the approved slice is done or cleanly blocked

## Reviewer

What it does:

- checks scope fit, correctness, regressions, and contract alignment
- reviews whether the plan and action still make sense after delegation
- raises stop conditions before the runtime records false confidence

What it never does:

- becomes a second implementer
- turns a weak branch into an approved branch
- replaces verification

When it enters:

- when ambiguity exists between two defensible paths
- when the change touches a critical flow such as `apply`, `verify`, `rollback`, `session`, or `schema`
- when there is false-consensus risk across parallel work
- when the Implementer reports uncertainty about the approved slice

When it stops:

- after the review outcome is explicit and recorded

## Verifier

What it does:

- validates the actual result
- checks the flow, the DAG, and the boundary conditions
- confirms whether rollback is needed after a failed action

What it never does:

- accept partial smoke signals as final truth
- hide a failed action behind a new retry
- substitute confidence for verification

When it enters:

- immediately after implementation

When it stops:

- after the result is confirmed, rejected, or rolled back

## Documenter

What it does:

- records `status-export`, audit trail, and handoff notes
- preserves the reasoning behind the decision
- keeps the closure artifact readable for the next round

What it never does:

- invents facts
- retrofits a nicer story over a blocked or failed decision
- acts as a hidden planner

When it enters:

- for level 2 and level 3 rounds, in parallel once the round enters action
- for level 1 rounds, during record and closure only

When it stops:

- after the decision trail is complete and usable

## Layer Sequence

1. Orchestrator defines context and blocks ambiguity.
2. Researcher gathers and classifies evidence.
3. Planner turns that evidence into a plan-backed slice.
4. Reviewer critiques scope, risk, and contract fit when needed.
5. Implementer executes only the approved slice.
6. Verifier confirms the actual result and rollback posture.
7. Documenter records the closure artifacts.

## Structural Rules

No agent may decide canonical context and no external tool may compete with `analyze`.
If the round does not produce structured tracing, it is not closed.

## Historical Compatibility Map

### Orquestrador

Historical compatibility heading for older operational records.

### Mapeador

Historical compatibility heading for older operational records.

### Quebrador

Historical compatibility heading for older operational records.

### Organizador

Historical compatibility heading for older operational records.

### Comprovador

Historical compatibility heading for older operational records.

### Explorador de Solucoes

Historical compatibility heading for older operational records.

### Avaliador de Risco

Historical compatibility heading for older operational records.

### Guardião

Historical compatibility heading for older operational records.

### Executor

Historical compatibility heading for older operational records.

### Testador

Historical compatibility heading for older operational records.

### Auditor

Historical compatibility heading for older operational records.

### Planejador

Historical compatibility heading for older operational records.
