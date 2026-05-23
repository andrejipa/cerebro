"""Cross-process concurrency tests for RuntimeManagerStore — Phase 9.

Tests use multiprocessing.Process with a shared Barrier for synchronized race
starts and a Manager().list() for result collection.  All worker functions are
at module level for Windows-spawn compatibility.

Scenarios:
  - 8 processes competing for the same lease: exactly 1 succeeds.
  - Wrong-owner release / heartbeat always returns False and leaves lease active.
  - Persistent rate limit enforced under concurrent write pressure.
  - Token revoked mid-session blocks the next operation.
  - Token expired mid-session blocks the next operation.
  - Expired lease reclaim leaves <= 1 active lease for the observation.
"""
from __future__ import annotations

import multiprocessing
import os
import sys
import tempfile
import time
import unittest
from pathlib import Path

# ---------------------------------------------------------------------------
# Module-level worker functions (required for Windows spawn compatibility)
# ---------------------------------------------------------------------------

def _add_project_root(db_root: str) -> None:
    """Add the project root (parent of db_root) to sys.path if needed."""
    # db_root is the cerebro dir; its parent may differ, but we actually need
    # db_root itself on the path so 'core.*' imports work.
    project_root = str(Path(db_root))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)


def _worker_acquire_lease(
    project_root: str,
    db_root: str,
    obs_id: str,
    owner: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    """Try to acquire a lease after all workers are ready (barrier-synchronized)."""
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore, RuntimeManagerStoreError

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    try:
        store.acquire_lease(obs_id, owner, 60, "concurrent-test")
        results[idx] = "success"
    except RuntimeManagerStoreError as exc:
        results[idx] = f"blocked:{exc.code}"
    except Exception as exc:
        results[idx] = f"error:{exc}"


def _worker_release_lease(
    project_root: str,
    db_root: str,
    lease_id: str,
    wrong_owner: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    """Try to release a lease with a wrong owner after barrier."""
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    released = store.release_lease(lease_id, wrong_owner)
    results[idx] = "released" if released else "noop"


def _worker_heartbeat_lease(
    project_root: str,
    db_root: str,
    lease_id: str,
    wrong_owner: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    """Try to heartbeat a lease with a wrong owner after barrier."""
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    updated = store.heartbeat_lease(lease_id, wrong_owner, 60)
    results[idx] = "renewed" if updated else "noop"


def _worker_rate_limit(
    project_root: str,
    db_root: str,
    agent_id: str,
    operation: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    """Attempt one rate-limited operation after barrier."""
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    result = store.check_and_increment_rate_limit(agent_id, operation)
    results[idx] = "allowed" if result.allowed else "blocked"


def _worker_authenticate(
    project_root: str,
    db_root: str,
    raw_token: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    """Authenticate a token after barrier."""
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    token = store.authenticate_adapter_token(raw_token)
    results[idx] = "valid" if token is not None else "rejected"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TOML_CONTENT = (
    '[center]\nversion = 1\n\n'
    '[[observations]]\n'
    'id = "obs-concur-1"\n'
    'title = "Concurrency test obs"\n'
    'status = "open"\n'
    'kind = "slice"\n'
    'priority = "high"\n'
    'boundary = "docs/"\n'
    'trigger = "none"\n'
    'dependencies = []\n'
    'dependencies_satisfied = true\n'
    'next_action = "test"\n'
    'done_when = "done"\n'
    'halt_if = "never"\n'
)

ALL_SCOPES = list(
    {"runtime:read", "runtime:lease", "runtime:execute",
     "runtime:trace", "runtime:metrics", "runtime:replay"}
)


def _make_store(tmp_dir: str) -> "RuntimeManagerStore":
    from core.runtime_manager_store import RuntimeManagerStore

    root = Path(tmp_dir)
    store = RuntimeManagerStore(root)
    store.initialize_schema()
    obs_path = root / "docs" / "operations" / "observation_center.toml"
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(_TOML_CONTENT, encoding="utf-8")
    store.sync_observation_center(obs_path)
    return store


def _run_workers(target, worker_args_list: list, n_workers: int, timeout: float = 30.0) -> list:
    """Launch n_workers processes, wait, return results list."""
    ctx = multiprocessing.get_context("spawn")
    manager = ctx.Manager()
    results = manager.list(["pending"] * n_workers)
    barrier = ctx.Barrier(n_workers)

    processes = []
    for idx, extra_args in enumerate(worker_args_list):
        p = ctx.Process(
            target=target,
            args=(*extra_args, barrier, results, idx),
            daemon=True,
        )
        p.start()
        processes.append(p)

    for p in processes:
        p.join(timeout=timeout)
        if p.is_alive():
            p.terminate()
            p.join(timeout=5.0)

    return list(results)


# ---------------------------------------------------------------------------
# Test cases
# ---------------------------------------------------------------------------

class TestConcurrentLeaseAcquisition(unittest.TestCase):
    """8 processes race to acquire the same lease; exactly 1 must win."""

    def test_exactly_one_acquires_lease(self):
        project_root = str(Path(__file__).parent.parent)
        with tempfile.TemporaryDirectory() as tmp:
            _make_store(tmp)
            n = 8
            obs_id = "obs-concur-1"
            worker_args = [
                (project_root, tmp, obs_id, f"owner-{i}")
                for i in range(n)
            ]
            results = _run_workers(_worker_acquire_lease, worker_args, n)

        successes = [r for r in results if r == "success"]
        contention = [r for r in results if r == "blocked:lease_contention"]
        self.assertEqual(len(successes), 1, f"Expected 1 success, got: {results}")
        self.assertEqual(len(contention), n - 1, f"Expected {n-1} contention, got: {results}")

    def test_lease_contention_code_is_stable(self):
        """RuntimeManagerStoreError raised by duplicate lease has code=lease_contention."""
        from core.runtime_manager_store import RuntimeManagerStore, RuntimeManagerStoreError

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            store.acquire_lease("obs-concur-1", "owner-a", 60, "first")
            with self.assertRaises(RuntimeManagerStoreError) as cm:
                store.acquire_lease("obs-concur-1", "owner-b", 60, "second")
            self.assertEqual(cm.exception.code, "lease_contention")


class TestWrongOwnerLeaseOps(unittest.TestCase):
    """Wrong-owner release / heartbeat must be a noop for all concurrent callers."""

    def _setup_lease(self, tmp: str):
        from core.runtime_manager_store import RuntimeManagerStore

        store = _make_store(tmp)
        lease = store.acquire_lease("obs-concur-1", "real-owner", 300, "test")
        return store, lease.lease_id

    def test_wrong_owner_release_always_noop(self):
        project_root = str(Path(__file__).parent.parent)
        with tempfile.TemporaryDirectory() as tmp:
            store, lease_id = self._setup_lease(tmp)
            n = 4
            worker_args = [
                (project_root, tmp, lease_id, f"wrong-owner-{i}")
                for i in range(n)
            ]
            results = _run_workers(_worker_release_lease, worker_args, n)

        self.assertTrue(all(r == "noop" for r in results), f"Expected all noop, got: {results}")

    def test_wrong_owner_heartbeat_always_noop(self):
        project_root = str(Path(__file__).parent.parent)
        with tempfile.TemporaryDirectory() as tmp:
            store, lease_id = self._setup_lease(tmp)
            n = 4
            worker_args = [
                (project_root, tmp, lease_id, f"wrong-owner-{i}")
                for i in range(n)
            ]
            results = _run_workers(_worker_heartbeat_lease, worker_args, n)

        self.assertTrue(all(r == "noop" for r in results), f"Expected all noop, got: {results}")

    def test_lease_remains_active_after_wrong_owner_ops(self):
        """The original lease must remain active after wrong-owner operations."""
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store, lease_id = self._setup_lease(tmp)
            store.release_lease(lease_id, "wrong-owner")
            store.heartbeat_lease(lease_id, "wrong-owner", 60)
            leases = store.list_leases(observation_id="obs-concur-1")
            active = [l for l in leases if l.lease_id == lease_id and l.status == "active"]
            self.assertEqual(len(active), 1)

    def test_lease_owner_mismatch_code_stable(self):
        """release_lease with wrong owner produces lease_owner_mismatch in the trace events."""
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store, lease_id = self._setup_lease(tmp)
            result = store.release_lease(lease_id, "definitely-wrong-owner")
            self.assertFalse(result)
            # Verify trace captured the diagnostic in event payload_json
            traces = store.list_traces(operation="lease", limit=50)
            noop_traces = [t for t in traces if t.status == "release_noop"]
            self.assertTrue(len(noop_traces) >= 1)
            last_noop = noop_traces[-1]
            # Check that at least one event's payload_json contains the code
            payloads = " ".join(e.payload_json for e in last_noop.events)
            self.assertIn("lease_owner_mismatch", payloads)


class TestPersistentRateLimitConcurrency(unittest.TestCase):
    """Concurrent processes must not collectively bypass the rate limit."""

    def test_concurrent_writes_respect_mutate_limit(self):
        """RATE_LIMIT_MUTATE=10 means ≤10 of N callers are allowed per window."""
        from core.runtime_manager_store import RATE_LIMIT_MUTATE

        project_root = str(Path(__file__).parent.parent)
        n = RATE_LIMIT_MUTATE + 5  # send more than the limit
        agent_id = "concur-agent"
        operation = "run"  # mutate op

        with tempfile.TemporaryDirectory() as tmp:
            _make_store(tmp)
            worker_args = [
                (project_root, tmp, agent_id, operation)
                for _ in range(n)
            ]
            results = _run_workers(_worker_rate_limit, worker_args, n)

        allowed = [r for r in results if r == "allowed"]
        blocked = [r for r in results if r == "blocked"]
        # At most RATE_LIMIT_MUTATE allowed; at least 5 blocked.
        self.assertLessEqual(len(allowed), RATE_LIMIT_MUTATE,
                             f"Too many allowed: {results}")
        self.assertGreaterEqual(len(blocked), 5,
                                f"Too few blocked: {results}")

    def test_rate_limit_not_bypassed_by_single_minute_window(self):
        """All 15 sequential calls in one minute: last 5 must be blocked."""
        from core.runtime_manager_store import RuntimeManagerStore, RATE_LIMIT_MUTATE

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            agent_id = "seq-agent"
            operation = "run"
            results = []
            for _ in range(RATE_LIMIT_MUTATE + 5):
                r = store.check_and_increment_rate_limit(agent_id, operation)
                results.append(r.allowed)

        allowed = sum(1 for r in results if r)
        self.assertEqual(allowed, RATE_LIMIT_MUTATE)


class TestTokenRevokedMidSession(unittest.TestCase):
    """A token revoked between calls must block the next authenticate call."""

    def test_revoked_token_rejected_by_authenticate(self):
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            token_record, raw = store.issue_adapter_token(
                agent_id="agent-revoke",
                agent_role="runner",
                scopes=ALL_SCOPES,
                ttl_seconds=3600,
            )
            # Token valid before revocation
            self.assertIsNotNone(store.authenticate_adapter_token(raw))
            # Revoke
            store.revoke_adapter_token(token_record.token_id)
            # Token rejected after revocation
            self.assertIsNone(store.authenticate_adapter_token(raw))

    def test_revoked_token_blocks_concurrent_authenticate(self):
        """Token revoked before barrier; all workers see it as rejected."""
        project_root = str(Path(__file__).parent.parent)
        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            token_record, raw = store.issue_adapter_token(
                agent_id="agent-revoke-concurrent",
                agent_role="runner",
                scopes=ALL_SCOPES,
                ttl_seconds=3600,
            )
            store.revoke_adapter_token(token_record.token_id)

            n = 4
            worker_args = [(project_root, tmp, raw) for _ in range(n)]
            results = _run_workers(_worker_authenticate, worker_args, n)

        self.assertTrue(
            all(r == "rejected" for r in results),
            f"Expected all rejected, got: {results}",
        )

    def test_per_operation_auth_rejects_revoked_token(self):
        """build_app: a tool call after token revocation raises PermissionError."""
        from core.runtime_manager_store import RuntimeManagerStore
        from adapters.runtime_manager_mcp_stdio.server import _require_current_token_factory

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            token_record, raw = store.issue_adapter_token(
                agent_id="agent-perops",
                agent_role="runner",
                scopes=ALL_SCOPES,
                ttl_seconds=3600,
            )
            require_fn = _require_current_token_factory(store, raw)
            # Token valid now
            os.environ["CEREBRO_RUNTIME_MCP_TOKEN"] = raw
            try:
                t = require_fn("runtime:read", "L0_observe")
                self.assertIsNotNone(t)
                # Revoke mid-session
                store.revoke_adapter_token(token_record.token_id)
                # Next call must raise
                with self.assertRaises(PermissionError) as cm:
                    require_fn("runtime:read", "L0_observe")
                self.assertIn("token_revoked_mid_session", str(cm.exception))
            finally:
                os.environ.pop("CEREBRO_RUNTIME_MCP_TOKEN", None)


class TestTokenExpiredMidSession(unittest.TestCase):
    """A token that expires mid-session must block the next authenticate call."""

    def test_expired_token_rejected_by_authenticate(self):
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            token_record, raw = store.issue_adapter_token(
                agent_id="agent-expire",
                agent_role="runner",
                scopes=ALL_SCOPES,
                ttl_seconds=1,  # expires almost immediately
            )
            # Immediately valid
            self.assertIsNotNone(store.authenticate_adapter_token(raw))
            # Force-expire by back-dating the expires_at in DB
            import sqlite3
            from contextlib import closing
            past = "2000-01-01T00:00:00+00:00"
            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute(
                    "UPDATE adapter_tokens SET expires_at = ? WHERE token_id = ?",
                    (past, token_record.token_id),
                )
                conn.commit()
            # Now rejected
            self.assertIsNone(store.authenticate_adapter_token(raw))

    def test_per_operation_auth_rejects_expired_token(self):
        """build_app: tool call after forced expiry raises PermissionError."""
        import sqlite3
        from contextlib import closing
        from adapters.runtime_manager_mcp_stdio.server import _require_current_token_factory

        with tempfile.TemporaryDirectory() as tmp:
            from core.runtime_manager_store import RuntimeManagerStore
            store = _make_store(tmp)
            token_record, raw = store.issue_adapter_token(
                agent_id="agent-expire-ops",
                agent_role="runner",
                scopes=ALL_SCOPES,
                ttl_seconds=3600,
            )
            require_fn = _require_current_token_factory(store, raw)
            # Valid now
            t = require_fn("runtime:read", "L0_observe")
            self.assertIsNotNone(t)
            # Force expire
            past = "2000-01-01T00:00:00+00:00"
            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute(
                    "UPDATE adapter_tokens SET expires_at = ? WHERE token_id = ?",
                    (past, token_record.token_id),
                )
                conn.commit()
            # Next call rejected
            with self.assertRaises(PermissionError) as cm:
                require_fn("runtime:read", "L0_observe")
            self.assertIn("token_revoked_mid_session", str(cm.exception))


class TestExpiredLeaseReclaim(unittest.TestCase):
    """reclaim_expired_leases must leave <= 1 active lease per observation."""

    def test_reclaim_leaves_no_active_lease(self):
        """After reclaim, an expired lease is no longer active."""
        import sqlite3
        from contextlib import closing
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            lease = store.acquire_lease("obs-concur-1", "owner-a", 300)
            # Force-expire the lease
            past = "2000-01-01T00:00:00+00:00"
            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = ? WHERE lease_id = ?",
                    (past, lease.lease_id),
                )
                conn.commit()
            reclaimed = store.reclaim_expired_leases()
            self.assertGreaterEqual(reclaimed, 1)
            leases = store.list_leases(observation_id="obs-concur-1")
            active = [l for l in leases if l.status == "active"]
            self.assertEqual(len(active), 0)

    def test_reclaim_then_new_acquire_succeeds(self):
        """After reclaim, a new process can acquire the same observation lease."""
        import sqlite3
        from contextlib import closing
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            # First lease
            lease = store.acquire_lease("obs-concur-1", "owner-a", 300)
            past = "2000-01-01T00:00:00+00:00"
            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = ? WHERE lease_id = ?",
                    (past, lease.lease_id),
                )
                conn.commit()
            store.reclaim_expired_leases()
            # New acquire must succeed
            new_lease = store.acquire_lease("obs-concur-1", "owner-b", 300)
            self.assertEqual(new_lease.owner, "owner-b")
            self.assertEqual(new_lease.status, "active")
            leases = store.list_leases(observation_id="obs-concur-1")
            active = [l for l in leases if l.status == "active"]
            self.assertEqual(len(active), 1)

    def test_reclaim_does_not_create_two_active_leases(self):
        """After reclaim, the observation has at most 1 active lease."""
        import sqlite3
        from contextlib import closing
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            # Acquire and expire a lease
            lease = store.acquire_lease("obs-concur-1", "owner-a", 300)
            past = "2000-01-01T00:00:00+00:00"
            with closing(sqlite3.connect(store.db_path)) as conn:
                conn.execute(
                    "UPDATE managed_leases SET expires_at = ? WHERE lease_id = ?",
                    (past, lease.lease_id),
                )
                conn.commit()
            store.reclaim_expired_leases()
            # Acquire a new lease
            store.acquire_lease("obs-concur-1", "owner-b", 300)
            # There must be exactly 1 active lease
            leases = store.list_leases(observation_id="obs-concur-1")
            active = [l for l in leases if l.status == "active"]
            self.assertLessEqual(len(active), 1)


class TestLeaseContencionDiagnosticCodes(unittest.TestCase):
    """Stable diagnostic codes are present on RuntimeManagerStoreError."""

    def test_acquire_duplicate_raises_with_lease_contention_code(self):
        from core.runtime_manager_store import RuntimeManagerStore, RuntimeManagerStoreError

        with tempfile.TemporaryDirectory() as tmp:
            store = _make_store(tmp)
            store.acquire_lease("obs-concur-1", "owner-a", 300)
            try:
                store.acquire_lease("obs-concur-1", "owner-b", 300)
                self.fail("Expected RuntimeManagerStoreError")
            except RuntimeManagerStoreError as exc:
                self.assertEqual(exc.code, "lease_contention")
                self.assertIn("obs-concur-1", str(exc))

    def test_generic_store_error_has_empty_code(self):
        from core.runtime_manager_store import RuntimeManagerStoreError

        exc = RuntimeManagerStoreError("something went wrong")
        self.assertEqual(exc.code, "")
        self.assertEqual(str(exc), "something went wrong")

    def test_store_error_with_code(self):
        from core.runtime_manager_store import RuntimeManagerStoreError

        exc = RuntimeManagerStoreError("lease busy", code="lease_contention")
        self.assertEqual(exc.code, "lease_contention")


if __name__ == "__main__":
    # Required for Windows: spawn context needs the guard.
    multiprocessing.freeze_support()
    unittest.main()
