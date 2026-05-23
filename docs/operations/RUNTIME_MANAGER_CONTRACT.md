# Runtime Manager Contract

## Status

- status: phase-8 contract (supersedes phase-4)
- authority: subordinate to `FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_8.md`
- canonical store: `runtime.db` (schema v15, production)
- bridge: `observation_center.toml` remains the TOML import source; `managed_*` tables hold runtime-owned state
- autonomy policy: `core/runtime_manager_policy.py` encodes L0–L4 classification (pure, no I/O)
- MCP adapter: `adapters/runtime_manager_mcp_stdio/` enforces `max_autonomy_level` per token

## Mission

The runtime manager coordinates local Cerebro work without relying on chat or
Markdown interpretation. It determines what can run, what is blocked, what
evidence is required, which approval applies, and what must be replayed after a
decision.

## Non-Goals

The runtime manager is not:

- an agent framework;
- a free command executor;
- a replacement for Git;
- a target-project orchestrator;
- a second source of truth beside core-owned runtime state;
- an OpenTelemetry, MCP, Temporal, LangGraph, or Agents SDK adapter.

## Authority Model

Canonical authority must be singular.

Phase 4 authority order:

```text
AGENTS.md
-> active formal trigger
-> observation_center.toml   (TOML import source)
-> this contract
-> core-owned runtime.db APIs (production since schema v9)
-> Markdown projections
```

`core/` owns runtime-manager state. `observation_center.toml` is the TOML
import source; `runtime.db` is the live operational store. Markdown, TOML, and
JSON outputs are projections, config, fixtures, exports, or replay artifacts.

## Canonical Runtime States

Minimum state vocabulary:

- `idle`: no eligible open item;
- `planning`: a bounded item is being shaped;
- `blocked`: an item cannot proceed under current gates;
- `ready`: all non-execution gates are satisfied;
- `executing`: reserved for a later constrained executor phase;
- `validating`: checks are running or results are being recorded;
- `closed`: item completed, superseded, or archived;
- `needs_human`: human decision is required.

## Work Queue Contract

A work item must include:

- stable id;
- title;
- status;
- priority;
- kind;
- boundary;
- trigger;
- dependencies;
- dependency status;
- next action;
- done condition;
- halt condition;
- evidence requirements;
- approval requirements;
- owner/lease when work is active.

Single-flight is default. More than one executable item requires an explicit
later trigger.

## Scheduler Contract

The scheduler must be read-only in Phase 1.

It may:

- select the highest-priority eligible item;
- explain why no item is eligible;
- report missing dependencies, decisions, evidence, tools, approvals,
  validations, leases, stop conditions, triggers, or boundaries;
- return a stable no-op result.

It must not:

- execute actions;
- mutate target projects;
- grant permission;
- silently override blocked or waiting status;
- treat advisory reports as truth.

## Gate Diagnostics Contract

`reason` is a human summary. Machine callers must use `gate_diagnostics`,
projected by both `runtime-manager status` and `runtime-manager next`.

Each diagnostic must include:

- stable `code`;
- `subject_id`, either a work item id or `runtime-manager`;
- ordered `details`, using ids or `id:state` pairs where a gate has state;
- stable `severity`, currently `blocking` or `informational`;
- boolean `blocking`, which is the machine-readable readiness signal.

Current diagnostic codes:

- `stale_source`;
- `active_lease_expired` (informational; expired active leases do not block selection);
- `failed_replay_run` (informational; failed replay runs do not block selection);
- `active_lease_non_open`;
- `active_lease`;
- `active_stop_condition`;
- `waiting_status`;
- `blocked_status`;
- `dependencies_unsatisfied`;
- `missing_decisions`;
- `missing_evidence`;
- `missing_tools`;
- `missing_approvals`;
- `missing_validations`;
- `missing_trigger`;
- `missing_boundary`.

Informational diagnostics (`active_lease_expired`, `failed_replay_run`) appear
in `gate_diagnostics` even when selection succeeds. They surface stale records
that operators should clean up but do not prevent execution readiness. All other
diagnostics are blocking. Machine callers must not infer blocking status from
presence in `gate_diagnostics`; they must read `blocking`.

Diagnostics are core-produced read-model facts. They do not grant permission,
repair state, run validation, expire leases, execute commands, call tools,
choose adapters, or mutate target projects.

## Selection Audit Contract

`selection_audit` is the replayable scheduler explanation projected by both
`runtime-manager status` and `runtime-manager next`. It is projection-only and
must never append events during status/next reads.

The audit envelope must include:

- `policy_version`, currently `runtime-manager-selection-v1`;
- `sort_policy`, currently `priority_rank`, `source_index`, then `id`;
- `decision`, one of `selected`, `no_eligible`, or `global_blocked`;
- `selected_id`, or an empty string when no item is selected;
- `global_blockers`, for stale source, invalid active lease, or global stop;
- `eligible_ids`, already ordered by the sort policy;
- `entries`, one per imported observation.

