# Third-Party Pilot Recon — Claude

Read-only reconnaissance of three real candidate projects for the first
"Cerebro manages a third-party project" pilot. No mutation was performed on
any candidate and no `.cerebro/` directory was created anywhere outside the
Cerebro repository. All evidence below comes from `Glob` path enumeration and
bounded reads of already-present markdown headers.

## Executive Recommendation

**Recommended first pilot: `D:\projetos_cli\pessoais\rpg_caminhada`.**

Why this one and not the others:

- It is the only candidate with effectively **zero personal-data risk**. No CPFs, no tax filings, no client PII anywhere in the tree. Exposure of `.cerebro/state.json` would reveal only a hobby game-design project.
- It already carries a **hand-made context-management system** under `cerebro_base/` that defines an explicit source hierarchy (`03_HIERARQUIA_DE_FONTES.md`), a canonical entry point (`CEREBRO.md`), and a project-definition file (`_PROJETO.md`) with filled front-matter `fonte_de_verdade: canonica`. That is a ready-made **oracle** to test whether `bootstrap-scan` and `experiments/context_discovery/` independently rediscover the same canonical files the human already curated by hand.
- Its stack (TypeScript + React Native via Expo, Supabase backend, one Python simulation script) is heterogeneous enough to exercise the scanner across `package.json`, `pyproject.toml` absence, `supabase/migrations/*.sql`, `src/`, and the rich Obsidian-style markdown graph under `cerebro_base/`, without drowning the scanner in millions of files.
- It has no active production pressure. If Cerebro corrupts or rejects something, nothing downstream breaks: no client is waiting on a tax deadline and no fiscal authority is auditing the folder.
- It reveals real context-friction: the project is marked `tempo em andamento: novo — iniciado em 2026-04-05` with `estado das frentes principais: nenhuma frente iniciada`, so the pilot will catch the scanner at exactly the bootstrap moment `context_discovery` was designed to help — a new project where the human is still deciding which files matter.

The other two candidates are rejected as first pilot for concrete reasons recorded in the matrix below. Both can become second or third pilots if `rpg_caminhada` closes cleanly, but neither should be the first.

## Candidate Matrix

| Project | Approx size | Stack inferred | Canonical sources found | Risk | Pilot value | Recommendation |
|---|---|---|---|---|---|---|
| `pessoais\rpg_caminhada` | Medium (code + Obsidian-style docs; `node_modules` already excluded by default scanner) | TypeScript + React Native (Expo); Supabase (PostgreSQL migrations + edge functions); Python simulation; Obsidian `.md` graph under `cerebro_base/` | Very clear: `cerebro_base/CEREBRO.md`, `cerebro_base/_PROJETO.md` (filled frontmatter), `cerebro_base/AGENTS.md`, `cerebro_base/03_HIERARQUIA_DE_FONTES.md`, `cerebro_base/00_HUB_DO_CEREBRO.md`, `cerebro_base/GDD_MVP.md`, `cerebro_base/BACKLOG_TECNICO_MVP.md`, `cerebro_base/REGRAS_DO_DOMINIO.md`, `cerebro_base/DECISIONS.md`, `cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md`, `cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md` | Low — personal hobby project, no third-party PII | High — hand-curated canonical hierarchy provides an oracle for `bootstrap-scan` and `context_discovery` validation | **yes (first pilot)** |
| `Portal\Resolução Humaita Codex` | Large (3+ years of fiscal competencies 2023-10 to 2025-12, multiple dossiê cycles, `98_TEMPORARIOS_DESCARTE_TECNICO/` with many unzipped XLSX payloads) | Document-heavy Obsidian-like markdown vault; depends on external XLSX workbooks; consulting/legal work on Brazilian fiscal reconciliation (ICMS, DARs, DAMs, EFD) | Inferable but not explicit: `00_PAINEL_VIGENTE/Conceito - *.md`, `01_TRABALHO_VIGENTE/02_ANALISES_POR_COMPETENCIA/YYYY-MM.md`, `01_TRABALHO_VIGENTE/04_RASCUNHOS_RETIFICACAO/YYYY-MM_DOSSIE_CORRECAO.md`, `01_TRABALHO_VIGENTE/00_ENTRADAS_COPIAS_SEGURAS/YYYY_INDICE_COPIAS_SEGURAS.md` | Medium-high — consulting product with identifiable client name ("Humaitá"); XLSX payloads in `DESCARTE_TECNICO/` likely contain third-party fiscal data | Medium — would stress-test scanner at real volume, but risk dominates | **later** |
| `escritorio\IRPF e Caixa Rural` | Very large (multiple real clients, DBK tax backup files, bundled Java Runtime for AR2025 installer, thousands of JRE library files) | Fiscal-services organizational tree; uses the Brazilian Receita Federal AR2025 installer as a third-party tool under `material_apoio/`; Obsidian-style methodology vault under `IRPF/_SISTEMA/` | System/methodology layer clear (`IRPF/_SISTEMA/01_METODOLOGIA/*.md`, `IRPF/_SISTEMA/04_KIT_PORTATIL_PARA_NOVO_CLIENTE/`), but entangled with per-client client files (`CONTRIBUINTES/01_IRPF/CLIENTES/*`) that carry PII | High — CPFs literally in directory names (`IRACY_APARECIDA_ARAUJO__CPF_11399970259`), DBK files with taxpayer IDs in filenames, active production use for multiple third-party individuals; LGPD exposure if `.cerebro/state.json` were ever shared | Low for a *first* pilot — the risk of accidentally registering a file path that leaks a CPF into the canonical `.cerebro/state.json` outweighs the pilot learning | **no** |

