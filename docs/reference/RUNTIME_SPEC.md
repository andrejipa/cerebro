# Cerebro Runtime Specification v1

## 1. Purpose

Cerebro is a local context continuity runtime that exists to:

- register explicit operational state
- validate context integrity
- reconstruct the working point
- allow consistent resume of validated state across invocations

It exists to solve one problem:

`loss of context during agent-assisted execution`

## 2. Fundamental Principle

Context must be:

- explicit
- validatable
- versioned
- reproducible

It must never be:

- inferred implicitly
- reconstructed by heuristics
- dependent on external memory such as chat history

## 3. Architectural Position

```text
project/
  ...
  .cerebro/
    state.json
    session.local.json
    runtime.lock
    logs/
```

`runtime.lock` may appear transiently while the core serializes runtime mutations.
It is coordination only and not canonical state.

Cerebro is a cognitive layer attached to the project.

It is not:

- the project filesystem
- a documentation tool
- a substitute for Git
- a semantic analysis engine

## 4. Operational Model

Default entrypoint:

```text
cerebro analyze
```

`cerebro analyze` is the official operational entrypoint for runtime continuity.
`resume` remains only as a compatibility command over the same deterministic core flow.

Required flow:

1. load state from `state.json`
2. run `validate`
3. if invalid, block
4. if valid:
   reconstruct the checkpoint
   open the local session in `session.local.json`
   return the current context

## 5. Execution Contract

### `validate`

Responsibilities:

- verify structural integrity
- verify source existence
- verify source hashes
- verify session consistency
- verify live operational refs backing actions still applied and checks in the current verification run
- refresh the persisted canonical validation record without changing `sources`, `checkpoint`, or `revision`
- persist at most 32 validation detail items inside `last_validation.details`

Output:

- `OK` means the runtime is usable
- `FAIL` means the runtime is blocked
- runtime use requires at least one registered source
- `validate` does not promise arbitrary artifacts or historical audit-consumed artifacts or derived exports remain available after they were already read elsewhere
- when simultaneous failures exceed the persisted validation-detail budget, the visible validation surface may degrade into truncated or overflow-style diagnostics rather than enumerate every underlying root cause cleanly

### `checkpoint`

Responsibilities:

- execute only on validated context
- update the operational state
- record the current goal
- record the next step
- close the local session
- stay within the bounded checkpoint payload budget

Session rule:

- the first bootstrap checkpoint may seed the runtime before the first session exists
- after that seed exists, checkpoint closure requires an active local session opened by `analyze` or `resume`, that session's `session_id` / `owner_claim_id` to still match the canonical live-session registry in `agent_runtime.audit`, the matching external session claim for that same session, the matching external live proof for that claim, and an explicit caller-supplied `session_token`; the claim stores only `session_token_sha256` plus `session_live_proof_sha256`, while the CLI accepts `--session-token`, `--session-token -` from stdin, or `CEREBRO_SESSION_TOKEN`
- after that seed exists, the caller must also still run from the same local holder context that opened the session; replay from a different terminal or process holder context blocks with `session_owner_binding_mismatch`
- after that seed exists, the active session actor must also match the checkpoint caller; a different current holder blocks closure with `checkpoint_actor_mismatch`
- within one checkpoint invocation, the core only closes the same validated `session_id`; if the active session changes after validation, the command fails closed with `session_changed_during_operation`
- `checkpoint.goal` is bounded to 200 characters
- `checkpoint.summary` is bounded to 1000 characters
- `checkpoint.next_step` is bounded to 300 characters
- `checkpoint.constraints` stores at most 8 items, each bounded to 160 characters
- checkpoint therefore remains a short operational summary rather than an unlimited closure transcript

### `verify`

Responsibilities:

- execute only registered verification command ids
- execute only commands that are explicitly marked `allow_in_verify=true`
- execute only commands that declare `side_effect=read_only`
- enforce the current execution policy before command execution
- execute each verification command inside a disposable sandbox clone of the current project root
- scrub `CEREBRO_SESSION_TOKEN` from the verify subprocess environment and redirect `CEREBRO_SESSION_CLAIMS_DIR`, `CEREBRO_SESSION_LIVE_PROOFS_DIR`, plus user-state/temp roots to disposable sandbox-owned paths instead of the live host locations
- hold `runtime.lock` while verify commands run so another Cerebro command cannot legitimately rewrite live runtime authority in the same window
- persist a state check plus one command check per executed verification command
- write stdout and stderr artifacts for each command execution

