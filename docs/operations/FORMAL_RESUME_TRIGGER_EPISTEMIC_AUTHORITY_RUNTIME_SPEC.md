# FORMAL RESUME TRIGGER — EPISTEMIC AUTHORITY RUNTIME SPEC

status: consumed
created_at: 2026-04-24
accepted_by: operator request to mature Risk-Adaptive Epistemic Runtime into a strong specification
consumed_at: 2026-04-24
result: docs-only specification produced

## Purpose

Create a docs-only specification for the next conceptual layer of Cerebro:
Risk-Adaptive Epistemic Runtime.

The spec must clarify how authority, evidence sufficiency, reversibility,
blast radius, confidence propagation, promotion, demotion, and protocol
self-audit should work before any runtime implementation is considered.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md`
- `docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/observation_center.toml`

Read-only context:

- `AGENTS.md`
- `docs/operations/FREEZE_POLICY.md`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md`
- `docs/handoffs/HANDOFF_RISK_ADAPTIVE_EPISTEMIC_RUNTIME.md`

## Forbidden

- No edits to `core/`, `cli/`, `extensions/`, `tests/`, `.cerebro/`, or `core/schema.py`.
- No promotion of `claim_extraction` or `claim_evaluation` into runtime authority.
- No claim graph implementation.
- No runtime gate implementation.
- No state mutation.
- No third-party project mutation.
- No new canonical artifact.

## Acceptance Criteria

- Spec preserves:
  - `registered != true`
  - `retrieved != relevant`
  - `remembered != trusted`
  - `silence != negative evidence`
- Spec distinguishes permission from sufficient evidence.
- Spec defines authority states.
- Spec defines operational zones 0/1/2/3 as a floor, not the full risk model.
- Spec defines reversibility-weighted authorization and blast radius declaration.
- Spec defines promotion gates and demotion triggers.
- Spec defines dependency-based confidence propagation.
- Spec defines protocol self-audit.
- Spec explicitly says what is not authorized yet.
- Architecture/doc governance tests remain green.
- Full AGENTS-equivalent gate remains green before closure.

## Stop Conditions

Stop immediately if the spec implies:

- a runtime permission mechanism exists today;
- readiness reports authorize mutation;
- derived evidence is canonical truth;
- silence can become negative evidence;
- risk-adaptive means lower rigor rather than more accurate rigor.

## Closure Evidence

- Specification produced: `docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md`
- Boundary preserved: docs-only.
- No edits to `core/`, `cli/`, `extensions/`, `tests/`, `.cerebro/`, or `core/schema.py`.
- No promotion of `claim_extraction` or `claim_evaluation` into runtime authority.
- Runtime implementation remains unauthorized.
