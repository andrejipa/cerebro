# Epistemic Guard Pre-Action Stress Matrix

- state_change: none
- authority: non-authoritative; advisory pre-action stress matrix only
- stress_pass_is_not_permission: true
- must_not_execute_automatically: true
- silence_is_not_negative_evidence: true

## Summary

- case_count: 6
- pass_count: 6
- fail_count: 0
- all_cases_passed: true
- blocked_or_human_count: 5
- blocker_count: 6
- boundary_error_count: 2

## Cases

### clean_pre_action_report

- description: Clean declared advisory action remains allowed only as an advisory report.
- expected_action_readiness: advisory_report_allowed
- actual_action_readiness: advisory_report_allowed
- expected_human_decision: none
- actual_human_decision: none
- blocker_count: 0
- boundary_error: false
- passed: true
- actual_error: none

### missing_proposed_action

- description: A pre-action manifest without [proposed_action] fails closed.
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- blocker_count: 1
- boundary_error: true
- passed: true
- actual_error: pre-action manifest requires [proposed_action]

### mutating_expected_state

- description: A pre-action manifest that expects state mutation fails closed.
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- blocker_count: 1
- boundary_error: true
- passed: true
- actual_error: pre-action reports must declare expected_state_change = 'none'

### runtime_promotion_without_trigger

- description: Runtime/canonical promotion without an active trigger remains blocked.
- expected_action_readiness: canonical_change_requires_trigger
- actual_action_readiness: canonical_change_requires_trigger
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- blocker_count: 2
- boundary_error: false
- passed: true
- actual_error: none

### stale_approval

- description: Approval whose read set changed remains blocked.
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- blocker_count: 1
- boundary_error: false
- passed: true
- actual_error: none

### read_write_drift

- description: Read/write drift remains blocked by the prewrite guard.
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- blocker_count: 1
- boundary_error: false
- passed: true
- actual_error: none
