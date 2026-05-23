# Cost Topology

This document records the current cost topology of the Cerebro runtime as implemented today.

It is not a wish list.
It describes where cost actually comes from, what has already been changed, what remains acceptable, and which optimizations are explicitly rejected for now.

## Current Topology

### Hotspot 1 - Consolidation read model

- Path: `status-export` -> `read_parallel_approach_consolidation_view()` -> `_read_parallel_approach_consolidation_histories()`
- Cost origin: reverse scan of `events.jsonl`, per-line filtering, consolidation parsing, chain validation
- Frequency: medium
- Impact: medium
- Growth trend: linear with event-log size
- Criticality: diagnostic
- Cost type:
  - inevitable: validation of consolidation lineage before publishing a head
  - avoidable: rescanning the same log more than once per export; parsing unrelated `runtime_event` lines as JSON

Accepted mitigations:

- shared read-only consolidation view for `recent consolidations` + `requested heads`
- raw-line prefilter before `json.loads` for obvious non-consolidation events

Rejected mitigations:

- persistent consolidation index
- cross-process cache
- background compaction or repair job

Reason for rejection: the structural cost is higher than the current need, and it would create a second source of truth or invalidation burden.

### Hotspot 2 - State load and validation on read-only surfaces

- Path: `read_snapshot()`, `read_agent_runtime()`, `read_task_assessments()`
- Cost origin: `load_state()`, `canonicalize_state_data()`, `validate_state_data()`, `deepcopy`
- Frequency: medium
- Impact: low to medium
- Growth trend: roughly linear with state size
- Criticality: core
- Cost type:
  - inevitable: canonicalization and validation before exposing runtime-derived state
  - avoidable: repeated state reads within one command when equivalent data is already in memory

Current status:

- observed in profiling, but not currently the dominant bottleneck
- partially reduced on `status-export` by reusing `agent_runtime + recent_events` already loaded in-process when deriving `task_assessments`
- repeated state hydration still exists between `read_snapshot()` and `read_agent_runtime()`, but the previous third reload via `read_task_assessments()` was removed
- `apply` single-file now also reuses one combined `snapshot + runtime` read before the first mutation, removing the extra `read_sources()` + `read_agent_runtime()` preflight reloads from that path

Accepted mitigation:

- derive `task_assessments` from already loaded runtime and recent events inside `status-export`
- read snapshot plus runtime from a single canonical state load on the `status-export` path
- read snapshot plus runtime from a single canonical state load on the `apply` single-file preflight path

Rejected mitigations:

- persistent state cache across commands
- extension-local snapshot cache
- widening `StateSnapshot` into a second runtime carrier

Reason for rejection now: the remaining measured cost is lower than consolidation-log scanning, and the next steps would increase coupling between read surfaces for low gain.

### Hotspot 5 - Retention report and retention apply

- Path: `validate --retention-report/--retention-apply` -> `validate_state()` -> `inspect_retention()` / `apply_retention()`
- Cost origin: one additional canonical state reload plus a full `events.jsonl` scan to assemble the retention report and archive metadata
- Frequency: low
- Impact: low to medium
- Growth trend: linear with event-log size
- Criticality: operational diagnostics and cleanup
- Cost type:
  - inevitable: retention needs the canonical cleanup view before reporting or archiving
  - avoidable: the current command still re-enters retention helpers after `validate_state()` and reconstructs report data from the full append-only log

Current status:

- confirmed by proactive sweep on April 18, 2026
- functionally healthy; the issue is undocumented cost, not correctness drift
- no dedicated benchmark has been recorded yet

Accepted mitigation:

- document the extra reload plus full-log scan explicitly so future work does not treat the cost as surprising

Rejected mitigations for now:

- caching retention candidates across commands
- persistent retention index
- partial log mirror for archive metadata

Reason for rejection now: frequency is still low, the path is maintenance-only, and stronger structure would add invalidation and second-source-of-truth risk before there is measured pressure.

