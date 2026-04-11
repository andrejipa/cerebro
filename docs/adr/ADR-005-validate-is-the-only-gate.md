# ADR-005: Validate Is The Only Gate

## Context

Multiple operational gates produce ambiguous meanings for readiness and validity.

## Decision

Use `validate` as the only runtime integrity gate before operational continuity commands.

The official continuity entrypoint is `cerebro analyze`.
`resume` remains compatible, but it does not define a second gate or a second readiness model.

## Consequence

The product keeps one deterministic definition of structural validity.
The visible runtime flow stays converged around one official entrypoint.
