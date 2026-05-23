"""Runtime Manager deterministic evals.

Advisory-only. This package evaluates pre-built runtime manager
trace/metrics/replay artifacts for structural invariants.

Guardrails:
- eval_is_not_permission: True
- eval_pass_is_not_execution_approval: True
- must_not_execute_automatically: True

This package does NOT:
- read observation_center.toml or runtime.db inside the package
- write files, execute commands, mutate state
- expose CLI, MCP, Agents SDK, Temporal, LangGraph, or OpenTelemetry adapters
- grant permission, select work, or become a runtime gate
"""
from __future__ import annotations
"""runtime_manager_evals package"""
