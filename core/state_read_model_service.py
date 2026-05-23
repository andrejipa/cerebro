"""Read-only derived runtime views behind the StateStore facade."""

from __future__ import annotations

from typing import Callable

from core.decision_runtime import derive_task_assessments, evaluate_task_selection_consistency
from core.work_profile import derive_task_work_profiles


class StateReadModelService:
    """Derive read-only task views without taking authority from StateStore."""

    def __init__(
        self,
        *,
        load_agent_runtime: Callable[[], dict],
        load_task_assessments: Callable[..., tuple[dict, ...]] | None = None,
    ) -> None:
        self._load_agent_runtime = load_agent_runtime
        self._load_task_assessments = load_task_assessments or self.read_task_assessments

    def read_task_assessments(
        self,
        event_limit: int = 20,
        *,
        agent_runtime: dict | None = None,
        recent_events: tuple[dict, ...] | None = None,
    ) -> tuple[dict, ...]:
        """Return evidence-backed task assessments derived from runtime state."""
        del event_limit  # Signature stays facade-compatible while the derivation remains state-driven.
        runtime_block = agent_runtime if agent_runtime is not None else self._load_agent_runtime()
        recent_event_block = recent_events if recent_events is not None else ()
        return tuple(derive_task_assessments(runtime_block, recent_event_block))

    def read_task_selection_consistency(
        self,
        *,
        agent_runtime: dict | None = None,
        recent_events: tuple[dict, ...] | None = None,
        task_assessments: tuple[dict, ...] | list[dict] | None = None,
    ) -> dict:
        """Replay task selection from read-only state and report whether it still matches."""
        runtime_block = agent_runtime if agent_runtime is not None else self._load_agent_runtime()
        recent_event_block = recent_events if recent_events is not None else ()
        assessments = task_assessments
        if assessments is None:
            assessments = self._load_task_assessments(
                agent_runtime=runtime_block,
                recent_events=recent_event_block,
            )
        return evaluate_task_selection_consistency(
            runtime_block,
            recent_event_block,
            assessments=assessments,
        )

    def read_task_work_profiles(
        self,
        *,
        agent_runtime: dict | None = None,
    ) -> tuple[dict, ...]:
        """Return derived work profiles for the current canonical tasks."""
        runtime_block = agent_runtime if agent_runtime is not None else self._load_agent_runtime()
        return tuple(derive_task_work_profiles(runtime_block))