Current runtime note:

- the current runtime accepts an explicit subset of verification command ids when the caller provides one
- a subset run that does not execute the full `required_command_ids` set remains diagnostic only
- such a subset run does not clear `pending_action_ids`, does not promote task closure, and does not advance the canonical verification gate to `passed` from an unresolved state
- verify fails closed when a command leaves observable in-root sandbox drift after execution, so command-written workspace/runtime mutation no longer reaches the live project root through `verify`
- verify also fails closed and restores pre-run authority when a command persistently tampers with guarded live runtime authority such as `runtime.lock`, `state.json`, `events.jsonl`, `session.local.json`, the active external session claim, or the active live-proof backend entry itself, including Credential Manager-backed entries when that compatibility backend is used on Windows
- residual boundary: the runtime still does not provide OS-level proof against transient absolute-path tamper that is fully restored before process exit, arbitrary out-of-root side effects outside the guarded authority set, or perfectly concealed in-process changes that leave no observable path/type/content/mtime drift
- the persisted command check `artifact_ref` points to the stdout artifact only
- the sibling stderr artifact exists in the same verification run directory but is not surfaced as a second dedicated field in the canonical verification check record

Current runtime note:

- the current `apply` path now rejects declared `side_effect=read_only` `exec.command` before execution and reserves read-only command execution for `verify`
- because no command executes through that `apply` path, declared `read_only` `exec.command` does not create an action artifact directory, does not land a live workspace/runtime delta, and does not reopen `verification.pending_action_ids` under the current runtime
- residual boundary: the runtime still does not provide OS-level proof against out-of-root side effects or perfectly concealed in-process changes that leave no observable path/type/content/mtime drift

### `analyze`

Responsibilities:

- execute `validate`
- reconstruct context
- present the current checkpoint and registered source paths
- open a new local session only when no active local session already exists
- present the same validated revision that was just accepted

### `resume`

Responsibilities:

- execute `validate`
- reconstruct context
- open a new local session only when no active local session already exists
- present the same validated revision that was just accepted

Compatibility rule:

- `resume` remains available for compatibility
- `analyze` is the official recommended entrypoint

### `session-discard`

Responsibilities:

- validate the current state and local session under one runtime lock
- require the matching external session claim whenever `.cerebro/session.local.json` is still schema-valid enough to read, even if the session is stale
- clear the canonical live-session registry and remove `.cerebro/session.local.json` only when validation is otherwise clean or only session-scoped invalid
- rerun `validate`, persist the resulting `last_validation`, and record one trace-only `session_discarded` event without incrementing `revision`
- leave continuity explicitly closed until a later `analyze` or compatibility `resume` reopens it

## 6. Canonical State

Single canonical file:

```text
.cerebro/state.json
```

It contains:

- `agent_runtime`
- `sources`
- `checkpoint`
- `revision`
- `last_validation`

Current live-session identity is now also structured in canonical state through `agent_runtime.audit.active_session_id` and `agent_runtime.audit.active_session_claim_id`.

It does not currently contain dedicated structured fields for:

- protocol-contract version
- project identity
- detector health or detector coverage

When those anchors matter operationally, they survive only as explicit procedural metadata in the round record rather than as structured runtime state.
Structured trace observability such as `trace_status` and `trace_integrity` already exists inside `agent_runtime.audit`, but consumers that need it in stable machine-readable form should prefer the public read-only core surface over Markdown exports.

Current bounded runtime envelope:

- up to 32 registered sources
- up to 64 plan tasks
- up to 32 command-registry commands
- up to 64 retained approval items
- up to 64 retained applied actions
- up to 256 retained current-plan `batch_registry.used_ids`
- up to 32 verification checks
- up to 64 retained memory notes
- up to 32 retained rollback points
- up to 32 persisted validation detail items
- up to 16 `working_set` paths per task
- up to 16 `acceptance_criteria` entries per task

