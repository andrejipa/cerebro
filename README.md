# Cerebro Local Checkpoint

Minimal local checkpoint CLI for agent-assisted execution.

Current status: operational infrastructure, not an open-ended build project.

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
- `docs/reference/`: contracts, specs, extension model, and stable reference material
- `.github/`: CI workflows

Historical material, sandboxes, heavy source libraries, and local backups are intentionally excluded from versioned product scope.

## Documentation Map

Read the repository in this order:

- `README.md`: project scope, entry flow, and daily use
- `docs/reference/`: stable contracts, runtime specs, and architectural boundaries
- `docs/operations/`: operational baseline, freeze policy, board, and agent protocol
- `docs/adr/`: architectural decisions behind the current shape
- `docs/handoffs/`: transition records, closures, and blocked fronts

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

## What The Runtime Does Not Do

- it does not model the whole project
- it does not scan the repository to define truth automatically
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

Optional assistive step before `import-context` in a new or unknown project:

```powershell
cerebro bootstrap-scan --root path\to\project
```

`bootstrap-scan` only suggests candidate entry files by path and filename signals. It is heuristic assistance, not project truth. It does not create `.cerebro`, does not register `sources`, and does not bypass the manual `import-context` decision.
It is not a resume command, not a truth gate, and not a substitute for the standard runtime entrypoint.
If you use `--root` from another directory, change into the target project before running `import-context`, `checkpoint`, `analyze`, or any export.

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

## Operating It

Use the approved operational baseline in [docs/operations/OPERATIONS_BASELINE.md](docs/operations/OPERATIONS_BASELINE.md).

- bootstrap mode: `bootstrap-scan` if needed, then `init -> import-context -> checkpoint -> validate`
- continuous work mode: start with `cerebro analyze`, finish with `cerebro checkpoint`
- audit / engineering mode: use agents and the automation bridge only as external helpers, then return to Cerebro through `checkpoint` and `analyze`

## Evolution State

The core runtime and the current read-only export surface are complete for the current demand.
A final multi-role closure review closed the last safe external gaps and confirmed that no additional safe executable work remains inside the current contract.

The project is deliberately frozen for new capability growth until a concrete and repeated use case justifies opening the next layer explicitly.
Any future growth must enter through one minimum safe external increment at a time, not by automatic continuation.
In the absence of such a use case, the correct action is to operate the system, not evolve it.

## Runtime Files

- `.cerebro/state.json`
- `.cerebro/session.local.json`
- `.cerebro/logs/events.jsonl`

Only the first two affect runtime behavior.

## Out Of Repo Scope

The following categories are preserved only as local, ignored material when needed:

- `_local/legacy/`: old systems, historical scripts, and archived snapshots
- `_local/`: sandboxes, ad hoc experiments, local tools, and machine-local workspaces
- `_local/backup_pre_cleanup/`: local safety snapshots created before repository cleanup

These paths are not part of the active product and are not required for installation, tests, or CI.

## Repository Policy

Only the following belong in the tracked repository:

- product code in `core/`, `cli/`, and `extensions/`
- automated tests in `tests/`
- essential product documentation in `README.md`, `docs/reference/`, `docs/operations/`, `docs/adr/`, and `docs/handoffs/`
- CI and packaging metadata such as `.github/`, `.gitignore`, and `pyproject.toml`

The following do not belong in tracked history:

- legacy systems, historical snapshots, or migration leftovers
- sandboxes, temporary workspaces, and local experiments
- source libraries, PDFs, spreadsheets, exports, or knowledge dumps
- generated artifacts, backups, and machine-local state

Keep auxiliary material outside the tracked product or inside ignored paths under `_local/`.