Each audit entry must include:

- `observation_id`;
- `status`;
- `priority`;
- `source_index`;
- `eligible`;
- `sort_key`;
- `blockers`.

Audit blockers use stable `key=value` strings where details matter, for example
`missing_validations=val-1:expired` or `active_lease_other_item=item-2`. This
surface explains selection/no-op decisions; it does not select work outside the
core scheduler, create truth, approve execution, run commands, or mutate state.

## Decision Contract

Decision records must be versioned. A current decision must include:

- decision id;
- subject id;
- revision;
- status;
- effective time;
- expiry when applicable;
- human decision id when authority increases;
- evidence ids;
- supersession link when replaced.

No decision is permission unless the active trigger and approval policy say so.

## Approval Contract

An approval must include:

- explicit scope;
- action fingerprint;
- actor or authority reference;
- expiry;
- revocation path;
- audit event id.

Blanket approval is invalid for mutating execution. Reuse after scope drift is
invalid.

## Evidence Contract

Evidence must include:

- evidence id;
- kind;
- source;
- sanitized digest;
- retention class;
- accepted/rejected status;
- reason;
- linked decision or work item.

Raw secrets, raw sensitive output, and personal data must not be retained as
runtime evidence.

## Tool Manifest Contract

A registered tool or command must include:

- command id;
- argv prefix or callable id;
- path scope;
- side effect class;
- network/cloud flag;
- timeout;
- output budget;
- sensitive output policy;
- approval requirement;
- rollback expectation.

Phase 1 only designs and reads this surface. Execution is later.

## Event Contract

Runtime events must be append-only and replayable.

Minimum event vocabulary:

- `runtime_opened` — emitted once, on the very first sync, before any `queue_item_observed` events; payload includes `schema_version` and `reason: "first_sync"`;
- `queue_item_observed` — one per observation, emitted during each sync loop in observation order;
- `runtime_synced` — emitted after every sync; payload includes counts for all imported collection types (observations, decisions, evidence_records, tool_registry, approval_records, runtime_leases, replay_runs, validation_records, stop_conditions);
- `decision_opened`;
- `evidence_recorded`;
- `evidence_rejected`;
- `approval_checked`;
- `action_blocked`;
- `scheduler_noop`;
- `validation_recorded`;
- `decision_closed`;
- `runtime_closed`.

`read_status` and `read_next` are read-only and must never append events.

Each event must carry ids, timestamp, actor/system source, before/after digest
where relevant, and a reason.

## Rollback And Retry

Phase 1 does not add new execution rollback. It must still model rollback
requirements for future execution:

- reversible action id;
- preimage or rollback point;
- retry budget;
- failure class;
- validation required after rollback.

## Observability

Local event semantics come first. OpenTelemetry export is a later adapter.
Trace ids and replay digests must be stable before external export exists.

## Readiness Criteria

A work item is ready only when:

- status is eligible;
- dependencies are satisfied;
- boundary is authorized;
- trigger is active or consumed as required;
- required evidence is accepted;
- approvals are current;
- command/tool policy permits the proposed action;
- validation state is green;
- no stop condition is active.

Ready is not execution approval in Phase 1.

## Validation And Stop Conditions

Validation records are imported evidence of completed checks, not commands to
run. A required validation is satisfied only when a `validation_records` row
with the same id has `status = "green"` and an explicit, parseable
`fresh_until` timestamp that has not expired. Missing, `red`, `stale`, expired,
blank, or malformed freshness records block readiness.

Stop conditions are blocking records. A `stop_conditions` row with
`status = "active"` blocks readiness when its `subject_id` is the selected
observation id, `runtime-manager`, or `*`. `resolved` stop conditions remain
counted audit evidence but do not block readiness.

## Lease Expiry Contract

Runtime leases with `status = "active"` are subject to expiry classification in
the read model. A lease is **truly active** (blocking) when its `expires_at`
field is empty, malformed, or a future timestamp. A lease is **expired**
(non-blocking) when its `expires_at` is a parseable, past ISO-8601 timestamp.

Rules:

- An active lease with `expires_at` in the past does **not** block single-flight
  selection. Selection proceeds as if the lease does not exist.
- An active lease with an empty or malformed `expires_at` is treated
  **conservatively as still active** and continues to block selection.
- An active lease with a future `expires_at` is truly active and blocks selection.
- The `active_leases` counter reflects only truly-active (non-expired) leases.
- The `leases_expired` counter reflects leases that are `status = "active"` but
  whose `expires_at` has passed.
- Expired leases appear in `gate_diagnostics` under code `active_lease_expired`
  as an informational entry (not a blocking entry).
- Neither `status` nor `next` mutates, cleans up, or transitions expired leases.
  Expiry classification is read-model-only and produces no side effects.

