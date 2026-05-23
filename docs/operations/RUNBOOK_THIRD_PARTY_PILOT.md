# Runbook — Third-Party Project Pilot

## Purpose

Execute the first real third-party Cerebro pilot without expanding the runtime.
The goal is to learn from a real project using the existing canonical flow, not
to pre-build multi-project features.

## Inputs Required

- Claude recon file:
  `docs/operations/THIRD_PARTY_PILOT_RECON_CLAUDE.md`
- selected target: `D:\projetos_cli\pessoais\rpg_caminhada`, pending explicit
  human go
- intake gate:
  `docs/operations/THIRD_PARTY_INTAKE_GATE_RPG_CAMINHADA.md`
- human-approved initial source list
- green Cerebro AGENTS-equivalent gate before execution

## Phase 0 — Integrate Recon And Intake Gate

Read Claude's report and extract:

- recommended target
- target risk level
- `must_import` files
- `maybe_import` files
- `do_not_import_initially` files
- open questions
- stop conditions
- intake oracle result

Do not proceed if the recommendation is ambiguous or if the initial source set
requires guessing.

Recon integration result:

- scope: exactly one project, not a multi-project registry pilot
- target: `D:\projetos_cli\pessoais\rpg_caminhada`
- source-decision order: run `bootstrap-scan` first as a surface-only aid; use
  the intake gate to classify sources by role and conflict; approve an exact
  expanded import list; run `context_discovery` after the initial canonical
  source set exists as advisory drift/candidate review
- pilot log location: `D:\projetos_cli\ambiente_cerebro\cerebro\_local\third_party_pilot_2026-04-24\`
- if later `validate` fails because a registered source changed legitimately,
  default response is explicit re-registration through `import-context`, not
  source rollback
- task #8 / full-gate prerequisite is already satisfied at `923/0/0/6`

Intake integration result:

- the earlier four-file list is superseded because
  `cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md` is canonical but stale
- `cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md`,
  `cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md`, and
  `cerebro_base/04_MAPA_DE_RETORNO_ATUAL.md` are required before bootstrap v2
  can be trusted
- the target contains a legacy `.cerebro/state.json` schema v1; current runtime
  validation rejects it as `unsupported_schema_version`, so reuse is blocked
  unless a separate migration decision is made
- oracle: if the source set makes the agent think the next step is "create the
  schema" or "define progression formulas", the intake gate fails; the expected
  next step is Supabase validation / Edge Function implementation

## Phase 1 — Read-Only Preflight

Replace `<TARGET>` with the selected project path.

```powershell
$target = '<TARGET>'
Test-Path -LiteralPath $target
Get-ChildItem -Force -LiteralPath $target | Select-Object Mode,Name,Length,LastWriteTime | Format-Table -AutoSize
Test-Path -LiteralPath (Join-Path $target '.cerebro\state.json')
git -C $target status --short
cerebro bootstrap-scan --root $target --limit 12
```

Interpretation:

- `Test-Path` must be true.
- existing `.cerebro\state.json` is a stop unless the human chooses reuse.
  For `rpg_caminhada`, the observed legacy state is schema v1 and should be
  treated as archive/replace for bootstrap v2 unless the human explicitly opens
  a migration slice.
- dirty Git status is not automatically fatal, but must be named before any
  `.cerebro/` mutation.
- `bootstrap-scan` is assistive only; it does not read file contents and does
  not decide the source set.

## Phase 2 — Human Source Decision

Prepare a short list:

```text
must_import:
- ...

maybe_import:
- ...

excluded_initially:
- ...
```

Rules:

- start small
- prefer human-maintained project-definition and continuity files
- include at most one or two current-state handoff files
- avoid generated files, logs, lockfiles, build outputs, secrets, large assets,
  and historical dumps
- do not import files only because `context_discovery` or `bootstrap-scan`
  mentioned them

Stop until the human approves the exact `--files` list.

Current proposed first source list, pending human approval:

```text
must_import:
- cerebro_base/_PROJETO.md
- cerebro_base/CEREBRO.md
- cerebro_base/03_HIERARQUIA_DE_FONTES.md
- cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md
- cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md
- cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md
- cerebro_base/04_MAPA_DE_RETORNO_ATUAL.md

