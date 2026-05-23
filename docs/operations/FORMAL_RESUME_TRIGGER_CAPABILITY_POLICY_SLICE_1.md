# FORMAL RESUME TRIGGER - Capability Policy Slice 1

status: consumed
created_at: 2026-05-08
closed_at: 2026-05-08

## Objective

Create the first derived capability-policy layer for the Cerebro Control Plane
front.

This slice exists because MCP, Agents SDK tools, shell commands, browser
automation, and future external adapters need a local policy vocabulary before
they can be exposed safely.

## Scope

Allowed paths:

- `experiments/capability_policy/`
- `experiments/lifecycle.toml`
- this trigger
- live operational projections and queue/archive docs needed for closure

Forbidden paths:

- `core/`
- `cli/`
- `extensions/`
- `.cerebro/`
- third-party target projects

## Non-Authority Contract

The policy assessment must always declare:

```text
state_change = none
authority = non-authoritative
advisory_allow_is_not_permission = true
must_not_execute_automatically = true
```

It must not:

- execute commands;
- register tools;
- grant permission;
- mutate canonical state;
- create a runtime gate;
- write memory;
- expose MCP or other external adapters.

## Closure

Implemented `experiments/capability_policy/` as a read-only advisory
experiment.

The package adds:

- `CapabilityRule`;
- `CapabilityRequest`;
- `CapabilityAssessment`;
- TOML manifest loading;
- deterministic request evaluation;
- JSON and Markdown renderers;
- tests covering manifest replay, root-escape and `.cerebro` manifest
  rejection, duplicate rule rejection, advisory allow as non-permission,
  no-match fail-closed behavior, network/sensitive-data blocking,
  `.cerebro` write blocking, review-required policy, missing approval, and
  rendered non-authority boundaries.

Validation:

- `python -m unittest discover -s experiments/capability_policy/tests -v`
  passed `8/0`.
- `python -m unittest discover -s experiments/_lifecycle/tests -v` passed
  after lifecycle registration.

No runtime, CLI, extension, `.cerebro/`, schema, external-tool adapter, MCP,
Agents SDK, or third-party target mutation occurred.
