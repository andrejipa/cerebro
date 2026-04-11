# Legacy Reuse Map

This document records what can be reused from the old system without reintroducing its structural failures.

## Reuse Almost As-Is

- `return-map` as a read-only export derived from the current checkpoint
- short operational status as a read-only export
- bootstrap and closing discipline as human guidance, not runtime behavior

## Reuse Only If Reinterpreted

- `alignment` as a derived consistency view or checklist, never as state
- `vigilante de contexto` as a disposable external view, never as canonical truth
- graph and impact views as optional external visualizations
- agent modes as human playbooks, never as runtime semantics

## Historical Reference Only

- markdown subset rules for pseudo-runtime enforcement
- large hub and vault taxonomy documents
- Obsidian-specific navigation and Dataview panels

## Permanently Prohibited

- bootstrap or validation by heuristic
- hidden state influencing runtime decisions
- multiple sources of truth for continuity
- markdown or local tooling acting as runtime authority
- archive, sandbox, quarantine, or local vault content crossing into product scope

## Safe Roadmap Order

1. `status-export`
2. `return-map-export`
3. `alignment-export` only after a precise, non-authoritative definition exists
4. optional graph or impact views as external consumers
5. human operational templates that remain outside runtime authority
