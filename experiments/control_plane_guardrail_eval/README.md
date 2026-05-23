# Control Plane Guardrail Eval

Status: derived experiment, read-only.

This package evaluates `ControlPlaneTelemetryProjection` objects for authority
laundering. It checks whether telemetry-like spans and events preserve the
non-permission, non-truth, non-export, and development-only compatibility
markers required by the Control Plane.

It reports findings for cases such as:

- span status vocabulary that looks like approval, permission, execution, or
  success;
- packet verdicts projected to contradictory span statuses;
- exported telemetry markers;
- stable-looking OTel compatibility claims;
- missing span/event non-permission guardrails;
- sensitive GenAI message, model, or token-usage attributes.

It does not import `opentelemetry`, export telemetry, write files, append logs,
execute commands, grant permission, mutate `.cerebro/`, expose a CLI or adapter,
or become a runtime gate. A clean eval status is not truth or execution
approval.
