# Epistemic Readiness Human Decision Taxonomy

## Boundary

- state_change: none
- authority: non-authoritative; advisory human decision taxonomy evidence only
- taxonomy_role: advisory handoff decision vocabulary only
- human_decision_is_not_permission: true
- compatible_pair_is_not_permission: true
- taxonomy_is_not_memory: true
- taxonomy_is_not_authority: true
- taxonomy_is_not_runtime_gate: true
- taxonomy_is_not_claim_graph: true
- silence_is_not_negative_evidence: true

## Summary

- decision_count: `6`
- every entry has `can_mutate_state=false`
- every entry has `can_grant_permission=false`

## Decision Matrix

| Decision | Compatible Readiness | Escalation |
|---|---|---|
| `none` | `no_action` | `none` |
| `acknowledge` | `advisory_report_allowed`, `observe_only` | `operator_acknowledgement` |
| `approve_baseline_refresh` | `human_approval_required` | `human_approval` |
| `adjudicate_conflict` | `human_approval_required` | `human_adjudication` |
| `provide_missing_evidence` | `human_approval_required` | `evidence_request` |
| `review_blockers` | `blocked` | `blocker_review` |

## Entries

### none

- meaning: No human decision is requested because the advisory evidence contains no conflict, missing evidence, drift approval, or blocker.
- escalation_level: `none`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- clean metacognitive handoff
- zero active conflicts
- zero insufficient findings
- zero blockers

Allowed next actions:

- record that no human decision is currently requested
- continue observation in derived layers
- open a future trigger only if separate evidence appears

Forbidden interpretations:

- treat decision as permission
- treat clean advisory evidence as canonical truth
- skip future gates because no action is requested now

### acknowledge

- meaning: A human may acknowledge advisory evidence that is visible but not severe enough to require approval, adjudication, or blocker review.
- escalation_level: `operator_acknowledgement`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- advisory report allowed readiness
- no active blocker
- no authority promotion requested

Allowed next actions:

- record acknowledgement in a future human-facing note
- keep the artifact advisory
- open a separate trigger if the acknowledgement implies work

Forbidden interpretations:

- treat decision as permission
- treat acknowledgement as approval
- promote advisory evidence to authority

### approve_baseline_refresh

- meaning: A human may approve refreshing a derived replay baseline after material drift is visible and blockers are absent.
- escalation_level: `human_approval`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- material drift or refresh candidate
- no regression
- no high or blocking protocol self-audit candidate
- explicit human approval before any refresh

Allowed next actions:

- open a separate baseline-refresh trigger
- prepare a derived baseline refresh audit packet
- apply only the approved derived baseline refresh inside that trigger

Forbidden interpretations:

- treat decision as permission
- refresh the baseline automatically
- treat replay freshness as canonical truth
- mutate canonical state

### adjudicate_conflict

- meaning: A human must resolve or explicitly park conflicting advisory evidence before an agent treats the affected conclusion as usable.
- escalation_level: `human_adjudication`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- named conflict
- conflicting source evidence
- authority and freshness context for each side

Allowed next actions:

- request human conflict adjudication
- mark conflict unresolved in advisory output
- open a separate promotion or demotion trigger after adjudication

Forbidden interpretations:

- treat decision as permission
- resolve conflict by recency alone
- hide unresolved conflict behind a green summary
- promote or demote authority automatically

### provide_missing_evidence

- meaning: The agent lacks enough evidence and must seek bounded evidence rather than infer from silence.
- escalation_level: `evidence_request`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- insufficient finding or missing-evidence note
- description of the missing source or fact
- explicit statement that silence is not negative evidence

Allowed next actions:

- ask for the missing evidence
- read a newly approved bounded source in a future derived run
- rerun the advisory report after evidence is supplied

Forbidden interpretations:

- treat decision as permission
- infer falsehood from absent evidence
- invent a source
- import or register sources automatically

### review_blockers

- meaning: The current path is blocked by protocol risk, regression, or another high-severity advisory signal and must stop.
- escalation_level: `blocker_review`
- can_mutate_state: `false`
- can_grant_permission: `false`

Required evidence:

- blocked readiness
- blocker reason
- rollback or stop condition context
- explicit human review before continuation

Allowed next actions:

- stop the current action path
- inspect blocker evidence
- open a corrective trigger before retrying

Forbidden interpretations:

- treat decision as permission
- continue with best effort
- override blocker silently
- demote canonical behavior automatically

## Must Not Apply

- mutate state
- register sources
- update replay baseline
- write memory automatically
- act as runtime gate
- create canonical claim graph
- promote or demote authority
- treat a human decision as permission
- treat a compatible pair as permission
- infer negative evidence from silence
