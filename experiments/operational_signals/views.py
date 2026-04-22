from __future__ import annotations

import json
from typing import Any


def filter_records(
    records: list[dict[str, Any]],
    *,
    project: str | None = None,
    failure_mode: str | None = None,
    candidate_only: bool = False,
) -> list[dict[str, Any]]:
    filtered = records
    if project:
        filtered = [record for record in filtered if record["project_context"] == project]
    if failure_mode:
        filtered = [record for record in filtered if record["failure_mode"] == failure_mode]
    if candidate_only:
        filtered = [record for record in filtered if record["candidate_trigger"]]
    return sorted(filtered, key=lambda record: (record["timestamp"], record["id"]))


def render_json(payload: dict[str, Any]) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=True, sort_keys=True)


def render_markdown(payload: dict[str, Any]) -> str:
    lines = [
        "# Operational Insufficiency Signals",
        "",
        "- authority: derived-observability-only",
        "- non-authoritative: true",
        "- opt-in: true",
        "- observability-only: true",
        "",
        "## Totals",
        "",
        f"- records: `{payload['totals']['count']}`",
        f"- candidate triggers: `{payload['totals']['candidate_trigger_count']}`",
        f"- avg minutes spent: `{payload['totals']['costs']['avg_minutes_spent']:.2f}`",
        f"- avg extra files opened: `{payload['totals']['costs']['avg_extra_files_opened']:.2f}`",
        f"- avg manual search rounds: `{payload['totals']['costs']['avg_manual_search_rounds']:.2f}`",
        "",
        "## Top Failure Modes",
        "",
    ]
    for failure_mode, group in payload["by_failure_mode"].items():
        lines.append(
            f"- `{failure_mode}`: `{group['count']}` records, "
            f"`{group['candidate_trigger_count']}` candidate triggers"
        )
    lines.extend(["", "## Candidate Triggers", ""])
    if not payload["candidate_triggers"]:
        lines.append("- none")
    else:
        for record in payload["candidate_triggers"]:
            lines.append(
                f"- `{record['id']}` | `{record['project_context']}` | "
                f"`{record['failure_mode']}` | trigger_score `{record['trigger_score']:.4f}`"
            )
    return "\n".join(lines) + "\n"
