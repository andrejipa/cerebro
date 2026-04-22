# StateStore Decomposition Plan

## Status

- Slice 1 (Contract Extraction) executada em 2026-04-22 e commitada em `441facf`.
- Slices 2–5 planejadas; aguardam autorização incremental.

### Slice 1 — Contract Extraction (Concluída 2026-04-22)

- `core/store_protocols.py` criado com `ActionStoreSurface` e `VerificationStoreSurface`
  como `@runtime_checkable Protocol` classes
- `core/action_runtime.py`: 13 funções anotadas com `ActionStoreSurface`
- `core/verification_runtime.py`: 5 funções anotadas com `VerificationStoreSurface`
- `tests/test_runtime_units.py`: 7 testes de contrato adicionados
- Gate pós-slice: 737 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Comportamento inalterado. Sem novo artefato canônico.

## Why This Exists

`StateStore` is still the clearest architectural hotspot outside the now-clean
corrective queue. The current evidence remains consistent:

- it concentrates persistence, session lifecycle, validation, retention, read
  models, runtime coordination, audit-side helpers, and recovery paths
- `action_runtime` and `verification_runtime` still depend on a broad,
  duck-typed `StateStore` surface instead of an explicit narrow contract
- the remaining accepted residuals still touch boundaries that are easier to
  reason about when `StateStore` responsibilities are explicit

This document records a future-safe decomposition map without mutating runtime
authority today.

## Inputs Used

- `docs/operations/WEAKNESS_REPORT.md`
- `docs/operations/residuals.toml`
- live snapshot in `docs/operations/OPPORTUNITY_MAP.md`
- live snapshot in `docs/operations/SYSTEM_STATE.md`
- current method surface in `core/state_store.py`

## Decomposition Goals

- Reduce responsibility concentration behind a thin facade.
- Make runtime contracts explicit before any internal extraction.
- Preserve one canonical authority over `state.json`.
- Preserve fail-closed behavior and existing recovery semantics.
- Avoid introducing a second source of truth or a new canonical artifact.

## Non-Goals

- No runtime mutation.
- No service extraction in this slice.
- No new schema fields.
- No new CLI surface.
- No change to approval, session policy, `analyze`, `validate`, or the
  canonical snapshot contract.

## Current Responsibility Clusters

### 1. Canonical Persistence And Revision Control

Current surface:

- `StateStore.read_snapshot()`
- `StateStore.read_snapshot_and_runtime()`
- `StateStore.read_sources()`
- `StateStore.read_agent_runtime()`
- `StateStore.save_state()`

Why it is a seam:

- one cluster owns the canonical read/write path
- revision monotonicity and snapshot/runtime coherence live here already
- this is the boundary that must remain the single source of truth even after
  any future split

Future extracted shape:

- `CanonicalStateRepository`

What it may own in a future authorized slice:

- load/save of canonical state
- revision guards
- stable read models that are direct projections of canonical state

What it must not own:

- session authority side effects
- verification execution
- retention policy decisions

### 2. Session Authority And Lifecycle

Current surface:

- `StateStore.open_session()`
- `StateStore.close_session()`
- recovery paths around local session files, external claims/live proofs, and
  pending refresh handling

Why it is a seam:

- session ownership and crash recovery form a coherent failure domain
- most of the historically delicate recovery logic clusters here
- the accepted ownership residual is easier to isolate when the lifecycle
  surface is explicit

Future extracted shape:

- `SessionLifecycleService`

What it may own in a future authorized slice:

- open/close/discard lifecycle
- claim/live-proof coordination
- pending refresh journal handling
- session ownership reads used by runtime gates

What it must not own:

- canonical persistence authority beyond the facade-controlled commit points
- direct CLI orchestration

### 3. Validation And Retention Cycle

Current surface:

- `StateStore.validate_state()`
- `StateStore.apply_retention()`

Why it is a seam:

- validation and retention already act like a coordinated transaction boundary
- they mix structural checks, retry logic, protected-surface rules, and
  retention side effects
- this cluster is adjacent to accepted residuals and should become easier to
  reason about independently from session lifecycle

Future extracted shape:

- `ValidationRetentionService`

What it may own in a future authorized slice:

