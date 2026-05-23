"""Permanent adversarial regression layer for runtime corruption and stress scenarios."""

from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.analyze import run_analyze
from cli.commands.checkpoint import run_checkpoint
from cli.commands.init import run_init
from core.schema import build_initial_state
from core.state_store import StateStore
from extensions.handoff_export.exporter import export_handoff_markdown
from extensions.impact_export.exporter import export_impact_markdown
from extensions.return_map_export.exporter import export_return_map_markdown
from extensions.sources_export.exporter import export_sources_markdown
from extensions.status_export.exporter import export_status_markdown
from extensions.validation_export.exporter import export_validation_markdown


class AdversarialRevalidationTests(unittest.TestCase):
    def test_validate_reports_state_corruption_variants_explicitly(self) -> None:
        cases = [
            (
                "extra_root_key",
                lambda state: state.update({"extra": 1}),
                {"state_invalid_schema", "invalid_root_keys"},
            ),
            (
                "missing_checkpoint",
                lambda state: state.pop("checkpoint"),
                {"state_invalid_schema", "invalid_root_keys", "invalid_checkpoint"},
            ),
            (
                "bool_revision",
                lambda state: state.__setitem__("revision", True),
                {"state_invalid_schema", "invalid_revision"},
            ),
            (
                "goal_above_limit",
                lambda state: state["checkpoint"].__setitem__("goal", "x" * 201),
                {"state_invalid_schema", "invalid_checkpoint_field"},
            ),
        ]

        for name, mutate, expected_codes in cases:
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    run_init(root, None)
                    store = StateStore(root)
                    corrupted = build_initial_state()
                    mutate(corrupted)
                    store.state_path.write_text(json.dumps(corrupted, indent=2), encoding="utf-8")

                    result = store.validate_state()

                    self.assertFalse(result["ok"])
                    codes = {item["code"] for item in result["errors"]}
                    self.assertTrue(expected_codes.issubset(codes))

    def test_validate_reports_session_corruption_variants_explicitly(self) -> None:
        cases = [
            (
                "extra_session_key",
                {
                    "session_id": "session-test",
                    "opened_at": "2026-04-11T00:00:00+00:00",
                    "actor": "alice",
                    "based_on_revision": 0,
                    "owner_claim_id": "claim-test",
                    "extra": "x",
                },
                {"session_invalid_schema", "invalid_session_keys"},
            ),
            (
                "bool_based_on_revision",
                {
                    "session_id": "session-test",
                    "opened_at": "2026-04-11T00:00:00+00:00",
                    "actor": "alice",
                    "based_on_revision": True,
                    "owner_claim_id": "claim-test",
                },
                {"session_invalid_schema", "invalid_session_based_on_revision"},
            ),
        ]

        for name, payload, expected_codes in cases:
            with self.subTest(case=name):
                with tempfile.TemporaryDirectory() as tmp_dir:
                    root = Path(tmp_dir)
                    run_init(root, None)
                    session_path = root / ".cerebro" / "session.local.json"
                    session_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

                    result = StateStore(root).validate_state()

                    self.assertFalse(result["ok"])
                    codes = {item["code"] for item in result["errors"]}
                    self.assertTrue(expected_codes.issubset(codes))

    def test_analyze_blocks_on_invalid_session_json_and_exports_follow_failed_validation(self) -> None:
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
            session_path = root / ".cerebro" / "session.local.json"
            session_path.write_text("{invalid", encoding="utf-8")
            before_revision = store.read_snapshot().revision
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_analyze(root, type("Args", (), {"actor": "alice"}))

            output = stream.getvalue()
            snapshot = store.read_snapshot()
            self.assertEqual(exit_code, 1)
            self.assertIn("analysis_blocked", output)
            self.assertIn("session_invalid_json", output)
            self.assertEqual(snapshot.revision, before_revision)
            self.assertEqual(snapshot.last_validation.result, "fail")
            self.assertIn("Validation: fail", export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Validation: fail", export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Validation: fail", export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Validation: fail", export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Validation: fail", export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Session file: present", export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Session file: present", export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Session file: present", export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn("- Session file: present", export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
            self.assertIn(
                "- Validation: fail",
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
            )
            self.assertIn(
                "- Session file: present",
                export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
            )

    def test_repeated_runtime_cycle_remains_stable(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            session_token: str | None = None
            for iteration in range(3):
                args = type(
                    "Args",
                    (),
                    {
                        "goal": f"Goal {iteration}",
                        "summary": f"Summary {iteration}",
                        "next_step": f"Next {iteration}",
                        "constraint": [f"Constraint {iteration}"],
                        "actor": "alice",
                        "session_token": session_token,
                    },
                )
                checkpoint_exit = run_checkpoint(root, args)
                self.assertEqual(checkpoint_exit, 0)

                before = store.read_snapshot()
                stream = io.StringIO()
                with redirect_stdout(stream):
                    analyze_exit = run_analyze(root, type("Args", (), {"actor": "alice", "emit_session_token": True}))

                output = stream.getvalue()
                session_token = next(
                    line.split(": ", 1)[1]
                    for line in output.splitlines()
                    if line.startswith("session_token: ")
                )
                after = store.read_snapshot()
                self.assertEqual(analyze_exit, 0)
                self.assertEqual(after.revision, before.revision)
                self.assertEqual(after.checkpoint, before.checkpoint)
                self.assertEqual(after.sources, before.sources)
                self.assertIn(f"goal: Goal {iteration}", output)
                self.assertIn("validation: ok", output)
                self.assertIn("session_owner_proof: external_claim", output)
                self.assertIn("Goal", export_handoff_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
                self.assertIn("# Impact", export_impact_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
                self.assertIn("- Registered sources: 1", export_sources_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
                self.assertIn("- Validation: ok", export_status_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
                self.assertIn("- Validation: ok", export_validation_markdown(root, exported_at="2026-04-11T12:00:00+00:00"))
                self.assertIn(
                    f"- Goal: Goal {iteration}",
                    export_return_map_markdown(root, exported_at="2026-04-11T12:00:00+00:00"),
                )
