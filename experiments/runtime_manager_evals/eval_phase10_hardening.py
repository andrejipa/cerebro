"""eval_phase10_hardening -- Phase 10 invariant checks for local-only hardening.

Evaluators verify:
  1. stress_pass_is_not_permission marker on all StressResult objects
  2. integrity_report_is_not_permission on RuntimeIntegrityReport
  3. metrics objects carry not-authority markers
  4. traces retain no raw token / stdout / stderr
  5. replay path guard rejects out-of-scope paths
  6. L4 is still unconditionally blocked via MCP
  7. token_revoked_mid_session blocks the next call
  8. mcp_level_blocked counter incremented by all tools, not just run_command

NOT a runtime gate, NOT permission, NOT execution approval.
All evaluator functions return a list of finding dicts.

eval_phase10_hardening_is_not_permission = True (always)
"""
from __future__ import annotations

import inspect
from typing import Any

EVAL_AUTHORITY = "phase10 hardening eval only; not permission, not a runtime gate"
eval_phase10_hardening_is_not_permission = True


def _finding(check: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "check": check,
        "passed": passed,
        "detail": detail,
        "eval_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
    }


def _server_source() -> str:
    try:
        import adapters.runtime_manager_mcp_stdio.server as mod
        return inspect.getsource(mod)
    except Exception as exc:
        return f"__import_error__: {exc}"


def _store_source() -> str:
    try:
        import core.runtime_manager_store as mod
        return inspect.getsource(mod)
    except Exception as exc:
        return f"__import_error__: {exc}"


# ---------------------------------------------------------------------------
# Evaluator 1: stress_pass_is_not_permission on StressResult
# ---------------------------------------------------------------------------

