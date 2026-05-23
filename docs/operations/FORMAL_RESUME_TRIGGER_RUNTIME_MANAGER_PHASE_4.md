# Formal Resume Trigger — Runtime Manager Phase 4 Closing Sprint

status: active
created_at: 2026-05-08
owner: human-approved autonomous execution
level: 2
mode: feature-closing-sprint

## Purpose

Close Phase 4 of the Runtime Manager by completing the remaining operational
gaps that were not covered when the write-API store slices (4.1–4.4) were
implemented:

- Small read APIs missing from the store (`read_validation`, `list_approvals`,
  `check_rollback_eligibility`, `list_rollback_runs`)
- `auto_stop_on_failure` option in `run_command()`
- Full CLI surface for all write-API operations (lease, stop, validation,
  approval, rollback)
- Formal reconciliation: phase item resolved, contract updated, docs updated

## Architecture Decision: managed_* Tables (not source_kind)

Phase 4 uses separate `managed_*` tables (`managed_leases`,
`managed_stop_conditions`, `managed_validations`, `managed_approvals`,
`rollback_registry`) for runtime-owned state rather than a `source_kind` column
on existing TOML-imported tables. This is the canonical Phase 4 design.

Rationale:
- Clear import vs. runtime-owned boundary: `sync_observation_center()` never
  touches `managed_*` tables, so no migration or column-filter complexity.
- Easier audit: a single query on each `managed_*` table shows all runtime-owned
  state with no TOML rows mixed in.
- Lower migration risk than adding `source_kind` to existing TOML-imported tables.

This decision is final for Phase 4. `source_kind` may be revisited in a later
phase only if a concrete bug or audit finding requires it.

## Whitelist

Writable:
- `docs/operations/FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_4.md`
- `core/runtime_manager_store.py`
- `cli/commands/runtime_manager.py`
- `cli/main.py`
- `tests/test_runtime_manager_store.py`
- `tests/test_cli.py`
- `docs/operations/observation_center.toml`
- `docs/operations/observation_center_archive.toml`
- `docs/operations/RUNTIME_MANAGER_CONTRACT.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `cerebro/CLAUDE.md`

Readable:
- all of the above
- existing runtime manager tests
- existing CLI tests

## Explicit Non-Authorization

This trigger does not authorize:
- adding Temporal, LangGraph, MCP, OpenTelemetry, or external adapters;
- creating a worker daemon or background process;
- allowing commands outside the registry;
- changing the managed_* table approach to source_kind;
- weakening existing tests.

## Acceptance Criteria

- `read_validation(validation_id)` returns `ManagedValidation | None`.
- `list_approvals(subject_id, limit)` returns `list[ApprovalRecord]`.
- `check_rollback_eligibility(evidence_id)` checks eligibility without executing.
- `list_rollback_runs(forward_command_id, limit)` returns evidence rows where
  `command_id LIKE 'rollback:%'` (no separate table required).
- `run_command(..., auto_stop_on_failure=True)` raises a managed stop condition
  when timeout or non-zero returncode occurs.
- CLI: `runtime-manager lease acquire/release/heartbeat/list`
- CLI: `runtime-manager stop raise/resolve/list`
- CLI: `runtime-manager validation record/show`
- CLI: `runtime-manager approval record/revoke/list`
- CLI: `runtime-manager rollback <evidence-id>` and `rollback list`
- Full gate green after all changes.
- `runtime-manager-phase-4` marked resolved and archived.
- Contract updated to document managed_* architecture.

## Stop Conditions

- Any gate failure not directly caused by this sprint's changes.
- Any need to touch external adapters, worker daemons, or network services.
- Any need to change the managed_* table design mid-sprint.
