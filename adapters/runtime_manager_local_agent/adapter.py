"""LocalAgentAdapter -- wraps RuntimeManagerStore for safe agent access.

Invariants enforced by this layer (cannot be bypassed by callers):
  - No raw SQLite: every state change goes through RuntimeManagerStore public API.
  - No argv free-form: only registered command IDs reach the store.
  - Rate limits checked before every store call.
  - Mutations require an active lease held by this adapter session.
  - Trace / metrics / replay results are never used as execution permission here.
  - AdapterMetrics tracks calls; it is diagnostic, not authority.
"""
from __future__ import annotations

import datetime
from typing import Any

from adapters.runtime_manager_local_agent.agent_context import AgentContext
from adapters.runtime_manager_local_agent.metrics import AdapterMetrics, AdapterMetricsAccumulator
from adapters.runtime_manager_local_agent.rate_limiter import LocalRateLimiter
from core.runtime_manager_store import (
    AcquiredLease,
    ApprovalRecord,
    CommandEligibilityResult,
    CommandRunResult,
    ManagedValidation,
    RuntimeManagerMetrics,
    RuntimeManagerStatus,
    RuntimeObservation,
    RuntimeReplayResult,
    RuntimeTrace,
    RuntimeManagerStore,
)

_MUTATIONS_REQUIRING_LEASE = frozenset(
    {
        "run",
        "record_approval",
        "revoke_approval",
        "raise_stop_condition",
        "resolve_stop_condition",
        "record_validation",
    }
)


class AdapterError(RuntimeError):
    """Raised by LocalAgentAdapter on policy violations.

    Callers must handle this; it is not a store error.
    """

    def __init__(self, message: str, *, code: str = "adapter_error") -> None:
        super().__init__(message)
        self.code = code