## Replay Run Contract

Replay runs record post-hoc verification that an event or slice can be
replayed from its source. They are import-only evidence in Phase 1; no code
re-executes any command.

Rules:

- Replay run rows are imported from `observation_center.toml` and stored
  read-only in `runtime.db`.
- `replay_runs_total` counts all rows; `replay_runs_passed` and
  `replay_runs_failed` count rows by `status = "passed"` or `status = "failed"`.
- Failed replay runs appear in `gate_diagnostics` under code `failed_replay_run`
  as an informational entry; they do not block selection.
- `status` and `next` must never mutate, re-run, or close replay run rows.
- Schema guards verify the `replay_runs` table has all required columns, including
  `replay_id`, `source_event_id`, `status`, `replay_digest`, `checked_at`, and
  `reason`; missing columns raise `RuntimeManagerStoreError`.

## Phase 1 Deliverables

The first implementation slices should produce:

- `runtime.db` schema plan; done for the first local read model in
  `core.runtime_manager_store`;
- core-owned SQLite store; done for observation import, source digest, status,
  and next-item read selection;
- read-only status/next evaluator; done in core API and surfaced through
  `runtime-manager sync/status/next` CLI orchestration;
- projection/export back to docs; done for `status/next --out` as projection-only files
  that reject runtime paths, live authority files, live Markdown snapshots, and
  registered source paths;
- decision/evidence ledger tables behind core APIs; done for schema v2 import,
  required decision/evidence gating, and status/next counters;
- tool/approval policy tables behind core APIs; done for schema v3 import,
  required tool/approval gating, and status/next counters;
- event/replay/lease tables behind core APIs; done for append-only sync
  events, replay-run counters, active lease import, and single-flight lease
  gating;
- validation/stop-condition tables behind core APIs; done for schema v6 import,
  explicit `fresh_until` gating, green/red/stale/expired counters, schema guard
  tests, active stop-condition counters, global stop subjects, and status/next
  projection fields;
- structured per-gate diagnostics behind core APIs; done for stable
  `gate_diagnostics` projection in status/next JSON and text, including
  exact missing decision/evidence/tool/approval ids, validation `id:state`
  details, stale-source, lease, stop-condition, dependency, waiting/blocked,
  trigger, and boundary diagnostics;
- selection decision audit behind core APIs; done for stable
  `selection_audit` projection in status/next JSON and text, including policy
  version, sort policy, global blockers, ordered eligible ids, candidate
  entries, sort keys, and blockers without appending scheduler events;
- lease expiry/readiness semantics behind core APIs; done for read-model-only
  classification of expired vs truly-active leases, `leases_expired` counter,
  `active_lease_expired` diagnostic code, conservative treatment of empty and
  malformed `expires_at`, and non-mutation guarantee from `status`/`next`;
- replay diagnostics hardening behind core APIs; done for `replay_runs_passed`
  and `replay_runs_failed` per-status counters, `failed_replay_run` informational
  diagnostic surfacing failed replay runs without blocking selection, schema column
  guards for `runtime_leases.expires_at` and all `replay_runs` columns, and event
  isolation proof that `read_status`/`read_next` never append events;
- diagnostic severity contract behind core APIs; done for machine-readable
  `severity` and `blocking` fields in core diagnostics plus CLI JSON/text
  projections, with blocking vs informational assertions in tests;
- event vocabulary ordering and enrichment behind core APIs; done for
  `runtime_opened` emitted once before any `queue_item_observed` events on
  first sync, `runtime_synced` payload enriched with counts for all imported
  collection types, `read_status`/`read_next` proven event-isolated by
  dedicated test, `import json` added to the test module, and stale live-center
  tests migrated to synthetic helpers;
- tests for authority split, blocked states, stale evidence, approval absence,
  single-flight, replay, lease expiry, replay diagnostics, schema guards, and
  event isolation.

## Phase 2 Deliverables

The second implementation phase adds constrained command execution.
Phase 2 Slice 1 (schema v7) delivered:

- `command_registry` table behind core APIs; done for schema v7 import with
  all enforcement fields (`argv_prefix`, `path_scope`, `side_effect_class`,
  `network_allowed`, `timeout_seconds`, `output_budget_bytes`,
  `sensitive_output_policy`, `approval_requirement`, `rollback_class`, `status`);
  `DELETE FROM command_registry` on each sync; `commands_total`/`commands_enabled`
  counters in `RuntimeManagerStatus` and CLI JSON/text;
- `CommandPolicy` and `CommandEligibilityResult` frozen dataclasses;
- `check_command_eligibility()` read-only enforcement API; done for
  `command_not_registered`, `command_not_enabled`, `gate_blocked`,
  `no_eligible_observation`, and `approval_required` blocker codes; approval
  lookup verifies `subject_id=selected_observation_id`,
  `action_fingerprint=sha256:` over canonical JSON containing `command_id`,
  `argv_prefix`, and `path_scope`, plus `status="current"`; eligible result
  carries full policy and selected observation id;
