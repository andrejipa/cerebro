from __future__ import annotations

import hashlib
import io
import json
import os
import sys
import tempfile
import unittest
from contextlib import nullcontext, redirect_stdout
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from cli.commands._session_ownership import SESSION_TOKEN_ENV_VAR
from cli.commands.apply import run_apply
from cli.commands.analyze import run_analyze
from cli.commands.approve import run_approve
from cli.commands.init import run_init
from cli.main import main
from cli.commands.plan import run_plan
from cli.commands.rollback import run_rollback
from cli.commands.validate import run_validate
from cli.commands.verify import run_verify
from core import action_runtime as action_runtime_module
from core.agent_runtime import MAX_ACTION_HISTORY
from core.action_runtime import compute_action_fingerprint
from core.decision_runtime import choose_next_task
from core.schema import build_initial_state
from core.success_memory import build_success_memory_source
from core.state_store import (
    SESSION_CLAIMS_DIR_ENV_VAR,
    SESSION_LIVE_PROOFS_DIR_ENV_VAR,
    StateStore,
    StateStoreError,
)


class AlphaRuntimeTests(unittest.TestCase):
    def _read_session_claim(self, store: StateStore, claim_id: str) -> dict:
        claim_data, claim_errors = store._read_session_claim_file(claim_id)
        self.assertEqual(claim_errors, [])
        self.assertIsNotNone(claim_data)
        return claim_data

    def _read_session_claim_bytes(self, store: StateStore, claim_id: str, *, backend: str | None = None) -> bytes | None:
        return store._read_optional_session_claim_bytes(claim_id, backend=backend)

    def _plan_args(self, **overrides):
        base = {
            "goal": "Ship alpha",
            "summary": "Operate typed runtime.",
            "task": ["Task 1"],
            "verify_command": [],
            "autonomy_level": "A2",
            "protect_path": [],
            "blocked_command": [],
            "approval_required_kind": [],
        }
        base.update(overrides)
        return type("Args", (), base)

    def _approve_latest(self, root: Path, store: StateStore, *, decision: str = "approved") -> str:
        approval_id = store.read_agent_runtime()["approvals"]["items"][-1]["id"]
        exit_code = run_approve(
            root,
            type("Args", (), {"approval_id": approval_id, "decision": decision}),
        )
        self.assertEqual(exit_code, 0)
        return approval_id

    def _run_apply(
        self,
        root: Path,
        action_file: str | list[str],
        *,
        batch_id: str = "",
        retry_justification: str = "",
    ) -> int:
        return run_apply(
            root,
            type(
                "Args",
                (),
                {
                    "action_file": action_file,
                    "task_id": "",
                    "batch_id": batch_id,
                    "retry_justification": retry_justification,
                },
            ),
        )

    def _apply_with_approvals(
        self,
        root: Path,
        store: StateStore,
        action_file: str | list[str],
        *,
        batch_id: str = "",
        retry_justification: str = "",
    ) -> list[str]:
        approvals: list[str] = []
        for _ in range(8):
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = self._run_apply(
                    root,
                    action_file,
                    batch_id=batch_id,
                    retry_justification=retry_justification,
                )
            if exit_code == 0:
                return approvals
            self.assertIn("approval_required", stream.getvalue())
            approvals.append(self._approve_latest(root, store))
        self.fail("apply did not succeed after resolving required approvals")

    def _configure_read_only_exec_command_plan(
        self,
        store: StateStore,
        *,
        command_argv: list[str],
        goal: str,
        summary: str,
    ) -> None:
        validation = store.validate_state()
        store.update_agent_plan(
            {
                "goal": goal,
                "summary": summary,
                "tasks": [
                    {
                        "id": "task-001",
                        "title": "Run command",
                        "status": "ready",
                        "details": "Run command",
                        "depends_on": [],
                        "working_set": ["tracked.txt"],
                        "acceptance_criteria": ["verify succeeds"],
                        "action_ids": [],
                    }
                ],
                "command_registry": [
                    {
                        "id": "cmd-001",
                        "argv": command_argv,
                        "cwd": ".",
                        "timeout_ms": 120000,
                        "determinism": "high",
                        "side_effect": "read_only",
                        "risk": "low",
                        "allow_in_verify": False,
                    },
                    {
                        "id": "cmd-verify",
                        "argv": ["python", "-c", "print('verify-ok')"],
                        "cwd": ".",
                        "timeout_ms": 120000,
                        "determinism": "high",
                        "side_effect": "read_only",
                        "risk": "low",
                        "allow_in_verify": True,
                    },
                ],
                "required_command_ids": ["cmd-verify"],
                "autonomy_level": "A2",
                "protected_paths": [".cerebro/**", ".git/**"],
                "blocked_command_prefixes": ["rm"],
                "approval_required_kinds": [],
            },
            validated_revision=validation["revision"],
        )

    def test_initial_state_contains_agent_runtime(self) -> None:
        state = build_initial_state()

        self.assertIn("agent_runtime", state)
        self.assertEqual(state["agent_runtime"]["plan"]["status"], "idle")
        self.assertEqual(state["agent_runtime"]["execution_policy"]["autonomy_level"], "A1")
        self.assertEqual(state["agent_runtime"]["command_registry"]["commands"], [])
        self.assertEqual(state["agent_runtime"]["approvals"]["items"], [])
        self.assertEqual(state["agent_runtime"]["verification"]["required_command_ids"], [])
        self.assertEqual(state["agent_runtime"]["verification"]["pending_action_ids"], [])

    def test_plan_command_persists_plan_and_command_registry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            stream = io.StringIO()
            args = self._plan_args(
                task=["Define runtime", "Run verification"],
                verify_command=["python -c print('ok')"],
                autonomy_level="A2",
                protect_path=["secrets/**"],
                blocked_command=["powershell"],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            output = stream.getvalue()
            state = store.load_state()
            self.assertEqual(exit_code, 0)
            self.assertIn("plan_saved", output)
            self.assertEqual(state["agent_runtime"]["plan"]["goal"], "Ship alpha")
            self.assertEqual(len(state["agent_runtime"]["plan"]["tasks"]), 2)
            self.assertEqual(state["agent_runtime"]["command_registry"]["commands"][0]["id"], "cmd-001")
            self.assertEqual(state["agent_runtime"]["verification"]["required_command_ids"], ["cmd-001"])
            self.assertEqual(state["agent_runtime"]["execution_policy"]["autonomy_level"], "A2")
            self.assertIn("secrets/**", state["agent_runtime"]["execution_policy"]["protected_paths"])
            self.assertIn("powershell", state["agent_runtime"]["execution_policy"]["blocked_command_prefixes"])
            self.assertIn("fs.write_patch", state["agent_runtime"]["execution_policy"]["approval_required_kinds"])

    def test_plan_command_adapts_simple_domain_input_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="comprar arroz, leite, pao",
                input_file="",
                input_kind="list",
                verify_command=[],
            )

            exit_code = run_plan(root, args)

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 0)
            self.assertEqual(runtime["plan"]["goal"], "Complete listed items")
            self.assertEqual(runtime["plan"]["summary"], "Adapted from simple list input.")
            self.assertEqual([task["title"] for task in runtime["plan"]["tasks"]], ["comprar arroz", "leite", "pao"])

    def test_plan_command_resolves_relative_input_file_from_root_instead_of_process_cwd(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as other_dir:
            root = Path(tmp_dir)
            other_root = Path(other_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            (root / "input.txt").write_text("comprar arroz, leite, pao", encoding="utf-8")
            (other_root / "input.txt").write_text("wrong file", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="",
                input_file="input.txt",
                input_kind="list",
                verify_command=[],
            )

            previous_cwd = os.getcwd()
            try:
                os.chdir(other_root)
                exit_code = run_plan(root, args)
            finally:
                os.chdir(previous_cwd)

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 0)
            self.assertEqual(runtime["plan"]["goal"], "Complete listed items")
            self.assertEqual([task["title"] for task in runtime["plan"]["tasks"]], ["comprar arroz", "leite", "pao"])

    def test_plan_command_ignores_whitespace_goal_and_summary_overrides_for_domain_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            args = self._plan_args(
                goal="   ",
                summary="   ",
                task=[],
                input_text="Comprar leite",
                input_file="",
                input_kind="task",
                verify_command=[],
            )

            exit_code = run_plan(root, args)

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 0)
            self.assertEqual(runtime["plan"]["goal"], "Comprar leite")
            self.assertEqual(runtime["plan"]["summary"], "Adapted from single-task input.")

    def test_plan_command_reports_ambiguity_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="comprar arroz, leite, pao",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("AMBIGUITY DETECTED", output)
            self.assertIn("Possible interpretations:", output)
            self.assertIn("--input-kind list", output)
            self.assertIn("--input-kind task", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_reports_compound_instruction_ambiguity_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="review and merge",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("AMBIGUITY DETECTED", output)
            self.assertIn("rewrite-as-list", output)
            self.assertIn("rewrite the input as bullets, commas, or repeated --task flags", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_reports_long_compound_instruction_ambiguity_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="review the code and merge after final manual signoff",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("AMBIGUITY DETECTED", output)
            self.assertIn("rewrite-as-list", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_reports_semantic_ambiguity_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="organizar semana",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("AMBIGUITY DETECTED", output)
            self.assertIn("ambiguity_type: semantic", output)
            self.assertIn("ambiguity_level: high", output)
            self.assertIn("interpret as a lightweight checklist or flat task set", output)
            self.assertIn("interpret as a structured plan", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_reports_mixed_bullet_metadata_ambiguity_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="- Task A | id=alpha\n- Task B",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("AMBIGUITY DETECTED", output)
            self.assertIn("--input-kind list", output)
            self.assertIn("--input-kind structured", output)
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_rejects_invalid_domain_input_without_state_change(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="organiza isso",
                input_file="",
                input_kind="auto",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("domain_input_invalid", stream.getvalue())
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_plan_command_rejects_structured_verify_without_governed_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            before = store.load_state()
            stream = io.StringIO()

            args = self._plan_args(
                goal="",
                summary="",
                task=[],
                input_text="\n".join(
                    [
                        "goal: compras",
                        "verify: python -m unittest",
                        "- comprar arroz",
                        "- comprar leite",
                    ]
                ),
                input_file="",
                input_kind="structured",
                verify_command=[],
            )

            with redirect_stdout(stream):
                exit_code = run_plan(root, args)

            after = store.load_state()
            self.assertEqual(exit_code, 1)
            self.assertIn("domain_input_invalid", stream.getvalue())
            self.assertEqual(after["revision"], before["revision"])
            self.assertEqual(after["agent_runtime"], before["agent_runtime"])

    def test_sensitive_actions_require_approval_and_can_then_execute(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Mutate non-canonical files."))
            action_dir = root / "actions"
            action_dir.mkdir()

            create_file = action_dir / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            patch_file = action_dir / "patch.json"
            patch_file.write_text(
                json.dumps(
                    {
                        "id": "act-patch",
                        "kind": "fs.write_patch",
                        "summary": "patch draft",
                        "path": "draft.txt",
                        "expected_sha256": "",
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )
            move_file = action_dir / "move.json"
            move_file.write_text(
                json.dumps(
                    {
                        "id": "act-move",
                        "kind": "fs.move",
                        "summary": "move draft",
                        "from": "draft.txt",
                        "to": "notes/draft.txt",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            delete_file = action_dir / "delete.json"
            delete_file.write_text(
                json.dumps(
                    {
                        "id": "act-delete",
                        "kind": "fs.delete_soft",
                        "summary": "soft delete draft",
                        "path": "notes/draft.txt",
                    }
                ),
                encoding="utf-8",
            )

            create_exit = run_apply(root, type("Args", (), {"action_file": str(create_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(create_exit, 0)

            patch_payload = json.loads(patch_file.read_text(encoding="utf-8"))
            patch_payload["expected_sha256"] = store.compute_sha256("draft.txt")
            patch_file.write_text(json.dumps(patch_payload), encoding="utf-8")
            patch_stream = io.StringIO()
            with redirect_stdout(patch_stream):
                patch_exit = run_apply(root, type("Args", (), {"action_file": str(patch_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(patch_exit, 1)
            self.assertIn("approval_required", patch_stream.getvalue())
            patch_approval_id = self._approve_latest(root, store)
            patch_apply_exit = run_apply(root, type("Args", (), {"action_file": str(patch_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(patch_apply_exit, 0)

            move_stream = io.StringIO()
            with redirect_stdout(move_stream):
                move_exit = run_apply(root, type("Args", (), {"action_file": str(move_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(move_exit, 1)
            self.assertIn("approval_required", move_stream.getvalue())
            move_approval_id = self._approve_latest(root, store)
            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(move_file), "task_id": "", "batch_id": ""})), 0)

            delete_stream = io.StringIO()
            with redirect_stdout(delete_stream):
                delete_exit = run_apply(root, type("Args", (), {"action_file": str(delete_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(delete_exit, 1)
            self.assertIn("approval_required", delete_stream.getvalue())
            delete_approval_id = self._approve_latest(root, store)
            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(delete_file), "task_id": "", "batch_id": ""})), 0)

            state = store.load_state()
            self.assertFalse((root / "draft.txt").exists())
            self.assertFalse((root / "notes" / "draft.txt").exists())
            self.assertTrue((store.trash_dir / "act-delete" / "notes" / "draft.txt").exists())
            self.assertEqual(len(state["agent_runtime"]["actions"]), 4)
            self.assertEqual({patch_approval_id, move_approval_id, delete_approval_id}, {item["id"] for item in state["agent_runtime"]["approvals"]["items"]})
            applied_sensitive_actions = [item for item in state["agent_runtime"]["actions"] if item["approval_id"]]
            self.assertEqual(len(applied_sensitive_actions), 3)

    def test_apply_blocks_registered_source_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Protect canonical sources."))
            action_file = root / "blocked.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-blocked",
                        "kind": "fs.create_file",
                        "summary": "overwrite source",
                        "path": "tracked.txt",
                        "content": "changed",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("action_rejected", output)
            self.assertIn("registered context source", output)

    def test_verify_runs_registered_commands_and_persists_checks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Run one verification command.", verify_command=["python -c print('ok')"]))
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            output = stream.getvalue()
            state = store.load_state()
            self.assertEqual(exit_code, 0)
            self.assertIn("verification_passed", output)
            self.assertEqual(state["agent_runtime"]["verification"]["status"], "passed")
            self.assertEqual(state["agent_runtime"]["verification"]["state_check"]["status"], "passed")
            self.assertEqual(len(state["agent_runtime"]["verification"]["checks"]), 1)
            artifact_ref = state["agent_runtime"]["verification"]["checks"][0]["artifact_ref"]
            self.assertTrue((store.cerebro_dir / artifact_ref).exists())

    def test_verify_a1_policy_deny_returns_verification_failed_not_internal_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify policy denial",
                    "summary": "A1 should fail typed in verify.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify failure is typed"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A1",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            output = io.StringIO()
            previous_cwd = os.getcwd()
            try:
                os.chdir(root)
                with redirect_stdout(output):
                    exit_code = main(["verify"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output.getvalue())
            self.assertIn("autonomy level A1 does not allow command execution", output.getvalue())
            self.assertNotIn("internal_error", output.getvalue())

            verification = store.read_agent_runtime()["verification"]
            self.assertEqual(verification["status"], "idle")
            self.assertEqual(verification["checks"], [])
            self.assertFalse((store.artifacts_dir / "verification").exists())

    def test_verify_missing_executable_fails_cleanly_and_records_audit_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify launch failure",
                    "summary": "Missing executables must fail cleanly.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify failure is explicit"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["__definitely_missing_verify_executable__"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output.getvalue())
            self.assertIn("failed to execute verification command cmd-001", output.getvalue())
            self.assertNotIn("internal_error", output.getvalue())

            verification = store.read_agent_runtime()["verification"]
            self.assertEqual(verification["status"], "idle")
            self.assertEqual(verification["checks"], [])

            recent_events = store.read_recent_events(limit=8)
            matching = [event for event in recent_events if event.get("event") == "verify_failed" and event.get("command_id") == "cmd-001"]
            self.assertEqual(len(matching), 1)
            self.assertEqual(matching[0]["reason_code"], "command_execution_exception")

    def test_validate_fails_when_current_verification_artifact_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Verification artifact must stay live.", verify_command=["python -c print('ok')"]))

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            state = store.load_state()
            artifact_ref = state["agent_runtime"]["verification"]["checks"][0]["artifact_ref"]
            (store.cerebro_dir / artifact_ref).unlink()

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "runtime_artifact_missing")
            self.assertIn("agent_runtime.verification.checks[0].artifact_ref", result["errors"][0]["message"])

    def test_validate_fails_when_current_verification_artifact_content_diverges(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Verification artifact integrity.", verify_command=["python -c print('ok')"]))

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            state = store.load_state()
            artifact_ref = state["agent_runtime"]["verification"]["checks"][0]["artifact_ref"]
            (store.cerebro_dir / artifact_ref).write_text("tampered stdout\n", encoding="utf-8")

            result = store.validate_state()

            self.assertFalse(result["ok"])
            self.assertEqual(result["errors"][0]["code"], "runtime_artifact_hash_mismatch")
            self.assertIn("agent_runtime.verification.checks[0].artifact_ref", result["errors"][0]["message"])

    def test_verify_fails_when_command_mutates_workspace_and_real_root_stays_clean(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify safety",
                    "summary": "Verify must stay read-only.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Inspect tracked file",
                            "status": "ready",
                            "details": "Inspect tracked file",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                "from pathlib import Path; Path('verify-leak.txt').write_text('mutated', encoding='utf-8'); print('ok')",
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            output = stream.getvalue()
            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 1)
            self.assertIn("verification_failed", output)
            self.assertFalse((root / "verify-leak.txt").exists())
            self.assertEqual(runtime["verification"]["status"], "failed")
            self.assertIn(
                "mutated the observed sandbox state",
                runtime["verification"]["checks"][0]["message"],
            )
            self.assertTrue(store.validate_state()["ok"])

    def test_verify_fails_when_command_tampers_with_runtime_state_and_real_state_stays_canonical(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify safety",
                    "summary": "Verify must not tamper with runtime state.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Inspect runtime state",
                            "status": "ready",
                            "details": "Inspect runtime state",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    "import json; from pathlib import Path; "
                                    "state_path = Path('.cerebro/state.json'); "
                                    "data = json.loads(state_path.read_text(encoding='utf-8')); "
                                    "data['checkpoint']['summary'] = 'tampered by verify'; "
                                    "state_path.write_text(json.dumps(data), encoding='utf-8'); "
                                    "print('ok')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["verification"]["status"], "failed")
            self.assertIn(
                "changed .cerebro/state.json",
                runtime["verification"]["checks"][0]["message"],
            )
            self.assertNotEqual(store.load_state()["checkpoint"]["summary"], "tampered by verify")
            self.assertTrue(store.validate_state()["ok"])

    def test_verify_fails_and_restores_live_workspace_after_absolute_path_write(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            victim = root / "victim.txt"
            tracked.write_text("hello", encoding="utf-8")
            victim.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify sandbox escape",
                    "summary": "Verify must fail closed and restore the live project after absolute path tamper.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Tamper live workspace",
                            "status": "ready",
                            "details": "Tamper live workspace",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify fails and restores the live project"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    f"from pathlib import Path; "
                                    f"Path({str(root)!r}).joinpath('victim.txt').write_text('pwned\\n', encoding='utf-8'); "
                                    "print('ok')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["verification"]["status"], "failed")
            self.assertIn(
                "verify command mutated the live project outside the sandbox:",
                runtime["verification"]["checks"][0]["message"],
            )
            self.assertIn(
                "changed victim.txt",
                runtime["verification"]["checks"][0]["message"],
            )
            self.assertEqual(victim.read_text(encoding="utf-8"), "before\n")
            self.assertTrue(store.validate_state()["ok"])

    def test_verify_restores_live_workspace_from_pristine_snapshot_after_dual_tamper(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            victim = root / "victim.txt"
            tracked.write_text("hello", encoding="utf-8")
            victim.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify restore integrity",
                    "summary": "Verify must restore from a pristine snapshot even when sandbox and live files are both tampered.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Poison restore source",
                            "status": "ready",
                            "details": "Poison restore source",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify restores the original live file bytes"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    f"from pathlib import Path; "
                                    "Path('victim.txt').write_text('sandbox\\n', encoding='utf-8'); "
                                    f"Path({str(root)!r}).joinpath('victim.txt').write_text('live\\n', encoding='utf-8'); "
                                    "print('ok')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["verification"]["status"], "failed")
            self.assertIn("changed victim.txt", runtime["verification"]["checks"][0]["message"])
            self.assertEqual(victim.read_text(encoding="utf-8"), "before\n")
            self.assertTrue(store.validate_state()["ok"])

    def test_verify_redirects_session_authority_env_and_scrubs_session_token_for_subprocesses(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            with patch.dict(os.environ, {SESSION_CLAIMS_DIR_ENV_VAR: claims_dir}, clear=False):
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["tracked.txt"])
                validation = store.validate_state()
                session = store.open_session("alice", validated_revision=validation["revision"])
                before_claim = self._read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(before_claim)
                claim = self._read_session_claim(store, session["owner_claim_id"])
                before_live_proof = store._read_optional_session_live_proof_bytes(claim["live_proof_id"])
                validation = store.validate_state()
                store.update_agent_plan(
                    {
                        "goal": "Verify env isolation",
                        "summary": "Verify must not leak live session env or claims.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Probe session env",
                                "status": "ready",
                                "details": "Probe session env",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["verify succeeds"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [
                            {
                                "id": "cmd-001",
                                "argv": [
                                    "python",
                                    "-c",
                                    (
                                        "import os, sys; from pathlib import Path; "
                                        "claims = Path(os.environ['CEREBRO_SESSION_CLAIMS_DIR']); "
                                        "proofs = Path(os.environ['CEREBRO_SESSION_LIVE_PROOFS_DIR']); "
                                        "claim = claims / 'probe.json'; "
                                        "proof = proofs / 'probe.json'; "
                                        "claim.write_text('sandbox-only', encoding='utf-8'); "
                                        "proof.write_text('sandbox-only', encoding='utf-8'); "
                                        "print('secret=' + os.environ.get('INV2_SECRET', '')); "
                                        "print('lang=' + os.environ.get('LANG', '')); "
                                        "print('lc_all=' + os.environ.get('LC_ALL', '')); "
                                        "print('pyio=' + os.environ.get('PYTHONIOENCODING', '')); "
                                        "print('token=' + os.environ.get('CEREBRO_SESSION_TOKEN', ''))"
                                        "; print('path=' + os.environ.get('PATH', ''))"
                                        "; print('path_head=' + os.environ.get('PATH', '').split(os.pathsep)[0])"
                                        "; sys.stderr.write('stderr_secret=' + os.environ.get('INV2_SECRET', '') + '\\n')"
                                        "; sys.stderr.write('stderr_pyio=' + os.environ.get('PYTHONIOENCODING', ''))"
                                    ),
                                ],
                                "cwd": ".",
                                "timeout_ms": 120000,
                                "determinism": "high",
                                "side_effect": "read_only",
                                "risk": "low",
                                "allow_in_verify": True,
                            }
                        ],
                        "required_command_ids": ["cmd-001"],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                    expected_session_token=session["session_token"],
                )

                stream = io.StringIO()
                path_sentinel = "INV2-HOST-PATH-SENTINEL"
                current_path = os.environ.get("PATH", "")
                host_path = f"{path_sentinel}{os.pathsep}{current_path}" if current_path else path_sentinel
                with patch.dict(
                    os.environ,
                    {
                        "INV2_SECRET": "red-team-secret",
                        "LANG": "red-team-lang-secret",
                        "LC_ALL": "red-team-lc-secret",
                        "PYTHONIOENCODING": "red-team-pyio-secret",
                        "PATH": host_path,
                        SESSION_CLAIMS_DIR_ENV_VAR: claims_dir,
                        SESSION_TOKEN_ENV_VAR: session["session_token"],
                    },
                    clear=False,
                ):
                    with redirect_stdout(stream):
                        exit_code = run_verify(root, type("Args", (), {"command_id": []}))

                runtime = store.read_agent_runtime()
                artifact_ref = runtime["verification"]["checks"][0]["artifact_ref"]
                stdout_text = (store.cerebro_dir / artifact_ref).read_text(encoding="utf-8")
                stderr_text = (store.cerebro_dir / artifact_ref.replace(".stdout.txt", ".stderr.txt")).read_text(
                    encoding="utf-8"
                )
                self.assertEqual(exit_code, 0)
                self.assertEqual(before_claim, self._read_session_claim_bytes(store, session["owner_claim_id"]))
                self.assertEqual(before_live_proof, store._read_optional_session_live_proof_bytes(claim["live_proof_id"]))
                stdout_lines = stdout_text.splitlines()
                stderr_lines = stderr_text.splitlines()
                self.assertEqual(stdout_lines[0], "secret=")
                self.assertEqual(stdout_lines[1], "lang=")
                self.assertEqual(stdout_lines[2], "lc_all=")
                self.assertEqual(stdout_lines[3], "pyio=")
                self.assertEqual(stdout_lines[4], "token=")
                self.assertTrue(stdout_lines[5].startswith("path="))
                self.assertTrue(stdout_lines[6].startswith("path_head="))
                self.assertEqual(stderr_lines[0], "stderr_secret=")
                self.assertEqual(stderr_lines[1], "stderr_pyio=")
                self.assertNotIn("red-team-secret", stdout_text)
                self.assertNotIn("red-team-lang-secret", stdout_text)
                self.assertNotIn("red-team-lc-secret", stdout_text)
                self.assertNotIn("red-team-pyio-secret", stdout_text)
                self.assertNotIn("red-team-secret", stderr_text)
                self.assertNotIn("red-team-pyio-secret", stderr_text)
                self.assertNotIn(path_sentinel, stdout_lines[5])
                self.assertNotIn(path_sentinel, stdout_lines[6])
                self.assertTrue(store.validate_state()["ok"])

    @unittest.skipUnless(os.name == "nt", "PATH helper-chain smoke uses cmd.exe")
    def test_verify_preserves_resolved_command_parent_for_sibling_helper_chain(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as helper_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            session = store.open_session("alice", validated_revision=validation["revision"])
            validation = store.validate_state()
            (Path(helper_dir) / "helper.cmd").write_text("@echo helper-ok\r\n", encoding="utf-8")
            (Path(helper_dir) / "main.cmd").write_text("@echo off\r\nhelper.cmd\r\n", encoding="utf-8")
            store.update_agent_plan(
                {
                    "goal": "Verify resolved PATH compatibility",
                    "summary": "verify should keep the resolved command parent executable while artifacts stay scrubbed",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run sibling helper chain",
                            "status": "ready",
                            "details": "Run sibling helper chain",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds through resolved-command sibling helper lookup"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["main.cmd"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
                expected_session_token=session["session_token"],
            )

            helper_path = os.pathsep.join((helper_dir, os.environ.get("PATH", "")))
            with patch.dict(os.environ, {"PATH": helper_path}, clear=False):
                stream = io.StringIO()
                with redirect_stdout(stream):
                    exit_code = run_verify(root, type("Args", (), {"command_id": [], "session_token": session["session_token"]}))

            runtime = store.read_agent_runtime()
            artifact_ref = runtime["verification"]["checks"][0]["artifact_ref"]
            stdout_text = (store.cerebro_dir / artifact_ref).read_text(encoding="utf-8")
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout_text.strip(), "helper-ok")

    @unittest.skipUnless(os.name == "nt", "SYSTEMDRIVE regression is Windows-specific")
    def test_verify_redaction_keeps_legitimate_windows_drive_letters(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify artifact fidelity",
                    "summary": "verify redaction must not strip legitimate drive letters from artifacts",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run verify",
                            "status": "ready",
                            "details": "Run verify",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify preserves legitimate drive letters in stdout and stderr"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    "import sys; "
                                    "print('stdout=C:\\\\regression\\\\ok'); "
                                    "print('stderr=C:\\\\regression\\\\err', file=sys.stderr)"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            with patch.dict(os.environ, {"SYSTEMDRIVE": "C:"}, clear=False):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            runtime = store.read_agent_runtime()
            artifact_ref = runtime["verification"]["checks"][0]["artifact_ref"]
            stdout_text = (store.cerebro_dir / artifact_ref).read_text(encoding="utf-8")
            stderr_text = (store.cerebro_dir / artifact_ref.replace(".stdout.txt", ".stderr.txt")).read_text(
                encoding="utf-8"
            )
            self.assertEqual(exit_code, 0)
            self.assertEqual(stdout_text.strip(), r"stdout=C:\regression\ok")
            self.assertEqual(stderr_text.strip(), r"stderr=C:\regression\err")

    def test_verify_restores_live_external_session_claim_after_absolute_tamper_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            claims_context = (
                patch.dict(os.environ, {SESSION_CLAIMS_DIR_ENV_VAR: claims_dir}, clear=False)
                if os.name != "nt"
                else nullcontext()
            )
            with claims_context:
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["tracked.txt"])
                validation = store.validate_state()
                session = store.open_session("alice", validated_revision=validation["revision"])
                before_claim = self._read_session_claim_bytes(store, session["owner_claim_id"])
                self.assertIsNotNone(before_claim)
                claim_backend = store._session_claim_backend()
                if claim_backend == "wincred":
                    tamper_command = (
                        "from core.windows_credential_store import write_generic_credential; "
                        f"write_generic_credential({store._session_claim_target_name(session['owner_claim_id'])!r}, b'tampered'); "
                        "print('ok')"
                    )
                else:
                    claim_path = store._session_claim_path(session["owner_claim_id"])
                    tamper_command = (
                        f"from pathlib import Path; Path({str(claim_path)!r}).write_text('tampered', encoding='utf-8'); print('ok')"
                    )
                validation = store.validate_state()
                store.update_agent_plan(
                    {
                        "goal": "Verify live authority",
                        "summary": "Verify must fail and restore live session authority on absolute tamper.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Probe live claim",
                                "status": "ready",
                                "details": "Probe live claim",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["verify fails closed"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [
                            {
                                "id": "cmd-001",
                                "argv": ["python", "-c", tamper_command],
                                "cwd": ".",
                                "timeout_ms": 120000,
                                "determinism": "high",
                                "side_effect": "read_only",
                                "risk": "low",
                                "allow_in_verify": True,
                            }
                        ],
                        "required_command_ids": ["cmd-001"],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                    expected_session_token=session["session_token"],
                )

                stream = io.StringIO()
                with patch.dict(os.environ, {SESSION_TOKEN_ENV_VAR: session["session_token"]}, clear=False):
                    with redirect_stdout(stream):
                        exit_code = run_verify(root, type("Args", (), {"command_id": []}))

                runtime = store.read_agent_runtime()
                self.assertEqual(exit_code, 1)
                self.assertEqual(runtime["verification"]["status"], "failed")
                self.assertIn("live runtime authority", runtime["verification"]["checks"][0]["message"])
                self.assertIn("external session claim", runtime["verification"]["checks"][0]["message"])
                self.assertEqual(before_claim, self._read_session_claim_bytes(store, session["owner_claim_id"]))
                self.assertTrue(store.validate_state()["ok"])

    def test_verify_restores_live_external_session_proof_after_absolute_tamper_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as claims_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            with patch.dict(os.environ, {SESSION_CLAIMS_DIR_ENV_VAR: claims_dir}, clear=False):
                run_init(root, None)
                store = StateStore(root)
                store.register_sources(["tracked.txt"])
                validation = store.validate_state()
                session = store.open_session("alice", validated_revision=validation["revision"])
                claim = self._read_session_claim(store, session["owner_claim_id"])
                live_proof_id = claim["live_proof_id"]
                before_live_proof = store._read_optional_session_live_proof_bytes(live_proof_id)
                backend = store._session_live_proof_backend()
                if backend == "wincred":
                    original_live_proof, live_proof_errors = store._read_session_live_proof_file(live_proof_id)
                    self.assertEqual(live_proof_errors, [])
                    self.assertIsNotNone(original_live_proof)
                    tampered_live_proof = dict(original_live_proof)
                    tampered_live_proof["session_live_proof"] = "tampered"
                    tamper_command = (
                        "from core.windows_credential_store import write_generic_credential; "
                        f"write_generic_credential({store._session_live_proof_target_name(live_proof_id)!r}, "
                        f"{(json.dumps(tampered_live_proof, ensure_ascii=False) + chr(10)).encode('utf-8')!r}); "
                        "print('ok')"
                    )
                else:
                    live_proof_path = store._session_live_proof_path(live_proof_id)
                    tamper_command = (
                        f"from pathlib import Path; Path({str(live_proof_path)!r}).write_text('tampered', encoding='utf-8'); print('ok')"
                    )
                validation = store.validate_state()
                store.update_agent_plan(
                    {
                        "goal": "Verify live authority",
                        "summary": "Verify must fail and restore live session proof on absolute tamper.",
                        "tasks": [
                            {
                                "id": "task-001",
                                "title": "Probe live proof",
                                "status": "ready",
                                "details": "Probe live proof",
                                "depends_on": [],
                                "working_set": ["tracked.txt"],
                                "acceptance_criteria": ["verify fails closed"],
                                "action_ids": [],
                            }
                        ],
                        "command_registry": [
                            {
                                "id": "cmd-001",
                                "argv": [
                                    "python",
                                    "-c",
                                    tamper_command,
                                ],
                                "cwd": ".",
                                "timeout_ms": 120000,
                                "determinism": "high",
                                "side_effect": "read_only",
                                "risk": "low",
                                "allow_in_verify": True,
                            }
                        ],
                        "required_command_ids": ["cmd-001"],
                        "autonomy_level": "A2",
                        "protected_paths": [".cerebro/**", ".git/**"],
                        "blocked_command_prefixes": ["rm"],
                        "approval_required_kinds": ["fs.write_patch"],
                    },
                    validated_revision=validation["revision"],
                    expected_session_token=session["session_token"],
                )

                stream = io.StringIO()
                with patch.dict(os.environ, {SESSION_TOKEN_ENV_VAR: session["session_token"]}, clear=False):
                    with redirect_stdout(stream):
                        exit_code = run_verify(root, type("Args", (), {"command_id": []}))

                runtime = store.read_agent_runtime()
                self.assertEqual(exit_code, 1)
                self.assertEqual(runtime["verification"]["status"], "failed")
                self.assertIn("live runtime authority", runtime["verification"]["checks"][0]["message"])
                self.assertIn("external session live proof", runtime["verification"]["checks"][0]["message"])
                self.assertEqual(before_live_proof, store._read_optional_session_live_proof_bytes(live_proof_id))
                self.assertTrue(store.validate_state()["ok"])

    def test_verify_restores_live_state_after_absolute_tamper_attempt(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Verify live state",
                    "summary": "Verify must fail and restore live runtime state on absolute tamper.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Probe live state",
                            "status": "ready",
                            "details": "Probe live state",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify fails closed"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    "import json; from pathlib import Path; "
                                    f"state_path = Path({str(store.state_path)!r}); "
                                    "data = json.loads(state_path.read_text(encoding='utf-8')); "
                                    "data['checkpoint']['summary'] = 'absolute tamper'; "
                                    "state_path.write_text(json.dumps(data), encoding='utf-8'); "
                                    "print('ok')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            before_summary = store.load_state()["checkpoint"]["summary"]
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 1)
            self.assertEqual(runtime["verification"]["status"], "failed")
            self.assertIn("live runtime authority", runtime["verification"]["checks"][0]["message"])
            self.assertIn("state.json", runtime["verification"]["checks"][0]["message"])
            self.assertEqual(store.load_state()["checkpoint"]["summary"], before_summary)
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_is_rejected_before_execution_and_keeps_verify_passed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Safe exec command",
                    "summary": "Read-only command without drift should stay operational only.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('apply-ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": False,
                        },
                        {
                            "id": "cmd-verify",
                            "argv": ["python", "-c", "print('verify-ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                    ],
                    "required_command_ids": ["cmd-verify"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertEqual(runtime["plan"]["tasks"][0]["status"], "ready")
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_rejects_relative_workspace_mutation_without_touching_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Unsafe exec command",
                    "summary": "Read-only command must not mutate root.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                "from pathlib import Path; Path('exec-leak.txt').write_text('mutated', encoding='utf-8'); print('ok')",
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": False,
                        },
                        {
                            "id": "cmd-verify",
                            "argv": ["python", "-c", "print('verify-ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                    ],
                    "required_command_ids": ["cmd-verify"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertFalse((root / "exec-leak.txt").exists())
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_rejects_relative_runtime_tamper_without_touching_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Unsafe exec command",
                    "summary": "Read-only command must not mutate runtime state.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                (
                                    "import json; from pathlib import Path; "
                                    "state_path = Path('.cerebro/state.json'); "
                                    "data = json.loads(state_path.read_text(encoding='utf-8')); "
                                    "data['checkpoint']['summary'] = 'tampered by apply'; "
                                    "state_path.write_text(json.dumps(data), encoding='utf-8'); "
                                    "print('ok')"
                                ),
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": False,
                        },
                        {
                            "id": "cmd-verify",
                            "argv": ["python", "-c", "print('verify-ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                    ],
                    "required_command_ids": ["cmd-verify"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": [],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertNotEqual(store.load_state()["checkpoint"]["summary"], "tampered by apply")
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_rejects_absolute_workspace_mutation_without_touching_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            target_literal = json.dumps(str(tracked))
            self._configure_read_only_exec_command_plan(
                store,
                command_argv=[
                    "python",
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({target_literal}).write_text('tampered\\n', encoding='utf-8'); "
                        "print('ok')"
                    ),
                ],
                goal="Unsafe exec command",
                summary="Absolute path writes to the live root must fail closed.",
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(tracked.read_text(encoding="utf-8"), "hello\n")
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_rejects_absolute_runtime_state_tamper_without_touching_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            state_path_literal = json.dumps(str(store.state_path))
            self._configure_read_only_exec_command_plan(
                store,
                command_argv=[
                    "python",
                    "-c",
                    (
                        "import json; from pathlib import Path; "
                        f"state_path = Path({state_path_literal}); "
                        "data = json.loads(state_path.read_text(encoding='utf-8')); "
                        "data['checkpoint']['summary'] = 'abs-tampered by apply'; "
                        "state_path.write_text(json.dumps(data), encoding='utf-8'); "
                        "print('ok')"
                    ),
                ],
                goal="Unsafe exec command",
                summary="Absolute path runtime tamper must fail closed.",
            )

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertNotEqual(store.load_state()["checkpoint"]["summary"], "abs-tampered by apply")
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_exec_command_read_only_apply_rejects_absolute_artifact_tamper_without_touching_root(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            safe_stdout = store.artifacts_dir / "actions" / "act-safe" / "stdout.txt"
            safe_stdout.parent.mkdir(parents=True, exist_ok=True)
            safe_stdout.write_text("apply-ok\n", encoding="utf-8", newline="\n")
            artifact_path_literal = json.dumps(str(safe_stdout))
            self._configure_read_only_exec_command_plan(
                store,
                command_argv=[
                    "python",
                    "-c",
                    (
                        "from pathlib import Path; "
                        f"Path({artifact_path_literal}).write_text('forged artifact\\n', encoding='utf-8'); "
                        "print('ok')"
                    ),
                ],
                goal="Unsafe exec command",
                summary="Absolute path artifact tamper must fail closed.",
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("side_effect=read_only", output.getvalue())

            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(safe_stdout.read_text(encoding="utf-8"), "apply-ok\n")
            self.assertEqual(runtime["verification"]["status"], "passed")
            self.assertEqual(runtime["verification"]["pending_action_ids"], [])
            self.assertFalse((store.artifacts_dir / "actions" / "act-command").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_verification_success_records_decision_memory_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Learn from success.", verify_command=["python -c print('ok')"]))

            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-success",
                        "kind": "fs.create_file",
                        "summary": "create artifact",
                        "path": "artifact.txt",
                        "content": "alpha",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            state = store.load_state()
            workflow_notes = [note for note in state["agent_runtime"]["memory"]["notes"] if note["kind"] == "workflow"]
            self.assertEqual(len(workflow_notes), 1)
            self.assertIn("context:", workflow_notes[0]["summary"])
            self.assertIn("action:", workflow_notes[0]["summary"])
            self.assertIn("result:", workflow_notes[0]["summary"])
            self.assertIn("cost:", workflow_notes[0]["summary"])
            self.assertIn("reason:", workflow_notes[0]["summary"])
            self.assertTrue(workflow_notes[0]["source"].startswith("decision_success|task=task-001|"))
            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event": "decision_success"', events)
            self.assertIn('"task_id": "task-001"', events)

    def test_verification_failure_blocks_further_apply_until_resolved(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Failure gate.", verify_command=["python -c import sys; sys.exit(1)"]))

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(create_file), "task_id": "", "batch_id": ""})), 0)
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            second_file = root / "second.json"
            second_file.write_text(
                json.dumps(
                    {
                        "id": "act-second",
                        "kind": "fs.create_file",
                        "summary": "create second draft",
                        "path": "draft-2.txt",
                        "content": "beta\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_apply(root, type("Args", (), {"action_file": str(second_file), "task_id": "", "batch_id": ""}))
            self.assertEqual(exit_code, 1)
            self.assertIn("verification is failed; rerun verify successfully", stream.getvalue())
            state = store.load_state()
            self.assertEqual(len(state["agent_runtime"]["memory"]["notes"]), 1)
            self.assertEqual(state["agent_runtime"]["memory"]["notes"][0]["kind"], "pitfall")
            self.assertIn("cmd-001", state["agent_runtime"]["memory"]["notes"][0]["summary"])

    def test_verify_subset_keeps_pending_actions_until_full_required_coverage_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Subset verify",
                    "summary": "Partial verify must stay diagnostic only.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Create draft",
                            "status": "ready",
                            "details": "Create draft",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["all required verification commands pass"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('cmd1')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                        {
                            "id": "cmd-002",
                            "argv": [
                                "python",
                                "-c",
                                "import pathlib,sys; sys.exit(1 if pathlib.Path('draft.txt').exists() else 0)",
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                    ],
                    "required_command_ids": ["cmd-001", "cmd-002"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(create_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )

            subset_stream = io.StringIO()
            with redirect_stdout(subset_stream):
                subset_exit = run_verify(root, type("Args", (), {"command_id": ["cmd-001"]}))

            self.assertEqual(subset_exit, 1)
            subset_output = subset_stream.getvalue()
            self.assertIn("verification_partial", subset_output)
            self.assertIn("coverage: partial (1/2 required commands)", subset_output)
            self.assertIn("gate_status: idle", subset_output)
            self.assertIn("pending_actions: 1", subset_output)

            runtime_after_subset = store.read_agent_runtime()
            self.assertEqual(runtime_after_subset["verification"]["status"], "idle")
            self.assertEqual(runtime_after_subset["verification"]["pending_action_ids"], ["act-create"])
            self.assertEqual(
                [item["command_id"] for item in runtime_after_subset["verification"]["checks"]],
                ["cmd-001"],
            )
            self.assertEqual(runtime_after_subset["plan"]["tasks"][0]["status"], "running")

            full_stream = io.StringIO()
            with redirect_stdout(full_stream):
                full_exit = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(full_exit, 1)
            self.assertIn("verification_failed", full_stream.getvalue())
            self.assertNotIn("verification_blocked", full_stream.getvalue())

    def test_update_agent_verification_rejects_partial_subset_as_full_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            updated = store.update_agent_plan(
                {
                    "goal": "Direct verification update",
                    "summary": "Partial checks must not close the task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Create draft",
                            "status": "ready",
                            "details": "Create draft",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["all required verification commands pass"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('cmd1')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                        {
                            "id": "cmd-002",
                            "argv": ["python", "-c", "print('cmd2')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        },
                    ],
                    "required_command_ids": ["cmd-001", "cmd-002"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )
            updated = store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "create draft",
                    "target": "draft.txt",
                    "task_id": "task-001",
                    "batch_id": "",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {"fingerprint": "fp-act-001"},
                    "updated_at": "2026-04-14T00:00:10+00:00",
                },
                validated_revision=updated["revision"],
            )

            updated = store.update_agent_verification(
                {
                    "required_command_ids": ["cmd-001", "cmd-002"],
                    "pending_action_ids": ["act-001"],
                    "last_run_at": "2026-04-14T00:00:20+00:00",
                    "status": "passed",
                    "state_check": {
                        "status": "passed",
                        "exit_code": 0,
                        "message": "partial verify",
                    },
                    "checks": [
                        {
                            "id": "check-cmd-001",
                            "command_id": "cmd-001",
                            "status": "passed",
                            "exit_code": 0,
                            "artifact_ref": "",
                            "covered_action_ids": ["act-001"],
                            "message": "partial verify",
                        },
                    ],
                },
                validated_revision=updated["revision"],
            )

            verification = updated["agent_runtime"]["verification"]
            self.assertEqual(verification["status"], "idle")
            self.assertEqual(verification["pending_action_ids"], ["act-001"])
            self.assertEqual(updated["agent_runtime"]["plan"]["tasks"][0]["status"], "running")

    def test_failed_verification_remains_blocking_after_rollback_until_verify_passes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Failure retention",
                    "summary": "Failed verification must remain blocking.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Create draft",
                            "status": "ready",
                            "details": "Create draft",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [
                                "python",
                                "-c",
                                "import pathlib,sys; sys.exit(1 if pathlib.Path('draft.txt').exists() else 0)",
                            ],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            second_file = root / "second.json"
            second_file.write_text(
                json.dumps(
                    {
                        "id": "act-second",
                        "kind": "fs.create_file",
                        "summary": "create second draft",
                        "path": "draft-2.txt",
                        "content": "beta\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(create_file), "task_id": "", "batch_id": "batch-verify-fail", "retry_justification": ""})), 0)
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)
            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "", "batch_id": "batch-verify-fail"})), 0)

            blocked_stream = io.StringIO()
            with redirect_stdout(blocked_stream):
                blocked_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(second_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(blocked_exit, 1)
            self.assertIn("verification is failed; rerun verify successfully", blocked_stream.getvalue())

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(second_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )

    def test_rollback_invalidates_passed_verification_and_allows_rerun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback invalidates verify.", verify_command=["python -c print('ok')"]))

            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""})),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            verified_runtime = store.read_agent_runtime()["verification"]
            self.assertEqual(verified_runtime["status"], "passed")
            self.assertFalse(verified_runtime["pending_action_ids"])

            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""})), 0)

            invalidated_runtime = store.read_agent_runtime()["verification"]
            self.assertEqual(invalidated_runtime["status"], "idle")
            self.assertEqual(invalidated_runtime["checks"], [])
            self.assertEqual(invalidated_runtime["last_run_at"], "")
            self.assertFalse(invalidated_runtime["pending_action_ids"])

            verify_stream = io.StringIO()
            with redirect_stdout(verify_stream):
                rerun_exit = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(rerun_exit, 0)
            self.assertNotIn("verification_blocked", verify_stream.getvalue())

    def test_continuous_flow_from_bootstrap_validate_analyze_plan_apply_verify_to_rollback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            validate_stream = io.StringIO()
            with redirect_stdout(validate_stream):
                validate_exit = run_validate(root)
            validate_output = validate_stream.getvalue()
            self.assertEqual(validate_exit, 0)
            self.assertIn("validation_passed", validate_output)

            analyze_stream = io.StringIO()
            with redirect_stdout(analyze_stream):
                analyze_exit = run_analyze(root, type("Args", (), {"actor": "alice", "emit_session_token": True}))
            analyze_output = analyze_stream.getvalue()
            session_token = next(
                line.split(": ", 1)[1]
                for line in analyze_output.splitlines()
                if line.startswith("session_token: ")
            )
            self.assertEqual(analyze_exit, 0)
            self.assertIn("analysis_ready", analyze_output)
            self.assertIn("validation: ok", analyze_output)
            self.assertTrue(store.session_path.exists())

            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            with patch.dict(os.environ, {SESSION_TOKEN_ENV_VAR: session_token}, clear=False):
                plan_stream = io.StringIO()
                with redirect_stdout(plan_stream):
                    plan_exit = run_plan(
                        root,
                        self._plan_args(
                            summary="Continuous flow coverage.",
                            verify_command=["python -c print('ok')"],
                        ),
                    )
                plan_output = plan_stream.getvalue()
                self.assertEqual(plan_exit, 0)
                self.assertIn("plan_saved", plan_output)

                apply_stream = io.StringIO()
                with redirect_stdout(apply_stream):
                    apply_exit = run_apply(
                        root,
                        type(
                            "Args",
                            (),
                            {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""},
                        ),
                    )
                apply_output = apply_stream.getvalue()
                self.assertEqual(apply_exit, 0)
                self.assertIn("actions_applied: 1", apply_output)
                self.assertTrue((root / "draft.txt").exists())

                verify_stream = io.StringIO()
                with redirect_stdout(verify_stream):
                    verify_exit = run_verify(root, type("Args", (), {"command_id": []}))
                verify_output = verify_stream.getvalue()
                self.assertEqual(verify_exit, 0)
                self.assertIn("verification_passed", verify_output)

                rollback_stream = io.StringIO()
                with redirect_stdout(rollback_stream):
                    rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""}))
                rollback_output = rollback_stream.getvalue()
                self.assertEqual(rollback_exit, 0)
                self.assertIn("actions_rolled_back: 1", rollback_output)

            state = store.load_state()
            runtime = state["agent_runtime"]
            statuses = {item["id"]: item["status"] for item in runtime["actions"]}
            self.assertEqual(statuses["act-create"], "rolled_back")
            self.assertEqual(runtime["verification"]["status"], "idle")
            self.assertEqual(runtime["verification"]["checks"], [])
            self.assertEqual(runtime["verification"]["last_run_at"], "")
            self.assertFalse(runtime["verification"]["pending_action_ids"])
            self.assertFalse((root / "draft.txt").exists())
            self.assertEqual(tracked.read_text(encoding="utf-8"), "hello")

            final_validate_stream = io.StringIO()
            with redirect_stdout(final_validate_stream):
                final_validate_exit = run_validate(root)
            final_validate_output = final_validate_stream.getvalue()
            self.assertEqual(final_validate_exit, 0)
            self.assertIn("validation_passed", final_validate_output)
            self.assertTrue(store.validate_state()["ok"])

    def test_rollback_blocks_sensitive_action_without_approved_original_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("beta\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            self.assertEqual(
                run_plan(
                    root,
                    self._plan_args(
                        summary="Rollback approval gate.",
                        approval_required_kind=["fs.write_patch"],
                    ),
                ),
                0,
            )

            state = store.load_state()
            state["agent_runtime"]["actions"].append(
                {
                    "id": "act-patch",
                    "kind": "fs.write_patch",
                    "status": "applied",
                    "summary": "patch draft",
                    "target": "draft.txt",
                    "task_id": "task-001",
                    "batch_id": "",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {
                        "path": "draft.txt",
                        "post_sha256": hashlib.sha256(b"beta\n").hexdigest(),
                    },
                    "updated_at": "2026-04-16T00:00:00+00:00",
                }
            )
            store._write_json_atomic(store.state_path, state)

            stream = io.StringIO()
            with redirect_stdout(stream):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-patch", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("invalid_agent_action_status", output)
            self.assertIn("requires a non-empty approval_id under execution policy", output)
            self.assertEqual(draft.read_text(encoding="utf-8"), "beta\n")
            persisted = json.loads(store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(persisted["agent_runtime"]["actions"][0]["status"], "applied")

    def test_rollback_rejects_trimmed_action_even_when_audit_rollback_point_survives(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback history boundary."))

            overwrite_file = root / "overwrite.json"
            overwrite_file.write_text(
                json.dumps(
                    {
                        "id": "act-old",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft",
                        "path": "draft.txt",
                        "content": "after\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self._apply_with_approvals(root, store, str(overwrite_file))

            validation = store.validate_state()
            for index in range(1, MAX_ACTION_HISTORY + 1):
                store.record_agent_action(
                    {
                        "id": f"act-{index:03d}",
                        "kind": "fs.create_file",
                        "status": "blocked",
                        "summary": f"create filler {index:03d}",
                        "target": f"filler-{index:03d}.txt",
                        "task_id": "",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {
                            "created_new": True,
                            "path": f"filler-{index:03d}.txt",
                        },
                        "updated_at": f"2026-04-15T00:00:{index:02d}+00:00",
                    },
                    validated_revision=validation["revision"] + index - 1,
                )

            runtime = store.read_agent_runtime()
            self.assertNotIn("act-old", [action["id"] for action in runtime["actions"]])
            self.assertIn("act-old", [item["id"] for item in runtime["audit"]["rollback_points"]])

            stream = io.StringIO()
            with redirect_stdout(stream):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-old", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("requested action is no longer in retained canonical action history", output)
            self.assertIn("rollback_points are historical evidence only", output)
            self.assertEqual(draft.read_text(encoding="utf-8"), "after\n")

    def test_rollback_rejects_already_rolled_back_action_without_claiming_history_trim(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback idempotence boundary."))

            overwrite_file = root / "overwrite.json"
            overwrite_file.write_text(
                json.dumps(
                    {
                        "id": "act-old",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft",
                        "path": "draft.txt",
                        "content": "after\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self._apply_with_approvals(root, store, str(overwrite_file))
            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-old", "batch_id": ""})), 0)

            stream = io.StringIO()
            with redirect_stdout(stream):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-old", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("requested action is already rolled_back", output)
            self.assertNotIn("retained canonical action history", output)
            self.assertEqual(draft.read_text(encoding="utf-8"), "before\n")

    def test_rollback_batch_restores_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback batch."))
            batch_id = "batch-001"

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            patch_file = root / "patch.json"
            patch_file.write_text(
                json.dumps(
                    {
                        "id": "act-patch",
                        "kind": "fs.write_patch",
                        "summary": "patch draft",
                        "path": "draft.txt",
                        "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {"action_file": [str(create_file), str(patch_file)], "task_id": "", "batch_id": batch_id},
                    ),
                ),
                1,
            )
            self._approve_latest(root, store)
            self.assertEqual(
                run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {"action_file": [str(create_file), str(patch_file)], "task_id": "", "batch_id": batch_id},
                    ),
                ),
                0,
            )

            self.assertEqual((root / "draft.txt").read_text(encoding="utf-8"), "beta\n")
            rollback_exit = run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id}))
            self.assertEqual(rollback_exit, 0)
            self.assertFalse((root / "draft.txt").exists())
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-create"], "rolled_back")
            self.assertEqual(statuses["act-patch"], "rolled_back")

    def test_apply_rejects_batch_id_reuse_across_invocations_before_side_effects(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                self._plan_args(
                    summary="Reject batch reuse.",
                    approval_required_kind=["fs.write_patch"],
                ),
            )
            batch_id = "batch-reuse"

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(create_file), "task_id": "", "batch_id": batch_id})),
                0,
            )

            patch_file = root / "patch.json"
            patch_file.write_text(
                json.dumps(
                    {
                        "id": "act-patch",
                        "kind": "fs.write_patch",
                        "summary": "patch draft",
                        "path": "draft.txt",
                        "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(patch_file), "task_id": "", "batch_id": batch_id}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("batch_id is already bound to a previous apply invocation", output.getvalue())
            self.assertEqual((root / "draft.txt").read_text(encoding="utf-8"), "alpha\n")
            runtime = store.load_state()["agent_runtime"]
            self.assertEqual([item["id"] for item in runtime["actions"]], ["act-create"])
            self.assertEqual(runtime["approvals"]["items"], [])

    def test_apply_rejects_batch_id_reuse_even_after_original_batch_ages_out_of_action_history(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Reject aged-out batch reuse."))
            batch_id = "batch-reuse"

            first_file = root / "first.json"
            first_file.write_text(
                json.dumps(
                    {
                        "id": "act-old",
                        "kind": "fs.create_file",
                        "summary": "create old batch file",
                        "path": "old-batch.txt",
                        "content": "old\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(first_file), "task_id": "", "batch_id": batch_id})),
                0,
            )

            validation = store.validate_state()
            for index in range(1, MAX_ACTION_HISTORY + 1):
                store.record_agent_action(
                    {
                        "id": f"act-{index:03d}",
                        "kind": "fs.create_file",
                        "status": "blocked",
                        "summary": f"create filler {index:03d}",
                        "target": f"filler-{index:03d}.txt",
                        "task_id": "",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {
                            "created_new": True,
                            "path": f"filler-{index:03d}.txt",
                        },
                        "updated_at": f"2026-04-15T00:00:{index:02d}+00:00",
                    },
                    validated_revision=validation["revision"] + index - 1,
                )

            self.assertNotIn(batch_id, [item.get("batch_id") for item in store.read_agent_runtime()["actions"]])

            second_file = root / "second.json"
            second_file.write_text(
                json.dumps(
                    {
                        "id": "act-new",
                        "kind": "fs.create_file",
                        "summary": "create new batch file",
                        "path": "new-batch.txt",
                        "content": "new\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with redirect_stdout(output):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(second_file), "task_id": "", "batch_id": batch_id}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("batch_id is already bound to a previous apply invocation", output.getvalue())
            self.assertFalse((root / "new-batch.txt").exists())
            runtime = store.load_state()["agent_runtime"]
            self.assertEqual(runtime["batch_registry"]["used_ids"][-1], batch_id)

    def test_rollback_batch_reports_closed_history_when_batch_ages_out(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback aged-out batch."))
            batch_id = "batch-old"

            first_file = root / "first.json"
            first_file.write_text(
                json.dumps(
                    {
                        "id": "act-old",
                        "kind": "fs.create_file",
                        "summary": "create old batch file",
                        "path": "old-batch.txt",
                        "content": "old\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(first_file), "task_id": "", "batch_id": batch_id})),
                0,
            )

            validation = store.validate_state()
            for index in range(1, MAX_ACTION_HISTORY + 1):
                store.record_agent_action(
                    {
                        "id": f"act-{index:03d}",
                        "kind": "fs.create_file",
                        "status": "applied",
                        "summary": f"create filler {index:03d}",
                        "target": f"filler-{index:03d}.txt",
                        "task_id": "",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {
                            "created_new": True,
                            "path": f"filler-{index:03d}.txt",
                        },
                        "updated_at": f"2026-04-15T00:01:{index:02d}+00:00",
                    },
                    validated_revision=validation["revision"] + index - 1,
                )

            output = io.StringIO()
            with redirect_stdout(output):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id}))

            self.assertEqual(rollback_exit, 1)
            self.assertIn("requested batch_id is already closed in canonical batch history", output.getvalue())
            self.assertEqual((root / "old-batch.txt").read_text(encoding="utf-8"), "old\n")

    def test_multi_file_apply_batch_preflight_blocks_predictable_partial_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Batch apply preflight."))

            first_file = root / "first.json"
            first_file.write_text(
                json.dumps(
                    {
                        "id": "act-create-1",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            second_file = root / "second.json"
            second_file.write_text(
                json.dumps(
                    {
                        "id": "act-create-2",
                        "kind": "fs.create_file",
                        "summary": "duplicate create",
                        "path": "draft.txt",
                        "content": "beta\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {
                            "action_file": [str(first_file), str(second_file)],
                            "task_id": "",
                            "batch_id": "",
                            "retry_justification": "",
                        },
                    ),
                )

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("apply preflight failed before mutation", output)
            self.assertFalse((root / "draft.txt").exists())
            self.assertEqual(store.load_state()["agent_runtime"]["actions"], [])

    def test_multi_file_apply_batch_blocks_late_approval_without_partial_mutation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                self._plan_args(
                    summary="Batch apply approval.",
                    approval_required_kind=["fs.write_patch"],
                ),
            )

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            patch_file = root / "patch.json"
            patch_file.write_text(
                json.dumps(
                    {
                        "id": "act-patch",
                        "kind": "fs.write_patch",
                        "summary": "patch draft",
                        "path": "draft.txt",
                        "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )

            first_output = io.StringIO()
            with redirect_stdout(first_output):
                first_exit = run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {
                            "action_file": [str(create_file), str(patch_file)],
                            "task_id": "",
                            "batch_id": "",
                            "retry_justification": "",
                        },
                    ),
                )

            self.assertEqual(first_exit, 1)
            self.assertIn("approval_required", first_output.getvalue())
            self.assertFalse((root / "draft.txt").exists())
            self.assertEqual(store.load_state()["agent_runtime"]["actions"], [])
            approval_id = store.read_agent_runtime()["approvals"]["items"][-1]["id"]

            self.assertEqual(run_approve(root, type("Args", (), {"approval_id": approval_id, "decision": "approved"})), 0)

            second_output = io.StringIO()
            with redirect_stdout(second_output):
                second_exit = run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {
                            "action_file": [str(create_file), str(patch_file)],
                            "task_id": "",
                            "batch_id": "",
                            "retry_justification": "",
                        },
                    ),
                )

            self.assertEqual(second_exit, 0)
            self.assertIn("actions_applied: 2", second_output.getvalue())
            self.assertEqual((root / "draft.txt").read_text(encoding="utf-8"), "beta\n")
            statuses = {item["id"]: item["status"] for item in store.load_state()["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-create"], "applied")
            self.assertEqual(statuses["act-patch"], "applied")

    def test_multi_file_apply_batch_restores_pre_batch_workspace_after_persist_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Batch apply persist failure."))

            action_files: list[str] = []
            for action_id, filename, content in (
                ("act-a", "draft-a.txt", "alpha\n"),
                ("act-b", "draft-b.txt", "beta\n"),
            ):
                action_file = root / f"{action_id}.json"
                action_file.write_text(
                    json.dumps(
                        {
                            "id": action_id,
                            "kind": "fs.create_file",
                            "summary": f"create {filename}",
                            "path": filename,
                            "content": content,
                            "overwrite": False,
                        }
                    ),
                    encoding="utf-8",
                )
                action_files.append(str(action_file))

            def fail_batch_commit(self, action_records, validated_revision=None, **kwargs):
                raise StateStoreError("injected apply batch persist failure")

            stream = io.StringIO()
            with patch.object(StateStore, "record_agent_actions", new=fail_batch_commit):
                with redirect_stdout(stream):
                    exit_code = run_apply(
                        root,
                        type(
                            "Args",
                            (),
                            {
                                "action_file": action_files,
                                "task_id": "",
                                "batch_id": "",
                                "retry_justification": "",
                            },
                        ),
                    )

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("operation_failed: injected apply batch persist failure", output)
            self.assertFalse((root / "draft-a.txt").exists())
            self.assertFalse((root / "draft-b.txt").exists())
            self.assertEqual(store.load_state()["agent_runtime"]["actions"], [])

    def test_multi_file_apply_batch_continues_best_effort_restore_after_first_restore_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Batch apply compensation best effort."))

            action_files: list[str] = []
            for action_id, filename, content in (
                ("act-a", "draft-a.txt", "alpha\n"),
                ("act-b", "draft-b.txt", "beta\n"),
            ):
                action_file = root / f"{action_id}.json"
                action_file.write_text(
                    json.dumps(
                        {
                            "id": action_id,
                            "kind": "fs.create_file",
                            "summary": f"create {filename}",
                            "path": filename,
                            "content": content,
                            "overwrite": False,
                        }
                    ),
                    encoding="utf-8",
                )
                action_files.append(str(action_file))

            def fail_batch_commit(self, action_records, validated_revision=None, **kwargs):
                raise StateStoreError("injected apply batch persist failure")

            original_restore = action_runtime_module._restore_path_from_snapshot
            failed_path = {"name": ""}

            def flaky_restore(snapshot_path: Path, live_path: Path) -> None:
                if not failed_path["name"] and live_path.name.endswith(".txt"):
                    failed_path["name"] = live_path.name
                    raise OSError("forced first restore failure")
                original_restore(snapshot_path, live_path)

            stream = io.StringIO()
            with patch.object(StateStore, "record_agent_actions", new=fail_batch_commit):
                with patch("core.action_runtime._restore_path_from_snapshot", new=flaky_restore):
                    with redirect_stdout(stream):
                        exit_code = run_apply(
                            root,
                            type(
                                "Args",
                                (),
                                {
                                    "action_file": action_files,
                                    "task_id": "",
                                    "batch_id": "",
                                    "retry_justification": "",
                                },
                            ),
                        )

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("compensation restore failed after best-effort replay", output)
            self.assertIn("forced first restore failure", output)
            self.assertEqual(failed_path["name"], "draft-a.txt")
            self.assertTrue((root / "draft-a.txt").exists())
            self.assertFalse((root / "draft-b.txt").exists())
            self.assertEqual(store.load_state()["agent_runtime"]["actions"], [])

    def test_rollback_rejects_tampered_rollback_artifact(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback artifact integrity."))

            action_file = root / "overwrite.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-overwrite",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft",
                        "path": "draft.txt",
                        "content": "after\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self._apply_with_approvals(root, store, str(action_file))

            state = store.load_state()
            artifact_ref = state["agent_runtime"]["actions"][0]["rollback_ref"]
            (store.cerebro_dir / artifact_ref).write_text("forged-restore\n", encoding="utf-8")

            stream = io.StringIO()
            with redirect_stdout(stream):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-overwrite", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("rollback_blocked", output)
            self.assertIn("runtime_artifact_hash_mismatch", output)
            self.assertEqual(draft.read_text(encoding="utf-8"), "after\n")
            statuses = {item["id"]: item["status"] for item in store.load_state()["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-overwrite"], "applied")

    def test_rollback_batch_preflight_blocks_predictable_partial_reversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback preflight."))
            batch_id = "batch-partial"

            action_files: list[str] = []
            for action_id, filename, content in (
                ("act-a", "draft-a.txt", "ALPHA\n"),
                ("act-b", "draft-b.txt", "BETA\n"),
            ):
                (root / filename).write_text(content.lower(), encoding="utf-8")
                action_file = root / f"{action_id}.json"
                action_file.write_text(
                    json.dumps(
                        {
                            "id": action_id,
                            "kind": "fs.create_file",
                            "summary": f"overwrite {filename}",
                            "path": filename,
                            "content": content,
                            "overwrite": True,
                        }
                    ),
                    encoding="utf-8",
                )
                action_files.append(str(action_file))
            approvals = self._apply_with_approvals(root, store, action_files, batch_id=batch_id)
            self.assertEqual(len(approvals), 2)

            (root / "draft-a.txt").write_text("manually-diverged\n", encoding="utf-8")

            stream = io.StringIO()
            with redirect_stdout(stream):
                rollback_exit = run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("rollback preflight failed before mutation", output)
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-a"], "applied")
            self.assertEqual(statuses["act-b"], "applied")
            self.assertEqual((root / "draft-a.txt").read_text(encoding="utf-8"), "manually-diverged\n")
            self.assertEqual((root / "draft-b.txt").read_text(encoding="utf-8"), "BETA\n")

    def test_rollback_batch_restores_pre_batch_workspace_after_mid_execution_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback compensation."))
            batch_id = "batch-race"

            action_files: list[str] = []
            for action_id, filename, content in (
                ("act-a", "draft-a.txt", "ALPHA\n"),
                ("act-b", "draft-b.txt", "BETA\n"),
            ):
                action_file = root / f"{action_id}.json"
                action_file.write_text(
                    json.dumps(
                        {
                            "id": action_id,
                            "kind": "fs.create_file",
                            "summary": f"create {filename}",
                            "path": filename,
                            "content": content,
                            "overwrite": False,
                        }
                    ),
                    encoding="utf-8",
                )
                action_files.append(str(action_file))
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": action_files, "task_id": "", "batch_id": batch_id})),
                0,
            )

            original = run_rollback.__globals__["rollback_action"]
            call_count = {"value": 0}

            def inject_divergence(root_path, store_obj, agent_runtime, action_record, registered_paths):
                updated = original(root_path, store_obj, agent_runtime, action_record, registered_paths)
                call_count["value"] += 1
                if call_count["value"] == 1:
                    (root / "draft-a.txt").write_text("raced-change\n", encoding="utf-8")
                return updated

            stream = io.StringIO()
            with patch.dict(run_rollback.__globals__, {"rollback_action": inject_divergence}):
                with redirect_stdout(stream):
                    rollback_exit = run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("current file content diverged since apply: draft-a.txt", output)
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-a"], "applied")
            self.assertEqual(statuses["act-b"], "applied")
            self.assertEqual((root / "draft-a.txt").read_text(encoding="utf-8"), "ALPHA\n")
            self.assertEqual((root / "draft-b.txt").read_text(encoding="utf-8"), "BETA\n")

    def test_rollback_batch_continues_best_effort_restore_after_first_restore_failure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback compensation best effort."))
            batch_id = "batch-race"

            action_files: list[str] = []
            for action_id, filename, content in (
                ("act-a", "draft-a.txt", "ALPHA\n"),
                ("act-b", "draft-b.txt", "BETA\n"),
            ):
                action_file = root / f"{action_id}.json"
                action_file.write_text(
                    json.dumps(
                        {
                            "id": action_id,
                            "kind": "fs.create_file",
                            "summary": f"create {filename}",
                            "path": filename,
                            "content": content,
                            "overwrite": False,
                        }
                    ),
                    encoding="utf-8",
                )
                action_files.append(str(action_file))
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": action_files, "task_id": "", "batch_id": batch_id})),
                0,
            )

            original_rollback_action = run_rollback.__globals__["rollback_action"]
            rollback_call_count = {"value": 0}

            def inject_divergence(root_path, store_obj, agent_runtime, action_record, registered_paths):
                updated = original_rollback_action(root_path, store_obj, agent_runtime, action_record, registered_paths)
                rollback_call_count["value"] += 1
                if rollback_call_count["value"] == 1:
                    (root / "draft-a.txt").write_text("raced-change\n", encoding="utf-8")
                return updated

            original_restore = action_runtime_module._restore_path_from_snapshot
            failed_path = {"name": ""}

            def flaky_restore(snapshot_path: Path, live_path: Path) -> None:
                if not failed_path["name"] and live_path.name.endswith(".txt"):
                    failed_path["name"] = live_path.name
                    raise OSError("forced first restore failure")
                original_restore(snapshot_path, live_path)

            stream = io.StringIO()
            with patch.dict(run_rollback.__globals__, {"rollback_action": inject_divergence}):
                with patch("core.action_runtime._restore_path_from_snapshot", new=flaky_restore):
                    with redirect_stdout(stream):
                        rollback_exit = run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("compensation restore failed after best-effort replay", output)
            self.assertIn("forced first restore failure", output)
            self.assertEqual(failed_path["name"], "draft-b.txt")
            self.assertEqual((root / "draft-a.txt").read_text(encoding="utf-8"), "ALPHA\n")
            self.assertFalse((root / "draft-b.txt").exists())
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-a"], "applied")
            self.assertEqual(statuses["act-b"], "applied")

    def test_rollback_restores_workspace_when_persist_fails_after_physical_reversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback persist failure."))

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )

            def fail_batch_commit(self, action_records, validated_revision=None, **kwargs):
                raise StateStoreError("injected batch persist failure")

            stream = io.StringIO()
            with patch.object(StateStore, "record_agent_actions", new=fail_batch_commit):
                with redirect_stdout(stream):
                    rollback_exit = run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""}))

            output = stream.getvalue()
            self.assertEqual(rollback_exit, 1)
            self.assertIn("operation_failed: injected batch persist failure", output)
            self.assertTrue((root / "draft.txt").exists())
            self.assertEqual((root / "draft.txt").read_text(encoding="utf-8"), "alpha\n")
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-create"], "applied")

    def test_rollback_move_prunes_empty_destination_tree_created_by_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("alpha\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback move should clean empty destination dirs."))

            action_file = root / "move.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-move",
                        "kind": "fs.move",
                        "summary": "move draft into new tree",
                        "from": "draft.txt",
                        "to": "notes/archive/draft.txt",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            apply_stream = io.StringIO()
            with redirect_stdout(apply_stream):
                apply_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(apply_exit, 1)
            self.assertIn("approval_required", apply_stream.getvalue())
            self._approve_latest(root, store)
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )
            self.assertFalse(draft.exists())
            self.assertTrue((root / "notes" / "archive" / "draft.txt").exists())

            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-move", "batch_id": ""})), 0)

            self.assertTrue(draft.exists())
            self.assertEqual(draft.read_text(encoding="utf-8"), "alpha\n")
            self.assertFalse((root / "notes" / "archive" / "draft.txt").exists())
            self.assertFalse((root / "notes" / "archive").exists())
            self.assertFalse((root / "notes").exists())
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-move"], "rolled_back")

    def test_rollback_create_new_prunes_empty_destination_tree_created_by_apply(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            created = root / "notes" / "archive" / "draft.txt"
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Rollback create-new should clean empty destination dirs."))

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft inside new tree",
                        "path": "notes/archive/draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )
            self.assertTrue(created.exists())
            self.assertEqual(created.read_text(encoding="utf-8"), "alpha\n")

            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""})), 0)

            self.assertFalse(created.exists())
            self.assertFalse((root / "notes" / "archive").exists())
            self.assertFalse((root / "notes").exists())
            state = store.load_state()
            statuses = {item["id"]: item["status"] for item in state["agent_runtime"]["actions"]}
            self.assertEqual(statuses["act-create"], "rolled_back")

    def test_plan_apply_verify_and_dag_progression(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            updated = store.update_agent_plan(
                {
                    "goal": "DAG",
                    "summary": "Progress through dependencies.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Create draft",
                            "status": "ready",
                            "details": "Create draft",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Follow up",
                            "status": "ready",
                            "details": "Follow up",
                            "depends_on": ["task-001"],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-c", "print('ok')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "read_only",
                            "risk": "low",
                            "allow_in_verify": True,
                        }
                    ],
                    "required_command_ids": ["cmd-001"],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )
            self.assertEqual(updated["agent_runtime"]["plan"]["tasks"][1]["status"], "blocked")
            self.assertEqual(updated["agent_runtime"]["plan"]["current_task_id"], "task-001")

            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})), 0)
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            state = store.load_state()
            tasks = {item["id"]: item for item in state["agent_runtime"]["plan"]["tasks"]}
            self.assertEqual(tasks["task-001"]["status"], "done")
            self.assertEqual(tasks["task-002"]["status"], "ready")
            self.assertEqual(state["agent_runtime"]["plan"]["current_task_id"], "task-002")

    def test_plan_apply_and_verify_append_audit_events(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Audit trail.", verify_command=["python -c print('ok')"]))

            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-audit",
                        "kind": "fs.create_file",
                        "summary": "create artifact",
                        "path": "artifact.txt",
                        "content": "alpha",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})), 0)
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event": "plan_updated"', events)
            self.assertIn('"event": "task_selected"', events)
            self.assertIn('"event": "action_recorded"', events)
            self.assertIn('"event": "verification_completed"', events)

    def test_task_selected_event_carries_evidence_event_ids(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()

            updated = store.update_agent_plan(
                {
                    "goal": "Priority",
                    "summary": "Switch after verify.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Create draft",
                            "status": "ready",
                            "details": "Create draft",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Finalize file",
                            "status": "blocked",
                            "details": "Finalize file",
                            "depends_on": ["task-001"],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )
            updated = store.record_agent_action(
                {
                    "id": "act-001",
                    "kind": "fs.create_file",
                    "status": "applied",
                    "summary": "create draft",
                    "target": "draft.txt",
                    "task_id": "task-001",
                    "batch_id": "",
                    "approval_id": "",
                    "artifact_refs": [],
                    "rollback_ref": "",
                    "details": {"fingerprint": "fp-act-001"},
                    "updated_at": "2026-04-14T00:00:10+00:00",
                },
                validated_revision=updated["revision"],
            )
            store.update_agent_verification(
                {
                    "required_command_ids": [],
                    "pending_action_ids": [],
                    "last_run_at": "2026-04-14T00:00:20+00:00",
                    "status": "passed",
                    "state_check": {
                        "status": "passed",
                        "exit_code": 0,
                        "message": "state verified",
                    },
                    "checks": [],
                },
                validated_revision=updated["revision"],
            )

            events = [
                json.loads(line)
                for line in store.events_path.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
            plan_event_id = next(item["event_id"] for item in events if item["event"] == "plan_updated")
            verification_event_id = next(item["event_id"] for item in events if item["event"] == "verification_completed")
            selected_events = [
                item
                for item in events
                if item["event"] == "task_selected" and item.get("selected_task_id") == "task-002"
            ]

            self.assertEqual(len(selected_events), 1)
            selection_event = selected_events[0]
            self.assertEqual(selection_event["parent_event_id"], verification_event_id)
            self.assertIn(plan_event_id, selection_event["evidence_event_ids"])

    def test_plan_selection_prefers_lower_cost_lower_risk_ready_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()

            updated = store.update_agent_plan(
                {
                    "goal": "Priority",
                    "summary": "Prefer the better-scoped ready task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Underspecified task",
                            "status": "ready",
                            "details": "Underspecified task",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Scoped task",
                            "status": "ready",
                            "details": "Scoped task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            self.assertEqual(updated["agent_runtime"]["plan"]["current_task_id"], "task-002")
            assessments = {item["id"]: item for item in store.read_task_assessments()}
            self.assertGreater(assessments["task-002"]["priority"], assessments["task-001"]["priority"])

    def test_task_assessment_treats_simple_nontechnical_tasks_as_lightweight(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()

            updated = store.update_agent_plan(
                {
                    "goal": "Organizar rotina",
                    "summary": "Checklist simples.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Planejar treino",
                            "status": "ready",
                            "details": "Planejar treino",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Separar leituras",
                            "status": "ready",
                            "details": "Separar leituras",
                            "depends_on": [],
                            "working_set": [],
                            "acceptance_criteria": [],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A1",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            assessments = {item["id"]: item for item in store.read_task_assessments()}

            self.assertEqual(updated["agent_runtime"]["plan"]["current_task_id"], "task-001")
            self.assertEqual(assessments["task-001"]["workload_mode"], "light")
            self.assertEqual(assessments["task-001"]["work_unit_kind"], "state_only")
            self.assertNotIn("working set is undefined", assessments["task-001"]["evidence"])
            self.assertNotIn("acceptance criteria are missing", assessments["task-001"]["evidence"])

    def test_retry_without_new_evidence_is_blocked_and_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Retry discipline."))

            first_action = root / "create-first.json"
            first_action.write_text(
                json.dumps(
                    {
                        "id": "act-create-001",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(first_action), "task_id": "", "batch_id": "", "retry_justification": ""})),
                0,
            )

            alpha_sha = store.compute_sha256("draft.txt")
            patch_action = root / "patch-first.json"
            patch_action.write_text(
                json.dumps(
                    {
                        "id": "act-patch-001",
                        "kind": "fs.write_patch",
                        "summary": "patch draft",
                        "path": "draft.txt",
                        "expected_sha256": alpha_sha,
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(patch_action), "task_id": "", "batch_id": "", "retry_justification": ""})),
                1,
            )
            self._approve_latest(root, store)
            self.assertEqual(
                run_apply(root, type("Args", (), {"action_file": str(patch_action), "task_id": "", "batch_id": "", "retry_justification": ""})),
                0,
            )

            second_action = root / "patch-second.json"
            second_action.write_text(
                json.dumps(
                    {
                        "id": "act-patch-002",
                        "kind": "fs.write_patch",
                        "summary": "patch draft again",
                        "path": "draft.txt",
                        "expected_sha256": alpha_sha,
                        "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {
                            "action_file": str(second_action),
                            "task_id": "",
                            "batch_id": "",
                            "retry_justification": "trying again without evidence",
                        },
                    ),
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("retry blocked because the same action was already attempted without new evidence", stream.getvalue())
            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event": "retry_blocked"', events)

    def test_retry_after_new_evidence_requires_justification(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Retry justification."))

            alpha_action = root / "alpha.json"
            alpha_action.write_text(
                json.dumps(
                    {
                        "id": "act-alpha-001",
                        "kind": "fs.create_file",
                        "summary": "write alpha",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            beta_action = root / "beta.json"
            beta_action.write_text(
                json.dumps(
                    {
                        "id": "act-beta-001",
                        "kind": "fs.create_file",
                        "summary": "write beta",
                        "path": "draft.txt",
                        "content": "beta\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            alpha_retry_action = root / "alpha-retry.json"
            alpha_retry_action.write_text(
                json.dumps(
                    {
                        "id": "act-alpha-002",
                        "kind": "fs.create_file",
                        "summary": "restore alpha",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(self._run_apply(root, str(alpha_action)), 0)
            self._apply_with_approvals(root, store, str(beta_action))

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(alpha_retry_action), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("retry requires an explicit justification", stream.getvalue())

            self._apply_with_approvals(
                root,
                store,
                str(alpha_retry_action),
                retry_justification="restore known good content after target changed to beta",
            )
            self.assertEqual((root / "draft.txt").read_text(encoding="utf-8"), "alpha\n")

    def test_apply_requires_approval_for_destructive_create_file_but_not_benign_create(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("before\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Approval by effect.", approval_required_kind=["fs.write_patch"]))

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create fresh file",
                        "path": "fresh.txt",
                        "content": "fresh\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(self._run_apply(root, str(create_file)), 0)
            self.assertEqual((root / "fresh.txt").read_text(encoding="utf-8"), "fresh\n")
            self.assertEqual(store.read_agent_runtime()["approvals"]["items"], [])

            overwrite_file = root / "overwrite.json"
            overwrite_file.write_text(
                json.dumps(
                    {
                        "id": "act-overwrite",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft",
                        "path": "draft.txt",
                        "content": "after\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            blocked_stream = io.StringIO()
            with redirect_stdout(blocked_stream):
                blocked_exit = self._run_apply(root, str(overwrite_file))
            self.assertEqual(blocked_exit, 1)
            self.assertIn("approval_required", blocked_stream.getvalue())
            self.assertEqual(draft.read_text(encoding="utf-8"), "before\n")
            self.assertEqual(
                [item["id"] for item in store.read_agent_runtime()["actions"]],
                ["act-create"],
            )
            approval = store.read_agent_runtime()["approvals"]["items"][-1]
            self.assertEqual(approval["action_kind"], "fs.create_file")
            self.assertEqual(approval["target"], "draft.txt")

    def test_apply_batch_requires_approval_for_projected_destructive_create_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Batch approval by effect.", approval_required_kind=["fs.write_patch"]))

            create_file = root / "create.json"
            create_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )
            overwrite_file = root / "overwrite.json"
            overwrite_file.write_text(
                json.dumps(
                    {
                        "id": "act-overwrite",
                        "kind": "fs.create_file",
                        "summary": "overwrite draft",
                        "path": "draft.txt",
                        "content": "beta\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )

            blocked_stream = io.StringIO()
            with redirect_stdout(blocked_stream):
                blocked_exit = self._run_apply(
                    root,
                    [str(create_file), str(overwrite_file)],
                    batch_id="batch-approval",
                )
            self.assertEqual(blocked_exit, 1)
            self.assertIn("approval_required", blocked_stream.getvalue())
            self.assertFalse((root / "draft.txt").exists())
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(runtime["approvals"]["items"][-1]["target"], "draft.txt")

    def test_task_assessment_penalizes_real_cost_and_redundancy(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            updated = store.update_agent_plan(
                {
                    "goal": "Efficiency",
                    "summary": "Prefer the lower-cost task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Redundant task",
                            "status": "ready",
                            "details": "Redundant task",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["done"],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Clean task",
                            "status": "ready",
                            "details": "Clean task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["done"],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            current_revision = updated["revision"]
            timestamp = datetime.now(timezone.utc).isoformat(timespec="seconds")
            for action_id in ("act-red-001", "act-red-002"):
                updated = store.record_agent_action(
                    {
                        "id": action_id,
                        "kind": "fs.create_file",
                        "status": "rolled_back",
                        "summary": "redundant retry",
                        "target": "draft.txt",
                        "task_id": "task-001",
                        "batch_id": "",
                        "approval_id": "",
                        "artifact_refs": [],
                        "rollback_ref": "",
                        "details": {
                            "fingerprint": "same-fingerprint",
                            "evidence_token": f"evidence-{action_id}",
                        },
                        "updated_at": timestamp,
                    },
                    validated_revision=current_revision,
                )
                current_revision = updated["revision"]

            store.record_runtime_event(
                {
                    "event": "retry_blocked",
                    "phase": "apply",
                    "step": "retry_blocked",
                    "task_id": "task-001",
                    "fingerprint": "same-fingerprint",
                    "reason_code": "retry_blocked_no_new_evidence",
                    "reason": "retry blocked because the same action was already attempted without new evidence",
                }
            )

            assessments = {item["id"]: item for item in store.read_task_assessments()}
            self.assertGreater(assessments["task-001"]["real_cost"], assessments["task-002"]["real_cost"])
            self.assertLess(assessments["task-001"]["priority"], assessments["task-002"]["priority"])
            self.assertIn("task has 1 redundant action attempt(s)", assessments["task-001"]["evidence"])

    def test_task_assessment_rewards_verified_success_patterns(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Reinforce success",
                    "summary": "Prefer patterns that already worked.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Repeatable task",
                            "status": "ready",
                            "details": "Repeatable task",
                            "depends_on": [],
                            "working_set": ["artifact.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            before = store.read_task_assessments()

            state = store.load_state()
            state["agent_runtime"]["memory"]["notes"].append(
                {
                    "id": "workflow-success-task-x",
                    "kind": "workflow",
                    "summary": "context: single file change; action: none; result: done; cost: 10; reason: bounded working set",
                    "source": build_success_memory_source(
                        task_id="task-x",
                        working_set_bucket="single",
                        acceptance_defined=True,
                        action_kinds=[],
                        has_sensitive_actions=False,
                        cost=10,
                    ),
                    "ttl_days": 21,
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            store.save_state(state, expected_revision=state["revision"])

            after = store.read_task_assessments()
            self.assertGreater(after[0]["priority"], before[0]["priority"])
            self.assertIn("task matches 1 verified success pattern(s)", after[0]["evidence"])

    def test_pending_approval_blocks_only_related_task_and_redirects_selection(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Target approvals",
                    "summary": "Pending approvals should block only the related task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Approval-gated task",
                            "status": "ready",
                            "details": "Needs approval",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["approval resolved"],
                            "action_ids": [],
                        },
                        {
                            "id": "task-002",
                            "title": "Free task",
                            "status": "ready",
                            "details": "Can proceed now",
                            "depends_on": [],
                            "working_set": ["notes.txt"],
                            "acceptance_criteria": ["done"],
                            "action_ids": [],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )
            revision = store.load_state()["revision"]
            store.update_agent_approval(
                {
                    "id": "apr-001",
                    "status": "pending",
                    "fingerprint": "fp-001",
                    "action_kind": "fs.write_patch",
                    "task_id": "task-001",
                    "target": "draft.txt",
                    "reason": "approval required",
                    "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "resolved_at": "",
                },
                validated_revision=revision,
            )

            assessments = {item["id"]: item for item in store.read_task_assessments()}
            self.assertFalse(assessments["task-001"]["executable"])
            self.assertTrue(assessments["task-002"]["executable"])
            self.assertIn("task is waiting on a pending approval", assessments["task-001"]["evidence"])
            self.assertIn("task is blocked until approval is resolved", assessments["task-001"]["evidence"])
            self.assertIn("other runtime tasks are waiting on approval", assessments["task-002"]["evidence"])

            selection = choose_next_task(store.read_agent_runtime())
            self.assertEqual(selection["task_id"], "task-002")

    def test_approval_does_not_bleed_across_tasks_with_same_action_payload(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Scope approvals",
                    "summary": "Approval should stay scoped to the originating task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Task one",
                            "status": "ready",
                            "details": "Needs approval",
                            "depends_on": [],
                            "working_set": ["draft-a.txt"],
                            "acceptance_criteria": ["patched"],
                        },
                        {
                            "id": "task-002",
                            "title": "Task two",
                            "status": "ready",
                            "details": "Same payload, different task",
                            "depends_on": [],
                            "working_set": ["draft-b.txt"],
                            "acceptance_criteria": ["patched"],
                        },
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            payload = {
                "id": "act-patch",
                "kind": "fs.write_patch",
                "summary": "patch shared payload",
                "path": "draft.txt",
                "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
            }
            fingerprint = compute_action_fingerprint(payload)
            state = store.load_state()
            state["agent_runtime"]["approvals"]["items"].append(
                {
                    "id": "apr-001",
                    "status": "approved",
                    "fingerprint": fingerprint,
                    "action_kind": "fs.write_patch",
                    "task_id": "task-001",
                    "target": "draft.txt",
                    "reason": "approval required",
                    "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            store.save_state(state, expected_revision=state["revision"])

            draft = root / "draft.txt"
            draft.write_text("alpha\n", encoding="utf-8")
            action_file = root / "patch.json"
            action_file.write_text(json.dumps(payload), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    run_apply(
                        root,
                        type(
                            "Args",
                            (),
                            {
                                "action_file": str(action_file),
                                "batch_id": "",
                                "task_id": "task-002",
                                "retry_justification": "",
                            },
                        ),
                    ),
                    1,
                )

            self.assertIn("approval_required", output.getvalue())
            approvals = store.read_agent_runtime()["approvals"]["items"]
            matching = [item for item in approvals if item["fingerprint"] == fingerprint]
            self.assertEqual(2, len(matching))
            self.assertEqual({"task-001", "task-002"}, {item["task_id"] for item in matching})

    def test_approved_action_does_not_bleed_across_plan_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            self.assertEqual(
                run_plan(
                    root,
                    self._plan_args(
                        task=["Task A"],
                        verify_command=["python -c print('ok')"],
                        approval_required_kind=["exec.command"],
                    ),
                ),
                0,
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run registered command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            first_output = io.StringIO()
            with redirect_stdout(first_output):
                first_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(first_exit, 1)
            self.assertIn("approval_required", first_output.getvalue())
            self._approve_latest(root, store)

            self.assertEqual(
                run_plan(
                    root,
                    self._plan_args(
                        task=["Task B"],
                        verify_command=["python -c print('ok')"],
                        approval_required_kind=["exec.command"],
                    ),
                ),
                0,
            )
            self.assertEqual(store.read_agent_runtime()["approvals"]["items"], [])

            second_output = io.StringIO()
            with redirect_stdout(second_output):
                second_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(second_exit, 1)
            self.assertIn("approval_required", second_output.getvalue())
            self.assertEqual(store.read_agent_runtime()["actions"], [])
            self.assertEqual(store.read_agent_runtime()["approvals"]["items"][-1]["status"], "pending")

    def test_exec_command_requires_fresh_approval_when_registry_changes_without_replan(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Registry drift must invalidate approval",
                    "summary": "approval cannot be reused after command registry drift",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["approval is renewed after registry drift"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [sys.executable, "-c", "from pathlib import Path; Path('before.txt').write_text('before\\n', encoding='utf-8')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "workspace_write",
                            "risk": "medium",
                            "allow_in_verify": False,
                        }
                    ],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["exec.command"],
                },
                validated_revision=validation["revision"],
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run registered command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            first_output = io.StringIO()
            with redirect_stdout(first_output):
                first_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(first_exit, 1)
            self.assertIn("approval_required", first_output.getvalue())
            approved_id = self._approve_latest(root, store)

            state = store.load_state()
            state["agent_runtime"]["command_registry"]["commands"][0]["argv"] = [
                sys.executable,
                "-c",
                "from pathlib import Path; Path('after.txt').write_text('after\\n', encoding='utf-8')",
            ]
            store.save_state(state, expected_revision=state["revision"])

            second_output = io.StringIO()
            with redirect_stdout(second_output):
                second_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(second_exit, 1)
            self.assertIn("approval_required", second_output.getvalue())
            self.assertFalse((root / "before.txt").exists())
            self.assertFalse((root / "after.txt").exists())
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(runtime["approvals"]["items"][-1]["status"], "pending")
            self.assertEqual(runtime["approvals"]["items"][-2]["id"], approved_id)
            self.assertNotEqual(
                runtime["approvals"]["items"][-2]["fingerprint"],
                runtime["approvals"]["items"][-1]["fingerprint"],
            )

    def test_exec_command_missing_registry_entry_blocks_before_approval_reuse(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Missing command blocks before approval reuse",
                    "summary": "approval cannot be reused when command registry entry disappears",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Run command",
                            "status": "ready",
                            "details": "Run command",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["missing command fails before approval reuse"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": [sys.executable, "-c", "from pathlib import Path; Path('missing.txt').write_text('ran\\n', encoding='utf-8')"],
                            "cwd": ".",
                            "timeout_ms": 120000,
                            "determinism": "high",
                            "side_effect": "workspace_write",
                            "risk": "medium",
                            "allow_in_verify": False,
                        }
                    ],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["exec.command"],
                },
                validated_revision=validation["revision"],
            )

            action_file = root / "command.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-command",
                        "kind": "exec.command",
                        "summary": "run registered command",
                        "command_id": "cmd-001",
                    }
                ),
                encoding="utf-8",
            )

            first_output = io.StringIO()
            with redirect_stdout(first_output):
                first_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(first_exit, 1)
            self.assertIn("approval_required", first_output.getvalue())
            approved_id = self._approve_latest(root, store)

            state = store.load_state()
            state["agent_runtime"]["command_registry"]["commands"] = []
            store.save_state(state, expected_revision=state["revision"])

            second_output = io.StringIO()
            with redirect_stdout(second_output):
                second_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(second_exit, 1)
            self.assertIn("unknown command_id: cmd-001", second_output.getvalue())
            self.assertNotIn("approval_required", second_output.getvalue())
            self.assertFalse((root / "missing.txt").exists())
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"], [])
            self.assertEqual(len(runtime["approvals"]["items"]), 1)
            self.assertEqual(runtime["approvals"]["items"][0]["id"], approved_id)

    def test_plan_swap_keeps_historical_applied_action_without_requiring_current_task_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )

            swap_output = io.StringIO()
            with redirect_stdout(swap_output):
                swap_exit = run_plan(root, self._plan_args(task=["Task B"]))

            self.assertEqual(swap_exit, 0, swap_output.getvalue())
            validation = store.validate_state()
            self.assertTrue(validation["ok"], validation["errors"])
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["plan"]["tasks"][0]["action_ids"], [])
            self.assertEqual(runtime["actions"][0]["id"], "act-create")
            self.assertEqual(runtime["actions"][0]["status"], "applied")

    def test_plan_swap_keeps_historical_rolled_back_action_without_requiring_current_task_link(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )
            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""})), 0)

            swap_output = io.StringIO()
            with redirect_stdout(swap_output):
                swap_exit = run_plan(root, self._plan_args(task=["Task B"]))

            self.assertEqual(swap_exit, 0, swap_output.getvalue())
            validation = store.validate_state()
            self.assertTrue(validation["ok"], validation["errors"])
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["plan"]["tasks"][0]["action_ids"], [])
            self.assertEqual(runtime["actions"][0]["id"], "act-create")
            self.assertEqual(runtime["actions"][0]["status"], "rolled_back")

    def test_batch_id_reuse_after_plan_swap_targets_only_current_plan_batch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            batch_id = "batch-swap"

            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            old_action = root / "old.json"
            old_action.write_text(
                json.dumps(
                    {
                        "id": "act-old",
                        "kind": "fs.create_file",
                        "summary": "create old draft",
                        "path": "old.txt",
                        "content": "old\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(old_action), "task_id": "", "batch_id": batch_id, "retry_justification": ""}),
                ),
                0,
            )
            self.assertEqual(run_plan(root, self._plan_args(task=["Task B"])), 0)

            new_action = root / "new.json"
            new_action.write_text(
                json.dumps(
                    {
                        "id": "act-new",
                        "kind": "fs.create_file",
                        "summary": "create new draft",
                        "path": "new.txt",
                        "content": "new\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(new_action), "task_id": "", "batch_id": batch_id, "retry_justification": ""}),
                ),
                0,
            )
            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "", "batch_id": batch_id})), 0)

            runtime = store.read_agent_runtime()
            statuses = {action["id"]: action["status"] for action in runtime["actions"]}
            self.assertEqual(statuses["act-old"], "applied")
            self.assertEqual(statuses["act-new"], "rolled_back")
            self.assertTrue((root / "old.txt").exists())
            self.assertFalse((root / "new.txt").exists())

    def test_rollback_action_id_still_allows_historical_action_after_plan_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )
            self.assertEqual(run_plan(root, self._plan_args(task=["Task B"])), 0)
            self.assertEqual(run_rollback(root, type("Args", (), {"action_id": "act-create", "batch_id": ""})), 0)
            self.assertFalse((root / "draft.txt").exists())
            self.assertTrue(store.validate_state()["ok"])

    def test_legacy_approval_without_task_id_only_reuses_single_executable_task(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Reuse scoped approvals safely",
                    "summary": "Legacy approvals without task scope should only apply to a single executable task.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Only task",
                            "status": "ready",
                            "details": "Single executable task",
                            "depends_on": [],
                            "working_set": ["draft.txt"],
                            "acceptance_criteria": ["patched"],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            payload = {
                "id": "act-patch",
                "kind": "fs.write_patch",
                "summary": "patch legacy approval",
                "path": "draft.txt",
                "expected_sha256": hashlib.sha256(b"alpha\n").hexdigest(),
                "replacements": [{"old": "alpha", "new": "beta", "count": 1}],
            }
            fingerprint = compute_action_fingerprint(payload)
            state = store.load_state()
            state["agent_runtime"]["approvals"]["items"].append(
                {
                    "id": "apr-legacy-001",
                    "status": "approved",
                    "fingerprint": fingerprint,
                    "action_kind": "fs.write_patch",
                    "task_id": "",
                    "target": "draft.txt",
                    "reason": "legacy approval",
                    "requested_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                    "resolved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            store.save_state(state, expected_revision=state["revision"])

            draft = root / "draft.txt"
            draft.write_text("alpha\n", encoding="utf-8")
            action_file = root / "patch.json"
            action_file.write_text(json.dumps(payload), encoding="utf-8")

            output = io.StringIO()
            with redirect_stdout(output):
                self.assertEqual(
                    run_apply(
                        root,
                        type(
                            "Args",
                            (),
                            {
                                "action_file": str(action_file),
                                "batch_id": "",
                                "task_id": "task-001",
                                "retry_justification": "",
                            },
                        ),
                    ),
                    0,
                )

            self.assertIn("actions_applied: 1", output.getvalue())
            self.assertEqual("beta\n", draft.read_text(encoding="utf-8"))

    def test_blocked_apply_event_does_not_bleed_across_plan_swap(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("same\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "blocked.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-blocked",
                        "kind": "fs.write_patch",
                        "summary": "no-op patch",
                        "path": "draft.txt",
                        "expected_sha256": hashlib.sha256(b"same\n").hexdigest(),
                        "replacements": [{"old": "same", "new": "same", "count": 1}],
                    }
                ),
                encoding="utf-8",
            )
            blocked_output = io.StringIO()
            with redirect_stdout(blocked_output):
                blocked_exit = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(blocked_exit, 1)
            self.assertIn("apply blocked because the action would not change the effective workspace state", blocked_output.getvalue())

            self.assertEqual(run_plan(root, self._plan_args(task=["Task B"])), 0)
            assessments = {item["id"]: item for item in store.read_task_assessments()}

            self.assertNotIn("task has 1 blocked apply attempt(s)", assessments["task-001"]["evidence"])
            self.assertNotIn("apply_blocked=1", assessments["task-001"]["recent_history"])
            self.assertEqual(assessments["task-001"]["priority"], 65)

    def test_success_pattern_confidence_drops_after_blocked_retry(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Revalidate learning",
                    "summary": "Reduce reinforcement after blocked retries.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Repeatable task",
                            "status": "ready",
                            "details": "Repeatable task",
                            "depends_on": [],
                            "working_set": ["artifact.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            state = store.load_state()
            state["agent_runtime"]["memory"]["notes"].append(
                {
                    "id": "workflow-success-task-y",
                    "kind": "workflow",
                    "summary": "context: single file change; action: none; result: done; cost: 10; reason: bounded working set",
                    "source": build_success_memory_source(
                        task_id="task-y",
                        working_set_bucket="single",
                        acceptance_defined=True,
                        action_kinds=[],
                        has_sensitive_actions=False,
                        cost=10,
                    ),
                    "ttl_days": 21,
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            store.save_state(state, expected_revision=state["revision"])
            reinforced = store.read_task_assessments()

            store.record_runtime_event(
                {
                    "event": "retry_blocked",
                    "phase": "apply",
                    "step": "retry_blocked",
                    "task_id": "task-001",
                    "reason_code": "retry_blocked_no_new_evidence",
                    "reason": "retry blocked because the same action was already attempted without new evidence",
                }
            )
            challenged = store.read_task_assessments()

            self.assertLess(challenged[0]["priority"], reinforced[0]["priority"])
            self.assertIn(
                "recent blocked or failed attempts reduced confidence in the learned success pattern",
                challenged[0]["evidence"],
            )

    def test_malformed_success_memory_note_is_ignored_by_task_assessment(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            validation = store.validate_state()
            store.update_agent_plan(
                {
                    "goal": "Ignore malformed success memory",
                    "summary": "Bad workflow notes must not reinforce score.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Repeatable task",
                            "status": "ready",
                            "details": "Repeatable task",
                            "depends_on": [],
                            "working_set": ["artifact.txt"],
                            "acceptance_criteria": ["verify succeeds"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [],
                    "required_command_ids": [],
                    "autonomy_level": "A2",
                    "protected_paths": [".cerebro/**", ".git/**"],
                    "blocked_command_prefixes": ["rm"],
                    "approval_required_kinds": ["fs.write_patch"],
                },
                validated_revision=validation["revision"],
            )

            before = store.read_task_assessments()
            state = store.load_state()
            state["agent_runtime"]["memory"]["notes"].append(
                {
                    "id": "workflow-success-bad",
                    "kind": "workflow",
                    "summary": "Malformed workflow memory",
                    "source": "decision_success|task=task-z|ws=single|acceptance=1|actions=none|sensitive=0|cost=not-a-number",
                    "ttl_days": 21,
                    "updated_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                }
            )
            store.save_state(state, expected_revision=state["revision"])

            after = store.read_task_assessments()
            self.assertEqual(after[0]["priority"], before[0]["priority"])
            self.assertNotIn("task matches 1 verified success pattern(s)", after[0]["evidence"])

    def test_apply_blocks_no_effect_create_file_before_retry_loop(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="No-op apply should be rejected."))

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )
            self.assertEqual(
                run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                ),
                0,
            )

            no_effect_stream = io.StringIO()
            with redirect_stdout(no_effect_stream):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )
            self.assertEqual(exit_code, 1)
            self.assertIn("action would not change the effective workspace state", no_effect_stream.getvalue())
            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event": "apply_blocked"', events)

    def test_apply_blocks_same_path_move_before_mutation_and_action_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            draft = root / "draft.txt"
            draft.write_text("alpha\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Same-path move should fail closed."))

            action_file = root / "move.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-move",
                        "kind": "fs.move",
                        "summary": "move draft onto itself",
                        "from": "draft.txt",
                        "to": "./draft.txt",
                        "overwrite": True,
                    }
                ),
                encoding="utf-8",
            )

            no_effect_stream = io.StringIO()
            with redirect_stdout(no_effect_stream):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("action would not change the effective workspace state", no_effect_stream.getvalue())
            self.assertTrue(draft.exists())
            self.assertEqual(draft.read_text(encoding="utf-8"), "alpha\n")
            self.assertEqual(store.read_agent_runtime()["actions"], [])
            events = store.events_path.read_text(encoding="utf-8")
            self.assertIn('"event": "apply_blocked"', events)

    def test_apply_does_not_depend_on_recent_event_reads(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create artifact",
                        "path": "artifact.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            with patch.object(
                StateStore,
                "read_recent_events",
                side_effect=StateStoreError("unexpected trace read failure"),
            ):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 0)
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"][-1]["id"], "act-create")

    def test_apply_single_file_revalidates_state_before_mutating_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            self.assertEqual(run_plan(root, self._plan_args(task=["Task A"])), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create artifact",
                        "path": "artifact.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            original_load_state = StateStore.load_state
            load_state_calls = 0
            pre_mutation_load_state_calls: list[int] = []

            def counting_load_state(self):
                nonlocal load_state_calls
                load_state_calls += 1
                return original_load_state(self)

            from core import action_runtime as action_runtime_module

            original_apply_action = action_runtime_module.apply_action

            def counting_apply_action(*apply_args, **apply_kwargs):
                pre_mutation_load_state_calls.append(load_state_calls)
                return original_apply_action(*apply_args, **apply_kwargs)

            with (
                patch.object(StateStore, "load_state", counting_load_state),
                patch.object(action_runtime_module, "apply_action", side_effect=counting_apply_action),
            ):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 0)
            self.assertEqual(len(pre_mutation_load_state_calls), 1)
            self.assertGreaterEqual(pre_mutation_load_state_calls[0], 1)
            self.assertGreater(load_state_calls, pre_mutation_load_state_calls[0])
            runtime = store.read_agent_runtime()
            self.assertEqual(runtime["actions"][-1]["id"], "act-create")

    def test_single_file_apply_rolls_back_workspace_when_late_record_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            self.assertEqual(run_plan(root, self._plan_args(summary="Late record rejection.")), 0)

            action_file = root / "create.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
                        "kind": "fs.create_file",
                        "summary": "create draft",
                        "path": "draft.txt",
                        "content": "alpha\n",
                        "overwrite": False,
                    }
                ),
                encoding="utf-8",
            )

            output = io.StringIO()
            with (
                redirect_stdout(output),
                patch.object(StateStore, "record_agent_action", side_effect=StateStoreError("state changed after validation")),
            ):
                exit_code = run_apply(
                    root,
                    type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": "", "retry_justification": ""}),
                )

            self.assertEqual(exit_code, 1)
            self.assertIn("operation_failed", output.getvalue())
            self.assertFalse((root / "draft.txt").exists())
            runtime = store.read_agent_runtime()
            self.assertFalse(any(action["id"] == "act-create" for action in runtime["actions"]))

    def test_verify_allows_rerun_after_workspace_drift_outside_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Verify once.", verify_command=["python -c print('ok')"]))

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)
            (root / "scratch.txt").write_text("drift outside runtime", encoding="utf-8")

            rerun_stream = io.StringIO()
            with redirect_stdout(rerun_stream):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))
            self.assertEqual(exit_code, 0)
            self.assertNotIn("verification_blocked", rerun_stream.getvalue())
            events = store.events_path.read_text(encoding="utf-8")
            self.assertNotIn('"event": "verify_blocked"', events)

    def test_verify_allows_explicit_subset_rerun_after_workspace_drift_outside_runtime(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Verify subset once.", verify_command=["python -c print('ok')"]))

            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)
            (root / "scratch.txt").write_text("drift outside runtime", encoding="utf-8")

            rerun_stream = io.StringIO()
            with redirect_stdout(rerun_stream):
                exit_code = run_verify(root, type("Args", (), {"command_id": ["cmd-001"]}))
            self.assertEqual(exit_code, 0)
            self.assertNotIn("verification_blocked", rerun_stream.getvalue())
            events = store.events_path.read_text(encoding="utf-8")
            self.assertNotIn('"event": "verify_blocked"', events)

    def test_verify_uses_one_canonical_runtime_reload_before_command_execution(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(root, self._plan_args(summary="Verify load count.", verify_command=["python -c print('ok')"]))

            original_load_state = StateStore.load_state
            load_state_calls = 0
            pre_command_load_state_calls: list[int] = []

            from core import verification_runtime as verification_runtime_module

            original_run_verification_commands = verification_runtime_module.run_verification_commands

            def counting_load_state(self):
                nonlocal load_state_calls
                load_state_calls += 1
                return original_load_state(self)

            def counting_run_verification_commands(*verify_args, **verify_kwargs):
                pre_command_load_state_calls.append(load_state_calls)
                return original_run_verification_commands(*verify_args, **verify_kwargs)

            with (
                patch.object(StateStore, "load_state", counting_load_state),
                patch.object(
                    verification_runtime_module,
                    "run_verification_commands",
                    side_effect=counting_run_verification_commands,
                ),
            ):
                exit_code = run_verify(root, type("Args", (), {"command_id": []}))

            self.assertEqual(exit_code, 0)
            self.assertEqual(pre_command_load_state_calls, [1])


if __name__ == "__main__":
    unittest.main()