- validation cycle orchestration
- retention apply/report internals
- retry-on-change rules

What it must not own:

- command execution
- alternate persistence stores

### 4. Read Models And Operational Queries

Current surface:

- `StateStore.read_task_assessments()`
- snapshot/runtime/source reads reused by CLI and exported views

Why it is a seam:

- the read-model workload is broad but conceptually different from mutation and
  recovery
- recent cost and drift fixes already showed value in separating coherent read
  boundaries from mutation boundaries
- this is the lowest-risk candidate after protocol extraction because it can
  stay facade-backed and read-only

Future extracted shape:

- `StateReadModelService`

What it may own in a future authorized slice:

- task assessments
- stable derived read helpers
- coherence-preserving combined reads already surfaced by the facade

What it must not own:

- mutation side effects
- new cached authority

### 5. Runtime Coordination, Audit Glue, And Locking

Current surface:

- `StateStore.record_parallel_approach_consolidation()`
- `StateStore._runtime_lock()`
- cross-cutting helpers that coordinate timing, locking, and durable handoff

Why it is a seam:

- coordination primitives are operationally important but conceptually distinct
  from canonical data storage
- lock/recovery behavior is a recurring hardening hotspot
- this cluster should be narrowed last, after the higher-level contracts are
  explicit

Future extracted shape:

- `RuntimeCoordinationService`

What it may own in a future authorized slice:

- runtime lock plumbing
- durable coordination helpers
- narrow audit-side coordination primitives

What it must not own:

- business rules for validation, approval, or session policy

## First Future Slice Order

If a Formal Resume Trigger is ever accepted, the recommended order is:

1. Contract extraction before movement.
   - define explicit narrow protocols consumed by `action_runtime` and
     `verification_runtime`
   - goal: remove broad duck-typing before moving code
2. Read-model extraction behind the facade.
   - lowest-risk internal seam
   - preserve one canonical load path
3. Session lifecycle extraction.
   - isolate the crash/recovery domain with the highest historical density
4. Validation/retention extraction.
   - split transaction-like validation/retention concerns from session logic
5. Coordination/locking extraction.
   - narrow the remaining cross-cutting operational primitives last

This order is intentionally conservative: contract clarity first, risky
recovery paths second, and low-level coordination last.

## Required Guardrails For Any Future Resume

- Keep one facade as the only canonical authority entrypoint until the end of
  the migration.
- Keep `state.json` as the only source of canonical state.
- Do not create a service-specific persistence file, cache, or journal unless
  it already exists today and stays subordinate to the same authority rules.
- Preserve fail-closed behavior on session, validation, approval, and rollback
  boundaries.
- Preserve the current architecture rule that only the canonical layer owns
  runtime JSON serialization.
- Do not let any extracted service become a hidden second authority about
  state, ownership, or validation truth.

## Resume Trigger Preconditions

This plan should remain dormant unless all of these are true:

- a Formal Resume Trigger is explicitly documented and authorized
- the reason is a repeated unmet operational cost, recovery risk, or
  maintenance drag tied to `StateStore` concentration rather than curiosity
- the proposed slice fits one minimum safe increment at a time
- the slice can be validated end to end with proportional regression coverage
- the live snapshots are updated before and after the slice so the migration
  does not create documentary split-brain

## Proof Obligations For A Future Authorized Slice

Any future authorized extraction should prove at least:

- equivalent full gate green
- `python -m unittest tests.test_architecture -v` green
- no new canonical artifact
- no second source of truth
- no consumer reads stale or partial state through a side channel
- existing crash/recovery tests remain green for the touched seam

## Stop Conditions

Stop and escalate to explicit architecture review if a candidate slice:

- needs a new canonical artifact
- needs `core/validation.py` or schema changes just to make the extraction
  possible
- changes public CLI behavior as a prerequisite
- requires two seams to move at once to stay coherent
- cannot preserve the facade as the single authority boundary during migration

## Immediate Outcome Of This Planning Slice

- The hotspot is now mapped into concrete seams instead of a vague "split
  StateStore" recommendation.
- The preferred migration order is explicit.
- The resume-trigger preconditions are explicit.
- No runtime authority changed.
