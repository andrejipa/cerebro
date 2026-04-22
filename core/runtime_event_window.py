"""Helpers for slicing runtime event history to the current plan window."""

from __future__ import annotations


def events_since_latest_plan_update(events: tuple[dict, ...] | list[dict]) -> tuple[dict, ...]:
    """Return only the suffix of events that belongs to the latest plan generation."""
    if not isinstance(events, (tuple, list)):
        return ()

    normalized = tuple(event for event in events if isinstance(event, dict))
    for index in range(len(normalized) - 1, -1, -1):
        if normalized[index].get("event") == "plan_updated":
            return normalized[index:]
    return normalized
