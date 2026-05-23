# Control Plane Tool Manifest Review

`control_plane_tool_manifest_review` is a read-only, non-authoritative review of caller-supplied tool manifest candidates.

It exists before any registered tool manifest, MCP server, Agents SDK tool boundary, adapter, scheduler, queue reader, state store, runtime registry, or durable runtime exists in this repository.

The package evaluates whether a proposed manifest keeps tool risk explicit:

- per-tool decision and risk level;
- human confirmation for destructive or mutating tools;
- network and sensitive-output review posture;
- path scopes;
- approval, evidence, audit logging, rollback, timeout, rate limit, sandbox, and secret-handling policy;
- decision, rule, integrity, capability, and action-review evidence.

## Boundary

- state_change: none
- authority: non-authoritative; advisory control-plane tool manifest review only
- tool_manifest_review_is_not_permission: true
- manifest_candidate_is_not_registered_tool_manifest: true
- tool_decision_is_not_execution_approval: true
- tool_manifest_review_is_not_adapter: true
- tool_manifest_review_is_not_scheduler: true
- finding_is_not_truth: true
- must_not_execute_automatically: true

The package does not read `.cerebro/`, `docs/operations`, state files, queues, locks, sessions, events, runtime stores, tool registries, or target-project files. It does not import core runtime modules, runtime SDKs, CLI modules, adapters, MCP libraries, or network/process libraries. It does not write files, execute commands, mutate state, register tools, expose adapters, call MCP tools, schedule work, choose a next action, grant permission, approve execution, or become a source of truth.

All inputs are supplied by the caller as already-sanitized in-memory payloads or already-built advisory review objects.
