# ADR-003: No Heuristics

## Context

Heuristic discovery was a major source of hidden behavior and contamination risk in earlier designs.

## Decision

The core performs no repository scanning, inference, or semantic guessing.

## Consequence

Behavior is more predictable and testable, but convenience features must stay outside the core.
