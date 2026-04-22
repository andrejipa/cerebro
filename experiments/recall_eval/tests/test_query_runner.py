from __future__ import annotations

import unittest
from unittest.mock import patch

from experiments.recall_eval.indexer import build_project_index
from experiments.recall_eval.query_runner import _lexical_candidate_limit
from experiments.recall_eval.query_runner import _semantic_candidate_limit
from experiments.recall_eval.query_runner import run_query, run_query_variants
from experiments.recall_eval.retrievers.lexical import retrieve_lexical
from experiments.recall_eval.retrievers.semantic import retrieve_semantic
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir


class QueryRunnerTests(unittest.TestCase):
    def test_output_is_structured_uniformly_across_variants(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("Estado atual e contexto", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            for variant in ("A", "B", "C", "D"):
                output = run_query(
                    index,
                    query="onde esta a logica de progressao",
                    preferred_scope="code",
                    query_type="code_logic",
                    top_k=3,
                    variant=variant,
                )
                self.assertTrue(output["experimental"])
                self.assertEqual(output["authority"], "derived-assistive")
                self.assertTrue(output["non_authoritative"])
                self.assertTrue(output["read_only"])
                self.assertEqual(output["variant"], variant)
                self.assertGreaterEqual(len(output["results"]), 1)
                result = output["results"][0]
                self.assertEqual(result["rank"], 1)
                self.assertIn("raw_score", result)
                self.assertIn("final_score", result)
                self.assertIn("path", result)
                self.assertIn("scope", result)
                self.assertIn("reason_flags", result)
                self.assertIn("excerpt", result)

    def test_run_query_variants_matches_individual_variant_outputs(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("Estado atual e contexto", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            variant_outputs = run_query_variants(
                index,
                query="onde esta a logica de progressao",
                preferred_scope="code",
                query_type="code_logic",
                top_k=3,
            )

            for variant in ("A", "B", "C", "D"):
                single_output = run_query(
                    index,
                    query="onde esta a logica de progressao",
                    preferred_scope="code",
                    query_type="code_logic",
                    top_k=3,
                    variant=variant,
                )
                self.assertEqual(variant_outputs[variant], single_output)

    def test_run_query_variants_reuses_retrievals_across_variants(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("Estado atual e contexto", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            with patch(
                "experiments.recall_eval.query_runner.retrieve_lexical",
                wraps=retrieve_lexical,
            ) as lexical_mock, patch(
                "experiments.recall_eval.query_runner.retrieve_semantic",
                wraps=retrieve_semantic,
            ) as semantic_mock:
                outputs = run_query_variants(
                    index,
                    query="onde esta a logica de progressao",
                    preferred_scope="code",
                    query_type="code_logic",
                    top_k=3,
                )

            self.assertEqual(set(outputs), {"A", "B", "C", "D"})
            self.assertEqual(lexical_mock.call_count, 1)
            self.assertEqual(semantic_mock.call_count, 1)

    def test_variant_d_uses_semantic_candidate_limit(self) -> None:
        index = object()
        top_k = 3
        query = "onde esta a logica de progressao"
        lexical_candidates = [{"path": "src/progression.ts"}]
        semantic_limit = _semantic_candidate_limit(top_k)
        semantic_candidates = [{"path": f"docs/semantic_{idx:02d}.md"} for idx in range(semantic_limit)]

        with patch(
            "experiments.recall_eval.query_runner.retrieve_lexical",
            return_value=lexical_candidates,
        ) as lexical_mock, patch(
            "experiments.recall_eval.query_runner.retrieve_semantic",
            return_value=semantic_candidates,
        ) as semantic_mock, patch(
            "experiments.recall_eval.query_runner.merge_candidates",
            return_value=["merged"],
        ) as merge_mock, patch(
            "experiments.recall_eval.query_runner.rerank_candidates",
            return_value=[],
        ) as rerank_mock:
            output = run_query(
                index,
                query=query,
                preferred_scope="code",
                query_type="code_logic",
                top_k=top_k,
                variant="D",
            )

        lexical_limit = _lexical_candidate_limit(top_k)
        lexical_mock.assert_called_once_with(index, query=query, candidate_k=lexical_limit)
        semantic_mock.assert_called_once_with(index, query=query, candidate_k=semantic_limit)
        merge_mock.assert_called_once_with(lexical_candidates, semantic_candidates)
        rerank_mock.assert_called_once_with(
            ["merged"],
            preferred_scope="code",
            query_type="code_logic",
            top_k=top_k,
            mode="improved",
        )
        self.assertEqual(output["variant"], "D")
