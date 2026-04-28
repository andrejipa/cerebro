from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from cli.commands.init import run_init
from core.state_store import StateStore

from experiments.context_advisor import advise_context, render_markdown


def _initialize_with_sources(root: Path, paths: list[str]) -> StateStore:
    run_init(root, None)
    store = StateStore(root)
    store.register_sources(paths)
    store.update_checkpoint(
        {
            "goal": "Goal",
            "summary": "Summary",
            "next_step": "Next",
            "constraints": [],
        }
    )
    store.validate_state()
    return store


class ContextAdvisorTests(unittest.TestCase):
    def test_combines_discovery_candidate_with_vector_evidence_for_llm(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Demo\n\nGeneral setup.\n", encoding="utf-8")
            (root / "CURRENT.md").write_text(
                "# Project Scope\n\nCurrent state and next action for the project.",
                encoding="utf-8",
            )
            _initialize_with_sources(root, ["README.md"])

            report = advise_context(root)
            rendered = render_markdown(report)

            paths = {rec.relative_path for rec in report.recommendations}
            self.assertIn("CURRENT.md", paths)
            self.assertIn("- audience: LLM", rendered)
            self.assertIn("may_suggest:", rendered)
            self.assertIn("must_not_apply:", rendered)
            self.assertIn("- state_change: none", rendered)
            self.assertIn("CURRENT.md", rendered)

    def test_drift_and_missing_registered_sources_are_prioritized(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            tracked = root / "TRACKED.md"
            missing = root / "MISSING.md"
            tracked.write_text("# Original\n", encoding="utf-8")
            missing.write_text("# Missing soon\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md", "TRACKED.md", "MISSING.md"])
            tracked.write_text("# Changed\n\nNew canonical-looking content.", encoding="utf-8")
            missing.unlink()

            report = advise_context(root)
            kinds = [rec.kind for rec in report.recommendations[:2]]

            self.assertEqual(kinds, ["inspect_registered_source_drift", "inspect_missing_registered_source"])
            self.assertEqual(report.recommendations[0].priority, 100)

    def test_custom_queries_emit_semantic_hits_without_requiring_discovery_candidate(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "architecture.md").write_text(
                "# Architecture Decision\n\nThe runtime keeps canonical state separate from derived reports.",
                encoding="utf-8",
            )

            report = advise_context(root, queries=("canonical state derived reports",))

            semantic = [rec for rec in report.recommendations if rec.kind == "inspect_semantic_hit"]
            self.assertTrue(semantic)
            self.assertEqual(semantic[0].relative_path, "architecture.md")
            self.assertIn("do_not_treat_similarity_as_canonical_truth", semantic[0].must_not_apply)

    def test_advisor_does_not_mutate_runtime_or_project_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            (root / "CURRENT.md").write_text("# Estado atual\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md"])

            before = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }
            report = advise_context(root)
            after = {
                path.relative_to(root).as_posix(): path.read_bytes()
                for path in sorted(root.rglob("*"))
                if path.is_file()
            }

            self.assertEqual(report.state_change, "none")
            self.assertEqual(before, after)

    def test_renderer_has_stable_empty_shape(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("# Demo\n", encoding="utf-8")
            _initialize_with_sources(root, ["README.md"])

            rendered = render_markdown(advise_context(root))

            self.assertIn("# Context Advisor Report", rendered)
            self.assertIn("## LLM Contract", rendered)
            self.assertIn("## Recommendations", rendered)
            self.assertIn("## Discovery Summary", rendered)

    def test_rejects_too_many_queries_and_invalid_vector_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            with self.assertRaises(ValueError):
                advise_context(tmp_dir, queries=("a", "b", "c", "d", "e"))
            with self.assertRaises(ValueError):
                advise_context(tmp_dir, vector_limit=0)


if __name__ == "__main__":
    unittest.main()
