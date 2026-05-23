# Handoff - Epistemic Runtime Position After Closeout

## Read This First

This handoff records the point reached after the current Risk-Adaptive
Epistemic Runtime lane closed its operator-facing evidence chain.

It is not a runtime trigger. It is not permission. It is not a claim graph,
source registry, memory update, or authority promotion. It is a restart
surface for the next agent.

## Current Position

The Cerebro epistemic lane has moved past generic "memory" and "context"
language.

The current mature framing is:

```text
Cerebro is an epistemic governance layer for agentic work.
It should help decide whether an agent has enough current, trusted,
proportionate evidence to act.
```

The strongest operational rule remains:

```text
Explore fast.
Trust slowly.
Act only with proof.
Demote when proof degrades.
```

And the authority rule remains:

```text
Authority is not granted once.
It is continuously earned, propagated, and revocable.
```

## What Exists Now

The following are already real derived tracks, not just ideas:

```text
experiments/context_discovery/
experiments/context_vectors/
experiments/context_advisor/
experiments/claim_extraction/
experiments/claim_evaluation/
experiments/epistemic_readiness/
```

The current epistemic-readiness chain has:

- advisory readiness reports;
- action manifests;
- decision traces;
- trace diffs;
- protocol self-audit candidates;
- identity-stability evidence;
- baseline lifecycle and drift policy;
- replay bundle regeneration;
- metacognitive handoff;
- human-decision taxonomy and conformance;
- operator decision packet;
- operator evidence bundle;
- manifest intake;
- provenance index;
- review capsule;
- final review index;
- stress matrices;
- reproducibility checks;
- final closeout.

Slice 33 closed the current recursion lane with:

```text
closeout_status=closed_until_new_evidence
recommended_human_decision=none
action_readiness=no_action
recursive_hardening_stopped=true
blocker_count=0
missing_evidence_count=0
```

That means the current advisory evidence chain is sufficiently covered for its
own non-authoritative purpose. It does not mean Cerebro is finished forever.
It means more wrappers around this same chain are now noise until evidence
changes.

## Non-Negotiable Distinctions

Preserve these exactly:

```text
registered != true
retrieved != relevant
remembered != trusted
silence != negative evidence
authorization to explore != authorization to trust
canonical != permanent
permission != sufficient evidence
closeout != permission
digest equality != truth
stress pass != authority
no_action != human approval
```

## The Important Design Correction

The project should not become more conservative. It should become more
accurately rigorous.

Static defense says:

```text
everything important gets the same heavy ceremony
```

Risk-adaptive defense says:

```text
defense scales with authority impact, blast radius, irreversibility,
uncertainty, and evidence quality
```

The goal is not fewer gates. The goal is gates that attach to the right risk.
Derived experiments should move quickly when they are reversible and
non-authoritative. Canonical runtime authority should move slowly because its
blast radius is real.

## Why This Lane Stops Here

The current operator-evidence chain has now proved:

- its clean path is reproducible;
- degraded evidence becomes visible blockers;
- boundary errors block;
- `.cerebro/` targets block;
- mutating or stale upstream artifacts block;
- digest equality is treated as reproducibility evidence only;
- no artifact grants permission or authority;
- no artifact mutates canonical state.

Continuing to add another final-review layer over the final-review closeout
would mainly increase ceremony. It would not add new decision power unless it
introduces new evidence, a new oracle, or a new operator decision surface.

The correct stop rule is:

```text
Do not keep indexing the index.
Reopen only when new evidence changes the action question.
```

## What Can Reopen The Lane

Reopen the epistemic-readiness lane only if at least one of these appears:

1. A real blocker in an existing advisory artifact.
2. A mismatch between checked-in evidence and regenerated evidence.
3. A new operator decision surface that existing packets do not answer.
4. A human-approved promotion question.
5. A real project case where current advisory evidence gives the wrong answer.
6. A protocol self-audit finding tied to corrected decisions, not vibes.
7. A measurable false positive or false negative in a fixture or pilot.

Do not reopen for:

- cleaner prose;
- another summary of the same evidence;
- wanting the system to feel smarter;
- recursive proof of already-proved advisory outputs;
- treating no-action as a backlog item.

## Next Useful Frontier

The next good work is applied, not recursive.

The strongest candidate is a derived, advisory decision-envelope or
epistemic-guard slice that runs against a concrete action question.

The important shift:

```text
from: "Can the epistemic evidence chain prove itself?"
to:   "Can Cerebro catch a real wrong or insufficient action before it happens?"
```

Good applied oracles:

- stale diagnostic says "create schema", continuity says "schema exists";
- source proposal omits decisive continuity source;
- third-party target has existing `.cerebro/state.json` and no handling
  decision;
- action touches `core/` without active trigger;
- source set changes after human approval;
- read hash changes before write intent;
- protocol source repeatedly appears before corrected decisions.

## Recommended Next Trigger Shape

If the next session continues this direction, open a new trigger for a derived
experiment only:

```text
FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE_SLICE_1
```

Boundary:

```text
experiments/epistemic_guard/**
docs/operations/FORMAL_RESUME_TRIGGER_EPISTEMIC_GUARD_DECISION_ENVELOPE_ORACLE_SLICE_1.md
docs/operations/*EPISTEMIC_GUARD*
docs/operations/observation_center.toml
docs/operations/SYSTEM_STATE.md
docs/operations/OPPORTUNITY_MAP.md
```

Purpose:

```text
Build a read-only, deterministic advisory decision envelope over a concrete
action question and prove it catches stale/insufficient evidence without
becoming permission or runtime authority.
```

Minimum output:

```text
DecisionEnvelope
- intent
- action_profile
- read_set
- claim_summary
- missing_evidence
- stale_claims
- conflicts
- approval_status
- prewrite_guard_status
- sufficiency
- action_readiness
- recommended_human_decision
- state_change: none
```

Minimum fixtures:

- stale next action;
- silence is not negative evidence;
- existing state ambiguity;
- missing trigger for runtime mutation;
- approval expired by source-set change;
- read/write drift;
- protocol-induced stale source route.

## What Not To Do Next

Do not:

- add a second closeout over the closeout;
- promote `claim_extraction`, `claim_evaluation`, or `epistemic_readiness` into
  runtime authority;
- create a canonical claim graph;
- create a runtime gate;
- write under `.cerebro/`;
- mutate third-party projects;
- treat advisory report pass as permission;
- let a future agent restart at "what is this idea?".

## Resume Sentence

The next session should start from this sentence:

```text
The current epistemic evidence chain is closed until new evidence; the next
valuable step is an applied advisory decision-envelope oracle, not more
recursive hardening of the existing operator-evidence chain.
```
