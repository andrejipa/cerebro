# Control Plane Observation Transition Review

Read-only advisory review for caller-supplied observation-center transitions.

This package compares two supplied observation-center snapshots and optional
caller-supplied transition evidence. It detects temporal laundering such as a
waiting checkpoint becoming open-ready without evidence, unresolved observations
disappearing without removal or resolution evidence, queue-contract fields
changing between snapshots, multiple open-ready observations under
`single_flight`, `auto_continuation` being introduced, and critical observation
payload drift across snapshots.

It does not read `docs/operations/observation_center.toml` by itself, does not
write files, does not execute commands, does not mutate `.cerebro/`, does not
select work, does not schedule work, does not grant permission, does not approve
execution, and does not become a runtime or canonical gate.

The observed transition and the observed after-snapshot frontier are audit
evidence only. They are not truth, not a scheduler, not a next-action
instruction, and not permission to execute anything.
