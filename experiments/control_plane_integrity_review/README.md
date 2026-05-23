# Control Plane Integrity Review

`experiments/control_plane_integrity_review/` is a derived, read-only
consolidation layer for the Cerebro Control Plane front.

It consumes already-built advisory reports from:

- `control_plane_boundary_audit`;
- `control_plane_guardrail_eval`;
- `control_plane_lineage_invariant_eval`.

It emits a compact integrity review with one status, evidence summaries, source
status counts, severity counts, and finding details. The review exists so an
operator or later evaluator can see whether the current advisory chain stayed
coherent without reinterpreting many separate reports.

Boundary:

- `state_change: none`;
- non-authoritative advisory review only;
- `review_is_not_permission`;
- `integrity_pass_is_not_truth`;
- `finding_is_not_execution_approval`;
- `must_not_execute_automatically`;
- no file writing;
- no command execution;
- no `.cerebro/` mutation;
- no target mutation;
- no CLI or external adapter surface;
- no scheduler, runtime gate, or permission layer.
