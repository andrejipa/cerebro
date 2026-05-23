# ADR-008: Analyze Is The Standard Entrypoint

## Context

The runtime now exposes both `analyze` and `resume`.

Both commands depend on the same deterministic core, but leaving multiple visible resume entrypoints at the same architectural level creates avoidable ambiguity for humans, agents, prompts, and documentation. The system needs one official continuity protocol that is easy to teach, easy to test, and hard to reinterpret.

The runtime specification already defines a single continuity flow:

- validate canonical state
- block explicitly on failure
- reconstruct the current checkpoint
- expose the current context
- open the local session

That flow should have one official operational name.

## Decision

Adopt `cerebro analyze` as the permanent standard entrypoint for runtime continuity.

- `cerebro analyze` is the only recommended resume entrypoint for humans and agents.
- `resume` remains available only for compatibility and does not define a separate operational model.
- Main documentation, CLI help, tests, and governance documents must converge on `analyze` as the visible protocol.
- The decision does not change the core, schema, or runtime authority boundaries.

## Consequence

- The system exposes one official continuity protocol instead of multiple competing entrypoints.
- Documentation and prompts become more predictable.
- Future regressions that reintroduce entrypoint ambiguity can be caught by automated tests.
- The core remains unchanged; this is a convergence decision at the CLI and governance layers.
