# Cleanup Phase 4 Runbook

This runbook records the move of remaining locally held evidence and reference
material into an external archive, leaving only small repo-side manifests
behind.

The move was executed on 2026-05-07 after explicit human approval in the
cleanup thread. No delete was performed. The executed form used archive
packages with `data/`, `METADATA.toml`, `README.md`, `CHAIN_OF_CUSTODY.md`,
and `manifest-sha256.csv`.

This runbook is consistent with `LOCAL_ARTIFACT_RETENTION_POLICY.md` (rule 5:
"evidence has its canonical home outside the repo") and with
`CLEANUP_PROPOSAL_2026-05-07.md` (sequential, quarantine-or-move-first
discipline).

## Status Going Into Phase 4

Phases 1–3 already moved roughly 12.32 GiB of repo weight into
`_local_cleanup_quarantine_2026-05-07/` under a 14-day retention window.
Active scratch caches, the workspace mirror, and parent-level legacy bundles
are out of the active path.

A read-only inventory taken on 2026-05-07 (after Phase 3) found that the
remaining locally held evidence and reference material outside quarantine is
small in comparison: roughly **204.8 MiB across 133 files**. The breakdown:

```
PDFs : 143.3 MiB in  34 files
CSVs :  59.2 MiB in  79 files
XLSX :   2.3 MiB in  20 files
ZIPs :   0.0 MiB in   0 files
```

Most of that weight is concentrated in four well-defined clusters described
below.

## Inventory Clusters

### Cluster A — Technical reference library

```
_local/biblioteca_fontes/   ~ 143 MiB, 18 PDFs
```

Content shape: third-party engineering and computer-science books
(distributed systems, software architecture, type theory, OS internals).
Not project-specific. Not evidence of any audit. Reference material.

Retention class under `LOCAL_ARTIFACT_RETENTION_POLICY.md`: closest to
`evidence` because the bytes are not regenerable on demand, but the canonical
home is an external archive, never the repo.

Executed destination:

```text
D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes\data\biblioteca_fontes
```

Fixity:

```text
D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes\manifest-sha256.csv
```

### Cluster B — Active fiscal evidence (Pioneira)

```
_local/sandbox/estoque_pioneira_bootstrap_real/   ~ 4.3 MiB
```

Content shape: fiscal audit material for the Pioneira inventory case
(`LISTA_MESTRA_LASTRO`, `TABELA_FISCAL_RESSALVAS`, EFD retification, audit
narratives). This is the surviving live counterpart of material already in
Phase 3 quarantine.

Retention class: `evidence`. External archive home, repo-side manifest only.

Executed destination:

```text
D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real\data\estoque_pioneira_bootstrap_real
```

Fixity:

```text
D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real\manifest-sha256.csv
```

### Cluster C — Operational cleanup inventories

```
_local/cleanup_inventory_2026-05-07.csv         ~ 32.1 MiB
_local/cleanup_inventory_phase3_2026-05-07.csv  ~ 12.6 MiB
```

Content shape: mechanical inventory CSVs produced by Phases 1–3 of this
cleanup round. Operational metadata, not external evidence.

Retention class: `report_capsule`. Default lifetime 90 days from creation, so
`retention_until = 2026-08-05`. Reviewed on that date and either preserved
under a written rationale or removed.

### Cluster D — Internal duplication in `_local/legacy/`

```
_local/legacy/quarantine/...   ~ 8.6 MiB
_local/legacy/archive/...      ~ 4.3 MiB
```

Content shape: four exact copies of Pioneira bootstrap material spread across
`legacy/quarantine/seq1`, `legacy/quarantine/seq2`, `legacy/archive`, and
`sandbox/estoque_pioneira_bootstrap_real` (the live one in Cluster B). The
copies in `legacy/` are pure redundancy and were not captured by Phase 3
because they live under a different parent (`_local/legacy/`, not
`_local/root_cleanup_2026-04-24/`).

This is internal redundancy, not external evidence. It is out of scope for
Phase 4 and is parked for a separate Phase 5 round.

## Phase 4 Decisions

