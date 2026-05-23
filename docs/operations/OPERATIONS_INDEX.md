# Operations Index

Short map for finding the current operating surfaces without moving or pruning the historical archive.

## Live State
- `docs/operations/SYSTEM_STATE.md`: current human-readable system snapshot. Read the `Current Snapshot` section first.
- `docs/operations/OPPORTUNITY_MAP.md`: short next-action projection for operators.
- `docs/operations/observation_center.toml`: bootstrap/import queue source until SQLite promotion; legacy export/bootstrap compatibility after promotion.
- `docs/operations/observation_center_archive.toml`: resolved historical observations; not part of normal routing.

## Runtime Manager
- `docs/operations/RUNTIME_MANAGER_CONTRACT.md`: local runtime-manager contract, schema authority, gates, diagnostics, and CLI behavior.
- `core/runtime_manager_store.py`: core-owned SQLite store and migration boundary.
- `cli/commands/runtime_manager.py`: CLI projection/enforcement wrapper over the core store.
- `tests/gate_runner.py`: official local gate profiles (`base`, `mcp`, `full`).

## MCP
- `adapters/runtime_manager_mcp_stdio/`: optional FastMCP STDIO adapter.
- `tests/test_runtime_manager_mcp_stdio.py`: MCP adapter tests.
- `tests/test_runtime_manager_phase8_mcp.py`: MCP/autonomy policy tests.
- `pyproject.toml`: optional `.[mcp]` dependency declaration.

## Contracts And Freeze
- `AGENTS.md`: operator/agent contract and authority order.
- `docs/operations/FREEZE_POLICY.md`: freeze rules and allowed resume conditions.
- `docs/operations/FORMAL_RESUME_TRIGGER_OBSERVATION_CENTER_SQLITE_LEDGER_2026-05-23.md`: current trigger for the SQLite observation-center promotion.

## Experiments And Advisory Evidence
- `experiments/`: non-authoritative derived experiments and evaluators.
- `docs/operations/CEREBRO_CONTROL_PLANE_GROWTH_001.md`: control-plane front summary.
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`: generated advisory self-readiness report.

## Handoffs
- `docs/handoffs/`: durable handoffs and architectural position records.
- `docs/handoffs/HANDOFF_CONTENT_AWARE_ANALYSIS_LAYERING.md`: content-aware analysis layering rule.
