"""Tests for the LocalAgentAdapter (Phase 6).

Coverage:
    - AgentContext validation
    - LocalRateLimiter sliding window
    - LocalAgentAdapter read operations (no lease required)
    - LocalAgentAdapter lease lifecycle (acquire/release/heartbeat)
    - LocalAgentAdapter mutation enforcement (lease required)
    - LocalAgentAdapter lease owner enforcement
    - AdapterMetrics counters
    - AdapterError codes
    - eval_adapter_safety invariant evaluators
"""
from __future__ import annotations

import sys
import tempfile
import time
import unittest
from pathlib import Path

from adapters.runtime_manager_local_agent.agent_context import AgentContext
from adapters.runtime_manager_local_agent.rate_limiter import LocalRateLimiter, MUTATE_OPS
from adapters.runtime_manager_local_agent.metrics import AdapterMetrics, AdapterMetricsAccumulator
from adapters.runtime_manager_local_agent.adapter import AdapterError, LocalAgentAdapter
from experiments.runtime_manager_evals.eval_adapter_safety import (
    eval_adapter_no_direct_sql,
    eval_adapter_no_argv_acceptance,
    eval_adapter_no_external_sdk,
    eval_replay_result_is_not_permission,
    eval_metrics_result_is_not_permission,
    eval_lease_ownership_enforced,
    eval_rate_limit_blocks_abuse,
    eval_no_secret_in_trace_export,
    eval_approval_requires_fingerprint,
    eval_mutation_without_lease_blocked,
    eval_adapter_safety,
)
from core.runtime_manager_store import RuntimeManagerStore


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

ALWAYS_EXIT_0 = [sys.executable, "-c", "import sys; sys.exit(0)"]
ALWAYS_EXIT_7 = [sys.executable, "-c", "import sys; sys.exit(7)"]

def _setup_store(tmp_dir: Path) -> RuntimeManagerStore:
    """Create store with one observation and one command embedded in obs center TOML."""
    argv_json = f'["{sys.executable.replace(chr(92), "/")}"]'
    path_scope = str(tmp_dir).replace("\\", "/")
    obs_toml = f"""[center]
version = 1
updated_at = "2026-05-08T00:00:00Z"
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-agent"
title = "Agent test observation"
status = "open"
kind = "slice"
priority = "high"
boundary = "test"
trigger = "none"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"
auto_continuation = false

[[command_registry]]
id = "cmd-run"
argv_prefix = {argv_json}
path_scope = "{path_scope}"
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
"""
    obs_path = tmp_dir / "obs.toml"
    obs_path.write_text(obs_toml, encoding="utf-8")
    store = RuntimeManagerStore(tmp_dir)
    store.sync_observation_center(obs_path)
    return store


def _make_ctx(
    agent_id: str = "agent-01",
    agent_role: str = "runner",
    session_id: str = "sess-abc",
) -> AgentContext:
    return AgentContext(agent_id=agent_id, agent_role=agent_role, session_id=session_id)


# ---------------------------------------------------------------------------
# AgentContext tests
# ---------------------------------------------------------------------------


class AgentContextTests(unittest.TestCase):
    def test_valid_context_created(self) -> None:
        ctx = AgentContext(agent_id="bot-1", agent_role="runner", session_id="s-001")
        self.assertEqual(ctx.agent_id, "bot-1")
        self.assertEqual(ctx.agent_role, "runner")
        self.assertEqual(ctx.session_id, "s-001")

    def test_lease_owner_derived(self) -> None:
        ctx = AgentContext(agent_id="bot-1", agent_role="runner", session_id="s-001")
        self.assertEqual(ctx.lease_owner, "adapter:bot-1:s-001")

    def test_sanitized_label_contains_agent_id(self) -> None:
        ctx = AgentContext(agent_id="bot-1", agent_role="runner", session_id="s-001")
        label = ctx.sanitized_label()
        self.assertIn("bot-1", label)
        self.assertIn("runner", label)

    def test_sanitized_label_truncates_session(self) -> None:
        ctx = AgentContext(agent_id="bot-1", agent_role="runner", session_id="s-001-longvalue")
        label = ctx.sanitized_label()
        self.assertNotIn("s-001-longvalue", label)

    def test_invalid_agent_id_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentContext(agent_id="bad agent!", agent_role="runner", session_id="s-001")

    def test_empty_agent_role_rejected(self) -> None:
        with self.assertRaises(ValueError):
            AgentContext(agent_id="bot-1", agent_role="", session_id="s-001")

    def test_agent_id_with_dots_and_colons_valid(self) -> None:
        ctx = AgentContext(agent_id="ci.bot:v1", agent_role="runner", session_id="s-001")
        self.assertEqual(ctx.agent_id, "ci.bot:v1")


