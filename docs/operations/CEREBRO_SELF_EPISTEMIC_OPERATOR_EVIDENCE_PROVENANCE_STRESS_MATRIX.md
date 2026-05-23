# Epistemic Readiness Operator Evidence Provenance Stress Matrix

## Boundary

- state_change: none
- authority: non-authoritative; advisory operator evidence provenance stress matrix only
- matrix_role: advisory degraded-evidence operator evidence provenance stress matrix only
- provenance_stress_matrix_is_not_permission: true
- provenance_stress_matrix_is_not_memory: true
- provenance_stress_matrix_is_not_authority: true
- provenance_stress_matrix_is_not_runtime_gate: true
- provenance_stress_matrix_is_not_claim_graph: true
- provenance_stress_matrix_is_not_source_registry: true
- dependency_map_is_not_canonical_graph: true
- artifact_digest_is_not_truth: true
- text_digest_only_is_not_truth: true
- silence_is_not_negative_evidence: true

## Summary

- scenario_count: 9
- pass_count: 9
- fail_count: 0
- all_scenarios_passed: true
- blocker_count: 7
- boundary_error_count: 4
- text_digest_only_count: 1

## Scenarios

| Scenario | Expected | Observed | Passed | Blockers | Boundary Errors | Text Digest Only |
|---|---|---|---|---:|---:|---:|
| clean_provenance_chain | none/advisory_report_allowed | none/advisory_report_allowed | true | 0 | 0 | 0 |
| missing_artifact | review_blockers/blocked | review_blockers/blocked | true | 1 | 0 | 0 |
| malformed_json | review_blockers/blocked | review_blockers/blocked | true | 1 | 0 | 0 |
| mutating_artifact | review_blockers/blocked | review_blockers/blocked | true | 1 | 0 | 0 |
| root_escape | review_blockers/blocked | review_blockers/blocked | true | 1 | 1 | 0 |
| cerebro_state_target | review_blockers/blocked | review_blockers/blocked | true | 1 | 1 | 0 |
| duplicate_artifact_id | review_blockers/blocked | review_blockers/blocked | true | 1 | 1 | 0 |
| missing_upstream_dependency | review_blockers/blocked | review_blockers/blocked | true | 1 | 1 | 0 |
| text_digest_only_report | none/advisory_report_allowed | none/advisory_report_allowed | true | 0 | 0 | 1 |

## Must Not Apply

- mutate state
- register sources
- refresh artifacts automatically
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- create canonical evidence graph
- promote or demote authority
- treat provenance output as permission
- treat passing scenarios as permission
- treat artifact digests as truth
- hide blockers
- hide malformed provenance input
- hide dependency gaps
- infer negative evidence from silence