- `runtime-manager check <command_id>` CLI subcommand; JSON and text rendering;
- `_require_schema()` guard for `command_registry` table and all 14 columns;
- tests covering all blocker paths, full policy field round-trip, approval
  presence/absence, schema guard, and counts (10 new tests; suite: 1897/0/6).

Phase 2 Slices 2+2.1+2.2 (subprocess executor + hardening) delivered:

- `CommandRunResult` frozen dataclass with all fields (`eligible`, `command_id`,
  `observation_id`, `argv`, `stdout`, `stderr`, `returncode`, `timed_out`,
  `duration_seconds`, `stdout_truncated`, `stderr_truncated`, `blockers`,
  `event_id`);
- `run_command(command_id, observation_center_path)` executor: calls
  `check_command_eligibility()` first (no bypass); resolves `path_scope` against
  `self.root` using `Path.relative_to` (not `str.startswith`) to reject
  sibling-prefix false positives; executes exactly `policy.argv_prefix` — no
  extra arguments accepted so the approval fingerprint covers the full execution
  unit; runs subprocess via `Popen` with manual timeout-and-kill; truncates
  stdout/stderr to `output_budget_bytes` with `[TRUNCATED]` marker; redacts both
  streams when `sensitive_output_policy = "redact"`; appends `command_run` event
  via `_append_event()` with `command_id`, `observation_id`, `argv`, `returncode`,
  `timed_out`, `duration_seconds`, `stdout_truncated`, `stderr_truncated`,
  `rollback_class` in payload; returns `CommandRunResult` with `event_id`;
- `runtime-manager run <command_id>` CLI subcommand with JSON
  and text renderers; `check` and `run` parsers registered in `main.py`;
- tests cover ineligible return without subprocess, stdout/stderr capture,
  nonzero returncode, output budget truncation, sensitive output redact,
  `command_run` event payload, path scope violation, no-bypass when DB missing,
  `argv` exactly equal to `argv_prefix`, sibling-prefix path scope rejection,
  command-id-only approval rejection, and stale command-policy approval rejection.
  AGENTS-equivalent gate: 1035/0/0/6.

Phase 2 Slice 3 (evidence artifact capture) delivered:

- `execution_evidence` table (schema v8): `evidence_id` (PK autoincrement),
  `command_id`, `observation_id`, `approval_id` (empty when no approval needed),
  `action_fingerprint`, `rollback_class`, `returncode`, `timed_out`,
  `duration_seconds`, `stdout_digest` (sha256 of raw output before
  truncation/redaction), `stderr_digest`, `stdout_truncated`, `stderr_truncated`,
  `output_redacted`, `event_id` (FK to events), `recorded_at`; migration in
  `_migrate_schema`; column guard in `_require_schema`;
- `ExecutionEvidence` frozen dataclass mirroring all 16 columns;
- `run_command()` now captures `stdout_digest`/`stderr_digest` from raw output
  before truncation or redaction, resolves `approval_id` from matching
  `approval_records` row when `approval_requirement != "none"`, inserts
  `execution_evidence` row after the `command_run` event, returns `evidence_id`
  in `CommandRunResult`; ineligible paths return `evidence_id=-1` with no row;
- `CommandRunResult` gains `evidence_id: int` field;
- CLI `runtime-manager run` JSON and text renderers expose `evidence_id`;
- 8 new `ExecutionEvidenceTests`: table existence, row captured per run, stdout
  digest matches raw output, digest captured before truncation, `output_redacted`
  flag set, `approval_id` recorded from matching approval record, ineligible run
  has no evidence row, schema guard rejects missing table;
- 4 new `RuntimeManagerRunEndToEndTests` in `test_cli.py`: eligible run reports
  positive `evidence_id`, unregistered command blocked with `evidence_id=-1`,
  missing approval blocked with `evidence_id=-1`, DB-missing case exits non-zero.
  Suite: 1922/0/6.

## Advisory-Only Enforcement Fields

`network_allowed` and `side_effect_class` in `command_registry` are declared
policy fields and are recorded in `execution_evidence`, but are **not enforced
at the OS level**:

- `network_allowed`: blocking network access at the OS level requires
  platform-specific sandboxing (e.g., `unshare` on Linux, not available on
  Windows). The registry value is advisory: it signals intent and is carried
  through to the evidence record for audit purposes.
- `side_effect_class`: indicates whether the command is `read-only`, `mutating`,
  or `destructive`. It gates human approval classes and is visible in audit but
  is not enforced by the subprocess executor itself.

Callers must not rely on these fields as security boundaries. They exist to
support human review and audit, not to prevent OS-level side effects.

