# Formal Resume Trigger — Third-Party Project Pilot

## Status

- `consumed on 2026-04-24; rpg_caminhada pilot executed after explicit operator go`
- current slice result: first third-party project now has a fresh canonical Cerebro v2 `.cerebro/` runtime state
- precondition already satisfied for preparation: AGENTS-equivalent gate green at `923` tests, `0` failures, `0` errors, `6` skips
- task #8 / post-compaction full-gate concern: satisfied in this workspace before pilot preparation; no internal closure blocker remains
- closure gate: AGENTS-equivalent runner green after pilot execution and
  documentation reconciliation: `923` tests, `0` failures, `0` errors,
  `6` skips

## Execution Result

Selected target:

- `D:\projetos_cli\pessoais\rpg_caminhada`

Legacy-state handling:

- existing target `.cerebro/` was not reused or migrated
- legacy schema-v1 runtime directory was preserved at
  `D:\projetos_cli\pessoais\rpg_caminhada\.cerebro_legacy_v1_2026-04-24`
- fresh v2 runtime directory was initialized at
  `D:\projetos_cli\pessoais\rpg_caminhada\.cerebro`

Canonical CLI operations completed:

- `init`: `OK`
- `import-context`: registered `9` approved primary sources, `revision: 1`
- `checkpoint`: recorded the correct continuation state, `revision: 2`
- `validate`: `OK`, `validation_passed`, `sources: 9`, `revision: 2`
- `analyze`: `OK`, `analysis_ready`, `validation: ok`, `sources: 9`

Registered source set:

- `cerebro_base/_PROJETO.md`
- `cerebro_base/CEREBRO.md`
- `cerebro_base/03_HIERARQUIA_DE_FONTES.md`
- `cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md`
- `cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md`
- `cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md`
- `cerebro_base/04_MAPA_DE_RETORNO_ATUAL.md`
- `cerebro_base/REGRAS_DO_DOMINIO.md`
- `cerebro_base/04_CONHECIMENTO_CONSOLIDADO.md`

Read-only advisory follow-up:

- `experiments/context_discovery` generated
  `_local/third_party_pilot_2026-04-24/context_discovery_report.md`
- report summary: `registered_source_count=9`,
  `candidates_not_registered_count=20`,
  `drift_on_registered_sources_count=0`,
  `missing_registered_sources_count=0`,
  `state_change: none`
- the candidate list is proposal-only. It must not be treated as an automatic
  import list. Template candidates under `cerebro_base/00_PAINEL_VIGENTE/`
  are expected noise and should stay excluded unless a later human decision says
  otherwise.

Pilot evidence:

- exports were written under
  `D:\projetos_cli\cerebro\_local\third_party_pilot_2026-04-24\`
- target project source files were not edited by this slice
- Cerebro `core/`, `cli/`, `tests/`, `extensions/`, and implementation files
  were not touched by this slice

Improvement signal exposed:

- the first nine-source intake was sufficient to validate and analyze the
  target correctly
- context discovery is useful as a second-pass triage surface, but needs
  operator/LLM filtering because it correctly finds additional likely-relevant
  docs and also surfaces template noise
- next real decision is whether to import any additional source candidates from
  the advisory report; candidates remain proposals until imported through the
  canonical CLI after an explicit source-set decision

## Objective

Run one small, reversible, audit-first pilot where Cerebro manages a real
third-party project without adding speculative Cerebro features. The pilot is
meant to expose real operator friction in the existing runtime flow:

1. surface-only discovery with `cerebro bootstrap-scan`
2. read-only Third-Party Intake Gate
3. human source selection
4. explicit `cerebro import-context`
5. `cerebro checkpoint`
6. `cerebro validate`
7. `cerebro analyze`
8. read-only `experiments/context_discovery`
9. human review of any proposed source changes

## Candidate Projects

The current real candidates are:

- `D:\projetos_cli\Portal\Resolução Humaita Codex`
- `D:\projetos_cli\pessoais\rpg_caminhada`
- `D:\projetos_cli\escritorio`

Claude owns the parallel read-only reconnaissance in
`docs/operations/THIRD_PARTY_PILOT_RECON_CLAUDE.md`. This trigger must not be
executed until that report exists and the human selects exactly one target.

## Recon Integration

Claude's read-only recon recommends:

- selected-for-human-approval target: `D:\projetos_cli\pessoais\rpg_caminhada`
- reason: lowest sensitivity risk, no apparent client PII, strong existing
  `cerebro_base/` human-curated context hierarchy, heterogeneous but manageable
  stack, and no production-pressure deadline
- deferred target: `D:\projetos_cli\Portal\Resolução Humaita Codex` because it
  appears to be real consulting/fiscal work with identifiable client context
- rejected first-pilot target: `D:\projetos_cli\escritorio` because path names
  expose CPFs and the pilot would create unnecessary LGPD risk

The earlier four-file initial source set is superseded by the intake gate in
`docs/operations/THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md`. That audit found
the four files below are canonical, but insufficient by themselves because
`04_DIAGNOSTICO_INICIAL_ATUAL.md` is stale without the continuity/current-return
files:

- `cerebro_base/_PROJETO.md`
- `cerebro_base/CEREBRO.md`
- `cerebro_base/03_HIERARQUIA_DE_FONTES.md`
- `cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md`

The next step is explicit human approval of the intake decision, including the
legacy `.cerebro/state.json` v1 handling and the exact expanded import list.
No files are registered yet.

## Boundary Opened After Human Go

Allowed only after target selection and explicit human go:

- run read-only preflight commands against the selected target
- run `cerebro bootstrap-scan --root <selected-target>` from any directory
- review `docs/operations/THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md` and record
  the human source-set decision before import
- change into the selected target root and run:
  - `cerebro init`
  - `cerebro import-context --files ...`
  - `cerebro checkpoint --goal ... --summary ... --next-step ...`
  - `cerebro validate`
  - `cerebro analyze`
- run `experiments/context_discovery` from the Cerebro repo against the selected
  target as a read-only advisory report
- write local pilot artifacts under `D:\projetos_cli\cerebro\_local\third_party_pilot_2026-04-24\`
- update this trigger, `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, and
  `observation_center.toml` with the pilot outcome

Explicitly out of scope:

- editing files inside any third-party project except the selected project's
  `.cerebro/` runtime directory created by the canonical CLI
- running `import-context` without human-approved file list
- running `import-context` from the superseded four-file list without the intake
  warning and oracle decision
- using `context_discovery` output as an automatic import list
- mutating `.cerebro/state.json` by any path other than the canonical CLI
- touching Cerebro `core/`, `cli/`, `tests/`, `extensions/`, or
  `experiments/` implementation
- adding dashboard, registry, multi-project orchestration, GUI, or other feature
  work before repeated real pilot pain justifies a new trigger
- initializing more than one third-party project in this trigger

## Stop Conditions

Stop before `cerebro init` if:

- Claude's recon report is absent or inconclusive
- the human has not selected exactly one target
- the selected target path does not exist
- the selected target already has `.cerebro/state.json` and no explicit
  decision says to reuse or replace it
- the intake gate has not been reviewed and approved by the human
- the oracle question still leads to "create schema" or "define progression
  formulas" as the next project step
- the selected target appears to contain sensitive personal, legal, financial,
  credential, medical, or production-secret material in likely source files
- no small initial source set can be chosen confidently
- the target is not a real project root or has no clear canonical files
- the AGENTS-equivalent Cerebro gate is red before the pilot starts

Stop after `cerebro init` if:

- `import-context` proposes unexpected removals or additions
- the human rejects the source diff
- `validate` fails
- `analyze` cannot open continuity
- `context_discovery` suggests large drift that needs human triage before any
  further import

## Acceptance Criteria

The pilot slice can close only when:

- exactly one selected target has a canonical `.cerebro/state.json`
- the intake gate records the legacy-state decision and approved source set
- its initial source set was explicitly approved by the human
- `cerebro validate` passes in the selected target
- `cerebro analyze` opens continuity in the selected target
- a read-only `context_discovery` report was generated or explicitly skipped
  with reason
- any suggested follow-up source changes remain proposals, not automatic imports
- Cerebro's own AGENTS-equivalent gate stays green after documentation updates
- this trigger records the final target, commands, source list, gate result, and
  whether the pilot exposed a real Cerebro improvement need

## Coordination Contract

- Claude file: `docs/operations/THIRD_PARTY_PILOT_RECON_CLAUDE.md`
- Codex files: this trigger, `docs/operations/RUNBOOK_THIRD_PARTY_PILOT.md`,
  and `docs/operations/THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md`
- Integration waits for both fronts. The next loop combines Claude's target
  recommendation with this runbook and asks for the human go before mutating any
  third-party project.
