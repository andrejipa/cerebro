# Agent Protocol

This document defines the operational protocol for external agent work around Cerebro.
It is descriptive, not aspirational.
It must not be read as a promise of runtime features that do not already exist.

The protocol governs external coordination around the runtime.
It does not introduce a built-in multi-agent scheduler, a second source of truth, or a new authority above the canonical state.

## Canonical Role Set

Use only the canonical role names from `docs/operations/AGENT_ROLES.md` in new records and handoffs:

- Orchestrator
- Planner
- Implementer
- Reviewer
- Verifier
- Researcher
- Documenter

Legacy labels may appear in historical records, but they are not canonical for new operational work.

## Context Gate

On initialized work, start the round by opening continuity with `cerebro analyze` as the standard entrypoint.
After that continuity step, state whether the work is in `cerebro` or in a `caso`.
On uninitialized work, establish that context inside analysis before deeper bootstrap guidance.

1. Orchestrator asks: `estamos no cerebro ou em um caso?`
2. If the answer is ambiguous, the round becomes `blocked-context`.
3. If the answer is clear, Orchestrator records the context and continues the round formally.
4. No role may redefine canonical context after that opening.
5. No external tool may compete with `analyze` as the continuity entrypoint.

Hash-valid sources are not enough by themselves to clear this gate.
If the registered sources are semantically contradictory, materially stale against the declared goal, or too weak to answer the context gate safely, block the round inside analysis until one explicit human-arbitrated source position is recorded.

## Operational Axes

Use two different labels when describing work around Cerebro:

- runtime entry mode: `bootstrap` or `continuous work`
- external round intent label: `ENGINEERING`, `OPERATION`, `BREAKING`, or `CERTIFICATION`

Do not collapse those axes into one mode name.
Round intent labels classify why an external round exists; they do not create CLI modes, runtime enforcement, or a new authority above the canonical state.
Historical shorthand such as `audit / engineering` should be read as descriptive round context, not as a third runtime entry mode.

## Minimum Operational Flow

The canonical operating sequence is:

`READ -> ANALYZE -> PLAN -> DELEGATE -> ACT -> VERIFY -> RECORD`

Any deviation from this sequence is a protocol mismatch.
This sequence defines operational discipline for the round; it is not enforced by the CLI as a runtime gate.

### READ

Read the current checkpoint, validation posture, relevant runtime state, and any supporting derived surfaces needed for the round.
When deeper runtime context is required, read `status-export` and the audit trail explicitly.
If `status-export` shows event-backed decision provenance or selection replay diagnostics, use them as read-only evidence about the current decision surface, not as a replacement for canonical runtime state.
If registered sources disagree semantically, or if observability is degraded, treat that as unresolved evidence rather than as proof that the round is stable.
If `status-export` mixes current-plan diagnostics with accumulated runtime history, distinguish those time horizons explicitly in the round record instead of treating every reported counter as live-round pressure.

### ANALYZE

Separate evidence from hypothesis, classify the problem, identify blockers, and expose the decision trade-offs.

### PLAN

Build the next approved slice, define dependencies, set rollback and retry posture, and mark what is parallel-safe.

### DELEGATE

Assign only independent slices to canonical roles.
Delegation is explicit, not implicit.

### ACT

Execute only the approved slice and stay inside the approved surface.

### VERIFY

Check the result against the expected state, the approval boundary, and the verification target.
If the action is reversible and verification fails, prefer rollback over blind retry.
Rollback does not by itself certify closure: if verification failed before the rollback, the round remains blocked until verification passes again or another corrective path is chosen explicitly.
If a previously passed delta is later rolled back, treat that earlier passed verification as invalidated for the current workspace and rerun verification before claiming closure again.

### RECORD

Write the decision trail, the verification result, the remaining risk, and the next-step posture.
`status-export` and the audit trail are expected closure artifacts for external rounds as part of operational discipline, not CLI enforcement.

## Scope Definition

Before deeper analysis, the round must define scope explicitly:

- what will be analyzed now
- what is out of scope for now
- what should be analyzed later
- in what order the analysis should proceed

If the human materially changes the round goal or scope after planning has already begun, freeze the current slice and reopen analysis and plan before any further execution continues.

## Decision Discipline

