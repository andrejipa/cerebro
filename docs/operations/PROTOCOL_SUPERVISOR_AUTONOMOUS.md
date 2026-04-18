# Protocol: Supervisor vs Autonomous

This document formalizes the current external operating protocol for running Cerebro in external projects.
It is descriptive, not aspirational.
It does not create a new runtime authority, a new CLI mode, a new persisted state field, or a second source of truth.

`supervisor` and `autonomous` are external operating postures around the existing runtime.
They do not replace the current canonical runtime entry modes `bootstrap` and `continuous work`.
They do not replace `analyze` as the continuity entrypoint.

## Overview

This protocol defines:

- how Cerebro enters an external project
- how it asks for authorization
- how it distinguishes assisted control from limited autonomous operation
- how it uses the current CLI, approval gates, event log, `_local/automation_bridge`, and any strictly read-only external detectors that already exist
- how it pauses, resumes, and returns control without inventing new authority

This protocol applies to external projects operated with Cerebro.
It does not redefine how the Cerebro product repository itself is engineered.
It does not replace the canonical bootstrap flow for projects that are not initialized yet.
It is external operational discipline over the current runtime surface; it must not be read as uniform CLI enforcement of every posture boundary described here.

## Problem

The current system already has the main execution surfaces:

- canonical runtime state in `.cerebro/state.json`
- canonical continuity entry through `cerebro analyze`
- task planning, approval, apply, verify, rollback, and checkpoint commands
- approval gates and `autonomy_level`
- append-only runtime events in `.cerebro/logs/events.jsonl`
- local external helpers in `_local/autorun` and `_local/automation_bridge`

What is missing is one explicit protocol that says:

- when Cerebro is only observing
- when it is only proposing
- when it may coordinate work after human authorization
- when it may react automatically to real events
- when it must stop and return control

Without that protocol, three ambiguities remain:

- entry ambiguity: how Cerebro enters a project that is not yet initialized
- authority ambiguity: what `autonomous` can actually do without bypassing approval gates
- trigger ambiguity: how external monitors and bridges may react without becoming a second source of truth

## Objectives

This protocol resolves:

- explicit entry into initialized and uninitialized external projects
- explicit human handoff into assisted control
- explicit promotion from assisted control to limited autonomous operation
- explicit action limits by permission class
- explicit reaction to real events without automatic destructive execution
- explicit pause and return-to-human behavior

This protocol does not resolve:

- new canonical persistence
- new runtime schema fields
- automatic write-capable execution
- automatic bootstrap execution
- automatic `import-context`, `checkpoint`, `validate`, or `analyze`
- permanent daemon authority inside the runtime
- any authority for bridge logs, autorun summaries, or other external artifacts

This protocol guarantees:

- canonical authority remains in the existing runtime state
- every mutation still uses the current CLI and policy gates
- no write action proceeds without the current approval model
- autonomous operation remains limited to safe external observation and proposal
- human supervision remains part of the system
- external posture validity may depend on operator discipline where the current runtime does not persist or enforce the posture directly

## Modes

The protocol uses six external operating modes.
These are operational postures only.
They are not new runtime schema values and they do not alter CLI semantics.

Every round establishes context and scope explicitly.
On an initialized project, open continuity first through `cerebro analyze` as the standard entrypoint for the round, or through `cerebro resume` only when a compatibility workflow explicitly needs that session-opening step; then state whether the work is in `cerebro` or in a `caso`.
On an uninitialized project, establish that context inside `Analysis` before deeper bootstrap guidance.
If that context is ambiguous, block the round before deeper analysis, planning, or execution.
Define scope at that same opening: what is in focus now, what is out of scope for now, what can wait, and in what order analysis should proceed.
If the registered sources are hash-valid but too sparse, materially stale, or semantically contradictory to keep that context and scope clear, remain in `Analysis` or move to `Blocked`; do not advance on hash validity alone.
Strictly read-only detector support under an already authorized `Operational Control` posture is valid only when it stays inside the last explicitly declared context and scope of the current round.
If a detector cannot keep that same context and scope explicit, it may emit a non-canonical signal only.
It must not open or reopen protocol `Observation` on its own, and the next continuity-bearing round must return through `Analysis`.

### Analysis

Purpose:

- read the project
- determine whether `.cerebro/state.json` exists
- determine whether the project is already initialized
- establish the next correct entry step

Limits:

- no project mutation
- opening validated continuity through `analyze` or `resume` may update `.cerebro/session.local.json`
- under the current runtime, that local session is opened against one validated `state.revision`; it is not a durable multi-step round token once later commands advance `revision`
- no control assumption
- no `apply`, `approve`, `verify`, `rollback`, or `checkpoint`

### Observation

Purpose:

- watch for relevant events
- run read-only probes
- inspect tests, exports, and event-backed diagnostics

Limits:

- read-only only
- no `apply`, `approve`, `verify`, `rollback`, or `checkpoint`
- may use strictly read-only external detectors only as support inside a live current round
- within the Cerebro product repository, `_local/autorun` is one such detector

### Proposal

Purpose:

- summarize the current state
- recommend the next slice
- expose blockers, approvals, and risk

Limits:

- read-only only
- may package external context and prompt material
- does not assume control
- valid only after canonical bootstrap is complete

### Assisted Control

Purpose:

- coordinate the round after explicit human authorization
- build the next slice
- invoke the current CLI flow with explicit approvals

Limits:

- the human remains the supervisor
- mutations are allowed only through the current runtime commands
- risky or approval-governed actions still require explicit human approval

### Operational Control

Purpose:

- maintain continuous external observation under an already authorized control posture
- react to real events
- signal that a new proposal or human review is needed when evidence demands it

