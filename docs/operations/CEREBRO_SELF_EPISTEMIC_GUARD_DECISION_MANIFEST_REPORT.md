# Epistemic Guard Decision Envelope Oracle

- state_change: none
- authority: non-authoritative; advisory decision envelope only
- advisory_pass_is_not_permission: true
- registered_is_not_true: true
- retrieved_is_not_relevant: true
- remembered_is_not_trusted: true
- silence_is_not_negative_evidence: true
- permission_is_not_sufficient_evidence: true

## Summary

- scenario_count: 3
- blocked_or_human_count: 2
- advisory_allowed_count: 0
- derived_experiment_allowed_count: 1

## Envelopes

### manifest_driven_epistemic_guard_slice_2

- intent: Generate the manifest-driven advisory decision report for epistemic_guard slice 2.
- sufficiency: sufficient
- action_readiness: derived_experiment_allowed
- recommended_human_decision: none
- approval_status: not_required
- prewrite_guard_status: passed
- state_change: none
- blockers: none
- missing_evidence: none
- stale_claims: none
- conflicts: none

### runtime_promotion_without_trigger

- intent: Promote epistemic_guard from advisory evidence into a canonical runtime permission gate.
- sufficiency: blocked
- action_readiness: canonical_change_requires_trigger
- recommended_human_decision: review_blockers
- approval_status: missing_for_authority_impact
- prewrite_guard_status: passed
- state_change: none
- blockers: human_approval_missing_for_authority_impact, missing_active_trigger_for_runtime_or_canonical_change
- missing_evidence: none
- stale_claims: none
- conflicts: none

### approval_expired_for_manifest_report

- intent: Reuse an old approval after the evidence read set gained the slice 1 oracle report.
- sufficiency: blocked
- action_readiness: blocked
- recommended_human_decision: review_blockers
- approval_status: expired_by_source_set_change
- prewrite_guard_status: passed
- state_change: none
- blockers: approval_expired_by_source_set_change
- missing_evidence: none
- stale_claims: none
- conflicts: none
