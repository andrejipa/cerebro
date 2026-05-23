from __future__ import annotations

import json
import threading
from pathlib import Path
import unittest
from unittest.mock import patch

from experiments.recall_eval.benchmarks.compare_variants import main as compare_main
from experiments.recall_eval.evaluate import REPORT_JSON_PATH, REPORT_MD_PATH
from experiments.recall_eval import report as report_module
from experiments.recall_eval.tests._workspace_temp import workspace_tempdir

LEGACY_REPORT_JSON_PATH = Path(__file__).resolve().parents[1] / "report_latest.json"
LEGACY_REPORT_MD_PATH = Path(__file__).resolve().parents[1] / "report_latest.md"


def _zero_metrics() -> dict[str, float]:
    return {
        "recall_at_3": 0.0,
        "precision_at_3": 0.0,
        "hit_at_3": 0.0,
        "mrr": 0.0,
        "historical_error_rate": 0.0,
        "lateral_doc_error_rate": 0.0,
        "code_doc_confusion_rate": 0.0,
    }


class BenchmarkTests(unittest.TestCase):
    def test_compare_variants_entrypoint_is_callable(self) -> None:
        self.assertTrue(callable(compare_main))

    def test_report_targets_are_inside_experiment_tree(self) -> None:
        experiment_root = Path(__file__).resolve().parents[1]
        self.assertTrue(Path(REPORT_JSON_PATH).resolve().is_relative_to(experiment_root))
        self.assertTrue(Path(REPORT_MD_PATH).resolve().is_relative_to(experiment_root))

    def test_legacy_latest_artifacts_are_explicitly_historical(self) -> None:
        legacy_json = json.loads(LEGACY_REPORT_JSON_PATH.read_text(encoding="utf-8"))
        legacy_markdown = LEGACY_REPORT_MD_PATH.read_text(encoding="utf-8")

        self.assertTrue(legacy_json["historical"])
        self.assertEqual(legacy_json["status"], "superseded")
        self.assertEqual(legacy_json["superseded_by"]["json"], "report_round2_latest.json")
        self.assertEqual(legacy_json["superseded_by"]["markdown"], "report_round2_latest.md")
        self.assertNotIn("metrics", legacy_json)
        self.assertNotIn("projects", legacy_json)

        self.assertIn("Historical Recall Evaluation Snapshot", legacy_markdown)
        self.assertIn("report_round2_latest.md", legacy_markdown)
        self.assertIn("report_round2_latest.json", legacy_markdown)
        self.assertNotIn("Aggregate Metrics", legacy_markdown)

    def test_write_reports_restores_previous_pair_when_second_write_fails(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            json_path.write_text('{"old": true}', encoding="utf-8")
            markdown_path.write_text("# old markdown", encoding="utf-8")
            results = {
                "variants": {},
                "failure_analysis": {},
            }
            original_write_text_atomic = report_module._write_text_atomic

            def fail_on_markdown(path: Path, text: str) -> None:
                if path == markdown_path and text != "# old markdown":
                    raise OSError("simulated markdown write failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.recall_eval.report._write_text_atomic",
                side_effect=fail_on_markdown,
            ):
                with self.assertRaises(OSError):
                    report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            self.assertEqual(json_path.read_text(encoding="utf-8"), '{"old": true}')
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# old markdown")

    def test_write_reports_cleans_up_fresh_outputs_when_second_write_fails(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            results = {
                "variants": {},
                "failure_analysis": {},
            }
            original_write_text_atomic = report_module._write_text_atomic

            def fail_on_markdown(path: Path, text: str) -> None:
                if path == markdown_path:
                    raise OSError("simulated markdown write failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.recall_eval.report._write_text_atomic",
                side_effect=fail_on_markdown,
            ):
                with self.assertRaises(OSError):
                    report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            self.assertFalse(json_path.exists())
            self.assertFalse(markdown_path.exists())

    def test_write_reports_omits_host_specific_temp_root_from_json(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            results = {
                "variants": {},
                "failure_analysis": {},
                "temp_root": str(root / "random-temp-root"),
            }

            report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            persisted = json_path.read_text(encoding="utf-8")
            self.assertIn('"temp_root": "<omitted>"', persisted)
            self.assertNotIn(str(root / "random-temp-root"), persisted)

    def test_write_reports_normalizes_dataset_path_to_stable_reference(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            results = {
                "variants": {},
                "failure_analysis": {},
                "dataset_path": str(root / "nested" / "eval_dataset.yaml"),
            }

            report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            persisted = json_path.read_text(encoding="utf-8")
            self.assertIn('"dataset_path": "nested/eval_dataset.yaml"', persisted)
            self.assertNotIn(str(root), persisted)

    def test_write_reports_strips_host_specific_project_roots_from_json(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            results = {
                "variants": {
                    "A": {
                        "metrics": _zero_metrics(),
                        "projects": [
                            {
                                "name": "Project A",
                                "root": str(root / "nested" / "Project A"),
                                "metrics": _zero_metrics(),
                                "queries": [],
                            }
                        ],
                        "by_scope": {},
                        "by_query_type": {},
                    }
                },
                "failure_analysis": {},
            }

            report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            project = persisted["variants"]["A"]["projects"][0]
            self.assertEqual(project["root"], "Project A")
            self.assertNotIn(str(root), json_path.read_text(encoding="utf-8"))

    def test_write_reports_redacts_absolute_paths_from_nested_excerpts(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            results = {
                "variants": {
                    "A": {
                        "metrics": _zero_metrics(),
                        "projects": [
                            {
                                "name": "Project A",
                                "root": str(root / "nested" / "Project A"),
                                "metrics": _zero_metrics(),
                                "queries": [
                                    {
                                        "id": "q-1",
                                        "results": [
                                            {
                                                "rank": 1,
                                                "path": "docs/guide.md",
                                                "excerpt": (
                                                    "See `D:\\secret\\repo\\notes.md` and "
                                                    "/home/user/private/cache.txt plus docs/guide.md "
                                                    "and trailing `D:\\secret path\\cutoff "
                                                    "and links [spec](D:/Project Root/spec.md "
                                                    "plus [spec2](<D:/Project Root/spec.md>) "
                                                    "and [spec3](</home/user/Project Root/spec.md>)"
                                                ),
                                            }
                                        ],
                                    }
                                ],
                            }
                        ],
                        "by_scope": {},
                        "by_query_type": {},
                    }
                },
                "failure_analysis": {},
            }

            report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            persisted = json.loads(json_path.read_text(encoding="utf-8"))
            excerpt = persisted["variants"]["A"]["projects"][0]["queries"][0]["results"][0]["excerpt"]
            self.assertIn("`<absolute-path>`", excerpt)
            self.assertIn("<absolute-path>", excerpt)
            self.assertNotIn(r"D:\secret\repo\notes.md", excerpt)
            self.assertNotIn("/home/user/private/cache.txt", excerpt)
            self.assertNotIn("D:/Project Root/spec.md", excerpt)
            self.assertNotIn("/home/user/Project Root/spec.md", excerpt)
            self.assertNotIn("Project Root", excerpt)
            self.assertIn("docs/guide.md", excerpt)

    def test_write_reports_attempts_both_restores_when_first_restore_fails(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            json_path.write_text('{"old": true}', encoding="utf-8")
            markdown_path.write_text("# old markdown", encoding="utf-8")
            results = {
                "variants": {},
                "failure_analysis": {},
            }
            original_write_text_atomic = report_module._write_text_atomic
            call_order: list[str] = []

            def fail_on_second_write_and_first_restore(path: Path, text: str) -> None:
                call_order.append(path.name)
                if path == markdown_path and text != "# old markdown":
                    raise OSError("simulated markdown write failure")
                if path == json_path and text == '{"old": true}':
                    raise OSError("simulated json restore failure")
                original_write_text_atomic(path, text)

            with patch(
                "experiments.recall_eval.report._write_text_atomic",
                side_effect=fail_on_second_write_and_first_restore,
            ):
                with self.assertRaises(ExceptionGroup):
                    report_module.write_reports(results, markdown_path=markdown_path, json_path=json_path)

            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "# old markdown")
            self.assertIn(markdown_path.name, call_order)
            self.assertGreaterEqual(call_order.count(markdown_path.name), 2)

    def test_write_reports_serializes_concurrent_writers_across_rollback(self) -> None:
        with workspace_tempdir() as root:
            json_path = root / "report.json"
            markdown_path = root / "report.md"
            json_path.write_text('{"old": true}', encoding="utf-8")
            markdown_path.write_text("# old markdown", encoding="utf-8")

            first_json_written = threading.Event()
            release_first_writer = threading.Event()
            second_started_writing = threading.Event()
            original_write_text_atomic = report_module._write_text_atomic
            first_errors: list[str] = []
            second_errors: list[str] = []

            def fake_render_markdown(results: dict) -> str:
                return f"md:{results['label']}"

            def coordinated_write(path: Path, text: str) -> None:
                thread_name = threading.current_thread().name
                if thread_name == "first-writer" and path == json_path and text != '{"old": true}':
                    original_write_text_atomic(path, text)
                    first_json_written.set()
                    if not release_first_writer.wait(2):
                        raise TimeoutError("timed out waiting to release first writer")
                    raise OSError("simulated json write failure after first json write")
                if thread_name == "second-writer" and path == json_path:
                    second_started_writing.set()
                    original_write_text_atomic(path, text)
                    return
                original_write_text_atomic(path, text)

            def first_worker() -> None:
                try:
                    report_module.write_reports(
                        {"label": "first", "variants": {}, "failure_analysis": {}},
                        markdown_path=markdown_path,
                        json_path=json_path,
                    )
                except Exception as exc:  # pragma: no cover - asserted below
                    first_errors.append(type(exc).__name__)

            def second_worker() -> None:
                try:
                    if not first_json_written.wait(2):
                        raise TimeoutError("timed out waiting for first writer")
                    report_module.write_reports(
                        {"label": "second", "variants": {}, "failure_analysis": {}},
                        markdown_path=markdown_path,
                        json_path=json_path,
                    )
                except Exception as exc:  # pragma: no cover - asserted below
                    second_errors.append(type(exc).__name__)

            with patch(
                "experiments.recall_eval.report.render_markdown_report",
                side_effect=fake_render_markdown,
            ), patch(
                "experiments.recall_eval.report._write_text_atomic",
                side_effect=coordinated_write,
            ):
                first_thread = threading.Thread(target=first_worker, name="first-writer")
                second_thread = threading.Thread(target=second_worker, name="second-writer")
                first_thread.start()
                self.assertTrue(first_json_written.wait(2))

                second_thread.start()
                self.assertFalse(
                    second_started_writing.wait(0.1),
                    "second writer should stay blocked until the first rollback finishes",
                )

                release_first_writer.set()
                first_thread.join()
                second_thread.join()

            self.assertEqual(first_errors, ["OSError"])
            self.assertEqual(second_errors, [])
            self.assertIn('"label": "second"', json_path.read_text(encoding="utf-8"))
            self.assertEqual(markdown_path.read_text(encoding="utf-8"), "md:second")