Limits:

- autonomous operation is read-only in the current system
- no automatic write-capable execution
- no automatic approval resolution
- no automatic proposal opening inside the runtime
- no automatic `rollback`
- no automatic `checkpoint`

### Pause

Purpose:

- stop active operation cleanly
- wait for new human input or new real evidence

Limits:

- no active control loop
- no standing autonomous observation owned by this protocol
- ad hoc manual read-only inspection may still occur, but it does not by itself reopen control or count as `Operational Control`
- no mutation

## Transitions

Allowed transitions:

- `Analysis -> Observation`
- `Analysis -> Proposal`
- `Observation -> Pause`
- `Proposal -> Analysis`
- `Proposal -> Assisted Control`
- `Assisted Control -> Operational Control`
- `Assisted Control -> Pause`
- `Operational Control -> Assisted Control`
- `Operational Control -> Pause`
- `Observation -> Proposal`
- `Proposal -> Pause`
- `Pause -> Analysis`
- `Blocked -> Analysis`
- `Blocked -> Proposal` for remediation planning after non-context block reasons
- `Blocked -> Pause`
- any mode -> `Blocked`

`Blocked` is not a normal operating mode.
It is the fail-safe posture entered when the current round cannot proceed safely.

The protocol enters `Blocked` when:

- `validate` fails
- `analyze` fails
- the context gate is ambiguous (`blocked-context`)
- the registered sources are hash-valid but semantically conflicting, materially stale, or too weak to support the current declared context and scope
- required approval is rejected
- verification is failed and the corrective path is not yet chosen
- evidence is insufficient after the round has already entered normal continuity
- the current state uses an unsupported schema version

Transition rules:

- a project with no `.cerebro/state.json` may enter `Analysis` only
- canonical bootstrap remains a precondition for `Assisted Control` and `Operational Control`
- a project with valid runtime state should enter through `cerebro analyze`
- `Analysis -> Observation` is allowed only for same-round read-only evidence gathering after continuity has already been opened; it is not an alternative entrypoint for initialized project rounds
- `Observation` and `Proposal` are sibling pre-authorization stages of the same round: `Observation` gathers additional read-only evidence, while `Proposal` forms the recommendation once that evidence is sufficient
- detector-driven or operator-driven `Proposal` on an initialized project may return directly to `Analysis` when continuity still needs to be opened for the round
- `Proposal -> Assisted Control` requires explicit human authorization and an already opened continuity session for the round as operator discipline, normally from `cerebro analyze`; if continuity is not yet open, return to `Analysis` first
- `cerebro resume` may satisfy the same validated session-opening step only as a compatibility flow; it does not create handoff authority on its own
- any fresh `analyze` or `resume` invocation resets the round to the same pre-recommendation read-only stage in protocol terms: `Observation` when deeper read-only evidence is still needed, otherwise `Proposal`, until authorization is made explicit again
- a material goal or scope change after the current slice has already been shaped invalidates the current slice assumptions; return to `Analysis` or `Proposal` before further mutation and do not continue under the prior approval context
- `session_revision_invalid` is a structural runtime block: if a successful earlier command already advanced `state.revision`, do not treat the next failure as a soft retry; stop and handle it as blocked continuity
- `Assisted Control -> Operational Control` requires a second explicit human authorization
- `Operational Control` may fall back to `Assisted Control` or `Blocked` immediately when evidence weakens
- detector activity never reopens a new continuity-bearing round after `Pause`, `checkpoint`, restart, or any fresh `analyze` or `resume`; after any of those boundaries, detector output is signal-only until `Analysis` reopens the round
- pending approval stops the affected slice inside `Assisted Control`; it does not force the whole round into `Blocked` on its own
- `Blocked -> Analysis` is a live recovery path only after the condition that caused `Blocked` has been remediated enough for `validate` and the chosen continuity command to succeed again
- `blocked-context` does not exit directly to `Proposal`; clarify context first and re-enter through `Analysis`
- degraded observability blocks event-derived confidence for autonomous continuation; absence of external events alone never proves that the project is stable
- if a mutating command technically succeeds without first opening continuity for the round, freeze further mutation, record the mismatch, and re-enter through `Analysis` before treating the round as continuous again
- `Blocked` permits diagnostic reading only; returning from `Blocked` requires a fresh human decision about the next safe step

Prohibited transitions:

- `Analysis -> Operational Control`
- `Observation -> Assisted Control` without explicit handoff
- `Observation -> apply`
- `Proposal -> apply`
- `Operational Control -> automatic write-capable execution`
- any mode -> authority over `.cerebro/` outside the current runtime commands

## Permissions

The protocol uses four action classes.

### Read

Examples:

- `status-export`
- `sources-export`
- reading tests and logs
- bridge prompt packaging
- event inspection

Rule:

- allowed in every mode
- in `Blocked`, read access is diagnostic only and must not be used to continue execution implicitly
- `analyze` and `resume` are continuity-opening entry commands, not plain `Read` actions in this matrix; they validate state and open the local session surface used for continuity

### Organize

Examples:

- bridge run packets
- external summaries
- `status-export --out ...`
- disposable run logs

Rule:

- allowed in `Observation`, `Proposal`, `Assisted Control`, and `Operational Control`
- must stay outside `.cerebro/`
- must not overwrite registered source files

### Modify

Examples:

- `plan`
- `apply`
- `approve`
- `verify`
- `rollback`
- `checkpoint`

Rule:

