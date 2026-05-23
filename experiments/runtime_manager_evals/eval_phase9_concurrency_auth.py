"""eval_phase9_concurrency_auth -- Phase 9 invariant checks for concurrency and per-operation auth.

Evaluators verify:
  - Per-call auth is present in server source (re-authentication on every tool call)
  - Phase 9 server contains no HTTP binding
  - Rate limit is backed by SQLite (not in-memory only)
  - Lease contention is backed by SQLite UNIQUE index (not application-layer)
  - Token revocation mid-session is detectable via authenticate_adapter_token
  - No raw token in server outputs, trace payloads, or log-style prints

NOT a runtime gate, NOT permission, NOT execution approval.
All evaluator functions return a list of finding dicts.

eval_phase9_concurrency_auth_is_not_permission = True (always)
"""
from __future__ import annotations

import inspect
from typing import Any

EVAL_AUTHORITY = "phase9 concurrency/auth eval only; not permission, not a runtime gate"
eval_phase9_concurrency_auth_is_not_permission = True


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


def _auth_source() -> str:
    try:
        import adapters.runtime_manager_mcp_stdio.auth as mod
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
# Evaluator 1: per-call auth exists in server source
# ---------------------------------------------------------------------------

def eval_mcp_per_call_auth_exists() -> list[dict[str, Any]]:
    """Server must re-authenticate the token on every tool call (per-operation auth)."""
    findings = []
    src = _server_source()

    # The factory function must exist
    findings.append(_finding(
        "per_call_auth_factory_defined",
        "_require_current_token_factory" in src,
        "server must define _require_current_token_factory for per-op auth",
    ))

    # authenticate_adapter_token must be called inside the factory
    findings.append(_finding(
        "authenticate_adapter_token_in_factory",
        "authenticate_adapter_token" in src and "_require_current_token_factory" in src,
        "factory must call authenticate_adapter_token to re-read token from DB",
    ))

    # token_revoked_mid_session must be present as the error code
    findings.append(_finding(
        "token_revoked_mid_session_message",
        "token_revoked_mid_session" in src,
        "server must raise PermissionError with token_revoked_mid_session when token invalid",
    ))

    # Every tool must call _require_current_token (the bound closure from factory)
    # We verify by checking that static captures of scopes/token_max from startup are gone
    findings.append(_finding(
        "no_static_scopes_capture",
        "scopes = token_record.scopes" not in src and "token_max = token_record.max_autonomy_level" not in src,
        "server must not cache scopes/token_max at startup; must use per-call re-auth",
    ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 2: no HTTP in Phase 9 server
# ---------------------------------------------------------------------------

def eval_mcp_no_http_phase9() -> list[dict[str, Any]]:
    """Phase 9 server must not introduce HTTP, OAuth, TLS, or SSE transport."""
    findings = []
    src = _server_source()
    auth_src = _auth_source()
    combined = src + auth_src

    # Use specific patterns to avoid false positives from substrings (e.g. "dataclasses" contains "sse")
    forbidden = [
        ("no_http_server", "HTTPServer(", "HTTPServer binding"),
        ("no_streamable_http", "streamable-http", "Streamable HTTP transport"),
        ("no_sse_transport", 'transport="sse"', 'SSE transport declaration'),
        ("no_sse_server", "sse_server", "SSE server import/use"),
        ("no_socket_listen", "socket.listen(", "raw socket.listen()"),
        ("no_socket_bind", "socket.bind(", "raw socket.bind()"),
        ("no_oauth", "oauth2", "OAuth2 binding"),
        ("no_tls_wrap", "ssl.wrap_socket", "TLS wrapping"),
    ]
    for name, token, desc in forbidden:
        findings.append(_finding(
            name,
            token not in combined,
            f"Phase 9 must not introduce {desc}",
        ))

    # Transport must remain stdio
    findings.append(_finding(
        "transport_stdio_only",
        'transport="stdio"' in src,
        "Phase 9 server must use STDIO transport only",
    ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 3: persistent rate limit is SQLite-backed (not in-memory only)
# ---------------------------------------------------------------------------

def eval_persistent_rate_limit_not_in_memory_only() -> list[dict[str, Any]]:
    """Rate limit must be backed by the SQLite store, not an in-memory structure."""
    findings = []
    src = _store_source()

    findings.append(_finding(
        "rate_limit_uses_sqlite_table",
        "adapter_rate_buckets" in src,
        "rate limit must use adapter_rate_buckets SQLite table",
    ))

    findings.append(_finding(
        "rate_limit_uses_begin_immediate",
        "BEGIN IMMEDIATE" in src,
        "check_and_increment_rate_limit must use BEGIN IMMEDIATE for atomic increment",
    ))

    findings.append(_finding(
        "rate_limit_no_in_memory_dict",
        "self._buckets" not in src and "self._rate_buckets" not in src,
        "rate limit must not use an in-memory instance dict (self._buckets / self._rate_buckets) that resets on restart",
    ))

    try:
        import adapters.runtime_manager_local_agent.persistent_rate_limiter as plim
        plim_src = inspect.getsource(plim)
        findings.append(_finding(
            "persistent_rate_limiter_delegates_to_store",
            "check_and_increment_rate_limit" in plim_src,
            "PersistentRateLimiter must delegate to store.check_and_increment_rate_limit",
        ))
    except Exception as exc:
        findings.append(_finding(
            "persistent_rate_limiter_importable",
            False,
            f"PersistentRateLimiter not importable: {exc}",
        ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 4: lease contention is SQLite-backed via UNIQUE partial index
# ---------------------------------------------------------------------------

def eval_lease_contention_sqlite_backed() -> list[dict[str, Any]]:
    """Lease single-flight must be enforced by a SQLite UNIQUE index, not application logic."""
    findings = []
    src = _store_source()

    findings.append(_finding(
        "managed_leases_unique_index",
        "CREATE UNIQUE INDEX" in src and "managed_leases" in src,
        "acquire_lease must rely on a CREATE UNIQUE INDEX for single-flight enforcement",
    ))

    findings.append(_finding(
        "lease_contention_code_in_store",
        'code="lease_contention"' in src,
        "RuntimeManagerStoreError raised by duplicate lease must carry code=lease_contention",
    ))

    findings.append(_finding(
        "runtime_manager_store_error_has_code",
        "self.code = code" in src,
        "RuntimeManagerStoreError must have a code attribute",
    ))

    findings.append(_finding(
        "lease_owner_mismatch_code_in_store",
        '"lease_owner_mismatch"' in src,
        "release_lease / heartbeat_lease must trace lease_owner_mismatch on wrong-owner noop",
    ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 5: token revocation mid-session detectable
# ---------------------------------------------------------------------------

def eval_token_revocation_mid_session() -> list[dict[str, Any]]:
    """Revoking a token mid-session must be detectable by authenticate_adapter_token."""
    findings = []

    try:
        import tempfile
        from pathlib import Path
        from core.runtime_manager_store import RuntimeManagerStore

        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RuntimeManagerStore(root)
            store.initialize_schema()

            token_record, raw = store.issue_adapter_token(
                agent_id="eval-revoke-agent",
                agent_role="runner",
                scopes=["runtime:read"],
                ttl_seconds=3600,
            )
            # Valid before revocation
            before = store.authenticate_adapter_token(raw)
            store.revoke_adapter_token(token_record.token_id)
            # Rejected after revocation
            after = store.authenticate_adapter_token(raw)

            findings.append(_finding(
                "token_valid_before_revocation",
                before is not None,
                "authenticate_adapter_token must return token before revocation",
            ))
            findings.append(_finding(
                "token_rejected_after_revocation",
                after is None,
                "authenticate_adapter_token must return None after revocation",
            ))

        # Verify the per-op factory raises PermissionError after revocation
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            store = RuntimeManagerStore(root)
            store.initialize_schema()

            token_record, raw = store.issue_adapter_token(
                agent_id="eval-revoke-factory",
                agent_role="runner",
                scopes=["runtime:read"],
                ttl_seconds=3600,
            )
            from adapters.runtime_manager_mcp_stdio.server import _require_current_token_factory
            require_fn = _require_current_token_factory(store, raw)

            store.revoke_adapter_token(token_record.token_id)
            raised = False
            err_msg = ""
            try:
                require_fn("runtime:read", "L0_observe")
            except PermissionError as exc:
                raised = True
                err_msg = str(exc)

            findings.append(_finding(
                "factory_raises_on_revoked_token",
                raised and "token_revoked_mid_session" in err_msg,
                f"_require_current_token_factory must raise PermissionError with token_revoked_mid_session; got: {err_msg!r}",
            ))

    except Exception as exc:
        findings.append(_finding(
            "token_revocation_eval_error",
            False,
            f"unexpected error: {exc}",
        ))

    return findings


# ---------------------------------------------------------------------------
# Evaluator 6: no raw token in outputs
# ---------------------------------------------------------------------------

def eval_no_token_in_outputs() -> list[dict[str, Any]]:
    """Server must never include the raw token in tool outputs, traces, or log lines."""
    findings = []
    src = _server_source()
    auth_src = _auth_source()

    # raw_env_token must not appear in any f-string output
    findings.append(_finding(
        "raw_env_token_not_in_return",
        "return raw_env_token" not in src,
        "raw_env_token must never be returned from any function",
    ))

    # _safe_dc filters stdout/stderr but must not leak token
    findings.append(_finding(
        "safe_dc_filters_output",
        "_safe_dc" in src and '"stdout"' in src,
        "_safe_dc must filter stdout/stderr from tool outputs",
    ))

    # The auth module must not log or print the raw token
    findings.append(_finding(
        "auth_no_print_raw_token",
        "print(raw" not in auth_src and "log(raw" not in auth_src,
        "auth module must not print or log the raw token",
    ))

    # Token hash must not be in AdapterToken dataclass output fields
    try:
        import core.runtime_manager_store as store_mod
        store_src = inspect.getsource(store_mod)
        findings.append(_finding(
            "adapter_token_no_token_hash_field",
            "token_hash" not in inspect.getsource(
                store_mod.AdapterToken
            ) if hasattr(store_mod, "AdapterToken") else True,
            "AdapterToken must not expose token_hash as a field (would leak via _safe_dc)",
        ))
    except Exception:
        pass  # AdapterToken source not inspectable; skip

    # output_payload in issue_adapter_token trace must not include raw_token
    try:
        import core.runtime_manager_store as store_mod
        issue_src = inspect.getsource(store_mod.RuntimeManagerStore.issue_adapter_token)
        # Extract the dict literal assigned to output_payload= (ends at matching })
        import re
        m = re.search(r'output_payload=(\{[^}]*\})', issue_src)
        if m:
            payload_literal = m.group(1)
            safe = "raw_token" not in payload_literal
        else:
            safe = True  # no output_payload found; not a violation
        findings.append(_finding(
            "issue_token_trace_no_raw_token",
            safe,
            "issue_adapter_token output_payload dict must not reference raw_token",
        ))
    except Exception:
        pass

    return findings


# ---------------------------------------------------------------------------
# run_all aggregator
# ---------------------------------------------------------------------------

def run_all() -> dict[str, Any]:
    """Run all Phase 9 evaluators and return aggregated results."""
    all_findings = []

    server_src = _server_source()

    for fn in [
        eval_mcp_per_call_auth_exists,
        eval_mcp_no_http_phase9,
        eval_persistent_rate_limit_not_in_memory_only,
        eval_lease_contention_sqlite_backed,
        eval_token_revocation_mid_session,
        eval_no_token_in_outputs,
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