| Cluster | Action | Destination | Notes |
|---|---|---|---|
| A — biblioteca_fontes | moved-not-deleted | `D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes\` | external archive; SHA-256 verified |
| B — Pioneira evidence | moved-not-deleted | `D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real\` | external archive; SHA-256 verified |
| C — cleanup inventories | hold in place + manifest | `_local/cleanup_inventory_*.csv` (no move) | `report_capsule`, `retention_until = 2026-08-05` |
| D — `legacy/` redundancy | defer to Phase 5 | — | separate runbook, separate round |

## Preconditions

Before any Phase 4 move, all of the following must hold and be recorded:

1. AGENTS-equivalent gate green: `958 / 0 / 6` or current canonical baseline,
   measured on the same shell that will execute the moves.
2. Broken-reference tripwire clean for the source paths:

   ```powershell
   rg -n --fixed-strings "_local/biblioteca_fontes" docs core cli tests extensions experiments AGENTS.md README.md
   rg -n --fixed-strings "_local/sandbox/estoque_pioneira_bootstrap_real" docs core cli tests extensions experiments AGENTS.md README.md
   ```

   Hits inside `LOCAL_ARTIFACT_RETENTION_POLICY.md`,
   `CLEANUP_PROPOSAL_2026-05-07.md`, `CLEANUP_PHASE4_RUNBOOK.md`, and the
   manifests added by this round are expected and do not block. Hits anywhere
   else block until reviewed.

3. External destination drive present and writable. The default destination
   root is on `D:\` so the paths share a volume with the repo; this matters
   for atomicity of `Move-Item` on the source side and is not required on the
   destination side because the operation across volumes is allowed to take
   the slower copy-plus-delete path with explicit verification.

4. External destination directories already exist and are empty for this
   round, or contain only prior Phase 4 imports under a clear subfolder
   structure.

5. The `LOCAL_ARTIFACT_RETENTION_POLICY.md` document is in place and the
   manifests written by this round comply with its required-fields contract.

## Execution

Execution is per cluster, sequential. Each cluster is one round: move, gate,
tripwire, manifest, then proceed to the next.

### Cluster A — biblioteca_fontes

Default destination layout:

```
D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\
    biblioteca_fontes\
    MANIFEST.md
```

Move command:

```powershell
$src = 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\biblioteca_fontes'
$dst = 'D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes'
New-Item -ItemType Directory -Force -Path 'D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica' | Out-Null
Move-Item -LiteralPath $src -Destination $dst
```

Repo-side manifest left at the original parent:

```
D:\projetos_cli\ambiente_cerebro\cerebro\_local\biblioteca_fontes_MANIFEST.md
```

Manifest content (template):

```
# Local manifest — biblioteca_fontes

artifact_class      : evidence
owner               : andre.jipa
created_by          : CLEANUP_PHASE4_RUNBOOK.md (cluster A)
created_at          : 2026-05-07
retention_until     : indefinite-with-review-on:2027-05-07
delete_rule         : never deleted from external archive without explicit
                      written decision; the repo-side manifest may be removed
                      if and only if the external archive remains intact and
                      a canonical doc no longer cites it.
restore_rule        : copy or `Move-Item` from
                      D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes
                      back to D:\projetos_cli\ambiente_cerebro\cerebro\_local\biblioteca_fontes
canonical_reference : no

# Pointer
external_path       : D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes
size_at_move        : 143.3 MiB across 18 PDFs
notes               : third-party engineering reference library;
                      not project-specific evidence; not regenerable.
```

### Cluster B — Pioneira evidence

Default destination layout:

```
D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\
    evidencia_2023\
        estoque_pioneira_bootstrap_real\
    MANIFEST.md
```

Move command:

```powershell
$src = 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\sandbox\estoque_pioneira_bootstrap_real'
$dst = 'D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real'
New-Item -ItemType Directory -Force -Path 'D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023' | Out-Null
Move-Item -LiteralPath $src -Destination $dst
```

Repo-side manifest left at the original parent:

```
D:\projetos_cli\ambiente_cerebro\cerebro\_local\sandbox\estoque_pioneira_bootstrap_real_MANIFEST.md
```

Manifest content (template):

```
# Local manifest — estoque_pioneira_bootstrap_real

