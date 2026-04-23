# Validation Decomposition Plan

## Status

- phase: `B`
- mode: `autonomous-slice-loop`
- trigger status: `approved / active`
- current boundary:
  - `docs/`: authorized
  - `tests/`: authorized for `tests/test_validate_error_ordering.py` only
  - `core/`: authorized for `core/validation.py` only
  - `cli/`: closed
- characterization status:
  - `tests/test_validate_error_ordering.py` added with `15` tests
  - coverage split: `14` per-block malformed payloads + `1` mixed aggregate-order case
- slice progress:
  - completed: `13/14`
  - latest slice: `_validate_verification_relations_block`
- current live gate:
  - AGENTS-equivalent suite: `840` tests, `0` failures, `6` skips
  - architecture gate: `51` tests, `0` failures

## Scope Statement

This plan targets only `_validate_agent_runtime_block` in
`core/validation.py:192-1057`.

The goal is structural maintenance only: reduce the cognitive density of the
single runtime-validation function by extracting private helpers in the same
file while preserving exact observable behavior.

This plan is not:

- a cleanup pass
- a naming pass
- a message consolidation pass
- a type-system upgrade
- a justification for broader `core/validation.py` edits

No code is changed in this phase. This document exists only to decide whether a
future trigger can stay narrow enough to be safe.

## Function Snapshot

- target function length: `866` lines (`192-1057`, inclusive)
- current structure:
  - `9` primary shape-validation blocks
  - `5` relational tail blocks
- total sub-blocks identified for planning: `14`
- main risk of extraction:
  - silent drift in error append-order, exact error text, or exact error code
- main reason a trigger is required later:
  - the function lives in `core/validation.py`, which is explicitly frozen
    without an architecture decision and formal resume trigger

## Fan-Out Classification Table

