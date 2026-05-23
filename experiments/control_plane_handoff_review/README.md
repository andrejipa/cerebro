# Control Plane Handoff Review

`control_plane_handoff_review` is a read-only advisory package for reviewing
caller-supplied handoff claims between agents, roles, or a human checkpoint.

It consumes a handoff payload plus already-built observation-set,
observation-transition, and action-review evidence. It reports whether the
handoff hides blocked queue state, transition drift, dropped human decisions,
authority wording, or automatic continuation.

Boundary markers:

- state_change: none
- authority: non-authoritative; advisory control-plane handoff review only
- handoff_review_is_not_permission: true
- handoff_is_not_scheduler: true
- handoff_is_not_execution_approval: true
- observed_frontier_is_not_scheduler: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

This package is not a scheduler, not execution approval, not a runtime gate,
not an adapter, and not permission. It does not read `observation_center.toml`,
write files, execute commands, mutate `.cerebro/`, transfer control, expose
MCP/Agents SDK/Temporal/LangGraph/OpenTelemetry integrations, or choose the
next action.
