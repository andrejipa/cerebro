# ADR-004: Local Session Isolated

## Context

Session state is operational and local. It must not become shared project truth.

## Decision

Keep session state in `.cerebro/session.local.json`, separate from the canonical state file.

## Consequence

Resume flow can track local continuity without polluting shared state.
