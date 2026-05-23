from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from .logger import load_registry
from .scorer import aggregate_cost_metrics, score_record


def _aggregate_group(records: list[dict[str, Any]], key: str) -> dict[str, dict[str, Any]]:
    grouped: defaultdict[str, list[dict[str, Any]]] = defaultdict(list)
    for record in records:
        grouped[str(record[key])].append(record)

    summary: dict[str, dict[str, Any]] = {}
    for group_key, group_records in sorted(grouped.items()):
        summary[group_key] = {
            "count": len(group_records),
            "candidate_trigger_count": sum(1 for record in group_records if record["candidate_trigger"]),
            "repeat_count_total": sum(record["repeat_count"] for record in group_records),
            "costs": aggregate_cost_metrics(group_records),
        }
    return summary


def _build_analysis_payload(records: list[dict[str, Any]], *, schema_version: str) -> dict[str, Any]:
    by_project = _aggregate_group(records, "project_context")
    by_failure_mode = _aggregate_group(records, "failure_mode")
    by_confidence = _aggregate_group(records, "confidence")

    top_repeaters = sorted(
        records,
        key=lambda record: (
            record["candidate_trigger"],
            record["repeat_count"],
            record["trigger_score"],
            record["timestamp"],
        ),
        reverse=True,
    )

    return {
        "schema_version": schema_version,
        "authority": "derived-observability-only",
        "non_authoritative": True,
        "records": records,
        "totals": {
            "count": len(records),
            "candidate_trigger_count": sum(1 for record in records if record["candidate_trigger"]),
            "costs": aggregate_cost_metrics(records),
        },
        "by_project_context": by_project,
        "by_failure_mode": by_failure_mode,
        "by_confidence": by_confidence,
        "candidate_triggers": [record for record in top_repeaters if record["candidate_trigger"]],
        "top_repeaters": top_repeaters[:10],
    }


def build_analysis(path: str | Path | None = None) -> dict[str, Any]:
    registry = load_registry(path)
    records = [score_record(record) for record in registry["unmet_use_case"]]
    return _build_analysis_payload(records, schema_version=registry["schema_version"])
