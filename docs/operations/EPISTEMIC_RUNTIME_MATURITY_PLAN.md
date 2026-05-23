# Epistemic Runtime Maturity Plan

## Status

- Created on 2026-04-24 as docs-only maturation.
- This document is not a Formal Resume Trigger.
- It does not authorize runtime implementation, schema changes, new CLI surface,
  or writes under `.cerebro/`.
- It defines the strongest useful shape for a future epistemic layer so that a
  later trigger can be narrow instead of exploratory.

## Thesis

Cerebro already governs canonical state, sessions, approvals, rollback,
verification, DAG discipline, and derived context search. The missing layer is
knowledge validity before action.

The next architectural concept is an epistemic runtime: a layer that can answer,
before an agent acts:

- what claims the agent is relying on
- which sources support or contradict those claims
- whether the evidence is fresh enough for the action
- whether the current context is sufficient
- whether any read source changed before write time
- what rationale should be auditable after the decision

The unit of control should not be a file and should not be a free-form agent
answer. The unit should be a decision envelope.

## External Framing

The strongest name for this direction is not only memory engineering and not
only context engineering. It is epistemic engineering.

```text
Context Engineering
- governs what the agent sees now
- optimizes task-local context selection

Memory Engineering
- governs what persists across sessions
- optimizes recall and continuity

Epistemic Engineering
- governs whether retrieved context and persisted memory are reliable enough
  to support action
- optimizes justification, freshness, contradiction handling, and abstention
```

Agentic metacognition is the runtime behavior: the agent monitors its own
readiness, detects likely failure, and escalates before damage. Epistemic
engineering is the underlying discipline: the evidence contracts, claim graph,
decay policy, sufficiency gates, and audit trail that make metacognition
testable instead of rhetorical.

The mature Cerebro positioning is therefore:

```text
Cerebro is not a memory store.
Cerebro is not a RAG framework.
Cerebro is an epistemic governance layer for agentic work.
```

It should integrate with memory and retrieval systems, but its unique job is to
decide when "remembered" or "retrieved" still does not mean "safe to act on".

## Product Thesis

The product that does not yet exist is a pre-action knowledge-validity gate for
agents.

Current agent frameworks are mostly optimized around:

- storing memory
- retrieving memory
- routing tools
- orchestrating agents
- generating answers

Cerebro's differentiated surface should be optimized around:

- refusing action when evidence is stale or contradictory
- explaining what evidence would make action acceptable
- detecting when a protocol induced a bad decision
- aging memory without deleting it
- turning failures into eval fixtures
- making human handoff precise instead of vague

The core user-facing promise should be:

```text
Before an agent changes anything important, Cerebro can show why it believes
the agent knows enough to act, and where that belief could be wrong.
```

That is stronger than memory, retrieval, or orchestration. It is governance of
agent belief under operational risk.

## Maturity Ladder

The idea should mature in levels. Each level has a different risk profile.

### Level 0: Human Discipline

Current Cerebro posture:

- humans maintain hierarchy of sources
- agents read operational docs
- gates enforce runtime correctness
- memory quality is mostly manual

Strength: high auditability.
Weakness: depends on operator discipline.

### Level 1: Advisory Epistemic Report

Derived experiment only:

- creates decision envelopes
- extracts claims
- flags contradictions
- reports stale-by-conflict and stale-by-nonuse
- never blocks runtime

Strength: proves signal without authority.
Weakness: can be ignored.

### Level 2: Required Report For High-Risk Work

Still advisory, but mandatory for selected workflows:

- third-party intake
- source registration
- technology promotion
- docs that imply runtime authorization

Strength: introduces habit without touching core mutation semantics.
Weakness: still not enforceable at runtime.

### Level 3: Pre-Apply Advisory Gate

The runtime can ask for an envelope but does not yet persist it as canonical
truth:

- warns before apply
- blocks only when existing runtime policy already blocks
- compares read hashes and write hashes

