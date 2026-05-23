# Control Plane Observation Set Review

Read-only advisory review for caller-supplied observation-center snapshots.

This package reviews the coherence of a supplied observation set and optional
`control_plane_action_review` bundles. It checks queue-contract evidence such
as `machine-primary`, `single_flight`, unresolved/resolved shape,
`auto_continuation`, trigger state, dependency state, bundle/snapshot identity,
and multiple advisory bundles under a single-flight contract.

It does not read `docs/operations/observation_center.toml` by itself, does not
write files, does not execute commands, does not mutate `.cerebro/`, does not
select work, does not schedule work, does not grant permission, does not approve
execution, and does not become a runtime or canonical gate.

The observed open-ready frontier is audit evidence only. It is not a scheduler,
not a next-action instruction, and not permission to execute anything.
