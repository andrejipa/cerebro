"""
Explicit narrow protocol contracts for StateStore consumers.

These Protocols make the duck-typed dependency surface of action_runtime and
verification_runtime explicit without moving code or changing behavior.
StateStore satisfies both protocols structurally; the sandbox_store object
created inline in action_runtime satisfies ActionStoreSurface.
"""

from __future__ import annotations

from contextlib import AbstractContextManager
from pathlib import Path
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class ActionStoreSurface(Protocol):
    """Minimal path surface consumed by action_runtime."""

    cerebro_dir: Path
    artifacts_dir: Path
    trash_dir: Path


@runtime_checkable
class VerificationStoreSurface(Protocol):
    """State-mutation surface consumed by verification_runtime."""

    root: Path
    artifacts_dir: Path

    def capture_verify_authority_guard(self) -> list[dict]: ...

    def restore_verify_authority_guard_if_changed(
        self, snapshots: list[dict]
    ) -> str: ...

    def _runtime_lock(self) -> AbstractContextManager[None]: ...

    def _validate_state_locked(self) -> tuple[dict, dict | None]: ...

    def _read_owned_active_session(
        self, state: dict, expected_session_token: str | None
    ) -> dict | None: ...

    def update_agent_verification(
        self,
        verification_record: dict,
        validated_revision: int | None = None,
        *,
        expected_session_token: str | None = None,
    ) -> dict: ...
