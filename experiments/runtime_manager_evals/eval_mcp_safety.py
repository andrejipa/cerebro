"""eval_mcp_safety -- advisory-only safety invariant checks for the MCP STDIO server.

Evaluators inspect the server/tool source to detect safety violations:
  - no HTTP listener, socket, or network binding
  - no direct SQLite calls (only store API)
  - no raw token in trace, logs, or tool output fields
  - no raw argv or shell acceptance in tool signatures
  - record_approval not exposed as MCP tool
  - all scopes enforced via require_scope()
  - only mcp added as external SDK (no langchain, openai, temporal, etc.)
  - rate limit enforced before store call

NOT a runtime gate, NOT permission, NOT execution approval.
All evaluator functions return a list of finding dicts.

eval_mcp_safety_is_not_permission = True (always)
"""
from __future__ import annotations

import importlib
import inspect
from typing import Any

EVAL_AUTHORITY = "mcp safety eval only; not permission, not a runtime gate"


def _finding(check: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "check": check,
        "passed": passed,
        "detail": detail,
        "eval_mcp_safety_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
    }


def _server_source() -> str:
    try:
        import adapters.runtime_manager_mcp_stdio.server as mod
        return inspect.getsource(mod)
    except Exception as exc:
        return f"__import_error__: {exc}"


def _auth_source() -> str:
    try:
        import adapters.runtime_manager_mcp_stdio.auth as mod
        return inspect.getsource(mod)
    except Exception as exc:
        return f"__import_error__: {exc}"


def eval_mcp_no_http_socket(server_source: str) -> list[dict[str, Any]]:
    """MCP server must not open HTTP listeners or raw sockets."""
    findings = []
    forbidden = [
        ("no_http_server", "HTTPServer", "HTTPServer binding"),
        ("no_streamable_http", "streamable-http", "Streamable HTTP transport"),
        ("no_socket_listen", "socket.listen(", "raw socket.listen()"),
        ("no_socket_bind", "socket.bind(", "raw socket.bind()"),
        ("no_tcp_server", "TCPServer", "TCPServer instantiation"),
        ("no_uvicorn", "uvicorn.run(", "uvicorn HTTP server"),
        ("no_aiohttp", "aiohttp.web", "aiohttp web server"),
    ]
    for key, token, label in forbidden:
        passed = token not in server_source
        findings.append(_finding(
            check=f"no_http_socket:{key}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} {label}",
        ))
    return findings


def eval_mcp_no_direct_sql(server_source: str) -> list[dict[str, Any]]:
    """MCP server must not call SQLite directly; only RuntimeManagerStore APIs."""
    findings = []
    forbidden = ["sqlite3.connect(", "connection.execute(", "cursor.execute(", ".executescript("]
    for token in forbidden:
        passed = token not in server_source
        findings.append(_finding(
            check=f"no_direct_sql:{token.strip()}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} forbidden SQL token {token!r}",
        ))
    return findings


def eval_mcp_no_token_in_output(server_source: str) -> list[dict[str, Any]]:
    """Token fields must never appear in tool return values."""
    findings = []
    # Tool output must not include token, password, secret fields
    forbidden = [
        ("no_token_field", '"token"', 'raw "token" key in output dict'),
        ("no_password_field", '"password"', 'raw "password" key in output dict'),
        ("no_secret_field", '"secret"', 'raw "secret" key in output dict'),
        ("no_raw_token_log", "raw_token", "raw_token variable in server output"),
    ]
    # Allow raw_env_token (Phase 9 per-op auth variable) but disallow raw_token as a dict key
    # or direct reference in tool output.  raw_env_token contains "raw_token" as substring,
    # so we check for the dict-key form or explicit raw_token identifier.
    for key, token, label in forbidden:
        if key == "no_raw_token_log":
            # Phase 9: variable is raw_env_token; it should not appear as a string key or be
            # printed/returned as-is.  Accept raw_env_token in function body but reject
            # "raw_token" as a standalone quoted key or in return/print statements.
            bad = ('"raw_token"' in server_source or
                   "print(raw_token" in server_source or
                   "return raw_token" in server_source)
            passed = not bad
        else:
            passed = token not in server_source
        findings.append(_finding(
            check=f"no_token_in_output:{key}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} {label}",
        ))
    return findings


