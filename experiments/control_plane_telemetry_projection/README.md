# Control Plane Telemetry Projection

Status: derived experiment, read-only.

This package maps existing `ControlPlaneReviewPacket`,
`ControlPlaneReviewMatrix`, `ControlPlaneScenarioLabReport`, and
`ControlPlaneAdversarialReport` objects into deterministic in-memory
telemetry-like spans and events. It is a compatibility projection for future
observability work, not an OpenTelemetry exporter.

The projection records:

- one internal span per review packet;
- trace events from the existing Control Plane trace;
- blocker and replay-issue events;
- packet, replay, human-review, and guardrail attributes.
- scenario expectation drift as events, not success;
- adversarial findings as events, not execution approval.

It deliberately does not import `opentelemetry`, export OTLP, write files,
append logs, execute commands, register memory, grant permission, mutate
`.cerebro/`, expose a CLI, expose MCP or Agents SDK adapters, or become a
runtime gate. Semantic-convention compatibility is marked as development-only
because the GenAI semantic conventions are still evolving.
