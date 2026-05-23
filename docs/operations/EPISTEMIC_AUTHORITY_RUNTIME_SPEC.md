# Epistemic Authority Runtime Spec

status: specification
version: 2
created_at: 2026-04-24
updated_at: 2026-04-24
authority: non-runtime; docs-only operational specification
state_change: none

## 1. Purpose

Cerebro's next layer is a Risk-Adaptive Epistemic Runtime: a discipline for
checking whether an agent has enough current, trusted, proportionate evidence
to act.

Core rule:

```text
Explore fast.
Trust slowly.
Act only with proof.
Demote when proof degrades.
```

Authority rule:

```text
Authority is not granted once.
It is continuously earned, propagated, and revocable.
```

This document turns that rule into an operational specification. It does not
implement the runtime.

## 2. Scope

This specification governs future derived and canonical slices that handle
epistemic authority, evidence sufficiency, claim evaluation, readiness reports,
promotion, demotion, and protocol self-audit.

It applies to:

- docs-only conceptual slices;
- `experiments/` advisory layers;
- future advisory integration;
- future canonical runtime integration, if a separate trigger authorizes it.

It does not authorize any implementation by itself.

## 3. Non-Negotiable Distinctions

These distinctions are design constraints, not slogans:

```text
registered != true
retrieved != relevant
remembered != trusted
silence != negative evidence
authorization to explore != authorization to trust
canonical != permanent
permission != sufficient evidence
```

Operational consequences:

- A registered source may be stale, partial, superseded, or wrong.
- A retrieved source may be irrelevant to the decision.
- A remembered fact is cached evidence, not current authority.
- Missing text cannot become factual denial.
- Permission to explore does not grant trust in the result.
- Canonical authority can be demoted when proof degrades.
- An actor may be allowed to attempt a step while still lacking evidence to act.

## 4. Authority States

Authority is a state machine, not a boolean.

```text
advisory -> provisional -> canonical
canonical -> provisional -> advisory -> deprecated | quarantined
```

### advisory

May inform humans or LLMs. Must not decide action. Examples:
`ClaimCandidate`, `EvaluationFinding`, context reports, readiness reports.

### provisional

May guide a repeated workflow inside a declared boundary. Requires expiry,
review condition, dependencies, rollback story, and no silent promotion.

### canonical

Authoritative for runtime behavior or state. Requires a formal trigger,
architecture decision when structural, tests, rollback evidence, full gate, and
human approval where authority increases.

### deprecated

Readable for audit, not suitable for new operational decisions.

### quarantined

Readable but isolated because it is conflicting, unsafe, malformed, suspected to
have induced error, or too stale for use. Quarantine removes authority without
deleting history.

## 5. Operational Zones

Zones define the minimum control level. The final authorization still depends
on risk.

### ZONE 0: Observation

Read, inspect, compare, diagnose, audit. No mutation and no authority. Default
gate: G0.

### ZONE 1: Derived Experiment

Local `experiments/` work that is read-only, non-authoritative, no state
mutation, no runtime gate, no canonical claim graph, focused tests, and README
limits. Default gate: G2.

### ZONE 2: Advisory Integration

Reports, LLM-facing guidance, scoring, intake packs, readiness summaries, or
recommendations that influence humans or agents without mutating canonical
state. Default gate: G3.

### ZONE 3: Canonical Runtime

`core/`, `cli/`, `.cerebro/state.json`, schema, apply, verify, rollback,
session behavior, canonical claim graph, or runtime gate. Default gate: G4.

## 6. Reversibility-Weighted Authorization

Location is not enough. Authorization is weighted by risk:

```text
risk_score =
  authority_impact
  x blast_radius
  x irreversibility
  x uncertainty

authorization_level =
  max(zone_floor, risk_score)
```

Normative rules:

- Docs are not automatically low risk if they rewrite decision history.
- Experiments are not automatically low risk if their output is treated as
  authority.
