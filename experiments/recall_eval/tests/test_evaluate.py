from __future__ import annotations

import json
import shutil
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments.recall_eval.dataset import load_dataset
from experiments.recall_eval import indexer as indexer_module
from experiments.recall_eval.evaluate import _query_metrics, evaluate_dataset, expected_path_matches
from experiments.recall_eval.indexer import (
    build_experiment_temp_root,
    build_project_index,
    build_reusable_index_cache_root,
    ensure_outside_roots,
)
from experiments.recall_eval.retrievers.semantic import ensure_backend
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir


class EvaluateTests(unittest.TestCase):
    def test_dataset_loader_supports_old_and_new_fields(self) -> None:
        with workspace_tempdir() as root:
            dataset = {
                "projects": [
                    {
                        "name": "demo",
                        "root": str(root),
                        "queries": [
                            {
                                "id": "demo-1",
                                "query": "qual o estado atual",
                                "preferred_scope": "documentation",
                                "expected_paths": ["README.md"],
                                "notes": "legacy"
                            },
                            {
                                "id": "demo-2",
                                "query": "onde esta a logica",
                                "preferred_scope": "code",
                                "expected_paths": ["progression.ts"],
                                "expected_paths_exact": ["src/progression.ts"],
                                "expected_scope": "code",
                                "negative_paths": ["README.md"],
                                "difficulty": "hard",
                                "query_type": "code_logic",
                            },
                        ],
                    }
                ]
            }
            dataset_path = root.parent / "dataset_eval.json"
            dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

            loaded = load_dataset(dataset_path)
            self.assertEqual(loaded["projects"][0]["queries"][0]["difficulty"], "medium")
            self.assertEqual(loaded["projects"][0]["queries"][1]["query_type"], "code_logic")

    def test_dataset_loader_rejects_duplicate_query_ids_within_project(self) -> None:
        with workspace_tempdir() as root:
            dataset = {
                "projects": [
                    {
                        "name": "demo",
                        "root": str(root),
                        "queries": [
                            {"id": "dup", "query": "qual o estado atual"},
                            {"id": "dup", "query": "onde esta a logica"},
                        ],
                    }
                ]
            }
            dataset_path = root.parent / "dataset_eval.json"
            dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

            with self.assertRaisesRegex(ValueError, "Duplicate query id 'dup' in project 'demo'"):
                load_dataset(dataset_path)

    def test_metrics_are_computed_for_variants(self) -> None:
        with workspace_tempdir() as root:
            (root / "README.md").write_text("Estado atual e contexto do projeto", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "progression.ts").write_text("export const progression = true;", encoding="utf-8")
            dataset = {
                "projects": [
                    {
                        "name": "demo",
                        "root": str(root),
                        "queries": [
                            {
                                "id": "demo-1",
                                "query": "qual o estado atual",
                                "preferred_scope": "documentation",
                                "expected_paths": ["README.md"],
                                "expected_paths_exact": ["README.md"],
                                "expected_scope": "documentation",
                                "difficulty": "easy",
                                "query_type": "canonical_state",
                                "negative_paths": [],
                            },
                            {
                                "id": "demo-2",
                                "query": "onde esta a logica de progressao",
                                "preferred_scope": "code",
                                "expected_paths": ["progression.ts"],
                                "expected_paths_exact": ["src/progression.ts"],
                                "expected_scope": "code",
                                "difficulty": "hard",
                                "query_type": "code_logic",
                                "negative_paths": ["README.md"],
                            }
                        ],
                    }
                ]
            }
            dataset_path = root.parent / "dataset_eval.json"
            dataset_path.write_text(json.dumps(dataset), encoding="utf-8")
            results = evaluate_dataset(dataset_path)

            for variant in ("A", "B", "C", "D"):
                self.assertIn(variant, results["variants"])
                self.assertGreaterEqual(results["variants"][variant]["metrics"]["hit_at_3"], 0.0)
                self.assertIn("documentation", results["variants"][variant]["by_scope"])
                self.assertIn("code_logic", results["variants"][variant]["by_query_type"])

    def test_expected_path_matches_rejects_substring_siblings(self) -> None:
        self.assertFalse(expected_path_matches("docs/not_readme.md", "README.md"))
        self.assertFalse(expected_path_matches("docs/README_history.md", "README.md"))
        self.assertTrue(expected_path_matches("docs/README.md", "README.md"))
        self.assertTrue(
            expected_path_matches(
                "IRPF/_SISTEMA/03_MATERIAIS_DE_APOIO/material_de_apoio_crc_atividade_rural.pdf",
                "atividade_rural",
            )
        )

    def test_query_metrics_do_not_count_substring_siblings_as_hits_or_negative_paths(self) -> None:
        results = [
            {"path": "docs/not_readme.md", "scope": "documentation"},
            {"path": "docs/another.md", "scope": "documentation"},
            {"path": "src/other.py", "scope": "code"},
        ]
        query = {
            "expected_paths": ["README.md"],
            "expected_paths_exact": [],
            "negative_paths": ["README.md"],
            "preferred_scope": "documentation",
            "query_type": "canonical_state",
        }

        metrics = _query_metrics(results, query)

        self.assertFalse(metrics["hit_at_3"])
        self.assertEqual(metrics["matched_expected_count"], 0)
        self.assertFalse(metrics["lateral_doc_error"])
        self.assertEqual(metrics["mrr"], 0.0)

    def test_query_metrics_keep_recall_at_3_zero_when_first_hit_is_after_top_three(self) -> None:
        results = [
            {"path": "docs/a.md", "scope": "documentation"},
            {"path": "docs/b.md", "scope": "documentation"},
            {"path": "docs/c.md", "scope": "documentation"},
            {"path": "README.md", "scope": "documentation"},
        ]
        query = {
            "expected_paths": ["README.md"],
            "expected_paths_exact": [],
            "negative_paths": [],
            "preferred_scope": "documentation",
            "query_type": "canonical_state",
        }

        metrics = _query_metrics(results, query)

        self.assertEqual(metrics["recall_at_3"], 0.0)
        self.assertFalse(metrics["hit_at_3"])
        self.assertEqual(metrics["precision_at_3"], 0.0)
        self.assertEqual(metrics["matched_expected_count"], 0)
        self.assertEqual(metrics["mrr"], 0.25)

    def test_experiment_temp_root_stays_outside_projects(self) -> None:
        with workspace_tempdir() as project_dir:
            temp_root = build_experiment_temp_root([project_dir])
            try:
                ensure_outside_roots(temp_root, [project_dir])
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)

    def test_reusable_index_cache_root_stays_outside_projects(self) -> None:
        with workspace_tempdir() as project_dir:
            cache_root = build_reusable_index_cache_root([project_dir])
            ensure_outside_roots(cache_root, [project_dir])

    def test_experiment_temp_root_uses_safe_workspace_base_without_raw_tempfile_mkdtemp(self) -> None:
        with workspace_tempdir() as project_dir:
            repo_root = Path(indexer_module.__file__).resolve().parents[2]

            with patch(
                "experiments.recall_eval.indexer.tempfile.mkdtemp",
                side_effect=AssertionError("build_experiment_temp_root should not call raw tempfile.mkdtemp"),
            ):
                temp_root = build_experiment_temp_root([project_dir])
            try:
                temp_root_path = Path(temp_root).resolve()
                ensure_outside_roots(temp_root_path, [project_dir])
                self.assertTrue(temp_root_path.exists())
                self.assertTrue(temp_root_path.is_relative_to(repo_root))
            finally:
                shutil.rmtree(temp_root, ignore_errors=True)

    def test_reusable_index_cache_root_skips_tempdir_inside_project_root(self) -> None:
        with workspace_tempdir() as project_dir:
            repo_root = Path(indexer_module.__file__).resolve().parents[2]
            bad_temp_root = Path(project_dir) / "inside-project-temp"
            with patch(
                "experiments.recall_eval.indexer.tempfile.gettempdir",
                return_value=str(bad_temp_root),
            ):
                cache_root = build_reusable_index_cache_root([project_dir])

            cache_root_path = Path(cache_root).resolve()
            ensure_outside_roots(cache_root_path, [project_dir])
            self.assertTrue(cache_root_path.exists())
            self.assertTrue(cache_root_path.is_relative_to(repo_root))

    def test_building_index_does_not_write_inside_project_root(self) -> None:
        with workspace_tempdir() as root, workspace_tempdir() as temp_dir:
            file_path = root / "README.md"
            file_path.write_text("estado atual", encoding="utf-8")
            before = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

            from experiments.recall_eval.indexer import build_project_index

            build_project_index("demo", root, temp_dir)
            after = sorted(str(path.relative_to(root)) for path in root.rglob("*"))

            self.assertEqual(before, after)

    def test_build_project_index_reuses_cache_when_signature_matches(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as first_temp_dir,
            workspace_tempdir() as second_temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            (root / "README.md").write_text("estado atual e contexto", encoding="utf-8")

            first_index = build_project_index("demo", root, first_temp_dir, cache_root=cache_dir)

            with patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                side_effect=AssertionError("cache should have been reused"),
            ):
                second_index = build_project_index("demo", root, second_temp_dir, cache_root=cache_dir)

            self.assertEqual(first_index.idf, second_index.idf)
            self.assertEqual([chunk.path for chunk in first_index.chunks], [chunk.path for chunk in second_index.chunks])
            self.assertEqual(second_index.temp_root, str(Path(second_temp_dir).resolve()))

    def test_build_project_index_cache_hit_skips_source_recollection(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as first_temp_dir,
            workspace_tempdir() as second_temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            (root / "README.md").write_text("estado atual e contexto", encoding="utf-8")

            build_project_index("demo", root, first_temp_dir, cache_root=cache_dir)

            with patch(
                "experiments.recall_eval.indexer._iter_candidate_files",
                side_effect=AssertionError("cache hit should not rescan candidate files"),
            ), patch(
                "experiments.recall_eval.indexer._iter_candidate_directories",
                side_effect=AssertionError("cache hit should not rescan candidate directories"),
            ), patch(
                "experiments.recall_eval.indexer._collect_source_artifacts",
                side_effect=AssertionError("cache hit should not recollect source artifacts"),
            ), patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                side_effect=AssertionError("cache hit should not rebuild the index"),
            ):
                second_index = build_project_index("demo", root, second_temp_dir, cache_root=cache_dir)

            self.assertEqual(second_index.project_name, "demo")
            self.assertEqual(second_index.temp_root, str(Path(second_temp_dir).resolve()))

    def test_build_project_index_invalidates_cache_when_source_changes(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as first_temp_dir,
            workspace_tempdir() as second_temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            readme = root / "README.md"
            readme.write_text("estado atual", encoding="utf-8")
            build_project_index("demo", root, first_temp_dir, cache_root=cache_dir)
            readme.write_text("estado atual alterado com mais contexto", encoding="utf-8")

            real_build = indexer_module._build_fresh_project_index
            with patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                wraps=real_build,
            ) as build_mock:
                rebuilt_index = build_project_index("demo", root, second_temp_dir, cache_root=cache_dir)

            self.assertEqual(build_mock.call_count, 1)
            self.assertTrue(any("alterado" in chunk.text for chunk in rebuilt_index.chunks))

    def test_build_project_index_invalidates_cache_when_new_file_is_added_under_existing_empty_directory(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as first_temp_dir,
            workspace_tempdir() as second_temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            (root / "README.md").write_text("estado atual", encoding="utf-8")
            nested_dir = root / "docs" / "empty"
            nested_dir.mkdir(parents=True)
            build_project_index("demo", root, first_temp_dir, cache_root=cache_dir)
            (nested_dir / "fresh.md").write_text("novo arquivo indexavel", encoding="utf-8")

            real_build = indexer_module._build_fresh_project_index
            with patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                wraps=real_build,
            ) as build_mock:
                rebuilt_index = build_project_index("demo", root, second_temp_dir, cache_root=cache_dir)

            self.assertEqual(build_mock.call_count, 1)
            self.assertTrue(any(chunk.path == "docs/empty/fresh.md" for chunk in rebuilt_index.chunks))

    def test_build_project_index_invalidates_cache_when_builder_fingerprint_changes(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as first_temp_dir,
            workspace_tempdir() as second_temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            (root / "README.md").write_text("estado atual", encoding="utf-8")
            build_project_index("demo", root, first_temp_dir, cache_root=cache_dir)

            real_build = indexer_module._build_fresh_project_index
            with patch(
                "experiments.recall_eval.indexer._builder_fingerprint",
                return_value="forced-builder-drift",
            ), patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                wraps=real_build,
            ) as build_mock:
                build_project_index("demo", root, second_temp_dir, cache_root=cache_dir)

            self.assertEqual(build_mock.call_count, 1)

    def test_build_project_index_cache_payload_omits_host_specific_paths(self) -> None:
        with (
            workspace_tempdir() as project_dir,
            workspace_tempdir() as temp_dir,
            workspace_tempdir() as cache_dir,
        ):
            root = project_dir
            (root / "README.md").write_text("estado atual e contexto", encoding="utf-8")

            build_project_index("demo", root, temp_dir, cache_root=cache_dir)
            cache_files = list(Path(cache_dir).glob("*.json"))

            self.assertEqual(len(cache_files), 1)
            cached_payload = cache_files[0].read_text(encoding="utf-8")
            self.assertNotIn(str(root.resolve()), cached_payload)
            self.assertNotIn(str(Path(cache_dir).resolve()), cached_payload)

    def test_evaluate_dataset_reuses_index_cache_across_runs(self) -> None:
        with workspace_tempdir() as project_dir, workspace_tempdir() as cache_dir:
            root = project_dir
            (root / "README.md").write_text("Estado atual e contexto do projeto", encoding="utf-8")
            dataset = {
                "projects": [
                    {
                        "name": "demo",
                        "root": str(root),
                        "queries": [
                            {
                                "id": "demo-1",
                                "query": "qual o estado atual",
                                "preferred_scope": "documentation",
                                "expected_paths": ["README.md"],
                                "expected_paths_exact": ["README.md"],
                                "expected_scope": "documentation",
                                "difficulty": "easy",
                                "query_type": "canonical_state",
                                "negative_paths": [],
                            }
                        ],
                    }
                ]
            }
            dataset_path = root.parent / "dataset_eval.json"
            dataset_path.write_text(json.dumps(dataset), encoding="utf-8")

            first_results = evaluate_dataset(dataset_path, index_cache_root=cache_dir)

            with patch(
                "experiments.recall_eval.indexer._build_fresh_project_index",
                side_effect=AssertionError("evaluate_dataset should have reused the cached index"),
            ):
                second_results = evaluate_dataset(dataset_path, index_cache_root=cache_dir)

            self.assertEqual(first_results["variants"]["A"]["metrics"], second_results["variants"]["A"]["metrics"])

    def test_builder_fingerprint_is_cached_in_process(self) -> None:
        indexer_module._builder_fingerprint.cache_clear()
        read_calls: list[str] = []
        original_read_text = Path.read_text

        def tracked_read_text(path_obj: Path, *args, **kwargs) -> str:
            read_calls.append(path_obj.name)
            return original_read_text(path_obj, *args, **kwargs)

        try:
            with patch.object(indexer_module.Path, "read_text", autospec=True, side_effect=tracked_read_text):
                first = indexer_module._builder_fingerprint()
                second = indexer_module._builder_fingerprint()
        finally:
            indexer_module._builder_fingerprint.cache_clear()

        self.assertEqual(first, second)
        self.assertEqual(len(read_calls), 5)

    def test_semantic_backend_fails_closed_for_unknown_backend(self) -> None:
        with self.assertRaises(RuntimeError):
            ensure_backend("missing-backend")