## Deep Dive On Recommended Project: `pessoais\rpg_caminhada`

### Structure

- Root: mix of React Native scaffolding (`babel.config.js`, `expo-env.d.ts`), Python prototype (`simulacao_progressao.py`), Supabase backend (`supabase/migrations/`, `supabase/functions/_shared/`), TypeScript source (`src/lib/supabase/client.ts`, `src/lib/supabase/types.ts`), database schema (`database/schema.sql`), and a rich documentation vault (`cerebro_base/`).
- `cerebro_base/` is an Obsidian-style wiki with numbered top-level files (`00_HUB_DO_CEREBRO.md`, `01_…`, `03_HIERARQUIA_DE_FONTES.md`, `04_DIAGNOSTICO_INICIAL_ATUAL.md`, `04_MAPA_DE_RETORNO_ATUAL.md`, `07_PAINEL_OPERACIONAL_DERIVADO.md`, `08_VISOES_DE_GRAFO.md`, `10_LOCAL_GRAPH_DE_SESSAO.md`, `11_ANALISE_DE_IMPACTO_DERIVADA.md`, `12_INTEGRACAO_RUNTIME_OBSIDIAN.md`, `13_AUTOMACOES_OBSIDIAN_LOCAIS.md`) plus per-role files under `AGENTS_MODOS/`, per-source files under `fontes_livros/`, and templates under `00_PAINEL_VIGENTE/_TEMPLATE - *.md`.
- `livros_fontes/` holds PDFs of game-design references (Schell's *Art of Game Design*, Rogers' *Level Up*, Salen & Zimmerman *Rules of Play*, Schreiber & Romero *Game Balance*, plus mobile-development PDFs).
- `cerebro_base/fontes_livros/` holds markdown evidence notes derived from those PDFs, already normalized in the repo.
- `node_modules/`, `supabase/` (generated), and the PDF folder `livros_fontes/` are all already in ignored or auto-skipped scanner categories (`node_modules` is in `IGNORED_DIR_NAMES`; `livros_fontes` matches the `livros_fontes` token in the same list).

### Stack

- **Frontend:** React Native via Expo (evidence: `expo-env.d.ts`, `babel.config.js`, `.gitignore`, TypeScript under `src/`). No explicit `package.json` was confirmed in the Glob sample but the directory structure is idiomatic Expo.
- **Backend:** Supabase (Postgres migrations at `supabase/migrations/20260405000000_initial_schema.sql` and `20260405000001_add_enemy_templates.sql`; `supabase/functions/_shared/cors.ts` for edge functions).
- **Data model helpers:** Python script `simulacao_progressao.py` at the root, isolated — likely a balance-simulation prototype.
- **Docs layer:** Hand-curated Obsidian-style knowledge graph under `cerebro_base/`, already structured around exactly the same concepts Cerebro formalizes (entry point, source hierarchy, continuity memory, operational panel, diagnostic, onboarding).

### Signals Of Maturity