These are not unbounded historical surfaces. In the current runtime, retained approvals, actions, rollback points, and memory notes are last-N views and older entries may be trimmed from canonical state during long rounds.
The current runtime also keeps a bounded current-plan `batch_registry` of up to `256` non-empty labels already claimed by `apply`; that registry is operational authority, not audit evidence, and it resets on `plan_updated`.
Each persisted `plan` also carries a unique current-plan generation marker, and retained actions stamp that origin generation in `details`; this keeps historical retained actions from binding the new plan's `tasks[].action_ids` or current-plan batch authority after `plan_updated`, even when task ids are reused.
When retained actions age out, the runtime also prunes derived task and verification action-id references against the still-retained canonical action history instead of leaving orphan backlinks in canonical state.
Audit `rollback_points` remain historical execution evidence only; they do not reopen rollback authority once an action is no longer retained and currently `applied`.
The current runtime also persists action, rollback, and verification refs under `.cerebro/`; `validate` proves the live refs for actions still applied and the current verification run, and when persisted digest metadata exists it also proves content integrity for rollback-critical action artifacts and the current verification artifact, but it does not guarantee arbitrary artifacts or historical audit-consumed artifacts or derived outputs.
The current runtime preflights shared `batch_id` rollback before the first mutation and fails closed if any selected applied action no longer has a live reversible path; when a mid-execution failure or persistence failure interrupts rollback after some physical reversions, the runtime restores the pre-batch workspace/runtime surface and commits the resulting `rolled_back` states in one step after the physical rollback succeeds, but it still does not make execution perfectly atomic against arbitrary external writers while the batch is running.
Rollback and verify fail closed on tampered or digest-mismatched rollback-critical and current verification artifacts instead of trusting content blindly.
One `cerebro apply` invocation with multiple `--action-file` values currently supports filesystem action kinds only; it blocks the whole batch before mutation when a later item still needs approval or fails predictable preflight, restores the pre-batch workspace/runtime surface if a later execution or persistence failure interrupts the batch, and commits the action records in one revision only after the physical batch succeeds, but it still does not make execution perfectly atomic against arbitrary external writers while the batch is running.
The current runtime rejects declared `side_effect=read_only` `exec.command` during `apply` before execution and directs that read-only command surface to `verify`, because observable before/after drift proof was still vulnerable to temporary absolute-path tampering restored before command exit.
The current runtime blocks reuse of a non-empty `batch_id` across separate `apply` invocations while that label remains in the retained current-plan `batch_registry`. After `plan_updated` resets that registry, batch-based `apply` and `rollback --batch-id` stay scoped to the new current-plan generation only, while explicit `rollback --action-id` may still target a retained historical applied action.

Current initial execution-policy defaults:

- `autonomy_level = A1`
- protected paths include `.cerebro/**` and `.git/**`
- blocked command prefixes include `del`, `git`, `move`, `rd`, `ren`, `rename`, `rm`, and `rmdir`
- approval-required action kinds include `exec.command`, `fs.delete_soft`, `fs.move`, and `fs.write_patch`

Those defaults mean a plan or verification slice may be schema-valid while still being non-executable until the policy posture changes explicitly.

Rule:

`the only source of truth`

## 7. Local Session

Session file:

```text
.cerebro/session.local.json
```

Function:

- local continuity control
- not part of business authority

Current persisted keys:

- `session_id`
- `opened_at`
- `actor`
- `based_on_revision`
- `owner_claim_id`

Rule:

`disposable and isolated`

Current runtime limitation:

