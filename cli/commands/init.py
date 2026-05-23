"""Implementation of the init command.

cerebro init
    Bootstrap a new project: state.json + runtime.db + AGENTS.md +
    docs/operations scaffold.  Fails if the project is already initialised
    (state.json exists) and suggests --repair-scaffold.

cerebro init --repair-scaffold
    Create only the missing scaffold artefacts without touching existing files.
    Idempotent: safe to run repeatedly.

Design rules (Phase 11):
  - Never create CLAUDE.md in a managed project.
  - AGENTS.md template is neutral and agent-agnostic (no Claude-mandatory language).
  - observation_center.toml authority_order starts with AGENTS.md.
  - Existing files are never overwritten.
"""

from __future__ import annotations

import datetime
from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from core.runtime_manager_store import RuntimeManagerStore
from core.state_store import StateStore, StateStoreError

# ---------------------------------------------------------------------------
# Templates
# ---------------------------------------------------------------------------

_AGENTS_MD_TEMPLATE = """\
# AGENTS.md — Agent Instructions

This file follows the [AGENTS.md open standard](https://agents.md) and is the
**universal instruction file** for all AI agents working in this project.
It is readable by Claude Code, OpenAI Codex, GitHub Copilot, Cursor, and any
compatible tool.

> If a `CLAUDE.md` file exists in this directory it is a **local supplement**
> for Claude Code only. It is **subordinate** to this file and is not required
> to operate this project.

## Task Queue

The canonical task queue lives in:

    docs/operations/observation_center.toml

Read it before any work. Status vocabulary: `open`, `waiting`, `blocked`, `resolved`.
Authority order: `AGENTS.md → active triggers → observation_center.toml → projections`.

Run `cerebro sync` to import the queue into the runtime database.
Run `cerebro status` to see current state.
Run `cerebro next` to see the next eligible task.

## Runtime State

Machine-managed — do not edit directly:

- `.cerebro/state.json`   — checkpoint state
- `.cerebro/runtime.db`   — execution runtime (SQLite, schema v15+)

## Projections (read-only, not authority)

- `docs/operations/SYSTEM_STATE.md`   — current system snapshot
- `docs/operations/OPPORTUNITY_MAP.md` — next-action summary

Projections describe state. The observation center and runtime.db are authoritative.

## Adding Work

Add `[[observations]]` entries to `docs/operations/observation_center.toml`.
Required fields: `id`, `title`, `status`, `kind`, `priority`, `boundary`,
`trigger`, `dependencies`, `dependencies_satisfied`, `next_action`, `done_when`.

## Architecture Conventions

Document project-specific conventions here.  Remove this section when empty.
"""

_OBSERVATION_CENTER_TEMPLATE = """\
[center]
version = 1
updated_at = "{updated_at}"
queue_authority = "machine-primary"
projection_role = "SYSTEM_STATE.md and OPPORTUNITY_MAP.md summarize the live queue, but observation_center.toml is the front-door source of truth for unresolved work."
authority_order = "AGENTS.md -> active triggers -> observation_center.toml -> SYSTEM_STATE.md -> OPPORTUNITY_MAP.md -> active plans -> code/tests"
selection_contract = "Select the highest-priority observation whose status is open, whose boundary is authorized, whose trigger requirements are satisfied, and whose dependencies are already resolved."
selection_order = "status=open first, then priority, then the current checked-in order."
reconciliation_rule = "If AGENTS.md, the active trigger, the observation center, and the markdown projections diverge, the round becomes docs-only reconciliation before any implementation slice."
single_flight = true
overlap_policy = "If a prior round is still in flight, wait instead of starting overlapping work."
idempotency_contract = "Each round may move at most one observation materially forward."
notify_once_blocked = true
history_policy = "Resolved observations are rotated to observation_center_archive.toml at each docs-only reconciliation round."

# Status vocabulary: open | waiting | blocked | resolved
# Kind vocabulary:   slice | checkpoint | blocker

[projections]
system_state = "Mirror the live queue mode, queue head, and gate summary after each real round."
opportunity_map = "Mirror the live next action and minimal human-facing rationale after each real round."
trigger_docs = "Keep any active trigger aligned with the current open slice and mandatory stop conditions."
"""

