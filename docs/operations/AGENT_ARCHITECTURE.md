# Agent Architecture

This document describes the current multi-agent operating architecture for Cerebro.
It is descriptive, not aspirational. It must not be read as a promise of capabilities that the runtime does not already expose.

## Current Runtime Shape

The runtime is a scored, gated, auditable task system:

- each task has a score and the score influences task selection
- each action has its own retry history and retry block
- approval, rollback, DAG validation, and verify are separate control points
- approvals are task-scoped and active approvals reset when the plan generation changes
- each task derives its own `workload_mode` and `work_unit_kind`
- `status-export` exposes the current decision surface, including read-only decision provenance and replay diagnostics when available
- the read-only exports are derived views, not a second source of truth
- the audit trail records selection, approvals, retries, verification, and closure

The architecture does not depend on hidden authority.
It depends on explicit evidence, explicit delegation, and explicit records.

## Canonical Roles

The canonical roles for this phase are:

- Orchestrator
- Planner
- Implementer
- Reviewer
- Verifier
- Researcher
- Documenter

Legacy labels from older notes are non-canonical.
They may be read as historical aliases only.

## Canonical Flow

The canonical operating flow is:

`READ -> ANALYZE -> PLAN -> DELEGATE -> ACT -> VERIFY -> RECORD`

### READ

Read the current task state, approvals, DAG shape, retry state, verification history, and audit trail.

### ANALYZE

Separate facts from hypotheses, identify blockers, score tasks, and expose the decision trade-offs.

### PLAN

Build the next slice as a DAG-backed plan, define dependencies, and mark what can and cannot run in parallel.

### DELEGATE

Assign independent slices to canonical roles only when the slices are safe to separate.

### ACT

Implement only the approved slice.

### VERIFY

Check the result against the expected state, the DAG, and the approval boundary.
If a reversible action fails verification, prefer rollback over blind retry.

### RECORD

Write the decision trail, `status-export`, audit trail, and any handoff data needed for the next round.

## Decision Discipline

Every non-trivial decision should record:

- the task score
- the supporting evidence
- the blocking risk
- the approval state
- the rollback option
- the verification target
- the retry rule

When ambiguity, competing defensible paths, medium confidence, or false-consensus risk exists, the decision record should also capture an explicit debate record: problem, primary hypothesis, alternative hypothesis, critique findings, decision, and verification.

If the evidence is weak, the decision stays blocked.
If the same action fails repeatedly without new evidence, retry stays blocked until the state changes or a new approval path exists.
If the DAG is invalid or cyclic, planning stops before delegation.
If only one defensible path remains, the round records that dominance explicitly instead of fabricating parallel work.
If repeated iterations produce no new evidence or approved-slice reduction, the round returns to planning instead of widening branches.

## Positive Reinforcement And Success Memory

The runtime does not use hidden learning to improve decisions.
It can reuse explicit verified success memory as operational context:

- record which evidence pattern, score range, approval shape, task profile, and verify target led to a successful closure
- prefer a previously successful approach only when the current evidence class and approval boundary still match
- allow a current task to receive limited score reinforcement when it matches an explicit verified success pattern
- reduce that reinforcement immediately when recent blocked or failed attempts challenge the pattern
- treat a successful prior outcome as heuristic support, not as a substitute for evidence
- record why a successful path is being reused so the next round can verify the same reasoning

Success memory is explicit and traceable.
It is not automatic reinforcement learning.

## Parallel Delegation Rules

Parallel delegation is allowed only when all of the following are true:

- the slices are independent
- the slices do not write the same surface
- the approval scope covers each branch
- no branch depends on unresolved verification
- a join point exists for verification and record

Parallel delegation is not the default.
It is a controlled optimization, not a replacement for planning.
Open parallel comparison only when at least two independent and defensible approaches remain and the comparison is operationally useful.
Do not open decorative branches when one defensible path already dominates.

## Parallel Comparison And Consolidation

When multiple independent approaches are worth comparing, the operating protocol may compare them in parallel only if the branch rules above are satisfied.

The consolidation point must compare:

- evidence quality
- score
- reversibility
- rollback cost
- approval burden
- verification burden
- residual risk
- whether the approach matches a previously successful pattern

Consolidation must then:

- select one path as the operational winner
- record why the other paths lost
- keep the losing paths available as evidence, not as silent noise
- avoid merging incompatible branches into a false consensus
- supersede the prior head explicitly when the same subject is consolidated again

Read-only consumers must treat stale or replayed valid consolidation records as history, not as the active winner.

If the comparison does not produce a defensible winner, the round stays blocked or returns to planning.

## What The Runtime Does Not Promise

The runtime does not promise:

- automatic solution discovery
- unlimited retries
- implicit approvals
- parallel work across dependent branches
- a built-in role scheduler or hidden multi-agent authority
- rollback when the action graph does not support it
- a closed decision when the audit trail is incomplete
- hidden learning from prior success
- automatic winner selection without evidence and approval

The architecture must stay aligned with the real runtime, not with the desired future shape.