- allowed only in `Assisted Control`
- may be prepared during `Operational Control`, but not executed automatically
- canonical bootstrap commands for an uninitialized project remain outside this supervisor/autonomous handoff and must complete before `Assisted Control` exists
- must follow current runtime gates, approval rules, and validation posture
- if a mutating command is executed without an already opened continuity session for the round, the command result must not be treated as valid supervised continuity even if the runtime accepted it

### Destructive

Examples:

- rollback of meaningful applied actions
- sensitive filesystem deletion or move
- command execution with destructive side effects

Rule:

- never automatic
- requires explicit human approval and an available rollback path when reversible
- must still use the current runtime commands and policy gates

## Handoff

The handoff protocol is explicit.

### Entry into an external project

If the project is not initialized:

1. stay in `Analysis`
2. optionally use assistive discovery such as `bootstrap-scan`
3. recommend the canonical bootstrap sequence `init -> import-context -> checkpoint -> validate`
4. do not enter `Assisted Control` or `Operational Control` yet
5. after bootstrap completes successfully, start a new round with `cerebro analyze`
6. move to `Proposal` only after that successful `analyze`

If the explicit bootstrap source set is too sparse, stale, or contradictory to keep context and next-step intent clear, remain in `Analysis` and tighten the source set before treating bootstrap as operationally sufficient.

Pre-bootstrap recommendations remain part of `Analysis`.
They do not create a separate `Proposal` mode before canonical bootstrap exists.

If the project is initialized:

1. run `cerebro analyze` as the standard continuity entrypoint
2. `cerebro resume` may still be used only as a compatibility session-opening command over the same validated state
3. if the chosen continuity command fails, move to `Blocked`
4. if it succeeds and the round still needs deeper read-only evidence before recommendation, move to `Observation`
5. otherwise move to `Proposal`
6. do not treat a successful `resume` as restored assisted or operational control

### Assisted-control authorization

After a successful continuity-opening step on an initialized project, Cerebro remains in the round's pre-authorization stage first:

- `Observation` while deeper read-only evidence is still needed
- `Proposal` once the recommendation is ready

Cerebro asks for `Assisted Control` only when the round has reached `Proposal`.
That same rule applies whether continuity was opened through the standard `cerebro analyze` path or through the compatibility `cerebro resume` path over the same validated state.

At that point, Cerebro asks:

`Você quer que o Cérebro assuma o controle assistido deste projeto?`

If the answer is yes, Cerebro states:

`O Cérebro assumiu a coordenação do projeto. Vou organizar o contexto, orientar decisões e executar com disciplina. Vou pedir aprovação quando necessário.`

That begins `Assisted Control`.

### Operational-control authorization

Promotion to `Operational Control` is separate.
It requires explicit human authorization after assisted operation has already been established.

Promotion means:

- automatic observation may continue only as non-canonical read-only support inside the already declared context and scope of the current authorized round, before `checkpoint` and before any fresh `analyze` or `resume`, and only when a strictly read-only external detector is actually available
- automatic signaling that a new proposal may be needed may continue only as non-canonical external output
- write-capable execution still remains approval-bound and human-gated

### Auditability

This handoff does not create a new state field.
`.cerebro/session.local.json` is singular local continuity control for the current project root.
It is tied to the validated `state.revision` that opened it, and owner-authenticated mutating commands now refresh that binding in-band instead of letting routine same-owner progress stale the session immediately.
`Assisted Control` and `Operational Control` are session-local external postures.
They are not recovered automatically after process restart, monitor restart, or bridge restart.
After a restart, re-enter from the current canonical state through `Analysis` using `cerebro analyze` as standard, or through `cerebro resume` only when a compatibility workflow explicitly needs the same validated session-open step.
Either continuity command returns the round to the same pre-authorization stage of that round: `Observation` when deeper read-only evidence is still needed, otherwise `Proposal`; neither command recreates assisted or operational control by itself.
Ask for explicit authorization again before resuming any control posture beyond read-only observation.
Because the local session file is singular, `analyze` or `resume` now fail closed with `session_open_conflict` when another active session is already present.
The session file still does not record whether it was opened by `analyze` or `resume`, but it now carries a unique `session_id` plus persisted `owner_claim_id` for the live local continuity artifact, and canonical state mirrors that one live pair in `agent_runtime.audit.active_session_id` plus `active_session_claim_id`.
Replacing that session therefore requires explicit closure or `session-discard`; it is no longer a silent overwrite path.
This is an exclusivity-enforcing continuity surface for one active local session, not a last-writer-wins ownership surface.
After the seed round, `checkpoint` also stops treating any active session as sufficient: actor mismatch blocks with `checkpoint_actor_mismatch`, a missing or mismatched external claim blocks with `session_claim_missing` or `session_claim_mismatch`, a missing caller-supplied capability blocks with `session_token_required`, a different holder context blocks with `session_owner_binding_mismatch`, and a mid-command session swap blocks with `session_changed_during_operation`.
Owner-authenticated commands now require the matching external session claim plus the matching external live proof plus an explicit caller-supplied `session_token` plus the same local holder context that opened the session. That claim stores only `session_token_sha256` plus `session_live_proof_sha256`, never the bearer token or the raw live proof itself, so copied authority replay from another terminal or process holder context no longer succeeds, repo-local forgeries of `session.local.json` no longer suffice, and coherent restore of `state.json` plus `session.local.json` plus copied claim/proof files without the live backends now fails closed with `session_claim_missing`, `session_claim_mismatch`, `session_live_proof_missing`, or `session_live_proof_mismatch`.
The current runtime defaults both that external session claim and that external live proof to file-backed paths, including on Windows; this corrective fallback keeps continuity operational on hosts where the WinCred path fails with `CredWriteW failed: 8` for the two-credential session pair.
Residual boundary: with that file-backed default, ownership proof still does not close same-user tamper or restore of the external proof files themselves. The current closure covers repo-local forgery, missing or mismatched external proof, and bounded discard/fail-closed recovery, but not strong same-user protection against restore of the external authority store.
The protocol still does not attempt to prove durable multi-user ownership from session contents alone, especially across same-actor or same-machine reopen scenarios.
Control-posture ownership remains a human procedural fact layered over that singular runtime session.
Only the latest explicit human authorization keeps a control posture valid in protocol terms, and write-capable coordination must not continue when that authorization cannot be reasserted clearly in the current round.
Concurrent assisted controllers are therefore out of protocol for one project root under the current runtime.
Because that ownership is procedural, detector-driven observation is valid only as support inside a still-live authorized round; it never proves that authorization and it must degrade to signal-only output as soon as that round is closed, restarted, overwritten, or no longer clearly attributable to the latest explicit handoff.
If the round needs explicit continuity for the human operator, the active posture may be reflected in existing canonical checkpoint text and in normal round records, but that text does not recreate machine-readable authority on its own.
External bridge or autorun artifacts remain non-canonical support evidence only.
The same applies to governance decisions such as source arbitration, goal reset, degraded observability, detector coverage, project identity, or protocol-contract anchoring: under the current runtime they remain explicit procedural records, not structured runtime fields.
In the current runtime, `detector health` and `detector coverage` are `unknown` by default unless the round record explicitly establishes them as positively known.
Likewise, `project identity` and `protocol-contract identity` remain ambiguous by default when similar roots or docs-only semantic shifts are plausible and the round record does not name the procedural anchor used for each.