# ---------------------------------------------------------------------------
# LocalRateLimiter tests
# ---------------------------------------------------------------------------


class LocalRateLimiterTests(unittest.TestCase):
    def test_first_call_allowed(self) -> None:
        rl = LocalRateLimiter()
        allowed, retry = rl.check("agent-1", "status")
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)

    def test_mutate_limit_enforced(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        rl = LocalRateLimiter(clock=clock)
        for i in range(10):
            allowed, _ = rl.check("agent-1", "run")
            self.assertTrue(allowed, f"call {i} should be allowed")
        allowed, retry = rl.check("agent-1", "run")
        self.assertFalse(allowed)
        self.assertGreater(retry, 0)

    def test_read_limit_higher_than_mutate(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        rl = LocalRateLimiter(clock=clock)
        for i in range(60):
            allowed, _ = rl.check("agent-1", "status")
            self.assertTrue(allowed, f"read call {i} should be allowed")
        allowed, _ = rl.check("agent-1", "status")
        self.assertFalse(allowed)

    def test_different_agents_independent(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        rl = LocalRateLimiter(clock=clock)
        for _ in range(10):
            rl.check("agent-1", "run")
        rl.check("agent-1", "run")  # blocked for agent-1
        # agent-2 should still be fine
        allowed, _ = rl.check("agent-2", "run")
        self.assertTrue(allowed)

    def test_window_slides(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        rl = LocalRateLimiter(clock=clock)
        for _ in range(10):
            rl.check("agent-1", "run")
        t[0] = 61.0  # advance past window
        allowed, retry = rl.check("agent-1", "run")
        self.assertTrue(allowed)
        self.assertEqual(retry, 0)

    def test_is_mutate_op_correct(self) -> None:
        rl = LocalRateLimiter()
        self.assertTrue(rl.is_mutate_op("run"))
        self.assertTrue(rl.is_mutate_op("acquire_lease"))
        self.assertFalse(rl.is_mutate_op("status"))
        self.assertFalse(rl.is_mutate_op("list_traces"))

    def test_reset_clears_windows(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        rl = LocalRateLimiter(clock=clock)
        for _ in range(10):
            rl.check("agent-1", "run")
        rl.reset("agent-1")
        allowed, _ = rl.check("agent-1", "run")
        self.assertTrue(allowed)


# ---------------------------------------------------------------------------
# AdapterMetrics tests
# ---------------------------------------------------------------------------


class AdapterMetricsTests(unittest.TestCase):
    def test_initial_counters_zero(self) -> None:
        acc = AdapterMetricsAccumulator()
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_calls_total, 0)
        self.assertEqual(snap.adapter_mutations_total, 0)
        self.assertTrue(snap.metrics_is_not_permission)

    def test_record_call_increments_total(self) -> None:
        acc = AdapterMetricsAccumulator()
        acc.record_call()
        acc.record_call()
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_calls_total, 2)

    def test_blocked_call_increments_blocked(self) -> None:
        acc = AdapterMetricsAccumulator()
        acc.record_call(blocked=True)
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_calls_blocked, 1)
        self.assertEqual(snap.adapter_mutations_total, 0)

    def test_mutation_call_increments_mutations(self) -> None:
        acc = AdapterMetricsAccumulator()
        acc.record_call(is_mutation=True)
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_mutations_total, 1)

    def test_rate_limited_increments_rate_limited(self) -> None:
        acc = AdapterMetricsAccumulator()
        acc.record_call(blocked=True, rate_limited=True)
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_rate_limited, 1)

    def test_permission_laundering_blocked(self) -> None:
        acc = AdapterMetricsAccumulator()
        acc.record_permission_laundering_blocked()
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertEqual(snap.adapter_permission_laundering_blocked, 1)
        self.assertEqual(snap.adapter_calls_blocked, 1)

    def test_active_agent_leases_in_snapshot(self) -> None:
        acc = AdapterMetricsAccumulator()
        snap = acc.snapshot("2026-05-08T00:00:00Z", 3)
        self.assertEqual(snap.active_agent_leases, 3)

    def test_authority_field_present(self) -> None:
        acc = AdapterMetricsAccumulator()
        snap = acc.snapshot("2026-05-08T00:00:00Z", 0)
        self.assertIn("not", snap.authority)
        self.assertIn("permission", snap.authority)


