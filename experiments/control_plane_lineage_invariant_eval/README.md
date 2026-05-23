# Control Plane Lineage Invariant Eval

`experiments/control_plane_lineage_invariant_eval/` is a derived, read-only
advisory evaluator for cross-layer Control Plane invariants.

It compares already-built objects across these boundaries:

- review packet -> telemetry projection;
- review matrix -> telemetry projection;
- scenario lab -> telemetry projection;
- adversarial report -> telemetry projection;
- telemetry projection -> guardrail eval.

The evaluator checks that trace ids, packet verdicts, mapped statuses, blockers,
replay issues, matrix rows, human-review counts, scenario expectation drift,
expectation failures, adversarial findings, and projection span/event counts do
not disappear or change meaning between layers.

It does not rebuild packets, rerun scenario labs, read `.cerebro/`, write files,
append logs, execute commands, export telemetry, expose CLI/MCP/Agents SDK/
Temporal/LangGraph adapters, schedule work, mutate state, grant permission, or
become a runtime/canonical gate.

Reports preserve:

- `state_change: none`
- `authority: non-authoritative; advisory cross-layer invariant evaluation only`
- `eval_is_not_permission: true`
- `invariant_pass_is_not_truth: true`
- `finding_is_not_execution_approval: true`
- `must_not_execute_automatically: true`
