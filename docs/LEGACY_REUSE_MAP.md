# Legacy Reuse Map

This document records what can be reused from the old system without reintroducing its structural failures.

## Reuse Almost As-Is

- `return-map` as a read-only export derived from the current checkpoint
- short operational status as a read-only export
- bootstrap and closing discipline as human guidance, not runtime behavior

## Reuse Only If Reinterpreted

- `alignment` as a human checklist only; `alignment-export` remains blocked until the contract defines a canonical artifact for it
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
3. `impact-export` as a constrained read-only view of the current operational surface
4. keep `alignment-export` blocked unless a future architecture decision adds canonical support for it
5. optional graph views as external consumers
6. human operational templates that remain outside runtime authority