## Loop

Round entry happens before the assisted loop begins.
Open continuity with `cerebro analyze` as the standard entrypoint, or use `cerebro resume` only as a compatibility session-opening step over the same validated state.
After that continuity step, the round returns to the pre-recommendation read-only stage of the same round: `Observation` when deeper read-only evidence is still needed, otherwise `Proposal`.
Explicit assisted handoff must be reestablished before write-capable coordination resumes.
Under the current runtime, that opened continuity is still revision-bound, but owner-authenticated mutating commands now refresh the binding in the same command path instead of staling the session as normal progress.
When a later command still fails with `session_revision_invalid`, the round is structurally blocked by drift, stale artifacts, or external interference rather than by ordinary same-owner progress. `cerebro session-discard` may clear that block only when validation is otherwise clean or only session-scoped invalid, it also clears the canonical live-session registry, and it still requires the matching external claim plus an explicit caller-supplied `session_token` plus holder context whenever the stale session artifact remains schema-valid enough to read and still has a readable live proof; if the only remaining session defect is missing or mismatched live proof, discard may clear the stranded artifacts without bearer proof because the runtime can no longer prove an active session; it does not preserve continuity, so the next analyze-led round must still record the break explicitly before treating continuity as reopened.

Once explicit `Assisted Control` is active for the current round, the canonical external operating loop remains:

`READ -> ANALYZE -> PLAN -> DELEGATE -> ACT -> VERIFY -> RECORD`

This is the same canonical round flow described in `AGENT_PROTOCOL` and `OPERATIONS_BASELINE`.
`supervisor` and `autonomous` change posture around the round; they do not replace that sequence.

### Read

- start from the current validated continuity already opened for the round
- read `status-export` and the audit trail when deeper runtime evidence is needed
- inspect tests and other read-only probes
- if a new round has not opened continuity yet, return to `Analysis` first instead of mutating from `Proposal`

### Analyze

- classify the problem as `comprovado`, `provavel`, or `hipotese`
- separate evidence from hypothesis
- stop if evidence is insufficient

### Plan

- choose the smallest defensible slice
- use `plan` to persist the current slice
- a successful `plan` may advance `state.revision`; under the current runtime that can stale the earlier session for the next validating command
- check approval state
- determine whether the slice is approval-bound under policy
- treat an approval-bound slice as blocked until approval is explicit
- if the runtime has not yet created a pending approval record for the current action, a single `apply` attempt may be used only to request approval; if it returns `approval_required`, treat that result as gate materialization, not as `Act`
- once a pending approval exists for the current slice, resolve it with `approve`
- do not rerun `plan` for the same slice after a pending approval exists unless you intend to open a new plan generation and invalidate that approval context
- check retry posture
- check verify target

### Delegate

- delegate only independent external slices when delegation is operationally useful
- if no safe independent split exists, keep the round single-threaded

### Act

- use `apply` only inside the approved slice
- for an approval-bound action, `Act` begins only after approval is explicit
- if an earlier `apply` attempt only created the pending approval record and returned without mutation, treat it as part of the approval gate rather than as started execution
- after approval is granted, rerun the same `apply` step for the approved slice
- never bypass approval by external tooling
- a successful mutation may also advance `state.revision`; if the next validating command then fails with `session_revision_invalid`, treat that as blocked continuity rather than as a normal post-apply verify step
- some mutating commands validate state but do not uniformly enforce an already-open continuity session; under this protocol, executing them without first opening continuity is out of protocol even if the command technically succeeds

### Verify

- use `verify` for pending runtime deltas
- read `status-export` with its time horizon explicit: some diagnostics are current-plan, while some counters reflect longer-lived runtime history
- use tests and read-only exports as supporting evidence
- prefer `rollback` over blind retry when verification fails and the action is reversible
- rollback after a failed verification does not by itself clear the blocking state; rerun `verify` successfully or choose another corrective path explicitly before resuming mutation
- if a previously passed delta is later rolled back, treat that earlier verification as invalidated for the current workspace and rerun `verify` before claiming closure again

### Record

