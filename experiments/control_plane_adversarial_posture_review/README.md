# Control Plane Adversarial Posture Review

`control_plane_adversarial_posture_review` is a read-only, non-authoritative
review layer for caller-supplied Control Plane reports and bundles.

It checks whether advisory review artifacts still preserve their own defensive
posture when they are composed together. It detects false guardrails, forged
finding summaries, authority wording, status laundering, clean-status-with-
findings contradictions, blocked-status-without-evidence contradictions, and
expected blockers that disappeared.

Boundary:

- `state_change: none`
- non-authoritative advisory review only
- posture review is not permission
- posture status is not truth
- posture review is not an approval
- posture review is not a scheduler
- posture review is not a runtime gate
- posture review is not a state store
- findings are not execution approval
- must_not_execute_automatically

The package does not read `.cerebro/`, `docs/operations`, runtime state files,
queue files, approval stores, tool registries, evidence stores, or target files.
It does not write files, execute commands, schedule work, choose a next action,
grant permission, approve execution, mutate state, expose adapters, call tools,
or become a canonical gate.