### Hotspot 6 - `doctor` suite rerun

- Path: `doctor` -> `_suite_check()` -> `python -m unittest discover -s tests -v`
- Cost origin: full repository test-suite execution on every explicit `doctor` invocation
- Frequency: low
- Impact: high
- Growth trend: linear with total suite size
- Criticality: operational diagnostics
- Cost type:
  - inevitable: the command contract explicitly verifies repository test health, not just project-local runtime state
  - avoidable: only if the contract changes to accept stale suite status or a weaker diagnostic mode

Current status:

- confirmed by the April 18, 2026 audit pass
- functionally healthy; the issue is documented cost, not correctness drift
- latest revalidation measured `doctor` at the same order of magnitude as the full suite gate (`657` tests, about `35s`)

Accepted mitigation:

- document this path as an intentionally heavy, low-frequency diagnostic so operators do not treat `doctor` as a cheap probe

Rejected mitigations for now:

- caching or reusing a previous suite result
- silently downgrading the default check to a partial or skipped suite run
- adding a second persisted suite-status source of truth

Reason for rejection now: the current command contract is fail-closed and explicit about checking repository health; weakening it would trade correctness for speed and introduce stale-status risk during freeze.

### Hotspot 7 - `verify` live-project guard

- Path: `run_verify()` -> `run_verification_commands()` -> live-project manifest capture/diff/restore
- Cost origin: second disposable clone for pristine restore plus one manifest walk of the live project before and after each verification command
- Frequency: low
- Impact: medium
- Growth trend: roughly linear with live project tree size and command count
- Criticality: correctness and isolation
- Cost type:
  - inevitable: the guard must detect and revert live-project mutation outside the sandbox to keep `verify` fail-closed
  - avoidable: rescanning paths owned only by verification artifacts or broadening the guard to paths that the runtime already knows it owns

Current status:

- confirmed by the post-hardening audit on April 19, 2026
- functionally required; the guard closed a real escape where a verification command could mutate the live workspace through an absolute path and still report green
- no dedicated microbenchmark is recorded yet, but the added work is intentionally confined to the low-frequency `verify` path

Accepted mitigation:

- ignore runtime-owned verification artifact paths during the live-project diff
- keep the restore snapshot separate from the execution sandbox so a command cannot poison the rollback source

Rejected mitigations for now:

- trusting the disposable sandbox clone alone
- weakening the guard to best-effort logging without restoring the live project
- persisting a second long-lived manifest source of truth

Reason for rejection now: the original bug was correctness-critical, and the accepted guard keeps the new cost bounded to the `verify` path without introducing persistent cache invalidation.

### Hotspot 3 - Task assessment derivation

- Path: `derive_task_assessments()`
- Cost origin: scoring, evidence aggregation, recent-event interpretation
- Frequency: medium
- Impact: low to medium
- Growth trend: linear with tasks and recent-event window
- Criticality: core
- Cost type:
  - inevitable: assessment needs current runtime state plus recent evidence
  - avoidable: reloading recent events or runtime state redundantly inside one command

Current status:

- already pre-aggregated in the decision runtime
- no further optimization accepted in this phase

Reason for rejection now: not a measured hotspot after the current export optimizations.

### Hotspot 4 - Memory notes and recent workflow summaries

- Path: status panel rendering of recent memory notes
- Cost origin: sorting and formatting a capped slice
- Frequency: low
- Impact: low
- Growth trend: bounded
- Criticality: auxiliary

Decision: explicitly rejected for optimization now.

Reason: low frequency, low impact, bounded cost.

## Scale Projections

### Event log at 10x

- Consolidation reads remain the first diagnostic hotspot.
- Current mitigations keep the path linear, but still tied to log length.
- Risk level: medium, acceptable for current scale.

### Event log at 100x

- Full-history consolidation reads become an explicit future risk.
- If this path becomes user-facing slow under real workloads, the next acceptable move is a stronger read-only projection or summary file that remains fully derivable from the append-only log.
- Persistent indexing is still not automatically justified; it would require new measurement.