- use `checkpoint` to close the round
- preserve residual risk and the next step in the checkpoint text
- treat `status-export` and the audit trail as expected closure artifacts
- after the seed checkpoint, `checkpoint` is the runtime command that proves the round still had an active local session at closure time

### Pause or Continue

- if no further approved slice exists, move to `Pause`
- after `checkpoint`, any later continuity-bearing round re-enters through `Analysis` with `cerebro analyze` as the standard path
- after `Pause` or `checkpoint`, a strictly read-only detector may emit a non-canonical signal only; it does not reopen protocol `Observation`, and any later continuity-bearing round must return through `Analysis` before assisted control resumes

## Integration With The Current System

### Canonical state

- `.cerebro/state.json` remains the only persisted source of runtime truth
- `agent_runtime.memory.notes` remains the only persisted runtime memory surface already supported by the state
- `.cerebro/session.local.json` remains local continuity control only
- `.cerebro/logs/events.jsonl` remains an operational artifact, not canonical truth
- `agent_runtime.memory.notes` is heuristic historical support only; it does not arbitrate conflicting sources, goal drift, cross-project identity, or degraded observability on its own
- source arbitration, goal-reset decisions, degraded-observability judgments, detector-coverage judgments, and project-identity anchors are not persisted today as dedicated runtime fields; they remain explicit procedural records in checkpoint text and normal round records until the runtime models them more directly

### CLI

This protocol depends on the current commands exactly as they exist:

