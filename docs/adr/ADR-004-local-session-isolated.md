# ADR-004: Local Session Isolated

## Context

Session state is operational and local. It must not become shared project truth.

## Decision

Keep session state in `.cerebro/session.local.json`, separate from the canonical state file.

## Consequence

Resume flow can open a local continuity artifact for one validated revision without polluting shared state.
That artifact does not establish durable ownership or uninterrupted continuity across later reopen attempts.
