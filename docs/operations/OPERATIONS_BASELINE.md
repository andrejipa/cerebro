# Operations Baseline

This document is the operational baseline for daily Cerebro use.
It reflects the current runtime surface: scored tasks, action-scoped retry blocks, approval/rollback/DAG/verify gates, workload profiling, `status-export`, and the audit trail.

The system is infrastructure, not an open-ended feature project.
Use it through the formal freeze-break protocol.

## Operational Axes

Use two explicit labels when describing a round:

- runtime entry mode: `bootstrap` or `continuous work`
- external round intent label: `ENGINEERING`, `OPERATION`, `BREAKING`, or `CERTIFICATION`

Runtime entry mode describes how work enters the runtime.
Round intent labels classify why an external round exists and how it should be read in records.
These labels are operational discipline only; they do not create CLI modes or new runtime authority.

## What Cerebro Solves

- explicit continuity of project context
- deterministic restart through canonical runtime state
- read-only derived views over the current canonical state
- disciplined external execution with explicit approvals and verification

## One Daily Protocol

1. Start in the target project directory.
2. If the project has no `.cerebro/`, use bootstrap mode.
3. If the project is already initialized, start with `cerebro analyze`.
4. Then state whether the work is in `cerebro` or in a `caso`.
5. Read any supporting derived surfaces needed for the round, especially `status-export` and the audit trail when deeper runtime context matters.
6. Classify the evidence, score, approval state, retry posture, DAG shape, and verify target.
7. Plan and delegate only the slices that are independent and approved.
8. Act only inside the approved slice.
9. Verify the result.
10. Record the decision trail, the updated surface, and the residual risk.
11. If multiple approaches remain independently defensible and parallel comparison is operationally useful, compare them in parallel before consolidating the decision.
12. Reuse success memory only as documented heuristic support when the current evidence and approval boundary still match.

Use parallel comparison only when it is operationally useful and each branch is independently defensible under the current evidence and approval scope.
Do not create decorative branches when one viable path already dominates.
Hash-valid sources are not enough if they are semantically contradictory, materially stale against the declared goal, or too weak to support the context gate.
If the goal or scope changes materially after a slice has already been shaped, reopen analysis and planning instead of continuing under the old slice.
If event coverage or `status-export` observability is degraded, do not treat missing events as proof that the project is stable.

## Minimum Execution Protocol

1. On initialized work, open continuity first with `cerebro analyze`; on uninitialized work, stay in bootstrap/analysis until continuity exists.
2. Then answer: `estou no cerebro ou em um caso?`
3. Define scope for the round: what is in focus now, what is ignored for now, what can wait, and in what order analysis will proceed.
4. Classify the problem as `comprovado`, `provavel`, or `hipotese`.
5. If there is not enough proved evidence, do not advance.
6. If the registered sources are too sparse, stale, or contradictory to support the declared context and goal safely, stay in analysis instead of forcing a plan.
7. Build the next slice explicitly, including dependency shape, retry posture, and verification target.
8. Submit any risky slice to the approval boundary when policy requires it.
9. Execute only what is explicitly permitted and properly scoped.
10. Verify the result against the intended state.
11. Record the outcome, residual risk, and next step with expected tracing.
12. If a revision-changing command leaves the current `.cerebro/session.local.json` stale and the next command fails with `session_revision_invalid`, stop and treat the round as structurally blocked rather than smoothly continuous.

Treat any deviation from this flow as a protocol mismatch.
This flow defines operational discipline for the round; it is not enforced by the CLI as a runtime gate.

## Current Runtime Rules