- `analyze` opens validated continuity
- `resume` remains a compatibility continuity command over the same validated state and opens a local session, but it does not authorize a control posture by itself
- a successful `resume` must still be interpreted as the same pre-authorization stage for the round (`Observation` when deeper read-only evidence is still needed, otherwise `Proposal`) until explicit handoff is reestablished
- `analyze` and `resume` open `.cerebro/session.local.json` against the currently validated `state.revision`; under the current runtime that session is revision-bound rather than a durable multi-command round token
- `plan` defines the next slice and policy surface
- `apply` executes typed actions and raises approval when required
- `approve` resolves one pending approval
- `verify` validates pending action deltas
- `rollback` reverts reversible applied work
- `checkpoint` records closure and closes the round
- after the seed checkpoint, `checkpoint` is the command that blocks when no active local session exists for the round
- `plan`, `apply`, `approve`, `verify`, and `rollback` all validate state, but they do not by themselves prove that the round opened continuity through `analyze` or `resume`
- when one successful command advances `state.revision` without also refreshing or closing the session, the next validating command may fail with `session_revision_invalid`
- `session-discard` is the bounded in-band command path for that stale-session condition: it can clear only the local session, rerun `validate`, refresh the persisted canonical validation record, and record `session_discarded` as trace-only evidence without preserving governed continuity; it still requires the matching external claim plus holder context while the stale artifact remains schema-valid enough to read and still has a readable live proof
- `session-discard` still does not reopen continuity by itself; the next later analyze-led round that passes `validate` must record the continuity break explicitly before treating the round as reopened
- because of that boundary, supervised continuity remains an operator-verified protocol condition until closure is recorded through the normal runtime flow
- if one of those commands technically succeeds outside analyze-led continuity, treat the result as an out-of-protocol mutation that must be reconciled in the next analyze-led round before further governed execution continues
- `plan_updated` resets the current-plan approval surface, verification surface, and current-plan `batch_registry` for the new slice, but it does not erase historical applied actions, rollback points, or earlier audit events; those remain historical evidence and residual-risk context until an analyze-led round or explicit recovery step resolves them, and they no longer need to appear in the new plan's `tasks[].action_ids`
- once `plan_updated` clears `verification.pending_action_ids`, `status-export` no longer surfaces those earlier deltas as current-plan pending verification; interpret the historical action log and rollback surface separately from the new plan's clean verification surface
- `status-export` is a read-only Markdown surface, not a machine-stable runtime API; any monitor or automation that parses it is consuming best-effort presentation rather than canonical structured state
- the canonical runtime state does not persist a dedicated protocol-contract version, detector-health field, detector-coverage field, or project-identity field; those anchors remain procedural unless and until the runtime models them directly
- `agent_runtime.memory.notes` may survive a continuity break structurally, but after structural invalidity or out-of-band remediation they must be treated as historical support only until a fresh analyze-led round reaffirms their fit
- the current runtime envelope is bounded: up to 64 plan tasks, 32 command-registry commands, 64 retained applied actions, 256 retained current-plan batch labels, 32 verification checks, 64 retained memory notes, and 32 retained rollback points
- long or noisy rounds must therefore be split or closed before those ceilings are crossed; the runtime does not guarantee unbounded accumulation inside one continuity window
- retained approvals, applied actions, rollback points, and memory notes are last-N canonical surfaces rather than infinite runtime history; older entries may be trimmed away during long rounds
- the current runtime also keeps a bounded current-plan `batch_registry` of up to 256 non-empty labels already claimed by `apply`; that registry is operational authority, not audit evidence, and it resets on `plan_updated`
- each persisted `plan` also carries a unique current-plan generation marker, and retained actions stamp that origin generation in `details`; this keeps historical retained actions from binding the new plan's `tasks[].action_ids` or current-plan batch authority after `plan_updated`, even when task ids are reused
- when retained actions age out, the core prunes derived task and verification action-id references against the still-retained canonical action history instead of leaving orphan backlinks in canonical state
- audit `rollback_points` remain historical execution evidence only; they do not reopen rollback authority once an action is no longer retained and currently `applied`
- retained approval items are capped at 64; older approval records may trim away during approval-heavy rounds and stop being directly resolvable from canonical state
- canonical registered sources are capped at 32 entries, and re-registering sources replaces the full declared set rather than merging indefinitely
- the default execution-policy surface for a fresh runtime block includes `autonomy_level=A1`, protected paths `.cerebro/**` and `.git/**`, blocked command prefixes such as `git`, `rm`, and `rmdir`, and approval-required action kinds including `exec.command`, `fs.delete_soft`, `fs.move`, and `fs.write_patch`
- because of that policy surface, a slice may be structurally valid yet still be non-executable until the operator reshapes the plan or policy posture explicitly
- registered source files are reserved mutation targets in the current runtime; if one of them must become a write target, rotate or narrow the canonical source set explicitly before treating that mutation as in-protocol work
- the persisted validation record is bounded: `last_validation.details` stores at most 32 items, so severe simultaneous failure fan-out can collapse the visible validation surface into truncated or overflow-style diagnostics
- each task is capped at 16 `working_set` paths and 16 `acceptance_criteria`; if a faithful slice needs more than that, split it before persisting the task
- `checkpoint` remains a short bounded operational summary: `goal` up to 200 characters, `summary` up to 1000, `next_step` up to 300, and at most 8 `constraints` of up to 160 characters each
- task choice, retry pressure, and related runtime prioritization consume bounded recent-event windows rather than whole-log replay
- `trace_status` and `trace_integrity` are derived from a recent event tail and must not be read as a whole-log completeness proof
- trace durability is environment-shaped in the current runtime: `balanced` is the default trace-log posture, while `strict` fsyncs trace appends more aggressively; neither mode upgrades recent-tail diagnostics into whole-log proof
- live contention on `.cerebro/runtime.lock` is bounded too: the current core waits about five seconds before failing with a runtime-lock timeout if another owner still appears active
- `verify` runs only registered command ids that are explicitly eligible for verify and still allowed by the current execution policy
- the current runtime also accepts explicit verify subsets, but a subset run that does not execute the full `required_command_ids` set remains diagnostic only
- such a subset run does not clear pending-action coverage, does not mark plan progress closed, and does not advance the canonical verify gate out of an unresolved state
- `verify` now requires `allow_in_verify=true` plus `side_effect=read_only`, executes each selected command inside a disposable sandbox clone of the current project root, scrubs live session/env authority from the subprocess, keeps `runtime.lock` held while the commands execute, and fails closed when that sandbox shows observable in-root drift after command execution
- `verify` also restores and fails closed on persistent tamper of guarded live runtime authority files (`runtime.lock`, `state.json`, `events.jsonl`, `session.local.json`, the active external session claim, and the active live-proof backend entry itself, including Credential Manager-backed entries when that compatibility backend is used on Windows) instead of discovering that damage only after the command already escaped
- `apply` now rejects declared `side_effect=read_only` `exec.command` before execution and reserves read-only command execution for `verify`, because observable before/after drift proof was still bypassable by temporary absolute-path tampering restored before command exit
- that fail-closed rejection leaves no action artifact directory, no live workspace/runtime delta, and no new verify burden
- the residual verify boundary is still transient absolute-path tamper fully restored before command exit, arbitrary out-of-root side effects outside the guarded authority set, or perfectly concealed changes that leave no observable path/type/content/mtime drift
- command-gated verify artifacts are dual-channel in practice: stdout and stderr are both written, but the canonical verification check record names the stdout artifact only and leaves stderr as sibling support
- `validate` proves live refs for actions still applied and checks in the current verification run before the round is treated as executable; when persisted digest metadata exists for a rollback-critical action artifact or the current verification artifact, it also proves content integrity for that artifact; it does not certify arbitrary artifacts or historical audit-consumed artifacts or derived `status-export` / audit-trail outputs
- one `cerebro apply` invocation with multiple `--action-file` values currently supports filesystem action kinds only; it blocks the whole batch before mutation when a later item still needs approval or fails predictable preflight, restores the pre-batch workspace/runtime surface if a later execution or persist failure interrupts the batch, and commits the resulting action records in one revision only after the physical batch succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- the runtime now blocks reuse of a non-empty `batch_id` across separate `apply` invocations while that label remains in the retained current-plan `batch_registry`; after `plan_updated` resets that registry, batch-based `apply` and `rollback --batch-id` stay scoped to the new current-plan generation only, while explicit `rollback --action-id` may still target a retained historical applied action
- shared `batch_id` rollback is preflighted before the first mutation and fails closed if any selected reversible action no longer has a live reversible path; when a mid-execution failure or persistence failure interrupts rollback after some physical reversions, the runtime restores the pre-batch workspace/runtime surface and commits the resulting `rolled_back` states in one step after the physical rollback succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- rollback and verify fail closed on tampered or digest-mismatched rollback-critical and current verification artifacts instead of trusting content blindly
- the current runtime exposes one governed manual retention surface on `validate`: `cerebro validate --retention-report` is dry-run only, and `cerebro validate --retention-apply` archives only the currently eligible set after validation passes

### Approval gates

- approval remains task-scoped
- approval records do not bleed across tasks or plan generations
- autonomous operation does not resolve approvals automatically

### `autonomy_level`

`autonomy_level` remains a task execution policy inside the runtime.
It does not define the external operating mode by itself.

Operational meaning in this protocol:

- it constrains what the current planned task can execute
- it does not authorize automatic write-capable control
- `A0` and `A1` remain non-command-execution levels

### `_local/autorun`

`_local/autorun` is a bundled external local detector and probe runner for the Cerebro product repository itself.
It is not a generic monitor for arbitrary external project roots in the current system.
In this protocol it may:

