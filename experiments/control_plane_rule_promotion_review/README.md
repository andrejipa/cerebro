# Control Plane Rule Promotion Review

Advisory rule-promotion review for caller-supplied rule-change candidates.

- state_change: none
- authority: non-authoritative; advisory control-plane rule promotion review only
- rule_review_is_not_permission: true
- promotion_candidate_is_not_runtime_authority: true
- rule_record_is_not_truth: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package asks whether a proposed rule change is only a refresh candidate, needs human review, or is blocked by decision, integrity, action, evidence, rule-version, or boundary drift. Rule candidates are caller-supplied records with `rule_thread_id`, `revision`, and `supersedes_rule_id`; the review detects gaps, duplicate thread revisions, cross-thread supersession, non-previous supersession, multiple active versions, active-not-latest versions, and stale rule-change candidates. It does not promote rules, rewrite policy, apply changes, schedule work, grant permission, read docs/operations, read `.cerebro/`, mutate state, expose adapters, or become a runtime/canonical gate.