## Phase 3 (evidence read API) delivered:

- `read_evidence(evidence_id: int) -> ExecutionEvidence | None`: returns the
  matching `execution_evidence` row as a frozen dataclass, or `None` if not
  found; raises `RuntimeManagerStoreError` if DB is missing;
- `list_evidence(observation_id: str | None = None, limit: int = 50) ->
  tuple[ExecutionEvidence, ...]`: returns evidence rows newest first; filters by
  `observation_id` when supplied; `limit=0` returns all rows; negative limits
  fail closed with `RuntimeManagerStoreError`;
- `execution_evidence_total: int` added to `RuntimeManagerStatus`;
- `_read_ledger_counts()` now queries `SELECT COUNT(*) FROM execution_evidence`;
- `runtime_synced` event payload gains `"execution_evidence"` count key;
- `_row_to_evidence()` module-level helper maps `sqlite3.Row` to `ExecutionEvidence`;
- CLI `runtime-manager evidence show <id>` and `runtime-manager evidence list
  [--observation-id ID] [--limit N]` subcommands added to `main.py` and
  `cli/commands/runtime_manager.py`; both support `--format text|json`;
- `_evidence_payload()`, `_render_evidence_text()`, `_render_evidence_list_text()`
  helpers added; `_status_payload()` and `_render_status_text()` updated to
  include `execution_evidence_total`;
- 11 new `EvidenceReadAPITests` in `test_runtime_manager_store.py`: unknown id
  returns None, row returned after run, all fields match result, empty list before
  any run, newest-first ordering, limit caps rows, limit=0 returns all, filter by
  observation_id, negative limit fails closed, `execution_evidence_total` in
  status, raises on missing DB (read_evidence and list_evidence);
- 5 new `RuntimeManagerEvidenceEndToEndTests` in `test_cli.py`: evidence show
  returns record for valid id (JSON), evidence show returns non-zero for unknown
  id, evidence list returns all runs ordered newest-first, evidence list limit
  option, evidence list negative limit exits non-zero. Suite: 1939/0/6.

## Phase 4 — Write Authority & managed_* Tables

Phase 4 establishes the runtime-owned write API. The canonical architecture
uses separate `managed_*` tables rather than a `source_kind` column on existing
TOML-imported tables.

### managed_* Table Architecture

`sync_observation_center()` clears and re-imports only TOML-imported tables:
`observations`, `decisions`, `evidence_records`, `tool_registry`,
`approval_records`, `runtime_leases`, `replay_runs`, `validation_records`,
`stop_conditions`. It never touches `managed_*` tables.

Runtime-owned tables (survive sync):
- `managed_leases` — write-API leases (UNIQUE partial index per active observation)
- `managed_stop_conditions` — write-API stop conditions
- `managed_validations` — write-API validation records (take precedence over TOML)
- `managed_approvals` — write-API approvals
- `rollback_registry` — rollback policies keyed to forward command IDs

`_read_ledger_counts()` merges managed state into the selection model:
- managed stop conditions add to `active_stop_subjects`
- managed validations overwrite the TOML gate state for the same `validation_id`
- managed approvals add to `current_approval_ids`

### Write-API Event Vocabulary (Phase 4 additions)

- `lease_acquired`, `lease_released`, `lease_heartbeat`, `lease_reclaimed`
- `stop_condition_raised`, `stop_condition_resolved`
- `validation_recorded`
- `rollback_registered`, `rollback_executed`
- `approval_recorded`, `approval_revoked`
- `command_stop_raised` (emitted by auto_stop_on_failure)

### Rollback Model

Rollback runs are stored in `execution_evidence` with
`command_id = "rollback:<original_command_id>"`. No separate `rollback_runs`
table is required. `list_rollback_runs(forward_command_id, limit)` queries
`execution_evidence WHERE command_id LIKE 'rollback:%'`.

### Phase 4 Slices Delivered

- **4.1** (schema v9): WAL mode; `managed_leases`; `acquire_lease`,
  `release_lease`, `heartbeat_lease`, `reclaim_expired_leases`; `AcquiredLease`.
- **4.2** (schema v10): `managed_stop_conditions`, `managed_validations`;
  `raise_stop_condition`, `resolve_stop_condition`, `record_validation`.
- **4.3** (schema v11): `rollback_registry`; `register_rollback`,
  `rollback_command(evidence_id)`; `RollbackPolicy`, `RollbackResult`.
- **4.4** (schema v12): `managed_approvals`; `record_approval`,
  `revoke_approval`; `ApprovalRecord`; UNION approval queries.
- **4.5 (closing sprint)**: small read APIs (`read_validation`, `list_approvals`,
  `check_rollback_eligibility`, `list_rollback_runs`); `auto_stop_on_failure` in
  `run_command()`; full CLI surface for all write-API operations.


---

