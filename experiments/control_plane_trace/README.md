# Control Plane Trace

Status: derived experiment, read-only.

This package correlates existing advisory signals into one replayable trace:

- `experiments.control_plane_assessment.ControlPlaneAssessment`;
- `experiments.capability_policy.CapabilityAssessment`;
- a local deterministic trace over the combined review status.

It does not select tasks, execute tools, grant permission, register tools,
write memory, mutate `.cerebro/`, expose a CLI, or become a runtime gate.
Every trace declares `state_change = "none"`, `authority =
"non-authoritative"`, `trace_is_not_permission = true`, and
`must_not_execute_automatically = true`.
