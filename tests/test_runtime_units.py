from __future__ import annotations

import hashlib
import tempfile
import unittest
from pathlib import Path

from core.action_identity import action_runtime_signature, matches_action_retry_identity
from core.action_runtime import compute_action_fingerprint
from core.decision_runtime import choose_next_task, evaluate_task_selection_consistency
from core.discipline_runtime import (
    build_action_evidence_token,
    evaluate_action_effectiveness,
    evaluate_retry_discipline,
)
from core.memory_runtime import sync_success_memory_notes
from core.success_memory import parse_success_memory_note
from core.work_profile import derive_task_work_profile, derive_task_work_profiles


class RuntimeUnitTests(unittest.TestCase):
    def test_action_runtime_signature_extracts_kind_target_and_fingerprint(self) -> None:
        action = {
            "kind": "fs.create_file",
            "target": "draft.txt",
            "details": {"fingerprint": "fp-123"},
        }

        self.assertEqual(
            action_runtime_signature(action),
            ("fs.create_file", "draft.txt", "fp-123"),
        )

    def test_matches_action_retry_identity_prefers_stored_fingerprint(self) -> None:
        action = {
            "kind": "fs.create_file",
            "target": "draft.txt",
            "details": {"fingerprint": "fp-123"},
        }
        normalized_action = {
            "kind": "fs.create_file",
            "path": "draft.txt",
            "content": "alpha\n",
        }

        self.assertTrue(matches_action_retry_identity(action, normalized_action, "fp-123"))
        self.assertFalse(matches_action_retry_identity(action, normalized_action, "fp-other"))

    def test_matches_action_retry_identity_keeps_legacy_target_fallback_narrow(self) -> None:
        move_action = {
            "kind": "fs.move",
            "target": "draft.txt -> moved.txt",
            "details": {},
        }
        normalized_move = {
            "kind": "fs.move",
            "from": "draft.txt",
            "to": "moved.txt",
            "overwrite": True,
        }
        exec_action = {
            "kind": "exec.command",
            "target": "cmd-001",
            "details": {},
        }

        self.assertTrue(matches_action_retry_identity(move_action, normalized_move, ""))
        self.assertFalse(
            matches_action_retry_identity(
                exec_action,
                {"kind": "exec.command", "command_id": "cmd-001"},
                "",
            )
        )

    def test_derive_task_work_profile_classifies_state_only_task_as_light(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Comprar frutas",
                        "status": "ready",
                        "details": "Comprar frutas",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    }
                ],
            },
            "execution_policy": {
                "autonomy_level": "A1",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [],
            "verification": {
                "required_command_ids": [],
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

        profile = derive_task_work_profile(agent_runtime, agent_runtime["plan"]["tasks"][0])

        self.assertEqual(profile["workload_mode"], "light")
        self.assertEqual(profile["work_unit_kind"], "state_only")
        self.assertFalse(profile["requires_working_set"])
        self.assertFalse(profile["requires_acceptance_criteria"])

    def test_derive_task_work_profiles_keeps_light_task_light_in_mixed_governed_plan(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Lista simples",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    },
                    {
                        "id": "task-2",
                        "title": "Patch governado",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["src/app.py"],
                        "acceptance_criteria": ["pytest -q passes"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {
                "commands": [
                    {
                        "id": "cmd-001",
                        "argv": ["pytest", "-q"],
                        "cwd": ".",
                        "timeout_ms": 1000,
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

        profiles = {item["id"]: item for item in derive_task_work_profiles(agent_runtime)}

        self.assertEqual(profiles["task-1"]["workload_mode"], "light")
        self.assertEqual(profiles["task-1"]["work_unit_kind"], "state_only")
        self.assertEqual(profiles["task-2"]["workload_mode"], "heavy")
        self.assertEqual(profiles["task-2"]["work_unit_kind"], "governed_execution")

    def test_choose_next_task_prefers_running_task_over_higher_priority_ready_task(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "running",
                "current_task_id": "task-running",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-running",
                        "title": "Running but expensive",
                        "status": "running",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["wide/a.txt", "wide/b.txt", "wide/c.txt", "wide/d.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    },
                    {
                        "id": "task-ready",
                        "title": "Ready and cheaper",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["single.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [],
            "verification": {
                "required_command_ids": [],
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

        selection = choose_next_task(agent_runtime)

        self.assertEqual(selection["task_id"], "task-running")
        alternatives = {item["task_id"]: item["reason"] for item in selection["rejected_alternatives"]}
        self.assertIn("lower priority than selected task", alternatives["task-ready"])

    def test_choose_next_task_treats_lightweight_state_only_task_without_technical_penalties(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Organizar a semana",
                        "status": "ready",
                        "details": "Organizar a semana",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    }
                ],
            },
            "execution_policy": {
                "autonomy_level": "A1",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [],
            "verification": {
                "required_command_ids": [],
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

        selection = choose_next_task(agent_runtime)
        assessment = selection["assessments"][0]

        self.assertEqual(selection["task_id"], "task-1")
        self.assertEqual(assessment["workload_mode"], "light")
        self.assertEqual(assessment["work_unit_kind"], "state_only")
        self.assertNotIn("working set is undefined", assessment["evidence"])
        self.assertNotIn("acceptance criteria are missing", assessment["evidence"])

    def test_choose_next_task_prefers_scoped_governed_task_over_light_state_task(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Lista simples",
                        "status": "ready",
                        "details": "Lista simples",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    },
                    {
                        "id": "task-2",
                        "title": "Patch governado",
                        "status": "ready",
                        "details": "Patch governado",
                        "depends_on": [],
                        "working_set": ["src/app.py"],
                        "acceptance_criteria": ["pytest -q passes"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": [{"id": "cmd-001", "argv": ["pytest", "-q"], "cwd": ".", "timeout_ms": 1000, "determinism": "high", "side_effect": "read_only", "risk": "low", "allow_in_verify": True}]},
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

        selection = choose_next_task(agent_runtime)

        self.assertEqual(selection["task_id"], "task-2")
        alternatives = {item["id"]: item["priority"] for item in selection["assessments"]}
        self.assertGreater(alternatives["task-2"], alternatives["task-1"])

    def test_choose_next_task_uses_recent_events_only_for_provenance(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-2",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Lista simples",
                        "status": "ready",
                        "details": "Lista simples",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    },
                    {
                        "id": "task-2",
                        "title": "Patch governado",
                        "status": "ready",
                        "details": "Patch governado",
                        "depends_on": [],
                        "working_set": ["src/app.py"],
                        "acceptance_criteria": ["pytest -q passes"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {
                "commands": [
                    {
                        "id": "cmd-001",
                        "argv": ["pytest", "-q"],
                        "cwd": ".",
                        "timeout_ms": 1000,
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
        recent_events = (
            {
                "event_id": "plan-abc12345:000001",
                "trace_thread_id": "plan-abc12345",
                "recorded_at": "2026-04-14T00:00:00+00:00",
                "revision": 2,
                "event": "plan_updated",
                "event_type": "plan_updated",
                "phase": "plan",
                "step": "plan_updated",
                "parent_event_id": "",
                "tasks": ["task-1", "task-2"],
            },
            {
                "event_id": "plan-abc12345:000002",
                "trace_thread_id": "plan-abc12345",
                "recorded_at": "2026-04-14T00:00:01+00:00",
                "revision": 2,
                "event": "task_selected",
                "event_type": "task_selected",
                "phase": "decision",
                "step": "task_selected",
                "parent_event_id": "plan-abc12345:000001",
                "selected_task_id": "task-2",
            },
        )

        baseline = choose_next_task(agent_runtime)
        selection = choose_next_task(agent_runtime, recent_events)

        self.assertEqual(selection["task_id"], baseline["task_id"])
        self.assertEqual(selection["priority"], baseline["priority"])
        self.assertEqual(baseline["evidence_event_ids"], [])
        self.assertEqual(
            selection["evidence_event_ids"],
            ["plan-abc12345:000001", "plan-abc12345:000002"],
        )

    def test_task_selection_consistency_detects_stale_current_task(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Lista simples",
                        "status": "ready",
                        "details": "Lista simples",
                        "depends_on": [],
                        "working_set": [],
                        "acceptance_criteria": [],
                        "action_ids": [],
                    },
                    {
                        "id": "task-2",
                        "title": "Patch governado",
                        "status": "ready",
                        "details": "Patch governado",
                        "depends_on": [],
                        "working_set": ["src/app.py"],
                        "acceptance_criteria": ["pytest -q passes"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {
                "commands": [
                    {
                        "id": "cmd-001",
                        "argv": ["pytest", "-q"],
                        "cwd": ".",
                        "timeout_ms": 1000,
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

        replay = evaluate_task_selection_consistency(agent_runtime)

        self.assertEqual(replay["status"], "mismatch")
        self.assertEqual(replay["current_task_id"], "task-1")
        self.assertEqual(replay["derived_task_id"], "task-2")
        self.assertGreater(replay["priority_gap"], 0)

    def test_choose_next_task_penalizes_high_pending_action_burden_without_verified_closure(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-clean",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-burden",
                        "title": "Burdened task",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["draft-a.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": ["act-001", "act-002", "act-003"],
                    },
                    {
                        "id": "task-clean",
                        "title": "Clean task",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["draft-b.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-1"},
                },
                {
                    "id": "act-002",
                    "kind": "fs.write_patch",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-2"},
                },
                {
                    "id": "act-003",
                    "kind": "fs.move",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-3"},
                },
            ],
            "verification": {
                "required_command_ids": [],
                "pending_action_ids": ["act-001", "act-002", "act-003"],
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

        selection = choose_next_task(agent_runtime)
        assessments = {item["id"]: item for item in selection["assessments"]}

        self.assertEqual(selection["task_id"], "task-clean")
        self.assertIn(
            "task has high pending action burden without verified closure (3 pending actions)",
            assessments["task-burden"]["evidence"],
        )
        self.assertIn("pending_action_burden=3", assessments["task-burden"]["recent_history"])
        self.assertLess(assessments["task-burden"]["priority"], assessments["task-clean"]["priority"])

    def test_choose_next_task_does_not_flag_pending_action_burden_after_pending_actions_clear(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "ready",
                "current_task_id": "task-verified",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-verified",
                        "title": "Verified task",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["draft-a.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": ["act-001", "act-002", "act-003"],
                    }
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-1"},
                },
                {
                    "id": "act-002",
                    "kind": "fs.write_patch",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-2"},
                },
                {
                    "id": "act-003",
                    "kind": "fs.move",
                    "target": "draft-a.txt",
                    "status": "applied",
                    "details": {"fingerprint": "fp-3"},
                },
            ],
            "verification": {
                "required_command_ids": [],
                "pending_action_ids": [],
                "last_run_at": "2026-04-14T00:00:00+00:00",
                "status": "passed",
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

        selection = choose_next_task(agent_runtime)
        assessment = selection["assessments"][0]

        self.assertEqual(selection["task_id"], "task-verified")
        self.assertNotIn(
            "task has high pending action burden without verified closure (3 pending actions)",
            assessment["evidence"],
        )
        self.assertNotIn("pending_action_burden=3", assessment["recent_history"])

    def test_evaluate_action_effectiveness_blocks_no_effect_patch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "draft.txt"
            target.write_text("alpha\n", encoding="utf-8")
            normalized_action = {
                "kind": "fs.write_patch",
                "path": "draft.txt",
                "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                "replacements": [{"old": "alpha", "new": "alpha", "count": 1}],
            }

            result = evaluate_action_effectiveness(root, normalized_action)

            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason_code"], "action_no_effect")

    def test_evaluate_action_effectiveness_blocks_same_path_move_when_source_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            target = root / "draft.txt"
            target.write_text("alpha\n", encoding="utf-8")
            normalized_action = {
                "kind": "fs.move",
                "from": "draft.txt",
                "to": "./draft.txt",
                "overwrite": True,
            }

            result = evaluate_action_effectiveness(root, normalized_action)

            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason_code"], "action_no_effect")

    def test_exec_command_retry_is_blocked_without_new_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            normalized_action = {"kind": "exec.command", "command_id": "cmd-001"}
            agent_runtime = {
                "verification": {
                    "status": "passed",
                    "pending_action_ids": [],
                    "last_run_at": "2026-04-13T00:00:00+00:00",
                },
                "actions": [],
                "_recent_events": [],
            }
            fingerprint = "fingerprint-cmd-001"
            evidence_token = build_action_evidence_token(root, normalized_action, agent_runtime, "task-001")
            agent_runtime["actions"].append(
                {
                    "id": "act-cmd-001",
                    "kind": "exec.command",
                    "target": "cmd-001",
                    "status": "applied",
                    "details": {
                        "fingerprint": fingerprint,
                        "evidence_token": evidence_token,
                    },
                    "updated_at": "2026-04-13T00:00:00+00:00",
                }
            )

            result = evaluate_retry_discipline(
                root,
                normalized_action,
                fingerprint,
                agent_runtime,
                "task-001",
                retry_justification="",
            )

            self.assertFalse(result["allowed"])
            self.assertEqual(result["reason_code"], "retry_blocked_no_new_evidence")

    def test_exec_command_retry_allows_registry_snapshot_drift_as_new_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            payload = {
                "id": "act-cmd-001",
                "kind": "exec.command",
                "summary": "run command",
                "command_id": "cmd-001",
            }
            normalized_action = {"kind": "exec.command", "command_id": "cmd-001"}
            initial_command = {
                "id": "cmd-001",
                "argv": ["python", "-c", "print('alpha')"],
                "cwd": ".",
                "timeout_ms": 120000,
                "determinism": "high",
                "side_effect": "workspace_write",
                "risk": "medium",
                "allow_in_verify": False,
            }
            agent_runtime = {
                "verification": {
                    "status": "passed",
                    "pending_action_ids": [],
                    "last_run_at": "2026-04-13T00:00:00+00:00",
                },
                "command_registry": {"commands": [dict(initial_command)]},
                "actions": [],
                "_recent_events": [],
            }
            fingerprint_alpha = compute_action_fingerprint(payload, command_registry={"cmd-001": dict(initial_command)})
            evidence_alpha = build_action_evidence_token(root, normalized_action, agent_runtime, "task-001")
            agent_runtime["actions"].append(
                {
                    "id": "act-cmd-001",
                    "kind": "exec.command",
                    "target": "cmd-001",
                    "status": "applied",
                    "details": {
                        "fingerprint": fingerprint_alpha,
                        "evidence_token": evidence_alpha,
                    },
                    "updated_at": "2026-04-13T00:00:00+00:00",
                }
            )

            mutated_command = dict(initial_command)
            mutated_command["argv"] = ["python", "-c", "print('beta')"]
            agent_runtime["command_registry"]["commands"][0] = mutated_command
            fingerprint_beta = compute_action_fingerprint(payload, command_registry={"cmd-001": mutated_command})

            result = evaluate_retry_discipline(
                root,
                normalized_action,
                fingerprint_beta,
                agent_runtime,
                "task-001",
                retry_justification="",
            )

            self.assertTrue(result["allowed"])
            self.assertEqual(result["redundant_attempts"], 0)

    def test_sync_success_memory_notes_locks_first_subject_consolidation(self) -> None:
        notes = []
        first_success_records = [
            {
                "task_id": "task-a",
                "context": "title=task-a; working_set=single; acceptance=defined",
                "action_kinds": ["fs.create_file"],
                "result": "task task-a promoted",
                "cost": 12,
                "reason": "bounded working set",
                "working_set_bucket": "single",
                "acceptance_defined": True,
                "has_sensitive_actions": False,
                "pattern_signature": "ws=single|acceptance=defined|actions=fs.create_file|sensitive=no",
                "recorded_at": "2026-04-13T00:00:00+00:00",
            },
        ]

        updated = sync_success_memory_notes(notes, first_success_records)
        repeated = sync_success_memory_notes(
            updated,
            [
                {
                    "task_id": "task-b",
                    "context": "title=task-b; working_set=single; acceptance=defined",
                    "action_kinds": ["fs.create_file"],
                    "result": "task task-b promoted",
                    "cost": 18,
                    "reason": "same pattern",
                    "working_set_bucket": "single",
                    "acceptance_defined": True,
                    "has_sensitive_actions": False,
                    "pattern_signature": "ws=single|acceptance=defined|actions=fs.create_file|sensitive=no",
                    "recorded_at": "2026-04-13T00:00:10+00:00",
                }
            ],
        )
        distinct = sync_success_memory_notes(
            repeated,
            [
                {
                    "task_id": "task-c",
                    "context": "title=task-c; working_set=wide; acceptance=missing",
                    "action_kinds": ["fs.move"],
                    "result": "task task-c promoted",
                    "cost": 20,
                    "reason": "distinct pattern",
                    "working_set_bucket": "wide",
                    "acceptance_defined": False,
                    "has_sensitive_actions": True,
                    "pattern_signature": "ws=wide|acceptance=missing|actions=fs.move|sensitive=yes",
                    "recorded_at": "2026-04-13T00:00:20+00:00",
                }
            ],
        )

        self.assertEqual(len(updated), 1)
        self.assertEqual(len(repeated), 1)
        self.assertEqual(len(distinct), 2)
        note = repeated[0]
        self.assertTrue(note["source"].startswith("decision_success|task=task-a|"))
        parsed = parse_success_memory_note(note)
        self.assertIsNotNone(parsed)
        assert parsed is not None
        self.assertEqual(parsed["task_id"], "task-a")
        self.assertIn("first verified success for subject", note["summary"])
        self.assertNotIn("task-b", note["summary"])
        self.assertTrue(any(item["source"].startswith("decision_success|task=task-c|") for item in distinct))

    def test_choose_next_task_uses_consolidated_success_memory_weight(self) -> None:
        agent_runtime = {
            "plan": {
                "goal": "g",
                "summary": "s",
                "status": "running",
                "current_task_id": "task-1",
                "updated_at": "",
                "tasks": [
                    {
                        "id": "task-1",
                        "title": "Consolidated pattern",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["single.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    },
                    {
                        "id": "task-2",
                        "title": "No memory support",
                        "status": "ready",
                        "details": "",
                        "depends_on": [],
                        "working_set": ["other.txt"],
                        "acceptance_criteria": ["done"],
                        "action_ids": [],
                    },
                ],
            },
            "execution_policy": {
                "autonomy_level": "A2",
                "protected_paths": [],
                "blocked_command_prefixes": [],
                "approval_required_kinds": [],
            },
            "command_registry": {"commands": []},
            "approvals": {"items": []},
            "actions": [],
            "verification": {
                "required_command_ids": [],
                "pending_action_ids": [],
                "last_run_at": "",
                "status": "idle",
                "checks": [],
            },
            "memory": {
                "notes": [
                    {
                        "id": "workflow-success-1",
                        "kind": "workflow",
                        "summary": "first verified success for subject ws=single|acceptance=defined|actions=fs.create_file|sensitive=no: context: title=task-a; working_set=single; acceptance=defined; action: fs.create_file; result: task task-a promoted; cost: 12; reason: bounded working set",
                        "source": "decision_success|task=task-a|ws=single|acceptance=1|actions=fs.create_file|sensitive=0|cost=12",
                        "ttl_days": 21,
                        "updated_at": "2026-04-13T00:00:10+00:00",
                    }
                ]
            },
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

        selection = choose_next_task(agent_runtime)

        self.assertEqual(selection["task_id"], "task-1")
        self.assertIn("task matches 1 verified success pattern(s)", selection["evidence"])
        self.assertGreater(selection["priority"], 0)


class StoreProtocolContractTests(unittest.TestCase):
    def test_action_store_surface_is_satisfied_by_state_store(self) -> None:
        from core.state_store import StateStore
        from core.store_protocols import ActionStoreSurface

        with tempfile.TemporaryDirectory() as d:
            store = StateStore(d)
            self.assertIsInstance(store, ActionStoreSurface)

    def test_verification_store_surface_is_satisfied_by_state_store(self) -> None:
        from core.state_store import StateStore
        from core.store_protocols import VerificationStoreSurface

        with tempfile.TemporaryDirectory() as d:
            store = StateStore(d)
            self.assertIsInstance(store, VerificationStoreSurface)

    def test_inline_sandbox_store_satisfies_action_store_surface(self) -> None:
        from core.store_protocols import ActionStoreSurface

        with tempfile.TemporaryDirectory() as d:
            root = Path(d)
            sandbox_store = type(
                "SandboxStore",
                (),
                {
                    "cerebro_dir": root / ".cerebro",
                    "artifacts_dir": root / ".cerebro" / "artifacts",
                    "trash_dir": root / ".cerebro" / "trash",
                },
            )()
            self.assertIsInstance(sandbox_store, ActionStoreSurface)

    def test_action_store_surface_rejects_object_missing_required_attrs(self) -> None:
        from core.store_protocols import ActionStoreSurface

        incomplete = type("Incomplete", (), {"cerebro_dir": Path("/tmp")})()
        self.assertNotIsInstance(incomplete, ActionStoreSurface)

    def test_store_protocols_module_exports_both_surfaces(self) -> None:
        import core.store_protocols as sp

        self.assertTrue(hasattr(sp, "ActionStoreSurface"))
        self.assertTrue(hasattr(sp, "VerificationStoreSurface"))

    def test_action_runtime_store_params_are_annotated(self) -> None:
        import inspect
        import core.action_runtime as ar

        for fn_name in ("apply_action", "rollback_action", "preflight_apply_batch", "guarded_apply_batch"):
            fn = getattr(ar, fn_name)
            hints = {k: str(v) for k, v in inspect.get_annotations(fn).items()}
            self.assertIn("store", hints, f"{fn_name} missing store annotation")
            self.assertIn("ActionStoreSurface", hints["store"], f"{fn_name} store not typed as ActionStoreSurface")

    def test_verification_runtime_store_params_are_annotated(self) -> None:
        import inspect
        import core.verification_runtime as vr

        for fn_name in ("execute_verification_cycle", "run_verification_commands"):
            fn = getattr(vr, fn_name)
            hints = {k: str(v) for k, v in inspect.get_annotations(fn).items()}
            self.assertIn("store", hints, f"{fn_name} missing store annotation")
            self.assertIn("VerificationStoreSurface", hints["store"], f"{fn_name} store not typed as VerificationStoreSurface")


if __name__ == "__main__":
    unittest.main()
