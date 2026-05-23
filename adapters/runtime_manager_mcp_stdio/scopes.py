"""Scope constants and enforcement helpers for the MCP STDIO server."""
from __future__ import annotations

SCOPE_READ = "runtime:read"
SCOPE_LEASE = "runtime:lease"
SCOPE_EXECUTE = "runtime:execute"
SCOPE_TRACE = "runtime:trace"
SCOPE_METRICS = "runtime:metrics"
SCOPE_REPLAY = "runtime:replay"

ALL_SCOPES: frozenset[str] = frozenset(
    {SCOPE_READ, SCOPE_LEASE, SCOPE_EXECUTE, SCOPE_TRACE, SCOPE_METRICS, SCOPE_REPLAY}
)


def require_scope(token_scopes: tuple[str, ...], required: str) -> None:
    """Raise PermissionError if required scope is absent."""
    if required not in token_scopes:
        raise PermissionError(
            f"scope '{required}' required but token only has: {sorted(token_scopes)}"
        )