Strength: tests integration path.
Weakness: boundary with canonical state becomes sensitive.

### Level 4: Canonical Epistemic Gate

Only after eval proof:

- sensitive actions require valid decision envelope
- stale approval/source claims block execution
- high-impact actions require adversarial review
- handoff is structured when the gate cannot pass

Strength: real safety value.
Weakness: high risk of bureaucracy if false positives are not controlled.

### Level 5: Self-Correcting Method Layer

Cerebro audits its own protocols:

- detects low-yield required reads
- detects protocol files correlated with corrections
- proposes source hierarchy changes
- generates counterfactual replay fixtures from failures

Strength: the method improves from evidence.
Weakness: must never auto-promote its own conclusions without human review.

## Non-Negotiable Distinctions

The future system must preserve these distinctions:

```text
registered != true
retrieved != relevant
recent != valid
remembered != trusted
high confidence != sufficiently proven
human-readable != auditable
advisory != authoritative
```

These distinctions are the moat. Most memory systems collapse at least one of
them.

## Failure Taxonomy

An epistemic runtime should classify failures before proposing mechanisms.

```text
E1: Missing evidence
The agent did not read a source required for the action.

E2: Stale-by-age evidence
The source has not been refreshed within its decay policy.

E3: Stale-by-conflict evidence
The source looks current but a stronger source contradicts its claim.

E4: Stale-by-supersession evidence
The source was explicitly replaced.

E5: Misranked evidence
The relevant source existed but retrieval ranked it too low.

E6: Overtrusted memory
Long-term memory was treated as live operational truth.

E7: Under-specified approval
Human approval did not cover the actual source set, write set, or risk.

E8: Read/write drift
The world changed between read and write.

E9: Protocol-induced error
Cerebro's own instructions routed the agent toward the wrong source or
premature sufficiency.

E10: Adversarial review failure
The decision could not survive a structured attempt to disprove it.
```

Each failure type should map to an oracle fixture. The system should not add a
mechanism unless it closes at least one failure type measurably.

## Core Object: Decision Envelope

```text
DecisionEnvelope v0
- envelope_id
- created_at
- actor
- intent
- action_profile
- read_set
- claim_graph
- evidence_decay
- sufficiency_result
- confidence_result
- write_intent
- prewrite_guards
- rationale
- stop_conditions
- verdict
```

The envelope is a pre-action artifact. In the first implementation it should be
derived and advisory only. A later canonical integration may require it before
sensitive actions, but only after eval evidence proves that it blocks real bad
actions without turning routine work into ceremony.

## Claim Graph

The system should reason over claims, not files.

```text
Claim
- id
- text
- type
- authority_class
- source_refs
- support_refs
- conflict_refs
- freshness_state
- confidence
```

Important claim types:

- `current_next_action`
- `architecture_boundary`
- `formal_trigger_scope`
- `source_canonicality`
- `source_staleness`
- `test_evidence`
- `human_approval`
- `third_party_sensitivity`
- `write_permission`
- `rollback_expectation`

This matters because a source can be partially useful and partially stale. A
diagnostic file may still describe architecture accurately while its stated next
step is obsolete.

## Evidence Decay And Consistency

Freshness should be attached to evidence, not to whole files. But freshness is
still weaker than consistency.

The hard Cerebro failure mode is not "old file says old thing". It is "a file
that looks current carries a claim that is superseded by a stronger or newer
source". A source can have a recent timestamp and still be epistemically stale
because another source owns the live state.

```text
EvidenceDecay
- evidence_type
- decay_class
- expires_on_event
- expires_after_duration
- stale_when
- refresh_action
```

Proposed decay classes:

