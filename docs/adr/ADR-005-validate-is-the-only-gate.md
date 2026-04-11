# ADR-005: Validate Is The Only Gate

## Context

Multiple operational gates produce ambiguous meanings for readiness and validity.

## Decision

Use `validate` as the only runtime integrity gate before resume.

## Consequence

The product keeps one deterministic definition of structural validity.
