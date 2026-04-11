# ADR-006: Repository History Cleanup Baseline

## Context

On April 11, 2026, the repository history was rewritten to remove legacy systems, sandboxes, heavy source libraries, generated artifacts, and other non-product material.

Before the rewrite, Git history still carried obsolete directories such as `_sandbox/`, `archive/`, `cerebro_base/`, `quarantine/`, and `biblioteca_fontes/`, even though the active product had already been isolated.

The product needs a permanent repository policy that keeps Git history small, keeps CI focused on the active system, and prevents heavy or legacy material from re-entering the tracked tree.

## Decision

Treat the post-rewrite repository as the permanent baseline for active development.

- The baseline history starts from the rewritten commit lineage published on April 11, 2026.
- The tracked repository is limited to active product code, tests, essential documentation, extension scaffolding, and CI or packaging metadata.
- Legacy material, local backups, experiments, and heavy auxiliary files must remain outside tracked history or inside ignored local paths.
- Repository hygiene is enforced through `.gitignore`, documentation, and automated tests that reject forbidden roots, binary office artifacts, and oversized tracked files.

## Consequence

- Old clones created before April 11, 2026 are no longer compatible and must be discarded or re-cloned.
- The repository remains lightweight and easier to clone, validate, and evolve.
- Introducing large binary assets or legacy directories now requires an explicit policy change rather than an accidental commit.