The runtime does not advance on score alone.
Score helps select work, but evidence, approval, DAG validity, and verify decide whether work can move.

Every non-trivial decision record should make these points explicit:

- what evidence supports the task
- what the task score says
- what is blocked
- whether approval is required
- whether rollback exists
- what verify must prove
- what retry is allowed or blocked

When ambiguity, competing defensible paths, medium confidence, or false-consensus risk exists, the same decision record should also capture:

- the concrete problem being decided
- the primary hypothesis
- the alternative hypothesis
- the critique findings that challenged those paths
- the decision that survived review
- the verification result that will confirm or reject it

If the evidence is weak, stop.
If the DAG is invalid or cyclic, stop.
If the action is blocked by approval, stop until approval is explicit.
If the same action keeps failing without new evidence, retry is blocked.
If registered sources are hash-valid but semantically conflicting, materially stale, or too weak for the declared context and scope, stop until that source conflict is resolved explicitly.
If current observability is degraded enough that the round would be relying on missing events or partial event diagnostics as if they were clean evidence, stop until the round can proceed on stronger evidence.
If the current slice, plan, or supporting runtime surfaces would exceed the bounded runtime envelope or would depend on older runtime evidence that the core may trim away, stop and split or close the round before overflow.

## Debate And Stagnation Gate

Explicit debate is required when ambiguity, competing defensible paths, medium confidence, or false-consensus risk exists.
If only one defensible path remains, record that dominance explicitly and do not fabricate multi-agent work.

Treat the round as stagnating when one or more of these conditions hold:

- the same branch repeats blocked retry, apply, or verify without new evidence
- repeated iterations produce no new evidence, no approved-slice reduction, and no verified result
- parallel comparison is being proposed even though only one path is currently defensible

When stagnation is confirmed:

- stop the active branch
- return to `PLAN` and reduce the slice or reframe the question
- record the branch as blocked by stagnation or insufficient novelty
- require new evidence or a new persisted hypothesis before reopening the same branch

## Current Runtime Facts That Matter Operationally

The runtime currently derives operational weight per task:

- `light` / `state_only`
- `moderate` / `structured_state`
- `heavy` / `governed_execution`

Operational discipline must match that task profile:

