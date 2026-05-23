"""runtime_manager_stress_lab.scenarios — Phase 10 local stress scenarios.

All scenarios are deterministic, short-running, and carry:
  stress_pass_is_not_permission = True
  authority = "advisory/local stress only"

Results do NOT grant execution permission, approval, or runtime gate bypass.
Worker functions are at module level for Windows spawn compatibility.
"""
from __future__ import annotations

import multiprocessing
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

STRESS_AUTHORITY = "advisory/local stress only"
stress_pass_is_not_permission = True

_TOML_TEMPLATE = (
    "[center]\nversion = 1\n\n"
    "[[observations]]\n"
    'id = "obs-stress-1"\n'
    'title = "Stress test obs"\n'
    'status = "open"\n'
    'kind = "slice"\n'
    'priority = "high"\n'
    'boundary = "docs/"\n'
    'trigger = "none"\n'
    "dependencies = []\n"
    "dependencies_satisfied = true\n"
    'next_action = "test"\n'
    'done_when = "done"\n'
    'halt_if = "never"\n'
)

ALL_SCOPES = list({
    "runtime:read", "runtime:lease", "runtime:execute",
    "runtime:trace", "runtime:metrics", "runtime:replay",
})


# ---------------------------------------------------------------------------
# StressResult
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class StressResult:
    scenario: str
    passed: bool
    detail: str
    stress_pass_is_not_permission: bool = True
    authority: str = STRESS_AUTHORITY
    extra: dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _add_project_root(root: str) -> None:
    if root not in sys.path:
        sys.path.insert(0, root)


def _make_store(tmp_dir: str, project_root: str | None = None) -> Any:
    if project_root:
        _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    root = Path(tmp_dir)
    store = RuntimeManagerStore(root)
    store.initialize_schema()
    obs_path = root / "docs" / "operations" / "observation_center.toml"
    obs_path.parent.mkdir(parents=True, exist_ok=True)
    obs_path.write_text(_TOML_TEMPLATE, encoding="utf-8")
    store.sync_observation_center(obs_path)
    return store


# ---------------------------------------------------------------------------
# Module-level workers (required for Windows spawn compatibility)
# ---------------------------------------------------------------------------

