# ADR-007: Aristotelian Decision Checklist

## Context

The repository baseline is now intentionally small, product-focused, and protected against historical drift.

That baseline reduces noise in Git, but it does not by itself prevent future architectural regression. Humans and agents still need a simple way to evaluate proposed changes before they create new sources of truth, blur category boundaries, or introduce complexity that does not strengthen the system.

The project already depends on strict architectural distinctions:

- canonical runtime truth belongs only where the core defines it
- derived views must remain derived
- optional behavior belongs in extensions rather than in the core by default
- validation enforces runtime invariants, not governance prose

The project needs a permanent decision aid that reinforces those distinctions without turning governance text into executable product behavior.

## Decision

Adopt an Aristotelian-inspired decision checklist as a permanent architectural governance artifact.

- The checklist lives in `docs/reference/DECISION_CHECKLIST.md`.
- It is intended for human decision-making, ADR drafting, design review, and agent work prompts.
- It must be used as a manual discipline layer before introducing new files, flows, abstractions, or sources of truth.
- It must remain outside runtime state and outside automatic validation behavior.

The checklist is inspired by a practical Aristotelian discipline:

- distinguish what a thing is from what is merely said about it
- distinguish the core substance of the system from optional or derived additions
- reject category mixing that turns views, heuristics, or convenience layers into truth
- judge changes by purpose, invariants, and proportionality rather than by novelty alone

The checklist governs decisions, not execution.

- It does not belong in `.cerebro/state.json`.
- It is not an automatic `source`.
- It does not change `validate`.
- It does not alter CLI behavior, persistence rules, or extension loading.
- It does not create new runtime policy gates.

## Consequence

- The repository gains a durable governance mechanism without increasing runtime complexity.
- Humans and agents have a fast way to reject changes that create ambiguity, duplicate truth, or weaken invariants.
- Architectural discipline becomes easier to apply consistently during prompts, reviews, and ADR discussions.
- The checklist can guide evolution of the system, but any rule that should affect product behavior still requires an explicit product change and its own architectural decision.
