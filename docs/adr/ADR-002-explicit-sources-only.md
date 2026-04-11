# ADR-002: Explicit Sources Only

## Context

Automatic discovery creates hidden coupling and makes integrity impossible to reason about.

## Decision

Only files explicitly passed by the user can become `sources`.

## Consequence

The system stays deterministic, but source registration remains a deliberate user action.