- `cerebro_base/_PROJETO.md` has a front-matter `preenchido: true`, meaning the owner already completed the canonical project-identification interview.
- `cerebro_base/03_HIERARQUIA_DE_FONTES.md` has front-matter `preenchido: true` and `data_atualizacao: 2026-04-05`, and declares a four-level source hierarchy (`_PROJETO.md` > `04_DIAGNOSTICO_INICIAL_ATUAL.md` > `04_MEMORIA_CONTINUIDADE_ATUAL.md` > `04_CONHECIMENTO_CONSOLIDADO.md`). This is an explicit, machine-readable hierarchy that can validate Cerebro's scanner output.
- `cerebro_base/CEREBRO.md` enforces an explicit "ordem de execução obrigatória" for agents reading the project, with numbered reading steps 1–6. This is the exact pattern Cerebro was designed to support, hand-built one layer up in markdown.
- `cerebro_base/AGENTS.md` is minimal and points to `CEREBRO.md` as the real entry point. It is a good discipline signal, not fragmentation.
- The numbered filename convention (`00_…`, `01_…`, `04_…`) gives `bootstrap-scan` a natural priority bonus (already implemented in the scanner as `priority-style naming` for `00_/01_`).

### Signals Of Risk

- `node_modules/` is large but already in `IGNORED_DIR_NAMES`, so the scanner should not descend into it. **Verification during pilot:** confirm the shortlist contains zero entries under `node_modules/`.
- `livros_fontes/` contains PDFs of copyrighted books; these are read-only reference material for the project's design research. The scanner's existing `PENALIZED_PART_TOKENS` skip-list and the PDF suffix being outside `TEXTUAL_SUFFIXES` should keep those PDFs out of the shortlist. **Verification:** confirm no PDF appears in the import-context confirmation prompt.
- The project is very new (started 2026-04-05) and `04_DIAGNOSTICO_INICIAL_ATUAL.md` is filled but "nenhuma frente iniciada". This is a good pilot timing — the scanner will not be competing with mature legacy state — but it also means the pilot will generate more value from `context_discovery` drift/missing reports once real work starts, not from the first scan itself.
- Supabase migration files use real timestamps in filenames (`20260405000000_initial_schema.sql`). These are code not data, safe to register if the user chooses, but they are not markdown so bootstrap-scan will ignore them by suffix.

### Important Files (Preliminary Canonical Set)

See the next section for the recommended classification.

### Possible Obsolete Files

- `cerebro_base/_AVALIACAO_DO_CEREBRO.md` is named like a meta-evaluation of the local Cerebro system. It may or may not be current; the pilot owner should decide whether it belongs in the canonical set or stays out.
- Duplicate template files under `cerebro_base/00_PAINEL_VIGENTE/_TEMPLATE - *.md` should not be registered individually; they exist to be copied, not canonical by themselves.
- `cerebro_base/APRENDIZADO_OPERACIONAL.md`, `cerebro_base/VERSAO_DO_CEREBRO.md`, and `cerebro_base/CHANGELOG_DO_CEREBRO.md` refer to the *local Obsidian-style* cerebro, not to this Cerebro CLI. They are metadata about the hand-made system and should probably not be registered as canonical sources of the RPG project itself.

### Possible Sensitive Data

- No CPFs, no tax records, no client PII anywhere in the tree.
- `_PROJETO.md` names the project as `rpg_caminhada`, domain `software`, type `aplicativo mobile`. No personal identification.
- Supabase migration files reference game-design domain tables (enemy templates, progression). No user data.
- Overall: **no material sensitivity expected.** The main caveat is that if Supabase connection strings, API keys, or tokens exist somewhere in the tree (for example an `.env.local` or `supabase/config.toml`), those should be excluded from the registered source set — even though they would normally be in a `.gitignore`.

## Recommended Canonical Source Set

Classification for the pilot's first `import-context` decision. The operator reviews and confirms before registration; nothing below is automatically registered.

### must_import

- `cerebro_base/_PROJETO.md` — single primary source per the local hierarchy; defines project, domain, objective, stack, state
- `cerebro_base/CEREBRO.md` — canonical entry point; captures agent-reading protocol
- `cerebro_base/03_HIERARQUIA_DE_FONTES.md` — machine-readable source hierarchy; oracle for later validation
- `cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md` — canonical diagnostic of current onboarding state

### maybe_import

- `cerebro_base/00_HUB_DO_CEREBRO.md` — hub index; useful but may duplicate what the hierarchy already exposes
- `cerebro_base/GDD_MVP.md` — game design document MVP; likely important once the game design phase starts
- `cerebro_base/REGRAS_DO_DOMINIO.md` — domain rules; anchor for game mechanics
- `cerebro_base/DECISIONS.md` — decision log; candidate for continuity-memory
- `cerebro_base/NIVEL_DE_IMPLANTACAO_ATUAL.md` — calibration reference for agent intensity
- `cerebro_base/AGENTS_CORE.md` / `cerebro_base/AGENTS_RUNTIME.md` — operating instructions; relevant if the pilot wants agent-protocol context
- `cerebro_base/BACKLOG_TECNICO_MVP.md` — technical backlog; operator should decide whether it is canonical or projection
- Root `README.md` if one exists (not confirmed in sample)

