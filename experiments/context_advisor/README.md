# Context Advisor

`experiments/context_advisor/` is a derived, local-only, read-only experiment.

It combines:

- `experiments/context_discovery`: candidate, drift, and missing-source evidence
- `experiments/context_vectors`: deterministic local ranking evidence

The output is LLM-facing advisory context. A downstream model may use it to
decide what to inspect or propose next, but the report is not runtime authority.

Hard boundary:

- may suggest inspection
- may draft proposed context changes
- must not mutate `.cerebro/state.json`
- must not import sources
- must not edit the target project
- must preserve `state_change: none`
