# Formal Resume Trigger — Epistemic Guard Pre-Action Packet Stress/Repro Slice 6

Status: consumed
Opened: 2026-04-24
Accepted-by: operator instruction "mature sua ideia"
Consumed: 2026-04-24

## Objective

Harden the pre-action decision packet with degraded packet-level stress cases
and checked-artifact reproducibility evidence.

This slice proves that the packet does not become a fragile happy-path summary:
blocked reports, failed stress matrices, human-review reports, stale checked-in
artifacts, malformed artifacts, root escapes, and `.cerebro/` targets must stay
visible as blocked advisory evidence.

## Whitelist

- `docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_PRE_ACTION_PACKET_STRESS_REPRO_SLICE_6.md`
- `experiments/epistemic_guard/**`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_PACKET_STRESS_REPRO.json`
- `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_PACKET_STRESS_REPRO.md`
- `experiments/lifecycle.toml`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

## Explicit Prohibitions

- Do not touch `core/`, `cli/`, `extensions/`, `tests/`, `core/schema.py`, or
  `.cerebro/state.json`.
- Do not mutate target projects or canonical runtime state.
- Do not create a runtime gate, permission layer, canonical claim graph, source
  registry, memory writer, automatic execution path, or authority promotion.
- Do not treat stress pass, reproducibility, digest equality, packet readiness,
  or review-clear as permission, approval, truth, memory, source registration,
  runtime authority, or automatic execution.
- Do not infer negative evidence from omitted claims or sources.

## Acceptance Criteria

- A deterministic packet stress/repro report covers clean packet,
  blocked-report packet, human-review packet, failed-stress packet,
  reproducible checked artifacts, stale JSON artifact, malformed JSON artifact,
  missing artifact, root escape, and `.cerebro/` target.
- Degraded cases remain visible as blocked with review blockers.
- Reproducibility compares regenerated JSON/Markdown packet output to checked-in
  artifacts without making digest equality permission.
- JSON and Markdown renderers preserve `state_change: none`,
  `stress_pass_is_not_permission`, `reproducibility_is_not_permission`, and
  `must_not_execute_automatically`.
- Focused tests cover clean/degraded packet stress, reproducibility match,
  stale/malformed/missing artifacts, path boundary errors, and renderer
  guardrails.

## Required Gates

- Initial AGENTS-equivalent full gate before writes.
- Focused `experiments.epistemic_guard` tests after implementation.
- Architecture/doc-governance tests after documentation updates.
- Final AGENTS-equivalent full gate before marking this trigger consumed.

## Stop Conditions

- Any required gate fails.
- The slice needs runtime, schema, core, CLI, extension, test-architecture, or
  `.cerebro/` mutation.
- The output frames stress/reproducibility as permission, approval, truth,
  memory, authority, source registration, runtime gate, claim graph, or
  automatic execution.

## Initial Evidence

- Initial AGENTS-equivalent gate before writes: `923` tests, `0` failures,
  `0` errors, `6` skipped.

## Closure Evidence

- Added `experiments/epistemic_guard/pre_action_packet_stress.py` with
  `PreActionPacketStressReproReport`, `PreActionPacketArtifactCheck`,
  `check_pre_action_packet_artifacts(...)`,
  `build_pre_action_packet_stress_repro_report(...)`, and stable JSON/Markdown
  renderers.
- Added focused tests for clean/degraded packet behavior, reproducibility match,
  stale/malformed/missing artifacts, root-escape and `.cerebro` path rejection,
  and renderer guardrails.
- Generated
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_PACKET_STRESS_REPRO.json`
  and
  `docs/operations/CEREBRO_SELF_EPISTEMIC_GUARD_PRE_ACTION_PACKET_STRESS_REPRO.md`.
- Real output: `case_count=10`, `pass_count=10`, `fail_count=0`,
  `blocked_case_count=7`, `human_review_case_count=1`,
  `reproducible_case_count=1`, `mismatch_case_count=3`,
  `boundary_error_count=2`, and `state_change=none`.
- Focused validation: `experiments.epistemic_guard` `29/0`.
- Architecture/doc-governance validation: `64/0`.
- Full AGENTS-equivalent validation: `923` tests, `0` failures, `0` errors,
  `6` skipped.
- Boundary preserved: no `core/`, `cli/`, `extensions/`, top-level `tests/`,
  `core/schema.py`, `.cerebro/state.json`, runtime authority, source registry,
  memory writer, canonical claim graph, permission layer, or automatic execution
  was introduced.
