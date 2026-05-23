# Cleanup Proposal 2026-05-07

## Scope

This is an operational cleanup slice for local generated material only. It does
not open a runtime feature boundary, does not mutate `.cerebro/`, does not touch
`core/`, `cli/`, `extensions/`, `tests/`, or `.git/`, and does not delete source
evidence.

The cleanup uses quarantine moves first. Final deletion is a later human
decision after the retention window.

## Current Evidence

- Initial AGENTS-equivalent gate on 2026-05-07: `958` tests, `0` failures,
  `0` errors, `6` skips.
- Canonical reference grep before move found no literal references to
  `_local/root_cleanup_2026-04-24/repo_root_artifacts/.tmp_` in `docs/`,
  `core/`, `cli/`, `tests/`, `extensions/`, `experiments/`, `AGENTS.md`, or
  `README.md`.
- Phase 1 targets are ignored by Git through `.gitignore` rule `_local/`.
- Phase 2 target `cerebro-workingtree-backup-20260428/` is not ignored by Git
  today and appears as local untracked material.
- Mechanical inventory is outside Git at
  `_local/cleanup_inventory_2026-05-07.csv`.

## Inventory Policy

The inventory columns are:

```text
path,size_bytes,mtime,sha256_or_null,phase,action
```

Hashing is escalated rather than exhaustive:

- directory target rows carry `manifest:<sha256>` over sorted child
  `path + size + mtime`;
- files over `10 MB` carry full SHA-256 content hashes;
- smaller files carry `path + size + mtime` only.

This is sufficient for drift detection between inventory and move. The
quarantine preserves the content; the hash is not the archive.

## Quarantine

Quarantine path:

```text
D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07
```

The quarantine stays on the same drive as the repository so Windows `Move-Item`
can use same-volume rename semantics instead of cross-drive copy plus delete.

Retention policy:

- keep quarantine for `14` days after both an AGENTS-equivalent gate and the
  broken-reference tripwire remain clean;
- require human reconfirmation before final delete;
- if a later operational round depends on a quarantined path, restore the
  affected phase from quarantine and stop.

## Phase 1 - Active `_local` Scratch Caches

Targets:

```text
_local/root_cleanup_2026-04-24/repo_root_artifacts/.tmp_perf_cache
_local/root_cleanup_2026-04-24/repo_root_artifacts/.tmp_sandbox
_local/root_cleanup_2026-04-24/repo_root_artifacts/.tmp
```

Measured total: `3,564,174,983` bytes.

Risk classification: low operational risk. These are generated scratch/cache
surfaces under ignored `_local/`, but they are quarantined rather than deleted.

Execution:

```powershell
$q = 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase1'
New-Item -ItemType Directory -Force -Path $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts\.tmp_perf_cache' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts\.tmp_sandbox' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts\.tmp' -Destination $q
```

Post-phase gates:

```powershell
rg -n --fixed-strings "_local/root_cleanup_2026-04-24/repo_root_artifacts/.tmp_" docs core cli tests extensions experiments AGENTS.md README.md
# then run the AGENTS-equivalent unittest runner
```

Abort if:

- any target path changed since inventory;
- any canonical reference depends on the moved paths;
- the AGENTS-equivalent gate fails after move.

## Phase 2 - Working Tree Mirror

Target:

```text
cerebro-workingtree-backup-20260428
```

Measured total: `6,760,865,756` bytes.

Risk classification: low to medium. It is a full local mirror from 2026-04-28,
not canonical Git history. Before moving it, check recent history and handoff
references.

Pre-checks:

```powershell
git log --since=2026-04-28 --oneline --decorate
rg -n --fixed-strings "cerebro-workingtree-backup-20260428" docs AGENTS.md README.md
```

Execution:

```powershell
$q = 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase2'
New-Item -ItemType Directory -Force -Path $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\cerebro-workingtree-backup-20260428' -Destination $q
```

Post-phase gates:

```powershell
rg -n --fixed-strings "cerebro-workingtree-backup-20260428" docs AGENTS.md README.md
# then run the AGENTS-equivalent unittest runner
```

Abort if:

- a handoff or current operational doc references the mirror as live evidence;
- the AGENTS-equivalent gate fails after move.

## Phase 3 - Parent-Level Legacy Validation Rounds

Targets:

```text
_local/root_cleanup_2026-04-24/parent_level_cerebro_legacy/cerebro_sandbox_validacao
_local/root_cleanup_2026-04-24/parent_level_cerebro_legacy/cerebro.zip
_local/root_cleanup_2026-04-24/parent_level_cerebro_legacy/cerebro-backup-20260411-001153.git
_local/root_cleanup_2026-04-24/parent_level_cerebro_legacy/cerebro-postrewrite-20260411-001430.git
_local/backup_pre_cleanup/repo-pre-cleanup-20260411-000727.zip
```

Do not move the parent containers
`_local/root_cleanup_2026-04-24/` or `_local/backup_pre_cleanup/` in this phase:
tracked docs reference those local preservation categories. Only the legacy
children listed above move to quarantine.