## Phase 5 -- Observability & Local Policy (schema v13)

### Design Decisions

- **Traces are advisory, never authority.** Every trace carries
  `trace_is_not_permission=True`. Traces may not be used to grant
  permissions or approve execution.
- **Replay pass is not truth.** Every replay result carries
  `replay_pass_is_not_truth=True` and an explicit `authority` field.
  Replay results may not be used to trigger execution or approve commands.
- **No stdout/stderr in traces.** The `runtime_traces` table stores only
  sanitized metadata (operation, outcome, duration, subject_id). No execution
  output, no raw argv, no secrets.
- **Pure policy seam.** `core/runtime_manager_policy.py` is the first module
  extracted from the store for pure, I/O-free decision helpers. `decide_runtime_state`
  takes no external state and has no side effects.
- **Deterministic replay.** `replay_scenario()` accepts a JSON scenario with
  `trace_exists`, `metric_at_least`, `trace_forbids_text`, and `command_blocker`
  check types. Replay is deterministic: the same store state produces the same result.

### Schema v13 Changes

- `runtime_traces` table: `trace_id` (PK, `rt-<uuid>`), `operation` (TEXT),
  `subject_id` (TEXT), `status` (TEXT — outcome vocabulary: `acquired`,
  `released`, `read`, `recorded`, `raised`, `resolved`, `run`, `blocked`,
  `ineligible`, `failed`), `policy_version` (TEXT), `causation_id` (TEXT),
  `correlation_id` (TEXT), `input_digest` (TEXT, `sha256:<hex>`),
  `output_digest` (TEXT, `sha256:<hex>`), `started_at` (ISO-8601 UTC),
  `finished_at` (ISO-8601 UTC), `event_count` (INTEGER).
- `runtime_trace_events` table: `trace_event_id` (INTEGER PK AUTOINCREMENT),
  `trace_id` (TEXT FK → runtime_traces), `sequence` (INTEGER), `event_name`
  (TEXT), `subject_id` (TEXT), `payload_digest` (TEXT), `payload_json`
  (TEXT, sanitized), `created_at` (ISO-8601 UTC).
- Metrics are computed via inline queries in `read_metrics()`; no separate view.

### New Public APIs (Phase 5)

- `read_metrics()` -> `RuntimeManagerMetrics` -- local diagnostic counts.
- `list_traces(operation, subject_id, limit)` -> `tuple[RuntimeTrace, ...]`
- `read_trace(trace_id)` -> `RuntimeTrace | None`
- `export_trace(trace_id, format)` -> `str` -- formats: json, jsonl, otel-json.
- `replay_scenario(scenario_path)` -> `RuntimeReplayResult`

### CLI (Phase 5)

- `runtime-manager trace list [--operation OP] [--subject-id ID] [--limit N]`
- `runtime-manager trace show <trace_id>`
- `runtime-manager trace export <trace_id> [--format json|jsonl|otel-json]`
- `runtime-manager metrics`
- `runtime-manager replay --scenario <path>`

### Experiments & Fixtures (Phase 5)

- `experiments/runtime_manager_evals/` -- deterministic evaluators for
  trace/metrics/replay invariants (18 tests; advisory-only).
- `tests/fixtures/runtime_manager_scenarios/` -- 3 ready-to-use replay
  scenario JSON files.

### Reference Docs

- `RUNTIME_MANAGER_ADAPTER_CONTRACT.md` -- pre-commitment boundary for future adapters.
- `RUNTIME_MANAGER_MCP_THREAT_MODEL.md` -- pre-commitment threat model for MCP adapters.

### Phase 5 Closing Sprint

- schema v13, gate 2092/0/6 (after runtime_manager_evals tests added to full suite).
- `runtime-manager-phase-5` observation resolved and archived.

---

## Phase 6 -- Adapter Piloto Local (schema v13, no DDL change)

### Design Decisions

- **Local adapter boundary.** `adapters/runtime_manager_local_agent/` wraps
  every public store API. The adapter never writes to SQLite directly; all state
  transitions go through `RuntimeManagerStore` public methods.
- **Agent identity.** Every adapter call carries `AgentContext(agent_id,
  agent_role, session_id)`. No secrets in agent_id. Lease owner is derived as
  `f"adapter:{agent_id}:{session_id}"` to bind lease lifetime to session.
- **Rate limiting.** `LocalRateLimiter` enforces a sliding-window limit per
  `(agent_id, operation)`: read ops ≤ 60/min, mutate ops ≤ 10/min. Rate-limit
  blocks are counted in `AdapterMetrics.adapter_rate_limited`.
- **Lease enforcement.** Mutating operations (`run`, `record_approval`,
  `revoke_approval`, `raise_stop_condition`, `resolve_stop_condition`,
  `record_validation`) require the adapter to hold an active lease for the
  target observation. `release_lease` / `heartbeat_lease` verify owner matches.
