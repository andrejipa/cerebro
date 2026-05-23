# Formal Resume Trigger: Control Plane Guardrail Eval Slice 1

Status: consumed on 2026-05-08.

## Boundary

Allowed:

- `experiments/control_plane_guardrail_eval/**`
- `experiments/lifecycle.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center_archive.toml`

Forbidden:

- `core/`, `cli/`, `extensions/`, schema, runtime state, `.cerebro/`,
  target projects, persistent logs, MCP adapters, Agents SDK adapters,
  OpenTelemetry exporters, schedulers, command execution, and authority
  promotion.

## Intent

Create a read-only advisory evaluator that checks
`ControlPlaneTelemetryProjection` outputs for authority laundering.

## Done When

- the package exists;
- guardrail-eval tests pass;
- lifecycle ledger records the experiment;
- clean telemetry projections evaluate without findings;
- drifted telemetry projections produce findings for permission/status/export,
  stable semconv, sensitive GenAI fields, and missing non-permission markers;
- the output cannot be read as truth, permission, execution approval, runtime
  gate, or canonical observability state.

## Halt If

The slice writes files, appends logs, imports `opentelemetry`, exports OTLP,
executes commands, registers memory, grants permission, mutates `.cerebro/`,
exposes CLI/adapters, treats clean eval as execution approval, or promotes
telemetry into runtime authority.
