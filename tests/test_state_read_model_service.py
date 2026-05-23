from __future__ import annotations

import unittest

from core.state_read_model_service import StateReadModelService


def _runtime_fixture(*, current_task_id: str = "task-1") -> dict:
    return {
        "plan": {
            "goal": "g",
            "summary": "s",
            "status": "ready",
            "current_task_id": current_task_id,
            "updated_at": "",
            "tasks": [
                {
                    "id": "task-1",
                    "title": "Underspecified task",
                    "status": "ready",
                    "details": "Underspecified task",
                    "depends_on": [],
                    "working_set": [],
                    "acceptance_criteria": [],
                    "action_ids": [],
                },
                {
                    "id": "task-2",
                    "title": "Scoped task",
                    "status": "ready",
                    "details": "Scoped task",
                    "depends_on": [],
                    "working_set": ["tracked.txt"],
                    "acceptance_criteria": ["verify succeeds"],
                    "action_ids": [],
                },
            ],
        },
        "command_registry": {
            "commands": [
                {
                    "id": "cmd-001",
                    "kind": "exec.command",
                    "summary": "verify",
                    "argv": ["python", "-m", "pytest"],
                    "cwd": ".",
                    "timeout_seconds": 30,
                    "determinism": "high",
                    "side_effect": "read_only",
                    "risk": "low",
                    "allow_in_verify": True,
                }
            ]
        },
        "approvals": {"items": []},
        "actions": [],
        "verification": {
            "required_command_ids": ["cmd-001"],
            "pending_action_ids": [],
            "last_run_at": "",
            "status": "idle",
            "checks": [],
        },
        "memory": {"notes": []},
        "audit": {
            "last_event_at": "",
            "last_event_type": "",
            "last_action_id": "",
            "trace_thread_id": "bootstrap",
            "next_event_id": 1,
            "trace_status": "healthy",
            "trace_integrity": "reliable",
            "last_trace_error_at": "",
            "last_trace_error": "",
            "rollback_points": [],
        },
        "batch_registry": {"used_ids": []},
    }


def _assessment(task_id: str, *, priority: int) -> dict:
    return {
        "id": task_id,
        "priority": priority,
        "impact": priority,
        "cost": 10,
        "risk": 5,
        "real_cost": 10,
        "executable": True,
        "evidence": [],
        "evidence_event_ids": [],
    }


class StateReadModelServiceTests(unittest.TestCase):
    def test_read_task_assessments_uses_loader_when_runtime_missing(self) -> None:
        calls: list[str] = []

        def load_agent_runtime() -> dict:
            calls.append("load")
            return _runtime_fixture()

        service = StateReadModelService(load_agent_runtime=load_agent_runtime)

        assessments = {item["id"]: item for item in service.read_task_assessments()}

        self.assertEqual(calls, ["load"])
        self.assertEqual(set(assessments), {"task-1", "task-2"})

    def test_read_task_assessments_uses_provided_runtime_without_loader(self) -> None:
        service = StateReadModelService(
            load_agent_runtime=lambda: (_ for _ in ()).throw(AssertionError("unexpected runtime reload"))
        )

        assessments = {item["id"]: item for item in service.read_task_assessments(agent_runtime=_runtime_fixture())}

        self.assertEqual(set(assessments), {"task-1", "task-2"})

    def test_read_task_selection_consistency_reuses_supplied_assessments(self) -> None:
        service = StateReadModelService(
            load_agent_runtime=lambda: (_ for _ in ()).throw(AssertionError("unexpected runtime reload"))
        )
        service._load_task_assessments = lambda **kwargs: (_ for _ in ()).throw(AssertionError("unexpected assessment reload"))
        runtime = _runtime_fixture(current_task_id="task-1")
        assessments = (
            _assessment("task-2", priority=55),
            _assessment("task-1", priority=20),
        )

        replay = service.read_task_selection_consistency(
            agent_runtime=runtime,
            task_assessments=assessments,
        )

        self.assertEqual(replay["status"], "mismatch")
        self.assertEqual(replay["derived_task_id"], "task-2")

    def test_read_task_selection_consistency_uses_assessment_loader_when_missing(self) -> None:
        load_calls: list[dict] = []
        runtime = _runtime_fixture(current_task_id="task-1")

        def load_assessments(**kwargs) -> tuple[dict, ...]:
            load_calls.append(kwargs)
            return (
                _assessment("task-2", priority=60),
                _assessment("task-1", priority=10),
            )

        service = StateReadModelService(
            load_agent_runtime=lambda: runtime,
            load_task_assessments=load_assessments,
        )

        replay = service.read_task_selection_consistency()

        self.assertEqual(len(load_calls), 1)
        self.assertIs(load_calls[0]["agent_runtime"], runtime)
        self.assertEqual(load_calls[0]["recent_events"], ())
        self.assertEqual(replay["derived_task_id"], "task-2")

    def test_read_task_work_profiles_uses_loader_when_runtime_missing(self) -> None:
        calls: list[str] = []

        def load_agent_runtime() -> dict:
            calls.append("load")
            return _runtime_fixture()

        service = StateReadModelService(load_agent_runtime=load_agent_runtime)

        profiles = {item["id"]: item for item in service.read_task_work_profiles()}

        self.assertEqual(calls, ["load"])
        self.assertEqual(profiles["task-1"]["workload_mode"], "light")
        self.assertEqual(profiles["task-2"]["workload_mode"], "heavy")


if __name__ == "__main__":
    unittest.main()
