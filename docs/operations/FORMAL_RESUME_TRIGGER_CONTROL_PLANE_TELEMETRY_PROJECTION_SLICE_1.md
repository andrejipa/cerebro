# Formal Resume Trigger: Control Plane Telemetry Projection Slice 1

Status: consumed on 2026-05-08.

## Boundary

Allowed:

- `experiments/control_plane_telemetry_projection/**`
- `experiments/lifecycle.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center_archive.toml`

Forbidden:

- `core/`, `cli/`, `extensions/`, schema, runtime state, `.cerebro/`, target projects, persistent logs, MCP adapters, Agents SDK adapters, OpenTelemetry exporters, schedulers, command execution, and authority promotion.

## Intent

Create a read-only advisory projection from existing `ControlPlaneReviewPacket`
objects into deterministic in-memory telemetry-like spans and events.

## Done When

- the package exists;
- projection tests pass;
- lifecycle ledger records the experiment;
- the output explicitly marks semantic-convention compatibility as development-only;
- the output cannot be read as export, permission, execution approval, runtime gate, or canonical observability state.

## Halt If

The slice writes files, appends logs, imports `opentelemetry`, exports OTLP,
executes commands, registers memory, grants permission, mutates `.cerebro/`,
exposes CLI/adapters, or treats telemetry compatibility as stable authority.