def _worker_lease_race(
    project_root: str,
    db_root: str,
    obs_id: str,
    owner: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore, RuntimeManagerStoreError

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    try:
        store.acquire_lease(obs_id, owner, 60, "stress-lease-race")
        results[idx] = "success"
    except RuntimeManagerStoreError as exc:
        results[idx] = f"blocked:{exc.code}"
    except Exception as exc:
        results[idx] = f"error:{exc}"


def _worker_rate_limit_stress(
    project_root: str,
    db_root: str,
    agent_id: str,
    operation: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    result = store.check_and_increment_rate_limit(agent_id, operation)
    results[idx] = "allowed" if result.allowed else "blocked"


def _worker_concurrent_read(
    project_root: str,
    db_root: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    try:
        status = store.read_status()
        results[idx] = "ok" if status is not None else "none"
    except Exception as exc:
        results[idx] = f"error:{exc}"


def _worker_concurrent_write(
    project_root: str,
    db_root: str,
    agent_id: str,
    barrier: "multiprocessing.Barrier",
    results: "multiprocessing.managers.ListProxy",
    idx: int,
) -> None:
    _add_project_root(project_root)
    from core.runtime_manager_store import RuntimeManagerStore

    store = RuntimeManagerStore(Path(db_root))
    barrier.wait()
    try:
        r = store.check_and_increment_rate_limit(agent_id, "sync")
        results[idx] = "allowed" if r.allowed else "blocked"
    except Exception as exc:
        results[idx] = f"error:{exc}"


def _run_workers(target, args_list: list, n: int, timeout: float = 20.0) -> list:
    ctx = multiprocessing.get_context("spawn")
    with ctx.Manager() as manager:
        results = manager.list(["pending"] * n)
        barrier = ctx.Barrier(n)
        procs = [
            ctx.Process(target=target, args=(*args_list[i], barrier, results, i))
            for i in range(n)
        ]
        for p in procs:
            p.start()
        for p in procs:
            p.join(timeout=timeout)
        for p in procs:
            if p.is_alive():
                p.terminate()
        return list(results)


# ---------------------------------------------------------------------------
# Scenario 1: Lease race — exactly 1 of N processes wins
# ---------------------------------------------------------------------------

def stress_lease_race(n_workers: int = 8) -> StressResult:
    """N processes race for the same observation lease; exactly 1 must succeed."""
    import os
    project_root = str(Path(__file__).parent.parent.parent)

    with tempfile.TemporaryDirectory() as tmp:
        _make_store(tmp, project_root)
        args_list = [
            [project_root, tmp, "obs-stress-1", f"owner-{i}"]
            for i in range(n_workers)
        ]
        raw = _run_workers(_worker_lease_race, args_list, n_workers)

    successes = [r for r in raw if r == "success"]
    blocked = [r for r in raw if r.startswith("blocked:lease_contention")]
    errors = [r for r in raw if r.startswith("error:") or r == "pending"]

    passed = (
        len(successes) == 1
        and len(blocked) == n_workers - 1
        and not errors
    )
    return StressResult(
        scenario="stress_lease_race",
        passed=passed,
        detail=(
            f"{n_workers} workers: {len(successes)} success, "
            f"{len(blocked)} lease_contention, {len(errors)} errors"
        ),
        extra={"raw": raw},
    )


# ---------------------------------------------------------------------------
# Scenario 2: Rate limit under concurrency — allowed ≤ RATE_LIMIT_MUTATE
# ---------------------------------------------------------------------------

def stress_rate_limit_concurrency(n_workers: int = 20) -> StressResult:
    """N concurrent mutate ops: allowed count must not exceed RATE_LIMIT_MUTATE (10)."""
    from core.runtime_manager_store import RATE_LIMIT_MUTATE

    project_root = str(Path(__file__).parent.parent.parent)

    with tempfile.TemporaryDirectory() as tmp:
        _make_store(tmp, project_root)
        args_list = [
            [project_root, tmp, "stress-agent-rl", "run"]
            for _ in range(n_workers)
        ]
        raw = _run_workers(_worker_rate_limit_stress, args_list, n_workers)

    allowed = raw.count("allowed")
    blocked = raw.count("blocked")
    errors = [r for r in raw if r not in ("allowed", "blocked")]

    passed = allowed <= RATE_LIMIT_MUTATE and not errors
    return StressResult(
        scenario="stress_rate_limit_concurrency",
        passed=passed,
        detail=(
            f"{n_workers} workers: {allowed} allowed (limit={RATE_LIMIT_MUTATE}), "
            f"{blocked} blocked, {len(errors)} errors"
        ),
        extra={"raw": raw, "limit": RATE_LIMIT_MUTATE},
    )


# ---------------------------------------------------------------------------
# Scenario 3: Token revoke mid-session — revoked token is immediately rejected
# ---------------------------------------------------------------------------

def stress_token_revoke_mid_session() -> StressResult:
    """Revoke a token; authenticate_adapter_token must return None immediately."""
    project_root = str(Path(__file__).parent.parent.parent)
    _add_project_root(project_root)

    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp, project_root)

        token_record, raw = store.issue_adapter_token(
            agent_id="stress-revoke-agent",
            agent_role="runner",
            scopes=ALL_SCOPES,
            ttl_seconds=3600,
        )

        before = store.authenticate_adapter_token(raw)
        store.revoke_adapter_token(token_record.token_id)
        after = store.authenticate_adapter_token(raw)

        passed = before is not None and after is None
        return StressResult(
            scenario="stress_token_revoke_mid_session",
            passed=passed,
            detail=f"before={before is not None} after={after is not None}",
        )


# ---------------------------------------------------------------------------
# Scenario 4: Token expire mid-session — expired token rejected
# ---------------------------------------------------------------------------

def stress_token_expire_mid_session() -> StressResult:
    """Force-expire a token by setting its expiry to the past; must be rejected."""
    import sqlite3

    project_root = str(Path(__file__).parent.parent.parent)
    _add_project_root(project_root)

    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp, project_root)
        db_path = Path(tmp) / ".cerebro" / "runtime.db"

        _token_record, raw = store.issue_adapter_token(
            agent_id="stress-expire-agent",
            agent_role="runner",
            scopes=ALL_SCOPES,
            ttl_seconds=3600,
        )

        before = store.authenticate_adapter_token(raw)

        # Force expiry to the past
        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "UPDATE adapter_tokens SET expires_at = '2000-01-01T00:00:00+00:00'"
            )
            conn.commit()
        finally:
            conn.close()

        after = store.authenticate_adapter_token(raw)

        passed = before is not None and after is None
        return StressResult(
            scenario="stress_token_expire_mid_session",
            passed=passed,
            detail=f"before={before is not None} after={after is not None}",
        )


