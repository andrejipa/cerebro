# Handoff - Risk-Adaptive Epistemic Runtime

## Read This As Your Own Prior Reasoning

You are continuing the Cerebro epistemic-runtime line of thought. Do not treat
this as generic brainstorming. Treat it as the current conceptual frontier that
must be turned into bounded specs and then, only where authorized, into derived
experiments.

The project is still under deliberate freeze for canonical-runtime growth. The
goal is not to bypass the freeze. The goal is to stop using static defenses
where dynamic, risk-proportional defenses are the better design.

## Current Operational Reality

Cerebro has already moved beyond the older "persistent memory" framing.

The current thesis is:

```text
Cerebro is an epistemic runtime for agents.
It must not only remember.
It must evaluate whether the agent has sufficient, current, trusted evidence to act.
```

Implemented derived tracks already exist:

```text
experiments/context_discovery/
experiments/context_vectors/
experiments/context_advisor/
experiments/claim_extraction/
experiments/claim_evaluation/
```

Recent epistemic-runtime slices have already established:

```text
ClaimCandidate extraction is deterministic, bounded, read-only, and non-authoritative.
Claim evaluation is advisory-only and evaluates authority, confidence, sufficiency,
conflict, supersession, staleness-by-conflict, and readiness.
Self-readiness reports have been run over Cerebro's own operational sources.
Temporal trigger-consumption claims were normalized so trigger ids become subjects.
```

Do not regress from this state. Do not reopen claim extraction as if it were only
an idea. The next conceptual work should build on top of it.

## Non-Negotiable Distinctions

Preserve these distinctions exactly:

```text
registered != true
retrieved != relevant
remembered != trusted
silence != negative evidence
authorization to explore != authorization to trust
canonical != permanent
```

These are not slogans. They are design constraints.

## Maximum Formulation

The mature formulation is:

```text
Risk-Adaptive Epistemic Runtime
```

Core rule:

```text
Explore fast.
Trust slowly.
Act only with proof.
Demote when proof degrades.
```

Stronger authority rule:

```text
Authority is not granted once.
It is continuously earned, propagated, and revocable.
```

## Why The Current Defense Model Is Insufficient

The current Cerebro defense model is strong, but too static.

It protects canonical runtime well, but it tends to apply similar friction to:

```text
canonical runtime mutation
derived experiments
docs-only reasoning
advisory reports
discardable probes
```

That reduces speed exactly where the project needs exploration.

Do not propose "less defense" as the answer. The correct answer is:

```text
defense proportional to authority impact, reversibility, blast radius, and uncertainty
```

## Operational Zones

Keep the zone model, but do not let it be the only risk model.

```text
ZONE 0 - Observation
- reading, analysis, audit, diagnosis
- no heavy trigger
- no full gate by default

ZONE 1 - Derived Experiment
- experiments/
- read-only
- non-authoritative
- focused tests
- fast exploration

ZONE 2 - Advisory Integration
- reports, intake packs, scoring, LLM-facing guidance
- influences recommendations but not canonical state
- light formal trigger
- architecture/doc-governance gate

ZONE 3 - Canonical Runtime
- core/, cli/, state, schema, apply, verify, rollback
- heavy formal trigger
- full gate before and after
- strict stop conditions
```

Zone is a floor, not the whole risk calculation.

## Reversibility-Weighted Authorization

The important correction is that speed should not depend only on location.

Risk should include reversibility.

Conceptual formula:

```text
risk_score =
  authority_impact
  x blast_radius
  x irreversibility
  x uncertainty

authorization_level =
  max(zone_floor, risk_score)
```

Implications:

```text
docs/ is not automatically safe if the edit destroys historical decision context.
experiments/ is not automatically safe if output is treated as authority.
core/ is never low-friction, but a reversible, tested, rollback-proven change is less risky than an irreversible one.
```

The next policy should require a Blast Radius Declaration:

```text
writes:
reads:
authority_impact:
runtime_impact:
reversibility:
rollback:
gate_level:
promotion_path:
stop_conditions:
```

## Promotion Is Only Half The System

The old model had a good promotion path:

```text
Observation -> Derived -> Advisory -> Canonical
```

That is not enough.

A mature system also needs demotion.

Core rule:

```text
A canonical claim or behavior can be demoted
when protocol self-audit evidence exceeds a threshold.
Demotion requires human approval.
Demoted behavior remains readable but loses authority.
```

Authority states:

```text
canonical
provisional
advisory
deprecated
quarantined
```

Demotion triggers:

```text
conflict with a newer or more authoritative source
drop below confidence threshold
foundational dependency degraded
protocol self-audit detects protocol-induced error
absence of revalidation after N critical sessions
canonical behavior correlates with corrected bad decisions
```

This prevents Cerebro from fossilizing old authority.

## Confidence Must Propagate

Do not evaluate claims as isolated atoms.

Claims form a dependency network.

Rule:

```text
effective_confidence(A) =
  min(
    local_confidence(A),
    effective_confidence(dependency_1),
    effective_confidence(dependency_2),
    ...
  )
```

Principle:

```text
No conclusion can be more trusted than its weakest required foundation.
```

Example:

```text
"Edge Functions are ready"
depends on:
- schema exists
- schema was validated
- function contract is current
- runtime boundary permits the next step
```

If "schema was validated" degrades, every dependent readiness claim must degrade
automatically.

## Protocol Self-Audit

The most advanced idea is not just auditing data quality. It is auditing the
protocol itself.

Cerebro should eventually ask:

```text
Which Cerebro files were repeatedly read before corrected decisions?
Which protocol rule tends to correlate with later reversals?
Which canonical behavior induced an agent to act on stale or insufficient evidence?
Which guardrail creates too much friction for low-risk reversible exploration?
```

This is the path from static governance to adaptive governance.

## Relationship To Current Research And Market Direction

Current external direction supports this line:

```text
agentic governance
risk-based controls
AI safety levels
preparedness frameworks
agent observability
metacognitive monitoring
human handoff when risk is detected
```

But the distinctive Cerebro angle is narrower and stronger:

```text
epistemic governance
```

The question is not only:

```text
Does the agent have permission?
```

It is:

```text
Does the agent have enough trustworthy evidence to justify that permission?
```

## Suggested Next Spec

The next conceptual document should probably be:

```text
docs/operations/EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md
```

Suggested structure:

```text
1. Purpose
2. Non-Negotiable Distinctions
3. Authority States
4. Promotion Gates
5. Demotion Triggers
6. Confidence Propagation
7. Reversibility-Weighted Authorization
8. Blast Radius Declaration
9. Human Approval Points
10. Protocol Self-Audit
11. Recovery / Re-Promotion
12. Examples
13. Stop Conditions
```

This should be a spec, not an implementation. It should explicitly say what is
not yet authorized.

## Suggested Next Technical Slice

The operational next item currently points toward a tested report generator for
epistemic-readiness reports under `experiments/`.

Possible slice:

```text
experiments/epistemic_readiness/
```

or a bounded extension under:

```text
experiments/claim_evaluation/
```

Purpose:

```text
replace one-off operator scripts with repeatable, tested, advisory-only report generation
```

Inputs:

```text
bounded source heads
ClaimCandidate[]
EvaluationReport
```

Output:

```text
EpistemicReadinessReport
```

Possible fields:

```text
source_set
candidate_count
finding_count
ready_count
blocked_count
insufficient_count
temporal_claim_quality
authority_warnings
confidence_warnings
sufficiency_warnings
state_change: none
advisory_conclusion
evidence_refs
```

Strict constraints:

```text
advisory-only
read-only
no runtime gate
no claim graph authority
no state mutation
no third-party mutation
focused tests first
full AGENTS-equivalent gate at closure
```

## Do Not Do This

Do not promote `claim_extraction` or `claim_evaluation` into runtime authority.
Do not create a canonical claim graph without a separate trigger.
Do not treat readiness reports as permission to mutate anything.
Do not treat silence as negative evidence.
Do not collapse source retrieval into source relevance.
Do not use "risk-adaptive" as an excuse to skip evidence.

The design goal is not lower rigor. It is more accurate rigor.

## Best Next Move

If starting a new conversation, first read the live operational files:

```text
AGENTS.md
docs/operations/observation_center.toml
docs/operations/SYSTEM_STATE.md
docs/operations/OPPORTUNITY_MAP.md
docs/operations/FREEZE_POLICY.md
docs/operations/CEREBRO_SELF_EPISTEMIC_READINESS_REPORT.md
```

Then decide whether the next step is:

```text
1. docs-only spec: EPISTEMIC_AUTHORITY_RUNTIME_SPEC.md
2. derived implementation: tested epistemic-readiness report generator
```

If there is no active formal trigger for the chosen implementation slice, create
a narrow trigger first.

## One-Sentence Memory

Cerebro must become fast to explore, slow to trust, explicit to act, and able to
remove authority when evidence degrades.
