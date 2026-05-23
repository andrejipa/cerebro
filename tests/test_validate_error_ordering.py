from __future__ import annotations

import copy
import unittest

from core.schema import build_initial_state
from core.validation import _validate_agent_runtime_block


class ValidateAgentRuntimeErrorOrderingTests(unittest.TestCase):
    def _valid_runtime(self) -> dict:
        return copy.deepcopy(build_initial_state()["agent_runtime"])

    def _valid_task(
        self,
        task_id: str,
        *,
        status: str = "ready",
        depends_on: list[str] | None = None,
        action_ids: list[str] | None = None,
    ) -> dict:
        return {
            "id": task_id,
            "title": f"Task {task_id}",
            "status": status,
            "details": "Validation fixture task.",
            "depends_on": list(depends_on or []),
            "working_set": ["tracked.txt"],
            "acceptance_criteria": ["stays valid"],
            "action_ids": list(action_ids or []),
            "retry_blocked_count": 0,
            "verify_blocked_count": 0,
            "apply_blocked_count": 0,
        }

    def _valid_action(
        self,
        action_id: str,
        *,
        task_id: str = "",
        status: str = "pending_approval",
        kind: str = "exec.command",
        batch_id: str = "",
        approval_id: str = "",
        target: str = "target.txt",
        plan_generation_id: str = "",
    ) -> dict:
        details: dict[str, str] = {}
        if plan_generation_id:
            details["plan_generation_id"] = plan_generation_id
        return {
            "id": action_id,
            "kind": kind,
            "summary": "Action summary",
            "target": target,
            "details": details,
            "status": status,
            "task_id": task_id,
            "batch_id": batch_id,
            "approval_id": approval_id,
            "artifact_refs": [],
            "rollback_ref": "",
            "updated_at": "",
        }

    def _valid_approval(
        self,
        approval_id: str,
        *,
        status: str = "pending",
        action_kind: str = "fs.write_patch",
        task_id: str = "",
        target: str = "target.txt",
        fingerprint: str = "fp-001",
    ) -> dict:
        return {
            "id": approval_id,
            "status": status,
            "fingerprint": fingerprint,
            "action_kind": action_kind,
            "task_id": task_id,
            "target": target,
            "reason": "Approval fixture",
            "requested_at": "2026-04-16T00:00:00+00:00",
            "resolved_at": "2026-04-16T00:01:00+00:00",
        }

    def _ordered_errors(self, runtime: dict) -> list[tuple[str, str]]:
        return [
            (item["code"], item["message"])
            for item in _validate_agent_runtime_block(runtime)
        ]

    def test_plan_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [("invalid_agent_plan", "agent_runtime.plan must be an object")],
        )

    def test_execution_policy_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["execution_policy"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_execution_policy",
                    "agent_runtime.execution_policy must be an object",
                )
            ],
        )

    def test_command_registry_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["command_registry"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_command_registry",
                    "agent_runtime.command_registry must be an object",
                )
            ],
        )

    def test_approvals_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["approvals"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_approvals",
                    "agent_runtime.approvals must be an object",
                )
            ],
        )

    def test_actions_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["actions"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [("invalid_agent_actions", "agent_runtime.actions must be an array")],
        )

    def test_batch_registry_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["batch_registry"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_batch_registry",
                    "agent_runtime.batch_registry must be an object",
                )
            ],
        )

    def test_verification_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["verification"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_verification",
                    "agent_runtime.verification must be an object",
                )
            ],
        )

    def test_memory_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["memory"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [("invalid_agent_memory", "agent_runtime.memory must be an object")],
        )

    def test_audit_core_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["audit"] = "oops"
        self.assertEqual(
            self._ordered_errors(runtime),
            [("invalid_agent_audit", "agent_runtime.audit must be an object")],
        )

    def test_plan_dependency_relations_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["tasks"] = [
            self._valid_task("task-1", depends_on=["ghost", "task-2"]),
            self._valid_task("task-2", depends_on=["task-1"]),
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_plan_task_depends_on",
                    "task task-1 depends on unknown task id: ghost",
                ),
                (
                    "invalid_agent_plan_task_status",
                    "task task-1 cannot be 'ready' while dependencies are incomplete",
                ),
                (
                    "invalid_agent_plan_task_status",
                    "task task-2 cannot be 'ready' while dependencies are incomplete",
                ),
                (
                    "invalid_agent_plan_tasks",
                    "plan dependencies must form a DAG; cycle detected at task-1",
                ),
            ],
        )

    def test_audit_last_action_ref_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["actions"] = [self._valid_action("act-1")]
        runtime["audit"]["last_action_id"] = "missing-action"
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_audit_field",
                    "agent_runtime.audit.last_action_id must reference an existing action id",
                )
            ],
        )

    def test_task_action_ref_relations_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["tasks"] = [
            self._valid_task("task-1", action_ids=["act-missing"])
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_plan_task_action_ids",
                    "task task-1 references unknown action id: act-missing",
                )
            ],
        )

    def test_action_relations_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["tasks"] = [
            self._valid_task("task-1", action_ids=["act-1"])
        ]
        runtime["actions"] = [
            self._valid_action("act-1", task_id="task-1", batch_id="batch-missing")
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_field",
                    "action act-1 references unknown batch_id registry entry: batch-missing",
                )
            ],
        )

    def test_action_relations_unknown_task_id_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["generation_id"] = "plan-001"
        runtime["plan"]["tasks"] = [self._valid_task("task-1")]
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="read.plan",
                task_id="task-missing",
                status="planned",
                plan_generation_id="plan-001",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_field",
                    "action act-1 references unknown task id: task-missing",
                )
            ],
        )

    def test_action_relations_task_membership_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["generation_id"] = "plan-001"
        runtime["plan"]["tasks"] = [self._valid_task("task-1", action_ids=[])]
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="read.plan",
                task_id="task-1",
                status="planned",
                plan_generation_id="plan-001",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_field",
                    "task task-1 must include action act-1 in action_ids",
                )
            ],
        )

    def test_action_relations_unknown_approval_id_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="fs.write_patch",
                status="applied",
                approval_id="apr-missing",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_field",
                    "action act-1 references unknown approval id: apr-missing",
                )
            ],
        )

    def test_action_relations_pending_approval_resolved_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["approvals"]["items"] = [
            self._valid_approval("apr-1", status="approved")
        ]
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="fs.write_patch",
                approval_id="apr-1",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_status",
                    "action act-1 cannot be pending_approval with resolved approval apr-1",
                )
            ],
        )

    def test_action_relations_applied_rejected_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["approvals"]["items"] = [
            self._valid_approval("apr-1", status="rejected")
        ]
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="fs.write_patch",
                status="applied",
                approval_id="apr-1",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_status",
                    "action act-1 cannot be applied with rejected approval apr-1",
                ),
                (
                    "invalid_agent_action_status",
                    "action act-1 kind fs.write_patch requires approval apr-1 to be approved, got rejected",
                ),
            ],
        )

    def test_action_relations_legacy_single_task_fallback_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["plan"]["status"] = "ready"
        runtime["plan"]["tasks"] = [
            self._valid_task("task-1", action_ids=["act-1"])
        ]
        runtime["approvals"]["items"] = [
            self._valid_approval(
                "apr-1",
                status="approved",
                task_id="",
                target="tracked.txt",
            )
        ]
        runtime["actions"] = [
            self._valid_action(
                "act-1",
                kind="fs.write_patch",
                status="applied",
                task_id="task-1",
                batch_id="batch-missing",
                approval_id="apr-1",
                target="tracked.txt",
            )
        ]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_action_field",
                    "action act-1 references unknown batch_id registry entry: batch-missing",
                )
            ],
        )

    def test_verification_relations_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["verification"]["required_command_ids"] = ["cmd-missing"]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                (
                    "invalid_agent_verification_required_command_ids",
                    "unknown verification command id: cmd-missing",
                )
            ],
        )

    def test_mixed_error_order(self) -> None:
        runtime = self._valid_runtime()
        runtime["memory"] = "oops"
        runtime["verification"]["required_command_ids"] = ["cmd-missing"]
        self.assertEqual(
            self._ordered_errors(runtime),
            [
                ("invalid_agent_memory", "agent_runtime.memory must be an object"),
                (
                    "invalid_agent_verification_required_command_ids",
                    "unknown verification command id: cmd-missing",
                ),
            ],
        )
