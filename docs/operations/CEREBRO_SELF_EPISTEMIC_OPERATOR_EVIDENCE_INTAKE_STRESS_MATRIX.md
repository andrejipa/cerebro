# Epistemic Readiness Operator Evidence Intake Stress Matrix

## Boundary

- state_change: none
- authority: non-authoritative; advisory operator evidence intake stress matrix only
- matrix_role: advisory degraded-evidence operator evidence intake stress matrix only
- intake_stress_matrix_is_not_permission: true
- intake_stress_matrix_is_not_memory: true
- intake_stress_matrix_is_not_authority: true
- intake_stress_matrix_is_not_runtime_gate: true
- intake_stress_matrix_is_not_claim_graph: true
- intake_output_is_not_permission: true
- passing_scenario_is_not_permission: true
- digest_equality_is_not_truth: true
- malformed_intake_input_is_blocking_evidence: true
- silence_is_not_negative_evidence: true

## Summary

- scenario_count: `8`
- pass_count: `8`
- fail_count: `0`
- all_scenarios_passed: `true`
- blocker_count: `7`
- boundary_error_count: `7`

## Scenarios

| Scenario | Expected Decision | Observed Decision | Action Readiness | Boundary Error | Passed |
|---|---|---|---|---|---|
| `clean_manifest` | `none` | `none` | `advisory_report_allowed` | `false` | `true` |
| `missing_artifact` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `stale_digest` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `root_escape` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `non_json_artifact` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `mutating_payload` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `duplicate_artifact_id` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |
| `missing_required_artifact` | `review_blockers` | `review_blockers` | `blocked` | `true` | `true` |

## Visible Errors

- `missing_artifact`: drift_policy: artifact file is missing: missing-drift-policy.json
- `stale_digest`: metacognitive_handoff: digest mismatch
- `root_escape`: baseline_lifecycle: artifact path escapes root: ../outside.json
- `non_json_artifact`: baseline_lifecycle: artifact path must point to a .json file
- `mutating_payload`: drift_policy: artifact must declare state_change none
- `duplicate_artifact_id`: operator evidence intake artifact ids must be unique
- `missing_required_artifact`: missing required artifact declaration: operator_packet_stress_matrix

## Must Not Apply

- mutate state
- register sources
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- promote or demote authority
- treat intake output as permission
- treat passing scenarios as permission
- treat digest equality as truth
- hide blockers
- hide malformed manifest input
- hide stale or mismatched digest input
- infer negative evidence from silence
