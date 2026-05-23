"""Pytest tests for the Phase 10 local stress lab scenarios.

Each test runs one deterministic stress scenario and asserts it passes.
stress_pass_is_not_permission = True on every result — these tests verify
local behavioral invariants, not execution permission.
"""
from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from adapters.runtime_manager_mcp_stdio.server import _check_replay_path_scope
from experiments.runtime_manager_stress_lab.scenarios import (
    StressResult,
    stress_db_busy_contention,
    stress_expired_lease_reclaim,
    stress_lease_race,
    stress_rate_limit_concurrency,
    stress_reads_under_load,
    stress_replay_path_guard,
    stress_token_expire_mid_session,
    stress_token_revoke_mid_session,
)


def _assert_stress(result: StressResult, test: unittest.TestCase) -> None:
    test.assertTrue(
        result.stress_pass_is_not_permission,
        "StressResult must carry stress_pass_is_not_permission=True",
    )
    test.assertEqual(result.authority, "advisory/local stress only")
    test.assertTrue(result.passed, f"Scenario '{result.scenario}' failed: {result.detail}")


class TestStressLabInProcess(unittest.TestCase):
    """In-process (single-worker) stress scenarios — run fast, no subprocess overhead."""

    def test_stress_result_not_permission(self) -> None:
        """StressResult dataclass always carries not-permission markers."""
        r = StressResult(scenario="dummy", passed=True, detail="ok")
        self.assertTrue(r.stress_pass_is_not_permission)
        self.assertEqual(r.authority, "advisory/local stress only")

    def test_token_revoke_mid_session(self) -> None:
        _assert_stress(stress_token_revoke_mid_session(), self)

    def test_token_expire_mid_session(self) -> None:
        _assert_stress(stress_token_expire_mid_session(), self)

    def test_expired_lease_reclaim(self) -> None:
        _assert_stress(stress_expired_lease_reclaim(), self)

    def test_replay_path_guard(self) -> None:
        _assert_stress(stress_replay_path_guard(), self)


class TestReplayPathGuardUnit(unittest.TestCase):
    """Unit regressions for _check_replay_path_scope — the MCP server path guard."""

    def test_external_path_rejected_with_correct_code(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            with tempfile.TemporaryDirectory() as external_dir:
                root = Path(root_dir)
                external_file = Path(external_dir) / "evil.json"
                external_file.write_text("{}", encoding="utf-8")
                with self.assertRaises(ValueError) as ctx:
                    _check_replay_path_scope(root, str(external_file))
                self.assertIn("replay_path_out_of_scope", str(ctx.exception))

    def test_path_traversal_rejected_with_correct_code(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            with self.assertRaises(ValueError) as ctx:
                _check_replay_path_scope(root, "../outside.json")
            self.assertIn("replay_path_out_of_scope", str(ctx.exception))

    def test_valid_internal_path_accepted(self) -> None:
        with tempfile.TemporaryDirectory() as root_dir:
            root = Path(root_dir)
            internal = root / "scenario.json"
            internal.write_text("{}", encoding="utf-8")
            resolved = _check_replay_path_scope(root, "scenario.json")
            self.assertTrue(resolved.is_relative_to(root.resolve()))

    def test_stress_result_not_permission_preserved(self) -> None:
        result = stress_replay_path_guard()
        self.assertTrue(result.stress_pass_is_not_permission)
        self.assertEqual(result.authority, "advisory/local stress only")


class TestStressLabConcurrent(unittest.TestCase):
    """Multi-process stress scenarios — verify SQLite concurrency invariants."""

    def test_lease_race(self) -> None:
        _assert_stress(stress_lease_race(n_workers=8), self)

    def test_rate_limit_concurrency(self) -> None:
        _assert_stress(stress_rate_limit_concurrency(n_workers=20), self)

    def test_reads_under_load(self) -> None:
        _assert_stress(stress_reads_under_load(n_workers=12), self)

    def test_db_busy_contention(self) -> None:
        _assert_stress(stress_db_busy_contention(n_workers=16), self)