| Evidence type | Decay | Rationale |
| --- | --- | --- |
| Formal trigger scope | slow/event-driven | Stale only when consumed, superseded, or contradicted. |
| Architecture decision | slow/event-driven | Long-lived unless boundary changes. |
| SYSTEM_STATE current snapshot | medium | Useful, but must track live queue drift. |
| OPPORTUNITY_MAP next action | fast | It is a projection, not authority. |
| observation_center queue item | medium/event-driven | Primary queue, but status can flip after one round. |
| Test result | event-driven | Expires when relevant files or test harness change. |
| Human approval | event-driven | Expires when source set, write set, or risk changes. |
| Third-party intake | fast/event-driven | Sensitive until validated against current project state. |
| Context discovery/vector ranking | fast | Advisory signal, not truth. |

The first useful staleness model should combine:

```text
staleness_score =
  decay_weight
  + source_hash_drift
  + contradiction_weight
  + action_criticality_weight
  - explicit_refresh_weight
```

Staleness should not mean "old file". It should mean "evidence no longer strong
enough for this action".

The first implementation should therefore prefer claim consistency checks over
timestamp checks:

```text
consistency_check =
  claim_from_source_a
  vs claim_from_source_b
  weighted by authority, recency, and role
```

Example:

```text
diagnostic claim: "next step is create schema"
continuity claim: "schema exists; validate Edge Functions"
intake claim: "old source proposal is stale"
result: diagnostic next-step claim is stale even if the diagnostic file is new
```

This should be modeled as claim-level staleness:

```text
ClaimFreshness
- fresh: supported by current authority
- stale_by_age: old enough to require refresh
- stale_by_conflict: contradicted by stronger evidence
- stale_by_supersession: explicitly replaced by another source
- unknown: no enough evidence to classify
```

## Action Criticality

The gate must scale by risk.

```text
ActionCriticality
- low
- medium
- high
- critical
```

Suggested profiles:

| Profile | Examples | Required epistemic proof |
| --- | --- | --- |
| low | historical docs cleanup, report formatting | rationale + no active conflict |
| medium | derived experiment report, advisory analysis | read set + sufficiency + stale scan |
| high | third-party import, source registration, generated plan | claim graph + human approval + drift check |
| critical | core apply/verify/rollback/session/schema behavior | formal trigger + claim graph + eval + optimistic prewrite guard + rollback proof |

This prevents the epistemic layer from becoming a universal tax. Small work gets
small proof. Dangerous work gets explicit proof.

## Sufficiency Gates

Sufficiency should be checked per action profile.

```text
SufficiencyResult
- status: sufficient | partial | insufficient
- missing_claims
- missing_sources
- accepted_gaps
- blocker_gaps
- reason
```

Initial profiles:

### Docs-Only Maturation

Required:

- current `SYSTEM_STATE.md`
- current `OPPORTUNITY_MAP.md`
- current `observation_center.toml`
- relevant freeze or trigger document

Blocks when:

- projections diverge from observation center
- requested docs imply runtime authorization without trigger

### Third-Party Pilot

Required:

- intake gate
- selected target
- legacy `.cerebro/state.json` handling decision
- exact approved source list
- sensitive-material screen
- validate/analyze plan

Blocks when:

- source proposal is stale
- target has existing state and no handling decision exists
- oracle says the next project step is not the intended operational step

### Runtime Mutation

Required:

- active formal trigger
- exact whitelist
- relevant tests identified
- rollback story
- source/write-set prehashes
- no unresolved stale or conflict claims

Blocks when:

- any relevant file changed after read
- action extends beyond trigger scope
- confidence is high only because evidence is missing

## Confidence Calibration

Confidence must be derived from evidence, not self-reported.

```text
confidence =
  authority_score
  * freshness_score
  * corroboration_score
  * test_score
  * approval_score
  * conflict_penalty
```

The report should expose the decomposition:

```text
confidence: 0.64
authority: high
freshness: weak
corroboration: medium
tests: absent
approval: missing
conflicts: one stale source proposal
```

This is useful because the operator can see why confidence is low and what would
raise it.

## Decision Rationale Logging

Do not log private chain-of-thought. Log structured rationale.

