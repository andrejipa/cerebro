# Opportunity Map

## Current Snapshot — 2026-04-19

- Suite gate confirmed green: `696` tests, `0` failures, `6` skips via `python -m unittest discover -s tests -v`
- Architecture gate confirmed green: `51` tests, `0` failures via `python -m unittest tests.test_architecture -v`
- Current posture: deliberate freeze remains active for growth, but corrective hardening is active and authorized
- Current executable queue:
  - `WEAK-HIGH-003 — remover o sentinel sintético check-state do contrato de verification`
  - `WEAK-CRIT-001 — mover approval de overwrite destrutivo para policy por efeito`
- Current next item: `WEAK-HIGH-003 — check-state sintético`
- Current weakness posture:
  - `CRÍTICO`: `1` open, `0` Group 6
  - `ALTO`: `1` open, `0` Group 6
- Latest hardening result:
  - `DÉBITO 3` (`verify` host-trusting) foi fechado com regressão explícita para leak de env, leak por segmento de `PATH`, helper chain mínima por comando resolvido e preservação de `C:` legítimo
  - o drift entre `WEAKNESS_REPORT.md`, `SYSTEM_STATE.md` e `OPPORTUNITY_MAP.md` agora fica ancorado neste snapshot atual, que substitui a antiga trilha documenter-only descrita nas seções históricas abaixo

Bootstrap document created on 2026-04-16 for the autonomous loop.

## Entry Gate

- Suite gate confirmed green: `550` tests, `0` failures, `6` skips via `python -m unittest discover -s tests -v`
- `docs/operations/SYSTEM_STATE.md` did not exist before this bootstrap
- `docs/operations/OPPORTUNITY_MAP.md` did not exist before this bootstrap
- `.cerebro/state.json` is absent in this workspace, so the current loop is documentary/bootstrap-oriented rather than an active runtime continuity round

## Current Posture

- Freeze remains active: corrective maintenance and factual documentation are allowed; growth work stays blocked without a formal resume trigger
- No new mutating core slice is eligible right now under the current freeze posture
- The executable queue in this map is therefore limited to documentary reconciliation and formal closure work
- `WEAKNESS_REPORT.md` now carries one confirmed `CRÍTICO`, three confirmed `ALTO`, and multiple `MÉDIO`, but every mutating fix still requires `core/`, `cli/`, and `tests/` changes that are outside this documenter-only loop

## Executable Queue

### DOC-001 — Reconcile Documentary Drift

- Status: `done`
- Priority: `HIGH`
- Level: `1`
- Why it exists:
  - `BUG_REPORT.md` says the remaining corrective backlog is "dois residuos explicitos" but does not enumerate both, leaving residual intake ambiguous
  - `PHASE_CLOSURE.md` still closes the prior phase at `534` tests even though the current suite is `548`
  - `AGENTS.md` still shows a Unix-style `tail -5` snippet even though this repo runs under PowerShell
- Scope:
  - `docs/operations/BUG_REPORT.md`
  - `docs/operations/PHASE_CLOSURE.md`
  - `AGENTS.md`
- Done when:
  - residuals are explicit instead of implicit
  - the current documentary closure matches the post-Round-10 test count and status
  - the preflight suite command is portable to the declared shell
- Verify:
  - `python -m unittest discover -s tests -v`
- Result:
  - `BUG_REPORT.md` now names the accepted residuals explicitly
  - `PHASE_CLOSURE.md` now reflects the post-Round-10 `548`-test closure state
  - `AGENTS.md` now uses a PowerShell-portable preflight snippet

### DOC-002 — Proof Of Stop And Formal Re-Closure

- Status: `done`
- Priority: `MEDIUM`
- Level: `1`
- Depends on: `DOC-001`
- Why it exists:
  - after documentary reconciliation, the loop still needs an explicit stop-proof pass and refreshed closure record for the current frozen state