- score helps select work, but evidence still decides whether work can move
- retry is action-scoped, not narrative-scoped
- approval, rollback, DAG validation, and verify are separate gates
- approvals are task-local; an approved payload in one task must not bleed into another
- a new `plan_updated` generation resets runtime approvals; prior approvals must not authorize the next plan implicitly
- legacy approvals without `task_id` only remain reusable when a single task is executable; multi-task plans must request a fresh scoped approval
- blocked retry/apply/verify history only counts inside the current plan generation; stale blocked events from an older plan must not penalize the new one
- the runtime derives `workload_mode` (`light|moderate|heavy`) and `work_unit_kind` (`state_only|structured_state|governed_execution`) per task
- `heavy` workload classification is per-task, not plan-global; a technical task must not force unrelated lightweight tasks into governed mode
- verification without pending delta is blocked, including explicit command subsets already covered by the last passed verification
- `status-export` and the audit trail are expected closure artifacts for external rounds as part of operational discipline, not CLI enforcement
- `status-export` may expose read-only decision provenance such as `evidence_event_ids` and selection replay mismatch; these diagnostics do not override the canonical state
- `status-export` mixes current-plan diagnostics with some runtime-lifetime counters; read its time horizon explicitly instead of assuming every counter describes the current round only
- `status-export` is a Markdown export for human inspection first; any automation that parses its sections is consuming a best-effort derived surface, not a stable machine contract
- read-only exports are derived views, not canonical truth
- parallel delegation is allowed only for independent slices
- `analyze` and `resume` open local continuity against the currently validated `state.revision`; under the current runtime, that session is revision-bound rather than a durable multi-step round token
- owner-authenticated mutating commands now refresh that session binding in-band; `session_revision_invalid` is therefore residual drift or stale-artifact evidence rather than the normal result of same-owner progress
- `analyze` and `resume` also fail closed with `session_open_conflict` when another active local session is already present; they do not silently displace the current session holder
- each active local session now carries a unique `session_id` plus persisted `owner_claim_id`, and canonical state mirrors the one live pair in `agent_runtime.audit.active_session_id` plus `active_session_claim_id`; that repo-local identity still does not prove durable cross-operator or same-actor reopen authority beyond the live registered session
- owner-authenticated commands now require the matching external session claim plus the matching external live proof plus an explicit caller-supplied `session_token` plus the same local holder context that opened the session; the claim stores only `session_token_sha256` plus `session_live_proof_sha256`, not the bearer token or the raw live proof
- the current runtime defaults both that external session claim and that external live proof to file-backed paths, including on Windows; this is a deliberate corrective fallback because the WinCred path can fail with `CredWriteW failed: 8` for the two-credential session pair on some hosts
- residual boundary: with that file-backed default, ownership proof still does not close same-user tamper or restore of the external proof files themselves; the current closure covers repo-local forgery, missing or mismatched external proof, and bounded discard/fail-closed recovery, but not strong same-user protection against restore of the external authority store
- copied authority replay from a different terminal or process holder context blocks with `session_owner_binding_mismatch`, repo-local session forgery without that claim blocks with `session_claim_missing` or `session_claim_mismatch`, missing caller-supplied capability blocks with `session_token_required`, missing or mismatched live proof blocks with `session_live_proof_missing` or `session_live_proof_mismatch`, and restored or stray session artifacts outside the canonical live-session registry block with `session_not_registered` or `session_registry_mismatch`
- after the seed round, `checkpoint` only closes continuity when the active session actor still matches the checkpoint caller, the caller still owns the matching external claim from that same holder context, and the validated `session_id` stays unchanged; otherwise it blocks with `checkpoint_actor_mismatch`, `session_claim_missing`, `session_claim_mismatch`, `session_owner_binding_mismatch`, or `session_changed_during_operation`
- `cerebro session-discard` is the bounded in-band recovery step for that stale-session condition: it clears the local session plus the canonical live-session registry only when validation is otherwise clean or only session-scoped invalid, still requires the matching external session claim plus an explicit caller-supplied `session_token` plus holder context whenever the stale session artifact remains schema-valid enough to read and still has a readable live proof, reruns `validate`, refreshes the persisted canonical validation record, and records `session_discarded` as trace-only evidence without reopening continuity
- if validation also fails for non-session reasons, or if the session artifact cannot be removed, `session-discard` fails closed and the round remains blocked until those issues are remediated
- after successful `session-discard`, the first analyze-led round must still record that the prior continuity was broken and only then reopened
- canonical state does not persist a protocol-contract version, a dedicated project identifier, or detector-health / detector-coverage fields; when those anchors matter, carry them explicitly in the round record
- detector health and detector coverage are `unknown` by default unless the round record establishes them explicitly as positively known
- the current runtime envelope is bounded: up to 64 plan tasks, 32 command-registry commands, 64 retained applied actions, 256 retained current-plan batch labels, 32 verification checks, 64 retained memory notes, and 32 retained rollback points
- long rounds must therefore be split or closed before those ceilings are crossed; the runtime does not guarantee unbounded accumulation inside one continuity window
- retained approvals, applied actions, rollback points, and memory notes are last-N canonical surfaces rather than infinite runtime history
- the current runtime also keeps a bounded current-plan `batch_registry` of up to 256 non-empty labels already claimed by `apply`; that registry is operational authority, not audit evidence, and it resets on `plan_updated`
- each persisted `plan` also carries a unique current-plan generation marker, and retained actions stamp that origin generation in `details`; this keeps historical retained actions from binding the new plan's `tasks[].action_ids` or current-plan batch authority after `plan_updated`, even when task ids are reused
- when retained actions age out, the core prunes derived task and verification action-id references against the still-retained canonical action history instead of leaving orphan backlinks in canonical state
- audit `rollback_points` remain historical execution evidence only; they do not reopen rollback authority once an action is no longer retained and currently `applied`
- retained approval items are capped at 64; older approval records may trim away during approval-heavy rounds and stop being directly resolvable from canonical state
- canonical registered sources are capped at 32 entries, and re-registering sources replaces the full declared set rather than merging indefinitely
- the default execution-policy surface for a fresh runtime block includes `autonomy_level=A1`, protected paths `.cerebro/**` and `.git/**`, blocked command prefixes such as `git`, `rm`, and `rmdir`, and approval-required action kinds including `exec.command`, `fs.delete_soft`, `fs.move`, and `fs.write_patch`
- a schema-valid slice may therefore still be operationally non-executable until the plan or policy posture is reshaped explicitly
- a registered source file is also a reserved mutation target in the current runtime; if a file must move from context to write target, rotate or narrow the canonical source set explicitly before treating that mutation as normal work
- the persisted validation record is bounded: `last_validation.details` stores at most 32 items, so extreme failure fan-out can collapse the visible validation surface into truncated or overflow-style diagnostics
- each task is capped at 16 `working_set` paths and 16 `acceptance_criteria`; if a faithful slice needs more than that, split it before persisting the task
- `checkpoint` remains a short bounded summary: `goal` up to 200 characters, `summary` up to 1000, `next_step` up to 300, and at most 8 `constraints` of up to 160 characters each
- task choice and event-derived pressure are based on bounded recent-event windows rather than whole-log replay
- structured trace observability reports recent-tail health and integrity only; it is not a whole-log completeness proof
- trace durability is environment-dependent in the current runtime: `balanced` is the default trace-log posture, while `strict` fsyncs trace appends more aggressively; neither mode turns recent-tail diagnostics into whole-log proof
- live contention on `.cerebro/runtime.lock` is bounded too: the current core waits about five seconds before failing with a runtime-lock timeout if another owner still appears active
- the current runtime accepts explicit verify subsets too, but a subset run that does not cover the full `required_command_ids` set remains diagnostic only
- such a subset run does not clear pending-action coverage, does not promote task closure, and does not advance the canonical verify gate out of an unresolved state
- `verify` now requires `allow_in_verify=true` plus `side_effect=read_only`, runs each command inside a disposable sandbox clone of the current project root, scrubs live session/env authority from the subprocess, keeps `runtime.lock` held while the commands execute, and fails closed when that sandbox shows observable in-root drift after command execution
- `verify` also restores and fails closed on persistent tamper of guarded live runtime authority (`runtime.lock`, `state.json`, `events.jsonl`, `session.local.json`, the active external session claim, and the active live-proof backend entry itself, including Credential Manager-backed entries when that compatibility backend is used on Windows) instead of discovering that damage only after the command already escaped
- `apply` now rejects declared `side_effect=read_only` `exec.command` before execution and reserves read-only command execution for `verify`, because observable before/after drift proof was still bypassable by temporary absolute-path tampering restored before command exit
- that fail-closed rejection leaves no action artifact directory, no live workspace/runtime delta, and no new verify burden
- the residual verify boundary is still transient absolute-path tamper fully restored before command exit, arbitrary out-of-root side effects outside the guarded authority set, or perfectly concealed changes that leave no observable path/type/content/mtime drift
- command verify persists both stdout and stderr artifacts, but the canonical verification check record points to the stdout artifact only; treat stderr as sibling diagnostic support when command failure details matter
- `validate` proves live refs for actions still applied and checks in the current verification run before the runtime is treated as usable; when persisted digest metadata exists for a rollback-critical action artifact or the current verification artifact, it also proves content integrity for that artifact; it does not guarantee arbitrary artifacts or historical audit-consumed artifacts or derived `status-export` / audit-trail outputs
- one `cerebro apply` invocation with multiple `--action-file` values currently supports filesystem action kinds only; it blocks the whole batch before mutation when a later item still needs approval or fails predictable preflight, restores the pre-batch workspace/runtime surface if a later execution or persist failure interrupts the batch, and commits the resulting action records in one revision only after the physical batch succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- the runtime now blocks reuse of a non-empty `batch_id` across separate `apply` invocations while that label remains in the retained current-plan `batch_registry`; after `plan_updated` resets that registry, batch-based `apply` and `rollback --batch-id` stay scoped to the new current-plan generation only, while explicit `rollback --action-id` may still target a retained historical applied action
- shared `batch_id` rollback is preflighted before the first mutation and fails closed if any selected reversible action no longer has a live reversible path; when a mid-execution failure or persistence failure interrupts rollback after some physical reversions, the runtime restores the pre-batch workspace/runtime surface and commits the resulting `rolled_back` states in one step after the physical rollback succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- rollback and verify fail closed on tampered or digest-mismatched rollback-critical and current verification artifacts instead of trusting content blindly
- the current runtime exposes one governed manual retention surface on `validate`: `cerebro validate --retention-report` is dry-run only, and `cerebro validate --retention-apply` archives only the currently eligible set after validation passes
- `cerebro validate --retention-apply` also fails closed when it cannot append its own `retention_applied` trace event; the archive manifest gains `retention_event_id` only after that append succeeds, and rerun is the safe recovery path after a degraded append
- retention is deliberately manual, not automatic; no threshold-driven background cleanup runs without an explicit operator invocation
- artifact retention preserves all live runtime refs first, then preserves the most recent unreferenced `verification/*` groups and `actions/*` groups, and archives only older unreferenced groups into `.cerebro/trash/retention/`
- artifact cleanup is grouped, not file-by-file: if the current verification state keeps one `stdout` artifact live, the sibling files in that same verification run stay preserved with it
- unknown artifact surfaces stay blocked instead of being guessed as disposable
- event-log retention preserves every `parallel_approach_consolidated` entry in the active `events.jsonl`, preserves the latest non-consolidation tail, and archives only older non-consolidation lines into `.cerebro/trash/retention/`; this keeps the consolidation read-model derivable from the active log while bounding noise growth
- deleting or truncating those surfaces outside the governed retention flow remains out-of-band and can still break rollback, diagnosis, or audit reading without changing canonical state shape
- parallel comparison is allowed only for independent approaches with an explicit join point
- parallel comparison should be opened only when it is operationally useful and at least two approaches remain independently defensible under the current evidence and approval boundary
- the formal comparison result is append-only and must include the full compared set, one winner, and the rejected approaches
- repeated consolidation for the same subject must supersede the current head instead of reusing stale lineage
- read-only status surfaces must downgrade stale or replayed valid consolidation records instead of showing them as the current winner
- no implicit context is allowed
- no second source of truth is allowed
- no unverified retry should be treated as progress
- successful prior decisions may be reused as success memory, and may slightly reinforce later scoring only as a documented heuristic
- malformed success memory is ignored instead of being treated as weak success
- hash-valid registered sources do not resolve semantic conflict, temporal drift, or low-quality context on their own
- `agent_runtime.memory.notes` remains heuristic historical support only and may become operationally stale across material source, goal, or project changes
- after a structural continuity break or out-of-band remediation, existing memory notes remain historical support only until a fresh analyze-led round reaffirms that they still fit the current project, goal, and source set
- lack of detector signal is not proof that nothing changed when event coverage or detector health is unknown
- degraded `status-export` diagnostics reduce confidence in event-derived guidance; they do not clear the round automatically
- a technically accepted mutation outside analyze-led continuity remains a protocol mismatch until the round is reanchored explicitly
- a new `plan_updated` generation resets current-plan approvals, current-plan verification pressure, and the current-plan `batch_registry`, but historical applied actions and rollback points remain historical evidence; they do not become verified simply because the plan changed, and those retained historical actions no longer need to appear in the new plan's `tasks[].action_ids`
- rollback after failed verification does not by itself clear the blocking state; verification must pass again or another corrective path must be chosen explicitly
- rollback of a previously verified delta invalidates that earlier passed verification for the current workspace and reopens verification pressure
- a rollback path that existed at planning time may still fail later if the workspace diverged or rollback artifacts no longer match the applied delta; even with batch preflight plus pre-batch restore on observed rollback failure, arbitrary external writers during execution can still defeat a perfect atomicity guarantee, so treat the branch as blocked instead of assuming rollback is still available or transactionally isolated
- governance decisions such as source arbitration, goal reset, observability degradation, and project-identity anchoring are currently procedural records, not dedicated runtime fields
- if blocked runtime state prevents `checkpoint`, the recovery decision must be recorded outside canonical state and reconciled when a later analyze-led round succeeds
- the bundled `_local/autorun` monitor does not imply coverage of docs-only protocol changes; monitor silence is not proof that operational semantics stayed unchanged

