# Epistemic Guard Pre-Action Packet Stress/Repro Report

- state_change: none
- authority: non-authoritative; advisory pre-action packet stress/repro report only
- stress_pass_is_not_permission: true
- reproducibility_is_not_permission: true
- digest_equality_is_not_truth: true
- must_not_execute_automatically: true
- silence_is_not_negative_evidence: true

## Summary

- case_count: 10
- pass_count: 10
- fail_count: 0
- all_cases_passed: true
- blocked_case_count: 7
- human_review_case_count: 1
- reproducible_case_count: 1
- mismatch_case_count: 3
- boundary_error_count: 2
- blocker_count: 9

## Cases

### clean_packet

- description: Clean packet remains go_for_advisory_review without granting permission.
- expected_operator_posture: go_for_advisory_review
- actual_operator_posture: go_for_advisory_review
- expected_action_readiness: advisory_report_allowed
- actual_action_readiness: advisory_report_allowed
- expected_human_decision: none
- actual_human_decision: none
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 0
- boundary_error: false
- passed: true
- actual_error: none

### blocked_report_packet

- description: A packet built from a runtime/canonical mutation report remains blocked.
- expected_operator_posture: no_go_blocked
- actual_operator_posture: no_go_blocked
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 2
- boundary_error: false
- passed: true
- actual_error: none

### human_review_packet

- description: A packet with insufficient evidence requires human review instead of action.
- expected_operator_posture: go_requires_human_review
- actual_operator_posture: go_requires_human_review
- expected_action_readiness: human_approval_required
- actual_action_readiness: human_approval_required
- expected_human_decision: provide_missing_evidence
- actual_human_decision: provide_missing_evidence
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 0
- boundary_error: false
- passed: true
- actual_error: none

### failed_stress_packet

- description: A clean report paired with a failed stress matrix is blocked.
- expected_operator_posture: no_go_blocked
- actual_operator_posture: no_go_blocked
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 1
- boundary_error: false
- passed: true
- actual_error: none

### reproducible_checked_artifacts

- description: Checked packet JSON/Markdown exactly match regenerated output.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: advisory_report_allowed
- actual_action_readiness: advisory_report_allowed
- expected_human_decision: none
- actual_human_decision: none
- expected_reproducibility_status: reproducible
- actual_reproducibility_status: reproducible
- blocker_count: 0
- boundary_error: false
- passed: true
- actual_error: none

### stale_json_artifact

- description: A stale checked JSON packet artifact is blocked.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: blocked
- actual_reproducibility_status: blocked
- blocker_count: 1
- boundary_error: false
- passed: true
- actual_error: none

### malformed_json_artifact

- description: A malformed checked JSON packet artifact is blocked.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: blocked
- actual_reproducibility_status: blocked
- blocker_count: 2
- boundary_error: false
- passed: true
- actual_error: none

### missing_json_artifact

- description: A missing checked packet artifact is blocked.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: blocked
- actual_reproducibility_status: blocked
- blocker_count: 1
- boundary_error: false
- passed: true
- actual_error: none

### root_escape_artifact

- description: A checked artifact path outside the declared root fails closed.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 1
- boundary_error: true
- passed: true
- actual_error: packet artifact path escapes root

### cerebro_state_artifact_target

- description: A checked artifact path under .cerebro fails closed.
- expected_operator_posture: not_applicable
- actual_operator_posture: not_applicable
- expected_action_readiness: blocked
- actual_action_readiness: blocked
- expected_human_decision: review_blockers
- actual_human_decision: review_blockers
- expected_reproducibility_status: not_applicable
- actual_reproducibility_status: not_applicable
- blocker_count: 1
- boundary_error: true
- passed: true
- actual_error: packet artifact path may not live under .cerebro
