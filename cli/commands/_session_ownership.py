"""Helpers for proving ownership of one live local session across CLI invocations."""

from __future__ import annotations

import os
import sys

SESSION_TOKEN_ENV_VAR = "CEREBRO_SESSION_TOKEN"


def resolve_session_token(args) -> str | None:
    """Return one explicit session token from CLI args or environment."""
    raw_value = getattr(args, "session_token", None)
    if isinstance(raw_value, str):
        stripped = raw_value.strip()
        if stripped == "-":
            stdin_value = sys.stdin.readline()
            if isinstance(stdin_value, str) and stdin_value.strip():
                return stdin_value.strip()
            return None
        if stripped:
            return stripped
    env_value = os.environ.get(SESSION_TOKEN_ENV_VAR, "")
    if isinstance(env_value, str) and env_value.strip():
        return env_value.strip()
    return None


def session_token_output_lines(session_data: dict, *, emit_token: bool = False) -> list[str]:
    """Return stable output lines for one newly opened local session authority."""
    lines = [
        "session_owner_proof: external_claim",
        f"session_claim_id: {session_data['owner_claim_id']}",
    ]
    if emit_token:
        lines.append(f"session_token: {session_data['session_token']}")
    return lines
