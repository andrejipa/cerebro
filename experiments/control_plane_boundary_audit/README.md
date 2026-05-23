# Control Plane Boundary Audit

`experiments/control_plane_boundary_audit/` is a derived, read-only advisory
audit over the current Control Plane experiment packages.

It checks package source text for cross-layer boundary drift:

- missing `state_change`, `non-authoritative`, or no-auto-execute markers;
- imports of adapter/runtime/export surfaces such as OpenTelemetry, network,
  subprocess, Temporal, LangGraph, OpenAI, CLI, or extensions modules;
- file-writing, dynamic execution, process, or destructive filesystem calls;
- text that launders permission, runtime authority, canonical truth, or stable
  adapter semantics without an explicit negative marker.

The audit may read bounded package source files under `experiments/`, but it
does not write files, append logs, execute commands, export telemetry, expose
MCP/Agents SDK/Temporal/LangGraph adapters, mutate `.cerebro/`, schedule work,
grant permission, or become a runtime/canonical gate.

Reports preserve:

- `state_change: none`
- `authority: non-authoritative; advisory control-plane boundary audit only`
- `audit_is_not_permission: true`
- `finding_is_not_truth: true`
- `audit_pass_is_not_execution_approval: true`
- `must_not_execute_automatically: true`
