# Control Plane Assessment

Status: derived experiment, read-only.

This package composes existing Cerebro decision surfaces into one advisory
assessment report:

- `core.decision_runtime.choose_next_task`;
- `core.decision_runtime.evaluate_task_selection_consistency`;
- `experiments.epistemic_guard.DecisionEnvelope`;
- `experiments.claim_evaluation.EvaluationReport`;
- `experiments.operational_signals` analysis payloads.

It does not create a scheduler, gate, claim graph, permission layer, memory
writer, CLI surface, or canonical artifact. Every report declares
`state_change = "none"` and `authority = "non-authoritative"`.
