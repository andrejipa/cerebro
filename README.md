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

This repository surface is the official visual baseline for human navigation.
Do not reorganize it for style alone. Change it only if a concrete navigation or operational problem is demonstrated.

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

Two directories matter:

- **Cerebro repository root**: install Cerebro here; the local `venv\` and `cerebro.exe` live here
- **target project root**: use Cerebro here; `.cerebro\` is created here and all runtime commands operate here

If those are different directories, that is normal.
If you only read one thing, read this: install Cerebro in the Cerebro repository root, then change into the target project root before running `init`, `import-context`, `checkpoint`, `validate`, `analyze`, or any export.
Do not run `init`, `import-context`, `checkpoint`, `validate`, `analyze`, or any export from the Cerebro repository unless that repository is itself the project you want to track.

Recommended on Windows PowerShell:

```powershell
powershell -ExecutionPolicy Bypass -File .\docs\operations\install-cerebro.ps1
```

The installer script:

- checks for Python 3.11 or newer
- creates a local `venv\`
- installs Cerebro into that local environment
- validates the installed CLI with `cerebro --help`

Typical Windows layout:

```text
C:\tools\cerebro          <- install Cerebro here
D:\work\my-project        <- use Cerebro here
```

After the script finishes, either activate `venv\Scripts\Activate.ps1` from the Cerebro repository root and then use `cerebro` in the target project root, or call `venv\Scripts\cerebro.exe` directly.

## First Successful Run

If this is your first contact with Cerebro, ignore exports and advanced operational docs until this sequence succeeds once:

```powershell
cerebro init
cerebro import-context --files README.md pyproject.toml path\to\current-work.md
cerebro checkpoint --goal "..." --summary "..." --next-step "..."
cerebro validate
cerebro analyze
```

Use this sequence from the **target project root**, not from the Cerebro repository root.
Read it as two steps:

1. install Cerebro once in the Cerebro repository root
2. run the basic flow above from the target project root

If `analyze` or `validate` says that no sources are registered yet, the next command is `cerebro import-context --files ...`.

Manual fallback for operators who already manage their own Python environment:

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
`validate` only passes after at least one source is explicitly registered.
That first bootstrap `checkpoint` seeds the canonical checkpoint before the normal daily session flow exists.
`import-context` previews a sources diff and requires `y` confirmation before replacing the registered set.
Run bootstrap from the target project root.

For the first `import-context`, choose a small explicit set of human-maintained files:

- one project-definition file such as `README.md`, `pyproject.toml`, `package.json`, `go.mod`, or `Cargo.toml`
- one or two files that describe the current work, operating rules, or current project state
- never generated files, exports, logs, caches, backups, vendored libraries, or build output

Minimal first import example in a Python project:

```powershell
cerebro import-context --files README.md pyproject.toml path\to\current-work.md
```

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
- answer first whether the work is in `cerebro` or in a `caso`
- classify the problem as `comprovado`, `provavel`, or `hipotese`
- do not advance if evidence is not strong enough
- if more than one path exists, compare risk, reversibility, approval burden, and verification burden before deciding
- submit any risky slice to the approval boundary when policy requires it
- execute only the approved and properly scoped slice
- verify the result and audit the practical outcome
- finish with `cerebro checkpoint`
- record the expected tracing for the round as operational discipline

`cerebro analyze` is the official runtime entrypoint for continuity flow.
`cerebro resume` remains available for compatibility, but it is not the recommended surface.
After the first checkpoint seed exists, `cerebro checkpoint` is valid only for a round that already has an active local session.
Use the canonical CLI command names as documented; do not rely on aliases or synonyms.
Any daily use that skips this flow is operationally invalid.
Treat that invalidity as a protocol mismatch in operational records, not as CLI-enforced runtime invalidation.

## Operating It

Use the approved operational baseline in [docs/operations/OPERATIONS_BASELINE.md](docs/operations/OPERATIONS_BASELINE.md).

- runtime entry mode `bootstrap`: `bootstrap-scan` if needed, then `init -> import-context -> checkpoint -> validate`
- runtime entry mode `continuous work`: start with `cerebro analyze`, finish with `cerebro checkpoint`
- external protocol rounds: use agents and the automation bridge only as external helpers, record one round intent label (`ENGINEERING`, `OPERATION`, `BREAKING`, or `CERTIFICATION`), then return to Cerebro through `checkpoint` and `analyze`

## Evolution State

The current approved operational surface is complete for the current demand.
A real gap must be measured against the runtime, the seven read-only exports, and the currently approved external helpers within their explicit non-authoritative boundaries.
A final multi-role closure review closed the last safe external gaps and confirmed that no additional safe autonomous capability growth remains inside the current contract.

The project is deliberately frozen for new capability growth until a concrete and repeated use case justifies opening the next layer explicitly.
Any future growth must enter through one minimum safe external increment at a time, not by automatic continuation.
In the absence of such a use case, the correct action is to operate the system, not evolve it.

This freeze does not mean total inactivity. It means no new increment is currently authorized for the canonical runtime surface.

Outside that canonical surface, the repository may still carry approved derived tracks that remain explicitly non-authoritative. The current examples are:

- `experiments/recall_eval/`: implemented and benchmarked; archived — lexical baseline matched or beat embeddings; kept as historical evidence
- `experiments/operational_signals/`: opt-in derived observability track for operational insufficiency signals; advisory-only, records outside `.cerebro/`
- `experiments/context_discovery/`: derived content-aware discovery track; reports candidates not registered, drift on registered sources, and missing registered sources; non-authoritative, never mutates `.cerebro/`
- `experiments/context_vectors/`: deterministic local vector-search experiment; indexes bounded textual heads, returns ranked query hits with trace metadata; `recall_at_3=1.000` on 20 real oracle cases
- `experiments/context_advisor/`: LLM-facing advisory report combining `context_discovery` and `context_vectors` evidence; emits structured Markdown with `may_suggest` / `must_not_apply` boundaries
- `experiments/claim_extraction/`: deterministic claim-candidate extraction; emits `ClaimCandidate` units with authority and criticality hints; never builds a claim graph or mutates state
- `experiments/claim_evaluation/`: bounded advisory evaluator over `ClaimCandidate` inputs; evaluates authority, confidence, sufficiency, conflict, and operational readiness
- `experiments/epistemic_readiness/`: advisory report generator for epistemic-readiness assessment over explicit source manifests; read-only, never gates the runtime
- `experiments/epistemic_guard/`: deterministic advisory decision-envelope oracle for concrete action questions; evaluates evidence quality and approval status without modifying state
- `experiments/drift_detection/`: AST-based structural drift detector for `core/`, `cli/`, and `extensions/`; captures baseline snapshots and reports added, modified, and removed Python modules; includes deterministic staleness scoring (time + structural changes formula); never writes to `.cerebro/`
- `experiments/checkpoint_semantic_diff/`: deterministic Jaccard token-overlap scorer between checkpoint text and registered source content; classifies semantic alignment as high/medium/low/unavailable; never writes to `.cerebro/`
- `experiments/third_party_trigger_review/`: advisory checker for proposed third-party project triggers; reviews for completeness, boundary safety, and consolidation risk

Those derived tracks do not change the core freeze posture, do not create canonical state, and do not reopen architecture by themselves.

## Runtime Files

- `.cerebro/state.json`
- `.cerebro/session.local.json`
- `.cerebro/runtime.lock`
- `.cerebro/logs/events.jsonl`

`state.json` and `session.local.json` are the only persisted runtime inputs that define business continuity.
`runtime.lock` is a transient coordination file used while the core serializes concurrent mutations.
`events.jsonl` remains a non-canonical operational artifact.

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
Treat the current root layout and `docs/` segmentation as stable. New material must fit one of the existing areas or stay in ignored local space.