| Block | Lines | Locals Read | Locals Written | External State Accessed | Error Codes Emitted | Implicit Dependencies |
| --- | --- | --- | --- | --- | --- | --- |
| `plan_core` | `213-330` | `errors`, `plan`, `prefix`, `task_ids`, `task_statuses`, `task_dependencies`, `action_ids_by_task` | `current_task_id`, `depends_on`, `field`, `index`, `key`, `plan_status`, `task`, `task_id`, `task_prefix`, `task_status`, `tasks`, `value` | `PLAN_KEYS`, `PLAN_TASK_KEYS`, `VALID_PLAN_STATUSES`, `VALID_TASK_STATUSES`, `MAX_PLAN_TASKS`, `MAX_TASK_WORKING_SET`, `MAX_TASK_ACCEPTANCE_CRITERIA`, `_require_exact_keys`, `_validate_string`, `_validate_non_empty_string`, `_validate_string_list`, `_is_int`, `error` | `invalid_agent_plan`, `invalid_agent_plan_field`, `invalid_agent_plan_status`, `invalid_agent_plan_tasks`, `invalid_agent_plan_task_item`, `invalid_agent_plan_task_field`, `invalid_agent_plan_task_status`, `invalid_agent_plan_task_depends_on`, `invalid_agent_plan_task_working_set`, `invalid_agent_plan_task_acceptance_criteria`, `invalid_agent_plan_task_action_ids`, `invalid_agent_plan_current_task_id` | seeds `task_ids`, `task_statuses`, `task_dependencies`, `action_ids_by_task`; later used by approvals, task-relations, action-relations |
| `execution_policy_core` | `334-383` | `errors`, `execution_policy`, `prefix` | `approval_required_kinds`, `autonomy_level`, `item`, `raw_approval_required_kinds` | `EXECUTION_POLICY_KEYS`, `VALID_AUTONOMY_LEVELS`, `MAX_PROTECTED_PATHS`, `MAX_BLOCKED_COMMAND_PREFIXES`, `MAX_APPROVAL_REQUIRED_KINDS`, `_require_exact_keys`, `_validate_string_list`, `error` | `invalid_execution_policy`, `invalid_execution_policy_autonomy_level`, `invalid_execution_policy_protected_paths`, `invalid_execution_policy_blocked_command_prefixes`, `invalid_execution_policy_approval_required_kinds` | writes `approval_required_kinds`; later consumed only by `action_relations` |
| `command_registry_core` | `386-495` | `errors`, `command_registry`, `prefix`, `command_ids`, `allow_in_verify_command_ids` | `arg_index`, `argv`, `command`, `command_id`, `command_prefix`, `commands`, `determinism`, `index`, `item`, `risk`, `side_effect`, `timeout_ms` | `COMMAND_REGISTRY_KEYS`, `COMMAND_RECORD_KEYS`, `VALID_COMMAND_DETERMINISM`, `VALID_COMMAND_SIDE_EFFECTS`, `VALID_COMMAND_RISKS`, `MAX_COMMAND_REGISTRY_COMMANDS`, `_require_exact_keys`, `_validate_non_empty_string`, `_is_int`, `error` | `invalid_command_registry`, `invalid_command_registry_commands`, `invalid_command_registry_command_item`, `invalid_command_registry_command_id`, `invalid_command_registry_command_argv`, `invalid_command_registry_command_argv_item`, `invalid_command_registry_command_cwd`, `invalid_command_registry_command_timeout_ms`, `invalid_command_registry_command_determinism`, `invalid_command_registry_command_side_effect`, `invalid_command_registry_command_risk`, `invalid_command_registry_command_allow_in_verify`, `invalid_command_registry_command_verify_side_effect` | writes `command_ids` and `allow_in_verify_command_ids`; later consumed only by `verification_relations` |
| `approvals_core` | `498-569` | `errors`, `approvals`, `prefix`, `task_ids`, `approval_ids`, `approval_statuses`, `approval_items` | `approval`, `approval_id`, `approval_prefix`, `approval_task_id`, `field`, `index`, `items`, `status` | `APPROVALS_KEYS`, `APPROVAL_RECORD_KEYS`, `VALID_APPROVAL_STATUSES`, `MAX_APPROVAL_ITEMS`, `_require_exact_keys`, `_validate_non_empty_string`, `_validate_string`, `error` | `invalid_agent_approvals`, `invalid_agent_approvals_items`, `invalid_agent_approval_item`, `invalid_agent_approval_field`, `invalid_agent_approval_status` | depends on `task_ids` from `plan_core`; writes `approval_ids`, `approval_statuses`, `approval_items`; later consumed by `action_relations` |
| `actions_core` | `572-622` | `errors`, `actions`, `prefix`, `action_ids_seen`, `action_statuses` | `action`, `action_id`, `action_prefix`, `field`, `index`, `kind`, `status` | `ACTION_RECORD_KEYS`, `VALID_ACTION_KINDS`, `VALID_ACTION_STATUSES`, `MAX_ACTION_HISTORY`, `_require_exact_keys`, `_validate_string`, `_validate_string_list`, `error` | `invalid_agent_actions`, `invalid_agent_action_item`, `invalid_agent_action_id`, `invalid_agent_action_kind`, `invalid_agent_action_status`, `invalid_agent_action_field`, `invalid_agent_action_details`, `invalid_agent_action_artifact_refs` | writes `action_ids_seen` and `action_statuses`; later consumed by audit/action/verification relations |
| `batch_registry_core` | `626-653` | `errors`, `batch_registry`, `prefix`, `batch_registry_used_ids` | `batch_id`, `index`, `used_ids` | `BATCH_REGISTRY_KEYS`, `MAX_USED_BATCH_IDS`, `_require_exact_keys`, `_validate_non_empty_string`, `error` | `invalid_agent_batch_registry`, `invalid_agent_batch_registry_used_ids` | writes `batch_registry_used_ids`; later consumed only by `action_relations` |
| `verification_core` | `656-779` | `errors`, `verification`, `prefix` | `artifact_sha256`, `check`, `check_prefix`, `checks`, `exit_code`, `failed_attempt_count`, `field`, `index`, `state_check`, `state_check_exit_code`, `state_check_status`, `status`, `verification_status` | `VERIFICATION_KEYS`, `VERIFICATION_STATE_CHECK_KEYS`, `VERIFICATION_CHECK_KEYS`, `VALID_VERIFICATION_STATUSES`, `MAX_VERIFICATION_CHECKS`, `_require_exact_keys`, `_validate_string`, `_validate_string_list`, `_is_valid_sha256`, `_is_int`, `error` | `invalid_agent_verification`, `invalid_agent_verification_field`, `invalid_agent_verification_status`, `invalid_agent_verification_required_command_ids`, `invalid_agent_verification_pending_action_ids`, `invalid_agent_verification_failed_attempt_count`, `invalid_agent_verification_state_check`, `invalid_agent_verification_state_check_status`, `invalid_agent_verification_state_check_exit_code`, `invalid_agent_verification_state_check_field`, `invalid_agent_verification_checks`, `invalid_agent_verification_check_item`, `invalid_agent_verification_check_field`, `invalid_agent_verification_check_covered_action_ids`, `invalid_agent_verification_check_status`, `invalid_agent_verification_check_exit_code` | writes `state_check`; later consumed by `verification_relations` |
| `memory_core` | `782-821` | `errors`, `memory`, `prefix` | `field`, `index`, `kind`, `note`, `note_prefix`, `notes`, `ttl_days` | `MEMORY_KEYS`, `MEMORY_NOTE_KEYS`, `VALID_MEMORY_KINDS`, `MAX_MEMORY_NOTES`, `MAX_MEMORY_TTL_DAYS`, `_require_exact_keys`, `_validate_non_empty_string`, `_is_int`, `error` | `invalid_agent_memory`, `invalid_agent_memory_notes`, `invalid_agent_memory_note_item`, `invalid_agent_memory_note_field`, `invalid_agent_memory_note_kind`, `invalid_agent_memory_note_ttl_days` | no later block reads outputs from this block |
| `audit_core` | `824-906` | `errors`, `audit`, `prefix` | `active_session_claim_id`, `active_session_id`, `field`, `index`, `kind`, `next_event_id`, `rollback_point`, `rollback_points`, `rollback_prefix`, `trace_integrity`, `trace_status` | `AUDIT_KEYS`, `ROLLBACK_POINT_KEYS`, `VALID_TRACE_STATUSES`, `VALID_TRACE_INTEGRITIES`, `VALID_ROLLBACK_KINDS`, `MAX_ROLLBACK_POINTS`, `_require_exact_keys`, `_validate_string`, `_validate_non_empty_string`, `_is_int`, `error` | `invalid_agent_audit`, `invalid_agent_audit_field`, `invalid_agent_audit_rollback_points`, `invalid_agent_audit_rollback_point_item`, `invalid_agent_audit_rollback_point_field`, `invalid_agent_audit_rollback_point_kind` | later `audit_last_action_ref` reads `audit` only; no derived collection is written here |
| `plan_dependency_relations` | `907-940` | `errors`, `task_dependencies`, `task_ids`, `task_statuses` | `dep`, `depends_on`, `task_id`; nested `visit()` closure uses `visiting`, `visited` | `error` | `invalid_agent_plan_task_depends_on`, `invalid_agent_plan_task_status`, `invalid_agent_plan_tasks` | requires `plan_core` to have populated `task_ids`, `task_statuses`, `task_dependencies`; introduces nested DFS closure and order-sensitive append behavior |
| `audit_last_action_ref` | `948-951` | `errors`, `audit`, `action_ids_seen`, `prefix` | `last_action_id` | `error` | `invalid_agent_audit_field` | requires `actions_core` and `audit_core`; tiny but order-sensitive because it sits before action relations |
| `task_action_ref_relations` | `953-956` | `errors`, `action_ids_by_task`, `action_ids_seen` | `action_id`, `task_action_ids`, `task_id` | `error` | `invalid_agent_plan_task_action_ids` | requires `plan_core` and `actions_core`; tiny, deterministic tail block |
| `action_relations` | `958-1011` | `errors`, `actions`, `agent_runtime`, `task_ids`, `action_ids_by_task`, `approval_ids`, `approval_items`, `approval_statuses`, `approval_required_kinds`, `batch_registry_used_ids`, `executable_task_ids` | `action`, `action_id`, `action_status`, `approval`, `approval_error`, `approval_id`, `approval_status`, `batch_id`, `current_plan_action`, `item`, `legacy_single_task_fallback`, `task_id` | `action_belongs_to_current_plan`, `required_action_approval_error`, `error`, `next` | `invalid_agent_action_field`, `invalid_agent_action_status` | highest cross-block coupling; requires outputs from plan, approvals, actions, execution_policy, batch_registry; sensitive to exact append order and legacy fallback logic |
| `verification_relations` | `1013-1055` | `errors`, `verification`, `command_ids`, `allow_in_verify_command_ids`, `action_ids_seen`, `action_statuses`, `state_check`, `prefix` | `action_id`, `check`, `checks`, `command_id`, `covered_action_ids`, `gate`, `has_failed_check`, `pending_action_ids`, `required_command_ids`, `state_check_failed`, `verification_status` | `error` | `invalid_agent_verification_required_command_ids`, `invalid_agent_verification_pending_action_ids`, `invalid_agent_verification_check_field`, `invalid_agent_verification_check_covered_action_ids`, `invalid_agent_verification_status` | requires outputs from command_registry, actions, and verification core; order-sensitive because it closes the function with aggregate status checks |

