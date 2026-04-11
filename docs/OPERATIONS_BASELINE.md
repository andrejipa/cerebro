# Operations Baseline

This document is the operational baseline for daily Cerebro use.

The system is no longer in open-ended feature growth.
Use it as infrastructure.
Change it only through the formal freeze-break protocol.

## What Cerebro Solves

- explicit continuity of project context
- deterministic restart through canonical runtime state
- short read-only views over the current canonical state
- disciplined external execution without giving external tools authority

## One Daily Protocol

1. Start in the target project directory.
2. Choose the correct mode: bootstrap, continuous work, or audit/engineering.
3. If the project has no `.cerebro/`, use bootstrap mode.
4. If the project is already initialized, start with `cerebro analyze`.
5. Use exports only as derived views over the canonical state.
6. Use the automation bridge only for mechanical external execution and logging.
7. If bridge or agent work matters for continuity, return explicitly to Cerebro with `checkpoint` and `analyze`.
8. Treat bridge logs, agent notes, and external outputs as disposable unless they are re-anchored through normal project work and the canonical runtime flow.

## Mode 1: Bootstrap

Use this mode only when entering a project with no `.cerebro/` or when onboarding an already-live project that has not been initialized yet.

Protocol:

1. Optionally run `cerebro bootstrap-scan --root ...` to get assistive candidates.
2. Decide the initial source files explicitly.
3. Run `cerebro init`.
4. Run `cerebro import-context --files ...`.
5. Run `cerebro checkpoint --goal ... --summary ... --next-step ...`.
6. Run `cerebro validate`.
7. From that point on, stop bootstrapping and switch to `cerebro analyze` as the standard entrypoint.

## Mode 2: Continuous Work

Use this mode for normal day-to-day work in a project that already has `.cerebro/`.

Protocol:

1. Start with `cerebro analyze`.
2. Read the current checkpoint and the registered source surface.
3. Use exports only if a shorter derived view helps.
4. Do the actual project work outside the runtime as needed.
5. Close the round with `cerebro checkpoint`.
6. On the next round, restart again with `cerebro analyze`.

## Mode 3: Audit / Engineering

Use this mode only for external stress, regression validation, bridge-assisted execution, or protocol-driven agent work.

Protocol:

1. Anchor yourself in the target project with `cerebro analyze` when the project is already initialized.
2. If you need mechanical external execution, use the automation bridge.
3. If the task needs role-based external coordination, run one full agent round through the approved protocol.
4. Keep all external artifacts non-canonical.
5. Return to Cerebro explicitly through `checkpoint` and `analyze` before treating the round as continuity.

## Bridge Use

Use the automation bridge only for:

- repeated read-only audits
- mechanical execution packaging
- structured per-run logging that would otherwise be assembled manually

Do not use the automation bridge for:

- deciding canonical context
- choosing `sources`
- replacing `import-context`
- replacing `checkpoint` or `analyze`
- defining project truth

## Agent Use

Use the agent protocol only when the work is external engineering, audit, triage, correction, or flow validation.

Do not use the agent team as a replacement for the runtime.

- agents do not define state
- agents do not define semantics
- agents do not replace `analyze`
- agents do not create a second source of truth

## Do Not Tinker

If there is no concrete, repeated, unmet use case against the current runtime and export surface, do not evolve the system.

The correct action is:

- operate the system
- maintain it proportionally when a real bug appears
- stop there

Do not reopen engineering because:

- the system looks austere
- a richer interface seems appealing
- a new helper sounds clever
- the project feels "almost there"

## Red Lines

Never:

- change the core without formal architecture approval
- treat bridge output as canonical truth
- let heuristics choose context automatically
- register `sources` automatically
- bypass `validate` or `analyze`
- create a second source of truth
- reopen `alignment-export` without a canonical alignment artifact

## Onboarding Quick Start

- To enter a new project: use bootstrap mode.
- To resume a project: start with `cerebro analyze`.
- To inspect state quickly: use the read-only exports.
- To reduce mechanical Codex handoff work: use the automation bridge.
- To run external engineering rounds: use the approved agent protocol.
- If nothing concrete is broken or missing: do not modify the system.

## Status

Cerebro is now operational infrastructure.

Future evolution is still possible, but only through:

- one explicit next-layer decision
- one concrete repeated unmet use case
- one minimum safe external increment at a time
