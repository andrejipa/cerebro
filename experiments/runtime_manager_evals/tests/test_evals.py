"""Tests for runtime_manager_evals deterministic evaluators."""
from __future__ import annotations

import unittest
from experiments.runtime_manager_evals.eval_trace_invariants import eval_trace_invariants
from experiments.runtime_manager_evals.eval_metrics_invariants import eval_metrics_invariants
from experiments.runtime_manager_evals.eval_replay_invariants import eval_replay_invariants


VALID_TRACE = {
    "trace_id": "rt-abc123",
    "operation": "run",
    "started_at": "2026-05-08T20:00:00Z",
    "duration_ms": 250,
    "outcome": "ok",
    "trace_is_not_permission": True,
}

VALID_METRICS = {
    "runs_total": 2,
    "runs_passed": 1,
    "runs_failed": 1,
    "execution_evidence_total": 2,
    "traces_total": 5,
    "leases_active": 0,
    "stop_conditions_active": 0,
    "validations_green": 0,
}

VALID_REPLAY = {
    "scenario_id": "test-scenario",
    "passed": True,
    "replay_digest": "sha256:abc123",
    "checks": [{"check_id": "chk-1", "passed": True}],
    "authority": "runtime replay evidence only; not permission",
}


class TraceInvariantEvalTests(unittest.TestCase):
    def test_valid_trace_passes(self):
        result = eval_trace_invariants([VALID_TRACE])
        self.assertTrue(result.passed)

    def test_eval_markers_are_always_true(self):
        result = eval_trace_invariants([])
        self.assertTrue(result.eval_is_not_permission)
        self.assertTrue(result.eval_pass_is_not_execution_approval)
        self.assertTrue(result.finding_is_not_truth)
        self.assertTrue(result.must_not_execute_automatically)

    def test_missing_required_field_is_finding(self):
        bad = {k: v for k, v in VALID_TRACE.items() if k != "operation"}
        result = eval_trace_invariants([bad])
        self.assertFalse(result.passed)
        self.assertIn("missing_required_field", {f.code for f in result.findings})

    def test_missing_non_permission_marker_is_finding(self):
        bad = {**VALID_TRACE, "trace_is_not_permission": False}
        result = eval_trace_invariants([bad])
        self.assertFalse(result.passed)
        self.assertIn("missing_non_permission_marker", {f.code for f in result.findings})

    def test_invalid_outcome_is_finding(self):
        bad = {**VALID_TRACE, "outcome": "approved"}
        result = eval_trace_invariants([bad])
        self.assertFalse(result.passed)
        self.assertIn("invalid_outcome", {f.code for f in result.findings})

    def test_duplicate_trace_id_is_finding(self):
        result = eval_trace_invariants([VALID_TRACE, VALID_TRACE])
        self.assertFalse(result.passed)
        self.assertIn("duplicate_trace_id", {f.code for f in result.findings})

    def test_empty_trace_list_passes(self):
        self.assertTrue(eval_trace_invariants([]).passed)


class MetricsInvariantEvalTests(unittest.TestCase):
    def test_valid_metrics_passes(self):
        self.assertTrue(eval_metrics_invariants(VALID_METRICS).passed)

    def test_eval_markers_are_always_true(self):
        r = eval_metrics_invariants({})
        self.assertTrue(r.eval_is_not_permission)
        self.assertTrue(r.eval_pass_is_not_execution_approval)
        self.assertTrue(r.must_not_execute_automatically)

    def test_missing_field_is_finding(self):
        bad = {k: v for k, v in VALID_METRICS.items() if k != "runs_total"}
        self.assertFalse(eval_metrics_invariants(bad).passed)

    def test_runs_sum_exceeds_total_is_finding(self):
        bad = {**VALID_METRICS, "runs_passed": 3, "runs_failed": 3, "runs_total": 2}
        r = eval_metrics_invariants(bad)
        self.assertFalse(r.passed)
        self.assertIn("runs_sum_exceeds_total", {f.code for f in r.findings})

    def test_negative_metric_is_finding(self):
        bad = {**VALID_METRICS, "leases_active": -1}
        r = eval_metrics_invariants(bad)
        self.assertFalse(r.passed)
        self.assertIn("negative_metric", {f.code for f in r.findings})


