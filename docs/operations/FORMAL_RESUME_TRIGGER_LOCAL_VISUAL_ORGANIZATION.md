# Formal Resume Trigger — Local Visual Organization

## Status

- `approved for execution on 2026-04-24 by explicit human request`
- `consumed / completed on 2026-04-24 — full AGENTS-equivalent gate stayed green: 923 tests, 0 failures, 0 errors, 6 skips`
- reason: the repository root and parent project folder contain local temporary artifacts, old Cerebro backups, and visual clutter that make human navigation harder.

## Objective

Make the Cerebro workspace visually navigable for humans without deleting evidence, changing canonical runtime behavior, or treating local cleanup as product work.

## Boundary

Allowed:

- move local-only, ignored, generated, cache, sandbox, and legacy Cerebro artifacts from `D:\projetos_cli\cerebro\` into `D:\projetos_cli\cerebro\_local\root_cleanup_2026-04-24\repo_root_artifacts\`
- move old Cerebro-specific sibling artifacts from `D:\projetos_cli\` into `D:\projetos_cli\cerebro\_local\root_cleanup_2026-04-24\parent_level_cerebro_legacy\`
- create a local manifest under `D:\projetos_cli\cerebro\_local\root_cleanup_2026-04-24\`
- update `SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, and this trigger with the result

Explicitly out of scope:

- any deletion
- any mutation to `.cerebro/state.json`
- any move or edit under `core/`, `cli/`, `tests/`, `experiments/`, `extensions/`, `.git/`, `.github/`, `.codex/`, `.cerebro/`, or `docs/` except this trigger and the two live snapshots
- moving active sibling projects such as `escritorio`, `estoque_pioneira`, `pessoais`, `Portal`, `Games`, `Jogos`, or `SteamLibrary`
- changing AGENTS gate semantics or temp directory policy

## Stop Conditions

Stop immediately if:

- the pre-cleanup AGENTS-equivalent gate is not green
- any candidate move is git-tracked
- a destination already exists and would overwrite existing data
- a move would cross outside the explicit source and destination roots above
- the post-cleanup AGENTS-equivalent gate is not green

## Acceptance

- repository root is reduced to live project surfaces plus unavoidable local control folders
- all moved artifacts are preserved under `_local/root_cleanup_2026-04-24/`
- a manifest records original and final paths
- AGENTS-equivalent gate remains green
- live snapshots state that this was local visual organization only, not runtime evolution

## Outcome

- moved repo-root generated/cache/sandbox artifacts into `_local/root_cleanup_2026-04-24/repo_root_artifacts/`
- moved old Cerebro-specific parent-level backups into `_local/root_cleanup_2026-04-24/parent_level_cerebro_legacy/`
- preserved all moved data; no deletion was performed
- left active control/project surfaces in place: `.cerebro/`, `.codex/`, `.git/`, `.github/`, `.obsidian/`, `.worktrees/`, `venv/`, `cli/`, `core/`, `docs/`, `experiments/`, `extensions/`, `instrucoes/`, and `tests/`
- did not move active sibling projects from `D:\projetos_cli\`
- local manifest: `_local/root_cleanup_2026-04-24/MANIFEST.md`
