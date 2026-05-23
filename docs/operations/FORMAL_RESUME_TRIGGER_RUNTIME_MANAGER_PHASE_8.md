# Formal Resume Trigger — Runtime Manager Phase 8

**Phase:** 8 — Autonomy Calibration and Progressive Friction
**Status:** ACTIVE
**Authorized by:** Human instruction 2026-05-09
**Preconditions satisfied:** Phase 7 post-fix review passed; gate 2255/0/6; schema v14

---

## What is authorized

Implement canonical autonomy levels (L0–L4) and progressive friction for the
Runtime Manager.  This phase is strictly local and offline:

- Define and encode L0_observe / L1_derived / L2_local_code /
  L3_runtime_mutation / L4_external_high_risk as first-class policy constructs.
- Add `classify_action()` to `core/runtime_manager_policy.py` (pure, no I/O).
- Bump schema to v15: optional new columns in `command_registry`,
  `adapter_tokens`, and `execution_evidence`; new `policy_counters` table.
- Expose `classify_runtime_action()` on `RuntimeManagerStore`.
- Extend `CommandEligibilityResult` with autonomy metadata.
- Add CLI: `runtime-manager policy classify` and `policy explain-levels`.
- Enforce `max_autonomy_level` on MCP tokens; block L4 unconditionally.
- Add derived autonomy metrics in `read_metrics()`.
- Add `eval_autonomy_levels.py` evaluator.
- Full test coverage for all new surfaces.

## What is NOT authorized

- HTTP MCP transport, OAuth/TLS, multi-connection MCP server.
- Temporal, LangGraph, OpenAI Agents SDK, Cloudflare Agents SDK.
- Any network-opening code.
- Reducing security on L3/L4 or removing approval/lease requirements.
- Treating trace/metrics/replay results as execution permission.

## Mandatory stops

- Gate must remain ≥ 2255 passed / 0 failures after each slice.
- L4 must always be blocked for MCP token execution.
- Overrides must only increase the effective level, never decrease.
- Backward compatibility with commands that lack new optional fields.

## Closure condition

All tasks in the `runtime-manager-phase-8-autonomy-calibration` observation
are resolved, gate passes, and this trigger is superseded by
`FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_9.md` when a new phase begins.
