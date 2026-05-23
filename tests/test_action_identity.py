from __future__ import annotations

import unittest

from core.action_identity import (
    compute_exec_command_signature,
    compute_normalized_action_fingerprint,
)


class ActionIdentityTests(unittest.TestCase):
    def test_compute_exec_command_signature_is_stable_for_same_snapshot(self) -> None:
        registry_a = {
            "cmd-001": {
                "argv": ["python", "-m", "pytest"],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        }
        registry_b = {
            "cmd-001": {
                "argv": ["python", "-m", "pytest"],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        }

        self.assertEqual(
            compute_exec_command_signature(registry_a, "cmd-001"),
            compute_exec_command_signature(registry_b, "cmd-001"),
        )

    def test_compute_exec_command_signature_is_deterministic_for_missing_command(self) -> None:
        registry = {"cmd-001": {"argv": ["python"]}}

        self.assertEqual(
            compute_exec_command_signature(registry, "cmd-missing"),
            compute_exec_command_signature(registry, "cmd-missing"),
        )

    def test_compute_exec_command_signature_normalizes_non_list_argv(self) -> None:
        malformed_registry = {
            "cmd-001": {
                "argv": "python -m pytest",
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        }
        normalized_registry = {
            "cmd-001": {
                "argv": [],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        }

        self.assertEqual(
            compute_exec_command_signature(malformed_registry, "cmd-001"),
            compute_exec_command_signature(normalized_registry, "cmd-001"),
        )

    def test_compute_exec_command_signature_coerces_allow_in_verify_to_bool(self) -> None:
        truthy_registry = {
            "cmd-001": {
                "argv": ["python"],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": "yes",
            }
        }
        true_registry = {
            "cmd-001": {
                "argv": ["python"],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": True,
            }
        }
        false_registry = {
            "cmd-001": {
                "argv": ["python"],
                "cwd": ".",
                "timeout_ms": 1000,
                "determinism": "high",
                "side_effect": "read_only",
                "risk": "low",
                "allow_in_verify": False,
            }
        }

        self.assertEqual(
            compute_exec_command_signature(truthy_registry, "cmd-001"),
            compute_exec_command_signature(true_registry, "cmd-001"),
        )
        self.assertNotEqual(
            compute_exec_command_signature(true_registry, "cmd-001"),
            compute_exec_command_signature(false_registry, "cmd-001"),
        )

    def test_compute_normalized_action_fingerprint_ignores_id_and_summary(self) -> None:
        action_a = {
            "id": "act-001",
            "summary": "first",
            "kind": "fs.create_file",
            "path": "draft.txt",
            "content": "alpha\n",
        }
        action_b = {
            "id": "act-999",
            "summary": "second",
            "kind": "fs.create_file",
            "path": "draft.txt",
            "content": "alpha\n",
        }

        self.assertEqual(
            compute_normalized_action_fingerprint(action_a),
            compute_normalized_action_fingerprint(action_b),
        )

    def test_compute_normalized_action_fingerprint_uses_command_signature_only_for_exec_command(self) -> None:
        exec_action = {
            "kind": "exec.command",
            "command_id": "cmd-001",
        }
        create_file_action = {
            "kind": "fs.create_file",
            "path": "draft.txt",
            "content": "alpha\n",
        }

        self.assertNotEqual(
            compute_normalized_action_fingerprint(exec_action),
            compute_normalized_action_fingerprint(exec_action, command_signature="sig-001"),
        )
        self.assertEqual(
            compute_normalized_action_fingerprint(create_file_action),
            compute_normalized_action_fingerprint(create_file_action, command_signature="sig-001"),
        )


if __name__ == "__main__":
    unittest.main()