class ReplayInvariantEvalTests(unittest.TestCase):
    def test_valid_replay_passes(self):
        self.assertTrue(eval_replay_invariants(VALID_REPLAY).passed)

    def test_eval_markers_are_always_true(self):
        r = eval_replay_invariants({})
        self.assertTrue(r.eval_is_not_permission)
        self.assertTrue(r.replay_pass_is_not_truth)
        self.assertTrue(r.replay_pass_is_not_execution_approval)
        self.assertTrue(r.must_not_execute_automatically)

    def test_missing_field_is_finding(self):
        bad = {k: v for k, v in VALID_REPLAY.items() if k != "scenario_id"}
        self.assertFalse(eval_replay_invariants(bad).passed)

    def test_invalid_digest_format_is_finding(self):
        bad = {**VALID_REPLAY, "replay_digest": "md5:abc"}
        r = eval_replay_invariants(bad)
        self.assertFalse(r.passed)
        self.assertIn("invalid_digest_format", {f.code for f in r.findings})

    def test_duplicate_check_id_is_finding(self):
        bad = {**VALID_REPLAY, "checks": [{"check_id": "c", "passed": True}, {"check_id": "c", "passed": False}]}
        r = eval_replay_invariants(bad)
        self.assertFalse(r.passed)
        self.assertIn("duplicate_check_id", {f.code for f in r.findings})

    def test_check_missing_passed_is_finding(self):
        bad = {**VALID_REPLAY, "checks": [{"check_id": "c"}]}
        r = eval_replay_invariants(bad)
        self.assertFalse(r.passed)
        self.assertIn("check_missing_passed", {f.code for f in r.findings})