## Heuristics For Comparison And Consolidation

When more than one approach is available, compare them using the same operational frame:

- evidence strength
- score
- approval risk
- reversibility
- rollback cost
- verify burden
- residual risk
- whether the approach matches a previously successful pattern

The consolidation rule is simple:

- pick the path with the strongest current evidence and the cleanest closure path
- keep the losing path documented so the next round can reuse or reject it explicitly
- do not let familiarity override current evidence
- do not convert a past success into a blanket rule
- treat success memory as heuristic support only; it is not the formal consolidation ledger

## Mode 1: Bootstrap

Use this mode only when entering a project with no `.cerebro/` or when onboarding an already live project that has not been initialized yet.

Protocol:

1. Optionally run `cerebro bootstrap-scan --root ...` to get assistive candidates.
2. Decide the initial source files explicitly.
3. Run `cerebro init`.
4. Run `cerebro import-context --files ...`.
5. Run `cerebro checkpoint --goal ... --summary ... --next-step ...`.
6. Run `cerebro validate`.
7. From that point on, stop bootstrapping and switch to `cerebro analyze` as the standard entrypoint.

If the candidate source set is too sparse, stale, or contradictory to state context and next-step intent safely, remain in bootstrap/analysis and tighten the source set before treating initialization as operationally sufficient.
If safe bootstrap context would require more than 32 files at once, narrow or rotate the declared canonical source set explicitly instead of assuming the runtime can persist every candidate simultaneously.