- the session is validated against the current `state.revision`
- each session now carries a unique `session_id` plus persisted `owner_claim_id`, and that repo-local artifact must also match the canonical live-session registry in `agent_runtime.audit`; backup-restored or stray session artifacts therefore fail closed with `session_not_registered` or `session_registry_mismatch` instead of reviving discarded continuity
- owner-authenticated mutating commands now refresh `based_on_revision` in-band, so `session_revision_invalid` indicates drift, stale artifacts, or external interference rather than ordinary same-owner progress
- `analyze` and `resume` do not silently replace an already-active local session; they fail with `session_open_conflict` until the current session is closed or discarded explicitly
- owner-authenticated commands now validate one external session claim bound to the project root and the live session id, plus one external live proof bound to that same claim; the claim stores only `session_token_sha256` plus `session_live_proof_sha256`, never the bearer token or the raw live proof itself, so repo-local `session.local.json` forgery without that claim fails closed with `session_claim_missing` or `session_claim_mismatch`, and coherent restore of `state.json` plus `session.local.json` plus copied claim/proof files without the live backends now fails closed with `session_claim_missing`, `session_claim_mismatch`, `session_live_proof_missing`, or `session_live_proof_mismatch`
- the current runtime defaults both the external session claim and the external live proof to file-backed paths, including on Windows; this corrective fallback keeps continuity operational on hosts where the WinCred path fails with `CredWriteW failed: 8` for the two-credential session pair
- residual boundary: with that file-backed default, ownership proof still does not close same-user tamper or restore of the external proof files themselves; the current closure covers repo-local forgery, missing or mismatched external proof, and bounded discard/fail-closed recovery, but not strong same-user protection against restore of the external authority store
- owner-authenticated commands also require an explicit caller-supplied `session_token`; they no longer fall back to persisted claim contents, and missing proof fails with `session_token_required`
- owner-authenticated commands still reject copied live authority from a different terminal or process holder context; that replay fails closed with `session_owner_binding_mismatch`
- `checkpoint` no longer treats any active session as sufficient after the seed round: actor mismatch blocks with `checkpoint_actor_mismatch`, a missing or mismatched external claim blocks with `session_claim_missing` or `session_claim_mismatch`, a different holder context blocks with `session_owner_binding_mismatch`, and a mid-command session swap blocks with `session_changed_during_operation`
- the CLI now exposes one bounded in-band recovery command for that stale-session condition: `session-discard`
- `session-discard` only clears the local session plus the canonical live-session registry when validation is otherwise clean or only session-scoped invalid, and it still requires the matching external claim plus an explicit caller-supplied `session_token` plus holder context whenever the stale session artifact remains schema-valid enough to read and still has a readable live proof; if the only remaining session defect is missing or mismatched live proof, discard may clear the stranded artifacts without bearer proof because the runtime can no longer prove an active live session; it does not preserve continuity, auto-open a fresh session, or bypass non-session validation failures
- `analyze` and `resume` still open the session, but they only emit the bearer token when the caller explicitly opts into `--emit-session-token`; by default the command output keeps the claim id visible and leaves the token out of human output
- after successful `session-discard`, the first later analyze-led round that passes `validate` must still treat continuity as freshly reopened rather than silently continuous

## 7A. Event Horizon And Trace Horizon

The current runtime derives some decision and observability signals from bounded recent-event windows rather than whole-log replay.

- task choice and related runtime pressure signals use recent-event windows only
- trace observability is computed from a recent event tail, not from a full historical scan of `events.jsonl`

`trace_status` and `trace_integrity` therefore describe recent observable health and recent observable integrity only.
They are not a proof that older runtime-event history remained complete forever.
Trace durability is environment-shaped too: `balanced` is the default event-log posture, while `strict` fsyncs trace appends more aggressively.
The current runtime exposes one governed manual retention surface on `validate`: `cerebro validate --retention-report` is dry-run only, and `cerebro validate --retention-apply` archives only the currently eligible set after validation passes.

## 8. Sources

Sources are:

- explicitly registered files
- validated by hash
- registered as one bounded canonical set of at most 32 files at a time
- replaced as a full set when sources are re-registered
- reserved as mutation targets while they remain registered as canonical context

Sources are not:

- interpreted
- analyzed automatically

Rule:

`the system knows only what was declared`

## 9. Invariants

These must always remain true:

- state is valid under the schema
- `revision` is monotonic
- sources are consistent and inside root
- no runtime write happens outside `StateStore`
- `validate` does not change `sources`, `checkpoint`, or `revision`
- runtime use is blocked until sources are explicitly registered
- absence of a local session is not an error

## 10. Extensions

Extensions are:

- external to the core
- consumers of canonical state

They may:

- read through the public API
- generate derived outputs such as Markdown
- render the persisted canonical validation record, but not rerun live validation

They may not:

- alter state directly
- infer context
- create a second source of truth
- reopen validation independently from the persisted canonical state

## 11. Critical Separation

```text
CORE -> truth, validation, continuity
EXTENSIONS -> consumption, visualization, support
```

Permitted flow:

```text
core -> extension
```

Forbidden flow:

```text
extension -> core (implicit write)
```

## 12. Failure Behavior

If any validation fails:

- the runtime blocks execution
- it does not attempt automatic repair
- it does not infer missing state

Rule:

`explicit failure is correct`

## 13. Non-Goals

The system must not:

- understand project semantics
- infer absent context
- replace human communication
- automate decisions
- grow in complexity without need

## 14. Philosophy

The system does not try to be intelligent.

It guarantees one thing:

`the context in use is correct`

## 15. Final Definition

Cerebro is:

`a deterministic context runtime for agent-assisted execution`

## 16. Success Criteria

The system is successful if it:

- allows context resume without chat history
- prevents use of invalid context
- maintains consistency over time
- stays simple while it grows

## 17. Evolution

The system must grow through:

- external extensions
- not by core expansion

Any change to the core requires:

- structural justification
- contract updates
- full validation

## 18. Final Rule

If there is doubt:

`preserve consistency over added capability`