- missing `working_set`, missing `acceptance_criteria`, and missing verification commands are hard diagnostics only for work that is structurally `heavy`
- lightweight and moderate state work must stay disciplined, but must not be forced through mechanics that add no operational value
- approvals are task-scoped; one approval record must not authorize the same payload in a different task
- a new `plan_updated` generation resets active approvals; prior approvals must not authorize the next plan implicitly
- legacy approvals without `task_id` are reusable only when the plan has exactly one executable task
- retry is action-scoped, not narrative-scoped
- blocked retry, apply, and verify history only counts inside the current plan generation
- verification without pending delta is blocked, including explicit reruns of commands already covered by the last passed verification
- `agent_runtime.memory.notes` is persisted heuristic support only; a note may remain schema-valid after project, goal, or source drift and must not override current evidence
- after a structural continuity break or out-of-band remediation, existing memory notes remain historical only until a fresh analyze-led round reaffirms that they still fit the current project, goal, and source set
- silence from external detectors is not positive evidence when detector coverage or detector health is unknown, absent, or degraded
- a new `plan_updated` generation resets the current-plan approval surface, verification surface, and current-plan `batch_registry`, but historical applied actions, rollback points, and older audit events remain historical evidence and must not be mistaken for clean closure of the new plan; those retained historical actions no longer need to appear in the new plan's `tasks[].action_ids`
- `analyze` and `resume` open `.cerebro/session.local.json` against one currently validated `state.revision`; under the current runtime, that local session is revision-bound rather than a durable round token
- owner-authenticated mutating commands now refresh that session binding in the same command path; `session_revision_invalid` therefore signals drift, stale artifacts, or external interference rather than routine same-owner progress
- `analyze` and `resume` do not silently overwrite an already-active local session; they fail with `session_open_conflict` until the current session is closed or discarded explicitly
- each opened local session now carries a unique `session_id` plus persisted `owner_claim_id`, and canonical state mirrors the one live pair in `agent_runtime.audit.active_session_id` plus `active_session_claim_id`; that still identifies only the live local continuity artifact rather than durable multi-user or same-actor reopen authority beyond it
- owner-authenticated commands now require the matching external session claim plus the matching external live proof plus an explicit caller-supplied `session_token` plus the same local holder context that opened the session; the claim stores only `session_token_sha256` plus `session_live_proof_sha256`, not the bearer token or the raw live proof itself
- the current runtime defaults both that external session claim and that external live proof to file-backed paths, including on Windows; this corrective fallback keeps continuity operational on hosts where the WinCred path fails with `CredWriteW failed: 8` for the two-credential session pair
- residual boundary: with that file-backed default, ownership proof still does not close same-user tamper or restore of the external proof files themselves; the current closure covers repo-local forgery, missing or mismatched external proof, and bounded discard/fail-closed recovery, but not strong same-user protection against restore of the external authority store
- copied authority replay from a different terminal or process holder context blocks with `session_owner_binding_mismatch`, repo-local session forgery without that claim blocks with `session_claim_missing` or `session_claim_mismatch`, missing caller-supplied capability blocks with `session_token_required`, missing or mismatched live proof blocks with `session_live_proof_missing` or `session_live_proof_mismatch`, and restored or stray session artifacts outside the canonical live-session registry block with `session_not_registered` or `session_registry_mismatch`
- after the seed round, `checkpoint` only closes continuity when the active session actor still matches the checkpoint caller, the caller still owns the matching external claim from that same holder context, and the validated `session_id` stays unchanged; a different holder blocks with `checkpoint_actor_mismatch`, `session_claim_missing`, `session_claim_mismatch`, or `session_owner_binding_mismatch`, and a mid-command session swap blocks with `session_changed_during_operation`
- the current CLI does expose one bounded in-band stale-session recovery step: `session-discard`; it clears the local session plus the canonical live-session registry only when validation is otherwise clean or only session-scoped invalid, still requires the matching external claim plus an explicit caller-supplied `session_token` plus holder context whenever the stale session artifact remains schema-valid enough to read and still has a readable live proof, reruns `validate`, refreshes the persisted canonical validation record, and records `session_discarded` as trace-only evidence
- `session-discard` is still not a continuity opener or continuity-preservation step; the first later analyze-led round that passes `validate` must record that continuity was broken and only then reopened
- `status-export` mixes current-plan diagnostics with some lifetime action counters; do not read every exported counter as pressure from the current round only
- `status-export` is a read-only Markdown export, not a stable machine API; any automation that parses it must treat section shape and time horizon as best-effort support only
- source arbitration, goal-reset decisions, project-identity anchors, and degraded-observability judgments are governance facts in the current protocol, but the runtime does not persist them as dedicated structured fields; they survive only in checkpoint text, the normal round record, and other explicit human-written records
- the canonical runtime state does not currently persist a protocol-contract version, a dedicated project-identity field, or detector-health / detector-coverage fields; when those anchors matter, they must be carried explicitly in the round record
- detector health and detector coverage are therefore `unknown` by default in protocol terms unless the current round record explicitly establishes them as positively known
- the current runtime envelope is bounded: up to 64 plan tasks, 32 command-registry commands, 64 retained applied actions, 256 retained current-plan batch labels, 32 verification checks, 64 retained memory notes, and 32 retained rollback points
- the runtime therefore does not guarantee unbounded round growth; large rounds must be sliced or closed before those ceilings are crossed
- retained approvals, applied actions, rollback points, and memory notes are last-N canonical surfaces rather than infinite runtime history; older entries may be trimmed away during long rounds
- the current runtime also keeps a bounded current-plan `batch_registry` of up to 256 non-empty labels already claimed by `apply`; that registry is operational authority, not audit evidence, and it resets on `plan_updated`
- each persisted `plan` also carries a unique current-plan generation marker, and retained actions stamp that origin generation in `details`; this keeps historical retained actions from binding the new plan's `tasks[].action_ids` or current-plan batch authority after `plan_updated`, even when task ids are reused
- when retained actions age out, the core prunes derived task and verification action-id references against the still-retained canonical action history instead of leaving orphan backlinks in canonical state
- audit `rollback_points` remain historical execution evidence only; they do not reopen rollback authority once an action is no longer retained and currently `applied`
- retained approval items are capped at 64; older approval records may trim away during approval-heavy rounds and stop being directly resolvable from canonical state
- canonical registered sources are capped at 32 entries, and source registration replaces the full declared set rather than merging an unlimited source list
- the current runtime starts new plans under an execution-policy default of `autonomy_level=A1`, protected paths `.cerebro/**` and `.git/**`, blocked command prefixes such as `git`, `rm`, and `rmdir`, and approval-required action kinds including `exec.command`, `fs.delete_soft`, `fs.move`, and `fs.write_patch`
- because of that policy surface, a slice may be schema-valid yet still be non-executable until the plan is reshaped or the policy assumptions are made explicit in the round record
- registered source files are reserved mutation targets in the current runtime; if a file must stop being context and start being a write target, rotate or narrow the declared source set explicitly before treating that mutation as in-protocol work
- the persisted validation record is also bounded: `last_validation.details` stores at most 32 detail items, so simultaneous failure fan-out can degrade the persisted validation surface into a truncated or overflow-style diagnostic instead of a complete root-cause list
- each task is capped at 16 `working_set` paths and 16 `acceptance_criteria`; if a faithful slice needs more than that, split it before persisting the task
- `checkpoint` remains a short bounded operational summary: `goal` up to 200 characters, `summary` up to 1000, `next_step` up to 300, and at most 8 `constraints` of up to 160 characters each
- task prioritization, blocked-retry pressure, and similar runtime selection signals are derived from bounded recent-event windows rather than a full lifetime replay of the audit log
- `trace_status` and `trace_integrity` are current recent-tail diagnostics only, not a whole-log proof that older trace history remained complete
- trace durability is environment-shaped in the current runtime: `balanced` is the default event-log posture, while `strict` fsyncs trace appends more aggressively; neither mode upgrades recent-tail diagnostics into a whole-log proof
- live contention on `.cerebro/runtime.lock` is not unbounded; the current core waits about five seconds before failing with a runtime-lock timeout if another owner still appears active
- `verify` runs only registered command ids that are explicitly eligible for verify and still allowed by the current execution policy
- the current runtime also accepts explicit verify subsets, but a subset run that does not execute the full `required_command_ids` set remains diagnostic only
- such a subset run does not clear pending-action coverage, does not mark plan progress closed, and does not advance the canonical verify gate out of an unresolved state
- `verify` now requires `allow_in_verify=true` plus `side_effect=read_only`, executes each selected command inside a disposable sandbox clone of the current project root, scrubs live session/env authority from the subprocess, keeps `runtime.lock` held while the commands execute, and fails closed when that sandbox shows observable in-root drift after command execution
- `verify` also restores and fails closed on persistent tamper of guarded live runtime authority files (`runtime.lock`, `state.json`, `events.jsonl`, `session.local.json`, the active external session claim, and the active live-proof backend entry itself, including Credential Manager-backed entries when that compatibility backend is used on Windows) instead of discovering that damage only after the command already escaped
- `apply` now rejects declared `side_effect=read_only` `exec.command` before execution and reserves read-only command execution for `verify`, because observable before/after drift proof was still bypassable by temporary absolute-path tampering restored before command exit
- that fail-closed rejection leaves no action artifact directory, no live workspace/runtime delta, and no new verify burden
- the residual verify boundary is still transient absolute-path tamper fully restored before command exit, arbitrary out-of-root side effects outside the guarded authority set, or perfectly concealed changes that leave no observable path/type/content/mtime drift
- command-gated verify artifacts are dual-channel in practice: stdout and stderr are both written, but the canonical verification check record names the stdout artifact only and leaves stderr as a sibling support file
- `validate` proves live refs for actions still applied and checks in the current verification run before the round is treated as executable; when persisted digest metadata exists for a rollback-critical action artifact or the current verification artifact, it also proves content integrity for that artifact; it does not certify arbitrary artifacts or historical audit-consumed artifacts or derived `status-export` / audit-trail outputs
- one `cerebro apply` invocation with multiple `--action-file` values currently supports filesystem action kinds only; it blocks the whole batch before mutation when a later item still needs approval or fails predictable preflight, restores the pre-batch workspace/runtime surface if a later execution or persist failure interrupts the batch, and commits the resulting action records in one revision only after the physical batch succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- the runtime now blocks reuse of a non-empty `batch_id` across separate `apply` invocations while that label remains in the retained current-plan `batch_registry`; after `plan_updated` resets that registry, batch-based `apply` and `rollback --batch-id` stay scoped to the new current-plan generation only, while explicit `rollback --action-id` may still target a retained historical applied action
- shared `batch_id` rollback is preflighted before the first mutation and fails closed if any selected reversible action no longer has a live reversible path; when a mid-execution failure or persistence failure interrupts rollback after some physical reversions, the runtime restores the pre-batch workspace/runtime surface and commits the resulting `rolled_back` states in one step after the physical rollback succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- rollback and verify fail closed on tampered or digest-mismatched rollback-critical and current verification artifacts instead of trusting content blindly
- the current runtime exposes one governed manual retention surface on `validate`: `cerebro validate --retention-report` is dry-run only, and `cerebro validate --retention-apply` archives only the currently eligible set after validation passes

