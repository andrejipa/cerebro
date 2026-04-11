# ADR-001: Single State File

## Context

The product needs one authoritative runtime state that is easy to validate and hard to drift silently.

## Decision

Use a single canonical state file at `.cerebro/state.json`.

## Consequence

State is easier to validate and reason about, but all runtime state mutation must stay behind `StateStore`.