```text
DecisionRationale
- conclusion
- evidence_used
- evidence_rejected
- alternatives_considered
- winning_reason
- uncertainty
- verification_needed
- retrospective_candidate
```

The rationale should be terse and auditable. It should not attempt to preserve
every intermediate thought. The goal is postmortem clarity, not cognitive
transcription.

## Optimistic Prewrite Guards

Every high or critical action should carry a read/write consistency check.

```text
PrewriteGuard
- path
- read_hash
- current_hash
- status: unchanged | changed | missing | new
- response: allow | block | require_review
```

Rules:

- If writing a file that was read, current hash must match read hash.
- If writing a file not read, the envelope must explain why no read was needed.
- If another agent changed a planned write target, block and require review.
- If a generated artifact is written from multiple sibling outputs, guard the
  artifact family as one unit.

This is the multi-agent collision guard. It can work without central
coordination because the evidence is local and hash-based.

## Retrospective Loop

At closeout, the agent should propose but not commit lessons.

The goal is not autonomous self-learning. The goal is to reduce the human cost
of maintaining memory. The human still decides what deserves promotion; the
agent prepares a focused draft from concrete session evidence.

```text
RetrospectiveProposal
- missed_context
- stale_source_seen
- wrong_assumption
- useful_rule_candidate
- memory_update_candidate
- rejected_noise
```

Rules:

- No automatic canonical memory write.
- Accepted lessons require human approval or a future documented promotion path.
- Rejected lessons remain non-canonical trace only if useful for audit.
- Retrospectives should be tied to concrete envelope failures, not vibes.
- The default output is a human-review queue, not a memory update.
- A proposal without source evidence is noise and should be rejected.

The useful workflow is:

```text
session events -> retrospective draft -> human approve/reject/edit -> memory update
```

Not:

```text
session events -> automatic lesson -> canonical memory
```

## Intelligent Forgetting

The advanced memory problem is not only recall. It is honest forgetting.

Long-lived memory becomes dangerous when it keeps the visual shape of authority
after its supporting evidence has stopped being exercised. The system should
track memory health separately from memory existence.

```text
MemoryHealth
- trusted
- untested
- stale_by_nonuse
- stale_by_conflict
- superseded
- rejected
```

The first rule should be conservative in effect but aggressive in detection:

```text
if a memory claim has not been revalidated across N relevant sessions:
  mark suspicious
  do not delete
  lower confidence
  require refresh before high-impact use
```

For Cerebro, the most important distinction is:

- archival memory can remain readable forever
- operational memory must earn trust repeatedly

Possible decay signals:

- no recent session cited the claim successfully
- a newer claim occupies the same role
- a source was read in failed decisions more often than successful decisions
- a claim is often loaded but never used in final rationale
- a claim causes sufficiency to pass while later verification fails

This is not garbage collection. It is epistemic aging. The system keeps the
artifact but stops pretending all remembered facts are equally alive.

## Protocol Self-Audit

Cerebro should eventually ask whether Cerebro itself is inducing mistakes.

Bad decisions can come from stale project context, but they can also come from
bad operating method:

- a required file is too noisy and gets read without helping
- a snapshot creates false confidence
- a hierarchy document points agents toward obsolete sources
- an intake checklist misses the real blocker
- a protocol makes agents over-read before acting
- a protocol makes agents under-read because it says the wrong source is enough

The self-audit unit should be a protocol influence record:

```text
ProtocolInfluence
- decision_id
- protocol_sources_read
- claims_used
- claims_ignored
- outcome
- later_correction
- suspected_protocol_failure
```

The derived analysis should ask:

```text
- Which Cerebro files are frequently read but rarely cited in winning rationale?
- Which files appear in failed or corrected decisions?
- Which checklist items often fail to predict the actual blocker?
- Which source hierarchy entries route agents toward stale claims?
- Which protocol steps produce no change in confidence?
```

This is the "Cerebro knows when Cerebro is the problem" layer. It should start
as an offline report, not a runtime gate.

