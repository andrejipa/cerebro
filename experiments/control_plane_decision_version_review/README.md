# Control Plane Decision Version Review

`control_plane_decision_version_review` is a read-only advisory package for
reviewing caller-supplied decision records before any durable decision store
exists.

It checks whether decision threads preserve contiguous revisions, a single
current revision, explicit supersession, human-decision evidence, expiration
visibility, and consistency with handoff, transition, and action-review
evidence.

Boundary markers:

- state_change: none
- authority: non-authoritative; advisory control-plane decision version review only
- decision_review_is_not_permission: true
- decision_current_is_not_execution_approval: true
- decision_record_is_not_truth: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

This package is not a permission layer, not execution approval, not a
scheduler, not a decision store, not a runtime gate, and not a source of truth.
It does not read `docs/operations`, read `.cerebro/`, write files, execute
commands, mutate state, expose MCP/Agents SDK/Temporal/LangGraph/OpenTelemetry
adapters, apply decisions, choose next work, or grant permission.
