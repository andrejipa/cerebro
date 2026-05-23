"""Local pilot adapter for RuntimeManagerStore.

Entry points:
    LocalAgentAdapter      -- main adapter class.
    AgentContext           -- immutable agent identity.
    AdapterMetrics         -- read-only diagnostic counters.
    AdapterError           -- raised on policy violations (lease missing, rate limit, etc.).
    LocalRateLimiter       -- injectable sliding-window rate limiter (for tests).
    PersistentRateLimiter  -- store-backed fixed-window rate limiter (for production).

Invariants (cannot be overridden by callers):
    - No raw SQLite; every state change goes through RuntimeManagerStore public API.
    - No argv free-form; only registered command IDs reach the store.
    - Trace / metrics / replay results are never used as execution permission.
    - Mutations require an active lease held by this adapter instance.
    - Rate limits are enforced before calling the store.
"""
from adapters.runtime_manager_local_agent.agent_context import AgentContext
from adapters.runtime_manager_local_agent.metrics import AdapterMetrics
from adapters.runtime_manager_local_agent.rate_limiter import LocalRateLimiter
from adapters.runtime_manager_local_agent.persistent_rate_limiter import PersistentRateLimiter
from adapters.runtime_manager_local_agent.adapter import AdapterError, LocalAgentAdapter

__all__ = [
    "AgentContext",
    "AdapterMetrics",
    "LocalRateLimiter",
    "PersistentRateLimiter",
    "AdapterError",
    "LocalAgentAdapter",
]