_SYSTEM_STATE_TEMPLATE = """\
# System State

## Current Snapshot — {date}

This file is a **projection**. The canonical source of truth is
`docs/operations/observation_center.toml` and `.cerebro/runtime.db`.

No observations have been resolved yet.  Add work items to
`docs/operations/observation_center.toml` and run `cerebro sync` to begin.
"""

_OPPORTUNITY_MAP_TEMPLATE = """\
# Opportunity Map

## Current Snapshot — {date}

This file is a **projection** summarising the next recommended actions.
The canonical source of truth is `docs/operations/observation_center.toml`.

**Next action:** Add observations to `docs/operations/observation_center.toml`
and run `cerebro sync`.
"""

# ---------------------------------------------------------------------------
# Scaffold helpers
# ---------------------------------------------------------------------------

def _today() -> str:
    return datetime.date.today().isoformat()


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _write_if_absent(path: Path, content: str) -> bool:
    """Write content to path only if it does not already exist. Returns True if created."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return True


def _build_scaffold(root: Path) -> dict[str, bool]:
    """Create all scaffold artefacts that are absent. Returns {label: created}."""
    ops = root / "docs" / "operations"
    date = _today()

    artefacts = {
        "AGENTS.md": (
            root / "AGENTS.md",
            _AGENTS_MD_TEMPLATE,
        ),
        "docs/operations/observation_center.toml": (
            ops / "observation_center.toml",
            _OBSERVATION_CENTER_TEMPLATE.format(updated_at=_now_iso()),
        ),
        "docs/operations/SYSTEM_STATE.md": (
            ops / "SYSTEM_STATE.md",
            _SYSTEM_STATE_TEMPLATE.format(date=date),
        ),
        "docs/operations/OPPORTUNITY_MAP.md": (
            ops / "OPPORTUNITY_MAP.md",
            _OPPORTUNITY_MAP_TEMPLATE.format(date=date),
        ),
    }

    results: dict[str, bool] = {}
    for label, (path, content) in artefacts.items():
        results[label] = _write_if_absent(path, content)
    return results


# ---------------------------------------------------------------------------
# Public command handler
# ---------------------------------------------------------------------------

def run_init(root: Path, args=None) -> int:
    repair = getattr(args, "repair_scaffold", False)
    store = StateStore(root)

    if repair:
        return _run_repair(root, store)
    return _run_fresh(root, store)


def _run_fresh(root: Path, store: StateStore) -> int:
    """Normal init: fail if already initialised, then create everything."""
    try:
        store.initialize()
    except StateStoreError as exc:
        if "already exists" in str(exc):
            print_fail([
                user_error(
                    "state_exists",
                    f"{exc} — run `cerebro init --repair-scaffold` to create only missing scaffold artefacts.",
                )
            ])
        else:
            print_fail([user_error("operation_failed", str(exc))])
        return 1

    # Initialise runtime.db
    rm_store = RuntimeManagerStore(root)
    rm_store.initialize_schema()

    # Build scaffold
    created = _build_scaffold(root)

    lines = [
        f"instance_created: {store.cerebro_dir}",
        f"state_path: {store.state_path}",
        f"runtime_db: {rm_store.db_path}",
    ]
    for label, was_created in created.items():
        lines.append(f"{'created' if was_created else 'kept'}: {label}")
    lines.append("next_step: edit docs/operations/observation_center.toml then run `cerebro sync`")

    print_ok(lines)
    return 0


def _run_repair(root: Path, store: StateStore) -> int:
    """Repair mode: create only missing scaffold artefacts, never overwrite."""
    # runtime.db — create if absent
    rm_store = RuntimeManagerStore(root)
    if not rm_store.db_path.exists():
        rm_store.initialize_schema()
        db_status = "created"
    else:
        db_status = "kept"

    # Scaffold docs
    created = _build_scaffold(root)

    lines = [f"runtime_db: {db_status}"]
    for label, was_created in created.items():
        lines.append(f"{'created' if was_created else 'kept'}: {label}")
    lines.append("repair complete — existing files were not modified")

    print_ok(lines)
    return 0
