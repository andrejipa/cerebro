"""AgentContext -- immutable identity for one adapter session."""
from __future__ import annotations

import re
from dataclasses import dataclass

_SAFE_ID_RE = re.compile(r"^[a-zA-Z0-9_:.-]{1,128}$")


def _validate_id(value: str, field: str) -> str:
    if not _SAFE_ID_RE.match(value):
        raise ValueError(
            f"AgentContext.{field} must be 1-128 chars of [a-zA-Z0-9_:.-], got {value!r}"
        )
    return value


@dataclass(frozen=True)
class AgentContext:
    """Immutable identity threaded through every adapter call.

    agent_id:   unique identifier for the agent (no secrets; validated).
    agent_role: human-readable role label (e.g. "reviewer", "runner").
    session_id: unique per adapter session; binds lease ownership.
    """

    agent_id: str
    agent_role: str
    session_id: str

    def __post_init__(self) -> None:
        _validate_id(self.agent_id, "agent_id")
        _validate_id(self.session_id, "session_id")
        if not self.agent_role:
            raise ValueError("AgentContext.agent_role must not be empty")
        if len(self.agent_role) > 128:
            raise ValueError("AgentContext.agent_role must be <= 128 chars")

    @property
    def lease_owner(self) -> str:
        """Derived lease owner string: adapter:<agent_id>:<session_id>."""
        return f"adapter:{self.agent_id}:{self.session_id}"

    def sanitized_label(self) -> str:
        """Safe label for trace payloads: no secrets."""
        return f"agent={self.agent_id} role={self.agent_role} session={self.session_id[:8]}..."
