from __future__ import annotations

import hashlib
import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

from cli.commands.init import run_init
from cli.commands.plan import run_plan
from cli.commands.apply import run_apply
from cli.commands.approve import run_approve
from cli.commands.verify import run_verify
from cli.commands.status_export import run_status_export
from core.state_store import StateStore
from extensions.status_export.exporter import (
    StatusExportError,
    export_status_json,
    export_status_markdown,
    write_status_markdown,
)
from tests.runtime_fixtures import seed_registered_source

REPO_ROOT = Path(__file__).resolve().parents[1]


class StatusExportTests(unittest.TestCase):
    def test_export_contains_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("secret-content", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship fix",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Open tracked.txt and continue.",
                    "constraints": ["Do not change API"],
                }
            )
            store.validate_state()
            store.open_session("alice")

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Status", output)
            self.assertIn("- Exported at: 2026-04-11T12:00:00+00:00", output)
            self.assertIn("- Validation: ok", output)
            self.assertIn("- Validation basis: persisted canonical record only; exports do not rerun validate", output)
            self.assertIn("- Risk: low", output)
            self.assertIn("- Session file: present", output)
            self.assertIn("- Sources: 1", output)
            self.assertIn("- Revision: 2", output)
            self.assertIn("- Updated at:", output)
            self.assertIn("- Validated at:", output)
            self.assertIn("## Runtime", output)
            self.assertIn("- Plan status: idle", output)
            self.assertIn("- Current task id: none", output)
            self.assertIn("- Trace status: healthy", output)
            self.assertIn("- Trace integrity: reliable", output)
            self.assertIn("- Trace durability: balanced", output)
            self.assertIn("## Runtime Diagnostics", output)
            self.assertIn("## Recommended Next Actions", output)
            self.assertIn("## Prioritized Tasks", output)
            self.assertIn("## Flow Control", output)
            self.assertIn("- no_active_flow_controls", output)
            self.assertIn("## Recent Runtime Events", output)
            self.assertIn("- no_runtime_events_recorded", output)

    def test_export_json_contains_expected_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("secret-content", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Ship fix",
                    "summary": "Checkpoint is ready.",
                    "next_step": "Open tracked.txt and continue.",
                    "constraints": ["Do not change API"],
                }
            )
            store.validate_state()
            store.open_session("alice")

            payload = export_status_json(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["export_kind"], "status")
            self.assertEqual(payload["exported_at"], "2026-04-11T12:00:00+00:00")
            self.assertEqual(payload["revision"], 2)
            self.assertEqual(len(payload["root_sha256"]), 64)
            self.assertEqual(payload["payload"]["validation"]["result"], "ok")
            self.assertEqual(payload["payload"]["validation"]["risk"], "low")
            self.assertEqual(payload["payload"]["session_file"], "present")
            self.assertEqual(payload["payload"]["sources_count"], 1)
            self.assertEqual(payload["payload"]["runtime"]["plan_status"], "idle")
            self.assertEqual(payload["payload"]["runtime"]["current_task_id"], "none")
            self.assertEqual(payload["payload"]["runtime"]["registered_commands"], 0)
            self.assertEqual(payload["payload"]["runtime"]["pending_verification_actions"], 0)
            self.assertEqual(payload["payload"]["trace"]["trace_status"], "healthy")
            self.assertEqual(payload["payload"]["trace"]["trace_integrity"], "reliable")
            self.assertEqual(payload["payload"]["flow_control"]["approval_lines"], [])
            self.assertEqual(payload["payload"]["flow_control"]["batch_lines"], [])
            self.assertEqual(payload["payload"]["recent_runtime_events"], [])

    def test_export_flags_trace_degraded_and_invalidates_fragile_metrics(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            state = store.load_state()
            state["agent_runtime"]["audit"]["trace_status"] = "degraded"
            state["agent_runtime"]["audit"]["trace_integrity"] = "partial"
            state["agent_runtime"]["audit"]["last_trace_error_at"] = "2026-04-13T10:00:00+00:00"
            state["agent_runtime"]["audit"]["last_trace_error"] = "plan-abcd1234:000003: disk full"
            store.save_state(state, expected_revision=state["revision"])

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- Trace status: degraded", output)
            self.assertIn("- Trace integrity: partial", output)
            self.assertIn("- trace_degraded", output)
            self.assertIn("- runtime_diagnostics_partial", output)
            self.assertIn("- no_task_assessments_available", output)
            self.assertIn("- Recent failure pressure: n/a (trace partial)", output)
            self.assertIn(
                "restore trace append health before relying on event-derived diagnostics or cycle pressure",
                output,
            )

    def test_export_reports_fail_and_high_risk_for_inconsistent_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()
            tracked.write_text("changed", encoding="utf-8")
            store.validate_state()

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- Validation: fail", output)
            self.assertIn("- Validation basis: persisted canonical record only; exports do not rerun validate", output)
            self.assertIn("- Risk: high", output)
            self.assertIn("source_hash_mismatch", output)
            self.assertIn("- Session file: absent", output)

    def test_export_does_not_include_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("TOP SECRET BODY", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertNotIn("TOP SECRET BODY", output)
            self.assertNotIn("Ship fix", output)
            self.assertNotIn("Checkpoint is ready.", output)

    def test_export_surfaces_runtime_diagnostics_and_memory_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Observe runtime",
                        "summary": "Capture runtime diagnostics.",
                        "task": ["Task 1"],
                        "verify_command": ["python -c import sys; sys.exit(1)"],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": [],
                    },
                ),
            )
            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
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
                run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- Plan status: running", output)
            self.assertIn("- Current task id: none", output)
            self.assertIn("- Pending verification actions: 1", output)
            self.assertIn("- Memory notes: 1", output)
            self.assertIn("- verification_failed", output)
            self.assertIn("- actions_pending_verification", output)
            self.assertIn("run `cerebro verify` before applying additional workspace mutations", output)
            self.assertIn("fix the failing verification command or rollback the pending action set", output)
            self.assertIn("## Task Decision", output)
            self.assertIn("- Selected task: none", output)
            self.assertIn("## Recent Memory Notes", output)
            self.assertIn("[pitfall] verification failed for commands: cmd-001", output)
            self.assertIn("## Recent Runtime Events", output)
            self.assertIn(":: plan_updated", output)
            self.assertIn(":: action_recorded | action=act-create | status=applied | target=artifact.txt", output)
            self.assertIn(":: verification_completed | status=failed", output)

    def test_export_json_surfaces_runtime_diagnostics_and_memory_notes(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Observe runtime",
                        "summary": "Capture runtime diagnostics.",
                        "task": ["Task 1"],
                        "verify_command": ["python -c import sys; sys.exit(1)"],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": [],
                    },
                ),
            )
            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
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
                run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            payload = export_status_json(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(payload["payload"]["runtime"]["plan_status"], "running")
            self.assertEqual(payload["payload"]["runtime"]["pending_verification_actions"], 1)
            self.assertEqual(payload["payload"]["runtime"]["memory_notes"], 1)
            self.assertIn("verification_failed", payload["payload"]["runtime_diagnostics"])
            self.assertIn("actions_pending_verification", payload["payload"]["runtime_diagnostics"])
            self.assertIn(
                "run `cerebro verify` before applying additional workspace mutations",
                payload["payload"]["recommended_next_actions"],
            )
            self.assertEqual(payload["payload"]["task_decision"]["selected_task_id"], None)
            self.assertEqual(len(payload["payload"]["recent_memory_notes"]), 1)
            self.assertEqual(payload["payload"]["recent_memory_notes"][0]["kind"], "pitfall")
            event_names = [item["event"] for item in payload["payload"]["recent_runtime_events"]]
            self.assertIn("plan_updated", event_names)
            self.assertIn("action_recorded", event_names)
            self.assertIn("verification_completed", event_names)

    def test_export_highlights_pending_approvals_and_recent_batches(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Control flow",
                        "summary": "Observe approvals and batches.",
                        "task": ["Task 1"],
                        "verify_command": [],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": ["fs.write_patch"],
                    },
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
            self.assertEqual(
                run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {"action_file": [str(create_file), str(patch_file)], "task_id": "", "batch_id": "batch-001"},
                    ),
                ),
                1,
            )

            pending_output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            self.assertIn("## Flow Control", pending_output)
            self.assertIn("pending approval apr-001: fs.write_patch -> draft.txt", pending_output)
            self.assertNotIn("recent batch batch-001:", pending_output)

            self.assertEqual(
                run_approve(root, type("Args", (), {"approval_id": "apr-001", "decision": "approved"})),
                0,
            )
            self.assertEqual(
                run_apply(
                    root,
                    type(
                        "Args",
                        (),
                        {"action_file": [str(create_file), str(patch_file)], "task_id": "", "batch_id": "batch-001"},
                    ),
                ),
                0,
            )

            resolved_output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            self.assertIn("recent approval approved apr-001: fs.write_patch -> draft.txt", resolved_output)
            self.assertIn("recent batch batch-001: actions=2, latest_status=applied", resolved_output)

    def test_export_flags_incomplete_required_verification_coverage(self) -> None:
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
                    "summary": "Partial verify remains diagnostic.",
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
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": ["cmd-001"]})), 1)

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- actions_pending_verification", output)
            self.assertIn("- verification_required_coverage_incomplete", output)
            self.assertIn("run the remaining required verification commands before treating the current delta as closed", output)

    def test_export_surfaces_parallel_approach_consolidation_from_event_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a", "approach-c"],
                    "comparison_basis": ["lower rollback cost", "stronger verify coverage"],
                    "decision": "selected approach B after comparing reversibility and verification cost",
                    "comparison_event_ids": ["evt-001", "evt-002"],
                }
            )

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("## Parallel Approach Consolidations", output)
            self.assertIn(
                "- task task-019: id=",
                output,
            )
            self.assertIn(
                "winner=approach-b (approach B); supersedes=root; compared=approach-a, approach-b, approach-c; rejected=approach-a, approach-c",
                output,
            )
            self.assertIn("basis: lower rollback cost; stronger verify coverage", output)
            self.assertIn("decision: selected approach B after comparing reversibility and verification cost", output)
            self.assertIn("compared events: evt-001, evt-002", output)

    def test_export_shows_only_latest_valid_consolidation_per_subject(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["lower execution cost"],
                    "decision": "first decision",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-019",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["stronger verify coverage"],
                    "decision": "latest valid decision",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            latest_event = store.read_recent_events(limit=1)[0]
            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                handle.write(
                    json.dumps(
                        {
                            "recorded_at": "2026-04-13T10:00:00+00:00",
                            "event": "parallel_approach_consolidated",
                            "subject_kind": "task",
                            "subject_id": "task-019",
                            "compared_approach_ids": ["approach-a", "approach-b", "approach-c"],
                            "winner_id": "approach-c",
                            "winner_label": "spoofed",
                            "rejected_approach_ids": ["approach-a"],
                            "comparison_basis": ["invalid"],
                            "decision": "corrupted event",
                            "comparison_event_ids": ["evt-003"],
                        }
                    )
                )
                handle.write("\n")

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn(f"id={latest_event['consolidation_id']}", output)
            self.assertIn(f"supersedes={first_event['consolidation_id']}", output)
            self.assertIn("winner=approach-b (approach B)", output)
            self.assertIn("decision: latest valid decision", output)
            self.assertNotIn("winner=approach-c", output)
            self.assertNotIn("decision: first decision", output)
            self.assertIn("invalid_parallel_approach_consolidation_record | subject=task:task-019", output)

    def test_export_marks_stale_parallel_approach_consolidation_record(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-021",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["first decision"],
                    "decision": "first decision",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-021",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["rollback posture improved"],
                    "decision": "latest valid decision",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            latest_event = store.read_recent_events(limit=1)[0]
            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                replayed = dict(first_event)
                replayed["recorded_at"] = "2026-04-13T10:00:00+00:00"
                handle.write(json.dumps(replayed))
                handle.write("\n")

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn(f"id={latest_event['consolidation_id']}", output)
            self.assertIn("winner=approach-b (approach B)", output)
            self.assertNotIn("winner=approach-a (approach A)", output)
            self.assertIn(
                f"stale_parallel_approach_consolidation_record | subject=task:task-021 | consolidation={first_event['consolidation_id']} | target=current={latest_event['consolidation_id']}",
                output,
            )

    def test_export_fail_closes_on_divergent_duplicate_consolidation_id(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-022",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-a",
                    "winner_label": "approach A",
                    "rejected_approach_ids": ["approach-b"],
                    "comparison_basis": ["first decision"],
                    "decision": "first decision",
                    "comparison_event_ids": ["evt-001"],
                }
            )
            first_event = store.read_recent_events(limit=1)[0]
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-022",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["second decision"],
                    "decision": "latest valid decision",
                    "comparison_event_ids": ["evt-002"],
                }
            )
            with store.events_path.open("a", encoding="utf-8", newline="\n") as handle:
                corrupted = dict(first_event)
                corrupted["recorded_at"] = "2026-04-13T10:00:00+00:00"
                corrupted["decision"] = "corrupted replay"
                corrupted["comparison_event_ids"] = ["evt-corrupt"]
                handle.write(json.dumps(corrupted))
                handle.write("\n")

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn(
                f"stale_parallel_approach_consolidation_record | subject=task:task-022 | consolidation={first_event['consolidation_id']} | target=current=none",
                output,
            )
            self.assertNotIn("winner=approach-b (approach B)", output)

    def test_export_surfaces_verified_success_memory_and_event(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Learn success",
                        "summary": "Capture successful decisions.",
                        "task": ["Task 1"],
                        "verify_command": ["python -c print('ok')"],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": [],
                    },
                ),
            )
            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
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

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("## Recent Memory Notes", output)
            self.assertIn("[workflow] first verified success for subject", output)
            self.assertIn("context:", output)
            self.assertIn("reason: verify passed on pending workspace delta", output)
            self.assertIn("## Recent Runtime Events", output)
            self.assertIn(":: decision_success | task=task-001", output)

    def test_export_detects_repeated_verification_failures(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Detect stagnation",
                        "summary": "Observe repeated verify failures.",
                        "task": ["Task 1"],
                        "verify_command": ["python -c import sys; sys.exit(1)"],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": [],
                    },
                ),
            )
            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
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
                run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 1)

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- repeated_verification_failures", output)
            self.assertIn(
                "stop retrying the same verification path; replan, fix the command, or rollback the pending action set",
                output,
            )
            self.assertIn("## Cycle Cost", output)
            self.assertIn("- Actions per completed task: n/a (no completed tasks yet)", output)
            self.assertIn("- cycle_cost_rising_without_closure", output)
            self.assertIn(
                "reduce scope or replan before adding more actions to a cycle that is not closing",
                output,
            )

    def test_export_reports_actions_per_completed_task_after_verified_closure(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            run_plan(
                root,
                type(
                    "Args",
                    (),
                    {
                        "goal": "Close a cycle",
                        "summary": "Measure actions per completed task.",
                        "task": ["Task 1"],
                        "verify_command": ["python -c print('ok')"],
                        "autonomy_level": "A2",
                        "protect_path": [],
                        "blocked_command": [],
                        "approval_required_kind": [],
                    },
                ),
            )
            action_file = root / "action.json"
            action_file.write_text(
                json.dumps(
                    {
                        "id": "act-create",
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
                run_apply(root, type("Args", (), {"action_file": str(action_file), "task_id": "", "batch_id": ""})),
                0,
            )
            self.assertEqual(run_verify(root, type("Args", (), {"command_id": []})), 0)

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("## Cycle Cost", output)
            self.assertIn("- Actions: total=1, applied=1, failed=0, blocked=0, rolled_back=0", output)
            self.assertIn("- Task closures: completed=1, terminal=1, active=0", output)
            self.assertIn("- Actions per completed task: 1.00", output)
            self.assertIn("- Recent failure pressure: verification_failed=0, retry_blocked=0, apply_blocked=0, verify_blocked=0", output)

    def test_export_lists_task_priority_with_evidence(self) -> None:
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
                    "goal": "Priority",
                    "summary": "Show prioritized tasks.",
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

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            recent_events = store.read_recent_events(limit=5)
            plan_event_id = next(item["event_id"] for item in recent_events if item.get("event") == "plan_updated")

            self.assertIn("## Prioritized Tasks", output)
            self.assertIn("- task-002: status=ready", output)
            self.assertIn("- Selected task: task-002", output)
            self.assertIn("Evidence: working set is bounded to 1 path(s)", output)
            self.assertIn(f"Evidence events: {plan_event_id}", output)

    def test_export_flags_task_selection_replay_mismatch_even_with_partial_trace(self) -> None:
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
                    "summary": "Detect stale selection.",
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
            state = store.load_state()
            state["agent_runtime"]["plan"]["current_task_id"] = "task-001"
            state["agent_runtime"]["audit"]["trace_integrity"] = "partial"
            store.save_state(state, expected_revision=updated["revision"])

            output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- task_selection_replay_mismatch", output)
            self.assertIn("- trace_integrity_partial", output)
            self.assertIn("## Decision Replay", output)
            self.assertIn("- Replay status: mismatch", output)
            self.assertIn("- Current task id: task-001", output)
            self.assertIn("- Derived task id: task-002", output)

    def test_export_treats_lightweight_plan_without_technical_diagnostics(self) -> None:
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
                    "goal": "Rotina semanal",
                    "summary": "Plano leve de organizacao pessoal.",
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

            output = export_status_markdown(root, exported_at="2026-04-13T12:00:00+00:00")

            self.assertNotIn("plan_has_no_registered_verification_commands", output)
            self.assertNotIn("tasks_missing_acceptance_criteria", output)
            self.assertNotIn("tasks_missing_working_set", output)
            self.assertIn("- Workload modes: light=2, moderate=0, heavy=0", output)
            self.assertIn("- task-001: status=ready, mode=light, unit=state_only", output)
            self.assertIn("- Work profile: mode=light, unit=state_only", output)

    def test_export_reports_heavy_governed_work_profile_for_technical_task(self) -> None:
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
                    "goal": "Runtime patch",
                    "summary": "Governed technical work.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Patch exporter",
                            "status": "ready",
                            "details": "Patch exporter",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
                            "acceptance_criteria": ["python -m unittest passes"],
                            "action_ids": [],
                        }
                    ],
                    "command_registry": [
                        {
                            "id": "cmd-001",
                            "argv": ["python", "-m", "unittest", "discover", "-s", "tests", "-v"],
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

            output = export_status_markdown(root, exported_at="2026-04-13T12:00:00+00:00")

            self.assertIn("- Workload modes: light=0, moderate=0, heavy=1", output)
            self.assertIn("- task-001: status=ready, mode=heavy, unit=governed_execution", output)
            self.assertIn("- Work profile: mode=heavy, unit=governed_execution", output)

    def test_export_is_stable_for_same_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()

            first = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")
            second = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(first, second)

    def test_export_fails_explicitly_when_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaises(StatusExportError):
                export_status_markdown(root)

            with self.assertRaises(StatusExportError):
                export_status_json(root)

    def test_export_degrades_gracefully_when_task_assessments_fail(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.validate_state()

            with patch(
                "extensions.status_export.exporter._load_task_assessments",
                side_effect=StatusExportError("synthetic assessment failure"),
            ):
                output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("# Status", output)
            self.assertIn("- Validation: ok", output)
            self.assertIn("- task_assessment_surface_unavailable", output)
            self.assertIn("- task_assessments_unavailable", output)

    def test_export_does_not_mispublish_stale_or_current_none_when_consolidation_surface_fails(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.record_parallel_approach_consolidation(
                {
                    "subject_kind": "task",
                    "subject_id": "task-099",
                    "compared_approach_ids": ["approach-a", "approach-b"],
                    "winner_id": "approach-b",
                    "winner_label": "approach B",
                    "rejected_approach_ids": ["approach-a"],
                    "comparison_basis": ["benchmark"],
                    "decision": "picked approach B",
                    "comparison_event_ids": ["evt-001"],
                }
            )

            with patch(
                "extensions.status_export.exporter._load_parallel_consolidation_view",
                side_effect=StatusExportError("synthetic consolidation failure"),
            ):
                output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertIn("- parallel_consolidation_surface_unavailable", output)
            self.assertIn(":: parallel_approach_consolidated | subject=task:task-099", output)
            self.assertNotIn("stale_parallel_approach_consolidation_record", output)
            self.assertNotIn("target=current=none", output)

    def test_export_reuses_loaded_runtime_inputs_for_task_assessments(self) -> None:
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
                    "goal": "Priority",
                    "summary": "Show prioritized tasks.",
                    "tasks": [
                        {
                            "id": "task-001",
                            "title": "Scoped task",
                            "status": "ready",
                            "details": "Scoped task",
                            "depends_on": [],
                            "working_set": ["tracked.txt"],
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

            calls: list[dict[str, object]] = []
            original = StateStore.read_task_assessments

            def spy(self, event_limit: int = 20, *, agent_runtime=None, recent_events=None):
                calls.append(
                    {
                        "event_limit": event_limit,
                        "agent_runtime": agent_runtime,
                        "recent_events": recent_events,
                    }
                )
                return original(
                    self,
                    event_limit=event_limit,
                    agent_runtime=agent_runtime,
                    recent_events=recent_events,
                )

            with (
                patch.object(StateStore, "read_task_assessments", new=spy),
                patch.object(StateStore, "read_agent_runtime", side_effect=AssertionError("unexpected runtime reload")),
            ):
                output = export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            self.assertEqual(len(calls), 1)
            self.assertIsInstance(calls[0]["agent_runtime"], dict)
            self.assertIsInstance(calls[0]["recent_events"], tuple)
            self.assertIn("## Prioritized Tasks", output)
            self.assertIn("- task-001: status=ready", output)

    def test_export_does_not_change_revision_or_runtime_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            store.validate_state()
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00")

            after_state = store.state_path.read_text(encoding="utf-8")
            after_session = store.session_path.read_text(encoding="utf-8")
            after_revision = store.read_snapshot().revision
            self.assertEqual(before_revision, after_revision)
            self.assertEqual(before_state, after_state)
            self.assertEqual(before_session, after_session)

    def test_export_rejects_runtime_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_registered_source(root)
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/state.json")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/session.local.json")

            with self.assertRaises(StatusExportError):
                write_status_markdown(root, ".cerebro/status.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_status_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Status", output)
            self.assertIn("- Validation:", output)

    def test_cli_exports_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_status_export(root, type("Args", (), {"out": None, "format": "json"}))

            payload = json.loads(stream.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["export_kind"], "status")

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            args = type("Args", (), {"out": "status.md"})

            exit_code = run_status_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "status.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Status", content)

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store = StateStore(root)
            store.validate_state()
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "status-export"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("# Status", result.stdout)
            self.assertIn("- Validation:", result.stdout)
