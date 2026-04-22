# status-export

Read-only extension that renders a short operational status from the canonical state.

## What It Does

- reads the current state through the public core API
- renders a compact operational status view
- prints to stdout or writes to an explicit output file

## What It Does Not Do

- it does not modify state
- it does not modify session
- it does not inspect source contents
- it does not infer missing context
- it does not become a source of truth

The generated status is derived and disposable.
It is a human-readable Markdown view first, not a stable machine API.

Current reading limits:

- some diagnostics are current-plan only
- some counters summarize longer-lived runtime history
- consumers must interpret the time horizon explicitly instead of assuming every number refers to the current round
- section names, heading layout, and counter grouping remain presentation details unless another explicit integration contract stabilizes them
- automation that parses this Markdown is consuming best-effort support output and should stay version-aligned with the exporter it reads
