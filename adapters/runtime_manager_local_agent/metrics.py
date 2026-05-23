"""AdapterMetrics -- diagnostic counters for the local agent adapter.

These are advisory only; they are never used as execution permission.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class AdapterMetrics:
    """Read-only snapshot of adapter-level diagnostic counters."""

    generated_at: str
    adapter_calls_total: int
    adapter_calls_blocked: int
    adapter_rate_limited: int
    adapter_mutations_total: int
    adapter_permission_laundering_blocked: int
    active_agent_leases: int
    metrics_is_not_permission: bool = True
    authority: str = "adapter diagnostic counters only; not execution permission"


class AdapterMetricsAccumulator:
    """Mutable counter set; produces an AdapterMetrics snapshot on demand."""

    def __init__(self) -> None:
        self.adapter_calls_total: int = 0
        self.adapter_calls_blocked: int = 0
        self.adapter_rate_limited: int = 0
        self.adapter_mutations_total: int = 0
        self.adapter_permission_laundering_blocked: int = 0

    def record_call(self, *, blocked: bool = False, rate_limited: bool = False, is_mutation: bool = False) -> None:
        self.adapter_calls_total += 1
        if blocked:
            self.adapter_calls_blocked += 1
        if rate_limited:
            self.adapter_rate_limited += 1
        if is_mutation and not blocked and not rate_limited:
            self.adapter_mutations_total += 1

    def record_permission_laundering_blocked(self) -> None:
        self.adapter_calls_blocked += 1
        self.adapter_permission_laundering_blocked += 1

    def snapshot(self, generated_at: str, active_agent_leases: int) -> AdapterMetrics:
        return AdapterMetrics(
            generated_at=generated_at,
            adapter_calls_total=self.adapter_calls_total,
            adapter_calls_blocked=self.adapter_calls_blocked,
            adapter_rate_limited=self.adapter_rate_limited,
            adapter_mutations_total=self.adapter_mutations_total,
            adapter_permission_laundering_blocked=self.adapter_permission_laundering_blocked,
            active_agent_leases=active_agent_leases,
        )
