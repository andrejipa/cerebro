# Extension Model

## What An Extension Is

An extension is any consumer of the core that reads state and provides another interface or view.

Examples:

- alternate UIs
- generated reports
- integrations that react to validated state

## How Extensions Interact With The Core

Extensions may:

- use the CLI
- use the stable `StateStore` read API
- consume read models from the core

Extensions may not:

- write `.cerebro/state.json` directly
- write `.cerebro/session.local.json` directly
- write inside `.cerebro/` in any form
- mutate state automatically on external events
- infer or register sources without explicit user action
- treat logs as authority

## Authority Boundary

- core is the only authority over runtime state
- extensions are consumers only
- if future product behavior needs state mutation, it belongs in a core or CLI contract change, not in an extension