## Proposed Slice Order

The extraction order below follows the Phase A constraint: start with the
lowest-fan-out block that has zero dependence on later blocks, then move
outward toward higher-coupling relational blocks.

1. `_validate_memory_block` (`781-821`)
2. `_validate_execution_policy_block` (`334-383`)
3. `_validate_batch_registry_block` (`626-653`)
4. `_validate_command_registry_block` (`386-495`)
5. `_validate_audit_block` (`824-906`)
6. `_validate_actions_block` (`572-622`)
7. `_validate_approvals_block` (`498-569`)
8. `_validate_verification_block` (`656-779`)
9. `_validate_plan_block` (`213-330`)
10. `_validate_audit_last_action_ref_block` (`948-951`)
11. `_validate_task_action_ref_relations_block` (`953-956`)
12. `_validate_plan_dependency_relations_block` (`907-940`)
13. `_validate_verification_relations_block` (`1013-1055`)
14. `_validate_action_relations_block` (`958-1011`)

### Candidate First Slice

`_validate_memory_block` is the safest first slice.

Why it wins:

- zero dependence on later blocks
- no shared mutable collections are produced for later use
- no nested closure
- modest fan-out compared with plan, verification, audit, and action relations
- exact-order preservation is easy to characterize with one malformed memory
  payload and one mixed-validity note list