`bootstrap-scan` is assistive only.
Its `--root` flag affects the scan only and does not relocate later runtime commands.

## Mode 2: Continuous Work

Use this mode for normal day-to-day work in a project that already has `.cerebro/`.

Protocol:

1. Start with `cerebro analyze`.
2. Read `status-export` and the audit trail when the round needs the current decision surface.
   Treat any replay or provenance data there as diagnostic support only; the canonical state still decides what is current.
3. Answer explicitly whether the work is in `cerebro` or in a `caso`.
4. Classify the current problem as `comprovado`, `provavel`, or `hipotese`.
5. If evidence is not strong enough, stop and do not execute.
6. If more than one path exists, compare score, reversibility, retry cost, and approval risk before choosing.
7. Build a plan-backed slice and delegate only independent branches.
8. Treat the chosen path as blocked until approval is explicit when policy requires it.
9. Do the actual project work only inside the approved slice.
10. Verify the result.
11. Record the result, residual risk, and next step.
12. Close the round only after the record is complete.
13. If independent candidate approaches remain defensible and the comparison is operationally useful, compare them in parallel and consolidate explicitly before closure.

If the goal or scope changes materially after planning begins, reopen analysis and plan a new slice instead of continuing under the prior approval and verification assumptions.
If the intended slice would exceed the current bounded runtime envelope, reduce the slice or close and reopen the round before overflow occurs.
Do the same when approval-heavy work is approaching the retained approval cap, when the closure narrative would overflow checkpoint budget, or when one faithful task would need more than 16 `working_set` paths or `acceptance_criteria`.
Do the same when the planned mutation targets a file that is still registered as canonical context, or when the slice is valid on paper but blocked by the current execution-policy defaults.
Do the same when the round is leaning on a subset-verify run that did not execute the full required gate, or when rollback/diagnosis depends on runtime artifacts that are no longer proven present.