- Scope:
  - `docs/operations/PHASE_CLOSURE.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
- Done when:
  - the queue distinguishes executable items from blocked items cleanly
  - accepted residuals are named explicitly
  - the phase closure reflects the current green suite and current blocked items
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - `P1`: no new eligible performance hotspot
  - `P2`: no new bypass surface beyond accepted residuals and freeze-blocked items
  - `P3`: no new recovery/failure scenario outside the accepted residual set
  - one subagent reported a red suite locally, but the focal rerun of `tests.test_state_store.StateStoreTests.test_open_session_restores_registry_and_external_artifacts_when_session_file_write_fails` passed in the main workspace
  - `P5` gap closed: `PHASE_CLOSURE.md` now sits inside the automated documentary proof perimeter through explicit guards in `tests/test_doc_governance.py` and `tests/test_architecture.py`
  - formal re-closure is no longer blocked by the proof-perimeter gap

### DOC-003 — Reconcile Helper Alias Drift

- Status: `done`
- Priority: `LOW`
- Level: `1`
- Depends on: `DOC-002`
- Why it exists:
  - the proof-of-stop `P4` pass found that `AGENTS.md` used helper label `architect` as if it were a canonical role, which drifted from the seven-role canonical set
  - the live documentary gate had moved to `550` tests after proof-hardening, while the active map/state snapshot still showed `548`
- Scope:
  - `AGENTS.md`
  - `docs/operations/SYSTEM_STATE.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/PHASE_CLOSURE.md`
- Done when:
  - helper aliases are explicitly non-canonical
  - the documenter-only track boundary is explicit in the repo operating note
  - the live documentary gate is refreshed to `550` tests without rewriting the historical closure count inside `PHASE_CLOSURE.md`
- Verify:
  - `python -m unittest tests.test_doc_governance tests.test_architecture -v`
  - `python -m unittest discover -s tests -v`
- Result:
  - helper aliases are now explicit non-canonical tooling labels in `AGENTS.md`
  - the documenter-only track boundary is explicit again in the repo operating note
  - the live documentary gate in `OPPORTUNITY_MAP.md` and `SYSTEM_STATE.md` now reflects the `550`-test suite state
  - `PHASE_CLOSURE.md` now states that the `548`-test count remains the historical closure count, while later documentary proof-hardening lifted only the live suite gate

### DOC-004 — Reconcile New Weakness Intake From The 2026-04-17 Audit

- Status: `done`
- Priority: `HIGH`
- Level: `1`
- Depends on: `DOC-003`
- Why it exists:
  - the direct 2026-04-17 audit reproduced a policy gap where `fs.create_file` with `overwrite=true` still mutates an existing file without approval because the gate is keyed by `kind`
  - the same audit reproduced a rollback residual where `create-new` removes the file but leaves an empty directory
  - `BUG_REPORT.md`, `WEAKNESS_REPORT.md`, and `SYSTEM_STATE.md` did not yet reflect those findings, so the canonical queue understated the live blocked set
- Scope:
  - `docs/operations/WEAKNESS_REPORT.md`
  - `docs/operations/BUG_REPORT.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/SYSTEM_STATE.md`
- Done when:
  - the effect-level approval gap is explicitly named as open
  - the rollback empty-directory residual is explicitly named as open
  - the blocked set and weakness intake reflect the current confirmed queue instead of the pre-audit queue
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - the live weakness queue now includes the new effect-level approval gap and the rollback empty-directory residual
  - `BUG_REPORT.md` no longer claims that no approval residual remains open
  - `OPPORTUNITY_MAP.md` and `SYSTEM_STATE.md` now expose the fuller blocked set for the current documentary freeze track

### DOC-005 — Harden Preflight Gate Summary Against Noisy Test Output

- Status: `done`
- Priority: `MEDIUM`
- Level: `1`
- Depends on: `DOC-004`
- Why it exists:
  - the mandatory preflight snippet in `AGENTS.md` still relied on `Select-Object -Last 5`
  - in this workspace, `python -m unittest discover -s tests -v` can emit trailing operational lines after the suite summary, so the tail can hide the actual verdict
- Scope:
  - `AGENTS.md`
  - `docs/operations/OPPORTUNITY_MAP.md`
  - `docs/operations/SYSTEM_STATE.md`
- Done when:
  - the preflight command still runs in PowerShell
  - the preflight surfaces a stable suite verdict even when test output is noisy
  - the documentary snapshot records why the old tail-based check was insufficient
- Verify:
  - `python -m unittest discover -s tests -v`
  - `python -m unittest tests.test_architecture -v`
- Result:
  - `AGENTS.md` now captures the suite output in a temporary file and prints the final `Ran ... tests` line plus a stable pass/fail summary instead of trusting the raw tail
  - the documentary state now records that the previous tail-based preflight could hide the true verdict in this workspace

## Blocked By Freeze Or Architecture

### BLOCKED-102 — External session ownership residual

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: touches session hardening beyond the current frozen corrective envelope

### BLOCKED-103 — Verify isolation residual

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: touches residual verify authority/isolation boundaries that are accepted but not currently approved for growth

### BLOCKED-105 — Apply/Rollback external-writer atomicity

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: would require deeper runtime hardening on critical execution paths

### BLOCKED-106 — Project/protocol anchoring

- Source: `docs/operations/PROJECT_OS_BACKLOG.md`
- Status: `blocked`
- Reason: remains procedural and would require architecture-level authorization before canonical promotion

### BLOCKED-GAP-02 — Canonical intention entity

- Source: `docs/operations/adr/GAP-02-intencao-canonica.md`
- Status: `blocked`
- Reason: explicit ADR block under freeze; no schema/state expansion is authorized

### BLOCKED-ALIGNMENT-EXPORT

- Source: `docs/operations/FREEZE_POLICY.md`
- Status: `blocked`
- Reason: no canonical alignment artifact exists

### BLOCKED-P5-STRUCTURE — `PHASE_CLOSURE.md` structural proof hardening

- Source: proof-of-stop `P5`
- Status: `blocked`
- Reason: targeted literal guards already cover the current closure claim; deeper structural hardening would require a separate test-surface slice outside the active documenter-only queue

### BLOCKED-WEAK-CRIT-001 — `exec.command` post-mutation artifact persistence gap

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed critical fix requires mutating `core/action_runtime.py`, `cli/commands/apply.py`, and proportional regression tests, which this loop may not touch under `AGENTS.md`

### BLOCKED-WEAK-HIGH-001 — session refresh crash window

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed high-severity fix requires mutating `core/state_store.py` and proportional regression tests, which this loop may not touch under `AGENTS.md`

### BLOCKED-WEAK-HIGH-002 — open-session crash split

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed high-severity fix requires mutating `core/state_store.py` and proportional regression tests to close the `session_registry_mismatch` window, which this loop may not touch under `AGENTS.md`

### BLOCKED-WEAK-HIGH-003 — effect-level approval gap for `fs.create_file overwrite=true`

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed fix requires mutating `core/execution_policy.py`, `cli/commands/apply.py`, `core/action_runtime.py`, and proportional regression tests so approval can depend on destructive effect, not only `kind`

### BLOCKED-WEAK-MED-004 — rollback leaves empty directory residue after `create-new`

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked in documenter track`
- Reason: the confirmed fix requires mutating `core/action_runtime.py` and proportional regression tests to track and prune only the empty directories created by the current apply