Why `plan_core` is not first:

- it writes four collections later blocks depend on
- it already mixes shape validation, ID collection, and cross-field plan status
- it is the largest primary block by fan-out

## Characterization Tests Required Before Slice 1

The preparatory commit must add exactly one new file:

- `tests/test_validate_error_ordering.py`

That file must pin exact `(code, message)` ordering for one malformed payload
per identified sub-block. The golden expectations should live inline in the
test module to stay within the whitelist and avoid new fixture files.

Minimum characterization matrix:

1. `plan_core` malformed payload
2. `execution_policy_core` malformed payload
3. `command_registry_core` malformed payload
4. `approvals_core` malformed payload
5. `actions_core` malformed payload
6. `batch_registry_core` malformed payload
7. `verification_core` malformed payload
8. `memory_core` malformed payload
9. `audit_core` malformed payload
10. `plan_dependency_relations` malformed payload
11. `audit_last_action_ref` malformed payload
12. `task_action_ref_relations` malformed payload
13. `action_relations` malformed payload
14. `verification_relations` malformed payload

Required properties of the characterization tests:

- pin exact list order, not just set membership
- pin exact messages, not just error codes
- isolate each block as much as possible without inventing new behavior
- for `plan_dependency_relations`, pin the exact DFS/traversal-driven append
  order, not only the presence of the cycle/error messages
- include at least one mixed payload where earlier block errors coexist with one
  relational-tail error, so slice commits cannot reorder aggregate output

## Per-Slice Protocol

Every future slice under an approved trigger must follow this exact protocol:

1. add or preserve characterization coverage before touching the block
2. extract one private helper in `core/validation.py` only
3. keep local names verbatim inside the extracted helper
4. keep error text verbatim
5. keep error codes verbatim
6. keep append order verbatim
7. keep duplicate validations as-is; do not consolidate
8. keep helper signature narrow; if it needs more than about `6` primitive or
   collection arguments, treat that as a halt signal
9. run:
   - AGENTS-equivalent suite
   - `python -m unittest tests.test_architecture -v`
   - `python -m unittest tests.test_validate -v`
   - `python -m unittest tests.test_validate_error_ordering -v`