Measured total before move: approximately `2.71 GiB`.

Risk classification: medium-low. The validation rounds and archive bundles are
old local safety/experiment surfaces, not active runtime input. They are still
quarantined rather than deleted because some markdown reports may be useful for
future historical comparison.

Additional preservation:

- keep `_local/root_cleanup_2026-04-24/MANIFEST.md` in place;
- append a local manifest note that these children moved to Phase 3 quarantine;
- copy selected markdown summaries to
  `_local/cleanup_preserved_reports_2026-05-07/phase3/` before moving.

Inventory:

```text
_local/cleanup_inventory_phase3_2026-05-07.csv
```

Execution:

```powershell
$q = 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3'
New-Item -ItemType Directory -Force -Path $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy\cerebro_sandbox_validacao' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy\cerebro.zip' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy\cerebro-backup-20260411-001153.git' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy\cerebro-postrewrite-20260411-001430.git' -Destination $q
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\backup_pre_cleanup\repo-pre-cleanup-20260411-000727.zip' -Destination $q
```

Post-phase gates:

```powershell
rg -n "cerebro_sandbox_validacao|cerebro\\.zip|cerebro-backup-20260411-001153|repo-pre-cleanup-20260411-000727" docs AGENTS.md README.md
# then run the AGENTS-equivalent unittest runner
```

Rollback:

```powershell
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3\cerebro_sandbox_validacao' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3\cerebro.zip' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3\cerebro-backup-20260411-001153.git' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3\cerebro-postrewrite-20260411-001430.git' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase3\repo-pre-cleanup-20260411-000727.zip' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\backup_pre_cleanup'
```

## Tripwire Follow-Up - Repo-Root Scratch Remnants

After `LOCAL_ARTIFACT_TRIPWIRE.ps1` was introduced, it surfaced five
repo-root scratch directories that were small but still outside the declared
local lifecycle:

- `.tmp_browser/`
- `.tmp_operational_signals_suggestions_tests/`
- `.tmp_operational_signals_tests/`
- `.tmp_recall_eval/`
- `.tmp_recall_eval_tests/`

These were moved, not deleted, into:

```text
_local_cleanup_quarantine_2026-05-07/phase4_root_scratch/
```

The inventory for this follow-up lives at:

```text
_local/cleanup_inventory_root_scratch_2026-05-07.csv
```

Note: `.tmp_recall_eval/` is a regenerable experimental cache root referenced
by `experiments/recall_eval/indexer.py`; the reference identifies the producer,
not a canonical dependency on the existing bytes.

## Phase 4 - External Archive Ingest

Phase 4 moved evidence/reference bytes out of the repo and into external
archive packages. This was not a quarantine/delete flow: the material is
important, so the repo now keeps only pointer manifests and pre-move fixity
records.

Executed packages:

```text
D:\projetos_cli\ambiente_cerebro\arquivo_biblioteca_tecnica\biblioteca_fontes\
D:\projetos_cli\ambiente_cerebro\arquivo_pioneira\evidencia_2023\estoque_pioneira_bootstrap_real\
```

Each package contains:

```text
data/
METADATA.toml
README.md
CHAIN_OF_CUSTODY.md
manifest-sha256.csv
```

Repo-side pointers:

```text
_local/biblioteca_fontes_MANIFEST.md
_local/sandbox/estoque_pioneira_bootstrap_real_MANIFEST.md
```

Pre-move manifests:

```text
_local/phase4_cluster_a_biblioteca_fontes_pre_sha256.csv
_local/phase4_cluster_b_pioneira_evidence_pre_sha256.csv
```

Verification:

- Cluster A: `18` files, `142.96 MiB`, SHA-256 pre/post move matched.
- Cluster B: `174` files, `9.86 MiB`, SHA-256 pre/post move matched.

## No Double Counting

Phase 1 only targets active `_local/` cache directories. It intentionally does
not move matching cache directories inside `cerebro-workingtree-backup-20260428/`
because Phase 2 moves the mirror as one unit.

Expected quarantine total for Phase 1 plus Phase 2:

```text
10,325,040,739 bytes
```

## Rollback

Rollback is a same-volume move from quarantine back to the original parent path.

Phase 1 rollback:

```powershell
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase1\.tmp_perf_cache' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase1\.tmp_sandbox' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts'
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase1\.tmp' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts'
```

Phase 2 rollback:

```powershell
Move-Item -LiteralPath 'D:\projetos_cli\ambiente_cerebro\cerebro\_local_cleanup_quarantine_2026-05-07\phase2\cerebro-workingtree-backup-20260428' -Destination 'D:\projetos_cli\ambiente_cerebro\cerebro'
```

## Decision

Proceed sequentially:

1. Move Phase 1 to quarantine.
2. Run canonical-reference grep and AGENTS-equivalent gate.
3. If green, run Phase 2 pre-checks.
4. Move Phase 2 to quarantine only if pre-checks do not show a live dependency.
5. Run reference grep and AGENTS-equivalent gate again.
6. Keep quarantine for 14 days, then request explicit human approval before
   final deletion.