def eval_mcp_no_argv(server_source: str) -> list[dict[str, Any]]:
    """MCP tools must not accept free-form argv or shell parameters."""
    findings = []
    forbidden_patterns = [
        ("no_argv_param", "(argv)", "function accepting (argv)"),
        ("no_argv_param2", ", argv", "function accepting , argv"),
        ("no_shell_true", "shell=True", "shell=True subprocess flag"),
        ("no_raw_command", "raw_command", "raw_command parameter"),
    ]
    for key, token, label in forbidden_patterns:
        passed = token not in server_source
        findings.append(_finding(
            check=f"no_argv:{key}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} {label}",
        ))
    return findings


def eval_mcp_approval_not_exposed(server_source: str) -> list[dict[str, Any]]:
    """record_approval must not be a registered MCP tool."""
    # The server should not define a tool function named runtime_record_approval
    # or call store.record_approval directly from a tool.
    findings = []
    forbidden = [
        ("no_approval_tool_def", "def runtime_record_approval", "MCP tool runtime_record_approval"),
        ("no_approval_tool_def2", "def record_approval", "MCP tool def record_approval"),
    ]
    for key, token, label in forbidden:
        passed = token not in server_source
        findings.append(_finding(
            check=f"approval_not_exposed:{key}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} {label}",
        ))
    # Allowed: store.record_approval might appear in allowed-callers list or comments
    # but if it appears as a decorated @app.tool, that's a violation.
    # We accept the simpler pattern check here since formal tests cover runtime behavior.
    return findings


def eval_mcp_scopes_enforced(server_source: str) -> list[dict[str, Any]]:
    """Each tool should call require_scope before store access."""
    findings = []
    # require_scope must be imported and called
    has_import = "require_scope" in server_source
    findings.append(_finding(
        check="scopes_enforced:require_scope_imported",
        passed=has_import,
        detail=f"server source {'imports' if has_import else 'does NOT import'} require_scope",
    ))
    # Phase 9: require_scope is now called inside _require_current_token_factory (central helper).
    # Each tool calls _require_current_token which delegates scope enforcement.  Accept either:
    #   (a) ≥11 direct require_scope() calls per tool, OR
    #   (b) 1+ require_scope() calls inside a central helper that every tool must call.
    call_count = server_source.count("require_scope(")
    has_central_helper = "_require_current_token" in server_source
    sufficient = call_count >= 11 or (call_count >= 1 and has_central_helper)
    findings.append(_finding(
        check="scopes_enforced:require_scope_call_count",
        passed=sufficient,
        detail=(
            f"server source has {call_count} require_scope() calls"
            + (" via _require_current_token central helper" if has_central_helper else "")
            + f" (need ≥11 direct OR ≥1 via central helper)"
        ),
    ))
    return findings


def eval_mcp_only_mcp_sdk(server_source: str) -> list[dict[str, Any]]:
    """Only mcp is permitted as an external SDK import."""
    findings = []
    forbidden_sdks = [
        ("no_langchain", "langchain", "langchain SDK"),
        ("no_openai", "from openai", "openai SDK"),
        ("no_temporal", "temporalio", "temporal SDK"),
        ("no_langgraph", "langgraph", "langgraph SDK"),
        ("no_cloudflare_agents", "cloudflare_agents", "cloudflare agents SDK"),
        ("no_openai_agents", "openai_agents", "openai agents SDK"),
    ]
    for key, token, label in forbidden_sdks:
        passed = token not in server_source
        findings.append(_finding(
            check=f"only_mcp_sdk:{key}",
            passed=passed,
            detail=f"server source {'does not contain' if passed else 'CONTAINS'} {label}",
        ))
    return findings


