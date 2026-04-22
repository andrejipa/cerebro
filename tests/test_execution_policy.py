from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from core.execution_policy import (
    ExecutionPolicyError,
    action_requires_approval,
    ensure_command_allowed,
    ensure_mutation_path_allowed,
    required_action_approval_error,
)


class ExecutionPolicyTests(unittest.TestCase):
    def test_ensure_mutation_path_allowed_rejects_outside_protected_and_registered_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            protected = root / ".cerebro" / "state.json"
            tracked = root / "tracked.txt"
            protected.parent.mkdir(parents=True, exist_ok=True)
            protected.write_text("{}", encoding="utf-8")
            tracked.write_text("tracked\n", encoding="utf-8")

            self.assertEqual(
                ensure_mutation_path_allowed(root, root / "notes" / "draft.txt", [".cerebro/**"], {"tracked.txt"}),
                "notes/draft.txt",
            )

            with self.assertRaises(ExecutionPolicyError) as outside_ctx:
                ensure_mutation_path_allowed(root, root / ".." / "escape.txt", [".cerebro/**"], {"tracked.txt"})
            self.assertIn("path resolves outside root", str(outside_ctx.exception))

            with self.assertRaises(ExecutionPolicyError) as protected_ctx:
                ensure_mutation_path_allowed(root, protected, [".cerebro/**"], {"tracked.txt"})
            self.assertIn("path is protected by execution policy", str(protected_ctx.exception))

            with self.assertRaises(ExecutionPolicyError) as registered_ctx:
                ensure_mutation_path_allowed(root, tracked, [".cerebro/**"], {"tracked.txt"})
            self.assertIn("path is reserved as a registered context source", str(registered_ctx.exception))

    def test_ensure_command_allowed_enforces_autonomy_argv_and_blocklist(self) -> None:
        with self.assertRaises(ExecutionPolicyError) as autonomy_ctx:
            ensure_command_allowed("A1", ["python", "-V"], ["rm"])
        self.assertIn("autonomy level A1 does not allow command execution", str(autonomy_ctx.exception))

        with self.assertRaises(ExecutionPolicyError) as empty_ctx:
            ensure_command_allowed("A2", [], ["rm"])
        self.assertIn("command argv must be non-empty", str(empty_ctx.exception))

        with self.assertRaises(ExecutionPolicyError) as blank_ctx:
            ensure_command_allowed("A2", ["   "], ["rm"])
        self.assertIn("command argv[0] must be a non-empty string", str(blank_ctx.exception))

        with self.assertRaises(ExecutionPolicyError) as blocked_ctx:
            ensure_command_allowed("A2", ["PoWeRsHeLl", "-c", "echo ok"], ["powershell"])
        self.assertIn("command prefix is blocked by execution policy: powershell", str(blocked_ctx.exception))

        ensure_command_allowed("A2", ["python", "-V"], ["powershell"])

    def test_action_requires_approval_ignores_invalid_entries_and_required_action_approval_error_is_explicit(self) -> None:
        approval_required_kinds = ["fs.write_patch", "", None, "fs.move"]  # type: ignore[list-item]

        self.assertTrue(action_requires_approval("fs.write_patch", approval_required_kinds))
        self.assertFalse(
            action_requires_approval(
                {"kind": "fs.create_file", "overwrite": True},
                approval_required_kinds,
                target_exists=False,
            )
        )
        self.assertTrue(
            action_requires_approval(
                {"kind": "fs.create_file", "overwrite": True},
                approval_required_kinds,
                target_exists=True,
            )
        )
        self.assertTrue(
            action_requires_approval(
                {"kind": "fs.create_file", "details": {"created_new": False}},
                approval_required_kinds,
            )
        )

        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.create_file", "details": {"created_new": True}},
                "",
                {},
                approval_required_kinds,
            ),
            "",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.write_patch"},
                "",
                {},
                approval_required_kinds,
            ),
            "kind fs.write_patch requires a non-empty approval_id under execution policy",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.write_patch"},
                "apr-001",
                {"apr-001": "pending"},
                approval_required_kinds,
            ),
            "kind fs.write_patch requires approval apr-001 to be approved, got pending",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.write_patch"},
                "apr-missing",
                {},
                approval_required_kinds,
            ),
            "kind fs.write_patch requires approval apr-missing to exist and be approved",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.write_patch"},
                "apr-002",
                {"apr-002": "approved"},
                approval_required_kinds,
            ),
            "",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.create_file", "details": {"created_new": False}},
                "",
                {},
                approval_required_kinds,
            ),
            "kind fs.create_file requires a non-empty approval_id under execution policy",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.create_file", "overwrite": True},
                "",
                {},
                approval_required_kinds,
                target_exists=False,
            ),
            "",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.create_file", "overwrite": True},
                "",
                {},
                approval_required_kinds,
                target_exists=True,
            ),
            "kind fs.create_file requires a non-empty approval_id under execution policy",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.move", "overwrite": True},
                "",
                {},
                ["fs.write_patch"],
                target_exists=False,
            ),
            "",
        )
        self.assertEqual(
            required_action_approval_error(
                {"kind": "fs.move", "overwrite": True},
                "",
                {},
                ["fs.write_patch"],
                target_exists=True,
            ),
            "kind fs.move requires a non-empty approval_id under execution policy",
        )


if __name__ == "__main__":
    unittest.main()
