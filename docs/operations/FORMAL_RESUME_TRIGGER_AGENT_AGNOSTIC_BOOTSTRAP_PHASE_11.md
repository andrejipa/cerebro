# Formal Resume Trigger — Agent-Agnostic Bootstrap (Phase 11)

## Status

- status: consumed
- consumed_at: 2026-05-09
- gate: 2425 passed / 0 failures / 6 skipped (pre-Phase-11 baseline)
- schema: v15 (unchanged)

## Boundary

This trigger authorizes exactly the following work inside the cerebro repo:

1. Create `cli/project_root.py` — walk-up project root detection helper.
2. Evolve `cli/commands/init.py` — multi-agent scaffold creation + `--repair-scaffold` mode.
3. Add `--repair-scaffold` flag to the `init` subparser in `cli/main.py`.
4. Integrate walk-up root detection into `cli/main.py` dispatcher.
5. Create `AGENTS.md` template, `observation_center.toml` template, `SYSTEM_STATE.md`
   template, and `OPPORTUNITY_MAP.md` template used by `cerebro init`.
6. Add Phase 11 tests to `tests/test_cli.py` and `tests/test_architecture.py`.
7. Update `docs/operations/RUNTIME_MANAGER_CONTRACT.md`, `AGENTS.md` (this repo),
   `CLAUDE.md` (this repo), and operational docs.
8. Archive the `agent-agnostic-bootstrap-phase-11` observation.

## Hard Limits (never cross)

- Do NOT generate `CLAUDE.md` in any managed project (template or runtime).
- Do NOT make `CLAUDE.md` appear in `authority_order` as a requirement.
- Do NOT add HTTP, OAuth, TLS, Streamable HTTP, remote server, Temporal, LangGraph,
  OpenAI Agents SDK, cloud, external target mutation, or SQLite ledger migration.
- Do NOT bump schema version for docs/templates only.
- Do NOT overwrite existing `AGENTS.md` or existing scaffold docs.
- Preserve `SYSTEM_STATE.md ≤ 200 lines` and `OPPORTUNITY_MAP.md ≤ 400 lines`.
- `--project-root` is always sovereign over walk-up; walk-up never overrides explicit.

## Authority

`AGENTS.md` is the universal agent instruction file for any project managed by cerebro.
`CLAUDE.md`, if present, is a local supplement for Claude Code only — subordinate and optional.
`observation_center.toml` remains the canonical task queue.
`runtime.db` remains the durable execution state store.

## Stop Conditions

- Gate returns any failure: stop immediately, fix, re-run.
- Any new file generates `CLAUDE.md` in a managed project: revert immediately.
- `AGENTS.md` template contains Claude-mandatory language: revert and fix.
- Walk-up overrides an explicit `--project-root`: revert immediately.
