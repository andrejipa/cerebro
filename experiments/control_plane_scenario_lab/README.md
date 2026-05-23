# Control Plane Scenario Lab

`control_plane_scenario_lab` runs declared in-memory scenarios through the
advisory Control Plane chain:

1. `ControlPlaneAssessment`
2. `CapabilityAssessment`
3. `ControlPlaneReviewPacket`
4. `ControlPlaneReviewMatrix`

It exists to stress the current Control Plane behavior with clean, missing
capability, blocked runtime, and review-required scenarios.

It is not a scheduler, gate, executor, permission layer, CLI, persistent log,
MCP adapter, Agents SDK adapter, OpenTelemetry exporter, or runtime authority.

## Contract

- `state_change = none`
- `authority = non-authoritative`
- `lab_is_not_permission = true`
- `expectation_match_is_not_execution_approval = true`
- `replay_pass_is_not_truth = true`
- `must_not_execute_automatically = true`

The lab may report `expectation_drift_observed`, but that is only a signal to
review scenario expectations or Control Plane behavior. It never grants
permission to execute the scenario.

## Adversarial Probes

The package also includes in-memory hostile probes for the current advisory
chain. They mutate replay JSONL, weaken packet guardrails, duplicate matrix
trace ids, verify that `advisory_allow` remains non-permission through packet
and matrix projections, and inspect semantic contradictions that can survive
valid replay formatting.

Probe findings are observations about boundary resistance. They are not
execution approval, runtime readiness, scheduler output, or permission.
