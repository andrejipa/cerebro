from __future__ import annotations

from statistics import mean
from typing import Any

from .schema import compute_candidate_trigger, compute_trigger_score


def score_record(record: dict[str, Any]) -> dict[str, Any]:
    payload = dict(record)
    payload["trigger_score"] = compute_trigger_score(payload)
    payload["candidate_trigger"] = compute_candidate_trigger(payload)
    return payload


def aggregate_cost_metrics(records: list[dict[str, Any]]) -> dict[str, float]:
    if not records:
        return {
            "avg_minutes_spent": 0.0,
            "avg_extra_files_opened": 0.0,
            "avg_manual_search_rounds": 0.0,
        }
    return {
        "avg_minutes_spent": round(mean(record["operational_cost"]["minutes_spent"] for record in records), 4),
        "avg_extra_files_opened": round(mean(record["operational_cost"]["extra_files_opened"] for record in records), 4),
        "avg_manual_search_rounds": round(mean(record["operational_cost"]["manual_search_rounds"] for record in records), 4),
    }
