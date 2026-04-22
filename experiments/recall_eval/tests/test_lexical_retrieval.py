from __future__ import annotations

from pathlib import Path
import unittest
from unittest.mock import patch

from experiments.recall_eval.indexer import IndexedChunk, build_project_index
from experiments.recall_eval.indexer import ProjectIndex
from experiments.recall_eval.lexical_scoring import (
    prepare_query,
    score_prepared_query_against_chunk,
    score_query_against_chunk,
    tokenize_query,
)
from experiments.recall_eval.retrievers.lexical import retrieve_lexical
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir


class LexicalScoringTests(unittest.TestCase):
    def test_prepared_query_scoring_matches_legacy_wrapper(self) -> None:
        chunk = IndexedChunk(
            project_name="demo",
            root="X:/demo",
            path="src/progression.ts",
            chunk_id=0,
            text="progression logic state machine",
            source_kind="text",
            scope="code",
            scope_flags=(),
            token_counts={"progression": 1, "logic": 1, "state": 1, "machine": 1},
            weighted_tokens={"progression": 2.0, "logic": 1.5, "state": 1.0},
            vector_norm=(2.0**2 + 1.5**2 + 1.0**2) ** 0.5,
        )
        idf = {"progression": 2.0, "logic": 1.5, "state": 1.0}
        query_tokens = tokenize_query("onde esta a logica de progressao")

        legacy_score = score_query_against_chunk(query_tokens, chunk, idf)
        prepared_query = prepare_query(query_tokens, idf)
        prepared_score = score_prepared_query_against_chunk(prepared_query, chunk)

        self.assertAlmostEqual(prepared_score, legacy_score)

    def test_retrieve_lexical_prepares_query_once(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("estado atual e logica geral", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            with patch(
                "experiments.recall_eval.retrievers.lexical.prepare_query",
                wraps=prepare_query,
            ) as prepare_query_mock:
                results = retrieve_lexical(index, query="onde esta a logica de progressao")

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(prepare_query_mock.call_count, 1)

    def test_retrieve_lexical_breaks_score_ties_by_path_and_respects_candidate_limit(self) -> None:
        chunk_a = IndexedChunk(
            project_name="demo",
            root="X:/demo",
            path="a.md",
            chunk_id=0,
            text="alpha",
            source_kind="text",
            scope="documentation",
            scope_flags=(),
            token_counts={"alpha": 1},
            weighted_tokens={"alpha": 1.0},
            vector_norm=1.0,
        )
        chunk_b = IndexedChunk(
            project_name="demo",
            root="X:/demo",
            path="b.md",
            chunk_id=1,
            text="alpha",
            source_kind="text",
            scope="documentation",
            scope_flags=(),
            token_counts={"alpha": 1},
            weighted_tokens={"alpha": 1.0},
            vector_norm=1.0,
        )
        index = ProjectIndex(
            project_name="demo",
            root="X:/demo",
            temp_root="X:/tmp",
            chunks=(chunk_b, chunk_a),
            idf={"alpha": 1.0},
        )

        results = retrieve_lexical(index, query="alpha", candidate_k=1)

        self.assertEqual([candidate.path for candidate in results], ["a.md"])

    def test_retrieve_lexical_does_not_cache_query_across_indexes(self) -> None:
        with workspace_tempdir() as root_a, workspace_tempdir() as root_b:
            (root_a / "README.md").write_text("estado atual e logica geral", encoding="utf-8")
            (root_a / "src").mkdir()
            (root_a / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")

            (root_b / "README.md").write_text("estado vigente e registro documental", encoding="utf-8")
            (root_b / "docs").mkdir()
            (root_b / "docs" / "flow.md").write_text("logica de aprovacao e historico", encoding="utf-8")

            with workspace_tempdir() as temp_a, workspace_tempdir() as temp_b:
                index_a = build_project_index("demo-a", root_a, temp_a)
                index_b = build_project_index("demo-b", root_b, temp_b)

                with patch(
                    "experiments.recall_eval.retrievers.lexical.prepare_query",
                    wraps=prepare_query,
                ) as prepare_query_mock:
                    retrieve_lexical(index_a, query="onde esta a logica")
                    retrieve_lexical(index_b, query="onde esta a logica")

                self.assertEqual(prepare_query_mock.call_count, 2)