- **Fails closed.** If lease is absent for a required mutation, the adapter
  returns an error without calling the store. If rate limit is exceeded, the
  adapter returns a block without calling the store.
- **Adapter metrics.** `AdapterMetrics` is an in-memory counter set:
  `adapter_calls_total`, `adapter_calls_blocked`, `adapter_rate_limited`,
  `adapter_mutations_total`, `adapter_permission_laundering_blocked`,
  `active_agent_leases` (queried from store on demand). Metrics are diagnostic;
  they are never used as execution permission.
- **No external SDK.** `adapters/` imports only `core.runtime_manager_store`,
  standard library, and `dataclasses`. No MCP, LangGraph, Temporal, OpenAI
  Agents SDK, Cloudflare Agents SDK.
- **No argv free-form.** Adapter only passes command IDs to the store; the
  store enforces argv policy from `command_registry`.

### New Adapter Layer (Phase 6)

- `adapters/runtime_manager_local_agent/agent_context.py` --
  `AgentContext(agent_id, agent_role, session_id)` frozen dataclass.
- `adapters/runtime_manager_local_agent/rate_limiter.py` --
  `LocalRateLimiter` with injectable clock for deterministic tests.
- `adapters/runtime_manager_local_agent/metrics.py` --
  `AdapterMetrics` frozen dataclass + `AdapterMetricsAccumulator` mutable counter.
- `adapters/runtime_manager_local_agent/adapter.py` --
  `LocalAgentAdapter` with full public interface (status, next, lease, check,
  approval, run, trace, metrics, replay).
- `adapters/runtime_manager_local_agent/fixtures/mcp_tool_call_shape.json` --
  reference JSON documenting expected MCP-compatible call shape (no real server).

### New Evals (Phase 6)

- `experiments/runtime_manager_evals/eval_adapter_safety.py` -- 9 safety
  invariant checks covering: no direct SQL, no argv acceptance, no replay-as-
  permission, lease enforcement, lease ownership, rate limit block, secret
  redaction, approval fingerprint, no external SDK import.

### Phase 6 Closing

- Schema unchanged (v13). Gate: ≥ 2120 passed.
- `runtime-manager-phase-6` observation resolved and archived.
- `RUNTIME_MANAGER_MCP_THREAT_MODEL.md` updated with tested mitigations.

---

## Phase 8 — Autonomy Calibration and Progressive Friction

### New Policy Module

- `core/runtime_manager_policy.py` — expanded with:
  - `ActionInput` dataclass: all inputs needed to classify an action.
  - `ActionClassification` dataclass: `autonomy_level`, `required_controls`,
    `blocked_reason`, `friction_budget`, `rationale`,
    `classification_is_not_permission=True`.
  - `classify_action(inp)` — pure function, no I/O.
  - `LEVEL_ORDER` tuple, `_level_rank()` helper.

### Schema v15 Changes (backward-compatible migrations only)

- `command_registry` gains four optional columns (default=safe):
  `risk_level_override`, `requires_human_decision`, `data_sensitivity`,
  `target_scope`.
- `adapter_tokens` gains `max_autonomy_level` (default: `L3_runtime_mutation`).
- `execution_evidence` gains `autonomy_level` (default: `''`).
- New table `policy_counters` (key/value counters for `mcp_level_blocked`, etc.).

### Store API additions

- `classify_runtime_action(command_id)` → `ActionClassification`.
- `CommandPolicy` gains the four new optional fields.
- `CommandEligibilityResult` gains `autonomy_level`, `required_controls`,
  `friction_budget`, `rationale`.
- `run_command` fails closed for L4 commands.

### CLI additions

- `runtime-manager policy classify <command_id> [--format text|json]`
- `runtime-manager policy explain-levels [--format text|json]`

### MCP enforcement

- `AdapterToken` gains `max_autonomy_level` (default: `L3_runtime_mutation`).
- Each MCP tool annotates its operation level.
- `runtime_run_command` classifies the command and checks level ≤ token ceiling.
- L4 is unconditionally blocked for all MCP operations.
- Token issuance accepts optional `max_autonomy_level`.

### Autonomy metrics

- `read_metrics()` derives `actions_by_level` (L0–L4 counts from evidence).
- `mcp_level_blocked` counter in `policy_counters`.

### Phase 8 Closing

- Schema v15. Gate: ≥ 2255 passed.
- `runtime-manager-phase-8-autonomy-calibration` observation resolved.
- `RUNTIME_MANAGER_AUTONOMY_LEVELS.md` published.

---

## Phase 9 — Multiagent Cross-Process Concurrency and Per-Operation Auth

### Per-Operation Token Re-Authentication

- `adapters/runtime_manager_mcp_stdio/auth.py` exposes `load_raw_token_from_env()`
  returning the raw token string without authenticating.
