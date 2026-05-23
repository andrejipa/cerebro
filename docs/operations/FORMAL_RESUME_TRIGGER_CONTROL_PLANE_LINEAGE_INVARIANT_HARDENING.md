# FORMAL_RESUME_TRIGGER_CONTROL_PLANE_LINEAGE_INVARIANT_HARDENING

Status: consumed on 2026-05-08.

## Scope

Harden `experiments/control_plane_lineage_invariant_eval/` after the first
slice by closing concrete false-negative gaps in cross-layer checks.

## Added Coverage

- packet `trace_event_count` preservation;
- matrix row-event count and required human-decision identity preservation;
- scenario-lab expectation-failure event count and per-scenario failure
  preservation;
- scenario child-span preservation;
- adversarial finding-event count and finding-code preservation;
- adversarial probe child-span and per-probe finding-count preservation;
- guardrail report source-projection-role and finding-count consistency.

## Boundary

This remains advisory-only. It does not read `.cerebro/`, rebuild upstream
objects, rerun labs, write files, execute commands, export telemetry, expose
adapters, schedule work, grant permission, approve execution, or become a
runtime/canonical gate.
