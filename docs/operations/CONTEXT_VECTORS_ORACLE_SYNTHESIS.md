# Context Vectors Oracle Synthesis

Date: 2026-04-24

## Status

`experiments/context_vectors/` is mature enough to feed an LLM-facing advisory report layer.

It is not mature enough to become canonical runtime behavior, an automatic importer, or a state-mutating context authority.

## Evidence Set

| Oracle | Corpus role | Cases | Recall@1 | Recall@3 | Result |
| --- | --- | ---: | ---: | ---: | --- |
| `rpg_caminhada` | small project with human-curated continuity oracle | 4 | 1.000 | 1.000 | pass |
| `cerebro_self` | own repo with operational docs, code, tests, and local archives | 4 | 0.500 | 1.000 | pass |
| `portal_humaita` | dense third-party fiscal project with live, historical, temp, and nested legacy-Cerebro material | 6 | 0.500 | 1.000 | pass |
| `escritorio_irpf_caixa_rural` | office corpus with XML/PDF/binary noise, system docs, contributor docs, and client-specific maps | 6 | 1.000 | 1.000 | pass |

Aggregate:

- total oracle cases: `20`
- top-1 hits: `15/20`
- top-3 hits: `20/20`
- aggregate recall_at_1: `0.750`
- aggregate recall_at_3: `1.000`
- target/project mutation: `none`
- state_change across reports: `none`

## Failure Classes Discovered During Execution

### 1. Stale bootstrap continuity

Observed in `rpg_caminhada`.

Risk: a stale initial diagnosis could make an agent believe schema/formula work was still pending when the real next step was Edge Functions/Supabase validation.

Fix captured by oracle: the `next-real-work` query must surface `cerebro_base/04_MEMORIA_CONTINUIDADE_ATUAL.md` within top 3.

### 2. Local archive dominance

Observed in the Cerebro self-oracle.

Risk: `_local/legacy` material could outrank the current operational state.

Fix implemented: `_local/` is excluded from indexing.

### 3. Historical/temp/nested-Cerebro dominance

Observed in Portal Humaita.

Risk: `90_HISTORICO_*`, `98_TEMPORARIOS_*`, paths containing historical material, or an embedded old `cerebro/` methodology folder could compete with the live panel, canon, and current dossier.

Fix implemented: archival/temp/nested-Cerebro directory classes are excluded, and live-surface metadata cues lift current entry/status/canon surfaces.

### 4. Binary/XML/PDF scan starvation

Observed in Escritorio IRPF/Caixa Rural.

Risk: `max_files` could be exhausted by unsupported PDFs, XMLs, DBKs, or other non-indexable files before the scan reached later operational markdown surfaces.

Fix implemented: `max_files` counts indexable text candidates, not every filesystem entry encountered.

### 5. Deep artifact dominance over shallow system surfaces

Observed in Escritorio IRPF/Caixa Rural.

Risk: internal method docs or client-specific maps could outrank shallow README/index surfaces for broad "system", "registry", or "master organization" queries.

Fix implemented: bounded metadata cues lift shallow general README/index surfaces when the query asks for system, registry, master, organization, or general structure.

## What This Proves

- Sparse deterministic vectors plus bounded metadata cues are enough to find the right operational surface across four materially different real corpora.
- The current layer is useful as an advisory context-selection assistant.
- The layer is especially valuable at the start of a project session, where the main failure mode is opening a plausible but stale or overly specific file.
- The experiment now has real regression pressure, not only synthetic unit tests.

## What This Does Not Prove

- It does not prove that vector retrieval should mutate `.cerebro/state.json`.
- It does not prove that top-1 accuracy is high enough for autonomous source registration.
- It does not prove semantic understanding; the system is still deterministic sparse retrieval plus metadata heuristics.
- It does not replace human approval of canonical context.

## Decision

Promote `context_vectors` only one step:

- from: experiment with isolated oracle reports
- to: LLM-facing advisory report layer under `experiments/`

Do not promote it into `core/`, `cli/`, `extensions/`, or automatic source import.

The next useful product shape is a combined advisory report that joins:

- `context_discovery`: what changed, drifted, or is missing
- `context_vectors`: which files look most relevant to current operator intent
- oracle-style trace: why each candidate is being surfaced

## Next Slice

Create an LLM-facing combined report under `experiments/context_advisor/` or equivalent derived namespace.

Required properties:

- read-only
- local-only
- no network
- no canonical mutation
- emits Markdown report
- takes a project root and a small list of operator intents
- includes both file-system discovery and ranked relevance evidence
- keeps `state_change: none`

This is now higher leverage than adding more standalone oracles.
