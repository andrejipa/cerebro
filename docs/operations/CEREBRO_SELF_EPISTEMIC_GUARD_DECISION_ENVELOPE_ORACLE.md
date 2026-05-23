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

- scenario_count: 8
- blocked_or_human_count: 7
- advisory_allowed_count: 1

## Envelopes

### stale_next_action

- intent: Decide whether the next project step is to create schema or implement Edge Functions.
- sufficiency: insufficient
- action_readiness: human_approval_required
- recommended_human_decision: adjudicate_conflict
- approval_status: not_required
- prewrite_guard_status: not_applicable
- state_change: none
- blockers: none
- missing_evidence: none
- stale_claims: claim-old-next: source_stale
- conflicts: next_action:is has conflicting values across claim-new-next, claim-old-next

### silence_is_not_negative_evidence

- intent: Decide whether schema is absent because a diagnostic source did not mention it.
- sufficiency: partial
- action_readiness: human_approval_required
- recommended_human_decision: provide_missing_evidence
- approval_status: not_required
- prewrite_guard_status: not_applicable
- state_change: none
- blockers: none
- missing_evidence: req-schema-status: missing explicit schema existence evidence for schema-dependent action
- stale_claims: none
- conflicts: none

### existing_state_ambiguity

- intent: Start a third-party pilot where a prior .cerebro/state.json already exists.
- sufficiency: blocked
- action_readiness: blocked
- recommended_human_decision: adjudicate_conflict
- approval_status: not_required
- prewrite_guard_status: not_applicable
- state_change: none
- blockers: existing_state_ambiguity
- missing_evidence: none
- stale_claims: none
- conflicts: none

### missing_trigger_for_runtime_mutation

- intent: Edit core runtime behavior without an active formal trigger.
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

### approval_expired_by_source_set_change

- intent: Apply a plan after a new decisive source entered the read set.
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

### read_write_drift

- intent: Write a report based on a file whose digest changed after read.
- sufficiency: blocked
- action_readiness: blocked
- recommended_human_decision: review_blockers
- approval_status: approved_current
- prewrite_guard_status: blocked_read_write_drift
- state_change: none
- blockers: read_write_drift:SYSTEM_STATE.md
- missing_evidence: none
- stale_claims: none
- conflicts: none

### protocol_induced_stale_source_route

- intent: Follow a protocol route that prioritizes a stale diagnostic over current continuity.
- sufficiency: insufficient
- action_readiness: human_approval_required
- recommended_human_decision: adjudicate_conflict
- approval_status: not_required
- prewrite_guard_status: not_applicable
- state_change: none
- blockers: none
- missing_evidence: none
- stale_claims: claim-diagnostic-next: source_stale
- conflicts: next_action:is has conflicting values across claim-continuity-next, claim-diagnostic-next

### clean_advisory_report

- intent: Produce a read-only advisory report from current bounded evidence.
- sufficiency: sufficient
- action_readiness: advisory_report_allowed
- recommended_human_decision: none
- approval_status: not_required
- prewrite_guard_status: not_applicable
- state_change: none
- blockers: none
- missing_evidence: none
- stale_claims: none
- conflicts: none