def eval_stress_pass_is_not_permission() -> list[dict[str, Any]]:
    """Every StressResult must carry stress_pass_is_not_permission=True."""
    findings = []

    try:
        from experiments.runtime_manager_stress_lab.scenarios import (
            StressResult, stress_token_revoke_mid_session
        )

        r = StressResult(scenario="eval-dummy", passed=True, detail="eval check")
        findings.append(_finding(
            "stress_result_not_permission_field",
            r.stress_pass_is_not_permission is True,
            "StressResult must default stress_pass_is_not_permission=True",
        ))
        findings.append(_finding(
            "stress_result_advisory_authority",
            r.authority == "advisory/local stress only",
            f"StressResult.authority must be 'advisory/local stress only'; got {r.authority!r}",
        ))

        # Run a fast in-process scenario
        result = stress_token_revoke_mid_session()
        findings.append(_finding(
            "stress_revoke_scenario_not_permission",
            result.stress_pass_is_not_permission is True,
            "stress_token_revoke_mid_session result must carry stress_pass_is_not_permission=True",
        ))
    except Exception as exc:
        findings.append(_finding("stress_result_eval_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 2: integrity_report_is_not_permission on RuntimeIntegrityReport
# ---------------------------------------------------------------------------

def eval_integrity_report_is_not_permission() -> list[dict[str, Any]]:
    """RuntimeIntegrityReport must carry integrity_report_is_not_permission=True."""
    findings = []

    try:
        import tempfile
        from pathlib import Path
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RuntimeManagerStore(root)
            store.initialize_schema()
            obs_path = root / "docs" / "operations" / "observation_center.toml"
            obs_path.parent.mkdir(parents=True, exist_ok=True)
            obs_path.write_text("[center]\nversion = 1\n", encoding="utf-8")
            store.sync_observation_center(obs_path)
            report = store.check_integrity()

            findings.append(_finding(
                "integrity_report_not_permission_field",
                report.integrity_report_is_not_permission is True,
                "RuntimeIntegrityReport must carry integrity_report_is_not_permission=True",
            ))
            findings.append(_finding(
                "integrity_report_has_generated_at",
                bool(report.generated_at),
                "RuntimeIntegrityReport must include generated_at timestamp",
            ))
            findings.append(_finding(
                "integrity_report_issues_is_tuple",
                isinstance(report.issues, tuple),
                "RuntimeIntegrityReport.issues must be a tuple",
            ))

    except Exception as exc:
        findings.append(_finding("integrity_eval_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 3: metrics not authority
# ---------------------------------------------------------------------------

def eval_metrics_not_authority() -> list[dict[str, Any]]:
    """read_metrics must not return an object that grants authority."""
    findings = []
    store_src = _store_source()

    findings.append(_finding(
        "metrics_not_authority_in_source",
        "metrics_is_not_permission" in store_src,
        "RuntimeManagerMetrics must carry metrics_is_not_permission=True sentinel",
    ))

    # The RuntimeManagerMetrics dataclass must not have any 'is_permission' field
    try:
        import core.runtime_manager_store as store_mod
        metrics_src = inspect.getsource(store_mod.RuntimeManagerMetrics)
        findings.append(_finding(
            "metrics_dataclass_no_permission_grant",
            "is_permission = True" not in metrics_src,
            "RuntimeManagerMetrics must not contain a 'is_permission=True' field",
        ))
    except Exception as exc:
        findings.append(_finding("metrics_source_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 4: trace retains no token / stdout / stderr
# ---------------------------------------------------------------------------

def eval_trace_retains_no_secret() -> list[dict[str, Any]]:
    """Traces must not store raw token, stdout, or stderr."""
    findings = []
    store_src = _store_source()

    # runtime_traces table must not have stdout/stderr columns
    findings.append(_finding(
        "trace_table_no_stdout_column",
        '"stdout"' not in store_src.split("CREATE TABLE IF NOT EXISTS runtime_traces")[1].split("CREATE TABLE")[0]
        if "CREATE TABLE IF NOT EXISTS runtime_traces" in store_src else True,
        "runtime_traces table must not have a stdout column",
    ))

    # _record_operation_trace must not include stdout or raw_token in payload
    try:
        import core.runtime_manager_store as store_mod
        trace_fn_src = inspect.getsource(store_mod.RuntimeManagerStore._record_operation_trace)
        findings.append(_finding(
            "record_trace_no_raw_token",
            "raw_token" not in trace_fn_src,
            "_record_operation_trace must not include raw_token in payload",
        ))
        findings.append(_finding(
            "record_trace_no_stdout",
            "stdout" not in trace_fn_src,
            "_record_operation_trace must not log stdout",
        ))
    except Exception as exc:
        findings.append(_finding("trace_fn_source_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 5: replay path guard rejects out-of-scope paths
# ---------------------------------------------------------------------------

def eval_replay_path_guard() -> list[dict[str, Any]]:
    """replay_scenario via MCP must reject scenario_path outside the project root."""
    findings = []
    server_src = _server_source()

    findings.append(_finding(
        "replay_path_out_of_scope_code_present",
        "replay_path_out_of_scope" in server_src,
        "MCP server must raise with replay_path_out_of_scope for path traversal",
    ))
    findings.append(_finding(
        "replay_path_relative_to_check",
        "is_relative_to" in server_src,
        "MCP server must use is_relative_to() to enforce path scope",
    ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 6: L4 still unconditionally blocked via MCP
# ---------------------------------------------------------------------------

def eval_l4_still_blocked() -> list[dict[str, Any]]:
    """L4_external_high_risk must be unconditionally blocked regardless of token level."""
    findings = []
    server_src = _server_source()

    findings.append(_finding(
        "l4_unconditionally_blocked_in_check_level",
        "L4_external_high_risk" in server_src and "unconditionally" in server_src,
        "_check_level must reference L4_external_high_risk and state it is unconditionally blocked",
    ))

    try:
        import tempfile
        from pathlib import Path
        from core.runtime_manager_store import RuntimeManagerStore
        from adapters.runtime_manager_mcp_stdio.server import _check_level

        raised = False
        try:
            _check_level("L4_external_high_risk", "L4_external_high_risk")
        except PermissionError as exc:
            raised = True
            findings.append(_finding(
                "l4_raises_permission_error",
                raised,
                f"_check_level must raise PermissionError for L4; got: {exc!s:.80}",
            ))
    except Exception as exc:
        findings.append(_finding("l4_eval_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 7: token_revoked_mid_session blocks next call
# ---------------------------------------------------------------------------

def eval_token_revoked_blocks_next_call() -> list[dict[str, Any]]:
    """After revocation, _require_current_token_factory must raise PermissionError."""
    findings = []

    try:
        import tempfile
        from pathlib import Path
        from core.runtime_manager_store import RuntimeManagerStore
        from adapters.runtime_manager_mcp_stdio.server import _require_current_token_factory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RuntimeManagerStore(root)
            store.initialize_schema()

            token_record, raw = store.issue_adapter_token(
                agent_id="eval-revoke-p10",
                agent_role="runner",
                scopes=["runtime:read"],
                ttl_seconds=3600,
            )
            require_fn = _require_current_token_factory(store, raw)

            # Before revocation: must succeed
            try:
                require_fn("runtime:read", "L0_observe")
                before_ok = True
            except Exception:
                before_ok = False
            findings.append(_finding(
                "token_valid_before_revocation",
                before_ok,
                "require_fn must succeed before revocation",
            ))

            store.revoke_adapter_token(token_record.token_id)

            # After revocation: must raise PermissionError with correct code
            raised = False
            code_ok = False
            try:
                require_fn("runtime:read", "L0_observe")
            except PermissionError as exc:
                raised = True
                code_ok = "token_revoked_mid_session" in str(exc)

            findings.append(_finding(
                "token_revoked_blocks_next_call",
                raised and code_ok,
                f"require_fn must raise PermissionError(token_revoked_mid_session) after revocation; raised={raised} code_ok={code_ok}",
            ))

    except Exception as exc:
        findings.append(_finding("token_revoke_eval_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 8: mcp_level_blocked counter covers all tools via factory
# ---------------------------------------------------------------------------

def eval_level_block_counter_covers_all_tools() -> list[dict[str, Any]]:
    """mcp_level_blocked must be incremented inside _require_current_token_factory."""
    findings = []
    server_src = _server_source()

    # Locate the factory function body
    try:
        factory_start = server_src.index("def _require_current_token_factory")
        build_start = server_src.index("def build_app", factory_start)
        factory_body = server_src[factory_start:build_start]

        findings.append(_finding(
            "mcp_level_blocked_in_factory_body",
            'increment_policy_counter("mcp_level_blocked")' in factory_body,
            "_require_current_token_factory body must call increment_policy_counter('mcp_level_blocked')",
        ))
        findings.append(_finding(
            "factory_catches_permission_error_and_reraises",
            "except PermissionError" in factory_body and "raise" in factory_body,
            "_require_current_token_factory must catch PermissionError, increment counter, and re-raise",
        ))
    except (ValueError, Exception) as exc:
        findings.append(_finding("factory_body_parse_error", False, f"error: {exc}"))

    # Also verify that level-block counter is incremented in functional test
    try:
        import tempfile
        from pathlib import Path
        from core.runtime_manager_store import RuntimeManagerStore
        from adapters.runtime_manager_mcp_stdio.server import _require_current_token_factory

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RuntimeManagerStore(root)
            store.initialize_schema()

            _token_record, raw = store.issue_adapter_token(
                agent_id="eval-level-block",
                agent_role="runner",
                scopes=["runtime:execute"],
                ttl_seconds=3600,
                max_autonomy_level="L1_derived",
            )
            require_fn = _require_current_token_factory(store, raw)

            before_count = store.read_policy_counter("mcp_level_blocked")

            try:
                require_fn("runtime:execute", "L3_runtime_mutation")
            except PermissionError:
                pass

            after_count = store.read_policy_counter("mcp_level_blocked")

            findings.append(_finding(
                "mcp_level_blocked_incremented_functionally",
                after_count == before_count + 1,
                f"mcp_level_blocked counter must increment on level block; before={before_count} after={after_count}",
            ))

    except Exception as exc:
        findings.append(_finding("level_block_functional_error", False, f"error: {exc}"))

    return findings


# ---------------------------------------------------------------------------
# run_all aggregator
# ---------------------------------------------------------------------------

def run_all() -> dict[str, Any]:
    """Run all Phase 10 hardening evaluators and return aggregated results."""
    all_findings: list[dict[str, Any]] = []

    for fn in [
        eval_stress_pass_is_not_permission,
        eval_integrity_report_is_not_permission,
        eval_metrics_not_authority,
        eval_trace_retains_no_secret,
        eval_replay_path_guard,
        eval_l4_still_blocked,
        eval_token_revoked_blocks_next_call,
        eval_level_block_counter_covers_all_tools,
    ]:
        try:
            all_findings.extend(fn())
        except Exception as exc:
            all_findings.append(_finding(
                f"{fn.__name__}_error",
                False,
                f"evaluator raised: {exc}",
            ))

    passed = sum(1 for f in all_findings if f["passed"])
    failed = sum(1 for f in all_findings if not f["passed"])

    return {
        "total": len(all_findings),
        "passed": passed,
        "failed": failed,
        "eval_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
        "findings": all_findings,
    }
