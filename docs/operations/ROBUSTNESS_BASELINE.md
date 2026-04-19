# Robustness Baseline

This document records the permanent robustness baseline confirmed by the adversarial revalidation completed on April 11, 2026.

No critical or moderate failures were found in that cycle.
The baseline below is now part of the expected contract for future evolution.

## Covered Corruption Classes

### State

- invalid JSON in `.cerebro/state.json`
- missing required root or checkpoint keys
- unexpected extra root keys
- invalid scalar types such as boolean `revision`
- bounded-value overflow such as oversized checkpoint fields
- unsupported schema versions

### Sources

- registered file removed after registration
- registered file content changed after registration
- absolute paths and parent traversal attempts
- duplicate or unordered registered paths
- source count above the schema limit
- symlink resolution outside project root

### Session

- invalid JSON in `.cerebro/session.local.json`
- missing required keys
- unexpected extra keys
- invalid scalar types such as boolean `based_on_revision`
- `based_on_revision` greater than `state.revision`

### Runtime And CLI

- `analyze` blocks when `validate` fails
- blocked `analyze` does not open a local session
- `analyze` keeps `session_token` suppressed by default and only emits it when explicitly requested with `emit_session_token=True`
- repeated `checkpoint -> analyze` cycles preserve checkpoint, sources, and revision semantics
- `import-context` and `checkpoint` keep `operation_failed` stable under real `session.local.json` unlink failure and real `state.json` replace failure, while restoring local session plus external claim/live-proof artifacts
- `close_session()` fail-closes when `session.local.json` cannot be read or validated, records `session_close_failed`, and keeps registry, local session sidecar, external claim, and live-proof intact; `import-context` and `checkpoint` surface that branch as `operation_failed`
- runtime failures remain explicit and predictable under corruption

### Extensions

- current exports fail explicitly on invalid runtime JSON
- current exports fail explicitly on schema-invalid runtime state
- current exports reject writes inside `.cerebro/`
- current exports do not leak source file contents
- current exports remain read-only when executed in sequence
- current exports reflect the canonical failed validation state after a real `analyze` block
- current exports report local session-file presence only and do not treat it as a second validity gate
- tracked extensions do not read runtime JSON directly
- tracked extensions do not read arbitrary files or enumerate directories directly

## Confirmed Invariants