- Core is never low-friction.
- Reversible exploration may be fast only when it cannot silently gain
  authority.

## 7. Blast Radius Declaration

Every non-trivial slice must declare blast radius before execution.

Canonical TOML shape:

```toml
[blast_radius]
writes = []
reads = []
authority_impact = "none"        # none|advisory|provisional|canonical
runtime_impact = "none"          # none|indirect|direct
state_impact = "none"            # none|read-only|derived-output|canonical-mutation
third_party_impact = "none"      # none|read-only|derived-output|mutation
reversibility = "high"           # high|medium|low|none
rollback = "git-revert"          # delete-folder|git-revert|manual-reconstruction|not-reversible
gate_level = "G1"                # G0|G1|G2|G3|G4
promotion_path = "requires-trigger"
demotion_path = "mark-advisory-or-quarantine"
stop_conditions = []
```

If the actual slice exceeds this declaration, stop and write a narrower or
stronger trigger.

## 8. Risk Budget

A slice must also declare what it is allowed to spend.

Canonical TOML shape:

```toml
[risk_budget]
max_writes = 0
allowed_paths = []
allowed_authority_impact = "none"    # none|advisory|provisional|canonical
allowed_runtime_impact = "none"      # none|indirect|direct
max_irreversibility = "high"         # high|medium|low|none
required_rollback_evidence = "none"  # none|delete-folder|git-revert|manual-proof|test-proof
human_approval_required = false
```

If `allowed_authority_impact` is `advisory`, the output cannot be used as
permission. If it is `canonical`, a separate heavy trigger is required.

## 9. Promotion Gates

Promotion path:

```text
Observation -> Derived -> Advisory -> Canonical
```

Promotion requires:

- explicit evidence;
- fixtures or tests when behavior is repeatable;
- known source provenance;
- no unresolved stronger conflict;
- positive sufficiency result;
- dependencies declared;
- effective confidence above the target threshold;
- rollback or demotion path;
- human approval when authority increases to provisional or canonical.

No output from `claim_extraction`, `claim_evaluation`, `context_vectors`,
`context_discovery`, or `context_advisor` may jump directly to canonical.

## 10. Demotion Triggers

Demotion is recommended automatically but applied to canonical authority only
with human approval, except temporary quarantine pending review.

Triggers:

- conflict with a newer or more authoritative source;
- confidence below threshold;
- foundational dependency degraded;
- protocol self-audit detects induced error;
- absence of revalidation after N critical sessions;
- canonical behavior correlates with corrected decisions;
- source supersession;
- stale registered evidence;
- scope drift beyond original approval.

Demoted items remain readable. They lose operational authority.

## 11. Confidence Propagation

Every evaluated conclusion must list required dependencies.

Formula:

```text
effective_confidence(A) =
  min(
    local_confidence(A),
    effective_confidence(dependency_1),
    effective_confidence(dependency_2),
    ...
  )
```

Rules:

- No conclusion can be more trusted than its weakest required foundation.
- Missing required dependency sets effective confidence to `unknown`, not zero.
- Active conflict caps effective confidence at `partial` until adjudicated.
- Confidence output is advisory evidence unless a future canonical trigger says
  otherwise.

## 12. Sufficiency Gates

Sufficiency is action-relative.

Allowed statuses:

```text
insufficient
partial
sufficient
sufficient_with_human_review
blocked
```

Meaning:

- `insufficient`: required evidence is missing.
- `partial`: evidence exists but has gaps, stale sources, or weak dependencies.
- `sufficient`: evidence is enough for the declared action and risk level.
- `sufficient_with_human_review`: enough to proceed only after explicit human
  review.
- `blocked`: policy, conflict, trigger, gate, or risk budget blocks action.

Sufficiency must explain missing claims, missing sources, accepted gaps,
blocker gaps, and evidence that would change the verdict.

## 13. Memory Decay

Memory decay reduces authority. It does not delete memory.

Rules:

- Knowledge not revalidated loses confidence over time or after critical
  sessions.
- Decay affects operational use, not audit readability.
- Revalidation can restore confidence.
- Decayed memory may remain useful for historical context.
- Decay must never fabricate a negative claim.

Memory health states:

```text
trusted
untested
stale_by_nonuse
stale_by_conflict
superseded
rejected
```

## 14. Staleness Taxonomy

Staleness is claim-level where possible.

Types:

- `stale-by-age`: not refreshed within its decay policy.
- `stale-by-conflict`: contradicted by stronger evidence.
- `stale-by-supersession`: explicitly replaced.
- `stale-by-dependency`: a required foundation degraded.
- `stale-by-protocol-drift`: the protocol that made the claim actionable no
  longer matches current governance.

Recent files can be stale. Old files can remain valid. Staleness means evidence
is not strong enough for this action.

## 15. Action Readiness

Final advisory readiness must return one of:

```text
no_action
observe_only
propose_only
advisory_report_allowed
derived_experiment_allowed
canonical_change_requires_trigger
human_approval_required
blocked
```

The readiness output must include:

- action profile;
- sufficiency status;
- authority state;
- risk budget status;
- conflicts;
- stale claims;
- missing evidence;
- approval requirement;
- next evidence needed.

## 16. Metacognitive Handoff

The agent must ask for human intervention when it detects:

- low sufficiency for a consequential action;
- unresolved conflict;
- ambiguous authority;
- high risk;
- missing rollback evidence;
- exceeded risk budget;
- proposed authority promotion;
- canonical demotion or override.

Handoff format:

```text
known:
unknown:
conflicts:
missing_evidence:
risk:
recommended_human_decision:
```

The handoff must explain what is known, what is not known, and what evidence
would change the result.

## 17. Epistemic Observability

Future reports should record:

- sources read;
- claims extracted;
- claims evaluated;
- conflicts detected;
- decisions blocked;
- evidence used;
- evidence rejected;
- sufficiency level at decision time;
- authority state at decision time;
- risk budget consumed;
- human approval type, if any.

Do not log private chain-of-thought. Log structured rationale and evidence.

## 18. Human Approval Taxonomy

Approval is typed:

- `acknowledge`: human saw the advisory output.
- `approve_action`: human approves the bounded action.
- `approve_promotion`: human approves authority increase.
- `approve_demotion`: human approves authority decrease.
- `override_block`: human overrides a block and accepts risk.
- `adjudicate_conflict`: human selects or edits the winning evidence.

Approval expires when source set, write set, risk class, or authority impact
changes materially.

## 19. Anti-Noise Rule

Retrospective and self-audit must not automatically write lessons as truth.

Rules:

- emit learning candidates, not memory updates;
- include evidence for each candidate;
- human approves, rejects, or edits;
- rejected candidates do not become consolidated memory;
- broad lessons without source evidence are noise;
- the goal is lower human review cost without polluting canonical memory.

## 20. Standing Authorization for Derived Experiments

Derived experiments may move quickly when all conditions hold:

- path is under `experiments/`;
- read-only toward target projects and `.cerebro/`;
- non-authoritative;
- no state mutation;
- no runtime gate;
- no canonical claim graph;
- no network/model dependency unless separately authorized;
- focused tests;
- README states limits;
- full AGENTS-equivalent gate at closure under current project discipline.

This authorizes exploration, not trust. Any use as advisory integration,
workflow requirement, or runtime behavior requires promotion gates.

Never allowed without separate trigger:

- writes under `.cerebro/`;
- core/cli/extensions mutation;
- schema/state changes;
- third-party mutation;
- canonical claim graph;
- runtime gate;
- treating report output as permission.

## 21. Protocol Self-Audit

Protocol self-audit evaluates whether Cerebro's method induced bad decisions.

Inputs:

