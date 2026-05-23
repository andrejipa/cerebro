# Epistemic Readiness Decision Taxonomy Conformance

## Boundary

- state_change: none
- authority: non-authoritative; advisory decision taxonomy conformance evidence only
- conformance_role: advisory stress-matrix-to-taxonomy conformance evidence only
- conformance_is_not_permission: true
- covered_pair_is_not_permission: true
- incompatible_pair_must_be_visible: true
- conformance_is_not_memory: true
- conformance_is_not_authority: true
- conformance_is_not_runtime_gate: true
- conformance_is_not_claim_graph: true
- silence_is_not_negative_evidence: true

## Summary

- case_count: `5`
- pass_count: `5`
- fail_count: `0`
- all_cases_passed: `true`

## Conformance Matrix

| Scenario | Decision | Readiness | Compatible | Stress Passed | Conformance | Issues |
|---|---|---|---|---|---|---|
| `clean_no_action` | `none` | `no_action` | `true` | `true` | `true` | none |
| `insufficient_evidence` | `provide_missing_evidence` | `human_approval_required` | `true` | `true` | `true` | none |
| `active_conflict` | `adjudicate_conflict` | `human_approval_required` | `true` | `true` | `true` | none |
| `drift_review_required` | `approve_baseline_refresh` | `human_approval_required` | `true` | `true` | `true` | none |
| `protocol_blocker` | `review_blockers` | `blocked` | `true` | `true` | `true` | none |

## Case Details

### clean_no_action

- recommended_human_decision: `none`
- action_readiness: `no_action`
- escalation_level: `none`
- taxonomy_compatible: `true`
- stress_scenario_passed: `true`
- conformance_passed: `true`

Required evidence:

- clean metacognitive handoff
- zero active conflicts
- zero insufficient findings
- zero blockers

Allowed next actions:

- record that no human decision is currently requested
- continue observation in derived layers
- open a future trigger only if separate evidence appears

Issues:

- none

### insufficient_evidence

- recommended_human_decision: `provide_missing_evidence`
- action_readiness: `human_approval_required`
- escalation_level: `evidence_request`
- taxonomy_compatible: `true`
- stress_scenario_passed: `true`
- conformance_passed: `true`

Required evidence:

- insufficient finding or missing-evidence note
- description of the missing source or fact
- explicit statement that silence is not negative evidence

Allowed next actions:

- ask for the missing evidence
- read a newly approved bounded source in a future derived run
- rerun the advisory report after evidence is supplied

Issues:

- none

### active_conflict

- recommended_human_decision: `adjudicate_conflict`
- action_readiness: `human_approval_required`
- escalation_level: `human_adjudication`
- taxonomy_compatible: `true`
- stress_scenario_passed: `true`
- conformance_passed: `true`

Required evidence:

- named conflict
- conflicting source evidence
- authority and freshness context for each side

Allowed next actions:

- request human conflict adjudication
- mark conflict unresolved in advisory output
- open a separate promotion or demotion trigger after adjudication

Issues:

- none

### drift_review_required

- recommended_human_decision: `approve_baseline_refresh`
- action_readiness: `human_approval_required`
- escalation_level: `human_approval`
- taxonomy_compatible: `true`
- stress_scenario_passed: `true`
- conformance_passed: `true`

Required evidence:

- material drift or refresh candidate
- no regression
- no high or blocking protocol self-audit candidate
- explicit human approval before any refresh

Allowed next actions:

- open a separate baseline-refresh trigger
- prepare a derived baseline refresh audit packet
- apply only the approved derived baseline refresh inside that trigger

Issues:

- none

### protocol_blocker

- recommended_human_decision: `review_blockers`
- action_readiness: `blocked`
- escalation_level: `blocker_review`
- taxonomy_compatible: `true`
- stress_scenario_passed: `true`
- conformance_passed: `true`

Required evidence:

- blocked readiness
- blocker reason
- rollback or stop condition context
- explicit human review before continuation

Allowed next actions:

- stop the current action path
- inspect blocker evidence
- open a corrective trigger before retrying

Issues:

- none

## Must Not Apply

- mutate state
- register sources
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- promote or demote authority
- treat conformance pass as permission
- hide incompatible pairs
- infer negative evidence from silence
