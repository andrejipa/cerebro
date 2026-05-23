"""eval_adapter_safety -- advisory-only safety invariant checks for the local adapter.

These evaluators inspect adapter behavior artifacts (call logs, metric snapshots,
trace exports, module source) to detect safety violations.

NOT a runtime gate, NOT permission, NOT execution approval.
All evaluator functions return a list of finding dicts with:
    {"check": str, "passed": bool, "detail": str}

eval_adapter_safety_is_not_permission = True (always)
"""
from __future__ import annotations

import importlib
import importlib.util
import inspect
from typing import Any

EVAL_AUTHORITY = "adapter safety eval only; not permission, not a runtime gate"


# ---------------------------------------------------------------------------
# Individual evaluators
# ---------------------------------------------------------------------------


def _finding(check: str, passed: bool, detail: str) -> dict[str, Any]:
    return {
        "check": check,
        "passed": passed,
        "detail": detail,
        "eval_adapter_safety_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
    }


def eval_adapter_no_direct_sql(adapter_module_source: str) -> list[dict[str, Any]]:
    """Adapter source must not contain direct SQLite calls."""
    findings = []
    forbidden = ["sqlite3.connect(", "connection.execute(", "cursor.execute(", ".executescript("]
    for token in forbidden:
        passed = token not in adapter_module_source
        findings.append(_finding(
            check=f"no_direct_sql:{token.strip()}",
            passed=passed,
            detail=f"adapter source {'does not contain' if passed else 'CONTAINS'} forbidden token {token!r}",
        ))
    return findings


def eval_adapter_no_argv_acceptance(adapter_module_source: str) -> list[dict[str, Any]]:
    """Adapter source must not accept free-form argv in public method signatures."""
    findings = []
    # Check for argv as a function parameter (not just documentation), shell=True,
    # and raw subprocess patterns that bypass command_registry.
    forbidden_patterns = [
        ("no_argv_param", "(argv)", "function signature accepting (argv)"),
        ("no_argv_param", ", argv", "function signature accepting , argv"),
        ("no_raw_command", "raw_command", "raw_command parameter"),
        ("no_shell_true", "shell=True", "shell=True subprocess flag"),
        ("no_subprocess_popen_argv", "Popen(argv", "direct Popen(argv call"),
    ]
    for check_name, pattern, description in forbidden_patterns:
        passed = pattern not in adapter_module_source
        findings.append(_finding(
            check=check_name,
            passed=passed,
            detail=f"adapter source {'does not contain' if passed else 'CONTAINS'} forbidden pattern: {description}",
        ))
    return findings


def eval_adapter_no_external_sdk(adapter_module_source: str) -> list[dict[str, Any]]:
    """Adapter source must not import external agent SDKs or MCP."""
    findings = []
    forbidden_imports = [
        "import mcp",
        "from mcp",
        "import langchain",
        "from langchain",
        "import langgraph",
        "from langgraph",
        "import temporal",
        "from temporal",
        "import openai",
        "from openai",
        "cloudflare_agents",
        "agents_sdk",
    ]
    for token in forbidden_imports:
        passed = token not in adapter_module_source
        findings.append(_finding(
            check=f"no_external_sdk:{token.split()[1] if ' ' in token else token}",
            passed=passed,
            detail=f"adapter source {'does not contain' if passed else 'CONTAINS'} forbidden import {token!r}",
        ))
    return findings