# ---------------------------------------------------------------------------
# Scenario 5: Expired-lease reclaim — reclaim leaves 0 active stress leases
# ---------------------------------------------------------------------------

def stress_expired_lease_reclaim() -> StressResult:
    """Acquire lease with TTL=0 (immediately expired), reclaim; 0 active leases remain."""
    import sqlite3

    project_root = str(Path(__file__).parent.parent.parent)
    _add_project_root(project_root)

    with tempfile.TemporaryDirectory() as tmp:
        store = _make_store(tmp, project_root)
        db_path = Path(tmp) / ".cerebro" / "runtime.db"

        # Acquire then force-expire
        store.acquire_lease("obs-stress-1", "stress-owner", 60, "stress-reclaim")

        conn = sqlite3.connect(str(db_path))
        try:
            conn.execute(
                "UPDATE managed_leases SET expires_at = '2000-01-01T00:00:00+00:00'"
            )
            conn.commit()
        finally:
            conn.close()

        reclaimed = store.reclaim_expired_leases()

        # After reclaim, no truly-active leases should block single-flight
        conn2 = sqlite3.connect(str(db_path))
        try:
            conn2.row_factory = sqlite3.Row
            active = conn2.execute(
                "SELECT COUNT(*) AS cnt FROM managed_leases WHERE status = 'active'"
            ).fetchone()["cnt"]
        finally:
            conn2.close()

        passed = reclaimed >= 1 and active == 0
        return StressResult(
            scenario="stress_expired_lease_reclaim",
            passed=passed,
            detail=f"reclaimed={reclaimed} active_after={active}",
        )


# ---------------------------------------------------------------------------
# Scenario 6: Replay path guard — path outside scope is rejected
# ---------------------------------------------------------------------------

def stress_replay_path_guard() -> StressResult:
    """MCP server path guard must reject scenario_path that escapes the store root."""
    from adapters.runtime_manager_mcp_stdio.server import _check_replay_path_scope

    project_root = str(Path(__file__).parent.parent.parent)
    _add_project_root(project_root)

    with tempfile.TemporaryDirectory() as tmp_escape:
        with tempfile.TemporaryDirectory() as tmp_store:
            store = _make_store(tmp_store, project_root)
            store_root = store.root

            # Create a valid JSON file OUTSIDE the store root (in a separate temp dir)
            external_file = Path(tmp_escape) / "evil_scenario.json"
            external_file.write_text('{"scenario": "evil"}', encoding="utf-8")

            # --- 1. External path must be rejected with replay_path_out_of_scope ---
            rejection_ok = False
            rejection_detail = ""
            try:
                _check_replay_path_scope(store_root, str(external_file))
                rejection_detail = "guard did not reject external path"
            except ValueError as exc:
                msg = str(exc)
                if "replay_path_out_of_scope" in msg:
                    rejection_ok = True
                    rejection_detail = f"correctly rejected: {msg[:80]}"
                else:
                    rejection_detail = f"wrong error code: {msg[:80]}"
            except Exception as exc:
                rejection_detail = f"unexpected exception: {exc}"

            # --- 2. Path traversal with relative escape also rejected ---
            traversal_ok = False
            try:
                _check_replay_path_scope(store_root, "../outside.json")
                traversal_detail = "guard did not reject traversal path"
            except ValueError as exc:
                if "replay_path_out_of_scope" in str(exc):
                    traversal_ok = True
                    traversal_detail = "traversal rejected correctly"
                else:
                    traversal_detail = f"wrong error code: {exc}"
            except Exception as exc:
                traversal_detail = f"unexpected exception: {exc}"

            # --- 3. Valid path inside root is accepted ---
            inside_file = store_root / "valid_scenario.json"
            inside_file.write_text('{"scenario": "valid"}', encoding="utf-8")
            inside_ok = False
            try:
                result = _check_replay_path_scope(store_root, "valid_scenario.json")
                inside_ok = result.is_relative_to(store_root.resolve())
                inside_detail = "internal path accepted"
            except Exception as exc:
                inside_detail = f"internal path incorrectly rejected: {exc}"

        passed = rejection_ok and traversal_ok and inside_ok
        detail = (
            f"external={rejection_detail}; traversal={traversal_detail}; "
            f"internal={inside_detail}"
        )
        return StressResult(
            scenario="stress_replay_path_guard",
            passed=passed,
            detail=detail,
        )