def _utc_now() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class LocalAgentAdapter:
    """Safe adapter that wraps RuntimeManagerStore for agent callers.

    Usage::

        ctx = AgentContext(agent_id="ci-bot-1", agent_role="runner", session_id="s-abc")
        adapter = LocalAgentAdapter(store, ctx)
        adapter.acquire_lease("obs-1", ttl_seconds=300)
        result = adapter.run_command("cmd-deploy", observation_id="obs-1")

    All public methods:
        status, next_observation, acquire_lease, release_lease, heartbeat_lease,
        check_command, record_approval, revoke_approval, run_command,
        raise_stop_condition, resolve_stop_condition, record_validation,
        list_traces, read_trace, export_trace, read_metrics, read_adapter_metrics,
        replay_scenario.
    """

    def __init__(
        self,
        store: RuntimeManagerStore,
        context: AgentContext,
        rate_limiter: LocalRateLimiter | None = None,
    ) -> None:
        self._store = store
        self._ctx = context
        self._rl = rate_limiter if rate_limiter is not None else LocalRateLimiter()
        self._metrics = AdapterMetricsAccumulator()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _check_rate(self, operation: str) -> None:
        allowed, retry_after = self._rl.check(self._ctx.agent_id, operation)
        is_mut = self._rl.is_mutate_op(operation)
        if not allowed:
            self._metrics.record_call(blocked=True, rate_limited=True, is_mutation=is_mut)
            raise AdapterError(
                f"rate limit exceeded for agent={self._ctx.agent_id!r} operation={operation!r}; "
                f"retry after {retry_after}s",
                code="rate_limited",
            )

    def _require_lease(self, observation_id: str, operation: str) -> None:
        owner = self._ctx.lease_owner
        leases = self._store.list_leases(observation_id=observation_id)
        active = [
            lz for lz in leases if lz.status == "active" and lz.owner == owner
        ]
        if not active:
            self._metrics.record_call(blocked=True, is_mutation=True)
            raise AdapterError(
                f"adapter requires an active lease for observation={observation_id!r} "
                f"to perform operation={operation!r} as agent={self._ctx.agent_id!r}",
                code="lease_required",
            )

    def _active_agent_leases(self) -> int:
        owner = self._ctx.lease_owner
        all_leases = self._store.list_leases()
        return sum(1 for lz in all_leases if lz.status == "active" and lz.owner == owner)

    # ------------------------------------------------------------------
    # Read operations (no lease required)
    # ------------------------------------------------------------------

    def status(self) -> RuntimeManagerStatus:
        self._check_rate("status")
        self._metrics.record_call()
        return self._store.read_status()

    def next_observation(self) -> RuntimeObservation | None:
        self._check_rate("next")
        self._metrics.record_call()
        return self._store.read_next()

    def check_command(self, command_id: str) -> CommandEligibilityResult:
        self._check_rate("check")
        self._metrics.record_call()
        return self._store.check_command_eligibility(command_id)

    def list_traces(
        self,
        operation: str = "",
        subject_id: str = "",
        limit: int = 50,
    ) -> tuple[RuntimeTrace, ...]:
        self._check_rate("list_traces")
        self._metrics.record_call()
        return self._store.list_traces(operation=operation, subject_id=subject_id, limit=limit)

    def read_trace(self, trace_id: str) -> RuntimeTrace | None:
        self._check_rate("read_trace")
        self._metrics.record_call()
        return self._store.read_trace(trace_id)

    def export_trace(self, trace_id: str, format: str = "json") -> str:
        self._check_rate("export_trace")
        self._metrics.record_call()
        return self._store.export_trace(trace_id, format=format)

    def read_metrics(self) -> RuntimeManagerMetrics:
        self._check_rate("read_metrics")
        self._metrics.record_call()
        return self._store.read_metrics()

    def read_adapter_metrics(self) -> AdapterMetrics:
        return self._metrics.snapshot(
            generated_at=_utc_now(),
            active_agent_leases=self._active_agent_leases(),
        )

    def replay_scenario(self, scenario_path: str) -> RuntimeReplayResult:
        self._check_rate("replay")
        self._metrics.record_call()
        result = self._store.replay_scenario(scenario_path)
        return result

    # ------------------------------------------------------------------
    # Lease management (acquiring doesn't need existing lease; others do)
    # ------------------------------------------------------------------

    def acquire_lease(
        self, observation_id: str, *, ttl_seconds: int = 300, reason: str = ""
    ) -> AcquiredLease:
        self._check_rate("acquire_lease")
        self._metrics.record_call(is_mutation=True)
        owner = self._ctx.lease_owner
        return self._store.acquire_lease(
            observation_id, owner, ttl_seconds=ttl_seconds, reason=reason
        )

    def release_lease(self, lease_id: str, observation_id: str) -> bool:
        self._check_rate("release_lease")
        owner = self._ctx.lease_owner
        leases = self._store.list_leases(observation_id=observation_id)
        matching = [lz for lz in leases if lz.lease_id == lease_id and lz.owner == owner]
        if not matching:
            self._metrics.record_call(blocked=True, is_mutation=True)
            raise AdapterError(
                f"release_lease: lease_id={lease_id!r} not found or owner mismatch "
                f"for agent={self._ctx.agent_id!r}",
                code="lease_owner_mismatch",
            )
        self._metrics.record_call(is_mutation=True)
        return self._store.release_lease(lease_id, owner)

    def heartbeat_lease(self, lease_id: str, observation_id: str, *, extend_seconds: int = 300) -> bool:
        self._check_rate("heartbeat_lease")
        owner = self._ctx.lease_owner
        leases = self._store.list_leases(observation_id=observation_id)
        matching = [lz for lz in leases if lz.lease_id == lease_id and lz.owner == owner]
        if not matching:
            self._metrics.record_call(blocked=True, is_mutation=True)
            raise AdapterError(
                f"heartbeat_lease: lease_id={lease_id!r} not found or owner mismatch "
                f"for agent={self._ctx.agent_id!r}",
                code="lease_owner_mismatch",
            )
        self._metrics.record_call(is_mutation=True)
        return self._store.heartbeat_lease(lease_id, owner, extend_seconds=extend_seconds)

    # ------------------------------------------------------------------
    # Mutating operations (lease required for target observation)
    # ------------------------------------------------------------------

    def run_command(self, command_id: str, *, observation_id: str) -> CommandRunResult:
        self._check_rate("run")
        self._require_lease(observation_id, "run")
        self._metrics.record_call(is_mutation=True)
        return self._store.run_command(command_id)

    def record_approval(
        self,
        command_id: str,
        subject_id: str,
        *,
        scope: str = "single-use",
        expires_at: str = "",
    ) -> ApprovalRecord:
        self._check_rate("record_approval")
        self._require_lease(subject_id, "record_approval")
        self._metrics.record_call(is_mutation=True)
        actor = self._ctx.sanitized_label()
        return self._store.record_approval(command_id, subject_id, actor, scope=scope, expires_at=expires_at)

    def revoke_approval(self, approval_id: str, *, observation_id: str) -> bool:
        self._check_rate("revoke_approval")
        self._require_lease(observation_id, "revoke_approval")
        self._metrics.record_call(is_mutation=True)
        return self._store.revoke_approval(approval_id)

    def raise_stop_condition(self, observation_id: str, *, reason: str) -> Any:
        self._check_rate("raise_stop_condition")
        self._require_lease(observation_id, "raise_stop_condition")
        self._metrics.record_call(is_mutation=True)
        return self._store.raise_stop_condition(observation_id, reason=reason)

    def resolve_stop_condition(self, stop_condition_id: str, *, observation_id: str) -> bool:
        self._check_rate("resolve_stop_condition")
        self._require_lease(observation_id, "resolve_stop_condition")
        self._metrics.record_call(is_mutation=True)
        return self._store.resolve_stop_condition(stop_condition_id)

    def record_validation(
        self,
        validation_id: str,
        subject_id: str,
        *,
        status: str,
        reason: str,
        fresh_until: str = "",
        command_id: str = "",
    ) -> ManagedValidation:
        self._check_rate("record_validation")
        self._require_lease(subject_id, "record_validation")
        self._metrics.record_call(is_mutation=True)
        return self._store.record_validation(
            validation_id, subject_id,
            status=status, reason=reason,
            fresh_until=fresh_until, command_id=command_id,
        )
