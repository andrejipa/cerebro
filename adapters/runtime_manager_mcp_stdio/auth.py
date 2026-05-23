"""Token authentication for the MCP STDIO server.

The raw token comes ONLY from the env var CEREBRO_RUNTIME_MCP_TOKEN.
It is never accepted from CLI args, tool inputs, or client messages.

Phase 9: load_raw_token_from_env() exposes the raw token string so that
build_app can re-authenticate on every tool call (per-operation auth).
"""
from __future__ import annotations

import os
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from core.runtime_manager_store import AdapterToken, RuntimeManagerStore

ENV_VAR = "CEREBRO_RUNTIME_MCP_TOKEN"


class AuthError(Exception):
    """Raised when authentication fails at startup."""


def load_raw_token_from_env() -> str:
    """Return the raw token string from the env var without authenticating.

    Raises AuthError if the env var is absent or empty.
    The returned string is the secret credential; the caller must not persist
    it, log it, or include it in any tool output or trace payload.
    """
    raw = os.environ.get(ENV_VAR, "")
    if not raw:
        raise AuthError(
            f"env var {ENV_VAR} is absent or empty; server refuses to start"
        )
    return raw


def load_token_from_env(store: "RuntimeManagerStore") -> "AdapterToken":
    """Authenticate the process token from the env var.

    Returns the AdapterToken on success.  Raises AuthError otherwise so the
    server exits before accepting any tool calls.
    """
    raw = load_raw_token_from_env()
    token = store.authenticate_adapter_token(raw)
    if token is None:
        raise AuthError(
            f"token from {ENV_VAR} did not authenticate (unknown, revoked, or expired)"
        )
    return token
