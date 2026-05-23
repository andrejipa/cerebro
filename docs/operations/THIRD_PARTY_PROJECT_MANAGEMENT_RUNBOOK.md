# Third-Party Project Management Runbook

Status: operational guidance, docs-only
Date: 2026-04-25

## Purpose

This runbook defines how Cerebro should manage projects outside its own repo.
It turns the `rpg_caminhada` dogfood evidence into a repeatable operating model.

It does not authorize runtime implementation, target mutation, source import, or
canonical state changes by itself.

## Operating Principle

```text
Use third-party projects to improve Cerebro, not to hide ordinary product work
inside Cerebro process.
```

Third-party work may still improve the target product. That is acceptable when
the trigger declares why the work also improves Cerebro's project-management
capability.

## Modes

### Mode 0 - Recon

Read-only inspection of candidate projects.

Allowed:

- list structure;
- read bounded documentation;
- classify risk;
- recommend a pilot.

Not allowed:

- target file edits;
- target `.cerebro/` mutation;
- imports;
- runtime changes.

Output:

- candidate recommendation;
- risk classification;
- source-set concerns.

### Mode 1 - Intake Gate

Docs-only gate before target runtime mutation.

Must answer:

- selected target path;
- why this target is safe enough;
- whether target contains sensitive or regulated data;
- whether target already has `.cerebro/`;
- exact initial source set;
- handling plan for legacy target `.cerebro/`;
- rollback plan.

Stop if any of these are ambiguous.

### Mode 2 - Source-Set Classification

Before import, classify source roles:

```text
project_identity     = required
current_state        = required
continuity_delta     = required
decision_ledger      = required
next_work_map        = required
architecture_rules   = recommended
validation_surface   = recommended
```

If `current_state` or `continuity_delta` is missing, do not infer that the
project is empty. Treat the source set as insufficient.

### Mode 3 - Target Runtime Handling

If the target already has `.cerebro/`, classify it:

```text
unknown
legacy_compatible
legacy_incompatible
canonical_current
blocked
```

Rules:

- preserve unknown or legacy state before replacement;
- never overwrite target `.cerebro/` without explicit trigger language;
- never treat target `.cerebro/` as Cerebro repo state;
- record whether an active session token exists before continuing.

### Mode 4 - Applied Target Slice

Target mutation is allowed only with a formal trigger.

Each trigger must declare:

```toml
[third_party]
target_path = "D:\\projetos_cli\\pessoais\\rpg_caminhada"
slice_kind = "management_proof|target_product_work|both"
dogfood_value = "what Cerebro learns from this slice"
proof_cost = "none|low|medium|high|infrastructure-heavy"
cleanup_required = true
max_target_writes = 3
allowed_target_paths = []
forbidden_target_paths = []
forbidden_cerebro_paths = ["core/", "cli/", "extensions/", "tests/", ".cerebro/"]
```

Minimum proof:

- target-specific validation;
- local behavior proof when behavior changes;
- Cerebro architecture/doc-governance where Cerebro docs changed;
- final AGENTS-equivalent gate before closing Cerebro status.

### Mode 5 - Consolidation Stop

After three consecutive target-mutating slices, stop target work.

Run a Cerebro-side consolidation slice that answers:

- what did the target prove about Cerebro?
- what was unexpectedly expensive?
- which source assumptions were wrong?
- where did a human decision matter?
- which future Cerebro improvement is justified?
- which target work should stop until Cerebro absorbs the lesson?

This rule exists because target work can be productive while still starving the
Cerebro learning loop.

### Mode 6 - Cerebro Hardening Decision

Only after consolidation may Cerebro decide whether to open a new internal
improvement trigger.

Possible outcomes:

```text
no_action
docs_only_runbook_update
new_experiment
new_advisory_checker
runtime_feature_candidate
blocked_until_human_decision
```

Runtime feature candidates require a separate trigger and must still satisfy
the freeze policy.

## Standard Third-Party Trigger Checklist

Every third-party trigger should include:

- objective;
- target path;
- slice kind;
- dogfood value;
- allowed Cerebro files;
- allowed target files;
- explicitly forbidden target files;
- explicitly forbidden Cerebro files;
- proof plan;
- proof cost;
- cleanup plan;
- rollback plan;
- stop conditions;
- acceptance criteria;
- next Cerebro learning step.

## Standard Target Report Shape

Each target report should contain:

```text
1. Boundary
2. Target change
3. Local proof
4. Validation
5. Cleanup
6. What this proved about the target
7. What this taught Cerebro
8. What should not be inferred
9. Recommended next Cerebro step
```

## Stop Lines

Stop target work and return to Cerebro when:

- three consecutive target-mutating slices have completed;
- the next proposed slice is only product polish and has weak dogfood value;
- proof setup cost is growing faster than Cerebro learning;
- the source set looks stale or incomplete;
- target `.cerebro/` handling is ambiguous;
- the same class of report appears repeatedly without consolidation;
- user asks whether work is improving the target or Cerebro.

## Non-Negotiable Distinctions

```text
target report != Cerebro canonical state
target proof != future permission
source registration != truth
diagnostic silence != negative evidence
dogfood value != product value
local proof != cloud deployment permission
runbook guidance != runtime authority
```

## Applied Lesson From `rpg_caminhada`

The `rpg_caminhada` pilot proved that Cerebro can:

- select a real project;
- identify source-set omissions;
- handle legacy target `.cerebro/` safely;
- run target validation and local proof loops;
- coordinate many bounded target slices;
- keep Cerebro runtime state untouched while managing target work.

It also proved that Cerebro needs a stronger consolidation rhythm. The target
received many useful slices, but Cerebro should have paused earlier to extract
the general project-management pattern.

## Next Use

For the next third-party project, start with this runbook before opening target
mutation triggers.

For the current line of work, the next useful Cerebro step is not another
`rpg_caminhada` feature. It is a bounded internal hardening slice that turns
this runbook into either:

- a stricter trigger template;
- a docs-only checklist;
- or an advisory experiment that checks third-party trigger completeness.
