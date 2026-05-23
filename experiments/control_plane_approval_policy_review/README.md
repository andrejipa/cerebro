# Control Plane Approval Policy Review

`control_plane_approval_policy_review` is a read-only advisory review for
caller-supplied approval policy candidates before any approval store, permission
layer, scheduler, state store, queue reader, adapter, or canonical runtime gate
exists.

- state_change: none
- authority: non-authoritative; advisory control-plane approval policy review only
- approval_policy_review_is_not_permission: true
- approval_policy_review_is_not_approval_store: true
- approval_status_is_not_execution_approval: true
- approval_presence_is_not_sufficient_evidence: true
- approval_policy_review_is_not_scheduler: true
- approval_policy_review_is_not_runtime_gate: true
- approval_policy_review_is_not_state_store: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package reviews in-memory payloads and already-built advisory review
objects. It can report approval-policy drift, missing evidence controls,
missing current-decision requirements, missing expiration, missing action
fingerprints, missing revocation paths, blanket approval risk, reuse-after-scope
drift risk, and authority laundering.

It does not register approvals, store decisions, approve execution, select the
next action, schedule work, mutate state, read live stores, call tools, expose
adapters, or grant permission.
