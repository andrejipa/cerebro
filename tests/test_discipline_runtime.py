from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from core.digests import sha256_text
from core.discipline_runtime import (
    _resolve_workspace_path,
    _target_matches_last_outcome,
    build_action_evidence_token,
)


def _build_agent_runtime(
    *,
    verification: dict | None = None,
    commands: list[dict] | None = None,
) -> dict:
    return {
        "verification": {
            "status": "idle",
            "pending_action_ids": [],
            "last_run_at": "",
            **(verification or {}),
        },
        "command_registry": {"commands": list(commands or [])},
    }


class DisciplineRuntimeTests(unittest.TestCase):
    def test_resolve_workspace_path_rejects_absolute_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaisesRegex(ValueError, "path must be relative"):
                _resolve_workspace_path(root, str((root / "draft.txt").resolve()))

    def test_resolve_workspace_path_rejects_parent_directory_segments(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaisesRegex(ValueError, "path cannot contain '\\.\\.'"):
                _resolve_workspace_path(root, "../draft.txt")

    def test_resolve_workspace_path_rejects_resolved_paths_outside_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            candidate = root / "draft.txt"
            escaped = root.parent / "escaped.txt"
            original_resolve = Path.resolve

            def fake_resolve(path_self: Path, *args, **kwargs) -> Path:
                if path_self == root:
                    return root
                if path_self == candidate:
                    return escaped
                return original_resolve(path_self, *args, **kwargs)

            with patch.object(Path, "resolve", autospec=True, side_effect=fake_resolve):
                with self.assertRaisesRegex(ValueError, "path resolves outside workspace"):
                    _resolve_workspace_path(root, "draft.txt")

    def test_target_matches_last_outcome_recognizes_file_mutation_kinds(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            create_target = root / "draft-create.txt"
            create_target.write_bytes(b"alpha\n")
            create_match = _target_matches_last_outcome(
                root,
                {"kind": "fs.create_file", "path": "draft-create.txt"},
                [{"details": {"post_sha256": sha256_text("alpha\n")}}],
            )

            patch_target = root / "draft-patch.txt"
            patch_target.write_bytes(b"patched\n")
            patch_match = _target_matches_last_outcome(
                root,
                {"kind": "fs.write_patch", "path": "draft-patch.txt"},
                [{"details": {"post_sha256": sha256_text("patched\n")}}],
            )

            move_target = root / "moved.txt"
            move_target.write_bytes(b"moved\n")
            move_match = _target_matches_last_outcome(
                root,
                {"kind": "fs.move", "from": "draft.txt", "to": "moved.txt"},
                [{"details": {"post_sha256": sha256_text("moved\n")}}],
            )

            delete_match = _target_matches_last_outcome(
                root,
                {"kind": "fs.delete_soft", "path": "deleted.txt"},
                [{"details": {}}],
            )

            self.assertTrue(create_match)
            self.assertTrue(patch_match)
            self.assertTrue(move_match)
            self.assertTrue(delete_match)

    def test_target_matches_last_outcome_rejects_empty_action_history_and_invalid_details(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "draft.txt").write_text("alpha\n", encoding="utf-8")
            normalized_action = {"kind": "fs.create_file", "path": "draft.txt"}

            self.assertFalse(_target_matches_last_outcome(root, normalized_action, []))
            self.assertFalse(
                _target_matches_last_outcome(root, normalized_action, [{"details": "invalid"}])
            )

    def test_build_action_evidence_token_for_exec_command_changes_with_last_run_at(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            normalized_action = {"kind": "exec.command", "command_id": "cmd-001"}
            commands = [
                {
                    "id": "cmd-001",
                    "argv": ["python", "-m", "pytest"],
                    "cwd": ".",
                    "timeout_ms": 1000,
                    "determinism": "high",
                    "side_effect": "read_only",
                    "risk": "low",
                    "allow_in_verify": True,
                }
            ]

            token_alpha = build_action_evidence_token(
                root,
                normalized_action,
                _build_agent_runtime(
                    verification={"status": "passed", "last_run_at": "2026-04-23T00:00:00+00:00"},
                    commands=commands,
                ),
                "task-001",
            )
            token_beta = build_action_evidence_token(
                root,
                normalized_action,
                _build_agent_runtime(
                    verification={"status": "passed", "last_run_at": "2026-04-23T01:00:00+00:00"},
                    commands=commands,
                ),
                "task-001",
            )

            self.assertNotEqual(token_alpha, token_beta)

    def test_build_action_evidence_token_for_exec_command_reflects_command_registry_snapshot(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            normalized_action = {"kind": "exec.command", "command_id": "cmd-001"}
            shared_verification = {"status": "passed", "last_run_at": "2026-04-23T00:00:00+00:00"}
            alpha_commands = [
                {
                    "id": "cmd-001",
                    "argv": ["python", "-c", "print('alpha')"],
                    "cwd": ".",
                    "timeout_ms": 1000,
                    "determinism": "high",
                    "side_effect": "read_only",
                    "risk": "low",
                    "allow_in_verify": True,
                }
            ]
            beta_commands = [
                {
                    "id": "cmd-001",
                    "argv": ["python", "-c", "print('beta')"],
                    "cwd": ".",
                    "timeout_ms": 1000,
                    "determinism": "high",
                    "side_effect": "read_only",
                    "risk": "low",
                    "allow_in_verify": True,
                }
            ]

            token_alpha = build_action_evidence_token(
                root,
                normalized_action,
                _build_agent_runtime(verification=shared_verification, commands=alpha_commands),
                "task-001",
            )
            token_beta = build_action_evidence_token(
                root,
                normalized_action,
                _build_agent_runtime(verification=shared_verification, commands=beta_commands),
                "task-001",
            )

            self.assertNotEqual(token_alpha, token_beta)


if __name__ == "__main__":
    unittest.main()