- detect relevant filesystem events in the Cerebro product repository
- run tests
- optionally run `status-export`
- raise a non-canonical signal that human review or a new proposal may be needed

It may not:

- alter `.cerebro/`
- call `plan`, `apply`, `approve`, `verify`, `rollback`, or `checkpoint` automatically
- become project memory

For arbitrary external projects, this protocol does not assume a bundled filesystem monitor exists.
On an initialized external project, the human operator opens any new continuity-bearing round through `cerebro analyze` as the standard entrypoint.
Another strictly read-only detector that does not claim authority over runtime state may supply support signals or in-round read-only evidence inside an already live authorized round, but it does not open protocol `Observation` on its own.
Proposal entry for those projects applies only after canonical bootstrap exists and should normally be reached from `Analysis` on the initialized project.
On a project that is not initialized yet, detector output is assistive input to `Analysis` only and does not open protocol `Observation` or `Proposal`.
Those detectors do not compete with `cerebro analyze` as the continuity entrypoint for initialized external rounds.
For arbitrary external projects, absence of detector output is not evidence that nothing changed; if detector coverage or detector health is not positively known, rely on explicit human-triggered reading and analysis instead of event silence.
That same caution applies when operational semantics changed only through canonical docs, handoff text, or other human-written protocol material: detector silence does not certify semantic stability.

### `_local/automation_bridge`

`_local/automation_bridge` is an external execution packager.
In this protocol it may:

- package explicit task text and explicit context paths
- run read-only external execution against a target `--project-root`
- capture disposable logs and structured final output
- rely on the human operator to bind that `--project-root` explicitly to the project actually under discussion

It may not:

- define canonical context
- prove that the supplied `--project-root` semantically matches the project the human intended to operate
- treat `.cerebro/` itself or any runtime-authority directory as a valid substitute for the intended workspace root in an external-project round
- register `sources`
- bypass `analyze`
- bypass approval gates
- turn bridge logs into project truth

The bridge helper does not technically enforce semantic target identity for `--project-root`; it only enforces basic filesystem validity.
If the operator cannot positively verify that `--project-root` names the intended workspace root, or if it names `.cerebro/` itself or another runtime-authority directory, the bridge run is out of protocol and its output must be discarded as operational evidence.
Even when `--project-root` is verified, bridge output remains support evidence only and cannot by itself advance the mode machine or recreate control authority.
Binding ambiguity is therefore a stop condition, not a hint for automatic correction: if the intended workspace root cannot be verified clearly from explicit human intent plus the current canonical project state, discard the bridge run and return through `Analysis`.

## Triggers

The protocol is event-driven only within safe external limits.

Valid activation triggers:

- explicit human request
- discovery during `Analysis` that the target project is not initialized yet
- successful or failed `analyze`
- failed `validate`
- failed tests
- explicit diagnostics from `status-export`
- pending approval
- failed verification
- meaningful filesystem change detected by an external read-only monitor that is actually attached to the target project

Ignored triggers:

- changes inside `_local/autorun/runs/`
- changes inside `_local/automation_bridge/runs/`
- external run summaries by themselves
- stale bridge output without new project evidence

Anti-loop rule:

- external detectors must treat their own artifacts as disposable noise
- repeated identical probe results without new project evidence must not open new rounds automatically

## Security

Safety rules are strict:

- no action without evidence
- no write-capable action without the current runtime gate model
- no automatic destructive action
- no automatic approval resolution
- no mutation outside `StateStore` and the current CLI
- no external artifact becomes canonical truth

Fail-safe behavior:

- if `analyze` or `validate` fails, stop mutation and move to `Blocked`
- if `validate` fails with `session_revision_invalid`, treat the round as structurally blocked continuity rather than as an ordinary retry
- if `verify` fails, stop further mutation until the corrective path is chosen
- if approval is pending, stop the affected slice
- do not escalate to `Blocked` on pending approval alone unless another failure condition is also present
- if registered sources are semantically conflicting, materially stale, or too weak for the current declared context and scope, stop and return to explicit source arbitration before planning or mutation
- if `status-export` reports degraded trace or unavailable runtime-event reads, treat event-derived diagnostics as partial only and do not use them alone to justify continued autonomous observation
- if `validate` fails in a way that truncates or overflows the persisted validation-detail surface, treat the visible validation report as incomplete and return to explicit manual diagnosis instead of assuming the shown error is the only material root cause
- if a slice is still blocked only because the current execution policy forbids the command, path, or mutation target, treat that as a real protocol stop and replan instead of describing the slice as executable
- if a passed verify result came from only an explicit subset of the required command set, do not treat that result as proof that the full verification gate was satisfied
- if rollback or diagnosis depends on historical audit-consumed artifacts or derived diagnostic exports that are missing, untrusted, or no longer available, treat the branch as blocked even if `validate` still reports `OK`
- if the bridge or monitor fails, fall back to manual observation, proposal, or assisted control as appropriate
- if the runtime is blocked and therefore cannot accept `checkpoint`, the recovery decision must still be written in the external round record, but that record remains procedural guidance only until a later analyze-led round reconciles it with canonical runtime state; the current CLI exposes no import path that performs that reconciliation automatically
- that external blocked-round record uses the same minimum closure-record content required for a normal round, but written outside canonical state
- later reconciliation is manual restatement in the first analyze-led round that succeeds again; it is not import, replay, or automatic hydration
- if multiple external blocked-round records could plausibly match, the reopened round must cite the exact external record identifier, location, or timestamp being reconciled
- if the current slice would exceed the bounded runtime envelope, stop and narrow or close the round before overflow rather than treating runtime truncation as benign
- if a live `runtime.lock` timeout occurs, treat that as bounded coordination contention under the current runtime rather than as proof that the earlier owner was semantically safe, stale, or finished