- the core remains the only authority over runtime state
- `validate` preserves `revision`
- `save_state` rejects canonical writes whose `revision` would move backwards relative to the persisted state, even when `expected_revision` still matches the current file
- `analyze` remains orchestration over the same deterministic validation gate
- sources remain explicit, bounded, lexical, and rooted under the project
- local session corruption never mutates canonical state
- `apply` translates `exec.command` launch failures into explicit operational rejection plus audit evidence instead of leaking raw internal errors or partial action state
- `apply` also translates post-subprocess `exec.command` artifact persistence failures into a canonical failed action record instead of leaking `internal_error` or dropping the action from canonical history
- `exec.command` approval and retry now bind to the resolved command-registry snapshot, so drift in `argv`/`cwd`/`timeout_ms`/`determinism`/`side_effect`/`risk`/`allow_in_verify` requires a fresh gate instead of silently reusing an old approval or retry signature
- `apply` fail-closes `exec.command` before approval/retry when the referenced `command_id` is no longer present in the current `command_registry`
- `apply` fail-closes `fs.move` actions whose resolved `from` and `to` point to the same existing path, recording `action_no_effect` before any mutation or rollback-only poison can be introduced
- batch compensation in `apply` and `rollback` now replays remaining snapshot restores in best effort even after the first restore failure, then surfaces one canonical compensation error instead of silently abandoning later paths
- `verify` translates verification-command launch failures into explicit operational failure plus audit evidence instead of leaking raw internal errors or partial verification checks
- `verify` also translates execution-policy denials such as `autonomy_level A0/A1` into explicit `verification_failed` responses instead of leaking `internal_error`
- `verify` also translates post-subprocess verification artifact persistence failures into an audited canonical failed verification record instead of leaking `internal_error` or dropping verification state from canonical history
- `verify` now runs through a core-owned transaction helper, so the CLI no longer depends on `StateStore._runtime_lock()` directly, the happy-path preflight avoids one redundant canonical runtime reload, and the helper fail-closes if `root` and `StateStore.root` diverge
- `verify` proves ownership of the active session before spawning any verification command, so a missing or invalid `session_token` fails closed with no subprocess side effects and no premature verification mutation
- `verify` also fail-closes when sandbox preparation breaks before the first command, recording `verify_failed` plus a canonical failed verification record instead of aborting without audit evidence
- `verify` also fail-closes before execution when the selected command set would overflow the real `verification.checks` budget; `state_check` is now persisted separately, so the runtime accepts the full command budget without a synthetic `check-state` slot and still rejects true overflows instead of leaking `invalid_agent_verification_checks`
- `runtime.lock` recovers stale owners whose PID probe resolves to “inactive” (`ProcessLookupError`, `errno.ESRCH`, or Windows `WinError 87`) and reserves timeout only for owners that still appear alive
- `command_registry.commands[*].cwd` is only validated as a non-empty string in `validate_state_data`; the root boundary remains enforced later by `apply` and `verify`, which fail closed when a command `cwd` resolves outside the project
- `prepare_project_sandbox()` clones the workspace into a disposable tree without mutating the original project, and command-sandbox manifest diffs ignore pure directory `mtime` churn while still surfacing observable file drift
- execution policy helpers fail closed for outside-root mutation targets, protected/runtime-owned paths, registered source paths, blocked command prefixes, and missing approvals on governed action kinds
- `events_since_latest_plan_update()` slices provenance and retry-pressure inputs to the suffix owned by the latest `plan_updated`, while ignoring non-dict noise and fail-closing for invalid non-sequence inputs
- `verify` returns non-zero when selected checks pass but required verification coverage remains partial, while preserving `pending_action_ids` and the persisted verification state for the full rerun
- `verify` does not treat a previous passed snapshot as authority over later workspace drift outside the runtime; a rerun stays allowed when the workspace changed externally
- `validate` fail-closes with `state_missing` and user-facing guidance when `.cerebro/state.json` disappears after an otherwise successful `init`
- the integrated runtime flow `init -> validate -> analyze -> plan -> apply -> verify -> rollback` remains executable end-to-end in one continuous scenario, with session ownership preserved across commands and verification invalidated back to `idle` after rollback
- `open_session` persists the canonical active-session registry before `session.local.json` and rolls back the registry plus external proof artifacts if the final session-file write fails
- `close_session` also requires a readable/valid local session sidecar before cleanup, so session-read failures now abort before registry/claim/live-proof removal and leave explicit trace evidence instead of succeeding silently
- `session-discard` also recovers the narrow residue where that canonical registry survived but `session.local.json` is missing, clearing the active-session registry plus external claim/live-proof artifacts without bumping revision and without changing the plain `session_absent` path
- `open_session` also fails closed when that registry rollback itself fails after the final `session.local.json` write error, reusing the registry-only discard path so the canonical state returns to a valid no-session shape instead of persisting `session_registry_mismatch`
- state mutations that refresh an owned session now write a local `session.refresh.pending.json` journal; a crash before `state.json` commit restores the previous session sidecar on the next validation, and a stale post-commit journal finalizes without weakening `session_revision_invalid`
- file-backed session claim/live-proof errors redact external absolute paths and expose only bounded backend descriptors in user-facing failure messages
- `validate --retention-apply` fails closed when the `retention_applied` trace event cannot be committed; `retention_event_id` is added to the retention manifest only after that append succeeds, and rerun remains safe after a degraded append
- `validate --retention-apply` writes a local `manifest.pending.json` inside the archive before destructive retention steps and can finalize the same archive on rerun after a final-manifest failure without duplicating the cleanup set
- approval-governed action kinds remain governed after persistence: an action that requires approval cannot persist as `applied`, `failed`, or `rolled_back` without an approved `approval_id`
- `rollback` now fails closed for approval-governed actions whose original persisted approval is missing or no longer approved; the runtime does not invent a second rollback-only approval surface
- `rollback` of `fs.move` prunes only the empty destination directories created by the original apply, while preserving preexisting directories and any destination restored from `target_preimage_ref`
- `rollback` of `fs.create_file` in the `create-new` case also prunes only the empty destination directories created by the original apply after removing the created file
- extensions remain consumers and do not acquire authority through outputs

## Accepted Limits

- exports and derived views consume the canonical snapshot and the last persisted validation result
- exports do not revalidate the runtime by themselves
- exports do not open a second validation gate and do not attempt runtime repair
- CLI command names remain canonical; aliases require an explicit architecture decision
- hardening remains external to the core unless a future concrete gap cannot be stopped by tests and governance
- the current CLI regression layer for `import-context` and `checkpoint` now exercises real `Path.unlink` failure on `session.local.json` and real `os.replace` failure on `state.json` in `tests/test_validate.py`; this baseline still does not claim arbitrary host-level filesystem fault injection beyond those explicit rollback boundaries

## Permanent Defense Layers

- `tests/test_adversarial_revalidation.py`: adversarial corruption and repeated-runtime stress
- `tests/test_extension_contracts.py`: shared read-only export contract
- `tests/test_architecture.py`: structural and documentary boundary enforcement

## Evolution Rule

Any change that expands or changes the public surface must add proportional adversarial and regression coverage.

This applies to:

- new or changed CLI commands
- new or changed extensions
- new or changed external integrations

If a proposed change needs new authority over state, validation, `analyze`, session policy, or schema, resolve that at the architecture level before implementation.
