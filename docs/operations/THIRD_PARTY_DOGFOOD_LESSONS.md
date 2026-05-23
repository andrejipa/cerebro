# Third-Party Dogfood Lessons

Status: advisory operational lessons
Date: 2026-04-25
Primary pilot: `D:\projetos_cli\pessoais\rpg_caminhada`

## Purpose

This document consolidates what the `rpg_caminhada` pilot taught Cerebro about
managing third-party projects.

It is not canonical runtime state, not permission to mutate future projects, and
not a replacement for formal triggers. It is evidence for future third-party
management slices.

## Core Finding

Cerebro can manage a real third-party project, but the main risk is not only
technical correctness. The main risk is role drift.

Without an explicit stop line, the agent becomes a product developer for the
target project and forgets the purpose of the pilot: improving Cerebro's ability
to manage projects.

The correct framing is:

```text
Target project work is the experiment surface.
Cerebro capability improvement is the reason for the experiment.
Target reports are evidence.
Cerebro docs decide what becomes reusable guidance.
```

## What Worked

### 1. Formal Triggers Made Third-Party Work Auditable

Every meaningful target slice had a narrow trigger, whitelist, stop conditions,
and validation evidence. This prevented the target project from becoming an
unbounded implementation playground.

Reusable rule:

```text
No third-party mutation without a trigger that names the target path, allowed
files, forbidden files, proof plan, rollback plan, and Cerebro learning goal.
```

### 2. Local Proof Beat Speculation

The strongest progress came from local proof loops:

- target typecheck;
- Supabase local smoke or regression harness where needed;
- Expo/browser proof for UI work;
- Cerebro architecture/doc governance;
- final AGENTS-equivalent gate.

Reusable rule:

```text
Third-party work is not complete when code changes. It is complete when the
target behavior is proven locally and Cerebro records what the proof taught.
```

### 3. Advisory Reports Need a Return Path

Target reports under the third-party project were useful, but they are only
evidence. They do not automatically update Cerebro policy.

Reusable rule:

```text
Every target report must answer: what did this prove about the target, and what
does it suggest Cerebro should improve?
```

### 4. Source-Set Quality Matters More Than Scanner Cleverness

The initial source set would have been misleading without continuity/current
state files. The stale diagnostic said the project had no implementation even
though schema, types, migrations, app scaffold, and function stubs already
existed.

Reusable rule:

```text
A third-party source set must contain at least one file for each role:
project identity, current state, continuity/delta, decision ledger, and next
work map.
```

If any role is missing, Cerebro should treat the source set as incomplete, not
as negative evidence.

### 5. Target `.cerebro/` State Is Operational, Not Sacred

The pilot exposed real hygiene problems around legacy target `.cerebro/` state
and tokenless active sessions. Preserving old state before replacing it was the
right move.

Reusable rule:

```text
When a target already has `.cerebro/`, classify it before mutation:
unknown, legacy-compatible, legacy-incompatible, canonical-current, or blocked.
Preserve before replacing.
```

### 6. Infrastructure Work Is Still Third-Party Mutation

Docker, Supabase local runtime, env examples, Expo web dependencies, and local
server proof were all required for progress. They are easy to undercount because
they feel like setup.

Reusable rule:

```text
Tooling and local infrastructure changes must be declared in the trigger with
the same rigor as product code changes.
```

### 7. Consecutive Target Slices Need a Mandatory Consolidation Stop

The pilot ran many target slices before this consolidation. That produced real
product value, but it delayed the Cerebro learning loop.

Reusable rule:

```text
After three consecutive target-mutating slices, stop target work and run a
Cerebro-side consolidation slice before opening another target feature trigger.
```

This is not conservatism. It is how dogfood becomes product knowledge instead
of just outsourced implementation.

## What Failed Or Nearly Failed

### Stale Canonical-Looking Documents

The target had documents that looked authoritative but were stale. A diagnostic
can be canonical in form and false in current content.

Implication:

```text
registered != true
canonical-looking != current
silence != negative evidence
```

### Workstream Drift

The third-party pilot moved from source intake to validation, backend harnesses,
equipment runtime, combat UI, reward UI, inventory UI, and enemy decision UI.
That was productive, but it crossed from "prove Cerebro can manage" into
"continue building the product".

Implication:

```text
Each third-party trigger must declare whether the slice is:
- management proof;
- target product work;
- both.
```

If it is only target product work, Cerebro should require a fresh reason why the
slice still advances Cerebro.

### Proof Cost Was Not Explicit Enough

Some proof required Expo, Supabase, Docker, local users, browser DOM, and cleanup.
That cost needs to be visible before selecting a slice.

Implication:

```text
Third-party trigger risk budgets need a `proof_cost` field:
none, low, medium, high, or infrastructure-heavy.
```

### Target Reports Were Too Easy To Accumulate

Reports are useful, but many reports without synthesis create another ledger to
read.

Implication:

```text
Target reports need periodic compression into Cerebro-side lessons.
```

## Reusable Pattern

```text
1. Recon
2. Intake gate
3. Source-set classification
4. Safe target runtime handling
5. First proof slice
6. Applied target slices
7. Mandatory consolidation after three target-mutating slices
8. Cerebro hardening decision
```

## Candidate Improvements For Cerebro

These are candidates, not permission:

1. Add a third-party intake checklist that verifies source roles:
   identity, current state, continuity, decisions, next work.
2. Add a target `.cerebro/` classification procedure before any target runtime
   mutation.
3. Add a `dogfood_value` field to third-party triggers.
4. Add `proof_cost` and `cleanup_required` fields to third-party triggers.
5. Add a mandatory consolidation rule after three consecutive target-mutating
   slices.
6. Add a standard third-party report template with "target proof" and "Cerebro
   lesson" sections.
7. Add a runbook-level stop line: target product work pauses when Cerebro has
   enough evidence to improve its own management layer.

## Boundary

This document does not authorize:

- more work in `rpg_caminhada`;
- imports into any target `.cerebro/`;
- runtime changes in Cerebro;
- source registration;
- claim graph creation;
- memory writes;
- treating these lessons as canonical truth.

Next step: use `THIRD_PARTY_PROJECT_MANAGEMENT_RUNBOOK.md` as the operational
entry point for future third-party project management.