### BLOCKED-DOC-DRIFT-002 — `AGENT_ARCHITECTURE.md` remains misaligned with the runtime contract

- Source: `docs/operations/WEAKNESS_REPORT.md`
- Status: `blocked by architecture-test perimeter`
- Reason: the document drift is real, but `tests/test_architecture.py` currently asserts the literal `READ -> ANALYZE -> PLAN -> DELEGATE -> ACT -> VERIFY -> RECORD` flow and the `DELEGATE`/`RECORD` headings, so correcting the document would require coupled doc+test changes outside this documenter-only loop

## Accepted Residuals That Are Not Queue Items By Default

- file-backed session ownership does not yet close same-user tamper/restore of the external authority files
- verify still has residual bypass limits for perfectly restored transient tamper, out-of-root effects, or fully concealed drift
- apply/rollback still do not claim perfect atomicity against arbitrary external writers during execution
- performance has no currently eligible hotspot; the remaining event-log scaling risk is future-facing and measurement-gated

## Next Item

- `none — documenter queue exhausted; await Formal Resume Trigger`
- blocked residuals:
  - `WEAK-CRIT-001`, `WEAK-HIGH-001`, `WEAK-HIGH-002`, `WEAK-HIGH-003`, and `WEAK-MED-004` require leaving the documenter-only track because they are corrective runtime slices
  - `AGENT_ARCHITECTURE.md` drift is now explicitly known, but remains blocked by the coupled `tests/test_architecture.py` literal guard
  - `PHASE_CLOSURE.md` structural proof hardening remains outside the active documenter-only queue
- latest revalidation:
  - the weakness queue was re-read and reconciled on 2026-04-17
  - `WEAKNESS_REPORT.md` now exposes `1` `CRÍTICO`, `3` `ALTO`, and multiple `MÉDIO`
  - the deep audit reproduced a new effect-level approval gap (`fs.create_file overwrite=true` without approval) and a rollback residual (`create-new` leaves empty directory residue)
  - the deep audit also preserved the newer `MÉDIO` items (`close_session()` crash split, `verify` `32`-checks edge) plus a stronger coverage gap (`session + plan + apply + verify + rollback` end-to-end still fragmented)
  - undocumented runtime behaviors (`check-state` synthetic verify check, `plan_generation_id` fallback, auto-filled `consolidation_id`) were added to `WEAKNESS_REPORT.md`
  - the transient red gate seen in a prior `discover` tail did not reproduce on the next serial rerun; the live gate returned `550` tests, `0` failures, `6` skips, and `tests.test_architecture` stayed green
  - a later docs-only revalidation also stayed green (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) and still did not produce any new executable documentary slice
  - another full memory reread plus green gate revalidation (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) again confirmed that the current blocked set still yields no executable documentary-only slice
  - a subsequent full external-memory reread plus green gate revalidation (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green) again produced no executable documentary-only slice
  - the latest iteration also closed a documentary drift in the mandatory preflight itself: the raw `tail`-style summary could be hidden by trailing test output, so `AGENTS.md` now prints a stable verdict from a temporary capture while the live gate stayed green (`550` tests, `0` failures, `6` skips; `tests.test_architecture` green)
  - the first exact rerun of that hardened preflight also stayed stable (`Ran 550 tests in 26.018s` / `OK (skipped=6)`) and still produced no new documentary-only slice; `tests.test_architecture` remained green
  - the next exact rerun of that same hardened preflight also stayed stable (`Ran 550 tests in 25.856s` / `OK`), `tests.test_architecture` remained green (`Ran 50 tests in 0.544s` / `OK`), and no new documentary-only slice became executable
  - no documentary slice became executable from that intake alone
