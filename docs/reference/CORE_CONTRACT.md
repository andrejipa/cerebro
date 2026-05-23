# Core Contract

This document defines the stable public contract of the v1 core.

## What The Core Guarantees

- one canonical state file at `.cerebro/state.json`
- one local session file at `.cerebro/session.local.json`
- explicit source registration only
- deterministic validation through `validate`
- atomic writes for runtime JSON files
- monotonic `revision`
- stable read access through `StateStore` read methods and read models

## What The Core Does Not Do

- repository scanning
- context inference
- semantic interpretation of registered files
- direct extension writes to core state
- shared multi-user coordination
- automatic state mutation based on external files

## Immutable Behaviors

- `validate` never increments `revision`
- `validate` only succeeds when at least one source is registered
- `checkpoint` never changes `sources`
- `checkpoint` without an active local session is only allowed while seeding the very first checkpoint
- `analyze` is the standard operational entrypoint for continuity
- `analyze` only succeeds after `validate OK`
- `resume` only succeeds after `validate OK`
- `StateStore.update_checkpoint()` only succeeds after `validate OK`
- `StateStore.open_session()` only succeeds after `validate OK`
- `StateStore.open_session()` only succeeds when no active local session file is already present
- `validate`, `analyze`, and `resume` present the same validated revision they just checked; they do not reopen a second stale read for user output
- `session.local.json` never changes business validity
- `session.local.json` is validated against the current `state.revision` and against one canonical live-session registry in `agent_runtime.audit`; owner-authenticated mutating commands now refresh that revision binding in-band, while drifted or externally stale sessions still block later validating commands with `session_revision_invalid`
- `analyze` and `resume` fail closed with `session_open_conflict` instead of silently overwriting an already-active local session
- each opened local session now carries a unique `session_id` plus one persisted `owner_claim_id`, and canonical state mirrors the one live pair in `agent_runtime.audit.active_session_id` plus `active_session_claim_id`; that repo-local file is no longer the authority of possession by itself
- owner-authenticated commands now require four aligned proofs: the matching external session claim for that live session, the matching external live proof for that claim, an explicit `session_token` supplied by the caller, and the same local holder context that opened the session; the external claim stores only `session_token_sha256` plus `session_live_proof_sha256`, never the bearer token or the raw live proof
- the current runtime defaults both that external session claim and that external live proof to file-backed paths, including on Windows; this corrective fallback keeps continuity operational on hosts where the WinCred path fails with `CredWriteW failed: 8` for the two-credential session pair
- residual boundary: with that file-backed default, ownership proof still does not close same-user tamper or restore of the external proof files themselves; the current closure covers repo-local forgery, missing or mismatched external proof, and bounded discard/fail-closed recovery, but not strong same-user protection against restore of the external authority store
- replay from a different terminal or process holder context fails closed with `session_owner_binding_mismatch`, repo-local forgeries without the external claim fail with `session_claim_missing` or `session_claim_mismatch`, missing caller-supplied capability fails with `session_token_required`, missing or mismatched external live proof fails with `session_live_proof_missing` or `session_live_proof_mismatch`, and restored or stray session artifacts that no longer match the canonical live-session registry fail with `session_not_registered` or `session_registry_mismatch`
- after the seed round, `checkpoint` only closes continuity when the active session actor matches the requested checkpoint actor and the caller still owns the matching external claim from that same holder context; a different current holder blocks with `checkpoint_actor_mismatch`
- within one checkpoint invocation, the core only closes the same validated `session_id`; if the session changes after validation, closure fails with `session_changed_during_operation`
- the core now exposes one bounded in-band recovery step for stale or unwanted local continuity: `session-discard` / `StateStore.discard_session()`
- that recovery only removes the local session when validation is otherwise clean or only session-scoped invalid, clears the canonical live-session registry, requires the matching external claim plus an explicit caller-supplied `session_token` plus holder context whenever the session artifact is still schema-valid enough to read and still has a readable live proof, reruns `validate`, records a trace-only `session_discarded` event, and updates `last_validation` without incrementing `revision`
- `session-discard` does not reopen continuity and does not preserve an uninterrupted round; after successful discard, the next analyze-led round must still treat continuity as freshly reopened rather than uninterrupted
- if validation also fails for non-session reasons, or if the session artifact itself cannot be removed, discard fails closed and the round remains blocked
- the core enforces a bounded runtime envelope rather than unbounded growth; current caps limit plan tasks, command-registry commands, retained applied actions, retained current-plan batch labels, verification checks, retained memory notes, and retained rollback points
- some bounded runtime surfaces are last-N retained views rather than infinite history, so older approvals, actions, rollback points, or notes may be trimmed from canonical state during long rounds
- the current runtime also keeps a bounded current-plan `batch_registry` of up to 256 non-empty labels already claimed by `apply`; that registry is operational authority, not audit evidence, and it resets on `plan_updated`
- each persisted `plan` also carries a unique current-plan generation marker, and retained actions stamp that origin generation in `details`; this keeps historical retained actions from binding the new plan's `tasks[].action_ids` or current-plan batch authority after `plan_updated`, even when task ids are reused
- when older retained actions age out, the core prunes derived task and verification action-id references against the still-retained canonical action history instead of leaving orphan backlinks in canonical state
- audit `rollback_points` remain historical execution evidence only; they do not reopen rollback authority once an action is no longer retained and currently `applied`
- the registered source set is capped at 32 items and source registration replaces the full canonical set rather than merging indefinitely
- registered source paths remain reserved mutation targets while they are part of the canonical source set
- `last_validation.details` is capped at 32 persisted items; large simultaneous validation fan-out may therefore collapse the persisted failure surface into truncated or overflow-style diagnostics
- retained approval items are capped at 64
- per-task `working_set` and `acceptance_criteria` are capped at 16 items each
- checkpoint fields are intentionally short-bounded and do not carry an unlimited closure narrative
- the initial execution-policy block defaults to `autonomy_level=A1`, protected `.cerebro/**` and `.git/**`, blocked destructive command prefixes, and approval-required sensitive action kinds
- the core may therefore reject a schema-valid slice because it violates the current execution policy, even before approval or verification questions are resolved
- task-choice support and trace observability rely on bounded recent-event windows rather than a whole-log replay of `events.jsonl`
- the trace plane has environment-shaped durability modes; `balanced` is the default event-log posture, while `strict` fsyncs trace appends more aggressively
- the core may recover a stale `runtime.lock` automatically when the prior lock owner appears inactive; that is low-level coordination recovery only
- live runtime-lock contention is also bounded; the core currently times out after about five seconds if another lock owner still appears active
- verification executes only command-registry entries that are marked `allow_in_verify`, declare `side_effect=read_only`, still satisfy execution policy, and runs each command inside a disposable sandbox clone of the current project root while still writing stdout plus stderr artifacts even though the canonical command-check record names the stdout artifact only
- verify subprocesses no longer inherit the live session capability, the live external claim directory, or the live external proof directory: the runtime scrubs `CEREBRO_SESSION_TOKEN`, redirects `CEREBRO_SESSION_CLAIMS_DIR`, `CEREBRO_SESSION_LIVE_PROOFS_DIR`, plus user-state/temp roots to disposable sandbox-owned paths, and keeps `runtime.lock` held while command checks execute
- the core currently also allows callers to request an explicit subset of verify command ids, but a subset run that does not cover the full `required_command_ids` set remains diagnostic only
- such a subset run does not clear `pending_action_ids`, does not close task progress, and does not advance the canonical verification gate to `passed` from `idle` or `failed`
- verify fails closed when a command leaves observable in-root drift in that sandbox after execution, and it also fails closed plus restores pre-run authority when a command persistently tampers with guarded live runtime authority such as `runtime.lock`, `state.json`, `events.jsonl`, `session.local.json`, the active external session claim, or the active live-proof backend entry itself, including Credential Manager-backed entries when that compatibility backend is used on Windows
- the residual verify boundary is now narrower but still explicit: transient absolute-path tamper that is fully restored before command exit, or side effects on arbitrary out-of-root paths outside the guarded authority set, are still not covered by OS-level proof
- `apply` still enforces execution policy plus approval for `exec.command`, but the current runtime now rejects a selected command whose declared `side_effect` is `read_only` before execution and directs that read-only command surface to `verify` instead of trying to execute it as an action
- because the rejection happens before command execution, a declared `read_only` `exec.command` in `apply` does not create an action artifact directory, does not land a live workspace/runtime delta, and does not reopen `verification.pending_action_ids`; the residual boundary remains read-only commands that are deliberately reclassified as mutating and executed under the mutating `exec.command` path, or out-of-root side effects in other surfaces
- `validate` proves the continued existence of live operational refs backing actions still applied and checks in the current verification run; when persisted digest metadata exists for a rollback-critical action artifact or the current verification artifact, it also proves content integrity for that artifact; it does not guarantee arbitrary artifacts or historical audit-consumed artifacts or derived exports
- one `cerebro apply` invocation with multiple `--action-file` values currently supports filesystem action kinds only; it blocks the whole batch before mutation when a later item still needs approval or fails predictable preflight, restores the pre-batch workspace/runtime surface if a later execution or persist failure interrupts the batch, and commits the resulting action records in one revision only after the physical batch succeeds, but it still does not promise perfect atomicity against arbitrary external writers during execution
- the runtime now blocks reuse of a non-empty `batch_id` across separate `apply` invocations while that label remains in the retained current-plan `batch_registry`; after `plan_updated` resets that registry, batch-based `apply` and `rollback --batch-id` stay scoped to the new current-plan generation only, while explicit `rollback --action-id` may still target a retained historical applied action
- shared `batch_id` rollback is preflighted before the first mutation and fails closed if any selected reversible action no longer has a live reversible path; when a mid-execution failure or persistence failure interrupts the physical rollback phase, the core restores the pre-batch workspace/runtime surface and commits the resulting `rolled_back` states in one step after the physical rollback succeeds, but it still does not promise perfect atomic reversal against arbitrary external writers during execution
- rollback and verify fail closed on tampered or digest-mismatched rollback-critical and current verification artifacts instead of trusting content blindly
- the core exposes one governed manual retention surface on `validate`: `cerebro validate --retention-report` is dry-run only, and `cerebro validate --retention-apply` archives only the currently eligible set after validation passes
- only `StateStore` may read or write runtime JSON files
- consumers outside the core stay subordinate to persisted validation state and do not open a second validation gate
- growth beyond the current public surface requires an explicit demand and classification step before implementation

## Stable Public API

The stable core API is:

- `StateStore`
- `StateStoreError`
- `StateValidationError`
- `StateSnapshot`
- `CheckpointRecord`
- `SourceRecord`
- `ValidationRecord`

Consumers must use read methods and read models, not raw JSON shape.

Read-only helpers on `StateStore` such as `has_active_session()` are part of the supported extension boundary when they do not mutate runtime state. `has_active_session()` reports local session-file presence only; it is not a second session-validity gate.
`read_trace_observability()` is also part of that read-only extension boundary when consumers need structured trace health or integrity without parsing Markdown exports. It reports a bounded recent-tail view of trace health and integrity, not a whole-log completeness proof.

CLI command names are canonical. Do not add aliases or synonyms without an explicit architecture decision.

## Invariants

- `state.json` is always schema-valid when persisted by the core
- `sources` are relative, lexical, deduplicated, inside root, and hash-shaped
- checkpoint fields remain bounded
- session state remains local and optional
- unsupported schema versions fail explicitly