Only do this when the comparison is operationally useful and the alternatives are each defensible under the current evidence and approval posture.
Do not open decorative branches to simulate rigor.

## Mode 3: Audit / Engineering (External Protocol Round)

Use this round shape only for external stress, regression validation, bridge-assisted execution, or protocol-driven agent work.
When such a round is opened, record exactly one intent label: `ENGINEERING`, `OPERATION`, `BREAKING`, or `CERTIFICATION`.
That label classifies the round record; it is not a CLI-enforced runtime mode.

Protocol:

1. Anchor yourself in the target project with `cerebro analyze` when the project is already initialized.
2. Answer explicitly whether the round is in `cerebro` or in a `caso`.
3. Read `status-export` and the current audit trail when deeper runtime evidence is required.
4. Classify the target problem as `comprovado`, `provavel`, or `hipotese`.
5. If evidence is still weak, block the round before execution.
6. If you need mechanical external execution, use the automation bridge.
7. If the task needs role-based external coordination, run one full agent round through the approved protocol.
8. Execute only the slice that is approved and properly delegated.
9. Verify and record the real result before calling the work complete.
10. Keep all external artifacts non-canonical.
11. Return to Cerebro explicitly through `checkpoint` and `analyze` only after the round is fully recorded.
12. If `session_revision_invalid` blocks the next step after a revision-changing command, stop and record that blocked-round boundary explicitly instead of pretending the round remained continuously open.
13. If the runtime is too blocked to accept `checkpoint`, keep the blocked-round record explicit, but do not assume any CLI path will import it back automatically later.
14. When that blocked-round record exists outside canonical state, use the same minimum closure-record content and reconcile it later by explicit manual restatement in the first analyze-led round that succeeds again.
15. If more than one external blocked-round record could plausibly match, cite the exact external record identifier, path, or timestamp being reconciled.