### do_not_import_initially

- Any file under `node_modules/` (already scanner-excluded)
- Any file under `livros_fontes/` (PDFs, non-textual suffix; copyrighted third-party material)
- Any `*_TEMPLATE *.md` under `cerebro_base/00_PAINEL_VIGENTE/` (templates, not canonical content)
- Any Supabase migration file (`supabase/migrations/*.sql`) — code, not context; can be surfaced through a code-index layer later
- Any `.env`, `.env.local`, or `supabase/config.toml` if present (secrets hygiene)
- `cerebro_base/VERSAO_DO_CEREBRO.md`, `cerebro_base/CHANGELOG_DO_CEREBRO.md`, `cerebro_base/APRENDIZADO_OPERACIONAL.md`, `cerebro_base/_AVALIACAO_DO_CEREBRO.md` — metadata about the local hand-made cerebro, not about the RPG project itself

## Pilot Risks

Each risk paired with a concrete mitigation.

- **Risk:** Two distinct uses of the word "cerebro" in this pilot. The target project has its own `cerebro_base/` directory that is an Obsidian-style governance layer, and the Cerebro CLI will create a `.cerebro/` directory at the same project root. Operator confusion is likely.
  - **Mitigation:** Before running `cerebro init`, document explicitly in the runbook that `.cerebro/` is runtime state owned by the Cerebro CLI, and `cerebro_base/` is the owner's local Obsidian vault. Do not move, rename, or merge them.

- **Risk:** The owner's hand-made hierarchy declares `04_MEMORIA_CONTINUIDADE_ATUAL.md` as a live canonical source, but that file was not observed in the Glob sample (may not exist yet). If it is registered before it exists, SHA-256 validation will fail on the first `validate`.
  - **Mitigation:** During `import-context` confirmation, only register files that already exist on disk. If the file is missing, skip it; the owner can add it after onboarding.

- **Risk:** Supabase secrets or environment files might be silently present under `supabase/` or at the root. If registered, their content ends up in the canonical-source SHA-256 fingerprint; they would not be leaked, but the source list in `state.json` would expose their existence.
  - **Mitigation:** Restrict the first `import-context` to files under `cerebro_base/` only. Code and secrets are out of the first canonical set by construction.

- **Risk:** The scanner's `heuristic_basis: path-and-filename signals only` may miss the filled front-matter in `_PROJETO.md` and under-rank it against raw `README.md`. That was exactly the gap that Trigger A attempted and was withdrawn from.
  - **Mitigation:** This pilot intentionally exercises that gap. Part of the pilot value is observing whether `experiments/context_discovery/` (which is allowed to read bounded content) lifts the right files that `bootstrap-scan` misses.

- **Risk:** The pilot discovers a real ergonomic friction (for example: `import-context` requires explicit relative paths and the owner prefers a TUI) and the operator is tempted to open a feature-work slice. That would violate the freeze policy and the "no feature work to make the pilot comfortable" rule.
  - **Mitigation:** Log ergonomic frictions in the pilot report. Do not patch the Cerebro runtime inside the pilot loop. A future formal resume trigger is the only way to act on those findings.

- **Risk:** A subsequent `validate` fails because the owner edits `cerebro_base/_PROJETO.md` (it is a live document for them). SHA-256 drift is the expected, correct signal, but may look like a regression.
  - **Mitigation:** Brief the owner before the pilot: "if you edit a registered source, `validate` will fail on purpose and you re-register explicitly via `import-context` again." That is the auditability property, not a bug.

## Suggested First Pilot Flow

Proposed operational sequence. None of these steps mutates any project; `preflight` is read-only, and the mutating steps (`init`, `import-context`, `checkpoint`, `validate`, `analyze`) are explicitly **not** executed by this recon agent — they are operator actions.

