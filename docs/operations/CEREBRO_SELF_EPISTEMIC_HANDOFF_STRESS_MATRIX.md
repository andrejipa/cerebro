# Epistemic Readiness Handoff Stress Matrix

## Boundary

- state_change: none
- authority: non-authoritative; advisory handoff stress matrix evidence only
- matrix_role: advisory degraded-evidence handoff stress matrix only
- stress_matrix_is_not_permission: true
- stress_matrix_is_not_memory: true
- stress_matrix_is_not_authority: true
- stress_matrix_is_not_runtime_gate: true
- stress_matrix_is_not_claim_graph: true
- passing_scenario_is_not_permission: true
- silence_is_not_negative_evidence: true

## Summary

- scenario_count: `5`
- pass_count: `5`
- fail_count: `0`

## Scenario Matrix

| Scenario | Expected Decision | Observed Decision | Expected Readiness | Observed Readiness | Pass |
|---|---|---|---|---|---|
| `clean_no_action` | `none` | `none` | `no_action` | `no_action` | yes |
| `insufficient_evidence` | `provide_missing_evidence` | `provide_missing_evidence` | `human_approval_required` | `human_approval_required` | yes |
| `active_conflict` | `adjudicate_conflict` | `adjudicate_conflict` | `human_approval_required` | `human_approval_required` | yes |
| `drift_review_required` | `approve_baseline_refresh` | `approve_baseline_refresh` | `human_approval_required` | `human_approval_required` | yes |
| `protocol_blocker` | `review_blockers` | `review_blockers` | `blocked` | `blocked` | yes |

## Scenario Details

### clean_no_action

- title: Clean evidence produces no human decision
- purpose: Prove the handoff can say no action when all evidence is clean.
- recommended_human_decision: `none`
- action_readiness: `no_action`
- passed: `true`

Missing evidence:

- none

Conflicts:

- none

### insufficient_evidence

- title: Insufficient evidence asks for missing evidence
- purpose: Prove low sufficiency is not treated as permission to continue.
- recommended_human_decision: `provide_missing_evidence`
- action_readiness: `human_approval_required`
- passed: `true`

Missing evidence:

- stress-claim-1: sufficiency=insufficient
- stress-claim-1: operational_readiness=needs_review
- 1 findings are insufficient

Conflicts:

- none

### active_conflict

- title: Active conflict asks for adjudication
- purpose: Prove conflict dominates clean readiness and forces review.
- recommended_human_decision: `adjudicate_conflict`
- action_readiness: `human_approval_required`
- passed: `true`

Missing evidence:

- none

Conflicts:

- stress-claim-1: conflict=active

### drift_review_required

- title: Material drift requires explicit baseline refresh approval
- purpose: Prove drift evidence requests approval without refreshing anything.
- recommended_human_decision: `approve_baseline_refresh`
- action_readiness: `human_approval_required`
- passed: `true`

Missing evidence:

- baseline lifecycle requires human action: approve_baseline_refresh
- drift policy requires human action: approve_baseline_refresh

Conflicts:

- none

### protocol_blocker

- title: Protocol blocker stops action
- purpose: Prove protocol risk blocks action instead of asking for normal approval.
- recommended_human_decision: `review_blockers`
- action_readiness: `blocked`
- passed: `true`

Missing evidence:

- drift policy requires human action: review_blockers
- protocol self-audit reported 1 high/blocking candidates

Conflicts:

- none

## Must Not Apply

- mutate state
- register sources
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- promote or demote authority
- treat green scenarios as permission
- infer negative evidence from silence