If the round changes the operational protocol only through canonical docs or handoff text, do not rely on `_local/autorun` silence as proof that nothing operational changed.
Reopen the next relevant round explicitly through `analyze` and restate the intended protocol assumptions.
If project identity or protocol-contract identity could plausibly be confused, treat them as ambiguous until the round record names the procedural anchor used for each.
If the round grows toward the current runtime ceilings or starts depending on older action, rollback, or memory history that may be trimmed from canonical state, close or narrow it before that support disappears.

## Bridge Use

Use the automation bridge only for:

- repeated read-only audits
- mechanical execution packaging
- structured per-run logging that would otherwise be assembled manually

Do not use the automation bridge for:

- deciding canonical context
- choosing `sources`
- replacing `import-context`
- replacing `checkpoint` or `analyze`
- defining project truth

## Agent Use

Use the agent protocol only when the work is external engineering, audit, triage, correction, or flow validation.
On initialized work, start every such round by opening continuity with `cerebro analyze`, then declare whether the work is in `cerebro` or in a `caso`.
On uninitialized work, establish that context inside analysis before deeper bootstrap guidance.
If that context is ambiguous, block the round before planning or execution.
If a later successful command advances `state.revision` and the next step fails with `session_revision_invalid`, treat that as a structural runtime block, not as a silent continuation failure.

Do not use the agent team as a replacement for the runtime.

- agents do not define state
- agents do not define semantics
- agents do not define canonical context
- agents do not replace `analyze`
- external tools do not compete with `analyze`
- agents do not create a second source of truth

## Read-Only Exports

The runtime exposes a read-only export family for derived inspection:

- `handoff-export`
- `context-index-export`
- `impact-export`
- `sources-export`
- `return-map-export`
- `status-export`
- `validation-export`

These surfaces are useful operational views, not new canonical state.

## Red Lines

Never:

- change the core without formal architecture approval
- execute with only implicit evidence
- execute before approval is explicit
- ignore a blocked retry
- leave a round without tracing
- treat bridge output as canonical truth
- let heuristics choose context automatically
- register sources automatically
- bypass `validate` or `analyze`
- create a second source of truth

## Do Not Tinker

If there is no concrete, repeated, unmet use case against the current approved operational surface, do not evolve the system.

## Onboarding Quick Start

- To enter a new project: use bootstrap mode.
- To resume a project: start with `cerebro analyze`.
- To inspect state quickly: use the read-only exports.
- To run external engineering rounds: use the approved agent protocol.

## Status

Cerebro is operational infrastructure.

Future evolution is still possible, but only through:

- one explicit next-layer decision
- one concrete repeated unmet use case
- one minimum safe external increment at a time