## Adversarial Self-Review

For high and critical decisions, the agent should produce an adversarial review
of its own envelope before acting.

This is not free-form self-critique. It should attack the envelope structure:

```text
AdversarialReview
- weakest_claim
- strongest_conflicting_source
- missing_source_most_likely_to_change_verdict
- most_dangerous_assumption
- optimistic_locking_gap
- rollback_gap
- verdict_after_attack
```

The review should be required for:

- runtime mutation
- third-party source registration
- rollback or verification policy changes
- any promotion from derived advisory layer into canonical behavior
- any decision where confidence is high but evidence diversity is low

Allowed outcomes:

```text
survives
survives_with_warning
requires_more_context
blocked_by_conflict
blocked_by_missing_rollback
```

The useful test is whether the review can change the decision. If it never
changes a verdict, it is ceremony and should be removed.

## First Derived Experiment

The first implementation should be:

```text
experiments/epistemic_guard/
```

Scope:

- read-only
- no writes under `.cerebro/`
- no runtime imports from `core/`
- consume project files, `context_discovery`, and `context_vectors` outputs as
  advisory inputs
- produce a Markdown report and JSON envelope
- include local tests and oracle fixtures

Non-goals:

- no canonical gate
- no CLI promotion
- no schema change
- no automatic import-context decision
- no model/network dependency

## Oracle Fixtures

Minimum useful eval set:

1. Stale next action
   - A source says "create schema".
   - A newer intake says "schema exists; validate Edge Functions".
   - Expected: stale claim flagged; action blocked for source refresh.

2. Old stable architecture
   - An old architecture file defines a still-current boundary.
   - Expected: no stale block; evidence classified slow/event-driven.

3. Insufficient runtime mutation context
   - Intent touches `core/` without active trigger.
   - Expected: insufficient and blocked.

4. Third-party state ambiguity
   - Target has existing `.cerebro/state.json`.
   - No archive/replace decision exists.
   - Expected: blocked.

5. Read/write drift
   - Envelope read hash differs from prewrite hash.
   - Expected: blocked, require review.

6. Advisory ranking disagreement
   - `context_vectors` and `context_discovery` rank different source files.
   - Expected: confidence lowered, not automatically blocked.

7. Human approval expiry
   - Human approved source list A.
   - Source list changes to B.
   - Expected: approval stale.

8. Retrospective false lesson
   - Agent proposes a broad rule not supported by envelope evidence.
   - Expected: reject as non-canonical proposal.

9. Current-looking but superseded claim
   - A diagnostic file has a recent timestamp.
   - A continuity file with higher live-state authority contradicts its next
     action.
   - Expected: claim is stale by conflict, not fresh by timestamp.

10. Human-cost retrospective
   - Session has concrete stale-source and missing-context events.
   - Agent drafts only evidence-backed retrospective candidates.
   - Expected: no automatic memory write; output is approval-ready queue.

11. Memory decays by nonuse
   - A long-term memory claim exists and has not been revalidated across
     relevant sessions.
   - Expected: claim remains readable but loses trusted status for high-impact
     use.

12. Memory revived by evidence
   - A suspicious memory claim is cited by a fresh authoritative source and
     verified by a passing gate.
   - Expected: claim returns to trusted or untested state, depending on profile.

13. Protocol source is unhelpful
   - A protocol file is repeatedly read but never cited in rationale and never
     changes sufficiency.
   - Expected: protocol self-audit flags it as low-yield, not as a project
     source problem.

14. Protocol source correlates with corrections
   - Failed decisions share the same source-hierarchy instruction.
   - Expected: self-audit flags possible method-induced error.

15. Adversarial review finds missing blocker
   - Initial envelope says sufficient.
   - Adversarial pass finds a stronger conflicting source.
   - Expected: final verdict changes to blocked or requires_more_context.

## Implementation Slices

### Slice 0: Trigger Draft

