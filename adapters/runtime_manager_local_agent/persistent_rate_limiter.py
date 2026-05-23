"""PersistentRateLimiter -- store-backed fixed-window rate limiter.

Wraps RuntimeManagerStore.check_and_increment_rate_limit().  Survives
process restarts; window is per-minute (not sliding).  LocalRateLimiter
is retained for tests that need clock injection.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime_manager_store import RuntimeManagerStore, RateLimitResult


class PersistentRateLimiter:
    """Fixed-window rate limiter backed by the SQLite store.

    Each call delegates to the store, which atomically upserts the bucket
    for ``agent_id:operation:current_minute`` and returns whether the call
    is within the allowed limit.
    """

    def __init__(self, store: "RuntimeManagerStore") -> None:
        self._store = store

    def check(self, agent_id: str, operation: str) -> tuple[bool, int]:
        """Return (allowed, retry_after_seconds)."""
        result: RateLimitResult = self._store.check_and_increment_rate_limit(
            agent_id, operation
        )
        return result.allowed, result.retry_after_seconds
