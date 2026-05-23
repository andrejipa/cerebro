"""Shared plan-input helpers for legacy task flags and domain input adaptation."""

from __future__ import annotations

from pathlib import Path

from core.domain_input_adapter import DomainInputAdapterError, adapt_domain_input
from core.state_store import StateStoreError


def load_plan_input(root: Path, args) -> dict:
    """Return one normalized plan-input payload for the plan command."""
    has_text_input = bool(getattr(args, "input_text", "") or getattr(args, "input_file", ""))
    has_legacy_tasks = bool(getattr(args, "task", []) or getattr(args, "verify_command", []))

    if has_text_input and has_legacy_tasks:
        raise DomainInputAdapterError("use either --task/--verify-command or --input-text/--input-file, not both")
    if getattr(args, "input_text", "") and getattr(args, "input_file", ""):
        raise DomainInputAdapterError("use either --input-text or --input-file, not both")

    if has_text_input:
        raw_text = _read_domain_input_text(root, args)
        adapted = adapt_domain_input(raw_text, input_kind=getattr(args, "input_kind", "auto"))
        goal_override = getattr(args, "goal", "") or ""
        summary_override = getattr(args, "summary", "") or ""
        goal = goal_override.strip() or adapted["goal"]
        summary = summary_override.strip() or adapted["summary"]
        return {
            "goal": goal,
            "summary": summary,
            "tasks": adapted["tasks"],
            "verify_commands": adapted["verify_commands"],
            "input_kind": adapted["input_kind"],
        }

    goal = getattr(args, "goal", "") or ""
    summary = getattr(args, "summary", "") or ""
    if not goal.strip():
        raise StateStoreError("goal is required unless it is derived from domain input")
    if not summary.strip():
        raise StateStoreError("summary is required unless it is derived from domain input")
    return {
        "goal": goal,
        "summary": summary,
        "tasks": None,
        "verify_commands": list(getattr(args, "verify_command", []) or []),
        "input_kind": "legacy",
    }


def _read_domain_input_text(root: Path, args) -> str:
    raw_text = getattr(args, "input_text", "")
    if raw_text:
        return raw_text

    input_file = getattr(args, "input_file", "")
    if not input_file:
        raise DomainInputAdapterError("domain input text or file is required")
    target = Path(input_file)
    if not target.is_absolute():
        target = root / target
    try:
        return target.read_text(encoding="utf-8")
    except OSError as exc:
        raise DomainInputAdapterError(f"failed to read domain input file: {target}") from exc
