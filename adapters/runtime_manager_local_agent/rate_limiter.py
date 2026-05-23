"""LocalRateLimiter -- deterministic sliding-window rate limiter.

Limits are per (agent_id, operation).  The clock is injectable for testing.
"""
from __future__ import annotations

import time
from collections import deque
from typing import Callable

READ_LIMIT = 60
MUTATE_LIMIT = 10
WINDOW_SECONDS = 60.0

MUTATE_OPS: frozenset[str] = frozenset(
    {
        "run",
        "acquire_lease",
        "release_lease",
        "heartbeat_lease",
        "record_approval",
        "revoke_approval",
        "raise_stop_condition",
        "resolve_stop_condition",
        "record_validation",
        "rollback",
        "sync",
    }
)


class LocalRateLimiter:
    """In-memory sliding-window rate limiter.

    Each (agent_id, operation) pair has its own deque of timestamps.
    Exceeding the limit returns (False, retry_after_seconds).
    Staying within returns (True, 0).
    """

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock: Callable[[], float] = clock if clock is not None else time.monotonic
        self._windows: dict[tuple[str, str], deque[float]] = {}

    def check(self, agent_id: str, operation: str) -> tuple[bool, int]:
        limit = MUTATE_LIMIT if operation in MUTATE_OPS else READ_LIMIT
        key = (agent_id, operation)
        now = self._clock()
        window = self._windows.setdefault(key, deque())
        cutoff = now - WINDOW_SECONDS
        while window and window[0] < cutoff:
            window.popleft()
        if len(window) >= limit:
            retry_after = max(1, int(WINDOW_SECONDS - (now - window[0])) + 1)
            return False, retry_after
        window.append(now)
        return True, 0

    def is_mutate_op(self, operation: str) -> bool:
        return operation in MUTATE_OPS

    def reset(self, agent_id: str | None = None) -> None:
        """Clear all windows (or only for one agent_id). Used in tests."""
        if agent_id is None:
            self._windows.clear()
        else:
            keys_to_delete = [k for k in self._windows if k[0] == agent_id]
            for k in keys_to_delete:
                del self._windows[k]