recommended_if_human_wants_stronger_domain_grounding:
- cerebro_base/REGRAS_DO_DOMINIO.md
- cerebro_base/04_CONHECIMENTO_CONSOLIDADO.md

maybe_import_later:
- cerebro_base/00_HUB_DO_CEREBRO.md
- cerebro_base/GDD_MVP.md
- cerebro_base/DECISIONS.md
- cerebro_base/BACKLOG_TECNICO_MVP.md

excluded_initially:
- node_modules/
- livros_fontes/
- supabase/migrations/*.sql
- any .env or secret-bearing config
- templates under cerebro_base/00_PAINEL_VIGENTE/
- local hand-made Cerebro metadata not directly about the RPG project
```

## Phase 3 — Initialize The Selected Project

Run from the selected target root, not from the Cerebro repo.

```powershell
Set-Location -LiteralPath 'D:\projetos_cli\pessoais\rpg_caminhada'
cerebro init
cerebro import-context --files `
  cerebro_base/_PROJETO.md `
  cerebro_base/CEREBRO.md `
  cerebro_base/03_HIERARQUIA_DE_FONTES.md `
  cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md `
  cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md `
  cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md `
  cerebro_base/04_MAPA_DE_RETORNO_ATUAL.md
```

`import-context` previews a diff and asks for confirmation. Confirm only if the
diff exactly matches the approved source list. If the human also approves the
two recommended domain/knowledge sources, append them explicitly to the command;
do not infer them automatically.

## Phase 4 — Seed The First Checkpoint

Run from the selected target root.

```powershell
cerebro checkpoint `
  --goal "Pilot Cerebro continuity for this project" `
  --summary "Initial canonical source set registered after human review." `
  --next-step "Run validate, open analyze, then review the read-only context discovery report."
```

Then validate:

```powershell
cerebro validate
```

`validate` must pass before any continuity session is opened.

## Phase 5 — Open Continuity

Run from the selected target root.

```powershell
cerebro analyze --actor codex
```

If the next operator needs to close the session later, use the session token
workflow deliberately. Do not leave a session open accidentally at closeout.

## Phase 6 — Read-Only Context Discovery

Run this from the Cerebro repo root so the experimental package imports from
the checked-out Cerebro workspace.

```powershell
Set-Location -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro'
New-Item -ItemType Directory -Force -Path '_local\third_party_pilot_2026-04-24' | Out-Null
@'
from pathlib import Path
from experiments.context_discovery import discover_context, render_markdown

target = Path(r'D:\projetos_cli\pessoais\rpg_caminhada')
report = discover_context(target)
print(render_markdown(report))
'@ | python - | Tee-Object -FilePath '_local\third_party_pilot_2026-04-24\rpg_caminhada_context_discovery.md'
```

The report is advisory only:

- `candidates_not_registered` means "review", not "import"
- `drift_on_registered_sources` means "decide", not "auto-sync"
- `missing_registered_sources` means "triage", not "delete from state"

Any follow-up import requires a new human-approved `cerebro import-context`
diff.

## Phase 7 — Closeout

From the selected target root, close the pilot work with a checkpoint after the
human review decision is known.

```powershell
cerebro checkpoint `
  --actor codex `
  --goal "Pilot Cerebro continuity for this project" `
  --summary "<what was learned and what source set is canonical now>" `
  --next-step "<next human-approved project step>"
```

Then run:

```powershell
cerebro validate
```

Return to the Cerebro repo and run the AGENTS-equivalent full gate before
declaring the pilot closed.

## Required Closeout Record

Update `FORMAL_RESUME_TRIGGER_THIRD_PARTY_PILOT.md` with:

- selected target
- intake gate result and oracle answer
- legacy `.cerebro/state.json` decision
- approved source list
- commands run
- `validate` result in the target project
- `analyze` result in the target project
- path to the advisory `context_discovery` report or reason skipped
- human decision on any extra candidates
- Cerebro repo AGENTS-equivalent gate result
- concrete frictions observed, if any

If no repeated or material friction appears, do not open feature work.
