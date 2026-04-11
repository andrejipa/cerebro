# Cerebro Local Checkpoint

Minimal local checkpoint CLI for agent-assisted execution.

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

## What It Does

- stores a single local state file in `.cerebro/state.json`
- registers explicit context sources with SHA-256 hashes
- validates that registered sources still match
- stores a short operational checkpoint
- opens a local session on `resume`

## What It Does Not Do

- it does not model the whole project
- it does not scan the repository
- it does not infer context automatically
- it does not replace Git, issues, or human communication

## Install

```powershell
pip install -e .
```

## Basic Flow

```powershell
cerebro init
cerebro import-context --files path\\to\\file.txt
cerebro checkpoint --goal "..." --summary "..." --next-step "..."
cerebro resume
cerebro validate
```

Normal daily flow:

- start with `cerebro resume`
- finish with `cerebro checkpoint`

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