class AdapterSafetyEvalTests(unittest.TestCase):
    """Tests for eval_adapter_safety evaluators."""

    def setUp(self):
        from experiments.runtime_manager_evals.eval_adapter_safety import (
            eval_adapter_no_direct_sql,
            eval_adapter_no_argv_acceptance,
            eval_adapter_no_external_sdk,
            eval_replay_result_is_not_permission,
            eval_metrics_result_is_not_permission,
            eval_no_secret_in_trace_export,
            eval_approval_requires_fingerprint,
            eval_adapter_safety,
        )
        self.eval_sql = eval_adapter_no_direct_sql
        self.eval_argv = eval_adapter_no_argv_acceptance
        self.eval_sdk = eval_adapter_no_external_sdk
        self.eval_replay = eval_replay_result_is_not_permission
        self.eval_metrics = eval_metrics_result_is_not_permission
        self.eval_secret = eval_no_secret_in_trace_export
        self.eval_fp = eval_approval_requires_fingerprint
        self.eval_all = eval_adapter_safety

    def test_clean_source_passes_sql_check(self):
        findings = self.eval_sql("from core.runtime_manager_store import RuntimeManagerStore\n")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_sqlite_connect_fails_sql_check(self):
        findings = self.eval_sql("sqlite3.connect('db.sqlite')\n")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_clean_source_passes_argv_check(self):
        findings = self.eval_argv("def run_op(command_id: str) -> None: pass\n")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_argv_param_fails_argv_check(self):
        findings = self.eval_argv("def run(argv): pass\n")  # (argv) pattern
        self.assertFalse(all(f["passed"] for f in findings))

    def test_clean_source_passes_sdk_check(self):
        findings = self.eval_sdk("import dataclasses\nfrom core.runtime_manager_store import RuntimeManagerStore\n")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_mcp_import_fails_sdk_check(self):
        findings = self.eval_sdk("import mcp\n")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_langchain_import_fails_sdk_check(self):
        findings = self.eval_sdk("from langchain import something\n")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_replay_with_authority_passes(self):
        replay = {"passed": True, "authority": "runtime replay evidence only; not permission"}
        findings = self.eval_replay(replay)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_replay_without_authority_fails(self):
        replay = {"passed": True}
        findings = self.eval_replay(replay)
        self.assertFalse(all(f["passed"] for f in findings))

    def test_metrics_with_marker_passes(self):
        metrics = {"runs_total": 0, "metrics_is_not_permission": True}
        findings = self.eval_metrics(metrics)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_metrics_without_marker_fails(self):
        metrics = {"runs_total": 0}
        findings = self.eval_metrics(metrics)
        self.assertFalse(all(f["passed"] for f in findings))

    def test_no_secret_in_clean_trace_passes(self):
        findings = self.eval_secret("normal trace content without secrets", ["MY_SECRET"])
        self.assertTrue(all(f["passed"] for f in findings))

    def test_secret_in_trace_fails(self):
        findings = self.eval_secret("trace with MY_SECRET inside", ["MY_SECRET"])
        self.assertFalse(all(f["passed"] for f in findings))

    def test_approval_with_fingerprint_passes(self):
        findings = self.eval_fp({"action_fingerprint": "sha256:deadbeef"})
        self.assertTrue(all(f["passed"] for f in findings))

    def test_approval_without_fingerprint_fails(self):
        findings = self.eval_fp({"action_fingerprint": ""})
        self.assertFalse(all(f["passed"] for f in findings))

    def test_aggregator_all_passed_clean_inputs(self):
        clean_source = "from core.runtime_manager_store import RuntimeManagerStore\n"
        replay = {"passed": True, "authority": "runtime replay evidence only; not permission"}
        metrics = {"runs_total": 0, "metrics_is_not_permission": True}
        result = self.eval_all(
            adapter_module_source=clean_source,
            replay_result=replay,
            metrics_result=metrics,
        )
        self.assertTrue(result["all_passed"])
        self.assertTrue(result["eval_adapter_safety_is_not_permission"])

    def test_aggregator_fails_on_bad_source(self):
        bad_source = "sqlite3.connect('db')\nimport mcp\n"
        result = self.eval_all(adapter_module_source=bad_source)
        self.assertFalse(result["all_passed"])


