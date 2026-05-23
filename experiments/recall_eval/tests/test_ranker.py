from __future__ import annotations

import unittest

from experiments.recall_eval.indexer import build_project_index
from experiments.recall_eval.query_runner import run_query
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir


class RankerTests(unittest.TestCase):
    def test_baseline_and_improved_ranking_are_stable(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("Versao oficial vigente e estado atual", encoding="utf-8")
            (root / "90_historico").mkdir()
            (root / "90_historico" / "README_backup.md").write_text(
                "Versao oficial antiga backup historico",
                encoding="utf-8",
            )
            index = build_project_index("demo", root, temp_dir)

            baseline_first = run_query(index, query="qual a versao oficial vigente", variant="A")
            baseline_second = run_query(index, query="qual a versao oficial vigente", variant="A")
            improved = run_query(index, query="qual a versao oficial vigente", variant="B")

            self.assertEqual(baseline_first, baseline_second)
            self.assertEqual(baseline_first["results"][0]["path"], "README.md")
            self.assertEqual(improved["results"][0]["path"], "README.md")
            self.assertIn("boosted_readme", improved["results"][0]["reason_flags"])

    def test_code_queries_do_not_prefer_documentation_laterally(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("logica de progressao e contexto geral", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            output = run_query(
                index,
                query="onde esta a logica de progressao",
                preferred_scope="code",
                query_type="code_logic",
                variant="B",
            )

            self.assertEqual(output["results"][0]["path"], "src/progression.ts")
            self.assertIn("boosted_code_for_code_query", output["results"][0]["reason_flags"])

    def test_historical_queries_are_not_blocked_by_hygiene(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "90_historico").mkdir()
            (root / "90_historico" / "README.md").write_text("historico antigo consolidado", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            output = run_query(
                index,
                query="onde ficou o historico antigo",
                preferred_scope="historical",
                query_type="historical_lookup",
                variant="B",
            )

            self.assertEqual(output["results"][0]["scope"], "historical")
            self.assertIn("boosted_historical_query_alignment", output["results"][0]["reason_flags"])
