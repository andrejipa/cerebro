# Cerebro Local Checkpoint

Minimal local checkpoint CLI for agent-assisted execution.

## Baseline

The repository history was rewritten on April 11, 2026.

- baseline commit after history cleanup: `4be0b08`
- the tracked repository now contains only the active product
- pre-cleanup history and heavy legacy material were removed from Git history

Any clone created before April 11, 2026 is obsolete and must not be merged back into this repository.

## Product Scope

This repository tracks only the active v1 product:

- `core/`: state, schema, validation, and read models
- `cli/`: command entrypoints and terminal output
- `extensions/`: optional product extensions
- `tests/`: automated regression suite used by CI
- `docs/adr/`: architecture decisions for the active product
- `views/`: product-facing view documentation
- `.github/`: CI workflows

Historical material, sandboxes, heavy source libraries, and local backups are intentionally excluded from versioned product scope.

## Re-Clone After History Rewrite

If you cloned the repository before April 11, 2026, discard that clone and create a new one.

```powershell
cd ..
git clone https://github.com/andrejipa/cerebro.git cerebro
cd cerebro
pip install -e .
python -m unittest discover -s tests -v
```

Do not merge, rebase, or cherry-pick from a pre-rewrite clone without explicitly auditing the files involved.

## What It Does

- stores a single local state file in `.cerebro/state.json`
- registers explicit context sources with SHA-256 hashes
- validates that registered sources still match
- stores a short operational checkpoint
- opens a local session through `cerebro analyze`

## What It Does Not Do

- it does not model the whole project
- it does not scan the repository
- it does not infer context automatically
- it does not replace Git, issues, or human communication

## Install

```powershell
pip install -e .
```

## Bootstrap Once

```powershell
cerebro init
cerebro import-context --files path\\to\\file.txt
cerebro checkpoint --goal "..." --summary "..." --next-step "..."
cerebro validate
```

Bootstrap a new instance once with `init`, `import-context`, `checkpoint`, and `validate`.

## Daily Flow

```powershell
cerebro analyze
cerebro checkpoint --goal "..." --summary "..." --next-step "..."
```

Normal daily flow after the instance already exists:

- start with `cerebro analyze`
- finish with `cerebro checkpoint`

`cerebro analyze` is the official runtime entrypoint for human and agent resume flow.
`cerebro resume` remains available for compatibility, but it is not the recommended surface.
Use the canonical CLI command names as documented; do not rely on aliases or synonyms.

## Runtime Files

- `.cerebro/state.json`
- `.cerebro/session.local.json`
- `.cerebro/logs/events.jsonl`

Only the first two affect runtime behavior.

## Out Of Repo Scope

The following categories are preserved only as local, ignored material when needed:

- `_legacy/`: old systems, historical scripts, and archived snapshots
- `_local/`: sandboxes, ad hoc experiments, and machine-local workspaces
- `_backup_pre_cleanup/`: local safety snapshots created before repository cleanup

These paths are not part of the active product and are not required for installation, tests, or CI.

## Repository Policy

Only the following belong in the tracked repository:

- product code in `core/`, `cli/`, and `extensions/`
- automated tests in `tests/`
- essential product documentation in `README.md`, `docs/adr/`, `views/`, and root architecture docs
- CI and packaging metadata such as `.github/`, `.gitignore`, and `pyproject.toml`

The following do not belong in tracked history:

- legacy systems, historical snapshots, or migration leftovers
- sandboxes, temporary workspaces, and local experiments
- source libraries, PDFs, spreadsheets, exports, or knowledge dumps
- generated artifacts, backups, and machine-local state

Keep auxiliary material outside the repository or inside ignored paths such as `_local/`, `_legacy/`, and `_backup_pre_cleanup/`.
