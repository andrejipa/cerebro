from __future__ import annotations

import json
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from experiments.recall_eval.indexer import IndexedChunk, ProjectIndex, build_project_index
from experiments.recall_eval.retrievers.semantic import retrieve_semantic
from experiments.recall_eval.semantic_vectors import embed_sparse
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir


class SemanticRetrievalTests(unittest.TestCase):
    def test_retrieve_semantic_uses_precomputed_chunk_vectors(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            (root / "README.md").write_text("estado atual e contexto geral", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            index = build_project_index("demo", root, temp_dir)

            with patch(
                "experiments.recall_eval.retrievers.semantic.embed_sparse",
                wraps=embed_sparse,
            ) as embed_mock:
                results = retrieve_semantic(index, query="onde esta a logica de progressao")

            self.assertGreaterEqual(len(results), 1)
            self.assertEqual(embed_mock.call_count, 1)

    def test_embed_sparse_is_stable_across_hash_seeds(self) -> None:
        repo_root = Path(__file__).resolve().parents[3]
        script = (
            "import json\n"
            "from experiments.recall_eval.semantic_vectors import embed_sparse\n"
            "print(json.dumps(embed_sparse('onde esta a logica de progressao'), sort_keys=True))\n"
        )
        expected = json.dumps(embed_sparse("onde esta a logica de progressao"), sort_keys=True)

        for seed in ("1", "999"):
            env = dict(os.environ)
            env["PYTHONHASHSEED"] = seed
            output = subprocess.check_output(
                [sys.executable, "-c", script],
                cwd=repo_root,
                env=env,
                text=True,
            ).strip()
            self.assertEqual(output, expected)

    def test_retrieve_semantic_breaks_score_ties_by_path_and_respects_candidate_limit(self) -> None:
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
            semantic_vector=embed_sparse("alpha"),
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
            semantic_vector=embed_sparse("alpha"),
        )
        index = ProjectIndex(
            project_name="demo",
            root="X:/demo",
            temp_root="X:/tmp",
            chunks=(chunk_b, chunk_a),
            idf={"alpha": 1.0},
        )

        results = retrieve_semantic(index, query="alpha", candidate_k=1)

        self.assertEqual([candidate.path for candidate in results], ["a.md"])
