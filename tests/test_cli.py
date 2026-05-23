from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import threading
import tomllib
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest import mock

import cli.main as cli_main_module
import cli.project_dashboard as project_dashboard_module
import cli.project_registry as project_registry_module
import cli.commands.worktree as worktree_command_module
import cli.worktree_registry as worktree_registry_module
from cli.commands.init import run_init
from cli.commands.resume import run_resume
from cli.commands.validate import run_validate
from core.state_store import StateStore
from tests.runtime_fixtures import seed_registered_source


REPO_ROOT = Path(__file__).resolve().parents[1]


def _toml_escape(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"')


def _run_git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        ["git", *args],
        cwd=root,
        capture_output=True,
        text=True,
        check=False,
    )


def _init_git_repo(root: Path) -> None:
    init_result = subprocess.run(
        ["git", "init", "-b", "main", str(root)],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    if init_result.returncode != 0:
        raise AssertionError(init_result.stderr or init_result.stdout)
    for command in (
        ("config", "user.email", "codex@example.com"),
        ("config", "user.name", "Codex"),
    ):
        result = _run_git(root, *command)
        if result.returncode != 0:
            raise AssertionError(result.stderr or result.stdout)
    (root / "README.md").write_text("demo\n", encoding="utf-8")
    add_result = _run_git(root, "add", "README.md")
    if add_result.returncode != 0:
        raise AssertionError(add_result.stderr or add_result.stdout)
    commit_result = _run_git(root, "commit", "-m", "init")
    if commit_result.returncode != 0:
        raise AssertionError(commit_result.stderr or commit_result.stdout)


class CliHelpAndExitCodeTests(unittest.TestCase):
    def test_main_help_via_module_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.replace("\n", " ")
        self.assertIn("Deterministic context runtime.", result.stdout)
        self.assertIn("Install Cerebro once from the Cerebro repository root.", result.stdout)
        self.assertIn("Use Cerebro from the target project root.", result.stdout)
        self.assertIn("First successful run:", result.stdout)
        self.assertIn("cerebro init", result.stdout)
        self.assertIn("cerebro import-context --files ...", result.stdout)
        self.assertIn("cerebro checkpoint --goal ... --summary ... --next-step ...", result.stdout)
        self.assertIn("cerebro validate", result.stdout)
        self.assertIn("--project-root", result.stdout)
        self.assertIn("target project root", help_text)
        self.assertIn("After bootstrap, `cerebro analyze` is the standard entrypoint.", help_text)
        self.assertIn("Ignore exports and advanced commands until this succeeds once.", help_text)
        self.assertIn("analyze", result.stdout)
        self.assertIn("approve", result.stdout)
        self.assertIn("apply", result.stdout)
        self.assertIn("bootstrap-scan", result.stdout)
        self.assertIn("context-index-export", result.stdout)
        self.assertIn("doctor", result.stdout)
        self.assertIn("iteration-commit", result.stdout)
        self.assertIn("import-context", result.stdout)
        self.assertIn("handoff-export", result.stdout)
        self.assertIn("impact-export", result.stdout)
        self.assertIn("plan", result.stdout)
        self.assertIn("residuals-view", result.stdout)
        self.assertIn("rollback", result.stdout)
        self.assertIn("session-discard", result.stdout)
        self.assertIn("return-map-export", result.stdout)
        self.assertIn("runtime-manager", result.stdout)
        self.assertIn("sources-export", result.stdout)
        self.assertIn("status-export", result.stdout)
        self.assertIn("validation-export", result.stdout)
        self.assertIn("verify", result.stdout)
        self.assertIn("worktree", result.stdout)

    def test_subcommand_help_pages(self) -> None:
        for command in (
            "analyze",
            "approve",
            "apply",
            "bootstrap-scan",
            "context-index-export",
            "doctor",
            "iteration-commit",
            "init",
            "import-context",
            "checkpoint",
            "plan",
            "residuals-view",
            "resume",
            "rollback",
            "session-discard",
            "worktree",
            "handoff-export",
            "context-index-export",
            "impact-export",
            "return-map-export",
            "runtime-manager",
            "sources-export",
            "status-export",
            "validation-export",
            "validate",
            "verify",
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                self.assertIn(command, result.stdout)

    def test_runtime_manager_mcp_stdio_reports_missing_optional_extra(self) -> None:
        import adapters.runtime_manager_mcp_stdio as mcp_stdio

        with tempfile.TemporaryDirectory() as project_dir:
            project_root = Path(project_dir).resolve()
            missing_mcp = ModuleNotFoundError("No module named 'mcp'", name="mcp")
            stream = io.StringIO()
            with mock.patch.object(mcp_stdio, "run_stdio", side_effect=missing_mcp):
                with redirect_stdout(stream):
                    exit_code = cli_main_module.main([
                        "--project-root",
                        str(project_root),
                        "runtime-manager",
                        "mcp-stdio",
                    ])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("runtime_manager_mcp_unavailable", output)
        self.assertIn('python -m pip install -e ".[mcp]"', output)

    def test_cli_rejects_unapproved_human_aliases(self) -> None:
        for alias in (
            "gerente",
            "marcar",
            "conferir",
            "faxineiro",
            "memoria",
            "caminho",
            "impacto",
            "entrega",
        ):
            with self.subTest(alias=alias):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", alias],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 2)
                self.assertIn("invalid choice", result.stderr)

    def test_analyze_help_declares_standard_entrypoint(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "analyze", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Official runtime entrypoint", result.stdout)

    def test_resume_help_declares_compatibility_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "resume", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Compatibility command", result.stdout)

    def test_doctor_help_declares_read_only_diagnostic_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "doctor", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("read-only diagnostic report", result.stdout)
        self.assertIn("does not open continuity", result.stdout)
        self.assertIn("does not mutate runtime state", result.stdout)

    def test_iteration_commit_help_declares_generated_commit_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "iteration-commit", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("Generate an iteration commit message", result.stdout)
        self.assertIn("selected repository paths", result.stdout)

    def test_worktree_help_declares_isolated_git_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "worktree", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("isolated git worktrees", result.stdout)
        self.assertIn(".worktrees/", result.stdout)

    def test_runtime_manager_help_declares_core_delegation(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "runtime-manager", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.replace("\n", " ")
        self.assertIn("core.runtime_manager_store", result.stdout)
        self.assertIn("does not parse TOML, SQLite, or Markdown directly", help_text)
        self.assertIn("sync", result.stdout)
        self.assertIn("status", result.stdout)
        self.assertIn("next", result.stdout)

    def test_runtime_manager_cli_sync_status_and_next_use_core_read_model(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            (operations / "observation_center.toml").write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "projection only"
opportunity_map = "projection only"

[[observations]]
id = "runtime-manager-phase-1"
title = "Runtime Manager Phase 1"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "FORMAL_RESUME_TRIGGER_RUNTIME_MANAGER_PHASE_1.md"
dependencies = []
dependencies_satisfied = true
required_validations = ["val-1"]
next_action = "show status"
done_when = "done"
halt_if = "halt"

[[validation_records]]
id = "val-1"
subject_id = "runtime-manager-phase-1"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
fresh_until = "2099-01-01T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture green validation"
""".lstrip(),
                encoding="utf-8",
            )

            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            next_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)
            sync_payload = json.loads(sync_result.stdout)
            self.assertEqual(sync_payload["selected_id"], "runtime-manager-phase-1")
            self.assertEqual(sync_payload["validations"]["expired"], 0)
            self.assertEqual(sync_payload["selection_audit"]["policy_version"], "runtime-manager-selection-v1")
            self.assertEqual(sync_payload["selection_audit"]["sort_policy"], ["priority_rank", "source_index", "id"])
            self.assertEqual(sync_payload["selection_audit"]["decision"], "selected")
            self.assertEqual(sync_payload["selection_audit"]["selected_id"], "runtime-manager-phase-1")
            self.assertEqual(sync_payload["selection_audit"]["eligible_ids"], ["runtime-manager-phase-1"])
            self.assertEqual(status_result.returncode, 0, status_result.stderr or status_result.stdout)
            self.assertIn("mode: read-only status", status_result.stdout)
            self.assertIn("projection_role: projection_only_not_authority", status_result.stdout)
            self.assertIn("selected_id: runtime-manager-phase-1", status_result.stdout)
            self.assertIn("selection_audit_decision: selected", status_result.stdout)
            self.assertIn("selection_audit_policy_version: runtime-manager-selection-v1", status_result.stdout)
            self.assertIn("selection_audit_sort_policy: priority_rank, source_index, id", status_result.stdout)
            self.assertIn("selection_audit_eligible_ids: runtime-manager-phase-1", status_result.stdout)
            self.assertIn("decisions_total: 0", status_result.stdout)
            self.assertIn("evidence_total: 0", status_result.stdout)
            self.assertIn("tools_total: 0", status_result.stdout)
            self.assertIn("approvals_total: 0", status_result.stdout)
            self.assertIn("events_total: 3", status_result.stdout)
            self.assertIn("active_leases: 0", status_result.stdout)
            self.assertIn("leases_expired: 0", status_result.stdout)
            self.assertIn("replay_runs_total: 0", status_result.stdout)
            self.assertIn("replay_runs_passed: 0", status_result.stdout)
            self.assertIn("replay_runs_failed: 0", status_result.stdout)
            self.assertIn("validations_total: 1", status_result.stdout)
            self.assertIn("validations_green: 1", status_result.stdout)
            self.assertIn("validations_expired: 0", status_result.stdout)
            self.assertIn("stop_conditions_active: 0", status_result.stdout)
            self.assertEqual(next_result.returncode, 0, next_result.stderr or next_result.stdout)
            next_payload = json.loads(next_result.stdout)
            self.assertEqual(next_payload["projection_role"], "projection_only_not_authority")
            self.assertEqual(next_payload["selection_audit"]["decision"], "selected")
            self.assertEqual(next_payload["next"]["required_decisions"], [])
            self.assertEqual(next_payload["next"]["required_evidence"], [])
            self.assertEqual(next_payload["next"]["required_tools"], [])
            self.assertEqual(next_payload["next"]["required_approvals"], [])
            self.assertEqual(next_payload["next"]["required_validations"], ["val-1"])
            self.assertEqual(next_payload["next"]["next_action"], "show status")

    def test_runtime_manager_status_and_next_write_projection_outputs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            (operations / "observation_center.toml").write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "item"
title = "Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
next_action = "next"
done_when = "done"
halt_if = "halt"
""".lstrip(),
                encoding="utf-8",
            )
            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)

            status_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status", "--out", "runtime-status.txt"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            next_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next", "--format", "json", "--out", "runtime-next.json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(status_result.returncode, 0, status_result.stderr or status_result.stdout)
            self.assertIn("runtime_manager_projection_written", status_result.stdout)
            status_text = (root / "runtime-status.txt").read_text(encoding="utf-8")
            self.assertIn("projection_role: projection_only_not_authority", status_text)
            self.assertIn("validations_total: 0", status_text)
            self.assertIn("validations_expired: 0", status_text)
            self.assertIn("stop_conditions_active: 0", status_text)
            self.assertEqual(next_result.returncode, 0, next_result.stderr or next_result.stdout)
            next_payload = json.loads((root / "runtime-next.json").read_text(encoding="utf-8"))
            self.assertEqual(next_payload["projection_role"], "projection_only_not_authority")
            self.assertEqual(next_payload["next"]["id"], "item")
            self.assertEqual(next_payload["next"]["required_validations"], [])

    def test_runtime_manager_projection_rejects_runtime_and_authority_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            source = operations / "observation_center.toml"
            source.write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "item"
title = "Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
next_action = "next"
done_when = "done"
halt_if = "halt"
""".lstrip(),
                encoding="utf-8",
            )
            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)

            for output_path in (
                ".cerebro/status.txt",
                "docs/operations/observation_center.toml",
                "docs/operations/SYSTEM_STATE.md",
                "docs/operations/OPPORTUNITY_MAP.md",
            ):
                with self.subTest(output_path=output_path):
                    result = subprocess.run(
                        [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status", "--out", output_path],
                        cwd=root,
                        capture_output=True,
                        text=True,
                    )
                    self.assertEqual(result.returncode, 1)
                    self.assertIn("runtime_manager_failed", result.stdout)

    def test_runtime_manager_projection_rejects_registered_source_when_state_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("source\n", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True, exist_ok=True)
            (operations / "observation_center.toml").write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "item"
title = "Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
next_action = "next"
done_when = "done"
halt_if = "halt"
""".lstrip(),
                encoding="utf-8",
            )
            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)
            before = tracked.read_text(encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status", "--out", "tracked.txt"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("registered source", result.stdout)
            self.assertEqual(tracked.read_text(encoding="utf-8"), before)

    def test_runtime_manager_status_fails_closed_when_source_digest_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            source = operations / "observation_center.toml"
            source.write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "item"
title = "Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
next_action = "next"
done_when = "done"
halt_if = "halt"
""".lstrip(),
                encoding="utf-8",
            )
            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)
            source.write_text(source.read_text(encoding="utf-8") + "\n# drift\n", encoding="utf-8")

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            next_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertEqual(result.stdout.splitlines()[0], "FAIL")
            self.assertIn("state: blocked", result.stdout)
            self.assertIn("stale_source: true", result.stdout)
            self.assertIn("gate_diagnostics_total: 1", result.stdout)
            self.assertIn("gate_diagnostic: stale_source subject=runtime-manager", result.stdout)
            self.assertIn("selection_audit_decision: global_blocked", result.stdout)
            self.assertIn("selection_audit_global_blockers: stale_source", result.stdout)
            self.assertEqual(next_result.returncode, 1)
            self.assertEqual(next_result.stdout.splitlines()[0], "FAIL")
            self.assertIn("state: blocked", next_result.stdout)
            self.assertIn("stale_source", next_result.stdout)

    def test_runtime_manager_cli_explains_validation_and_stop_condition_blocks(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            source = operations / "observation_center.toml"
            source.write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "item"
title = "Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
required_validations = ["val-1"]
next_action = "next"
done_when = "done"
halt_if = "halt"
""".lstrip(),
                encoding="utf-8",
            )
            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            blocked_validation = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            blocked_validation_json = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)
            self.assertEqual(blocked_validation.returncode, 1)
            self.assertIn("required validations", blocked_validation.stdout)
            self.assertIn("gate_diagnostics_total: 1", blocked_validation.stdout)
            self.assertIn("gate_diagnostic: missing_validations subject=item details=val-1:missing", blocked_validation.stdout)
            self.assertEqual(blocked_validation_json.returncode, 1)
            validation_payload = json.loads(blocked_validation_json.stdout)
            self.assertIsNone(validation_payload["next"])
            self.assertEqual(
                validation_payload["gate_diagnostics"],
                [
                    {
                        "code": "missing_validations",
                        "subject_id": "item",
                        "details": ["val-1:missing"],
                        "severity": "blocking",
                        "blocking": True,
                    }
                ],
            )
            self.assertEqual(validation_payload["selection_audit"]["decision"], "no_eligible")
            self.assertEqual(validation_payload["selection_audit"]["eligible_ids"], [])
            self.assertEqual(
                validation_payload["selection_audit"]["entries"][0]["blockers"],
                ["missing_validations=val-1:missing"],
            )

            source.write_text(
                source.read_text(encoding="utf-8")
                + """

[[validation_records]]
id = "val-1"
subject_id = "item"
status = "green"
checked_at = "2026-05-08T00:00:00Z"
fresh_until = "2099-01-01T00:00:00Z"
command_id = "unit-test"
evidence_id = "ev-validation"
reason = "fixture green validation"

[[stop_conditions]]
id = "stop-1"
subject_id = "item"
status = "active"
severity = "high"
opened_at = "2026-05-08T00:00:00Z"
resolved_at = ""
reason = "fixture stop"
""",
                encoding="utf-8",
            )
            resync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            blocked_stop = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            blocked_stop_json = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(resync_result.returncode, 0, resync_result.stderr or resync_result.stdout)
            self.assertEqual(blocked_stop.returncode, 0, blocked_stop.stderr or blocked_stop.stdout)
            self.assertIn("active stop condition", blocked_stop.stdout)
            self.assertIn("gate_diagnostic: active_stop_condition subject=item details=<none>", blocked_stop.stdout)
            self.assertIn("validations_green: 1", blocked_stop.stdout)
            self.assertIn("validations_expired: 0", blocked_stop.stdout)
            self.assertIn("stop_conditions_active: 1", blocked_stop.stdout)
            self.assertEqual(blocked_stop_json.returncode, 0, blocked_stop_json.stderr or blocked_stop_json.stdout)
            stop_payload = json.loads(blocked_stop_json.stdout)
            self.assertEqual(
                stop_payload["gate_diagnostics"],
                [
                    {
                        "code": "active_stop_condition",
                        "subject_id": "item",
                        "details": [],
                        "severity": "blocking",
                        "blocking": True,
                    }
                ],
            )
            self.assertEqual(stop_payload["selection_audit"]["decision"], "no_eligible")
            self.assertEqual(stop_payload["selection_audit"]["entries"][0]["blockers"], ["active_stop_condition"])

    def test_runtime_manager_cli_expired_lease_does_not_block_and_appears_in_diagnostics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            operations = root / "docs" / "operations"
            operations.mkdir(parents=True)
            (operations / "observation_center.toml").write_text(
                """
[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[[observations]]
id = "open-item"
title = "Open Item"
status = "open"
kind = "slice"
priority = "critical"
boundary = "core/cli read-only"
trigger = "trigger.md"
dependencies = []
dependencies_satisfied = true
next_action = "do it"
done_when = "done"
halt_if = "halt"

[[runtime_leases]]
id = "lease-expired"
observation_id = "open-item"
owner = "agent-old"
status = "active"
acquired_at = "2026-01-01T00:00:00Z"
expires_at = "2000-01-01T00:00:00Z"
reason = "stale expired lease"
""".lstrip(),
                encoding="utf-8",
            )

            sync_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            status_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "status"],
                cwd=root,
                capture_output=True,
                text=True,
            )
            next_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "next", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(sync_result.returncode, 0, sync_result.stderr or sync_result.stdout)
            sync_payload = json.loads(sync_result.stdout)
            self.assertEqual(sync_payload["state"], "ready")
            self.assertEqual(sync_payload["selected_id"], "open-item")
            self.assertEqual(sync_payload["leases"]["active"], 0)
            self.assertEqual(sync_payload["leases"]["expired"], 1)
            self.assertEqual(
                sync_payload["gate_diagnostics"],
                [
                    {
                        "code": "active_lease_expired",
                        "subject_id": "runtime-manager",
                        "details": ["open-item"],
                        "severity": "informational",
                        "blocking": False,
                    }
                ],
            )
            self.assertEqual(status_result.returncode, 0, status_result.stderr or status_result.stdout)
            self.assertIn("active_leases: 0", status_result.stdout)
            self.assertIn("leases_expired: 1", status_result.stdout)
            self.assertIn("gate_diagnostic: active_lease_expired subject=runtime-manager details=open-item", status_result.stdout)
            self.assertIn("severity=informational blocking=false", status_result.stdout)
            self.assertEqual(next_result.returncode, 0, next_result.stderr or next_result.stdout)
            next_payload = json.loads(next_result.stdout)
            self.assertEqual(next_payload["next"]["id"], "open-item")
            self.assertEqual(next_payload["selection_audit"]["decision"], "selected")
            self.assertEqual(next_payload["selection_audit"]["global_blockers"], [])

    def test_session_discard_help_declares_explicit_reopen_boundary(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "session-discard", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("stale-session", result.stdout)
        self.assertIn("does not make continuity uninterrupted again", result.stdout)

    def test_validation_export_help_declares_persisted_validation_role(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "validation-export", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("read-only validation view", result.stdout)

    def test_export_subcommands_declare_json_format_option(self) -> None:
        for command in (
            "handoff-export",
            "context-index-export",
            "impact-export",
            "sources-export",
            "return-map-export",
            "status-export",
            "validation-export",
        ):
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )

                self.assertEqual(result.returncode, 0)
                self.assertIn("--format", result.stdout)
                self.assertIn("json", result.stdout)
                self.assertIn("md", result.stdout)

    def test_import_context_help_declares_diff_and_confirmation(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "import-context", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        help_text = result.stdout.replace("\n", " ")
        self.assertIn("sources diff", help_text)
        self.assertIn("requires confirmation", help_text)

    def test_plan_help_declares_domain_input_adapter_options(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "plan", "--help"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 0)
        self.assertIn("--input-text", result.stdout)
        self.assertIn("--input-file", result.stdout)
        self.assertIn("--input-kind", result.stdout)

    def test_export_help_pages_declare_read_only_derived_role(self) -> None:
        expected_fragments = {
            "handoff-export": ("Markdown handoff", "canonical", "state"),
            "context-index-export": ("read-only navigation index", "canonical", "sources", "checkpoint"),
            "impact-export": ("read-only impact view", "canonical", "state"),
            "residuals-view": ("read-only view", "docs/operations/residuals.toml"),
            "sources-export": ("read-only inventory", "canonical", "state"),
            "return-map-export": ("read-only return map", "canonical", "checkpoint"),
            "status-export": ("read-only operational status", "canonical", "state"),
            "validation-export": ("read-only validation view", "persisted", "canonical validation record"),
        }

        for command, fragments in expected_fragments.items():
            with self.subTest(command=command):
                result = subprocess.run(
                    [sys.executable, "-m", "cli.main", command, "--help"],
                    cwd=REPO_ROOT,
                    capture_output=True,
                    text=True,
                )
                self.assertEqual(result.returncode, 0)
                for fragment in fragments:
                    self.assertIn(fragment, result.stdout)

    def test_cli_usage_error_returns_exit_code_2(self) -> None:
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "checkpoint"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("usage:", result.stderr)

    def test_main_dispatches_current_working_directory_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["validate"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_handlers(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["--project-root", str(project_root), "validate"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_accepts_explicit_project_root_after_subcommand(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_validate(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_validate", side_effect=fake_validate):
                    exit_code = cli_main_module.main(["validate", "--project-root", str(project_root)])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_dispatches_current_working_directory_to_doctor_by_default(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_doctor(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_doctor", side_effect=fake_doctor):
                    exit_code = cli_main_module.main(["doctor"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_doctor_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_doctor(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_doctor", side_effect=fake_doctor):
                    exit_code = cli_main_module.main(["doctor", "--project-root", str(project_root)])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_dispatches_current_working_directory_to_iteration_commit_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_iteration_commit(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_iteration_commit", side_effect=fake_iteration_commit):
                    exit_code = cli_main_module.main(["iteration-commit", "--path", "docs/operations/IMPLEMENTATION_STATUS.md"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_iteration_commit_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_iteration_commit(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_iteration_commit", side_effect=fake_iteration_commit):
                    exit_code = cli_main_module.main(
                        ["iteration-commit", "--project-root", str(project_root), "--path", "docs/operations/IMPLEMENTATION_STATUS.md"]
                    )
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_dispatches_current_working_directory_to_worktree_handler(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_worktree(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_worktree", side_effect=fake_worktree):
                    exit_code = cli_main_module.main(["worktree", "create", "demo"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_dispatches_explicit_project_root_to_worktree_handler(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            observed: list[Path] = []

            def fake_worktree(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch.object(cli_main_module, "run_worktree", side_effect=fake_worktree):
                    exit_code = cli_main_module.main(["--project-root", str(project_root), "worktree", "create", "demo"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])

    def test_main_without_argv_opens_context_menu_and_dispatches_development_mode(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir, tempfile.TemporaryDirectory() as fake_home:
            root = Path(tmp_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                print("ANALYZE_CALLED")
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["1"]):
                            with mock.patch.object(cli_main_module, "render_open_dashboard", return_value="DASHBOARD\nestado_projeto: state_absent"):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])
            self.assertIn("CEREBRO", output)
            self.assertIn("(1) Desenvolvimento", output)
            self.assertIn("(2) Gerenciar projeto", output)
            self.assertIn("DASHBOARD", output)
            self.assertLess(output.index("DASHBOARD"), output.index("ANALYZE_CALLED"))
            self.assertFalse((fake_home_root / ".cerebro" / "projects.toml").exists())

    def test_main_none_uses_process_argv_for_context_menu_dispatch(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(sys, "argv", ["cerebro"]):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["1"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                exit_code = cli_main_module.main()
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_main_without_argv_opens_context_menu_and_dispatches_managed_project_mode(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                print("ANALYZE_CALLED")
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(project_root)]):
                            with mock.patch.object(cli_main_module, "render_open_dashboard", return_value="DASHBOARD\nestado_projeto: state_absent"):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])
            self.assertIn("DASHBOARD", output)
            self.assertLess(output.index("DASHBOARD"), output.index("ANALYZE_CALLED"))
            self.assertTrue(registry_path.exists())
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(registry["projects"][0]["name"], project_root.name)
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)
            self.assertTrue(registry["projects"][0]["last_used"])

    def test_main_without_argv_fails_closed_for_invalid_context_menu_selection(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch("builtins.input", side_effect=["9"]):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_invalid", output)

    def test_main_without_argv_fails_closed_when_context_menu_input_is_closed(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=True):
            with mock.patch("builtins.input", side_effect=EOFError()):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_input_closed", output)
        self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_for_blank_project_root(self) -> None:
        stream = io.StringIO()

        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2", "   "]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_root_missing", output)

    def test_main_without_argv_fails_closed_when_project_root_input_is_closed(self) -> None:
        stream = io.StringIO()

        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2", EOFError()]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_root_input_closed", output)
        self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_when_registry_lock_cleanup_fails(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            other_root = Path(other_dir).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            stream = io.StringIO()
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                        with mock.patch("sys.stdin.isatty", return_value=True):
                            with mock.patch("builtins.input", side_effect=["2", str(project_root)]):
                                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                    with redirect_stdout(stream):
                                        exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_invalid", output)
            self.assertNotIn("internal_error", output)
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_main_without_argv_fails_closed_when_registered_project_selection_input_is_closed(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", EOFError()]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_selection_closed", output)
            self.assertNotIn("internal_error", output)

    def test_main_without_argv_fails_closed_when_terminal_is_unavailable(self) -> None:
        stream = io.StringIO()

        with mock.patch("sys.stdin.isatty", return_value=False):
            with mock.patch("builtins.input", side_effect=AssertionError("input should not be called")):
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with redirect_stdout(stream):
                        exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("context_menu_unavailable", output)

    def test_main_without_argv_lists_registered_projects_and_dispatches_selected_project(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as second_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            second_root = Path(second_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            registry_path = registry_dir / "projects.toml"
            registry_path.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                        "[[projects]]",
                        'name = "beta"',
                        f'path = "{_toml_escape(str(second_root))}"',
                        'last_used = "2026-04-16T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            observed: list[Path] = []
            stream = io.StringIO()

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", "1"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [project_root])
            self.assertIn("Projetos registrados", output)
            self.assertEqual(registry["projects"][0]["path"], str(project_root))
            self.assertNotEqual(registry["projects"][0]["last_used"], "2026-04-17T10:00:00+00:00")

    def test_main_without_argv_fails_closed_when_project_registry_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home:
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text("not = [valid", encoding="utf-8")
            stream = io.StringIO()

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("sys.stdin.isatty", return_value=True):
                    with mock.patch("builtins.input", side_effect=["2"]):
                        with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                            with redirect_stdout(stream):
                                exit_code = cli_main_module.main([])

        output = stream.getvalue()
        self.assertEqual(exit_code, 1)
        self.assertIn("project_registry_invalid", output)

    def test_main_without_argv_fails_closed_for_invalid_registered_project_selection(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            registry_dir = fake_home_root / ".cerebro"
            registry_dir.mkdir(parents=True, exist_ok=True)
            (registry_dir / "projects.toml").write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "alpha"',
                        f'path = "{_toml_escape(str(project_root))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", "9"]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_registry_selection_invalid", output)

    def test_main_without_argv_fails_closed_when_managed_project_root_does_not_exist(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            missing_root = other_root / "missing-project"
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(missing_root)]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_root_not_found", output)

    def test_main_without_argv_fails_closed_when_managed_project_root_is_not_directory(self) -> None:
        with tempfile.TemporaryDirectory() as other_dir, tempfile.TemporaryDirectory() as fake_home:
            other_root = Path(other_dir).resolve()
            fake_home_root = Path(fake_home).resolve()
            invalid_root = other_root / "not-a-directory.txt"
            invalid_root.write_text("content", encoding="utf-8")
            stream = io.StringIO()

            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                    with mock.patch("sys.stdin.isatty", return_value=True):
                        with mock.patch("builtins.input", side_effect=["2", str(invalid_root)]):
                            with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                                with redirect_stdout(stream):
                                    exit_code = cli_main_module.main([])
            finally:
                os.chdir(previous_cwd)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("project_root_invalid", output)

    def test_project_registry_serializes_concurrent_updates(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_a_dir, tempfile.TemporaryDirectory() as project_b_dir:
            fake_home_root = Path(fake_home).resolve()
            project_a = Path(project_a_dir).resolve()
            project_b = Path(project_b_dir).resolve()
            entered = threading.Event()
            release = threading.Event()
            second_done = threading.Event()
            errors: list[Exception] = []
            original_load = project_registry_module._load_projects_unlocked
            load_calls = {"count": 0}

            def blocking_load(path: Path) -> list[dict[str, str]]:
                load_calls["count"] += 1
                if load_calls["count"] == 1:
                    entered.set()
                    release.wait(timeout=5)
                return original_load(path)

            def register_project(root: Path, *, done: threading.Event | None = None) -> None:
                try:
                    project_registry_module.register_or_update_project(root)
                except Exception as exc:  # pragma: no cover - test helper
                    errors.append(exc)
                finally:
                    if done is not None:
                        done.set()

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch.object(project_registry_module, "_load_projects_unlocked", side_effect=blocking_load):
                    first = threading.Thread(target=register_project, args=(project_a,))
                    second = threading.Thread(target=register_project, args=(project_b,), kwargs={"done": second_done})
                    first.start()
                    self.assertTrue(entered.wait(timeout=5))
                    second.start()
                    self.assertFalse(second_done.wait(timeout=0.2))
                    release.set()
                    first.join(timeout=5)
                    second.join(timeout=5)

            registry = tomllib.loads((fake_home_root / ".cerebro" / "projects.toml").read_text(encoding="utf-8"))
            paths = {Path(item["path"]) for item in registry["projects"]}
            self.assertEqual(errors, [])
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual(paths, {project_a, project_b})

    def test_project_registry_register_or_update_project_rejects_missing_root_outside_menu(self) -> None:
        with (
            tempfile.TemporaryDirectory() as fake_home,
            tempfile.TemporaryDirectory() as existing_project_dir,
            tempfile.TemporaryDirectory() as missing_parent_dir,
        ):
            fake_home_root = Path(fake_home).resolve()
            existing_project = Path(existing_project_dir).resolve()
            missing_root = (Path(missing_parent_dir).resolve() / "missing-project").resolve()
            registry_file = fake_home_root / ".cerebro" / "projects.toml"
            registry_file.parent.mkdir(parents=True, exist_ok=True)
            registry_file.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "existing"',
                        f'path = "{_toml_escape(str(existing_project))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            before = registry_file.read_text(encoding="utf-8")

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "project root is invalid"):
                    project_registry_module.register_or_update_project(missing_root)

            self.assertEqual(registry_file.read_text(encoding="utf-8"), before)

    def test_project_registry_save_projects_rejects_missing_root_outside_menu(self) -> None:
        with (
            tempfile.TemporaryDirectory() as fake_home,
            tempfile.TemporaryDirectory() as existing_project_dir,
            tempfile.TemporaryDirectory() as missing_parent_dir,
        ):
            fake_home_root = Path(fake_home).resolve()
            existing_project = Path(existing_project_dir).resolve()
            missing_root = (Path(missing_parent_dir).resolve() / "missing-project").resolve()
            registry_file = fake_home_root / ".cerebro" / "projects.toml"
            registry_file.parent.mkdir(parents=True, exist_ok=True)
            registry_file.write_text(
                "\n".join(
                    [
                        "version = 1",
                        "",
                        "[[projects]]",
                        'name = "existing"',
                        f'path = "{_toml_escape(str(existing_project))}"',
                        'last_used = "2026-04-17T10:00:00+00:00"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            before = registry_file.read_text(encoding="utf-8")

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "project root is invalid"):
                    project_registry_module.save_projects(
                        [
                            {
                                "name": "existing",
                                "path": str(existing_project),
                                "last_used": "2026-04-17T10:00:00+00:00",
                            },
                            {
                                "name": "missing",
                                "path": str(missing_root),
                                "last_used": "2026-04-17T11:00:00+00:00",
                            },
                        ]
                    )

            self.assertEqual(registry_file.read_text(encoding="utf-8"), before)

    def test_project_registry_register_or_update_project_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "failed to release project registry lock"):
                        project_registry_module.register_or_update_project(project_root)

            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_project_registry_save_projects_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with self.assertRaisesRegex(project_registry_module.ProjectRegistryError, "failed to release project registry lock"):
                        project_registry_module.save_projects(
                            [
                                {
                                    "name": "alpha",
                                    "path": str(project_root),
                                    "last_used": "2026-04-17T10:00:00+00:00",
                                }
                            ]
                        )

            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(Path(registry["projects"][0]["path"]), project_root)

    def test_project_registry_register_or_update_project_reports_write_and_lock_release_failure(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with mock.patch.object(
                        project_registry_module,
                        "_save_projects_unlocked",
                        side_effect=project_registry_module.ProjectRegistryError(
                            f"failed to write project registry: {registry_path}"
                        ),
                    ):
                        with self.assertRaisesRegex(
                            project_registry_module.ProjectRegistryError,
                            "failed to write project registry: .*failed to release project registry lock",
                        ):
                            project_registry_module.register_or_update_project(project_root)

            self.assertTrue(registry_path.with_suffix(".toml.lock").exists())

    def test_project_registry_save_projects_reports_write_and_lock_release_failure(self) -> None:
        with tempfile.TemporaryDirectory() as fake_home, tempfile.TemporaryDirectory() as project_dir:
            fake_home_root = Path(fake_home).resolve()
            project_root = Path(project_dir).resolve()
            registry_path = fake_home_root / ".cerebro" / "projects.toml"
            original_unlink = Path.unlink

            def failing_unlink(path: Path, *args: object, **kwargs: object) -> object:
                if path == registry_path.with_suffix(".toml.lock"):
                    raise PermissionError("lock busy")
                return original_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.home", return_value=fake_home_root):
                with mock.patch("pathlib.Path.unlink", new=failing_unlink):
                    with mock.patch.object(
                        project_registry_module,
                        "_save_projects_unlocked",
                        side_effect=project_registry_module.ProjectRegistryError(
                            f"failed to write project registry: {registry_path}"
                        ),
                    ):
                        with self.assertRaisesRegex(
                            project_registry_module.ProjectRegistryError,
                            "failed to write project registry: .*failed to release project registry lock",
                        ):
                            project_registry_module.save_projects(
                                [
                                    {
                                        "name": "alpha",
                                        "path": str(project_root),
                                        "last_used": "2026-04-17T10:00:00+00:00",
                                    }
                                ]
                            )

            self.assertTrue(registry_path.with_suffix(".toml.lock").exists())

    def test_explicit_analyze_does_not_render_open_dashboard(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()
            observed: list[Path] = []

            def fake_analyze(handler_root: Path, _args: object) -> int:
                observed.append(handler_root)
                return 0

            (root / ".git").mkdir()
            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "render_open_dashboard", side_effect=AssertionError("dashboard should not render")):
                    with mock.patch.object(cli_main_module, "run_analyze", side_effect=fake_analyze):
                        exit_code = cli_main_module.main(["analyze"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            self.assertEqual(observed, [root])

    def test_explicit_doctor_does_not_dispatch_analyze(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir).resolve()

            previous_cwd = Path.cwd()
            try:
                os.chdir(root)
                with mock.patch.object(cli_main_module, "run_analyze", side_effect=AssertionError("analyze should not run")):
                    with mock.patch.object(cli_main_module, "run_doctor", return_value=0) as fake_doctor:
                        exit_code = cli_main_module.main(["doctor"])
            finally:
                os.chdir(previous_cwd)

            self.assertEqual(exit_code, 0)
            fake_doctor.assert_called_once()

    def test_worktree_create_creates_git_worktree_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("worktree: demo", output)
            self.assertTrue((repo_root / ".worktrees" / "demo").exists())

            registry = tomllib.loads((repo_root / ".cerebro" / "worktrees.toml").read_text(encoding="utf-8"))
            self.assertEqual(len(registry["worktrees"]), 1)
            self.assertEqual(registry["worktrees"][0]["name"], "demo")
            self.assertEqual(registry["worktrees"][0]["branch"], "worktree-demo")
            self.assertEqual(Path(registry["worktrees"][0]["path"]), repo_root / ".worktrees" / "demo")

            branch_result = _run_git(repo_root, "branch", "--list", "worktree-demo")
            self.assertEqual(branch_result.returncode, 0)
            self.assertIn("worktree-demo", branch_result.stdout)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_create_rejects_invalid_name(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            invalid_name = str((repo_root / "escape").resolve())
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", invalid_name])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("invalid_worktree_name", output)
            self.assertFalse((repo_root / ".worktrees").exists())
            self.assertFalse((repo_root / ".cerebro" / "worktrees.toml").exists())

    def test_worktree_create_fails_closed_when_name_is_already_registered(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                first_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                second_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(first_exit, 0)
            self.assertEqual(second_exit, 1)
            self.assertIn("worktree_already_registered", output)

            registry_entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(registry_entries), 1)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_reports_active_registered_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                list_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 0)
            self.assertEqual(list_exit, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"demo | worktree-demo | active | {repo_root / '.worktrees' / 'demo'}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(repo_root / ".worktrees" / "demo"))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_reports_missing_registered_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_registry_module.save_worktrees(
                repo_root,
                [
                    {
                        "name": "demo",
                        "path": str(repo_root / ".worktrees" / "demo"),
                        "branch": "worktree-demo",
                        "created_at": "2026-04-18T00:00:00+00:00",
                        "status": "active",
                    }
                ],
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"demo | worktree-demo | missing | {repo_root / '.worktrees' / 'demo'}", output)

    def test_worktree_list_reports_unregistered_detached_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "detached-demo"

            add_result = _run_git(repo_root, "worktree", "add", "-b", "worktree-detached-demo", str(worktree_path))
            self.assertEqual(add_result.returncode, 0, add_result.stderr or add_result.stdout)
            detach_result = _run_git(worktree_path, "checkout", "--detach", "HEAD")
            self.assertEqual(detach_result.returncode, 0, detach_result.stderr or detach_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("worktrees: 1", output)
            self.assertIn(f"detached-demo | - | unregistered | {worktree_path}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-detached-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_list_fails_closed_when_git_listing_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "rev-parse", "--show-toplevel"]:
                    return subprocess.CompletedProcess(command, 0, stdout=str(repo_root) + "\n", stderr="")
                if command == ["git", "rev-parse", "--path-format=absolute", "--git-common-dir"]:
                    return subprocess.CompletedProcess(command, 0, stdout=str(repo_root / ".git") + "\n", stderr="")
                if command == ["git", "worktree", "list", "--porcelain"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git list failed")
                raise AssertionError(f"unexpected git command: {command}")

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("worktree_list_failed", output)
            self.assertIn("git list failed", output)

    def test_worktree_list_fails_closed_when_registry_name_does_not_match_path(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            registry_path = repo_root / ".cerebro" / "worktrees.toml"
            registry_path.parent.mkdir(parents=True, exist_ok=True)
            registry_path.write_text(
                "\n".join(
                    [
                        "[[worktrees]]",
                        'name = "fake-name"',
                        f'path = "{_toml_escape(str(repo_root / ".worktrees" / "real-name"))}"',
                        'branch = "worktree-real-name"',
                        'created_at = "2026-04-18T00:00:00+00:00"',
                        'status = "active"',
                        "",
                    ]
                ),
                encoding="utf-8",
            )
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(["--project-root", str(repo_root), "worktree", "list"])

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertIn("name does not match path basename", output)

    def test_worktree_list_uses_admin_root_when_invoked_from_child_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            create_stream = io.StringIO()
            child_path = repo_root / ".worktrees" / "demo"

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            self.assertEqual(create_exit, 0)

            list_stream = io.StringIO()
            with redirect_stdout(list_stream):
                list_exit = cli_main_module.main(["--project-root", str(child_path), "worktree", "list"])

            output = list_stream.getvalue()
            self.assertEqual(list_exit, 0)
            self.assertIn(f"repo_root: {repo_root}", output)
            self.assertIn(f"demo | worktree-demo | active | {child_path}", output)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(child_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_removes_worktree_branch_and_registry_entry(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 0)
            self.assertEqual(clean_exit, 0)
            self.assertIn("worktree: demo", output)
            self.assertFalse((repo_root / ".worktrees" / "demo").exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_registered_active_does_not_use_force_remove(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()
            observed_remove_commands: list[list[str]] = []
            real_run_git = worktree_command_module._run_git_command

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command[:3] == ["git", "worktree", "remove"]:
                    observed_remove_commands.append(command)
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            stream = io.StringIO()
            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertEqual(observed_remove_commands, [["git", "worktree", "remove", str(worktree_path)]])
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_blocks_dirty_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()

            with redirect_stdout(stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            (worktree_path / "dirty.txt").write_text("dirty\n", encoding="utf-8")

            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_dirty", output)
            self.assertTrue(worktree_path.exists())
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_keeps_registry_when_branch_delete_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            real_run_git = worktree_command_module._run_git_command
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_failed", output)
            self.assertIn("branch delete failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_create_cleans_up_when_registry_persist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_create_reports_cleanup_failure_when_registry_persist_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            real_run_git = worktree_command_module._run_git_command
            stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="cleanup branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                    with redirect_stdout(stream):
                        create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("cleanup failed", output)
            self.assertIn("cleanup branch delete failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_create_fails_closed_when_git_worktree_add_fails(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()
            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "worktree", "add", "-b", "worktree-demo", str(worktree_path)]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="git worktree add failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_create_failed", output)
            self.assertIn("git worktree add failed", output)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_create_serializes_concurrent_registry_updates(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            entered = threading.Event()
            release = threading.Event()
            second_done = threading.Event()
            errors: list[Exception] = []
            results: dict[str, dict[str, str]] = {}
            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                alpha_command = [
                    "git",
                    "worktree",
                    "add",
                    "-b",
                    "worktree-alpha",
                    str(repo_root / ".worktrees" / "alpha"),
                ]
                if command == alpha_command:
                    entered.set()
                    release.wait(timeout=5)
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            def create_worktree(name: str, *, done: threading.Event | None = None) -> None:
                try:
                    results[name] = worktree_command_module.create_worktree(repo_root, name)
                except Exception as exc:  # pragma: no cover - test helper
                    errors.append(exc)
                finally:
                    if done is not None:
                        done.set()

            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                first = threading.Thread(target=create_worktree, args=("alpha",))
                second = threading.Thread(target=create_worktree, args=("beta",), kwargs={"done": second_done})
                first.start()
                self.assertTrue(entered.wait(timeout=5))
                second.start()
                self.assertFalse(second_done.wait(timeout=0.2))
                release.set()
                first.join(timeout=5)
                second.join(timeout=5)

            registry_entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(errors, [])
            self.assertFalse(first.is_alive())
            self.assertFalse(second.is_alive())
            self.assertEqual({item["name"] for item in registry_entries}, {"alpha", "beta"})
            self.assertEqual({item["name"] for item in results.values()}, {"alpha", "beta"})
            self.assertTrue((repo_root / ".worktrees" / "alpha").exists())
            self.assertTrue((repo_root / ".worktrees" / "beta").exists())

    def test_worktree_create_reports_lock_release_failure_after_persisting(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            registry_path = repo_root / ".cerebro" / "worktrees.toml"
            lock_path = registry_path.with_suffix(".toml.lock")
            worktree_path = repo_root / ".worktrees" / "demo"
            stream = io.StringIO()
            real_unlink = Path.unlink

            def fake_unlink(path: Path, *args, **kwargs):
                if path == lock_path:
                    raise OSError("lock release failed")
                return real_unlink(path, *args, **kwargs)

            with mock.patch("pathlib.Path.unlink", autospec=True, side_effect=fake_unlink):
                with redirect_stdout(stream):
                    create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            output = stream.getvalue()
            registry = tomllib.loads(registry_path.read_text(encoding="utf-8"))
            self.assertEqual(create_exit, 1)
            self.assertIn("worktree_registry_invalid", output)
            self.assertTrue(worktree_path.exists())
            self.assertTrue(lock_path.exists())
            self.assertEqual(registry["worktrees"][0]["name"], "demo")
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            lock_path.unlink(missing_ok=True)
            cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
            delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)

    def test_worktree_clean_removes_unregistered_active_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            add_result = _run_git(repo_root, "worktree", "add", "-b", "worktree-demo", str(worktree_path))
            self.assertEqual(add_result.returncode, 0, add_result.stderr or add_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_worktree_clean_recovers_unregistered_branch_after_failed_create_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            real_run_git = worktree_command_module._run_git_command
            create_stream = io.StringIO()

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="cleanup branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            with mock.patch.object(
                worktree_registry_module.LockedWorktreeRegistry,
                "save",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                    with redirect_stdout(create_stream):
                        create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])

            self.assertEqual(create_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            clean_stream = io.StringIO()
            with redirect_stdout(clean_stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_recovers_when_checkout_was_removed_before_branch_delete(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            real_run_git = worktree_command_module._run_git_command

            def fake_run_git(command: list[str], *, cwd: Path, failure_code: str) -> subprocess.CompletedProcess[str]:
                if command == ["git", "branch", "-D", "worktree-demo"]:
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="branch delete failed")
                return real_run_git(command, cwd=cwd, failure_code=failure_code)

            first_stream = io.StringIO()
            with mock.patch.object(worktree_command_module, "_run_git_command", side_effect=fake_run_git):
                with redirect_stdout(first_stream):
                    first_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(first_clean_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            second_stream = io.StringIO()
            with redirect_stdout(second_stream):
                second_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(second_clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_recovers_when_registry_persist_fails_after_physical_cleanup(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            first_stream = io.StringIO()
            with mock.patch.object(
                worktree_command_module,
                "update_worktrees",
                side_effect=worktree_registry_module.WorktreeRegistryError("persist failed"),
            ):
                with redirect_stdout(first_stream):
                    first_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(first_clean_exit, 1)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

            second_stream = io.StringIO()
            with redirect_stdout(second_stream):
                second_clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            self.assertEqual(second_clean_exit, 0)
            self.assertFalse(worktree_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])
            self.assertEqual(_run_git(repo_root, "branch", "--list", "worktree-demo").stdout.strip(), "")

    def test_worktree_clean_fails_closed_when_removed_checkout_has_tampered_branch(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            create_branch_result = _run_git(repo_root, "branch", "keep-me")
            self.assertEqual(create_branch_result.returncode, 0, create_branch_result.stderr or create_branch_result.stdout)
            remove_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(remove_result.returncode, 0, remove_result.stderr or remove_result.stdout)

            entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(entries), 1)
            tampered_entry = dict(entries[0])
            tampered_entry["branch"] = "keep-me"
            worktree_registry_module.save_worktrees(repo_root, [tampered_entry])

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertIn("keep-me", _run_git(repo_root, "branch", "--list", "keep-me").stdout)

    def test_worktree_clean_fails_closed_when_active_worktree_has_tampered_branch(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            create_branch_result = _run_git(repo_root, "branch", "keep-me")
            self.assertEqual(create_branch_result.returncode, 0, create_branch_result.stderr or create_branch_result.stdout)
            checkout_result = _run_git(worktree_path, "checkout", "keep-me")
            self.assertEqual(checkout_result.returncode, 0, checkout_result.stderr or checkout_result.stdout)

            entries = worktree_registry_module.load_worktrees(repo_root)
            self.assertEqual(len(entries), 1)
            tampered_entry = dict(entries[0])
            tampered_entry["branch"] = "keep-me"
            worktree_registry_module.save_worktrees(repo_root, [tampered_entry])

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertTrue(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)
            self.assertIn("keep-me", _run_git(repo_root, "branch", "--list", "keep-me").stdout)

            cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
            self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
            delete_demo_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
            self.assertEqual(delete_demo_result.returncode, 0, delete_demo_result.stderr or delete_demo_result.stdout)
            delete_keep_result = _run_git(repo_root, "branch", "-D", "keep-me")
            self.assertEqual(delete_keep_result.returncode, 0, delete_keep_result.stderr or delete_keep_result.stdout)

    def test_worktree_clean_fails_closed_when_registry_entry_is_stale(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            worktree_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            detach_result = _run_git(worktree_path, "checkout", "--detach", "HEAD")
            self.assertEqual(detach_result.returncode, 0, detach_result.stderr or detach_result.stdout)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 1)
            self.assertIn("worktree_clean_registry_stale", output)
            self.assertTrue(worktree_path.exists())
            self.assertEqual(len(worktree_registry_module.load_worktrees(repo_root)), 1)
            self.assertIn("worktree-demo", _run_git(repo_root, "branch", "--list", "worktree-demo").stdout)

            try:
                cleanup_result = _run_git(repo_root, "worktree", "remove", "--force", str(worktree_path))
                self.assertEqual(cleanup_result.returncode, 0, cleanup_result.stderr or cleanup_result.stdout)
                delete_result = _run_git(repo_root, "branch", "-D", "worktree-demo")
                self.assertEqual(delete_result.returncode, 0, delete_result.stderr or delete_result.stdout)
            finally:
                pass

    def test_worktree_clean_uses_admin_root_when_invoked_from_child_worktree(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir:
            repo_root = Path(repo_dir).resolve()
            _init_git_repo(repo_root)
            child_path = repo_root / ".worktrees" / "demo"
            create_stream = io.StringIO()

            with redirect_stdout(create_stream):
                create_exit = cli_main_module.main(["--project-root", str(repo_root), "worktree", "create", "demo"])
            self.assertEqual(create_exit, 0)

            stream = io.StringIO()
            with redirect_stdout(stream):
                clean_exit = cli_main_module.main(["--project-root", str(child_path), "worktree", "clean", "demo"])

            output = stream.getvalue()
            self.assertEqual(clean_exit, 0)
            self.assertIn(f"repo_root: {repo_root}", output)
            self.assertFalse(child_path.exists())
            self.assertEqual(worktree_registry_module.load_worktrees(repo_root), [])

    def test_render_open_dashboard_reads_operational_summary_and_initialized_project_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_text(
                "\n".join(
                    [
                        "### CRÍTICO",
                        "- Nenhum item `CRÍTICO` aberto.",
                        "",
                        "### ALTO",
                        "- item alfa",
                        "  Status atual: Grupo 6",
                        "- item beta",
                        "  Status atual: Grupo 6",
                    ]
                ),
                encoding="utf-8",
            )
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `FATIA 4 — Dashboard de estado ao abrir`",
                    ]
                ),
                encoding="utf-8",
            )

            run_init(project_root)

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("impl-fatia-4: dashboard de estado - 617 testes", "617"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("DASHBOARD", output)
            self.assertIn(f"project_root: {project_root}", output)
            self.assertIn("testes: 617", output)
            self.assertIn("criticos_abertos: 0", output)
            self.assertIn("altos_abertos: 2", output)
            self.assertIn("ultima_iteracao: impl-fatia-4: dashboard de estado - 617 testes", output)
            self.assertIn("proximo_item: FATIA 4 — Dashboard de estado ao abrir", output)
            self.assertIn("estado_projeto: initialized", output)
            self.assertIn("revisao: 0", output)
            self.assertIn("validacao:", output)

    def test_render_open_dashboard_reports_not_initialized_when_project_has_no_state(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_text(
                "\n".join(
                    [
                        "### CRÍTICO",
                        "- Nenhum item `CRÍTICO` aberto.",
                        "",
                        "### ALTO",
                        "- item alfa",
                        "  Status atual: Grupo 6",
                    ]
                ),
                encoding="utf-8",
            )
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `FATIA 4 — Dashboard de estado ao abrir`",
                    ]
                ),
                encoding="utf-8",
            )

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("impl-fatia-4: dashboard de estado - 617 testes", "617"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("estado_projeto: state_absent", output)
            self.assertNotIn("revisao:", output)

    def test_render_open_dashboard_reports_state_unavailable_when_state_is_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_text(
                "\n".join(
                    [
                        "### CRÍTICO",
                        "- Nenhum item `CRÍTICO` aberto.",
                        "",
                        "### ALTO",
                        "- item alfa",
                        "  Status atual: Grupo 6",
                    ]
                ),
                encoding="utf-8",
            )
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_text(
                "\n".join(
                    [
                        "## Próxima fatia",
                        "- Qual é: `nenhuma — prova de parada e encerramento formal`",
                    ]
                ),
                encoding="utf-8",
            )
            state_dir = project_root / ".cerebro"
            state_dir.mkdir(parents=True, exist_ok=True)
            (state_dir / "state.json").write_text("{invalid", encoding="utf-8")

            output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("estado_projeto: state_unavailable", output)

    def test_render_open_dashboard_treats_invalid_doc_encoding_as_unknown(self) -> None:
        with tempfile.TemporaryDirectory() as repo_dir, tempfile.TemporaryDirectory() as project_dir:
            repo_root = Path(repo_dir).resolve()
            project_root = Path(project_dir).resolve()
            operations_dir = repo_root / "docs" / "operations"
            operations_dir.mkdir(parents=True, exist_ok=True)
            (operations_dir / "WEAKNESS_REPORT.md").write_bytes(b"\xff\xfe\xfd")
            (operations_dir / "IMPLEMENTATION_STATUS.md").write_bytes(b"\xff\xfe\xfd")

            with mock.patch.object(
                project_dashboard_module,
                "_read_latest_iteration",
                return_value=("unknown", "unknown"),
            ):
                output = project_dashboard_module.render_open_dashboard(project_root, repo_root=repo_root)

            self.assertIn("testes: unknown", output)
            self.assertIn("criticos_abertos: unknown", output)
            self.assertIn("altos_abertos: unknown", output)
            self.assertIn("proximo_item: unknown", output)
            self.assertIn("estado_projeto: state_absent", output)

    def test_plan_uses_explicit_project_root_for_relative_input_file(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as other_dir:
            project_root = Path(project_dir).resolve()
            other_root = Path(other_dir).resolve()
            run_init(project_root, None)
            store, _tracked = seed_registered_source(project_root)
            (project_root / "plan.txt").write_text("comprar arroz, leite, pao", encoding="utf-8")
            (other_root / "plan.txt").write_text("this must not be read", encoding="utf-8")

            stream = io.StringIO()
            previous_cwd = Path.cwd()
            try:
                os.chdir(other_root)
                with redirect_stdout(stream):
                    exit_code = cli_main_module.main(
                        [
                            "--project-root",
                            str(project_root),
                            "plan",
                            "--input-file",
                            "plan.txt",
                            "--input-kind",
                            "list",
                        ]
                    )
            finally:
                os.chdir(previous_cwd)

            runtime = store.read_agent_runtime()
            self.assertEqual(exit_code, 0)
            self.assertEqual(runtime["plan"]["goal"], "Complete listed items")
            self.assertEqual([task["title"] for task in runtime["plan"]["tasks"]], ["comprar arroz", "leite", "pao"])

    def test_bootstrap_scan_root_argument_overrides_global_project_root(self) -> None:
        with tempfile.TemporaryDirectory() as project_dir, tempfile.TemporaryDirectory() as scan_dir:
            project_root = Path(project_dir).resolve()
            scan_root = Path(scan_dir).resolve()
            (project_root / "README.md").write_text("project readme", encoding="utf-8")
            (scan_root / "README.md").write_text("scan readme", encoding="utf-8")
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = cli_main_module.main(
                    [
                        "--project-root",
                        str(project_root),
                        "bootstrap-scan",
                        "--root",
                        str(scan_root),
                        "--limit",
                        "1",
                    ]
                )

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn(f"scan_root: {scan_root}", output)
            self.assertIn(f'next_workdir: cd "{scan_root}"', output)
            self.assertNotIn(f"scan_root: {project_root}", output)


class CliOutputTests(unittest.TestCase):
    def test_init_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_init(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("instance_created:", output)
            self.assertIn("state_path:", output)
            self.assertIn("next_step: edit docs/operations/observation_center.toml", output)

    def test_validate_ok_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_registered_source(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("OK", output)
            self.assertIn("validation_passed:", output)

    def test_validate_ok_output_does_not_reopen_snapshot_after_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_registered_source(root)
            stream = io.StringIO()

            with mock.patch("cli.commands.validate.StateStore.read_snapshot", side_effect=AssertionError("unexpected")):
                with redirect_stdout(stream):
                    exit_code = run_validate(root)

            self.assertEqual(exit_code, 0)

    def test_validate_fail_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.unlink()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_validate(root)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("source_missing", output)

    def test_resume_blocked_output_is_clear(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            source_file = root / "tracked.txt"
            source_file.write_text("hello", encoding="utf-8")
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            source_file.write_text("changed", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"actor": "alice"})

            with redirect_stdout(stream):
                exit_code = run_resume(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("FAIL", output)
            self.assertIn("resume_blocked", output)
            self.assertIn("source_hash_mismatch", output)


class RuntimeManagerRunEndToEndTests(unittest.TestCase):
    """End-to-end CLI tests proving no bypass path in runtime-manager run."""

    def _write_center(self, root: Path, argv: list[str], *, approval_requirement: str = "none") -> None:
        import json as _json
        ops = root / "docs" / "operations"
        ops.mkdir(parents=True, exist_ok=True)
        (ops / "observation_center.toml").write_text(
            f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-e2e"
title = "e2e test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-e2e"
argv_prefix = {_json.dumps(argv)}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "{approval_requirement}"
rollback_class = "reversible"
status = "enabled"
""",
            encoding="utf-8",
        )

    def _sync(self, root: Path) -> None:
        subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
            cwd=root,
            check=True,
            capture_output=True,
        )

    def test_cli_run_executes_registered_command_and_reports_evidence_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('cli-e2e-ok')"]
            self._write_center(root, argv)
            self._sync(root)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-e2e", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["eligible"])
            self.assertEqual(payload["returncode"], 0)
            self.assertIn("cli-e2e-ok", payload["stdout"])
            self.assertGreater(payload["evidence_id"], 0)

    def test_cli_run_fails_for_unregistered_command_without_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root, [sys.executable, "-c", "print('nope')"])
            self._sync(root)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-not-in-registry",
                 "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["eligible"])
            self.assertIn("command_not_registered", payload["blockers"])
            self.assertEqual(payload["evidence_id"], -1)

    def test_cli_run_fails_when_approval_required_but_absent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            argv = [sys.executable, "-c", "print('needs-approval')"]
            self._write_center(root, argv, approval_requirement="required")
            self._sync(root)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-e2e", "--format", "json"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertFalse(payload["eligible"])
            self.assertIn("approval_required", payload["blockers"])
            self.assertEqual(payload["evidence_id"], -1)

    def test_cli_run_no_subprocess_when_db_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-any"],
                cwd=root,
                capture_output=True,
                text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("FAIL", result.stdout)


class RuntimeManagerEvidenceEndToEndTests(unittest.TestCase):
    """CLI end-to-end tests for runtime-manager evidence show/list."""

    def _write_center(self, root: Path) -> None:
        import json as _json
        ops = root / "docs" / "operations"
        ops.mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, "-c", "print('evidence-cli')"]
        (ops / "observation_center.toml").write_text(
            f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-ev"
title = "evidence cli test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-ev"
argv_prefix = {_json.dumps(argv)}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
""",
            encoding="utf-8",
        )

    def _sync_and_run(self, root: Path) -> dict:
        subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
            cwd=root, check=True, capture_output=True,
        )
        result = subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-ev", "--format", "json"],
            cwd=root, capture_output=True, text=True,
        )
        return json.loads(result.stdout)

    def test_evidence_show_returns_record_for_valid_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            run_payload = self._sync_and_run(root)
            evidence_id = run_payload["evidence_id"]
            self.assertGreater(evidence_id, 0)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "evidence", "show",
                 str(evidence_id), "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIsNotNone(payload["evidence"])
            self.assertEqual(payload["evidence"]["evidence_id"], evidence_id)
            self.assertEqual(payload["evidence"]["command_id"], "cmd-ev")
            self.assertEqual(payload["evidence"]["observation_id"], "obs-ev")

    def test_evidence_show_returns_nonzero_for_unknown_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root, check=True, capture_output=True,
            )

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "evidence", "show",
                 "99999", "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertIsNone(payload["evidence"])

    def test_evidence_list_returns_all_runs(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root, check=True, capture_output=True,
            )
            for _ in range(3):
                subprocess.run(
                    [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-ev"],
                    cwd=root, capture_output=True,
                )

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "evidence", "list",
                 "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["total"], 3)
            ids = [e["evidence_id"] for e in payload["evidence"]]
            self.assertEqual(ids, sorted(ids, reverse=True), "evidence list should be newest first")

    def test_evidence_list_limit_option(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root, check=True, capture_output=True,
            )
            for _ in range(5):
                subprocess.run(
                    [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "run", "cmd-ev"],
                    cwd=root, capture_output=True,
                )

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "evidence", "list",
                 "--limit", "2", "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(len(payload["evidence"]), 2)

    def test_evidence_list_negative_limit_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            subprocess.run(
                [sys.executable, "-m", "cli.main", "--project-root", str(root), "runtime-manager", "sync"],
                cwd=root, check=True, capture_output=True,
            )

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "runtime-manager", "evidence", "list",
                 "--limit", "-1", "--format", "json"],
                cwd=root, capture_output=True, text=True,
            )

            self.assertNotEqual(result.returncode, 0)
            self.assertIn("limit must be >= 0", result.stdout)


class RuntimeManagerPhase4CLITests(unittest.TestCase):
    """End-to-end CLI tests for Phase 4 subcommands: lease, stop, validation, approval, rollback."""

    def _write_center(self, root: Path, *, approval_requirement: str = "none",
                      rollback_class: str = "reversible") -> None:
        import json as _json
        ops = root / "docs" / "operations"
        ops.mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, "-c", "print('p4-cli')"]
        (ops / "observation_center.toml").write_text(
            f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-p4"
title = "phase4 cli test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-p4"
argv_prefix = {_json.dumps(argv)}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "{approval_requirement}"
rollback_class = "{rollback_class}"
status = "enabled"
""",
            encoding="utf-8",
        )

    def _cli(self, root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=check,
        )

    def _sync(self, root: Path) -> None:
        self._cli(root, "runtime-manager", "sync", check=True)

    # ── lease ──────────────────────────────────────────────────────────────────

    def test_lease_acquire_returns_json_with_lease_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "lease", "acquire",
                               "obs-p4", "--owner", "agent-1", "--ttl-seconds", "60",
                               "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("lease_id", payload)
            self.assertTrue(payload["lease_id"])
            self.assertEqual(payload["observation_id"], "obs-p4")

    def test_lease_list_returns_json_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "lease", "acquire",
                      "obs-p4", "--owner", "agent-1", "--ttl-seconds", "60", check=True)
            result = self._cli(root, "runtime-manager", "lease", "list", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("leases", payload)
            self.assertEqual(len(payload["leases"]), 1)
            self.assertEqual(payload["leases"][0]["observation_id"], "obs-p4")

    def test_lease_release_removes_active_lease(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            acq = self._cli(root, "runtime-manager", "lease", "acquire",
                            "obs-p4", "--owner", "agent-1", "--ttl-seconds", "60",
                            "--format", "json", check=True)
            lease_id = json.loads(acq.stdout)["lease_id"]
            result = self._cli(root, "runtime-manager", "lease", "release",
                               str(lease_id), "--owner", "agent-1", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["released"])

    # ── stop ───────────────────────────────────────────────────────────────────

    def test_stop_raise_returns_json_with_condition_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "stop", "raise",
                               "obs-p4", "--reason", "test-reason", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("stop_condition_id", payload)
            self.assertTrue(payload["stop_condition_id"])
            self.assertEqual(payload["subject_id"], "obs-p4")

    def test_stop_list_shows_raised_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "stop", "raise",
                      "obs-p4", "--reason", "test-reason", check=True)
            result = self._cli(root, "runtime-manager", "stop", "list", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("stop_conditions", payload)
            self.assertEqual(len(payload["stop_conditions"]), 1)
            self.assertEqual(payload["stop_conditions"][0]["subject_id"], "obs-p4")

    def test_stop_resolve_clears_condition(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            raised = self._cli(root, "runtime-manager", "stop", "raise",
                               "obs-p4", "--reason", "test-reason",
                               "--format", "json", check=True)
            cond_id = json.loads(raised.stdout)["stop_condition_id"]
            result = self._cli(root, "runtime-manager", "stop", "resolve",
                               str(cond_id), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["resolved"])

    # ── validation ─────────────────────────────────────────────────────────────

    def test_validation_record_returns_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "validation", "record",
                               "val-cli-1", "obs-p4",
                               "--status", "red", "--reason", "failed",
                               "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["validation_id"], "val-cli-1")
            self.assertEqual(payload["status"], "red")

    def test_validation_show_returns_recorded_validation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "validation", "record",
                      "val-cli-2", "obs-p4",
                      "--status", "red", "--reason", "failed", check=True)
            result = self._cli(root, "runtime-manager", "validation", "show",
                               "val-cli-2", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["validation_id"], "val-cli-2")

    def test_validation_show_not_found_returns_error(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "validation", "show",
                               "no-such-val", "--format", "json")
            self.assertNotEqual(result.returncode, 0)

    # ── approval ───────────────────────────────────────────────────────────────

    def test_approval_record_returns_json_with_approval_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root, approval_requirement="required")
            self._sync(root)
            result = self._cli(root, "runtime-manager", "approval", "record",
                               "cmd-p4", "obs-p4", "--actor", "human-1",
                               "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("approval_id", payload)
            self.assertTrue(payload["approval_id"])
            self.assertEqual(payload["command_id"], "cmd-p4")

    def test_approval_list_shows_recorded_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root, approval_requirement="required")
            self._sync(root)
            self._cli(root, "runtime-manager", "approval", "record",
                      "cmd-p4", "obs-p4", "--actor", "human-1", check=True)
            result = self._cli(root, "runtime-manager", "approval", "list", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("approvals", payload)
            self.assertEqual(len(payload["approvals"]), 1)
            self.assertEqual(payload["approvals"][0]["command_id"], "cmd-p4")

    def test_approval_revoke_revokes_approval(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root, approval_requirement="required")
            self._sync(root)
            rec = self._cli(root, "runtime-manager", "approval", "record",
                            "cmd-p4", "obs-p4", "--actor", "human-1",
                            "--format", "json", check=True)
            approval_id = json.loads(rec.stdout)["approval_id"]
            # approval_id is a UUID string
            result = self._cli(root, "runtime-manager", "approval", "revoke",
                               approval_id, "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["revoked"])

    # ── rollback ───────────────────────────────────────────────────────────────

    def test_rollback_list_returns_empty_initially(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "rollback", "list", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertIn("rollback_runs", payload)
            self.assertEqual(payload["rollback_runs"], [])

    def test_rollback_executes_and_appears_in_list(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            run = self._cli(root, "runtime-manager", "run", "cmd-p4",
                            "--format", "json", check=True)
            evidence_id = json.loads(run.stdout)["evidence_id"]
            # register rollback via store directly
            from core.runtime_manager_store import RuntimeManagerStore
            store = RuntimeManagerStore(root)
            store.register_rollback(
                "cmd-p4",
                argv_prefix=(sys.executable, "-c", "print('undo')"),
            )
            result = self._cli(root, "runtime-manager", "rollback",
                               "--evidence-id", str(evidence_id), "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["eligible"])


class RuntimeManagerPhase5CLITests(unittest.TestCase):
    """End-to-end CLI tests for Phase 5 trace, metrics, and replay surfaces."""

    def _write_center(self, root: Path) -> None:
        ops = root / "docs" / "operations"
        ops.mkdir(parents=True, exist_ok=True)
        argv = [sys.executable, "-c", "print('SECRET_TOKEN=phase5-cli')"]
        (ops / "observation_center.toml").write_text(
            f"""[center]
version = 1
queue_authority = "machine-primary"
single_flight = true

[projections]
system_state = "p"
opportunity_map = "p"

[[observations]]
id = "obs-p5"
title = "phase5 cli test"
status = "open"
kind = "slice"
priority = "critical"
boundary = "authorized"
trigger = "TRIGGER.md"
dependencies = []
dependencies_satisfied = true
next_action = "run"
done_when = "done"
halt_if = "never"

[[command_registry]]
id = "cmd-p5"
argv_prefix = {json.dumps(argv)}
path_scope = "."
side_effect_class = "read-only"
network_allowed = false
timeout_seconds = 10
output_budget_bytes = 65536
sensitive_output_policy = "none"
approval_requirement = "none"
rollback_class = "reversible"
status = "enabled"
""",
            encoding="utf-8",
        )

    def _cli(self, root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=check,
        )

    def _sync(self, root: Path) -> None:
        self._cli(root, "runtime-manager", "sync", check=True)

    def test_trace_list_show_and_export_otel_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "status", "--format", "json", check=True)

            listed = self._cli(root, "runtime-manager", "trace", "list", "--format", "json")
            self.assertEqual(listed.returncode, 0, listed.stderr)
            list_payload = json.loads(listed.stdout)
            self.assertGreaterEqual(list_payload["total"], 1)
            trace_id = list_payload["traces"][0]["trace_id"]

            shown = self._cli(root, "runtime-manager", "trace", "show", trace_id, "--format", "json")
            self.assertEqual(shown.returncode, 0, shown.stderr)
            show_payload = json.loads(shown.stdout)
            self.assertTrue(show_payload["trace"]["trace_is_not_permission"])

            exported = self._cli(root, "runtime-manager", "trace", "export", trace_id, "--format", "otel-json")
            self.assertEqual(exported.returncode, 0, exported.stderr)
            export_payload = json.loads(exported.stdout)
            self.assertTrue(export_payload["projection_is_not_opentelemetry_export"])
            self.assertTrue(export_payload["telemetry_is_not_permission"])

    def test_trace_show_missing_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)

            result = self._cli(root, "runtime-manager", "trace", "show", "rt-missing", "--format", "json")

            self.assertNotEqual(result.returncode, 0)
            payload = json.loads(result.stdout)
            self.assertIsNone(payload["trace"])

    def test_metrics_json_counts_run_and_traces(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "run", "cmd-p5", "--format", "json", check=True)

            result = self._cli(root, "runtime-manager", "metrics", "--format", "json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertEqual(payload["runs_total"], 1)
            self.assertEqual(payload["runs_passed"], 1)
            self.assertGreaterEqual(payload["traces_total"], 1)

    def test_replay_json_passes_and_does_not_treat_trace_as_permission(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            self._cli(root, "runtime-manager", "run", "cmd-p5", "--format", "json", check=True)
            scenario = root / "phase5-replay.json"
            scenario.write_text(
                json.dumps(
                    {
                        "scenario_id": "phase5-cli-replay",
                        "checks": [
                            {"id": "run-traced", "type": "trace_exists", "operation": "run"},
                            {"id": "run-counted", "type": "metric_at_least", "metric": "runs_total", "min": 1},
                            {
                                "id": "secret-not-retained",
                                "type": "trace_forbids_text",
                                "text": "SECRET_TOKEN=phase5-cli",
                            },
                        ],
                    }
                ),
                encoding="utf-8",
            )

            result = self._cli(root, "runtime-manager", "replay", "--scenario", str(scenario), "--format", "json")

            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["passed"])
            self.assertEqual(payload["authority"], "runtime replay evidence only; not permission")


class RuntimeManagerIntegrityCheckCliTests(unittest.TestCase):
    """Phase 10 — CLI integrity check end-to-end tests."""

    def _write_center(self, root: Path) -> None:
        ops = root / "docs" / "operations"
        ops.mkdir(parents=True, exist_ok=True)
        (ops / "observation_center.toml").write_text(
            "[center]\nversion = 1\n\n"
            "[[observations]]\n"
            'id = "obs-integrity"\n'
            'title = "integrity test obs"\n'
            'status = "open"\n'
            'kind = "slice"\n'
            'priority = "high"\n'
            'boundary = "docs/"\n'
            'trigger = "none"\n'
            "dependencies = []\n"
            "dependencies_satisfied = true\n"
            'next_action = "test"\n'
            'done_when = "done"\n'
            'halt_if = "never"\n',
            encoding="utf-8",
        )

    def _cli(self, root: Path, *args: str, check: bool = False) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", "--project-root", str(root), *args],
            cwd=root,
            capture_output=True,
            text=True,
            check=check,
        )

    def _sync(self, root: Path) -> None:
        self._cli(root, "runtime-manager", "sync", check=True)

    def test_integrity_check_returns_zero_on_clean_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "integrity", "check", "--format", "text")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("RUNTIME MANAGER INTEGRITY CHECK", result.stdout)
            self.assertIn("integrity_report_is_not_permission: true", result.stdout)

    def test_integrity_check_json_carries_not_permission_marker(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            self._write_center(root)
            self._sync(root)
            result = self._cli(root, "runtime-manager", "integrity", "check", "--format", "json")
            self.assertEqual(result.returncode, 0, result.stderr)
            payload = json.loads(result.stdout)
            self.assertTrue(payload["integrity_report_is_not_permission"])
            self.assertIn("generated_at", payload)
            self.assertIn("issues", payload)

    def test_integrity_check_without_db_returns_nonzero(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            result = self._cli(root, "runtime-manager", "integrity", "check")
            self.assertNotEqual(result.returncode, 0)


# ---------------------------------------------------------------------------
# Phase 11 — Agent-Agnostic Bootstrap tests
# ---------------------------------------------------------------------------

class CerebroInitScaffoldTests(unittest.TestCase):
    """Phase 11: cerebro init creates multi-agent scaffold (no CLAUDE.md)."""

    def _cli(self, cwd: Path, *args: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, "-m", "cli.main", *args],
            cwd=cwd,
            capture_output=True,
            text=True,
        )

    def test_init_creates_state_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._cli(root, "init")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".cerebro" / "state.json").exists())

    def test_init_creates_runtime_db(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._cli(root, "init")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / ".cerebro" / "runtime.db").exists())

    def test_init_creates_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            result = self._cli(root, "init")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue((root / "AGENTS.md").exists())

    def test_init_does_not_create_claude_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            self.assertFalse((root / "CLAUDE.md").exists(),
                             "cerebro init must never create CLAUDE.md in a managed project")

    def test_init_creates_observation_center_toml(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            obs = root / "docs" / "operations" / "observation_center.toml"
            self.assertTrue(obs.exists())

    def test_init_creates_system_state_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            self.assertTrue((root / "docs" / "operations" / "SYSTEM_STATE.md").exists())

    def test_init_creates_opportunity_map_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            self.assertTrue((root / "docs" / "operations" / "OPPORTUNITY_MAP.md").exists())

    def test_init_observation_center_authority_starts_with_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            obs_text = (root / "docs" / "operations" / "observation_center.toml").read_text(encoding="utf-8")
            data = tomllib.loads(obs_text)
            authority = data["center"].get("authority_order", "")
            self.assertTrue(
                authority.startswith("AGENTS.md"),
                f"authority_order must start with AGENTS.md, got: {authority!r}",
            )

    def test_init_agents_md_does_not_require_claude(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._cli(root, "init")
            content = (root / "AGENTS.md").read_text(encoding="utf-8").lower()
            forbidden_phrases = [
                "claude is required",
                "requires claude",
                "must use claude",
                "only works with claude",
            ]
            for phrase in forbidden_phrases:
                self.assertNotIn(phrase, content,
                                 f"AGENTS.md template must not contain Claude-mandatory language: {phrase!r}")

    def test_init_preserves_existing_agents_md(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            original = "# My custom AGENTS.md\n"
            (root / "AGENTS.md").write_text(original, encoding="utf-8")
            self._cli(root, "init")
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), original,
                             "cerebro init must not overwrite existing AGENTS.md")

    def test_init_fails_on_already_initialized_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            r1 = self._cli(root, "init")
            self.assertEqual(r1.returncode, 0)
            r2 = self._cli(root, "init")
            self.assertNotEqual(r2.returncode, 0)
            self.assertIn("repair-scaffold", r2.stdout + r2.stderr)

    def test_repair_scaffold_creates_missing_artefacts(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            # Manually create state.json so fresh init would fail
            run_init(root, None)
            # Remove AGENTS.md to simulate partial scaffold
            agents_md = root / "AGENTS.md"
            agents_md.unlink()
            result = self._cli(root, "init", "--repair-scaffold")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertTrue(agents_md.exists())

    def test_repair_scaffold_does_not_overwrite_existing_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_init(root, None)
            original = "# preserved\n"
            (root / "AGENTS.md").write_text(original, encoding="utf-8")
            self._cli(root, "init", "--repair-scaffold")
            self.assertEqual((root / "AGENTS.md").read_text(encoding="utf-8"), original)

    def test_repair_scaffold_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run_init(root, None)
            r1 = self._cli(root, "init", "--repair-scaffold")
            r2 = self._cli(root, "init", "--repair-scaffold")
            self.assertEqual(r1.returncode, 0)
            self.assertEqual(r2.returncode, 0)


class ProjectRootWalkUpTests(unittest.TestCase):
    """Phase 11: walk-up root detection."""

    def test_walkup_finds_cerebro_dir_from_subdir(self) -> None:
        from cli.project_root import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".cerebro").mkdir()
            subdir = root / "src" / "nested"
            subdir.mkdir(parents=True)
            result = find_project_root(start=subdir)
            self.assertEqual(result.path, root.resolve())
            self.assertEqual(result.source, "cerebro")

    def test_walkup_finds_git_when_no_cerebro(self) -> None:
        from cli.project_root import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            subdir = root / "deep" / "dir"
            subdir.mkdir(parents=True)
            result = find_project_root(start=subdir)
            self.assertEqual(result.path, root.resolve())
            self.assertEqual(result.source, "git")

    def test_walk_up_false_always_returns_cwd(self) -> None:
        from cli.project_root import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            start = Path(tmp) / "subdir"
            start.mkdir()
            result = find_project_root(start=start, walk_up=False)
            self.assertEqual(result.path, start.resolve())
            self.assertEqual(result.source, "cwd")

    def test_explicit_project_root_overrides_walkup(self) -> None:
        from cli.project_root import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            explicit = root / "explicit_root"
            explicit.mkdir()
            # Even if .cerebro exists at root, explicit wins
            (root / ".cerebro").mkdir()
            result = find_project_root(explicit=str(explicit), start=root)
            self.assertEqual(result.path, explicit.resolve())
            self.assertEqual(result.source, "explicit")

    def test_cerebro_marker_takes_priority_over_git(self) -> None:
        from cli.project_root import find_project_root
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / ".git").mkdir()
            inner = root / "subproject"
            inner.mkdir()
            (inner / ".cerebro").mkdir()
            result = find_project_root(start=inner / "src")
            (inner / "src").mkdir(exist_ok=True)
            result = find_project_root(start=inner / "src")
            self.assertEqual(result.path, inner.resolve())
            self.assertEqual(result.source, "cerebro")