1. **Preflight read-only.** Operator changes into `D:\projetos_cli\pessoais\rpg_caminhada` in a shell. Operator verifies no existing `.cerebro/` directory is present at that root (fresh pilot). Operator reviews this recon doc.
2. **Confirm project choice.** Operator confirms `rpg_caminhada` is the chosen first pilot. If operator disagrees, stop and discuss.
3. **Bootstrap scan (non-authoritative).** Operator runs `cerebro bootstrap-scan --limit 8` from the project root. The scanner produces a shortlist from path/filename signals only. The shortlist is **not** a registration.
4. **Human chooses canonical sources.** Operator compares the scanner shortlist against the `must_import` / `maybe_import` classification in this doc. Operator selects the first explicit set, typically the four `must_import` files.
5. **`cerebro init`.** Creates the `.cerebro/` runtime directory at the project root. No canonical source is registered yet.
6. **`cerebro import-context --files ...`.** Operator passes explicit relative paths for the chosen canonical set. The command previews a diff and asks for `y` confirmation. Operator reviews and accepts.
7. **`cerebro checkpoint --goal ... --summary ... --next-step ...`.** Operator seeds the first checkpoint. Short, honest content: the state right now is "bootstrap; first pilot of Cerebro as third-party manager".
8. **`cerebro validate`.** Proves that the registered SHA-256s match the current files. This should be green immediately after step 6.
9. **`cerebro analyze`.** Runtime entrypoint; confirms that the daily flow works on this project.
10. **`python -m experiments.context_discovery.discovery` (or equivalent entry) against the project root.** Non-authoritative content-aware pass; produces a report showing candidates not registered, drift, and missing sources. Operator reviews.
11. **Human review of the report.** Operator records, in the pilot log (not in any runtime file), which suggestions were valuable, which were false positives, and what ergonomic frictions appeared.
12. **Daily use for N days.** Operator uses `cerebro analyze` + `cerebro checkpoint` at real session boundaries. No feature work on Cerebro during this period.

## Stop Conditions

The pilot should stop (and this recon should be treated as ineligible for promotion) if any of the following is observed before running `cerebro init`:

- The operator does not have write access to the target project root.
- A pre-existing `.cerebro/` directory is found at the target root and its provenance is unknown.
- The target project contains files whose path or filename alone reveals third-party personal data (this is already why the `escritorio` candidate was rejected).
- The operator realizes the target project is on an active production deadline and cannot absorb the novelty cost of learning the Cerebro flow.
- Any currently-pending Cerebro slice (for example task #8 — the 2b.1 compaction full gate on Windows) has not yet been confirmed green. Do not open a new frente while an earlier one is formally unclosed.

## Questions For Codex / Human

These are the open questions I could not answer from read-only recon alone. The operator and Codex (working on the protocol/runbook side) should resolve them before step 5:

1. **Scope of the pilot.** Is the pilot scope "one project under active solo development" or "multiple projects registered simultaneously in the global `~/.cerebro/projects.toml` registry"? My reading is the former; confirm.
2. **Runbook ownership of the scanner gap.** The known gap is that `bootstrap-scan` is filename-and-path-only; the pilot's step 4 relies on the operator manually bridging the gap. Is that acceptable for the first pilot, or does Codex want to run `experiments/context_discovery/` before `import-context` and merge both outputs for the human decision?
3. **Pilot log location.** Where does the pilot report land? I recommend outside the target project (to avoid polluting `rpg_caminhada`) and outside the Cerebro repo (to avoid implicit promotion of a pilot-specific doc into Cerebro's canonical docs). A local `D:\projetos_cli\_pilot_logs\rpg_caminhada_pilot_2026-04-XX.md` convention would keep auditability without leaking into either side.
4. **Rollback plan if `validate` fails.** If the owner edits a registered source during daily use and `validate` fails, is the default response "re-register via `import-context`" (my recommendation) or "rollback the source edit"? The former respects user agency and is the auditability-correct path; confirm.
5. **Cross-check with pending task #8.** Before any live pilot runs, task #8 (2b.1 compaction full gate on Windows) should close green. If it does not, the operating snapshot is still considered blocked, and opening a third-party pilot on top of a blocked internal state violates the "no new slice before the gate" rule. Confirm this ordering.
6. **Does Codex intend to write `FORMAL_RESUME_TRIGGER_THIRD_PARTY_PILOT.md` as a narrow-scope trigger for the pilot itself, or as a documentation-only marker that the pilot is authorized without reopening the freeze?** I assumed the latter, but this recon does not depend on that choice.

---

No command was executed against any candidate project. No `.cerebro/` directory was created outside the Cerebro repository. No file was moved, deleted, or formatted. The deliverable is this recon document only. Formal integration with Codex's runbook/trigger and the operator's acceptance is the next step and belongs outside the scope of this frente.
