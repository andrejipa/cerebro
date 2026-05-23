# Cerebro Control Plane Growth 001

Status: active growth front
Created: 2026-05-08

## Thesis

Cerebro should grow from a strong local runtime into a control plane for
agentic work.

The next value is not more narrative memory. The next value is making the
runtime answer, with machine-readable evidence:

- what can run now;
- what is blocked;
- which evidence supports action;
- which evidence is stale or insufficient;
- which approval applies;
- which rollback and verification proof are required;
- what should be replayed if the decision fails.

## Senior Direction

Do not start with MCP, Temporal, LangGraph, OpenAI Agents SDK, or OpenTelemetry.
Those become adapters after the local control-plane contract is sharper.

The control plane should first harden the assets Cerebro already has:

- `observation_center.toml` as queue authority;
- advisory `DecisionEnvelope` output from `epistemic_guard`;
- claim extraction/evaluation as evidence hygiene;
- drift and checkpoint semantic diff as freshness signals;
- third-party trigger review as applied dogfood governance;
- trace/audit evidence from the runtime.

## Growth Lanes

### Lane 1 - Queue Ledger

Goal: replace the fragile long-lived TOML queue with an append-only local
ledger only when the design proves it removes operational ambiguity.

First step is design, not migration.

Minimum future shape:

- observations;
- observation dependencies;
- round runs;
- round events;
- leases/single-flight;
- generated projections for `SYSTEM_STATE.md` and `OPPORTUNITY_MAP.md`;
- deterministic export for review.

Done only when Markdown becomes projection, not scheduler.

### Lane 2 - Decision Envelope

Goal: make `DecisionEnvelope` the standard pre-action evidence artifact for
third-party, runtime-risk, and promotion decisions.

Promotion order:

```text
experiment -> advisory report -> advisory required -> pre-apply advisory -> canonical gate
```

No jump to canonical gate without replay evidence and false-positive review.

### Lane 3 - Capability Policy

Goal: define allowed, denied, review-required, and path-scoped capabilities
before any MCP or external tool adapter.

The policy must cover:

- command ids;
- argv/path scope;
- data sensitivity;
- network/cloud prohibition;
- output budget;
- approval requirement;
- evidence artifact retention;
- rollback expectation.

### Lane 4 - Trace And Replay

Goal: every important decision becomes replayable without reading the chat.

Minimum event vocabulary:

- decision_opened;
- evidence_read;
- evidence_rejected;
- approval_checked;
- action_blocked;
- action_started;
- verification_recorded;
- rollback_recorded;
- decision_closed.

The first trace format can stay local JSONL. OpenTelemetry GenAI export is a
future adapter.

### Lane 5 - Third-Party Control Surface

Goal: turn the `rpg_caminhada` dogfood lessons into a repeatable control-plane
mode.

Required path:

```text
recon -> intake -> source-set decision -> target .cerebro handling -> action -> proof -> consolidation
```

After three target-mutating slices, consolidation is mandatory.

### Lane 6 - Operator UX

Goal: reduce human context load.

Future commands may be justified only if they answer operational questions that
current `analyze` plus exports cannot answer cleanly:

- `what is next?`
- `why blocked?`
- `what evidence is stale?`
- `what approval is missing?`
- `what replay proves this?`

No CLI growth is authorized by this document.

## Anti-Lixo Rule

Every new slice must answer:

```text
Which decision does this improve?
Which failure does this prevent?
Which replay/test proves it?
Which older surface becomes smaller, generated, archived, or unnecessary?
```

If a slice cannot answer all four, it is noise.

## First Implementation Candidates

### Candidate A - Ledger Design Only

Docs-only design for a local ledger with no runtime migration.

Useful if the queue continues to accumulate blocker/waiting state that is hard
to project cleanly.

### Candidate B - Advisory-Required Decision Envelope

Promote `epistemic_guard` output from optional experiment to required advisory
evidence for third-party intake and runtime-risk planning.

Useful because the code already exists and catches stale next action, missing
trigger, approval expiry, read/write drift, and protocol-induced source errors.

### Candidate C - Capability Manifest Design

Design a local capability manifest before MCP or external tool exposure.

Useful because tool governance is prerequisite to any integration.

## Rule Refactor Protocol

Existing rules may be refactored when they are obsolete, misleading, or block a
proven control-plane need.

The refactor path is:

```text
name the stale rule -> cite the operational failure -> propose replacement ->
prove no authority leak -> update tests/docs proportionally
```

Do not bypass rules informally. Replace them with better rules and evidence.

## Recommended Next Slice

Pick a read-only control-plane assessment report first.

Reason: the repo already has `decision_runtime`, `epistemic_guard`,
`claim_extraction`, `claim_evaluation`, and `operational_signals`. The next
step should compose those existing signals into one report before promoting any
single signal into a required advisory gate.

Proposed trigger:

```text
FORMAL_RESUME_TRIGGER_CONTROL_PLANE_ASSESSMENT_REPORT_SLICE_1
```

Scope:

- derived experiment only;
- no runtime authority;
- no CLI promotion;
- no `.cerebro/` writes;
- no reimplementation of task selection, claim evaluation, or readiness scoring;
- focused tests for composition boundaries and non-authoritative output.

Minimum output:

```text
selected_task_id
decision_runtime_reason
epistemic_action_readiness
blockers
missing_evidence
operational_signal_summary
recommended_human_decision
state_change = none
authority = non-authoritative
```

Done when the report can explain the next candidate action and blockers without
becoming permission, scheduler authority, memory, or a runtime gate.

## Deferred Integrations

- MCP: after capability policy and audit exist.
- OpenAI Agents SDK: after handoff and envelope traces are stable.
- LangGraph: after local decision graph/checkpoint need is proven.
- Temporal: after long-running durable worker need is real.
- OpenTelemetry GenAI: after local trace semantics are stable.

## Stop Lines

Stop if:

- the front asks for canonical authority before advisory precision is measured;
- a framework is introduced to compensate for unclear local contracts;
- docs grow without shrinking or generating another operational surface;
- queue authority splits between TOML/ledger/Markdown;
- third-party work resumes without source-set and `.cerebro/` handling clarity.
