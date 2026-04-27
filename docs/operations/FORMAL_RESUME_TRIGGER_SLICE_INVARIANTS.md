# Formal Resume Trigger — Slice Invariants Field

status: open
created_at: 2026-04-27
consumed_at: —
owner: pending human approval
level: 2
mode: schema-additive

## Purpose

Add an optional `invariants` field to the action schema that declares
structural invariants which must hold after any action of a given type,
separate from functional test commands.

The distinction:
- `test_commands` — functional regression: does the code still work?
- `invariants` — structural integrity: is the system still in a valid state?

Examples of invariants that are currently implicit or unverified:
- `git_working_tree_clean` — no untracked mutations outside declared scope
- `no_new_import_cycles` — import graph did not gain cycles
- `all_exports_read_only` — extensions/ files did not gain write paths
- `schema_version_unchanged` — core/schema.py version field unchanged
- `test_count_nondecreasing` — suite did not lose tests

## Motivation

Identified as a gap versus the current state of the art in agentic runtime
verification (2025-2026). The field is additive — it does not change existing
runtime behavior or require enforcement by the runtime itself. Invariants
declared in this field are checked by the documenter/reviewer layer, not by
the canonical runtime.

A later trigger may authorize runtime enforcement if operational evidence
shows the docs-layer check is insufficient.

## Scope — minimum safe increment

This trigger authorizes only:

1. Adding `invariants` as an optional list field to `core/schema.py` action
   type definitions — additive only, no existing field changes.
2. Adding validation in `core/validation.py` that checks declared invariants
   are from a known vocabulary (no free-text) — additive only.
3. Updating `docs/` to document the new field.
4. Adding proportional tests for the new schema field and validation logic.

## Whitelist

Writable:
- `core/schema.py` — add `invariants` optional field only
- `core/validation.py` — add invariant vocabulary check only
- `tests/test_validate.py` — new tests for invariants field
- `docs/operations/FORMAL_RESUME_TRIGGER_SLICE_INVARIANTS.md`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`
- `AGENTS.md`

Readable:
- All existing core/, tests/, docs/

## Explicit Non-Authorization

This trigger does not authorize:
- runtime enforcement of invariants during `apply` or `verify`
- changes to `state.json` shape or canonical state authority
- changes to `cli/` commands or command policy
- changes to `extensions/`
- any new canonical artifact beyond the `invariants` field
- free-text invariants (must be from declared vocabulary)

## Acceptance Criteria

- `core/schema.py` accepts `invariants: list[str] | None` in action type defs.
- `core/validation.py` rejects unknown invariant names with a typed error.
- Vocabulary covers at minimum: `git_working_tree_clean`, `no_new_import_cycles`,
  `schema_version_unchanged`, `test_count_nondecreasing`, `all_exports_read_only`.
- All existing tests continue to pass.
- New tests prove: valid invariants accepted, unknown invariants rejected,
  field is optional (existing action types unaffected).
- Full AGENTS-equivalent gate passes.
