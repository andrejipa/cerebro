# Third-Party Trigger Template

Status: reusable trigger template, docs-only
Created: 2026-04-25

Use this template when opening any future Cerebro-managed slice against a
project outside `D:\projetos_cli\ambiente_cerebro\cerebro`.

This template is not permission to execute. It is the minimum trigger shape
required before execution can be reviewed. A filled trigger still needs the
normal AGENTS gate, explicit whitelist, stop conditions, and human/governance
approval required by the active workstream.

## Non-Negotiable Framing

```text
Target project work is the experiment surface.
Cerebro capability improvement is the reason for the experiment.
Target proof is evidence.
Cerebro docs decide what becomes reusable guidance.
```

Every third-party trigger must make this separation explicit. Improving the
target project is allowed only when the same slice also declares what it teaches
Cerebro about managing projects.

## Required Structured Block

Place this block near the top of the trigger and fill every field.

```toml
[third_party]
target_path = "D:/absolute/path/to/target_project"
slice_kind = "management_proof|target_product_work|both"
dogfood_value = "What Cerebro learns from this target work."
target_product_value = "What the target project gains, if anything."
proof_cost = "none|low|medium|high|infrastructure-heavy"
cleanup_required = true
target_cerebro_handling = "absent|legacy_external|legacy_compatible|legacy_incompatible|canonical_current|blocked"
consecutive_target_mutating_slices_before_this = 0
max_target_writes = 3
expected_target_runtime = "none|local-only|local-with-services|cloud-prohibited"

[source_roles]
project_identity = "path/to/source"
current_state = "path/to/source"
continuity_delta = "path/to/source"
decision_ledger = "path/to/source"
next_work_map = "path/to/source"
architecture_rules = "path/to/source or none"
validation_surface = "path/to/source or none"

[boundaries]
allowed_cerebro_paths = [
  "docs/operations/FORMAL_RESUME_TRIGGER_....md",
  "docs/operations/SYSTEM_STATE.md",
  "docs/operations/OPPORTUNITY_MAP.md",
  "docs/operations/observation_center.toml",
]
allowed_target_paths = [
  "D:/absolute/path/to/target_project/path/from/trigger",
]
forbidden_cerebro_paths = [
  "core/",
  "cli/",
  "extensions/",
  "tests/",
  "core/schema.py",
  ".cerebro/",
]
forbidden_target_paths = [
  "D:/absolute/path/to/target_project/.cerebro/",
  "D:/absolute/path/to/target_project/.env",
  "D:/absolute/path/to/target_project/secrets/",
]

[risk_budget]
authority_impact = "none|advisory|canonical-prohibited"
runtime_impact = "none|target-only|cerebro-runtime-prohibited"
reversibility = "high|medium|low"
rollback = "git-revert|manual-target-revert|delete-generated-files|not-reversible"
gate_level = "G0|G1|G2|G3"
promotion_path = "none|requires-consolidation|requires-separate-trigger"
```

## Required Narrative Sections

Every third-party trigger must include these sections.

### Objective

State the smallest useful slice. One trigger, one slice.

Required distinction:

- Target objective: what changes or is proven in the target project.
- Cerebro objective: what Cerebro learns or hardens because of this slice.

If the Cerebro objective is weak, stop. That is target product work, not
Cerebro-managed dogfood.

### Why This Target

Explain why this target is appropriate now:

- current operational need;
- risk classification;
- why another lower-risk target or docs-only slice is not better;
- whether the target contains sensitive, regulated, or high-blast-radius data;
- whether the target already has `.cerebro/`.

Sensitive data does not automatically block local work, but it must raise proof
discipline and prohibit network/cloud exposure unless separately authorized.

### Source-Set Sufficiency

List the source roles and say whether each is present, stale, missing, or
ambiguous.

Rules:

- Missing `current_state` means the agent does not know the current state.
- Missing `continuity_delta` means the agent does not know what changed since
  older docs.
- Silence is not negative evidence.
- Canonical-looking does not mean current.

If source sufficiency is partial, the slice may be recon or advisory only. It
must not become target mutation unless the trigger explains why evidence is
still sufficient.

### Target `.cerebro/` Handling

Declare exactly one:

```text
absent
legacy_external
legacy_compatible
legacy_incompatible
canonical_current
blocked
```

Rules:

- Unknown target `.cerebro/` state blocks mutation.
- Never overwrite target `.cerebro/` without explicit trigger language.
- Never treat target `.cerebro/` as Cerebro repo state.
- Preserve before replacement if replacement is explicitly authorized.

### Scope

List allowed Cerebro files and allowed target files separately.

Allowed target paths must be as narrow as possible. Globs are allowed only when
the trigger explains why a fixed file list is not yet knowable.

### Explicit Prohibitions

At minimum, prohibit:

- Cerebro `core/`;
- Cerebro `cli/`;
- Cerebro `extensions/`;
- canonical `tests/` unless separately authorized;
- `core/schema.py`;
- Cerebro `.cerebro/`;
- target `.cerebro/` unless explicitly authorized;
- source registration;
- memory writes;
- claim graph creation;
- runtime gates;
- cloud deployment;
- secrets or env edits unless explicitly listed.

### Proof Plan

Declare proof before implementation.

Allowed proof types:

```text
none                  = docs-only or recon only
target_typecheck      = target static validation
target_unit           = target local regression/unit test
target_local_runtime  = local service/runtime proof
browser_dom           = UI proof through local browser/DOM
cerebro_arch_docs     = Cerebro architecture/doc governance
cerebro_full_gate     = AGENTS-equivalent full gate
```

Proof cost must match the required proof. If the proof needs local services,
browser, Docker, Supabase, Expo, or cleanup, mark `proof_cost` at least
`medium` and usually `infrastructure-heavy`.

### Cleanup Plan

Required when `cleanup_required = true`.

Must name:

- temporary processes;
- generated files;
- local users/test data;
- local services;
- report/log files;
- what remains intentionally as evidence.

### Rollback Plan

Must say how to undo:

- Cerebro docs;
- target code/files;
- target local data;
- generated or temporary artifacts.

If rollback is manual, say so. If rollback is not reversible, the trigger must
escalate to human approval before any write.

### Stop Conditions

At minimum:

- AGENTS-equivalent gate red;
- source-set sufficiency drops below the declared threshold;
- target `.cerebro/` handling is ambiguous;
- target writes exceed `max_target_writes`;
- implementation requires paths outside whitelist;
- proof cost exceeds declared `proof_cost`;
- slice becomes pure target product work without Cerebro learning;
- three consecutive target-mutating slices have already completed;
- runtime/schema/state/authority work becomes necessary.

### Acceptance Criteria

Must include:

- exact target behavior or evidence expected;
- exact Cerebro learning expected;
- required target validation;
- required Cerebro validation;
- target report location if target mutation occurs;
- final AGENTS-equivalent gate before closure.

### Target Report Shape

If the target is mutated, the target report must include:

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

Target report is evidence, not Cerebro state.

## Mandatory Reviewer Pass

Before execution, run the trigger text through
`experiments/third_party_trigger_review`.

Expected result:

```text
readiness = "ready_for_human_review"
state_change = "none"
```

Important:

- `ready_for_human_review` is not permission.
- Any blocker means do not execute.
- Any warning must be acknowledged in the trigger or fixed.
- `consolidation_required` means stop target work and consolidate in Cerebro.

## Consolidation Rule

After three consecutive target-mutating slices, stop target work.

The next slice must be Cerebro-side consolidation, not another target feature.

The consolidation must answer:

- what did the target prove about Cerebro?
- what was unexpectedly expensive?
- which source assumptions were wrong?
- where did human judgment matter?
- which future Cerebro improvement is justified?
- which target work should stop until Cerebro absorbs the lesson?

## Filled Trigger Skeleton

Use this skeleton as the body of a new formal trigger.

```markdown
# FORMAL RESUME TRIGGER - [Target] [Slice Name]

status: active
created_at: YYYY-MM-DD

## Structured Third-Party Block

\`\`\`toml
[third_party]
target_path = "D:/absolute/path/to/target_project"
slice_kind = "management_proof|target_product_work|both"
dogfood_value = "What Cerebro learns from this target work."
target_product_value = "What the target gains."
proof_cost = "none|low|medium|high|infrastructure-heavy"
cleanup_required = true
target_cerebro_handling = "absent|legacy_external|legacy_compatible|legacy_incompatible|canonical_current|blocked"
consecutive_target_mutating_slices_before_this = 0
max_target_writes = 3
expected_target_runtime = "none|local-only|local-with-services|cloud-prohibited"

[source_roles]
project_identity = "..."
current_state = "..."
continuity_delta = "..."
decision_ledger = "..."
next_work_map = "..."
architecture_rules = "none"
validation_surface = "none"

[boundaries]
allowed_cerebro_paths = [
  "docs/operations/FORMAL_RESUME_TRIGGER_....md",
  "docs/operations/SYSTEM_STATE.md",
  "docs/operations/OPPORTUNITY_MAP.md",
  "docs/operations/observation_center.toml",
]
allowed_target_paths = [
  "D:/absolute/path/to/target_project/...",
]
forbidden_cerebro_paths = [
  "core/",
  "cli/",
  "extensions/",
  "tests/",
  "core/schema.py",
  ".cerebro/",
]
forbidden_target_paths = [
  "D:/absolute/path/to/target_project/.cerebro/",
]

[risk_budget]
authority_impact = "none"
runtime_impact = "target-only"
reversibility = "high"
rollback = "manual-target-revert"
gate_level = "G2"
promotion_path = "requires-consolidation"
\`\`\`

## Objective

Target objective:

Cerebro objective:

## Why This Target

## Source-Set Sufficiency

## Target `.cerebro/` Handling

## Scope

Allowed Cerebro files:

Allowed target files:

## Explicit Prohibitions

## Proof Plan

## Cleanup Plan

## Rollback Plan

## Stop Conditions

## Acceptance Criteria

## Target Report Shape

## Reviewer Evidence

- `experiments.third_party_trigger_review`: pending before execution
- expected readiness: `ready_for_human_review`
- state_change: `none`

## Closure

Only fill after implementation and validation.
\`\`\`

## What This Template Does Not Authorize

- It does not authorize target mutation.
- It does not authorize target `.cerebro/` mutation.
- It does not authorize Cerebro runtime changes.
- It does not authorize source registration.
- It does not authorize memory writes.
- It does not authorize claim graph creation.
- It does not authorize runtime gates.
- It does not override AGENTS, active triggers, or the freeze policy.