artifact_class      : evidence
owner               : andre.jipa
created_by          : CLEANUP_PHASE4_RUNBOOK.md (cluster B)
created_at          : 2026-05-07
retention_until     : indefinite-with-review-on:2027-05-07
delete_rule         : never deleted from external archive while the Pioneira
                      audit case remains open; closure is recorded in a
                      separate decision doc, not here.
restore_rule        : copy or `Move-Item` from
                      D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real
                      back to D:\projetos_cli\ambiente_cerebro\cerebro\_local\sandbox\estoque_pioneira_bootstrap_real
canonical_reference : no

# Pointer
external_path       : D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real
size_at_move        : 4.3 MiB
notes               : surviving live fiscal-evidence material for the
                      Pioneira inventory case; counterpart of the same
                      project's content already preserved in Phase 3
                      quarantine.
```

### Cluster C — cleanup inventories (no move)

These stay in place. The manifest declares their class and retention so the
next round does not re-handle them:

```
D:\projetos_cli\ambiente_cerebro\cerebro\_local\cleanup_inventory_2026-05-07_MANIFEST.md
D:\projetos_cli\ambiente_cerebro\cerebro\_local\cleanup_inventory_phase3_2026-05-07_MANIFEST.md
```

Manifest template:

```
# Local manifest — cleanup_inventory_<DATE>

artifact_class      : report_capsule
owner               : andre.jipa
created_by          : CLEANUP_PROPOSAL_2026-05-07.md (Phase 1–3 inventories)
created_at          : 2026-05-07
retention_until     : 2026-08-05
delete_rule         : remove on or after 2026-08-05 unless a written rationale
                      preserves it; rationale must cite a downstream use.
restore_rule        : not regenerable as bytes; rerun the inventory script if
                      a new round needs equivalent measurement.
canonical_reference : no

notes               : mechanical inventory of moves performed by
                      CLEANUP_PROPOSAL_2026-05-07.md; operational metadata
                      only; never canonical.
```

## Post-execution Per Cluster

After each cluster move:

1. Re-run the broken-reference tripwire on the source path. Expect zero
   non-self-cite hits.
2. Run the AGENTS-equivalent gate from `AGENTS.md`. Expect the baseline to
   stay green.
3. Update `CLEANUP_PROPOSAL_2026-05-07.md` with a Phase 4 entry recording
   what moved, where, and the gate result.
4. If anything fails or shows unexpected references, halt and use the rollback
   procedure below before proceeding to the next cluster.

## Rollback

Cluster A:

```powershell
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\biblioteca_fontes'
```

Cluster B:

```powershell
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\sandbox\estoque_pioneira_bootstrap_real'
```

Cluster C: nothing to roll back; the data did not move.

## Abort Criteria

Abort the round and roll back if any of the following are observed:

- the AGENTS-equivalent gate goes red after the move;
- the broken-reference tripwire shows a hit outside the documented self-cite
  set;
- the external destination is on a volume that becomes unavailable mid-move;
- the move command produces a partial result (the source still exists and the
  destination also exists for the same logical artifact);
- a canonical doc is found to cite the moved path during the round and was
  missed by pre-checks.

## Decision

This runbook authorizes only the plan, not the execution. The next operational
round may execute Cluster A, then Cluster B, then write the Cluster C
manifests, in that order. Cluster D is deferred to a separate Phase 5 runbook.

After Phase 4 closes:

- repo `_local/` weight drops by roughly 147.6 MiB (Clusters A + B);
- repo retains roughly 44.7 MiB of operational metadata under Cluster C with
  a documented expiration;
- external archives carry the moved evidence under explicit manifests on both
  ends.

The 14-day retention window for the Phase 1–3 quarantine continues
independently of Phase 4 and is not affected by these moves.

## Out Of Scope

- Final deletion of `_local_cleanup_quarantine_2026-05-07/` — separate
  decision after the 14-day retention window.
- Phase 5 consolidation of `_local/legacy/` redundancy — separate runbook.
- External archive layout, backup tooling, or storage topology beyond the
  paths used by this round.
- Any change to `core/`, `cli/`, `extensions/`, `tests/`, `experiments/`,
  `.cerebro/`, schema, `validate`, `analyze`, session policy, or canonical
  retention surfaces.
