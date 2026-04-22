from __future__ import annotations

import io
import json
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.context_index_export import run_context_index_export
from cli.commands.init import run_init
from core.state_store import StateStore
from extensions.context_index_export.exporter import (
    ContextIndexExportError,
    export_context_index_json,
    export_context_index_markdown,
    write_context_index_markdown,
)
from tests.runtime_fixtures import seed_checkpointed_runtime, seed_registered_source

REPO_ROOT = Path(__file__).resolve().parents[1]


class ContextIndexExportTests(unittest.TestCase):
    def test_export_contains_expected_fields_and_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tracked.txt").write_text("secret-content", encoding="utf-8")
            docs_dir = root / "docs"
            docs_dir.mkdir()
            (docs_dir / "guide.md").write_text("guide content", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt", "docs/guide.md"])
            state = store.load_state()
            for item in state["sources"]:
                item["role"] = "reference" if item["path"] == "docs/guide.md" else "primary"
            store.save_state(state)
            store.update_checkpoint(
                {
                    "goal": "Ship fix",
                    "summary": "Keep tracked.txt stable.",
                    "next_step": "Open docs/guide.md and then revisit tracked.txt.",
                    "constraints": ["Do not change API"],
                }
            )
            store.validate_state()
            store.open_session("alice")

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("# Context Index", output)
            self.assertIn("- Exported at: 2026-04-12T12:00:00+00:00", output)
            self.assertIn("- Validation: ok", output)
            self.assertIn("- Session file: present", output)
            self.assertIn("- Registered sources: 2", output)
            self.assertIn("- Primary sources: 1", output)
            self.assertIn("- Reference sources: 1", output)
            self.assertIn("- Source families: 2", output)
            self.assertIn("- Checkpoint anchors: 2", output)
            self.assertIn("### (root)", output)
            self.assertIn("- tracked.txt [primary]", output)
            self.assertIn("### docs", output)
            self.assertIn("- docs/guide.md [reference]", output)
            self.assertIn("- tracked.txt [primary] reasons: basename", output)
            self.assertIn("- docs/guide.md [reference] reasons: path", output)
            self.assertIn("- Goal: Ship fix", output)
            self.assertIn("- Next step: Open docs/guide.md and then revisit tracked.txt.", output)

    def test_export_json_contains_expected_fields_and_groups(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "tracked.txt").write_text("secret-content", encoding="utf-8")
            docs_dir = root / "docs"
            docs_dir.mkdir()
            (docs_dir / "guide.md").write_text("guide content", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt", "docs/guide.md"])
            state = store.load_state()
            for item in state["sources"]:
                item["role"] = "reference" if item["path"] == "docs/guide.md" else "primary"
            store.save_state(state)
            store.update_checkpoint(
                {
                    "goal": "Ship fix",
                    "summary": "Keep tracked.txt stable.",
                    "next_step": "Open docs/guide.md and then revisit tracked.txt.",
                    "constraints": ["Do not change API"],
                }
            )
            store.validate_state()
            store.open_session("alice")

            payload = export_context_index_json(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertEqual(payload["schema_version"], "1")
            self.assertEqual(payload["export_kind"], "context_index")
            self.assertEqual(payload["exported_at"], "2026-04-12T12:00:00+00:00")
            self.assertEqual(payload["revision"], 2)
            self.assertEqual(len(payload["root_sha256"]), 64)
            self.assertEqual(payload["payload"]["validation"], "ok")
            self.assertEqual(payload["payload"]["session_file"], "present")
            self.assertEqual(payload["payload"]["registered_sources"], 2)
            self.assertEqual(payload["payload"]["primary_sources"], 1)
            self.assertEqual(payload["payload"]["reference_sources"], 1)
            self.assertEqual(payload["payload"]["source_families"], 2)
            self.assertEqual(payload["payload"]["checkpoint_anchors"], 2)
            self.assertEqual(
                payload["payload"]["checkpoint"],
                {
                    "goal": "Ship fix",
                    "summary": "Keep tracked.txt stable.",
                    "next_step": "Open docs/guide.md and then revisit tracked.txt.",
                    "constraints": ["Do not change API"],
                },
            )
            families = {
                item["family"]: item for item in payload["payload"]["families"]
            }
            self.assertEqual(families["(root)"]["count"], 1)
            self.assertEqual(
                families["(root)"]["sources"],
                [{"path": "tracked.txt", "role": "primary"}],
            )
            self.assertEqual(families["docs"]["count"], 1)
            self.assertEqual(
                families["docs"]["sources"],
                [{"path": "docs/guide.md", "role": "reference"}],
            )
            anchors = {
                item["path"]: item for item in payload["payload"]["continuity_anchors"]
            }
            self.assertEqual(anchors["tracked.txt"]["reasons"], ["basename"])
            self.assertEqual(anchors["docs/guide.md"]["reasons"], ["path"])

    def test_export_does_not_include_source_contents(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("TOP SECRET BODY", encoding="utf-8")
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

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertNotIn("TOP SECRET BODY", output)

    def test_export_flattens_multiline_checkpoint_fields(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal\n## injected",
                    "summary": "Summary\n## injected",
                    "next_step": "Next\n- injected",
                    "constraints": ["line one\n## injected", "line two\n- injected"],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("- Goal: Goal ## injected", output)
            self.assertIn("- Summary: Summary ## injected", output)
            self.assertIn("- Next step: Next - injected", output)
            self.assertIn("- line one ## injected", output)
            self.assertIn("- line two - injected", output)
            self.assertNotIn("\n## injected\n", output)

    def test_export_does_not_anchor_basename_inside_larger_filename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "api.md"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["api.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Look at myapi.md only.",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- api.md [primary] reasons:", output)

    def test_export_does_not_anchor_basename_inside_larger_mixed_case_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            tracked = root / "Guide.md"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["Guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Use AGuide.mdX only.",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- Guide.md [primary] reasons:", output)

    def test_export_does_not_anchor_path_inside_larger_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            tracked = docs_dir / "guide.md"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["docs/guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Look at src/docs/guide.md only.",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- docs/guide.md [primary] reasons:", output)

    def test_export_does_not_anchor_path_inside_larger_mixed_case_token(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Docs").mkdir()
            tracked = root / "Docs" / "Guide.md"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["Docs/Guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Open ADocs/Guide.mdX first.",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- Docs/Guide.md [primary] reasons:", output)

    def test_export_does_not_anchor_common_free_text_noun(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            docs_dir = root / "docs"
            docs_dir.mkdir()
            tracked = docs_dir / "guide.md"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["docs/guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Need a guide for new operators, not the file itself.",
                    "next_step": "Prepare a short guide and sync with ops.",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- docs/guide.md [primary] reasons:", output)

    def test_export_does_not_anchor_ambiguous_duplicate_basename(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs").mkdir()
            (root / "src").mkdir()
            (root / "docs" / "guide.md").write_text("docs", encoding="utf-8")
            (root / "src" / "guide.md").write_text("src", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["docs/guide.md", "src/guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Look at guide.md first.",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- docs/guide.md [primary] reasons:", output)
            self.assertNotIn("- src/guide.md [primary] reasons:", output)

    def test_export_fails_without_registered_sources(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)

            with self.assertRaises(ContextIndexExportError):
                export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            with self.assertRaises(ContextIndexExportError):
                export_context_index_json(root, exported_at="2026-04-12T12:00:00+00:00")

    def test_export_is_stable_for_same_state(self) -> None:
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
                    "next_step": "Open tracked.txt",
                    "constraints": [],
                }
            )

            first = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")
            second = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertEqual(first, second)

    def test_export_fails_explicitly_when_state_cannot_be_read(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)

            with self.assertRaises(ContextIndexExportError):
                export_context_index_markdown(root)

            with self.assertRaises(ContextIndexExportError):
                export_context_index_json(root)

    def test_export_does_not_anchor_case_mismatched_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "Docs").mkdir()
            (root / "Docs" / "Guide.md").write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["Docs/Guide.md"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "open docs/guide.md now",
                    "next_step": "None",
                    "constraints": [],
                }
            )

            output = export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertIn("## Continuity Anchors", output)
            self.assertIn("- none", output)
            self.assertNotIn("- Docs/Guide.md [primary] reasons:", output)

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
                    "next_step": "Open tracked.txt",
                    "constraints": [],
                }
            )
            store.validate_state()
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision

            export_context_index_markdown(root, exported_at="2026-04-12T12:00:00+00:00")

            self.assertEqual(before_revision, store.read_snapshot().revision)
            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_export_rejects_runtime_output_paths(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            store, _ = seed_registered_source(root)
            store.open_session("alice")
            before_state = store.state_path.read_text(encoding="utf-8")
            before_session = store.session_path.read_text(encoding="utf-8")

            with self.assertRaises(ContextIndexExportError):
                write_context_index_markdown(root, ".cerebro/state.json")

            with self.assertRaises(ContextIndexExportError):
                write_context_index_markdown(root, ".cerebro/session.local.json")

            with self.assertRaises(ContextIndexExportError):
                write_context_index_markdown(root, ".cerebro/context-index.md")

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_session, store.session_path.read_text(encoding="utf-8"))

    def test_cli_exports_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_context_index_export(root, type("Args", (), {"out": None}))

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("# Context Index", output)
            self.assertIn("## Source Families", output)

    def test_cli_exports_json_to_stdout(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            stream = io.StringIO()

            with redirect_stdout(stream):
                exit_code = run_context_index_export(root, type("Args", (), {"out": None, "format": "json"}))

            payload = json.loads(stream.getvalue())
            self.assertEqual(exit_code, 0)
            self.assertEqual(payload["export_kind"], "context_index")

    def test_cli_exports_to_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            args = type("Args", (), {"out": "context-index.md"})

            exit_code = run_context_index_export(root, args)

            self.assertEqual(exit_code, 0)
            output_path = root / "context-index.md"
            self.assertTrue(output_path.exists())
            content = output_path.read_text(encoding="utf-8")
            self.assertIn("# Context Index", content)

    def test_cli_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "context-index-export"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 0)
            self.assertIn("# Context Index", result.stdout)
            self.assertIn("## Source Families", result.stdout)

    def test_cli_subprocess_rejects_runtime_output_path(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            run_init(root, None)
            seed_checkpointed_runtime(root)
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "context-index-export", "--out", ".cerebro/blocked.md"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            self.assertEqual(result.returncode, 1)
            self.assertIn("context_index_export_failed", result.stdout)