def eval_mcp_rate_limit_before_store(server_source: str) -> list[dict[str, Any]]:
    """Rate limit (_rate) must be called before store operations in each tool."""
    findings = []
    has_rate_helper = "_rate(" in server_source
    findings.append(_finding(
        check="rate_limit_enforced:_rate_helper_present",
        passed=has_rate_helper,
        detail=f"server source {'defines' if has_rate_helper else 'MISSING'} _rate() enforcement helper",
    ))
    rate_count = server_source.count("_rate(")
    # One _rate() call per tool (≥11 tools) plus one definition
    sufficient = rate_count >= 12
    findings.append(_finding(
        check="rate_limit_enforced:_rate_call_count",
        passed=sufficient,
        detail=f"server source has {rate_count} _rate() references (need ≥12)",
    ))
    return findings


def eval_mcp_token_from_env_only(auth_source: str) -> list[dict[str, Any]]:
    """Token must come from env var only, never from CLI args or tool parameters."""
    findings = []
    has_env_var = "CEREBRO_RUNTIME_MCP_TOKEN" in auth_source
    findings.append(_finding(
        check="token_from_env:env_var_name",
        passed=has_env_var,
        detail=f"auth source {'contains' if has_env_var else 'MISSING'} CEREBRO_RUNTIME_MCP_TOKEN constant",
    ))
    has_os_environ = "os.environ" in auth_source
    findings.append(_finding(
        check="token_from_env:os_environ_used",
        passed=has_os_environ,
        detail=f"auth source {'uses' if has_os_environ else 'does NOT use'} os.environ for token loading",
    ))
    # sys.argv must not appear in auth
    no_argv = "sys.argv" not in auth_source and "argparse" not in auth_source
    findings.append(_finding(
        check="token_from_env:no_argv_in_auth",
        passed=no_argv,
        detail=f"auth source {'does not use' if no_argv else 'USES'} sys.argv or argparse for token",
    ))
    return findings


def eval_mcp_not_permission_markers(server_source: str) -> list[dict[str, Any]]:
    """Trace, replay, and metrics results must carry not_permission=True."""
    findings = []
    markers = [
        ("trace_not_permission", '"not_permission": True', "trace/replay/metrics not_permission=True marker"),
    ]
    for key, token, label in markers:
        count = server_source.count(token)
        # Should appear at least 3 times (trace_list, trace_show, trace_export, metrics, replay)
        passed = count >= 3
        findings.append(_finding(
            check=f"not_permission_marker:{key}",
            passed=passed,
            detail=f"server source has {count} {label} instances (need ≥3)",
        ))
    return findings


def eval_mcp_replay_path_guard(server_source: str) -> list[dict[str, Any]]:
    """replay_scenario must anchor path inside store.root to prevent traversal."""
    findings = []
    checks = [
        ("root_resolve", "store.root", "path anchored to store.root"),
        ("is_relative_to", "is_relative_to", "is_relative_to() boundary check"),
    ]
    for key, token, label in checks:
        passed = token in server_source
        findings.append(_finding(
            check=f"replay_path_guard:{key}",
            passed=passed,
            detail=f"server source {'contains' if passed else 'MISSING'} {label}",
        ))
    return findings


# ---------------------------------------------------------------------------
# Aggregator
# ---------------------------------------------------------------------------


def eval_mcp_safety() -> dict[str, Any]:
    """Run all MCP safety evaluators and return an aggregated report."""
    server_src = _server_source()
    auth_src = _auth_source()

    all_findings: list[dict[str, Any]] = []
    all_findings.extend(eval_mcp_no_http_socket(server_src))
    all_findings.extend(eval_mcp_no_direct_sql(server_src))
    all_findings.extend(eval_mcp_no_token_in_output(server_src))
    all_findings.extend(eval_mcp_no_argv(server_src))
    all_findings.extend(eval_mcp_approval_not_exposed(server_src))
    all_findings.extend(eval_mcp_scopes_enforced(server_src))
    all_findings.extend(eval_mcp_only_mcp_sdk(server_src))
    all_findings.extend(eval_mcp_rate_limit_before_store(server_src))
    all_findings.extend(eval_mcp_token_from_env_only(auth_src))
    all_findings.extend(eval_mcp_not_permission_markers(server_src))
    all_findings.extend(eval_mcp_replay_path_guard(server_src))

    total = len(all_findings)
    passed = sum(1 for f in all_findings if f["passed"])
    return {
        "eval_mcp_safety_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
        "total": total,
        "passed": passed,
        "failed": total - passed,
        "findings": all_findings,
    }