Recovery behavior:

- use `rollback` only through the current runtime command
- if `rollback` rejects because the workspace diverged or rollback artifacts no longer match the applied delta, treat the branch as blocked and choose a new corrective path explicitly instead of assuming reversibility still exists
- if a shared `batch_id` rollback fails and the runtime cannot preserve or restore the pre-batch workspace/runtime surface, treat the branch as blocked and choose the corrective path explicitly instead of assuming the batch rolled back atomically
- if one `cerebro apply` invocation with multiple `--action-file` values fails before commit, treat it as a blocked batch with no canonical partial apply unless the compensation restore itself failed and surfaced an explicit runtime error
- if `apply` rejects because a non-empty `batch_id` is already present in the retained current-plan `batch_registry`, treat the label as closed for new mutation and choose a fresh batch boundary instead of trying to extend the old one implicitly
- re-enter through `analyze` before treating a resumed round as continuity
- keep `Blocked` diagnostic: read to explain the failure, then return through an explicit next step instead of resuming mutation implicitly
- when `Blocked` comes from structural invalidity, stale hashes, or failed validation, `Proposal` may still be used for remediation planning, but `Analysis` is not a live exit until the underlying state has been repaired enough for `validate` to pass
- when `Blocked` comes from `session_revision_invalid`, do not describe the round as still smoothly open; use `session-discard` only to clear the local session when the block is session-scoped, then return through `analyze` before further governed mutation
- when `Blocked` comes from `source_hash_mismatch` or another stale-source condition, treat the current slice, approval assumptions, and success-memory fit as stale until a fresh analyze-led round re-reads the repaired canonical state
- when `Blocked` comes from execution-policy denial against a command, protected path, or registered-source mutation target, do not keep retrying the same slice; reshape the plan or context posture explicitly first
- when `Blocked` comes from an unsupported schema version, no new round may proceed until external remediation restores a supported state version
- when a mutating command succeeded outside analyze-led continuity, freeze further mutation, re-enter through `Analysis`, and record which parts of the resulting state still survive the reopened round
- when the blocked state prevented canonical closure, reconcile the external blocked-round record in the first later round that successfully reopens continuity, and do not treat that procedural record by itself as new runtime truth
- `.cerebro/runtime.lock` remains coordination only, but the core may remove a stale lock automatically when the prior owner appears inactive; treat that as low-level recovery of a transient coordination artifact, not as proof that the interrupted round was semantically safe or continuously understood

## Risks

Primary risks in this model:

- operators may confuse external posture with runtime authority
- a live local session may block a later `analyze` or `resume` with `session_open_conflict` until the current holder closes or discards it explicitly
- some mutating commands may still run on validated state without proving that continuity was opened for the current round
- revision-bound local continuity may stale after a successful state write and block the next governed command with `session_revision_invalid`
- bridge or autorun logs may be misread as project memory
- a read-only autonomous posture may be misread as permission for autonomous writes
- external detectors may open noisy or repetitive proposals if they do not filter their own artifacts
- a product-repo-local monitor may be mistaken for a general external-project detector
- bridge output may be attributed to the wrong project if the human binds `--project-root` incorrectly
- governance decisions that exist only in prose may be forgotten, misread, or mistaken for structured runtime state
- `status-export` may be misread if historical counters are treated as if they described only the current round
- monitor or automation consumers may misread `status-export` as a stable machine contract even though they are parsing derived Markdown
- the current runtime does not persist which protocol-contract version governed the round when semantics changed only in docs
- docs-only protocol changes may be missed by detectors that do not watch the canonical docs surface
- when those risks are material, the round record must name the procedural project anchor and protocol-contract anchor explicitly; without that, later rounds must treat project identity or contract identity as ambiguous

## Architectural Decision

The current system adopts a conservative model:

- `supervisor` is the default operating posture after handoff
- `autonomous` is limited to external read-only observation and signaling that a proposal may be needed
- all write-capable execution remains inside `Assisted Control`
- approval gates, rollback, verify, and checkpoint remain the same as they are today

This decision was chosen because it is the strongest model that:

- matches the current CLI and policy surface
- does not require schema change
- does not invent authority for external helpers
- stays safe under the current bridge and monitor limits

## Order Of Implementation

This section defines rollout order for external project operation using the current system.
It does not define a new engineering roadmap.

1. Determine whether the target project is initialized.
2. If not initialized, complete canonical bootstrap mode first: `init -> import-context -> checkpoint -> validate`.
3. After bootstrap, or immediately when already initialized, start the round with `cerebro analyze` as the standard continuity entrypoint.
4. Use `cerebro resume` only when a compatibility workflow explicitly needs that session-opening path; it does not skip proposal or authorization.
5. Operate in the round's pre-authorization stage until assisted-control authorization is explicit: `Observation` while deeper read-only evidence is still being gathered, otherwise `Proposal`.
6. Use `Assisted Control` for any write-capable round.
7. Use `_local/automation_bridge` only for read-only external execution packaging, and bind its `--project-root` explicitly before treating its output as relevant support evidence.
8. Treat bundled `_local/autorun` as a product-repo-local detector only; do not assume it monitors arbitrary external projects.
9. Promote to `Operational Control` only for ongoing automatic observation and signaling that a proposal may be needed.
10. Return to `Pause` after the round is recorded through the normal runtime flow.

Never do these steps out of order:

- do not promote to `Operational Control` before assisted handoff exists
- do not treat external monitors as authority before runtime continuity is established
- do not treat bridge output as continuity before returning through `checkpoint` and `analyze`
