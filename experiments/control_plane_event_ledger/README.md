# Control Plane Event Ledger

Status: derived experiment, read-only.

This package turns a `ControlPlaneTrace` into an in-memory JSONL event ledger
and parses that JSONL back into a verified ledger shape. It is the first local
Trace and Replay artifact for the Control Plane front.

It does not write files, append logs, register memory, export OpenTelemetry,
execute commands, grant permission, mutate `.cerebro/`, expose a CLI, or become
a runtime gate. Every ledger declares `state_change = "none"`, `authority =
"non-authoritative"`, `ledger_is_not_permission = true`, and
`must_not_execute_automatically = true`.

Each row declares `ledger_role = "derived_control_plane_trace_event"` and an
`event_digest` for deterministic replay checking. Digest equality is not truth,
freshness, permission, or operational readiness; it only proves that a replayed
row still matches the derived payload shape.
