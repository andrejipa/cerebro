# FORMAL RESUME TRIGGER - Cerebro Control Plane Growth 001

status: consumed
created_at: 2026-05-08
closed_at: 2026-05-08

## Objective

Open one bounded growth lane for Cerebro as a control plane, not as another
documentation layer.

The slice exists because the current repo already has runtime state,
approvals, rollback, verification, a machine-primary queue, advisory epistemic
experiments, and third-party dogfood evidence. The unmet need is now
operational consolidation: a small set of promoted control-plane contracts that
make those pieces act as one product surface.

## Concrete Use Case

An operator should be able to ask "what can Cerebro safely do next, why, and
what evidence blocks it?" without reading large historical snapshots or
manually reconciling queue, freeze policy, advisory reports, and trigger docs.

Current approved surfaces partly satisfy this through `observation_center.toml`,
`SYSTEM_STATE.md`, `OPPORTUNITY_MAP.md`, `epistemic_guard`, and third-party
trigger review, but they do not yet provide a single growth program with
promotion rules, stop lines, and a first executable docs-only slice.

## Scope

Allowed files for this slice:

- `docs/operations/FORMAL_RESUME_TRIGGER_CEREBRO_CONTROL_PLANE_GROWTH_001.md`
- `docs/operations/CEREBRO_CONTROL_PLANE_GROWTH_001.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `docs/operations/freeze_review.toml`

Forbidden files and paths:

- `core/`
- `cli/`
- `extensions/`
- `tests/`
- `.cerebro/`
- `core/schema.py`
- third-party project files

## Authorized Work

This trigger authorizes docs-only growth planning and queue reconciliation for
the first `Cerebro Control Plane` lane.

It may:

- name the control-plane growth front;
- define the minimal promotion ladder;
- define stage-1 stop conditions;
- record why the prior freeze is no longer sufficient;
- update the live queue and projections to route the next slice.

It may not:

- implement a SQLite ledger;
- promote `DecisionEnvelope` into runtime authority;
- add or rename CLI commands;
- alter canonical state, schema, validation, sessions, apply, verify, or rollback;
- write under `.cerebro/`;
- call MCP, Temporal, LangGraph, or Agents SDK as runtime dependencies;
- mutate a third-party target project.

## Growth Shape

The approved front is:

```text
Cerebro Control Plane:
state ledger -> decision envelope -> advisory gate -> trace/replay -> operator UX
```

This trigger only opens the first docs-only slice:

```text
Growth 001: define the front, promotion ladder, first queue item, and stop lines.
```

Later implementation requires separate triggers, starting with a read-only
assessment report that composes existing signals without duplicating authority.
Only after that should the project consider:

- a derived local ledger design that keeps Markdown as generated projection; or
- an advisory-required `DecisionEnvelope` path for third-party and runtime-risk work.

## Evidence Basis

Local evidence already present:

- `docs/operations/observation_center.toml` is the machine-primary queue.
- `experiments/epistemic_guard/` already emits advisory `DecisionEnvelope` evidence.
- `experiments/claim_extraction/` and `experiments/claim_evaluation/` already evaluate claims as advisory evidence.
- `experiments/drift_detection/` and `experiments/checkpoint_semantic_diff/` already detect freshness/alignment signals.
- `THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md` and `THIRD_PARTY_TRIGGER_TEMPLATE.md` already encode third-party operating rules.
- `FREEZE_POLICY.md` allows resume when a concrete repeated use case is unmet by the current approved surface.

External framing checked on 2026-05-08:

- OpenAI Agents SDK is useful for agents, tools, handoffs, and tracing, but should remain an adapter candidate until local control-plane contracts are stable.
- MCP is an integration protocol, not governance; capability policy and audit must exist before tool exposure.
- Temporal/LangGraph are deferred until durable workflow need exceeds local ledger/replay.
- OpenTelemetry GenAI is a future trace export target, not the first local trace format.

## Stop Conditions

Stop immediately if:

- any implementation file outside the allowed list is needed;
- the plan creates a second source of truth;
- Markdown projections are treated as scheduler authority over `observation_center.toml`;
- advisory experiments are described as permission, truth, memory, or runtime gates;
- a framework dependency becomes necessary to finish this slice;
- the focused doc-governance or architecture tests fail.

## Acceptance Criteria

This slice is complete when:

- `CEREBRO_CONTROL_PLANE_GROWTH_001.md` exists and defines the front, lanes, promotion ladder, anti-lixo rule, and first implementation candidates;
- `observation_center.toml` has one open docs-only control-plane observation;
- `SYSTEM_STATE.md` and `OPPORTUNITY_MAP.md` project that observation without reviving stale target work;
- `freeze_review.toml` records `resume_authorized` for this human-approved opening;
- focused doc-governance and architecture tests pass.

## Closure

Closed. The docs-only growth front was opened, and the first technical slice was
completed under `FORMAL_RESUME_TRIGGER_CONTROL_PLANE_ASSESSMENT_REPORT_SLICE_1`.

Validation for this trigger:

- `python -m unittest tests.test_doc_governance -v` passed `19/0`.
- `python -m unittest tests.test_architecture -v` passed `51/0`.
