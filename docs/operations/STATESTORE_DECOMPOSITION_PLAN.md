# StateStore Decomposition Plan

## Status

- Slice 1 (Contract Extraction) executada em 2026-04-22 e commitada em `441facf`.
- Slice 2 (Read-Model Extraction) executada em 2026-04-22 e commitada em `579c4a4`.
- Slice 3 (Session Lifecycle Extraction) executada em 2026-04-22 e commitada em `591d06a`.
- Slice 4 (Validation/Retention Seam) executada em 2026-04-22 e commitada em `3ab67c0`.
- Slice 5 (Coordination/Locking Extraction) executada em 2026-04-22 no working tree corrente; gate pós-slice confirmado verde.

### Slice 1 — Contract Extraction (Concluída 2026-04-22)

- `core/store_protocols.py` criado com `ActionStoreSurface` e `VerificationStoreSurface`
  como `@runtime_checkable Protocol` classes
- `core/action_runtime.py`: 13 funções anotadas com `ActionStoreSurface`
- `core/verification_runtime.py`: 5 funções anotadas com `VerificationStoreSurface`
- `tests/test_runtime_units.py`: 7 testes de contrato adicionados
- Gate pós-slice: 737 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Comportamento inalterado. Sem novo artefato canônico.

### Slice 1a — Encapsulation Cleanup (Concluída 2026-04-22)

- Três métodos usados por `verification_runtime` promovidos a API pública em
  `StateStore`:
  - `_runtime_lock` → `runtime_lock`
  - `_validate_state_locked` → `validate_state_locked`
  - `_read_owned_active_session` → `read_owned_active_session`
- `core/store_protocols.py` (`VerificationStoreSurface`) atualizado para expor
  apenas nomes públicos; Protocol deixa de documentar dependência em underscore
- `core/verification_runtime.py` (`execute_verification_cycle`) atualizado para
  chamar a API pública
- Chamadas internas dentro de `state_store.py` migradas consistentemente
- Gate pós-slice: 737 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Comportamento inalterado. Apenas rename + Protocol refinado.

### Slice 2 — Read-Model Extraction (Concluída 2026-04-22)

- `core/state_read_model_service.py` criado para encapsular o trio read-only:
  - `read_task_assessments`
  - `read_task_selection_consistency`
  - `read_task_work_profiles`
- `core/state_store.py` preserva a surface pública e agora delega esses três
  métodos para o serviço read-only, mantendo a facade como autoridade única
- `tests/test_state_read_model_service.py`: 5 testes diretos do serviço
- `tests/test_state_store.py`: 3 guards de passthrough da facade
- Gate pós-slice: 759 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Comportamento canônico preservado; nenhuma mudança de CLI, schema ou autoridade

### Slice 3 — Session Lifecycle Extraction (Concluída 2026-04-22)

- `core/state_session_artifacts_service.py` criado para encapsular o cluster de
  artefatos/autoridade de sessão:
  - claim/live-proof storage e addressing
  - owner-binding e hash helpers
  - leitura/validação de claim, live proof e `session.local.json`
  - snapshots/restore de claim e live proof
- `core/state_store.py` preserva a surface existente e agora delega esse
  cluster para o serviço via wrappers tardios, mantendo no facade a ordenação
  de revisão, `session.refresh.pending.json`, recovery transacional e locking
- `tests/test_state_session_artifacts_service.py`: 4 testes diretos do serviço
- `tests/test_state_store.py`: 3 guards de delegação da facade
- `tests/test_windows_credential_store.py`: bateria direta convertida para mocks
  de `Advapi32`, removendo dependência do host real e mantendo cobertura do
  módulo WinCred
- `tests/test_architecture.py`: allowlist ajustada para permitir serialização
  JSON nesse helper específico sem reabrir autoridade sobre `state.json`
- Gate pós-slice: 770 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Debate de boundary: a posição vencedora manteve `open_session`,
  `close_session`, `discard_session`, pending refresh e locking em `StateStore`,
  extraindo apenas a camada de artefatos/autoridade para evitar cruzar cedo com
  o seam de validation/retention

### Slice 4 — Validation/Retention Seam (Retenção extraída; concluída 2026-04-22)

- `core/state_retention_service.py` criado para encapsular o cluster de
  retenção que já era coeso e subordinate à facade:
  - policy description
  - retention report/event-log planning
  - artifact-group planning and unknown-surface blocking
  - pending retention journal loading/finalization
  - retention manifest/result builders
- `core/state_store.py` preserva a surface pública existente e agora delega os
  helpers de retenção para o serviço, mantendo no facade:
  - `validate_state()` / `validate_state_locked()`
  - `runtime_lock()`
  - `load_state()` / `save_state()`
  - pending session refresh recovery
  - trace ordering and revision authority
- `tests/test_state_retention_service.py`: 2 testes diretos do serviço
- `tests/test_validate.py`: 3 guards novos para stale `expected_revision` e
  unknown artifact surfaces
- `tests/test_architecture.py`: allowlist ajustada para permitir serialização
  JSON nesse helper específico sem reabrir autoridade sobre `state.json`
- Gate pós-slice: 775 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Debate de boundary: a posição vencedora extraiu apenas a metade de retenção do
  seam. `validate_state*` permanece em `StateStore` até existir um motor
  estateless que compute erros sem carregar junto recovery de sessão e
  persistência de `last_validation`

### Slice 5 — Coordination/Locking Extraction (Concluída 2026-04-22)

- `core/state_runtime_lock_service.py` criado para encapsular o cluster de
  coordenação de lock que já estava coeso e subordinate à facade:
  - `runtime_lock()` reentrante
  - lifecycle do arquivo `runtime.lock`
  - stale-lock detection/recovery
  - current-process lock ownership tracking
  - timeout/poll/release retry choreography
- `core/state_store.py` preserva a surface pública e agora delega esse cluster
  para o serviço, mantendo no facade:
  - verify/apply orchestration
  - validation authority
  - session recovery
  - revision ordering and canonical persistence
- `tests/test_state_runtime_lock_service.py`: 2 testes diretos do serviço
- `tests/test_state_store.py`: 1 guard novo de serialização entre duas
  instâncias de `StateStore` após a extração
- Gate pós-slice: 778 testes, 0 falhas, 6 skips; 51 testes arquiteturais, 0 falhas
- Debate de boundary: a posição vencedora extraiu apenas o cluster
  `runtime_lock`/stale-lock recovery. Guards de verify/apply continuam em
  `StateStore` porque ainda cruzam autoridade de validação, sessão e revisão

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
