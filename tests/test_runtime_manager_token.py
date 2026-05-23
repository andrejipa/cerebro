"""Tests for schema v14 token and persistent rate limit store APIs."""
from __future__ import annotations

import datetime
import tempfile
import unittest
from pathlib import Path

from core.runtime_manager_store import (
    ADAPTER_TOKEN_SCOPES,
    RATE_LIMIT_MUTATE,
    RATE_LIMIT_MUTATE_OPS,
    RATE_LIMIT_READ,
    AdapterToken,
    RateLimitResult,
    RuntimeManagerStore,
)


def _store(tmp_dir: str) -> RuntimeManagerStore:
    root = Path(tmp_dir)
    store = RuntimeManagerStore(root)
    store.initialize_schema()
    return store


class AdapterTokenSchemaTests(unittest.TestCase):
    def test_adapter_token_constants_defined(self):
        self.assertIn("runtime:read", ADAPTER_TOKEN_SCOPES)
        self.assertIn("runtime:lease", ADAPTER_TOKEN_SCOPES)
        self.assertIn("runtime:execute", ADAPTER_TOKEN_SCOPES)
        self.assertIn("runtime:trace", ADAPTER_TOKEN_SCOPES)
        self.assertIn("runtime:metrics", ADAPTER_TOKEN_SCOPES)
        self.assertIn("runtime:replay", ADAPTER_TOKEN_SCOPES)

    def test_rate_limit_constants(self):
        self.assertEqual(RATE_LIMIT_READ, 60)
        self.assertEqual(RATE_LIMIT_MUTATE, 10)
        self.assertIn("run", RATE_LIMIT_MUTATE_OPS)
        self.assertIn("acquire_lease", RATE_LIMIT_MUTATE_OPS)

    def test_adapter_token_dataclass_is_frozen(self):
        tok = AdapterToken(
            token_id="tok-abc",
            agent_id="agent-1",
            agent_role="worker",
            scopes=("runtime:read",),
            status="active",
            issued_at="2026-05-08T00:00:00Z",
            expires_at="2026-05-09T00:00:00Z",
            revoked_at="",
        )
        self.assertEqual(tok.agent_id, "agent-1")
        self.assertTrue(tok.token_is_not_credential)
        with self.assertRaises((AttributeError, TypeError)):
            tok.status = "revoked"  # type: ignore[misc]

    def test_rate_limit_result_dataclass_is_frozen(self):
        r = RateLimitResult(
            allowed=True,
            retry_after_seconds=0,
            agent_id="a",
            operation="status",
        )
        self.assertTrue(r.rate_limit_is_not_permission)
        with self.assertRaises((AttributeError, TypeError)):
            r.allowed = False  # type: ignore[misc]


