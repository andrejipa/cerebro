# Runtime Manager Autonomy Levels

**Status:** Phase 8 — active policy
**Authority:** subordinate to FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_8.md
**Not a permission, not a runtime gate:** classification is advisory evidence only.

---

## Overview

Five canonical levels describe how much autonomy an action requires and how
much friction must be present before it can execute.  Higher levels require
more controls; overrides can only _increase_ the effective level, never reduce.

```
L0_observe         friction=0   no lease, no approval
L1_derived         friction=1   lightweight diff check for operational docs
L2_local_code      friction=2   lease + command_registry (approval conditional)
L3_runtime_mutation friction=4  lease + approval + evidence + trace
L4_external_high_risk friction=9 human decision required; NOT executable via MCP
```

---

## Level Definitions

### L0_observe

**Purpose:** read, observe, plan — zero side effects on runtime state.

**Typical operations:**
- `runtime_status`, `runtime_next`, `runtime_check_command`
- `runtime_trace_list/show/export`, `runtime_metrics`, `runtime_replay_scenario`
- Any pure read from the store

**Controls required:** none (rate limit applies)
**Lease required:** no
**Approval required:** no
**MCP executable:** yes

---

### L1_derived

**Purpose:** write derived artefacts (docs, projections, evals) that summarise
or reflect existing runtime state but do not touch runtime authority.

**Typical operations:**
- Updating SYSTEM_STATE.md, OPPORTUNITY_MAP.md, eval output files
- Writing docs/ projections with no schema or runtime mutation

**Controls required:**
- Lightweight diff check when operational docs are touched
**Lease required:** no
**Approval required:** no (by default)
**MCP executable:** yes (with token scoped to L1+)

---

### L2_local_code

**Purpose:** local code and test mutations without network, secrets, or external
adapters.

**Typical operations:**
- Running registered test commands
- Editing local code files within `path_scope`
- Local git operations that do not touch remotes

**Controls required:**
- Lease (single-flight enforcement)
- Command must be in `command_registry`
- Approval only when `approval_requirement != "none"` in the policy
**Lease required:** yes
**Approval required:** conditional on policy
**MCP executable:** yes (with token scoped to L2+)

---

### L3_runtime_mutation

**Purpose:** mutate runtime state — run commands, manage approvals/rollbacks,
manage stop conditions, manage tokens, use MCP STDIO mutations.

**Typical operations:**
- `run_command`, `record_approval`, `rollback_command`
- `raise_stop_condition`, `resolve_stop_condition`
- `issue_adapter_token`, `revoke_adapter_token`
- `runtime_run_command` via MCP

**Controls required:**
- Lease
- Command in registry
- Approval when `approval_requirement != "none"`
- Execution evidence written
- Operation trace written
**Lease required:** yes
**Approval required:** per policy (when approval_requirement="required")
**MCP executable:** yes (with token scoped to L3 and appropriate scopes)

---

### L4_external_high_risk

**Purpose:** any action that opens a network connection, accesses cloud/remote
resources, handles high-sensitivity data, targets external systems, or is
explicitly marked for human decision.

**Typical triggers (any one sufficient):**
- `network_allowed = true`
- `data_sensitivity` in ("high", "critical")
- `requires_human_decision = true`
- `target_scope` in ("external", "cloud", "release", "production")
- `side_effect_class = "external"`
- `risk_level_override = "L4_external_high_risk"`

**Controls required:**
- Explicit human decision per action
- Lease with short TTL
- Approval
- Evidence
- Trace
- Full gate validation

**MCP executable:** **NO — blocked unconditionally in this phase.**
Any MCP token attempting an L4 action receives a PermissionError immediately,
regardless of scopes or `max_autonomy_level`.

---

## Classification Rules

1. **Base level** is derived from `side_effect_class`:

   | side_effect_class     | base level          |
   |-----------------------|---------------------|
   | `read-only`           | L0_observe          |
   | `derived-write`       | L1_derived          |
   | `docs-write`          | L1_derived          |
   | `local-mutation`      | L2_local_code       |
   | `test-run`            | L2_local_code       |
   | `runtime-mutation`    | L3_runtime_mutation |
   | `system-mutation`     | L3_runtime_mutation |
   | `destructive`         | L3_runtime_mutation |
   | `external`            | L4_external_high_risk|
   | _(unknown)_           | L3_runtime_mutation  |

2. **Elevators** (each independently forces the level to at least the given target):
   - `network_allowed = true` → L4
   - `data_sensitivity in ("high", "critical")` → L4
   - `data_sensitivity = "sensitive"` → min L3
   - `requires_human_decision = true` → L4
   - `target_scope in ("external", "cloud", "release", "production")` → L4

3. **Override** (`risk_level_override`): only increases, never decreases.
   If the override names a level lower than computed, it is ignored silently.

4. **Final level** = max(base_level, all_elevator_levels, override_level).

---

## `max_autonomy_level` on Adapter Tokens

Each adapter token carries a `max_autonomy_level` field (default:
`L3_runtime_mutation`).  A tool call whose effective level exceeds the token's
ceiling is rejected with a `PermissionError` before any store access.

| Default            | Rationale                                       |
|--------------------|-------------------------------------------------|
| L3_runtime_mutation| Full local capability; L4 always blocked        |

Tokens may be issued with a lower ceiling (e.g., L0 for read-only agents).

---

## Friction Budget

| Level                 | Budget | Meaning                          |
|-----------------------|--------|----------------------------------|
| L0_observe            | 0      | No gates                         |
| L1_derived            | 1      | One lightweight check            |
| L2_local_code         | 2      | Lease + registry                 |
| L3_runtime_mutation   | 4      | Lease + registry + approval + evidence |
| L4_external_high_risk | 9      | Full gate + human decision       |

The budget is advisory: it communicates the expected cost of friction to the
caller so agents can plan their round accordingly.

---

## Invariants (always true)

- Classification never returns a level lower than the base derived from
  `side_effect_class`.
- Overrides only increase the effective level.
- L4 is always blocked for MCP execution in Phase 8.
- `classification_is_not_permission = True` on every result.
- No classification changes the database; it is a pure read.