## Success Memory And Limited Reinforcement

Use success memory as an explicit heuristic, not as hidden policy change.

- record successful decision shapes: evidence class, score range, approval shape, rollback posture, verify target, and task profile
- the runtime may apply limited score reinforcement when a current task matches an explicit verified success pattern
- recent blocked or failed attempts reduce that reinforcement immediately
- malformed success-memory notes are ignored rather than normalized into a false signal
- success memory supports tie-breaking and prioritization; it does not replace evidence, approval, or verification

## Parallel Delegation Rules

Parallel delegation is allowed only when all of the following are true:

- the slices are independent
- the slices do not write the same surface
- the approval scope covers every branch
- no branch depends on unresolved verification
- the join point for verification and record is explicit

Parallel delegation is a controlled optimization.
It is not a default replacement for planning.
Open parallel comparison only when at least two independent and defensible approaches exist and the comparison is operationally useful.
Do not open decorative branches just to satisfy a multi-agent ritual.

## Consolidation Protocol

When parallel agents compare approaches, consolidation happens at the join point and must be explicit.

The join point must compare:

- score
- evidence class
- reversibility
- rollback cost
- approval risk
- verify burden
- residual risk
- prior success memory, if relevant

The selected path must be the one that is most defensible under the current evidence, not merely the one that is most familiar.