# ---------------------------------------------------------------------------
# Scenario 7: Reads under load — N concurrent reads return consistent status
# ---------------------------------------------------------------------------

def stress_reads_under_load(n_workers: int = 12) -> StressResult:
    """N concurrent read_status() calls must all succeed without corruption."""
    project_root = str(Path(__file__).parent.parent.parent)

    with tempfile.TemporaryDirectory() as tmp:
        _make_store(tmp, project_root)
        args_list = [[project_root, tmp] for _ in range(n_workers)]
        raw = _run_workers(_worker_concurrent_read, args_list, n_workers)

    ok = raw.count("ok")
    errors = [r for r in raw if r not in ("ok", "none")]

    passed = ok == n_workers and not errors
    return StressResult(
        scenario="stress_reads_under_load",
        passed=passed,
        detail=f"{n_workers} readers: {ok} ok, {len(errors)} errors",
        extra={"raw": raw},
    )


# ---------------------------------------------------------------------------
# Scenario 8: DB busy contention — concurrent writes handled by WAL mode
# ---------------------------------------------------------------------------

def stress_db_busy_contention(n_workers: int = 16) -> StressResult:
    """N concurrent rate-limit writes must all complete (WAL handles contention)."""
    project_root = str(Path(__file__).parent.parent.parent)

    with tempfile.TemporaryDirectory() as tmp:
        _make_store(tmp, project_root)
        # Each worker uses a unique agent_id to avoid hitting the rate limit cap
        args_list = [
            [project_root, tmp, f"stress-busy-agent-{i}"]
            for i in range(n_workers)
        ]
        raw = _run_workers(_worker_concurrent_write, args_list, n_workers)

    completed = [r for r in raw if r in ("allowed", "blocked")]
    errors = [r for r in raw if r not in ("allowed", "blocked")]

    passed = len(completed) == n_workers and not errors
    return StressResult(
        scenario="stress_db_busy_contention",
        passed=passed,
        detail=(
            f"{n_workers} concurrent writers: {len(completed)} completed, "
            f"{len(errors)} errors"
        ),
        extra={"raw": raw},
    )


# ---------------------------------------------------------------------------
# run_all aggregator
# ---------------------------------------------------------------------------

def run_all() -> dict[str, Any]:
    """Run all stress scenarios and return aggregated results (advisory only)."""
    scenarios = [
        stress_lease_race,
        stress_rate_limit_concurrency,
        stress_token_revoke_mid_session,
        stress_token_expire_mid_session,
        stress_expired_lease_reclaim,
        stress_replay_path_guard,
        stress_reads_under_load,
        stress_db_busy_contention,
    ]
    results = []
    for fn in scenarios:
        try:
            results.append(fn())
        except Exception as exc:
            results.append(StressResult(
                scenario=fn.__name__,
                passed=False,
                detail=f"scenario raised: {exc}",
            ))

    passed = sum(1 for r in results if r.passed)
    failed = sum(1 for r in results if not r.passed)
    return {
        "total": len(results),
        "passed": passed,
        "failed": failed,
        "stress_pass_is_not_permission": True,
        "authority": STRESS_AUTHORITY,
        "results": [
            {
                "scenario": r.scenario,
                "passed": r.passed,
                "detail": r.detail,
                "stress_pass_is_not_permission": r.stress_pass_is_not_permission,
                "authority": r.authority,
            }
            for r in results
        ],
    }