class IssueAdapterTokenTests(unittest.TestCase):
    def test_issue_returns_token_and_raw(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("agent-1", "worker", frozenset({"runtime:read"}), 3600)
            self.assertIsInstance(tok, AdapterToken)
            self.assertEqual(tok.status, "active")
            self.assertEqual(tok.agent_id, "agent-1")
            self.assertEqual(tok.agent_role, "worker")
            self.assertIn("runtime:read", tok.scopes)
            self.assertTrue(tok.token_is_not_credential)
            # raw token is 64 hex chars (32 bytes)
            self.assertEqual(len(raw), 64)

    def test_token_id_prefix(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, _ = store.issue_adapter_token("agent-2", "reader", frozenset({"runtime:read"}), 60)
            self.assertTrue(tok.token_id.startswith("tok-"))

    def test_expires_at_is_in_future(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, _ = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            now = datetime.datetime.now(datetime.timezone.utc)
            expires = datetime.datetime.fromisoformat(tok.expires_at)
            self.assertGreater(expires, now)

    def test_scopes_persisted_correctly(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            scopes_in = frozenset({"runtime:read", "runtime:execute", "runtime:trace"})
            tok, _ = store.issue_adapter_token("agent-1", "worker", scopes_in, 3600)
            self.assertEqual(frozenset(tok.scopes), scopes_in)

    def test_raw_token_not_in_token_record(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            import dataclasses
            fields = dataclasses.asdict(tok)
            for v in fields.values():
                self.assertNotEqual(str(v), raw)

    def test_two_tokens_different_ids_and_raws(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok1, raw1 = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 60)
            tok2, raw2 = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 60)
            self.assertNotEqual(tok1.token_id, tok2.token_id)
            self.assertNotEqual(raw1, raw2)

    def test_invalid_scope_raises(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            with self.assertRaises(Exception):
                store.issue_adapter_token("a", "r", frozenset({"bad:scope"}), 60)

    def test_empty_scopes_allowed(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("a", "r", frozenset(), 60)
            self.assertEqual(tok.scopes, ())

    def test_ttl_zero_raises(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            with self.assertRaises(Exception):
                store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 0)

    def test_ttl_negative_raises(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            with self.assertRaises(Exception):
                store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), -1)


class AuthenticateAdapterTokenTests(unittest.TestCase):
    def test_authenticate_valid_token(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("agent-1", "worker", frozenset({"runtime:read"}), 3600)
            result = store.authenticate_adapter_token(raw)
            self.assertIsNotNone(result)
            self.assertEqual(result.token_id, tok.token_id)
            self.assertEqual(result.agent_id, "agent-1")

    def test_authenticate_unknown_token_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            result = store.authenticate_adapter_token("deadbeef" * 8)
            self.assertIsNone(result)

    def test_authenticate_wrong_token_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            _, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            # Flip last char
            bad = raw[:-1] + ("0" if raw[-1] != "0" else "1")
            self.assertIsNone(store.authenticate_adapter_token(bad))

    def test_authenticate_revoked_token_returns_none(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            store.revoke_adapter_token(tok.token_id)
            self.assertIsNone(store.authenticate_adapter_token(raw))

    def test_authenticate_expired_token_returns_none(self):
        import sqlite3, json
        from contextlib import closing
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, raw = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            # Backdate expires_at to one second in the past
            db_path = Path(td) / ".cerebro" / "runtime.db"
            with closing(sqlite3.connect(str(db_path))) as conn:
                conn.execute(
                    "UPDATE adapter_tokens SET expires_at = ? WHERE token_id = ?",
                    ("2000-01-01T00:00:00+00:00", tok.token_id),
                )
                conn.commit()
            result = store.authenticate_adapter_token(raw)
            self.assertIsNone(result)


class RevokeAdapterTokenTests(unittest.TestCase):
    def test_revoke_active_token_returns_true(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, _ = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            self.assertTrue(store.revoke_adapter_token(tok.token_id))

    def test_revoke_already_revoked_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            tok, _ = store.issue_adapter_token("a", "r", frozenset({"runtime:read"}), 3600)
            store.revoke_adapter_token(tok.token_id)
            self.assertFalse(store.revoke_adapter_token(tok.token_id))

    def test_revoke_unknown_token_returns_false(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            self.assertFalse(store.revoke_adapter_token("tok-nonexistent"))


class PersistentRateLimitTests(unittest.TestCase):
    def test_read_op_allowed_within_limit(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            result = store.check_and_increment_rate_limit("agent-1", "status")
            self.assertIsInstance(result, RateLimitResult)
            self.assertTrue(result.allowed)
            self.assertEqual(result.agent_id, "agent-1")
            self.assertEqual(result.operation, "status")
            self.assertTrue(result.rate_limit_is_not_permission)

    def test_mutate_op_allowed_within_limit(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            result = store.check_and_increment_rate_limit("agent-1", "run")
            self.assertTrue(result.allowed)

    def test_different_agents_independent_buckets(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            for _ in range(RATE_LIMIT_MUTATE):
                store.check_and_increment_rate_limit("agent-1", "run")
            # agent-1 is now at limit; agent-2 is fresh
            r = store.check_and_increment_rate_limit("agent-2", "run")
            self.assertTrue(r.allowed)

    def test_mutate_op_blocked_at_limit(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            for _ in range(RATE_LIMIT_MUTATE):
                r = store.check_and_increment_rate_limit("agent-x", "run")
                self.assertTrue(r.allowed)
            blocked = store.check_and_increment_rate_limit("agent-x", "run")
            self.assertFalse(blocked.allowed)
            self.assertGreater(blocked.retry_after_seconds, 0)

    def test_read_op_blocked_at_limit(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            for _ in range(RATE_LIMIT_READ):
                store.check_and_increment_rate_limit("agent-y", "status")
            blocked = store.check_and_increment_rate_limit("agent-y", "status")
            self.assertFalse(blocked.allowed)

    def test_result_not_permission_marker(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            result = store.check_and_increment_rate_limit("a", "status")
            self.assertTrue(result.rate_limit_is_not_permission)

    def test_different_operations_independent_buckets(self):
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            for _ in range(RATE_LIMIT_MUTATE):
                store.check_and_increment_rate_limit("ag", "run")
            # Different operation has its own bucket
            r = store.check_and_increment_rate_limit("ag", "acquire_lease")
            self.assertTrue(r.allowed)

    def test_persistent_across_store_instances(self):
        """Counts persist in SQLite across different store instances."""
        with tempfile.TemporaryDirectory() as td:
            root = Path(td)
            store1 = RuntimeManagerStore(root)
            store1.initialize_schema()
            for _ in range(RATE_LIMIT_MUTATE):
                store1.check_and_increment_rate_limit("agent-z", "run")

            store2 = RuntimeManagerStore(root)
            blocked = store2.check_and_increment_rate_limit("agent-z", "run")
            self.assertFalse(blocked.allowed)


class PersistentRateLimiterWrapperTests(unittest.TestCase):
    def test_wrapper_delegates_to_store(self):
        from adapters.runtime_manager_local_agent.persistent_rate_limiter import PersistentRateLimiter
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            limiter = PersistentRateLimiter(store)
            allowed, retry = limiter.check("agent-1", "status")
            self.assertTrue(allowed)
            self.assertEqual(retry, 0)

    def test_wrapper_returns_blocked_at_limit(self):
        from adapters.runtime_manager_local_agent.persistent_rate_limiter import PersistentRateLimiter
        with tempfile.TemporaryDirectory() as td:
            store = _store(td)
            limiter = PersistentRateLimiter(store)
            for _ in range(RATE_LIMIT_MUTATE):
                limiter.check("agent-m", "run")
            allowed, retry = limiter.check("agent-m", "run")
            self.assertFalse(allowed)
            self.assertGreater(retry, 0)


if __name__ == "__main__":
    unittest.main()
