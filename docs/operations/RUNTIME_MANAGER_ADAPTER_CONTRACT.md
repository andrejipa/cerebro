# Runtime Manager Adapter Contract

**Status:** draft (Phase 5 -- no real adapters yet)
**Authority:** docs-only; not a runtime gate

---

## Purpose

This document defines the contract that any future adapter must satisfy
before it may call into the Runtime Manager store. No real adapter exists
as of Phase 5. This is a pre-commitment boundary document.

## What an Adapter Is

An adapter is any code outside core/ that calls RuntimeManagerStore methods
to acquire leases, record approvals, run commands, raise stop conditions,
or read traces/metrics for external presentation.

Examples (not yet implemented):
- MCP server exposing runtime-manager tools to an LLM agent
- CLI bridge calling store on behalf of a CI/CD pipeline
- Webhook handler triggering run_command from an external event

## What an Adapter Must NOT Do

1. Read or write runtime.db directly (bypass the store API).
2. Accept raw argv from untrusted sources -- argv must come from
   the command_registry in the TOML, not from adapter inputs.
3. Grant permissions based on trace output or replay results.
   Traces and replay results are advisory-only.
4. Expose or forward raw stdout/stderr from execution_evidence.
5. Import LangGraph, Temporal, OpenAI Agents SDK, or Cloudflare Agents SDK
   without a formal human trigger (separate Phase 6+ trigger required).
6. Bypass approval requirements -- every call to run_command must
   go through check_command_eligibility first.

## What an Adapter Must Declare

1. adapter_is_not_runtime_authority: True
2. adapter_is_not_permission_layer: True
3. adapter_reads_sanitized_traces_only: True

## Boundary Enforcement

The boundary audit (experiments/control_plane_boundary_audit/) will flag
any experiment package that imports core/ or calls store methods directly.
Real adapters must live under cli/ or a dedicated adapters/ directory,
never under core/ or experiments/.

## Activation Criteria for a Real Adapter

Before any real adapter ships:
- A formal human trigger (FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_6.md
  or similar) must authorize it.
- RUNTIME_MANAGER_MCP_THREAT_MODEL.md must be reviewed and signed off.
- The adapter must pass the boundary audit with zero findings.
- The gate must remain green.
