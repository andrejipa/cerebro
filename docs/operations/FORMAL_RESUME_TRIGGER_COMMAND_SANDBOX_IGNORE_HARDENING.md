# Formal Resume Trigger — Command Sandbox Ignore Hardening

status: consumed
created_at: 2026-04-25
consumed_at: 2026-04-25
owner: human-approved Codex execution
level: 2
mode: corrective-maintenance

## Purpose

Close the audit finding that verification sandboxing and manifests copy/hash
local generated material that is not part of the product surface, especially
`_local/`, `.git/`, `venv/`, `.tmp*/`, caches, and build artifacts.

This is corrective reliability/performance hardening. It does not change command
semantics or runtime authority.

## Whitelist

Writable:

- `docs/operations/FORMAL_RESUME_TRIGGER_COMMAND_SANDBOX_IGNORE_HARDENING.md`
- `core/command_sandbox.py`
- `tests/test_command_sandbox.py`
- `docs/operations/observation_center.toml`
- `docs/operations/SYSTEM_STATE.md`
- `docs/operations/OPPORTUNITY_MAP.md`

Readable:

- `AGENTS.md`
- live operational docs
- `core/verification_runtime.py`
- `core/command_sandbox.py`
- existing verification/sandbox tests

## Explicit Non-Authorization

This trigger does not authorize:

- edits to `core/schema.py`;
- edits to `cli/`;
- edits to `extensions/`;
- edits to `.cerebro/` or canonical state;
- changing command execution policy, approval policy, verification result
  semantics, or sandbox command environment;
- ignoring `.cerebro/` in sandbox clones or manifests;
- adding a runtime feature, third-party target behavior, or new advisory layer.

## Acceptance Criteria

- `prepare_project_sandbox(...)` does not copy ignored local/generated roots.
- `capture_tree_manifest(...)` does not hash/report ignored local/generated
  roots.
- Normal workspace files and `.cerebro/` remain included.
- The ignore policy is explicit, deterministic, and shared between copy and
  manifest capture.
- Focused sandbox tests prove ignored roots are omitted and ordinary files still
  clone/manifest.
- `tests.test_architecture` remains green.
- Full AGENTS-equivalent gate remains green.

## Stop Conditions

- Any need to change `core/verification_runtime.py` command semantics.
- Any test shows `.cerebro/` must be ignored to pass.
- Any legitimate checked-in test depends on ignored generated roots being copied
  into the verification sandbox.
- Any gate failure not directly explained by this slice.

## Closure Evidence

Result: consumed on 2026-04-25.

Implemented:

- `core/command_sandbox.py` now has a shared deterministic ignore policy for
  sandbox copy and manifest capture.
- Ignored local/generated roots include `_local/`, `.git/`, `venv/`, `.tmp*/`,
  caches, and build artifacts.
- `.cerebro/` remains included in sandbox clones and manifests.
- `prepare_project_sandbox(...)` and `capture_tree_manifest(...)` use the same
  ignore predicate, avoiding copy/hash divergence.

Validation:

- Focused sandbox/verification tests: `14/0`.
- Architecture gate: `51/0`.
- Full AGENTS-equivalent gate after implementation: `928/0/0/6`.

Non-authorization preserved: no command execution semantics, approval policy,
verification result semantics, `core/schema.py`, `cli/`, `extensions/`,
`.cerebro/`, or canonical state changed.
