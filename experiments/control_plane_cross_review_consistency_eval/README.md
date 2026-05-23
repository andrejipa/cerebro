# Control Plane Cross-Review Consistency Eval

`control_plane_cross_review_consistency_eval` is a read-only,
non-authoritative evaluator for caller-supplied Control Plane advisory review
artifacts.

It detects contradictions between reviews that can disappear when each artifact
is checked alone: the same trace with conflicting replay digests, the same
identity appearing clean and blocked, an action review claiming advisory posture
over integrity drift, ready/allowed/active candidates over blocked dependency
evidence, and clean statuses carrying blocked ids.

Boundary:

- `state_change: none`
- non-authoritative advisory cross-review consistency evaluation only
- consistency eval is not permission
- consistency status is not truth
- consistency eval is not execution approval
- consistency eval is not a scheduler
- consistency eval is not a runtime gate
- consistency eval is not a state store
- findings are not truth
- must_not_execute_automatically

The package does not read `.cerebro/`, `docs/operations`, runtime state files,
queue files, approval stores, evidence stores, tool registries, target files, or
raw evidence. It does not write files, execute commands, mutate state, rank work,
choose a next action, schedule work, approve execution, grant permission, call
tools, expose adapters, or become a canonical gate.