The consolidation record must say:

- which approach won
- which approaches were actually compared
- which approaches were rejected
- why they were rejected
- whether success memory influenced the choice
- what would have to change before the losing path could return

The formal consolidation record lives in the append-only audit trail.
If the compared set is incomplete, if the winner is outside the compared set, or if the evidence references cannot be resolved, the consolidation is invalid.
Repeated consolidation for the same subject must explicitly supersede the current head for that subject.
Read-only consumers must treat replayed or stale valid consolidation records as non-current history, never as the active winner.

If the parallel comparison cannot produce a clear winner, the round should return to planning instead of fabricating consensus.

## Approval, Rollback, And Verify

The runtime uses approval, rollback, DAG validation, and verify as separate gates.

- approval decides whether the slice may run
- rollback defines the safe recovery path when the action is reversible
- DAG validation prevents invalid or cyclic planning
- verify confirms whether the result matches the intended state

If approval is missing, no action starts.
If rollback is not available for a risky branch, the branch should stay blocked until the risk is explicit.
If rollback later becomes non-executable because the workspace diverged, required artifacts are missing, or the reversible path no longer matches the applied delta, treat the branch as blocked and choose a new corrective path explicitly instead of assuming the original rollback posture still exists.
Even with batch preflight plus pre-batch restore on observed rollback failure, arbitrary external writers during execution can still defeat any practical atomicity guarantee; treat that path as blocked instead of assuming the shared batch is transactionally isolated.
If only an explicit subset of verify commands ran, treat that run as diagnostic support only; do not treat it as proof that the full required verification gate was satisfied unless the whole required set was intentionally covered.
If the branch depends on historical audit-consumed artifacts or derived diagnostic exports that are no longer available, treat recovery and diagnosis as blocked even if `validate` still returns `OK`.
If verify fails, the round returns to the relevant corrective step instead of pretending success.

## Stop Rules

Stop the round immediately when any of these conditions hold:

- the context is ambiguous
- only blocked items remain
- the evidence is still hypothesis-only
- approval has not been granted for a required slice
- the DAG is invalid
- verification failed and the recovery path is not clear
- the round is stagnating and no new evidence or narrower slice has been introduced
- the record cannot be written cleanly
- registered sources are hash-valid but semantically conflicting, materially stale, or too weak to support the declared context and scope
- the round goal or scope changed materially after the current slice, approval assumptions, or verification target were formed
- event-derived confidence is required, but observability is degraded or unavailable enough that missing events would be misread as proof of stability
- a technically accepted mutation happened outside an analyze-led continuity round and has not yet been reconciled through a fresh continuity-opening step
- `validate` fails with `session_revision_invalid` or another continuity-structure error that prevents the next round step from reopening or closing safely
- `validate` fails in a way that truncates or overflows the persisted validation-detail surface, so the visible validation record no longer enumerates every material root cause cleanly
- the slice is structurally valid but still blocked by the current execution policy, registered-source reservation, or a live runtime-lock timeout
- the intended closure or recovery claim depends on a subset-verify run that did not execute the full `required_command_ids` gate
- the current recovery or diagnosis path depends on historical audit-consumed artifacts or derived diagnostic exports that are missing, untrusted, or no longer available
- the current state uses an unsupported schema version
- the current slice or round would exceed the bounded runtime envelope or would require older trimmed runtime evidence as if it were still guaranteed present

If the runtime is too blocked to accept `checkpoint`, the round still needs an explicit blocked-round record outside canonical state.
That external blocked-round record is procedural guidance only until the next successful analyze-led round reconciles it back into the normal runtime flow.
The current CLI exposes no import command that rehydrates that blocked-round record into canonical state automatically.
That blocked-round record uses the same minimum record shape required for closure, but written outside canonical state.
Its reconciliation is manual restatement in the first later analyze-led round that succeeds again; it is not import, replay, or automatic hydration.
When multiple external records could plausibly exist, the reopened round must cite the explicit external record identifier, location, or timestamp it is reconciling instead of assuming the linkage implicitly.

Stop delegation immediately when:

- a branch shares mutable surface with another active branch
- the branch depends on unresolved verification
- the branch would exceed the approved slice

## Round States

- `awaiting-human-approval`

## Ownership And Collision Rules

- one active editor per file at a time

## Handoff Format

Every delegation, handoff, or review record must identify the agent as:

- `Papel funcional: <role>`

Tool nicknames, UI aliases, and historical labels are non-canonical.

## Record Requirements

Every closure record must include:

- the context gate result
- the task score or scores that mattered
- the evidence class used in the decision
- the plan and dependency shape
- the delegation choice
- the approval state
- the verification result
- the rollback decision, if any
- the retry posture
- the residual risk
- the next step
- any success-memory note that influenced the choice
- any explicit source arbitration, goal reset, or observability degradation that invalidated an earlier slice
- the explicit project anchor used for the round when similar roots, clones, mirrors, or bridge targets could be confused
- any continuity break such as `session_revision_invalid`, out-of-protocol mutation, or other structural runtime block that prevented normal closure
- the protocol-contract anchor used for the round when docs-only semantic changes could alter how later operators interpret the checkpoint or handoff
- whether any `status-export` evidence used current-plan diagnostics, accumulated history, or both
- when reconciling an external blocked-round record, the explicit external record identifier, path, or timestamp that was reconciled
- the consolidation rationale when multiple approaches were compared

Without that record, closure is incomplete.
If the runtime is blocked and cannot accept `checkpoint`, write the same minimum record in the external round handoff and reconcile it in the first later round that successfully reopens continuity.
The canonical `checkpoint` only carries the short state-safe subset of that record.
When the full closure or blocked-round explanation does not fit inside checkpoint budget, keep the checkpoint concise and carry the fuller explanation in the round record or external blocked-round record explicitly.

Record defaults in the current runtime:

- `project anchor` means the explicit procedural identifier of the workspace root used for the round; when similar roots, clones, mirrors, or bridge targets could be confused, the record must include the written disambiguation used by the operator
- `protocol-contract anchor` means the explicit procedural reference to the canonical docs set that governed the round and to the human-visible identifier used to locate that set at that time
- if either anchor is omitted where ambiguity was plausible, later rounds must treat project identity or contract identity as ambiguous instead of assuming continuity
