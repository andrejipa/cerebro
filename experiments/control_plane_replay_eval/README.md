# Control Plane Replay Eval

Status: derived experiment, read-only.

This package evaluates in-memory JSONL produced by
`experiments.control_plane_event_ledger`. It classifies whether a replay keeps
the local Control Plane contract, is incomplete, fails replay verification, or
contains authority drift.

It does not write files, append logs, execute commands, select tasks, recompute
readiness, grant permission, mutate `.cerebro/`, expose a CLI, or become a
runtime gate. Passing evaluation is not truth, permission, freshness, approval,
or operational readiness.
