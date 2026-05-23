# Control Plane Runtime State Review

Advisory runtime-state review for caller-supplied state snapshots.

- state_change: none
- authority: non-authoritative; advisory control-plane runtime state review only
- state_review_is_not_permission: true
- snapshot_is_not_canonical_state: true
- observed_state_is_not_scheduler: true
- state_status_is_not_execution_approval: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package reviews caller-supplied runtime-state snapshots and optional caller-supplied structural payloads for state, session, recent events, and lock observation. It checks identity, revisions, supersession, secret/raw-evidence flags, state-authority flags, work-selection flags, execution-permission flags, queue authority, observation ids, decision ids, rule ids, runtime-adoption ids, plan graph consistency, action/approval/verification relationships, trace event continuity, session revision/claim consistency, and lock observation drift.

This review does not read `.cerebro/`, does not read state.json, does not read docs/operations, does not open a state store, does not read queues, does not import core runtime modules, does not write files, does not execute commands, does not recover locks, does not choose next action, does not schedule work, does not grant permission, and does not become canonical state or a runtime gate.