- decision records or reports;
- protocol sources read;
- claims used and ignored;
- later corrections;
- conflicts discovered after action;
- human overrides;
- gate failures;
- repeated friction points.

Signals:

- file repeatedly read before corrected decisions;
- protocol rule correlated with reversals;
- required source rarely changes sufficiency;
- source hierarchy routes agents toward stale claims;
- guardrail blocks reversible low-risk work too often;
- canonical behavior correlates with corrected action.

Outputs are advisory:

- demotion recommendation;
- quarantine recommendation;
- protocol edit candidate;
- fixture candidate;
- lighter gate candidate for reversible exploration;
- human adjudication request.

## 22. Recovery / Re-Promotion

Deprecated or quarantined items can return to authority.

Requirements:

- new evidence;
- test or fixture where behavior is repeatable;
- no active stronger conflict;
- dependency confidence restored;
- sufficiency positive for the target action;
- human approval for canonical restoration;
- explicit record of why the prior demotion no longer applies.

Absence of recent failure is not recovery.

## 23. Examples

### Docs edit that rewrites historical decision context

Zone: 0 or 1 by path, but risk can rise. If the edit changes why a prior
decision was made, it needs G1 plus explicit rollback and may need human review.
Docs are not automatically low risk.

### Fast read-only experiment

`experiments/epistemic_readiness/` reads bounded source heads, emits advisory
Markdown/JSON, has focused tests, and says `state_change: none`. Readiness:
`derived_experiment_allowed`. It cannot mutate state.

### Claim extraction is not a claim graph

`claim_extraction` emits `ClaimCandidate`. It cannot resolve final authority,
truth, confidence, or runtime permission.

### Claim evaluation is not a runtime gate

`claim_evaluation` emits advisory findings. Even `ready` means "evidence looks
sufficient for this advisory slice", not "apply may proceed".

### Schema exists -> schema validated -> Edge Functions ready

`Edge Functions ready` depends on `schema exists`, `schema validated`, current
function contract, and permitted next action. If `schema validated` is missing,
the readiness is at most partial even when `schema exists` is true.

### Demotion of suspicious canonical behavior

If a canonical protocol rule appears in repeated corrected decisions,
self-audit recommends quarantine. Human approval is required before demoting
canonical authority except emergency quarantine pending review.

### Protocol self-audit source correlation

If a source hierarchy file repeatedly routes agents to stale diagnostics,
self-audit emits a protocol-edit candidate. It does not rewrite the hierarchy.

### Memory decay

A long-lived memory claim not revalidated across N relevant sessions becomes
`stale_by_nonuse`. It remains readable but cannot support high-impact action
without refresh.

### Human handoff by low sufficiency

If the source set lacks current next-action evidence, readiness returns
`human_approval_required` or `blocked` with `missing_evidence` rather than
guessing.

### Re-promotion after evidence

A quarantined rule can return to provisional if a new fixture proves the old
failure is fixed, no conflict remains, and a human approves the promotion path.

## 24. Stop Conditions

Stop if:

- advisory output is treated as canonical truth;
- report readiness is treated as permission;
- silence becomes negative evidence;
- retrieval is treated as relevance;
- registration is treated as truth;
- memory is treated as trust;
- risk-adaptive controls reduce evidence instead of matching risk;
- promotion lacks evidence;
- canonical promotion lacks human approval;
- demotion hides history;
- a second source of truth appears;
- implementation starts without a separate trigger.

## 25. What This Does Not Authorize

This spec does not authorize:

- edits to `core/`, `cli/`, `extensions/`, `.cerebro/`, state, or schema;
- a runtime gate;
- a canonical claim graph;
- automatic promotion or demotion;
- automatic memory learning;
- treating reports as permission;
- third-party mutation;
- network/model-backed authority;
- canonical integration of `claim_extraction` or `claim_evaluation`.

The next implementation, if chosen, must be a separate formally triggered
derived experiment or advisory report generator with its own blast radius,
risk budget, focused tests, and full gate closure.
