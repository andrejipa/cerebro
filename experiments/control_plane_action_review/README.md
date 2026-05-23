# Control Plane Action Review

`experiments/control_plane_action_review/` is a derived, read-only pre-action
bundle for one observation-center item.

It accepts caller-supplied observation data and already-built advisory boundary
evidence, then composes the current Control Plane chain:

- assessment;
- capability assessments;
- trace/replay review packet;
- review matrix;
- in-memory telemetry projection;
- guardrail evaluation;
- lineage invariant evaluation;
- integrity review.

The output answers why an observation is waiting, blocked, needs human review, or
is only advisory-reviewable. It does not read `observation_center.toml` itself
and does not write artifacts.

Boundary:

- `state_change: none`;
- non-authoritative advisory action review only;
- `bundle_is_not_permission`;
- `action_posture_is_not_execution_approval`;
- `replay_pass_is_not_truth`;
- `must_not_execute_automatically`;
- no file writing;
- no command execution;
- no `.cerebro/` mutation;
- no target mutation;
- no CLI or external adapter surface;
- no scheduler, runtime gate, or permission layer.