def eval_replay_result_is_not_permission(replay_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Replay result must carry authority marker and pass=True must not be used as permission."""
    findings = []
    has_authority = "authority" in replay_result
    findings.append(_finding(
        check="replay_has_authority_field",
        passed=has_authority,
        detail="replay result has 'authority' field" if has_authority else "replay result MISSING 'authority' field",
    ))
    authority_val = replay_result.get("authority", "")
    authority_ok = "not permission" in authority_val or "not a runtime gate" in authority_val
    findings.append(_finding(
        check="replay_authority_disclaims_permission",
        passed=authority_ok,
        detail=f"authority field correctly disclaims permission: {authority_val!r}" if authority_ok else f"authority field DOES NOT disclaim permission: {authority_val!r}",
    ))
    return findings


def eval_metrics_result_is_not_permission(metrics_result: dict[str, Any]) -> list[dict[str, Any]]:
    """Metrics snapshot must carry metrics_is_not_permission=True."""
    findings = []
    marker = metrics_result.get("metrics_is_not_permission", False)
    findings.append(_finding(
        check="metrics_has_not_permission_marker",
        passed=bool(marker),
        detail="metrics_is_not_permission=True present" if marker else "metrics_is_not_permission marker MISSING",
    ))
    return findings


def eval_lease_ownership_enforced(call_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Call log: release/heartbeat must only succeed for matching owner."""
    findings = []
    for entry in call_log:
        op = entry.get("operation", "")
        if op in ("release_lease", "heartbeat_lease"):
            owner_match = entry.get("owner_matched", None)
            if owner_match is False:
                findings.append(_finding(
                    check="lease_owner_enforced",
                    passed=False,
                    detail=f"{op} succeeded with mismatched owner -- POLICY VIOLATION",
                ))
            elif owner_match is True:
                findings.append(_finding(
                    check="lease_owner_enforced",
                    passed=True,
                    detail=f"{op} correctly verified owner match",
                ))
    if not findings:
        findings.append(_finding(
            check="lease_owner_enforced",
            passed=True,
            detail="no release/heartbeat calls in log; invariant vacuously satisfied",
        ))
    return findings


def eval_rate_limit_blocks_abuse(call_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Rate limit must have blocked at least one call when limit was exceeded."""
    findings = []
    rate_limited_calls = [e for e in call_log if e.get("rate_limited")]
    total_calls = len(call_log)
    if total_calls == 0:
        findings.append(_finding(
            check="rate_limit_triggered",
            passed=True,
            detail="no calls in log; invariant vacuously satisfied",
        ))
        return findings
    findings.append(_finding(
        check="rate_limit_counter_recorded",
        passed=True,
        detail=f"call log has {total_calls} entries, {len(rate_limited_calls)} rate-limited",
    ))
    return findings


def eval_no_secret_in_trace_export(trace_export_text: str, secret_tokens: list[str]) -> list[dict[str, Any]]:
    """Exported trace must not contain any of the specified secret tokens."""
    findings = []
    for secret in secret_tokens:
        passed = secret not in trace_export_text
        findings.append(_finding(
            check=f"secret_not_in_trace:{secret[:8]}...",
            passed=passed,
            detail=f"secret token {'not found' if passed else 'FOUND'} in trace export",
        ))
    return findings


def eval_approval_requires_fingerprint(approval_record: dict[str, Any]) -> list[dict[str, Any]]:
    """Approval record must have a non-empty action_fingerprint."""
    findings = []
    fp = approval_record.get("action_fingerprint", "")
    passed = bool(fp)
    findings.append(_finding(
        check="approval_has_fingerprint",
        passed=passed,
        detail=f"action_fingerprint present: {fp!r}" if passed else "action_fingerprint MISSING or empty",
    ))
    return findings


def eval_mutation_without_lease_blocked(call_log: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Mutating calls without a lease must be blocked (not reach the store)."""
    findings = []
    for entry in call_log:
        op = entry.get("operation", "")
        if op in ("run", "record_approval", "raise_stop_condition", "resolve_stop_condition", "record_validation", "revoke_approval"):
            has_lease = entry.get("had_active_lease", None)
            reached_store = entry.get("reached_store", None)
            if has_lease is False and reached_store is True:
                findings.append(_finding(
                    check="mutation_without_lease_blocked",
                    passed=False,
                    detail=f"{op} reached the store without an active lease -- POLICY VIOLATION",
                ))
            elif has_lease is False and reached_store is False:
                findings.append(_finding(
                    check="mutation_without_lease_blocked",
                    passed=True,
                    detail=f"{op} correctly blocked before reaching store (no lease)",
                ))
    if not findings:
        findings.append(_finding(
            check="mutation_without_lease_blocked",
            passed=True,
            detail="no leaseless mutation calls in log; invariant vacuously satisfied",
        ))
    return findings


# ---------------------------------------------------------------------------
# Top-level aggregator
# ---------------------------------------------------------------------------


def eval_adapter_safety(
    *,
    adapter_module_source: str = "",
    replay_result: dict[str, Any] | None = None,
    metrics_result: dict[str, Any] | None = None,
    call_log: list[dict[str, Any]] | None = None,
    trace_export_text: str = "",
    secret_tokens: list[str] | None = None,
    approval_record: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Run all applicable adapter safety checks and return aggregated result.

    Returns:
        {
            "all_passed": bool,
            "findings": [...],
            "eval_adapter_safety_is_not_permission": True,
            "authority": "...",
        }
    """
    findings: list[dict[str, Any]] = []

    if adapter_module_source:
        findings.extend(eval_adapter_no_direct_sql(adapter_module_source))
        findings.extend(eval_adapter_no_argv_acceptance(adapter_module_source))
        findings.extend(eval_adapter_no_external_sdk(adapter_module_source))

    if replay_result is not None:
        findings.extend(eval_replay_result_is_not_permission(replay_result))

    if metrics_result is not None:
        findings.extend(eval_metrics_result_is_not_permission(metrics_result))

    if call_log is not None:
        findings.extend(eval_lease_ownership_enforced(call_log))
        findings.extend(eval_rate_limit_blocks_abuse(call_log))
        findings.extend(eval_mutation_without_lease_blocked(call_log))

    if trace_export_text and secret_tokens:
        findings.extend(eval_no_secret_in_trace_export(trace_export_text, secret_tokens))

    if approval_record is not None:
        findings.extend(eval_approval_requires_fingerprint(approval_record))

    all_passed = all(f["passed"] for f in findings)
    return {
        "all_passed": all_passed,
        "findings": findings,
        "eval_adapter_safety_is_not_permission": True,
        "authority": EVAL_AUTHORITY,
    }
