from __future__ import annotations

from copy import deepcopy
import unittest

from core.decision_runtime import derive_task_assessments
from core.success_memory import build_success_memory_source


def _build_agent_runtime(
    tasks: list[dict],
    *,
    actions: list[dict] | None = None,
    approvals: list[dict] | None = None,
    verification: dict | None = None,
    memory_notes: list[dict] | None = None,
    commands: list[dict] | None = None,
) -> dict:
    return {
        "plan": {
            "goal": "g",
            "summary": "s",
            "status": "running",
            "current_task_id": tasks[0]["id"] if tasks else "",
            "updated_at": "",
            "tasks": deepcopy(tasks),
        },
        "execution_policy": {
            "autonomy_level": "A2",
            "protected_paths": [],
            "blocked_command_prefixes": [],
            "approval_required_kinds": [],
        },
        "command_registry": {"commands": deepcopy(commands or [])},
        "approvals": {"items": deepcopy(approvals or [])},
        "actions": deepcopy(actions or []),
        "verification": {
            "required_command_ids": [],
            "pending_action_ids": [],
            "last_run_at": "",
            "status": "idle",
            "checks": [],
            **(deepcopy(verification) if verification is not None else {}),
        },
        "memory": {"notes": deepcopy(memory_notes or [])},
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


def _build_task(
    task_id: str,
    *,
    status: str = "ready",
    working_set: list[str] | None = None,
    acceptance_criteria: list[str] | None = None,
    depends_on: list[str] | None = None,
    action_ids: list[str] | None = None,
    retry_blocked_count: object = 0,
    verify_blocked_count: object = 0,
    apply_blocked_count: object = 0,
) -> dict:
    return {
        "id": task_id,
        "title": task_id,
        "status": status,
        "details": "",
        "depends_on": list(depends_on or []),
        "working_set": list(working_set or []),
        "acceptance_criteria": list(acceptance_criteria or []),
        "action_ids": list(action_ids or []),
        "retry_blocked_count": retry_blocked_count,
        "verify_blocked_count": verify_blocked_count,
        "apply_blocked_count": apply_blocked_count,
    }


def _build_success_note(
    *,
    task_id: str,
    working_set_bucket: str = "single",
    acceptance_defined: bool = True,
    action_kinds: list[str] | None = None,
    has_sensitive_actions: bool = False,
    cost: int = 10,
) -> dict:
    return {
        "id": f"workflow-success-{task_id}",
        "kind": "workflow",
        "summary": "verified success pattern",
        "source": build_success_memory_source(
            task_id=task_id,
            working_set_bucket=working_set_bucket,
            acceptance_defined=acceptance_defined,
            action_kinds=list(action_kinds or []),
            has_sensitive_actions=has_sensitive_actions,
            cost=cost,
        ),
        "ttl_days": 21,
        "updated_at": "2026-04-23T00:00:00+00:00",
    }


class DecisionRuntimeAssessmentsTests(unittest.TestCase):
    def test_derive_task_assessments_normalizes_invalid_block_counters(self) -> None:
        baseline_task = _build_task("task-baseline")
        invalid_task = _build_task(
            "task-baseline",
            retry_blocked_count="invalid",
            verify_blocked_count=-3,
            apply_blocked_count=None,
        )

        baseline = derive_task_assessments(_build_agent_runtime([baseline_task]))[0]
        invalid = derive_task_assessments(_build_agent_runtime([invalid_task]))[0]

        for field in ("impact", "estimated_cost", "real_cost", "cost", "risk", "priority", "executable"):
            self.assertEqual(invalid[field], baseline[field], field)
        self.assertEqual(invalid["recent_history"], baseline["recent_history"])
        self.assertFalse(any("blocked retry attempt" in item for item in invalid["evidence"]))
        self.assertFalse(any("blocked verify attempt" in item for item in invalid["evidence"]))
        self.assertFalse(any("blocked apply attempt" in item for item in invalid["evidence"]))

    def test_derive_task_assessments_blocks_ready_and_running_tasks_after_failed_verification(self) -> None:
        for status in ("ready", "running"):
            with self.subTest(status=status):
                task = _build_task(f"task-{status}", status=status)
                assessment = derive_task_assessments(
                    _build_agent_runtime([task], verification={"status": "failed"})
                )[0]

                self.assertFalse(assessment["executable"])
                self.assertIn(
                    "task is blocked until verification is rerun successfully",
                    assessment["evidence"],
                )

    def test_derive_task_assessments_blocks_only_the_task_waiting_on_pending_approval(self) -> None:
        tasks = [
            _build_task("task-blocked"),
            _build_task("task-free"),
        ]
        approvals = [
            {
                "id": "apr-001",
                "status": "pending",
                "fingerprint": "fp-001",
                "action_kind": "fs.write_patch",
                "task_id": "task-blocked",
                "target": "draft.txt",
                "reason": "approval required",
                "requested_at": "",
                "resolved_at": "",
            }
        ]

        assessments = derive_task_assessments(_build_agent_runtime(tasks, approvals=approvals))
        by_id = {item["id"]: item for item in assessments}

        self.assertFalse(by_id["task-blocked"]["executable"])
        self.assertIn("task is waiting on a pending approval", by_id["task-blocked"]["evidence"])
        self.assertIn("task is blocked until approval is resolved", by_id["task-blocked"]["evidence"])
        self.assertTrue(by_id["task-free"]["executable"])
        self.assertIn("other runtime tasks are waiting on approval", by_id["task-free"]["evidence"])

    def test_derive_task_assessments_reduces_success_pattern_confidence_after_blocked_attempts(self) -> None:
        task = _build_task(
            "task-repeatable",
            working_set=["artifact.txt"],
            acceptance_criteria=["done"],
        )
        notes = [_build_success_note(task_id="task-repeatable")]

        reinforced = derive_task_assessments(
            _build_agent_runtime([task], memory_notes=notes)
        )[0]
        challenged_task = _build_task(
            "task-repeatable",
            working_set=["artifact.txt"],
            acceptance_criteria=["done"],
            retry_blocked_count=1,
        )
        challenged = derive_task_assessments(
            _build_agent_runtime([challenged_task], memory_notes=notes)
        )[0]
        challenged_without_note = derive_task_assessments(
            _build_agent_runtime([challenged_task])
        )[0]

        self.assertIn("task matches 1 verified success pattern(s)", reinforced["evidence"])
        self.assertIn("task matches 1 verified success pattern(s)", challenged["evidence"])
        self.assertGreater(reinforced["priority"], challenged["priority"])
        self.assertEqual(challenged["impact"], challenged_without_note["impact"])
        self.assertIn(
            "recent blocked or failed attempts reduced confidence in the learned success pattern",
            challenged["evidence"],
        )
        self.assertIn("success_pattern_confidence_reduced", challenged["recent_history"])

    def test_derive_task_assessments_orders_by_status_then_priority_then_cost_then_id(self) -> None:
        tasks = [
            _build_task("running-task", status="running"),
            _build_task(
                "ready-high",
                working_set=["single.txt"],
                acceptance_criteria=["done"],
            ),
            _build_task("ready-low"),
            _build_task("blocked-low", status="blocked"),
            _build_task("blocked-a", status="blocked", depends_on=["dep-1"]),
            _build_task("blocked-b", status="blocked", depends_on=["dep-1"]),
        ]

        assessments = derive_task_assessments(_build_agent_runtime(tasks))
        ordered_ids = [item["id"] for item in assessments]

        self.assertEqual(
            ordered_ids,
            ["running-task", "ready-high", "ready-low", "blocked-low", "blocked-a", "blocked-b"],
        )
        running = assessments[0]
        ready_high = assessments[1]
        ready_low = assessments[2]
        blocked_low = assessments[3]
        blocked_a = assessments[4]
        blocked_b = assessments[5]

        self.assertGreater(ready_high["priority"], ready_low["priority"])
        self.assertGreater(ready_high["priority"], running["priority"])
        self.assertEqual(blocked_low["priority"], 0)
        self.assertEqual(blocked_a["priority"], 0)
        self.assertEqual(blocked_b["priority"], 0)
        self.assertLess(blocked_low["cost"], blocked_a["cost"])
        self.assertEqual(blocked_a["cost"], blocked_b["cost"])


if __name__ == "__main__":
    unittest.main()