class McpSafetyEvalTests(unittest.TestCase):
    """Tests for eval_mcp_safety evaluators."""

    def setUp(self):
        from experiments.runtime_manager_evals.eval_mcp_safety import (
            eval_mcp_no_http_socket,
            eval_mcp_no_direct_sql,
            eval_mcp_no_token_in_output,
            eval_mcp_no_argv,
            eval_mcp_approval_not_exposed,
            eval_mcp_scopes_enforced,
            eval_mcp_only_mcp_sdk,
            eval_mcp_rate_limit_before_store,
            eval_mcp_token_from_env_only,
            eval_mcp_not_permission_markers,
            eval_mcp_replay_path_guard,
            eval_mcp_safety,
        )
        self.no_http = eval_mcp_no_http_socket
        self.no_sql = eval_mcp_no_direct_sql
        self.no_token_out = eval_mcp_no_token_in_output
        self.no_argv = eval_mcp_no_argv
        self.no_approval = eval_mcp_approval_not_exposed
        self.scopes = eval_mcp_scopes_enforced
        self.only_mcp = eval_mcp_only_mcp_sdk
        self.rate = eval_mcp_rate_limit_before_store
        self.env_only = eval_mcp_token_from_env_only
        self.not_perm = eval_mcp_not_permission_markers
        self.path_guard = eval_mcp_replay_path_guard
        self.aggregator = eval_mcp_safety

    # -- no_http_socket --

    def test_clean_source_passes_http_check(self):
        findings = self.no_http("app.run(transport='stdio')")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_http_server_fails_http_check(self):
        findings = self.no_http("HTTPServer(('', 8080), handler)")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_socket_listen_fails_http_check(self):
        findings = self.no_http("s.socket.listen(5)")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- no_direct_sql --

    def test_clean_source_passes_sql_check(self):
        findings = self.no_sql("store.read_status()")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_sqlite_connect_fails_sql_check(self):
        findings = self.no_sql("sqlite3.connect('runtime.db')")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- no_token_in_output --

    def test_clean_source_passes_token_output_check(self):
        findings = self.no_token_out("return {'status': 'ok'}")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_raw_token_field_fails(self):
        findings = self.no_token_out('return {"token": raw_token}')
        self.assertFalse(all(f["passed"] for f in findings))

    # -- no_argv --

    def test_clean_source_passes_argv_check(self):
        findings = self.no_argv("def runtime_run_command(command_id: str, lease_id: str) -> dict:")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_argv_param_fails_argv_check(self):
        findings = self.no_argv("def run(argv): pass")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_shell_true_fails_argv_check(self):
        findings = self.no_argv("subprocess.run(cmd, shell=True)")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- approval_not_exposed --

    def test_no_approval_tool_passes(self):
        findings = self.no_approval("def runtime_run_command(command_id: str) -> dict: pass")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_approval_tool_def_fails(self):
        findings = self.no_approval("def runtime_record_approval(obs_id: str) -> dict: pass")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- scopes_enforced --

    def test_scopes_with_require_scope_passes(self):
        src = "\n".join(["require_scope(scopes, SCOPE_READ)"] * 12) + "\nfrom scopes import require_scope\n"
        findings = self.scopes(src)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_missing_require_scope_fails(self):
        findings = self.scopes("def tool(): pass")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- only_mcp_sdk --

    def test_only_mcp_import_passes(self):
        findings = self.only_mcp("from mcp.server.fastmcp import FastMCP")
        self.assertTrue(all(f["passed"] for f in findings))

    def test_langchain_import_fails(self):
        findings = self.only_mcp("from langchain import something")
        self.assertFalse(all(f["passed"] for f in findings))

    def test_openai_import_fails(self):
        findings = self.only_mcp("from openai import OpenAI")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- rate_limit_before_store --

    def test_rate_helper_present_passes(self):
        src = "def tool():\n" + "    _rate('op')\n" * 12 + "    store.read_status()\n"
        findings = self.rate(src)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_missing_rate_helper_fails(self):
        findings = self.rate("def tool(): store.read_status()")
        self.assertFalse(all(f["passed"] for f in findings))

    # -- token_from_env --

    def test_env_var_in_auth_passes(self):
        src = "ENV_VAR = 'CEREBRO_RUNTIME_MCP_TOKEN'\nos.environ.get(ENV_VAR)"
        findings = self.env_only(src)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_argv_in_auth_fails(self):
        src = "CEREBRO_RUNTIME_MCP_TOKEN = 'x'\nos.environ.get('x')\nimport argparse\n"
        findings = self.env_only(src)
        self.assertFalse(all(f["passed"] for f in findings))

    # -- not_permission_markers --

    def test_three_not_permission_markers_passes(self):
        src = '"not_permission": True\n' * 3
        findings = self.not_perm(src)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_two_not_permission_markers_fails(self):
        src = '"not_permission": True\n' * 2
        findings = self.not_perm(src)
        self.assertFalse(all(f["passed"] for f in findings))

    # -- replay_path_guard --

    def test_path_guard_passes_with_root_anchoring(self):
        src = (
            "resolved = (store.root / scenario_path).resolve()\n"
            "if not resolved.is_relative_to(store.root.resolve()):\n"
            "    raise ValueError('must resolve inside')\n"
        )
        findings = self.path_guard(src)
        self.assertTrue(all(f["passed"] for f in findings))

    def test_path_guard_fails_without_is_relative_to(self):
        src = (
            "safe = Path(scenario_path)\n"
            "if safe.is_absolute() or '..' in safe.parts:\n"
            "    raise ValueError('bad path')\n"
        )
        findings = self.path_guard(src)
        self.assertFalse(all(f["passed"] for f in findings))

    def test_path_guard_fails_without_store_root(self):
        src = (
            "resolved = Path(scenario_path).resolve()\n"
            "if not resolved.is_relative_to(base_dir):\n"
            "    raise ValueError('bad path')\n"
        )
        findings = self.path_guard(src)
        failed = [f for f in findings if not f["passed"]]
        self.assertTrue(any("store.root" in f["detail"] for f in failed))

    # -- aggregator --

    def test_aggregator_runs_without_error(self):
        result = self.aggregator()
        self.assertIn("eval_mcp_safety_is_not_permission", result)
        self.assertTrue(result["eval_mcp_safety_is_not_permission"])
        self.assertIn("findings", result)
        self.assertIn("total", result)
        self.assertIn("passed", result)

    def test_aggregator_all_checks_pass_on_real_server(self):
        result = self.aggregator()
        failed = [f for f in result["findings"] if not f["passed"]]
        self.assertEqual(failed, [], msg=f"Failed MCP safety checks:\n" + "\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))


class AutonomyLevelEvalTests(unittest.TestCase):
    """Tests for eval_autonomy_levels evaluators."""

    def setUp(self):
        from experiments.runtime_manager_evals.eval_autonomy_levels import (
            eval_l0_read_only,
            eval_l1_derived_write,
            eval_l2_local_code,
            eval_l3_runtime_mutation,
            eval_l4_external_elevators,
            eval_override_only_increases_level,
            eval_classification_is_not_permission,
            eval_mcp_never_executes_l4,
            eval_explain_levels_completeness,
            run_all,
        )
        self.eval_l0 = eval_l0_read_only
        self.eval_l1 = eval_l1_derived_write
        self.eval_l2 = eval_l2_local_code
        self.eval_l3 = eval_l3_runtime_mutation
        self.eval_l4 = eval_l4_external_elevators
        self.eval_override = eval_override_only_increases_level
        self.eval_not_perm = eval_classification_is_not_permission
        self.eval_mcp_l4 = eval_mcp_never_executes_l4
        self.eval_explain = eval_explain_levels_completeness
        self.run_all = run_all

    def test_l0_all_pass(self):
        findings = self.eval_l0()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_l1_all_pass(self):
        findings = self.eval_l1()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_l2_all_pass(self):
        findings = self.eval_l2()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_l3_all_pass(self):
        findings = self.eval_l3()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_l4_all_pass(self):
        findings = self.eval_l4()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_override_all_pass(self):
        findings = self.eval_override()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_not_permission_markers_all_pass(self):
        findings = self.eval_not_perm()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_mcp_never_executes_l4_all_pass(self):
        findings = self.eval_mcp_l4()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_explain_levels_all_pass(self):
        findings = self.eval_explain()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_run_all_returns_eval_is_not_permission(self):
        result = self.run_all()
        self.assertTrue(result["eval_is_not_permission"])

    def test_run_all_no_failures(self):
        result = self.run_all()
        failed = [f for f in result["findings"] if not f["passed"]]
        self.assertEqual(failed, [], msg="\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))


class Phase9ConcurrencyAuthEvalTests(unittest.TestCase):
    """Tests for eval_phase9_concurrency_auth evaluators."""

    def setUp(self):
        from experiments.runtime_manager_evals.eval_phase9_concurrency_auth import (
            eval_mcp_per_call_auth_exists,
            eval_mcp_no_http_phase9,
            eval_persistent_rate_limit_not_in_memory_only,
            eval_lease_contention_sqlite_backed,
            eval_token_revocation_mid_session,
            eval_no_token_in_outputs,
            run_all,
        )
        self.per_call_auth = eval_mcp_per_call_auth_exists
        self.no_http = eval_mcp_no_http_phase9
        self.rate_persistent = eval_persistent_rate_limit_not_in_memory_only
        self.lease_sqlite = eval_lease_contention_sqlite_backed
        self.revocation = eval_token_revocation_mid_session
        self.no_token_out = eval_no_token_in_outputs
        self.run_all = run_all

    def test_per_call_auth_all_pass(self):
        findings = self.per_call_auth()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_per_call_auth_not_permission_marker(self):
        findings = self.per_call_auth()
        self.assertTrue(all(f["eval_is_not_permission"] for f in findings))

    def test_no_http_phase9_all_pass(self):
        findings = self.no_http()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_rate_limit_persistent_all_pass(self):
        findings = self.rate_persistent()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_lease_contention_sqlite_all_pass(self):
        findings = self.lease_sqlite()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_token_revocation_mid_session_all_pass(self):
        findings = self.revocation()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg="\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))

    def test_no_token_in_outputs_all_pass(self):
        findings = self.no_token_out()
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg=str(failed))

    def test_run_all_returns_eval_is_not_permission(self):
        result = self.run_all()
        self.assertTrue(result["eval_is_not_permission"])

    def test_run_all_no_failures(self):
        result = self.run_all()
        failed = [f for f in result["findings"] if not f["passed"]]
        self.assertEqual(failed, [], msg="\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))


class Phase10HardeningEvalTests(unittest.TestCase):
    """Tests for eval_phase10_hardening evaluators."""

    def setUp(self) -> None:
        from experiments.runtime_manager_evals.eval_phase10_hardening import (
            eval_stress_pass_is_not_permission,
            eval_integrity_report_is_not_permission,
            eval_metrics_not_authority,
            eval_trace_retains_no_secret,
            eval_replay_path_guard,
            eval_l4_still_blocked,
            eval_token_revoked_blocks_next_call,
            eval_level_block_counter_covers_all_tools,
            run_all,
        )
        self.stress_not_perm = eval_stress_pass_is_not_permission
        self.integrity_not_perm = eval_integrity_report_is_not_permission
        self.metrics_not_auth = eval_metrics_not_authority
        self.trace_no_secret = eval_trace_retains_no_secret
        self.replay_path = eval_replay_path_guard
        self.l4_blocked = eval_l4_still_blocked
        self.token_revoked = eval_token_revoked_blocks_next_call
        self.level_counter = eval_level_block_counter_covers_all_tools
        self.run_all = run_all

    def _assert_all_pass(self, findings: list) -> None:
        failed = [f for f in findings if not f["passed"]]
        self.assertEqual(failed, [], msg="\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))

    def test_stress_pass_is_not_permission_all_pass(self) -> None:
        self._assert_all_pass(self.stress_not_perm())

    def test_integrity_report_is_not_permission_all_pass(self) -> None:
        self._assert_all_pass(self.integrity_not_perm())

    def test_metrics_not_authority_all_pass(self) -> None:
        self._assert_all_pass(self.metrics_not_auth())

    def test_trace_retains_no_secret_all_pass(self) -> None:
        self._assert_all_pass(self.trace_no_secret())

    def test_replay_path_guard_all_pass(self) -> None:
        self._assert_all_pass(self.replay_path())

    def test_l4_still_blocked_all_pass(self) -> None:
        self._assert_all_pass(self.l4_blocked())

    def test_token_revoked_blocks_next_call_all_pass(self) -> None:
        self._assert_all_pass(self.token_revoked())

    def test_level_block_counter_covers_all_tools_all_pass(self) -> None:
        self._assert_all_pass(self.level_counter())

    def test_run_all_returns_eval_is_not_permission(self) -> None:
        result = self.run_all()
        self.assertTrue(result["eval_is_not_permission"])

    def test_run_all_no_failures(self) -> None:
        result = self.run_all()
        failed = [f for f in result["findings"] if not f["passed"]]
        self.assertEqual(failed, [], msg="\n".join(
            f"  {f['check']}: {f['detail']}" for f in failed
        ))


if __name__ == "__main__":
    unittest.main()