10. if the slice passes those tests but still appears to have changed
    validation shape or append order outside the characterization coverage that
    is explicitly pinned, treat that as risk and halt instead of continuing
11. continue automatically at one slice per heartbeat round while all of these
    stay true:
    - the next slice is still within slices `4-11`
    - the active whitelist is unchanged
    - every required gate stays green
12. reintroduce a mandatory operator checkpoint before slice `12/14`
13. stop immediately for operator review on any halt condition

## Stop Conditions

Halt the future campaign immediately if any of the following becomes true:

- an extracted helper would require a new module
- an extracted helper would require a dataclass, context object, accumulator,
  protocol, or other new abstraction layer
- the helper boundary is not clean without renaming locals
- exact error order changes under characterization tests
- exact error text changes under characterization tests
- a slice passes the current tests but may still have changed validation shape
  or append order outside the characterization coverage that is explicitly
  pinned
- any slice needs more than about `6` primitive or collection inputs
- any gate turns red
- any slice needs to touch a file outside the approved whitelist
- fan-out inspection reveals hidden shared mutable state beyond the collections
  already mapped above

## Blockers Identified In Phase A

- `action_relations` is the most likely late-campaign halt point because it
  depends on outputs from five earlier blocks plus the legacy
  `required_action_approval_error(...)` fallback.
- `plan_dependency_relations` contains the only nested closure in the function;
  the helper boundary must preserve the current DFS traversal order exactly.
- `verification_relations` looks separable, but it depends on three earlier
  collections plus `state_check` from `verification_core`; characterization
  must pin both unknown-command and aggregate-status paths before extraction.

## Phase A Output

- identified sub-blocks: `14`
- candidate first slice: `_validate_memory_block`
- trigger need for continuation: `yes`

## Phase B Progress

- characterization-oracle commit content is now present in:
  - `tests/test_validate_error_ordering.py`
- characterization gate result:
  - `python -m unittest tests.test_validate_error_ordering -v` → `15` tests, `0` failures
  - `python -m unittest tests.test_validate -v` → `76` tests, `0` failures, `3` skips
  - `python -m unittest tests.test_architecture -v` → `51` tests, `0` failures
  - AGENTS-equivalent suite → `840` tests, `0` failures, `6` skips
- current autonomous window:
  - slices `10-11` were pre-approved for autonomous continuation at one slice
    per heartbeat round while gates stayed green
  - that window is now consumed cleanly at `11/14`
- current next autonomous slice:
  - `none; no autonomous continuation is open beyond slice 12`
- current checkpoint status:
  - the mandatory operator checkpoint before slice `12/14` was explicitly
    consumed on `2026-04-23`
  - `_validate_plan_dependency_relations_block` (`slice 12/14`) then landed
    cleanly under that approval with the characterization oracle and all gates
    green
  - the mandatory operator checkpoint before slice `13/14` was explicitly
    consumed on `2026-04-23`
  - `_validate_verification_relations_block` (`slice 13/14`) then landed
    cleanly under that approval with the characterization oracle and all gates
    green
- current next approved slice:
  - `none; reassessment is now required before any slice 14 work`
- next mandatory operator checkpoint:
  - before `_validate_action_relations_block` (`slice 14/14`)
- completed slice commits:
  - `refactor(validate): extract _validate_memory_block (slice 1/14)`
  - `refactor(validate): extract _validate_execution_policy_block (slice 2/14)`
  - `refactor(validate): extract _validate_batch_registry_block (slice 3/14)`
  - `refactor(validate): extract _validate_command_registry_block (slice 4/14)`
  - `refactor(validate): extract _validate_audit_block (slice 5/14)`
  - `refactor(validate): extract _validate_actions_block (slice 6/14)`
  - `refactor(validate): extract _validate_approvals_block (slice 7/14)`
  - `refactor(validate): extract _validate_verification_block (slice 8/14)`
  - `refactor(validate): extract _validate_plan_block (slice 9/14)`
  - `refactor(validate): extract _validate_audit_last_action_ref_block (slice 10/14)`
  - `refactor(validate): extract _validate_task_action_ref_relations_block (slice 11/14)`
  - `refactor(validate): extract _validate_plan_dependency_relations_block (slice 12/14)`
  - `refactor(validate): extract _validate_verification_relations_block (slice 13/14)`