Create a Formal Resume Trigger for a read-only derived experiment only. The
trigger must explicitly prohibit runtime integration.

### Slice 1: Envelope Schema and Fixtures

Add `experiments/epistemic_guard/` with:

- dataclasses or simple typed dictionaries for `DecisionEnvelope`
- JSON serialization
- fixture loader
- tests for schema stability

### Slice 2: Claim Extraction

Implement deterministic claim extraction from bounded text heads:

- headings
- explicit status lines
- trigger status
- next action sections
- source list approvals
- stale/superseded markers

No LLM, no model dependency.

### Slice 3: Evidence Decay, Consistency, and Staleness

Implement decay policies and event-driven expiry.

Key tests:

- old architecture does not stale out
- stale next action does
- changed source hash expires test and approval evidence
- recent file with contradicted next-action claim is stale by conflict
- stronger live-state source supersedes weaker diagnostic claim

### Slice 4: Sufficiency Profiles

Implement action profiles:

- docs-only
- third-party-pilot
- derived-experiment
- runtime-mutation

The runtime-mutation profile should block by default unless a trigger and
whitelist are supplied as evidence.

### Slice 5: Optimistic Prewrite Advisory

Add read/write hash guard evaluation, still advisory only.

### Slice 6: Report Renderer

Produce Markdown and JSON reports with stable shape:

- verdict
- confidence breakdown
- stale claims
- missing claims
- conflicts
- prewrite guards
- recommended next evidence

### Slice 7: Memory Health Prototype

Add advisory memory-health classification:

- trusted
- untested
- stale by nonuse
- stale by conflict
- superseded

No deletion. No automatic memory rewrite.

### Slice 8: Adversarial Envelope Review

Add deterministic adversarial review over the envelope:

- weakest claim
- strongest conflict
- missing evidence
- dangerous assumption
- rollback/prewrite gap

The review must be able to change the advisory verdict.

### Slice 9: Protocol Self-Audit

Add offline report over decision envelopes:

- low-yield protocol files
- protocol claims correlated with corrections
- checklist steps that do not improve sufficiency
- source-hierarchy entries that route to stale claims

This remains derived and retrospective only.

### Slice 10: Real Oracle Run

Run against `rpg_caminhada` intake material and compare with
`context_discovery` and `context_vectors`.

Close only if it catches the stale four-file proposal without inventing
canonical truth.

The oracle must include at least one current-looking source whose claim is
wrong because a stronger continuity/intake source supersedes it. If the
experiment only catches old timestamps, it has not solved the Cerebro problem.

### Slice 11: Promotion Decision

Decide whether to:

- keep as derived advisory layer
- add a canonical CLI command
- integrate as pre-apply advisory
- reject as too noisy

No promotion without measured precision/recall over the oracle fixtures and at
least one real-project pilot.

## Acceptance Bar For Any Future Runtime Integration

Runtime integration should require all of:

- oracle suite green
- false-positive rate acceptable on docs-only and derived work
- catches at least one real stale/insufficient-context failure from pilot use
- no writes under `.cerebro/` except through existing canonical runtime paths
- no new source of truth
- no weakening of current validation or architecture gates
- full AGENTS-equivalent gate green

## Strategic Position

The mature version of the idea is not "confidence scores" and not "agent
thought logs". It is a pre-action evidence contract.

Cerebro should eventually be able to reject an action with:

```text
BLOCKED
reason: insufficient epistemic envelope
missing: human approval for source set, fresh next-action claim
stale: 04_DIAGNOSTICO_INICIAL_ATUAL.md next-step claim
conflict: intake gate says schema exists, old proposal says create schema
required_refresh: read current continuity file and approve expanded source set
```

That is the useful frontier: not smarter prose, but explicit proof that the
agent knows enough to act.

The prafrentex frontier is one step beyond that:

```text
Cerebro should not only detect weak project evidence.
Cerebro should detect weak Cerebro method.
```

That is what separates a memory layer from a self-correcting operational
runtime.