### Long-lived state history

- Canonical state validation is expected and should not be optimized away casually.
- The risk is not correctness cost alone, but repeated validation work across multiple read surfaces in the same command.
- Current risk level: low to medium.

## Benchmarks Recorded

- `status-export` with `20_000` noise events and `5` stale replays:
  - `229.893ms/iter` before batched head lookup
  - `74.671ms/iter` after batched head lookup
  - `36.274ms/iter` after shared consolidation view
  - `11.643ms/iter` after raw-line prefilter for non-consolidation events
- `task_assessments` derivation in a synthetic runtime with `64` tasks and `20` recent events:
  - `2.520ms/iter` through `StateStore.read_task_assessments()`
  - `0.259ms/iter` when reusing already loaded `agent_runtime + recent_events`
- `status-export` profile in the same synthetic large-log scenario:
  - `load_state()` invoked `3` times before local task-assessment reuse
  - `load_state()` invoked `2` times after the change
- snapshot/runtime read on the same synthetic runtime with `64` tasks:
  - `4.162ms/iter` through `read_snapshot()` + `read_agent_runtime()`
  - `2.457ms/iter` through `read_snapshot_and_runtime()`
- equivalent read-only export flow under `20_000` noise events and replayed consolidations:
  - `19.645ms/iter` before the combined snapshot/runtime read
  - `17.353ms/iter` after the combined snapshot/runtime read
- `apply` single-file on a synthetic runtime with `1` registered source and `1` ready task:
  - `load_state()` invoked `6` times before the combined snapshot/runtime read
  - `load_state()` invoked `4` times after the change
  - pre-mutation `load_state()` count at the entry to `apply_action()` fell from `4` to `2`
  - `20.697ms/iter` before the change
  - `18.408ms/iter` after the change
- `verify` happy path on a synthetic runtime with `1` registered source and `1` read-only command:
  - `load_state()` invoked `4` times before the core transaction helper
  - `load_state()` invoked `3` times after the change
  - pre-command `load_state()` count at the entry to `run_verification_commands()` fell from `2` to `1`
  - `155.864ms/iter` before the change
  - `154.274ms/iter` after the change
- session-refresh crash-hardening on a synthetic runtime with `1` registered source and `1` active session:
  - `validate_state()` at `3.354ms/iter`
  - `update_agent_plan()` through `_save_state_with_refreshed_session()` at `13.150ms/iter`
  - verdict: cost maintained — no measurable hotspot shift after adding the local pending-session journal
- verify artifact-persistence hardening on a synthetic runtime with `1` registered source and `1` read-only command:
  - `run_verify()` at `136.883ms/iter`
  - verdict: cost maintained — no measurable new hotspot; the new branch only executes on artifact-persistence failure and the success path keeps the same I/O shape
- verify live-project guard on the current post-hardening path:
  - no dedicated microbenchmark recorded yet
  - expected cost shape: one extra disposable clone plus live-project manifest scan/diff per verification command
  - verdict: measurable but acceptable on the low-frequency `verify` path; keep documented until fresh measurement justifies deeper optimization

## Optimization Rules In Force

- Optimize only when frequency and impact justify it.
- Prefer elimination of redundant work before introducing new structure.
- Prefer local batching or reject-only prefilters before caches or indexes.
- Never weaken canonical validation, stale-replay defense, or read-only fail-closed behavior for speed.
- When a derived read surface fails, do not publish stronger interpretations than the remaining evidence supports.
- If there is doubt, do not optimize yet; measure again first.

## Residual Risks

- Consolidation read cost still scales with the append-only event log.
- A future 100x growth in event volume could justify a stronger derived read-only projection, but not without fresh measurement.
- State read duplication exists but is not currently severe enough to justify extra coupling.
- The `verify` live-project guard adds tree-walk and clone cost proportional to workspace size; this is currently accepted because it closes a correctness-critical escape and remains outside hot interactive paths.
