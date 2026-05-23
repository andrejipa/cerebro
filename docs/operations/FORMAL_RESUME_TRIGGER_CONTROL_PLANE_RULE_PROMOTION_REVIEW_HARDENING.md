# Formal Resume Trigger — Control Plane Rule Promotion Review Hardening

Date: 2026-05-08

## Scope

Harden `experiments/control_plane_rule_promotion_review/` with caller-supplied rule versioning and supersession checks.

## Boundary

- state_change: none
- authority: non-authoritative; advisory control-plane rule promotion review only
- no `.cerebro/` reads or writes
- no `docs/operations` reads as source of truth
- no CLI/runtime/adapter/scheduler surface
- no rule store, contract store, rule application, promotion, enforcement, or permission grant

## Accepted Work

- Add `rule_thread_id`, `revision`, and `supersedes_rule_id` to rule candidates.
- Reject duplicate `(rule_thread_id, revision)` pairs.
- Detect revision gaps, missing supersession, unknown/self/cross-thread/non-previous supersession, multiple active versions, active-not-latest versions, and stale rule-change candidates.
- Reject forged active/non-active derived summaries in renderers.
- Extend boundary-audit laundering tokens for rule-version, supersession, and rule-store claims.

## Close Criteria

- Focused rule-promotion tests pass.
- Boundary audit tests pass.
- Lifecycle/docs/architecture gates pass.
- Full Windows-safe gate passes before treating the hardening as closed.