- `build_app` captures the raw env token; a `_require_current_token(scope, level)`
  closure re-authenticates via `store.authenticate_adapter_token(raw_env_token)` on
  **every tool call**.
- A revoked or expired token blocks the next tool call with `PermissionError`
  (`token_revoked_mid_session`) before any store access.
- Scopes and `max_autonomy_level` are read from the freshly-authenticated token, not
  a startup snapshot.

### Stable Lease Contention Diagnostic Codes

- `RuntimeManagerStoreError` gains an optional `code: str` attribute (default `""`).
- `acquire_lease` raises with `code="lease_contention"` on UNIQUE constraint violation.
- `release_lease` and `heartbeat_lease` trace `code="lease_owner_mismatch"` when a
  noop is triggered by an owner mismatch.
- Stable codes: `lease_contention`, `lease_owner_mismatch`, `lease_expired_reclaimed`,
  `token_revoked_mid_session`.

### Rate Limit Atomic Hardening

- `check_and_increment_rate_limit` uses `BEGIN IMMEDIATE` to claim the write lock
  before the increment+read, preventing any interleaved write from another process.

### Cross-Process Concurrency Tests

- `tests/test_runtime_manager_concurrency.py` uses `multiprocessing.Process` with a
  shared `multiprocessing.Barrier` for synchronized race starts and a
  `multiprocessing.Manager().list()` for result collection.
- Scenarios: 8-process lease race (≤ 1 success), wrong-owner lease ops, persistent
  rate limit under concurrency, token revoked mid-session, token expired mid-session,
  expired-lease reclaim leaves ≤ 1 active lease.

### MCP STDIO Hardening

- `_require_current_token(required_scope, operation_level)` is the single central
  gate for every tool.
- `runtime_run_command` uses the freshly-read `max_autonomy_level` for the command
  classification check.
- `record_approval` remains NOT exposed via MCP.
- L4 remains blocked unconditionally.
- HTTP is NOT introduced in this phase.

### Phase 9 Closing

- Schema unchanged (v15). Gate: ≥ 2353 passed.
- `runtime-manager-phase-9-concurrency-auth-readiness` observation resolved.
- `RUNTIME_MANAGER_MCP_THREAT_MODEL.md` updated: T16–T19 delivered; T20–T22 open.

---

## Phase 10 — Local-Only Hardening

Phase 10 is local-only. No HTTP, OAuth, TLS, SSE, Streamable HTTP, Temporal,
LangGraph, cloud transport, or SQLite ledger migration. Schema stays v15 unless
a genuine bug requires a change (must stop and report before any DDL).

### Local Stress Lab

- `experiments/runtime_manager_stress_lab/` — deterministic, short scenarios:
  lease race, rate limit concurrency, token revoke/expire mid-session,
  expired-lease reclaim, replay path guard, reads under load, DB busy contention.
- Every `StressResult` carries `stress_pass_is_not_permission=True` and
  `authority="advisory/local stress only"`.
- All scenarios run inside the normal pytest gate (no long sleeps).

### Integrity Check

- `RuntimeIntegrityReport` dataclass and `check_integrity()` method on the store.
- Checks: orphan trace events, incomplete old traces, expired-but-active leases,
  expired-but-active tokens, stale rate buckets, evidence without expected trace,
  policy-counter plausibility, not-permission markers on relevant rows.
- CLI: `runtime-manager integrity check [--format text|json]`.
- The integrity report is diagnostic only; it is not permission.

### Known Polish

- `_max_level()` dead code removed from `core/runtime_manager_policy.py`.
- `mcp_level_blocked` counter now incremented for ALL MCP tools blocked by the
  token ceiling, not just `runtime_run_command` (fix in `_require_current_token_factory`).
- Stable error codes standardized in CLI/MCP error outputs:
  `lease_contention`, `lease_owner_mismatch`, `token_revoked_mid_session`,
  `rate_limited`, `autonomy_level_blocked`, `replay_path_out_of_scope`.

### Architecture and Packaging

- `adapters.runtime_manager_mcp_stdio` and `adapters.runtime_manager_local_agent`
  added to `[tool.setuptools].packages` in `pyproject.toml`.
- Architecture tests: no HTTP/socket/listener in adapters; MCP STDIO does not
  write SQLite directly; adapters only call public store API; `record_approval`
  remains unexposed via MCP.

### Phase 10 Evals

- `experiments/runtime_manager_evals/eval_phase10_hardening.py` with evaluators:
  stress-pass not-permission, integrity-pass not-permission, metrics not authority,
  trace retains no token/stdout/stderr, replay path guard, L4 still blocked,
  token-revoked blocks next call, level-block counter covers all tools.

### Phase 10 Closing

- Schema unchanged (v15). Gate: 0 failures required.
- `runtime-manager-phase-10-local-hardening-stress` observation resolved and archived.