# ---------------------------------------------------------------------------
# LocalAgentAdapter read operation tests
# ---------------------------------------------------------------------------


class AdapterReadOpsTests(unittest.TestCase):
    def test_status_returns_runtime_status(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            status = adapter.status()
            self.assertIsNotNone(status)

    def test_next_observation_returns_observation_or_none(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            obs = adapter.next_observation()
            # obs-agent is in the queue, so should return something
            self.assertIsNotNone(obs)

    def test_check_command_returns_eligibility(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            result = adapter.check_command("cmd-run")
            self.assertIsNotNone(result)
            self.assertIsInstance(result.eligible, bool)

    def test_read_metrics_returns_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            metrics = adapter.read_metrics()
            self.assertIsNotNone(metrics)
            self.assertIsInstance(metrics.runs_total, int)

    def test_read_adapter_metrics_initial_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            am = adapter.read_adapter_metrics()
            self.assertIsInstance(am, AdapterMetrics)
            self.assertTrue(am.metrics_is_not_permission)
            self.assertEqual(am.adapter_calls_total, 0)

    def test_read_metrics_increments_adapter_calls(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            adapter.read_metrics()
            am = adapter.read_adapter_metrics()
            self.assertEqual(am.adapter_calls_total, 1)


# ---------------------------------------------------------------------------
# LocalAgentAdapter lease lifecycle tests
# ---------------------------------------------------------------------------


class AdapterLeaseTests(unittest.TestCase):
    def test_acquire_lease_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            lease = adapter.acquire_lease("obs-agent", ttl_seconds=300)
            self.assertEqual(lease.owner, ctx.lease_owner)

    def test_release_lease_succeeds_for_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            lease = adapter.acquire_lease("obs-agent", ttl_seconds=300)
            released = adapter.release_lease(lease.lease_id, "obs-agent")
            self.assertTrue(released)

    def test_release_lease_fails_for_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx1 = _make_ctx(agent_id="agent-1", session_id="sess-1")
            ctx2 = _make_ctx(agent_id="agent-2", session_id="sess-2")
            adapter1 = LocalAgentAdapter(store, ctx1)
            adapter2 = LocalAgentAdapter(store, ctx2)
            lease = adapter1.acquire_lease("obs-agent", ttl_seconds=300)
            with self.assertRaises(AdapterError) as cm:
                adapter2.release_lease(lease.lease_id, "obs-agent")
            self.assertEqual(cm.exception.code, "lease_owner_mismatch")

    def test_heartbeat_lease_fails_for_wrong_owner(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx1 = _make_ctx(agent_id="agent-1", session_id="sess-1")
            ctx2 = _make_ctx(agent_id="agent-2", session_id="sess-2")
            adapter1 = LocalAgentAdapter(store, ctx1)
            adapter2 = LocalAgentAdapter(store, ctx2)
            lease = adapter1.acquire_lease("obs-agent", ttl_seconds=300)
            with self.assertRaises(AdapterError) as cm:
                adapter2.heartbeat_lease(lease.lease_id, "obs-agent", extend_seconds=300)
            self.assertEqual(cm.exception.code, "lease_owner_mismatch")

    def test_active_agent_leases_counted(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            am_before = adapter.read_adapter_metrics()
            adapter.acquire_lease("obs-agent", ttl_seconds=300)
            am_after = adapter.read_adapter_metrics()
            self.assertEqual(am_before.active_agent_leases, 0)
            self.assertEqual(am_after.active_agent_leases, 1)


# ---------------------------------------------------------------------------
# LocalAgentAdapter mutation enforcement tests
# ---------------------------------------------------------------------------


class AdapterMutationEnforcementTests(unittest.TestCase):
    def test_run_without_lease_raises_adapter_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            with self.assertRaises(AdapterError) as cm:
                adapter.run_command("cmd-run", observation_id="obs-agent")
            self.assertEqual(cm.exception.code, "lease_required")

    def test_run_with_lease_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            adapter.acquire_lease("obs-agent", ttl_seconds=300)
            result = adapter.run_command("cmd-run", observation_id="obs-agent")
            self.assertIsNotNone(result)

    def test_record_approval_without_lease_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            with self.assertRaises(AdapterError) as cm:
                adapter.record_approval("cmd-run", "obs-agent")
            self.assertEqual(cm.exception.code, "lease_required")

    def test_record_approval_with_lease_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            adapter.acquire_lease("obs-agent", ttl_seconds=300)
            approval = adapter.record_approval("cmd-run", "obs-agent")
            self.assertIsNotNone(approval.approval_id)

    def test_raise_stop_condition_without_lease_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            with self.assertRaises(AdapterError) as cm:
                adapter.raise_stop_condition("obs-agent", reason="test stop")
            self.assertEqual(cm.exception.code, "lease_required")

    def test_raise_stop_condition_with_lease_succeeds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            adapter.acquire_lease("obs-agent", ttl_seconds=300)
            condition = adapter.raise_stop_condition("obs-agent", reason="test stop")
            self.assertIsNotNone(condition)

    def test_record_validation_without_lease_raises(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            with self.assertRaises(AdapterError) as cm:
                adapter.record_validation(
                    "val-1", "obs-agent", status="green", reason="ok",
                    fresh_until="2099-01-01T00:00:00Z",
                )
            self.assertEqual(cm.exception.code, "lease_required")

    def test_mutation_blocked_increments_blocked_counter(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            try:
                adapter.run_command("cmd-run", observation_id="obs-agent")
            except AdapterError:
                pass
            am = adapter.read_adapter_metrics()
            self.assertEqual(am.adapter_calls_blocked, 1)


# ---------------------------------------------------------------------------
# Rate limit enforcement via adapter
# ---------------------------------------------------------------------------


class AdapterRateLimitTests(unittest.TestCase):
    def test_rate_limit_blocks_excess_mutations(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            rl = LocalRateLimiter(clock=clock)
            adapter = LocalAgentAdapter(store, ctx, rate_limiter=rl)
            # exhaust the mutate limit for "acquire_lease"
            for _ in range(10):
                try:
                    adapter.acquire_lease("obs-agent", ttl_seconds=300)
                except Exception:
                    pass
                finally:
                    try:
                        leases = store.list_leases(observation_id="obs-agent")
                        for lz in leases:
                            if lz.status == "active":
                                store.release_lease(lz.lease_id, lz.owner)
                    except Exception:
                        pass
            with self.assertRaises(AdapterError) as cm:
                adapter.acquire_lease("obs-agent", ttl_seconds=300)
            self.assertEqual(cm.exception.code, "rate_limited")

    def test_rate_limited_increments_adapter_metrics(self) -> None:
        t = [0.0]

        def clock() -> float:
            return t[0]

        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            rl = LocalRateLimiter(clock=clock)
            adapter = LocalAgentAdapter(store, ctx, rate_limiter=rl)
            for _ in range(10):
                rl.check(ctx.agent_id, "acquire_lease")
            try:
                adapter.acquire_lease("obs-agent", ttl_seconds=300)
            except AdapterError:
                pass
            am = adapter.read_adapter_metrics()
            self.assertGreater(am.adapter_rate_limited, 0)


# ---------------------------------------------------------------------------
# Adapter module source safety (static checks)
# ---------------------------------------------------------------------------


class AdapterSourceSafetyTests(unittest.TestCase):
    @classmethod
    def _adapter_source(cls) -> str:
        p = Path(__file__).parent.parent / "adapters" / "runtime_manager_local_agent" / "adapter.py"
        return p.read_text(encoding="utf-8")

    def test_adapter_has_no_direct_sql(self) -> None:
        findings = eval_adapter_no_direct_sql(self._adapter_source())
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=f"Direct SQL found in adapter: {failed}")

    def test_adapter_has_no_argv(self) -> None:
        findings = eval_adapter_no_argv_acceptance(self._adapter_source())
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=f"argv reference found in adapter: {failed}")

    def test_adapter_has_no_external_sdk(self) -> None:
        findings = eval_adapter_no_external_sdk(self._adapter_source())
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=f"External SDK found in adapter: {failed}")


# ---------------------------------------------------------------------------
# eval_adapter_safety evaluator unit tests
# ---------------------------------------------------------------------------


class EvalAdapterSafetyTests(unittest.TestCase):
    def test_clean_adapter_source_passes_all_checks(self) -> None:
        clean_source = "from core.runtime_manager_store import RuntimeManagerStore\nclass LocalAgentAdapter:\n    pass\n"
        result = eval_adapter_safety(adapter_module_source=clean_source)
        self.assertTrue(result["eval_adapter_safety_is_not_permission"])
        failed = [f for f in result["findings"] if not f["passed"]]
        self.assertEqual(failed, [])

    def test_sqlite_in_source_fails_sql_check(self) -> None:
        bad_source = "import sqlite3\nconn = sqlite3.connect('db')\nconn.execute('SELECT 1')\n"
        findings = eval_adapter_no_direct_sql(bad_source)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_argv_in_source_fails_argv_check(self) -> None:
        bad_source = "def run(argv): pass\n"  # (argv) pattern
        findings = eval_adapter_no_argv_acceptance(bad_source)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_argv_param_in_signature_fails_check(self) -> None:
        bad_source = "def process(self, command_id, argv): pass\n"  # , argv pattern
        findings = eval_adapter_no_argv_acceptance(bad_source)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_mcp_import_in_source_fails_sdk_check(self) -> None:
        bad_source = "import mcp\nfrom mcp import server\n"
        findings = eval_adapter_no_external_sdk(bad_source)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_replay_result_with_authority_passes(self) -> None:
        replay = {"passed": True, "authority": "runtime replay evidence only; not permission"}
        findings = eval_replay_result_is_not_permission(replay)
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_replay_result_without_authority_fails(self) -> None:
        replay = {"passed": True}
        findings = eval_replay_result_is_not_permission(replay)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_metrics_with_marker_passes(self) -> None:
        metrics = {"runs_total": 1, "metrics_is_not_permission": True}
        findings = eval_metrics_result_is_not_permission(metrics)
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_metrics_without_marker_fails(self) -> None:
        metrics = {"runs_total": 1}
        findings = eval_metrics_result_is_not_permission(metrics)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_lease_owner_mismatch_in_log_fails(self) -> None:
        call_log = [{"operation": "release_lease", "owner_matched": False}]
        findings = eval_lease_ownership_enforced(call_log)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_lease_owner_match_in_log_passes(self) -> None:
        call_log = [{"operation": "release_lease", "owner_matched": True}]
        findings = eval_lease_ownership_enforced(call_log)
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_rate_limit_blocked_in_log_passes(self) -> None:
        call_log = [{"operation": "run", "rate_limited": True}]
        findings = eval_rate_limit_blocks_abuse(call_log)
        all_pass = all(f["passed"] for f in findings)
        self.assertTrue(all_pass)

    def test_secret_not_in_trace_passes(self) -> None:
        findings = eval_no_secret_in_trace_export("normal trace content", ["SECRET_TOKEN"])
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_secret_in_trace_fails(self) -> None:
        findings = eval_no_secret_in_trace_export("trace with SECRET_TOKEN", ["SECRET_TOKEN"])
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_approval_with_fingerprint_passes(self) -> None:
        approval = {"action_fingerprint": "sha256:abc123"}
        findings = eval_approval_requires_fingerprint(approval)
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_approval_without_fingerprint_fails(self) -> None:
        approval = {"action_fingerprint": ""}
        findings = eval_approval_requires_fingerprint(approval)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_mutation_without_lease_reaching_store_fails(self) -> None:
        call_log = [{"operation": "run", "had_active_lease": False, "reached_store": True}]
        findings = eval_mutation_without_lease_blocked(call_log)
        failed = [f for f in findings if not f["passed"]]
        self.assertGreater(len(failed), 0)

    def test_mutation_without_lease_blocked_passes(self) -> None:
        call_log = [{"operation": "run", "had_active_lease": False, "reached_store": False}]
        findings = eval_mutation_without_lease_blocked(call_log)
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [])

    def test_aggregator_returns_all_passed_when_clean(self) -> None:
        clean_source = "from core.runtime_manager_store import RuntimeManagerStore\n"
        replay = {"passed": True, "authority": "runtime replay evidence only; not permission"}
        metrics = {"runs_total": 0, "metrics_is_not_permission": True}
        result = eval_adapter_safety(
            adapter_module_source=clean_source,
            replay_result=replay,
            metrics_result=metrics,
        )
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["eval_adapter_safety_is_not_permission"])


# ---------------------------------------------------------------------------
# Adapter integration: metrics end-to-end
# ---------------------------------------------------------------------------


class AdapterMetricsIntegrationTests(unittest.TestCase):
    def test_full_cycle_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            store = _setup_store(Path(tmp_dir))
            ctx = _make_ctx()
            adapter = LocalAgentAdapter(store, ctx)
            adapter.status()
            adapter.read_metrics()
            lease = adapter.acquire_lease("obs-agent", ttl_seconds=300)
            adapter.run_command("cmd-run", observation_id="obs-agent")
            adapter.release_lease(lease.lease_id, "obs-agent")
            am = adapter.read_adapter_metrics()
            self.assertGreaterEqual(am.adapter_calls_total, 4)
            self.assertGreaterEqual(am.adapter_mutations_total, 2)
            self.assertEqual(am.adapter_permission_laundering_blocked, 0)
            self.assertTrue(am.metrics_is_not_permission)


if __name__ == "__main__":
    unittest.main()
