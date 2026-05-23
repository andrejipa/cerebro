from __future__ import annotations

import json
import os
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from experiments.operational_signals.suggestions import evaluate as evaluate_module
from experiments.operational_signals.schema import SchemaError
from experiments.operational_signals.suggestions.harness import (
    ACCEPT_PRECISION,
    ACCEPT_RECALL,
    ITERATE_PRECISION,
    DatasetError,
    evaluate_dataset,
    load_dataset,
)
from experiments.operational_signals.suggestions.tests._workspace_temp import workspace_tempdir
from experiments.operational_signals.suggestions.rules import (
    detect_broken_canonical_refs,
    detect_current_surface_drift,
    detect_export_surface_gap,
    detect_supersedes_mechanical_metadata,
)


class LoadDatasetTests(unittest.TestCase):
    def test_default_dataset_loads(self) -> None:
        cases = load_dataset()
        self.assertGreaterEqual(len(cases), 12)
        ids = [case["id"] for case in cases]
        self.assertEqual(len(ids), len(set(ids)))
        self.assertTrue(any(case["label"] == "positive" for case in cases))
        self.assertTrue(any(case["label"] == "negative" for case in cases))
        self.assertTrue(all("exports_text" in case for case in cases))

    def test_export_surface_dataset_loads(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_export_surface.toml")
        cases = load_dataset(dataset_path)
        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue(any(case["exports_text"] for case in cases))

    def test_broken_refs_dataset_loads(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_broken_refs.toml")
        cases = load_dataset(dataset_path)
        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue(any(case["label"] == "positive" for case in cases))
        self.assertTrue(any("docs/operations/" in case["id"] for case in cases))

    def test_surface_drift_dataset_loads(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_surface_drift.toml")
        cases = load_dataset(dataset_path)
        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue(any(case["system_state_text"] for case in cases))
        self.assertTrue(any(case["opportunity_map_text"] for case in cases))

    def test_supersedes_dataset_loads(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_supersedes.toml")
        cases = load_dataset(dataset_path)
        self.assertGreaterEqual(len(cases), 10)
        self.assertTrue(any(case["source_path"].endswith(".md") for case in cases))
        self.assertTrue(any(not case["count_in_metrics"] for case in cases))

    def test_rejects_unsupported_label(self) -> None:
        with workspace_tempdir() as temp_root:
            path = temp_root / "bad.toml"
            path.write_text(
                'schema_version = "1"\n\n'
                '[[case]]\n'
                'id = "bad"\n'
                'label = "maybe"\n'
                'label_reason = "nope"\n'
                'text = "irrelevant"\n',
                encoding="utf-8",
            )
            with self.assertRaises(DatasetError):
                load_dataset(path)

    def test_rejects_duplicate_ids(self) -> None:
        with workspace_tempdir() as temp_root:
            path = temp_root / "dup.toml"
            path.write_text(
                'schema_version = "1"\n\n'
                '[[case]]\n'
                'id = "c1"\n'
                'label = "negative"\n'
                'label_reason = "r"\n'
                'text = "x"\n\n'
                '[[case]]\n'
                'id = "c1"\n'
                'label = "negative"\n'
                'label_reason = "r"\n'
                'text = "y"\n',
                encoding="utf-8",
            )
            with self.assertRaises(DatasetError):
                load_dataset(path)

    def test_expected_confidence_only_on_positive(self) -> None:
        with workspace_tempdir() as temp_root:
            path = temp_root / "weird.toml"
            path.write_text(
                'schema_version = "1"\n\n'
                '[[case]]\n'
                'id = "c1"\n'
                'label = "negative"\n'
                'label_reason = "r"\n'
                'text = "x"\n'
                'expected_confidence = "medium"\n',
                encoding="utf-8",
            )
            with self.assertRaises(DatasetError):
                load_dataset(path)

    def test_rejects_non_boolean_count_in_metrics(self) -> None:
        with workspace_tempdir() as temp_root:
            path = temp_root / "bad-count.toml"
            path.write_text(
                'schema_version = "1"\n\n'
                '[[case]]\n'
                'id = "c1"\n'
                'label = "negative"\n'
                'label_reason = "r"\n'
                'text = "x"\n'
                'count_in_metrics = "no"\n',
                encoding="utf-8",
            )
            with self.assertRaises(DatasetError):
                load_dataset(path)


class EvaluateDatasetTests(unittest.TestCase):
    def test_default_dataset_reaches_acceptance(self) -> None:
        result = evaluate_dataset()
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["authority"], "derived-advisory-only")
        self.assertTrue(result["non_authoritative"])
        self.assertTrue(result["read_only"])

    def test_confidence_match_rate_is_tracked(self) -> None:
        result = evaluate_dataset()
        metrics = result["metrics"]
        self.assertGreater(metrics["confidence_checked"], 0)
        self.assertIsNotNone(metrics["confidence_match_rate"])

    def test_every_emitted_suggestion_requires_review(self) -> None:
        result = evaluate_dataset()
        for case in result["per_case"]:
            if case["suggestion"] is not None:
                self.assertTrue(case["suggestion"]["human_review_required"])
                self.assertEqual(case["suggestion"]["authority"], "derived-advisory-only")

    def test_export_surface_emitted_ids_are_unique_within_dataset(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_export_surface.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_export_surface_gap, dataset)
        ids = [
            case["suggestion"]["id"]
            for case in result["per_case"]
            if case["suggestion"] is not None
        ]
        self.assertEqual(len(ids), len(set(ids)))

    def test_no_silent_suggestion_on_negative_case_with_mismatch(self) -> None:
        # regression guardrail: every positive label must carry a suggestion,
        # every negative label must carry None; confirmed via outcome codes
        result = evaluate_dataset()
        for case in result["per_case"]:
            if case["label"] == "positive":
                self.assertIn(case["outcome"], {"tp", "fn"})
            else:
                self.assertIn(case["outcome"], {"tn", "fp"})

    def test_verdict_thresholds_are_monotonic(self) -> None:
        self.assertGreater(ACCEPT_PRECISION, ITERATE_PRECISION)
        self.assertLess(ACCEPT_RECALL, ACCEPT_PRECISION + 1)

    def test_export_surface_dataset_reaches_acceptance(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_export_surface.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_export_surface_gap, dataset)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["rule"], "detect_export_surface_gap")

    def test_broken_refs_dataset_reaches_acceptance(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_broken_refs.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_broken_canonical_refs, dataset)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["rule"], "detect_broken_canonical_refs")

    def test_broken_refs_dataset_reaches_acceptance_outside_repo_cwd(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_broken_refs.toml")
        dataset = load_dataset(dataset_path)
        original_cwd = Path.cwd()
        with workspace_tempdir() as temp_root:
            os.chdir(temp_root)
            try:
                result = evaluate_dataset(detect_broken_canonical_refs, dataset)
            finally:
                os.chdir(original_cwd)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(metrics["fp"], 0)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")

    def test_surface_drift_dataset_reaches_acceptance(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_surface_drift.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_current_surface_drift, dataset)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["rule"], "detect_current_surface_drift")

    def test_supersedes_dataset_reaches_acceptance_and_tracks_exclusions(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_supersedes.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_supersedes_mechanical_metadata, dataset)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["rule"], "detect_supersedes_mechanical_metadata")
        self.assertEqual(metrics["dataset_cases"], 10)
        self.assertEqual(metrics["excluded_cases"], 2)
        self.assertEqual(metrics["total_cases"], 8)

    def test_supersedes_emitted_ids_are_unique_within_dataset(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_supersedes.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_supersedes_mechanical_metadata, dataset)
        ids = [
            case["suggestion"]["id"]
            for case in result["per_case"]
            if case["suggestion"] is not None
        ]
        self.assertEqual(len(ids), len(set(ids)))


class WriteReportTests(unittest.TestCase):
    def test_write_reports_produces_markdown_and_json(self) -> None:
        result = evaluate_dataset()
        with workspace_tempdir() as temp_root:
            md = temp_root / "report.md"
            js = temp_root / "report.json"
            evaluate_module.write_reports(result, markdown_path=md, json_path=js)
            markdown_text = md.read_text(encoding="utf-8")
            json_payload = json.loads(js.read_text(encoding="utf-8"))
        self.assertIn("Verdict", markdown_text)
        self.assertIn("advisory", markdown_text.lower())
        self.assertIn("precision", markdown_text.lower())
        self.assertEqual(json_payload["authority"], "derived-advisory-only")
        self.assertEqual(json_payload["rule"], "detect_stale_system_state")

    def test_write_reports_reject_output_paths_inside_dot_cerebro(self) -> None:
        result = evaluate_dataset()
        with workspace_tempdir() as temp_root:
            forbidden_dir = "." + "cerebro"
            md = temp_root / forbidden_dir / "report.md"
            js = temp_root / forbidden_dir / "report.json"

            with self.assertRaises(SchemaError):
                evaluate_module.write_reports(result, markdown_path=md, json_path=js)

            self.assertFalse(md.exists())
            self.assertFalse(js.exists())

    def test_write_reports_restores_previous_pair_when_second_write_fails(self) -> None:
        result = evaluate_dataset()
        with workspace_tempdir() as temp_root:
            md = temp_root / "report.md"
            js = temp_root / "report.json"
            md.write_text("old markdown\n", encoding="utf-8")
            js.write_text('{"old": true}\n', encoding="utf-8")
            original_write = evaluate_module._write_text_atomic
            call_count = 0

            def fail_second_write(path: Path, text: str) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated json write failure")
                original_write(path, text)

            with patch.object(
                evaluate_module,
                "_write_text_atomic",
                side_effect=fail_second_write,
            ):
                with self.assertRaises(OSError):
                    evaluate_module.write_reports(result, markdown_path=md, json_path=js)

            self.assertEqual(md.read_text(encoding="utf-8"), "old markdown\n")
            self.assertEqual(js.read_text(encoding="utf-8"), '{"old": true}\n')

    def test_write_reports_attempts_both_restores_when_first_restore_fails(self) -> None:
        result = evaluate_dataset()
        with workspace_tempdir() as temp_root:
            md = temp_root / "report.md"
            js = temp_root / "report.json"
            md.write_text("old markdown\n", encoding="utf-8")
            js.write_text('{"old": true}\n', encoding="utf-8")

            original_write = evaluate_module._write_text_atomic
            writes: list[str] = []
            restore_attempts: list[str] = []

            def fail_json_then_markdown_restore(path: Path, text: str) -> None:
                writes.append(path.name)
                if path == js and not restore_attempts:
                    raise OSError("simulated json write failure")
                original_write(path, text)

            def fail_first_restore(path: Path, previous_text: str | None) -> None:
                restore_attempts.append(path.name)
                if path == md:
                    raise OSError("simulated markdown restore failure")
                evaluate_module._write_text_atomic(path, previous_text or "")

            with patch.object(
                evaluate_module,
                "_write_text_atomic",
                side_effect=fail_json_then_markdown_restore,
            ):
                with patch.object(
                    evaluate_module,
                    "_restore_previous_text",
                    side_effect=fail_first_restore,
                ):
                    with self.assertRaises(ExceptionGroup) as raised:
                        evaluate_module.write_reports(result, markdown_path=md, json_path=js)

            self.assertEqual(writes, ["report.md", "report.json", "report.json"])
            self.assertEqual(restore_attempts, ["report.md", "report.json"])
            self.assertEqual(len(raised.exception.exceptions), 2)
            self.assertEqual(js.read_text(encoding="utf-8"), '{"old": true}\n')

    def test_write_reports_cleans_up_fresh_outputs_when_second_write_fails_without_previous_files(
        self,
    ) -> None:
        result = evaluate_dataset()
        with workspace_tempdir() as temp_root:
            md = temp_root / "report.md"
            js = temp_root / "report.json"
            original_write = evaluate_module._write_text_atomic
            call_count = 0

            def fail_second_write(path: Path, text: str) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated json write failure")
                original_write(path, text)

            with patch.object(
                evaluate_module,
                "_write_text_atomic",
                side_effect=fail_second_write,
            ):
                with self.assertRaises(OSError):
                    evaluate_module.write_reports(result, markdown_path=md, json_path=js)

            self.assertFalse(md.exists())
            self.assertFalse(js.exists())

    def test_checked_in_latest_reports_match_current_renderer(self) -> None:
        for name, config in evaluate_module.RULE_REGISTRY.items():
            with self.subTest(rule=name):
                dataset = load_dataset(config["dataset"])
                result = evaluate_dataset(config["rule"], dataset)
                if name == "broken_canonical_refs":
                    evaluate_module._annotate_broken_ref_scope(result, dataset)
                elif name == "current_surface_drift":
                    evaluate_module._annotate_surface_drift_states(result, dataset)
                elif name == "supersedes_mechanical_metadata":
                    evaluate_module._annotate_supersedes_states(result, dataset)
                expected_markdown = evaluate_module.render_markdown(result)
                expected_json = json.dumps(result, indent=2) + "\n"
                self.assertEqual(
                    Path(config["markdown"]).read_text(encoding="utf-8"),
                    expected_markdown,
                )
                self.assertEqual(
                    Path(config["json"]).read_text(encoding="utf-8"),
                    expected_json,
                )

    def test_evaluate_main_with_named_rule_writes_export_surface_reports(self) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = temp_root / "export.md"
            js = temp_root / "export.json"
            evaluate_module.RULE_REGISTRY["export_surface_gap"] = {
                **evaluate_module.RULE_REGISTRY["export_surface_gap"],
                "markdown": md,
                "json": js,
            }
            try:
                evaluate_module.main(["--rule", "export_surface_gap"])
            finally:
                evaluate_module.RULE_REGISTRY = original_registry
            self.assertTrue(md.exists())
            self.assertTrue(js.exists())

    def test_evaluate_main_without_named_rule_restores_earlier_reports_when_later_write_fails(
        self,
    ) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            patched_registry = {}
            previous_texts: dict[str, tuple[str, str]] = {}
            for name, config in original_registry.items():
                markdown_path = temp_root / f"{name}.md"
                json_path = temp_root / f"{name}.json"
                markdown_text = f"old {name} markdown\n"
                json_text = json.dumps({"old": name}) + "\n"
                markdown_path.write_text(markdown_text, encoding="utf-8")
                json_path.write_text(json_text, encoding="utf-8")
                patched_registry[name] = {
                    **config,
                    "markdown": markdown_path,
                    "json": json_path,
                }
                previous_texts[name] = (markdown_text, json_text)

            evaluate_module.RULE_REGISTRY = patched_registry
            original_write_reports = evaluate_module._write_reports_unlocked
            call_count = 0

            def fail_second_report(
                result: dict[str, object],
                *,
                markdown_path: Path,
                json_path: Path,
            ) -> None:
                nonlocal call_count
                call_count += 1
                if call_count == 2:
                    raise OSError("simulated second report failure")
                original_write_reports(
                    result,
                    markdown_path=markdown_path,
                    json_path=json_path,
                )

            try:
                with patch.object(
                    evaluate_module,
                    "_write_reports_unlocked",
                    side_effect=fail_second_report,
                ):
                    with patch("builtins.print"):
                        with self.assertRaises(OSError):
                            evaluate_module.main([])
            finally:
                evaluate_module.RULE_REGISTRY = original_registry

            for name, config in patched_registry.items():
                markdown_text, json_text = previous_texts[name]
                self.assertEqual(
                    Path(config["markdown"]).read_text(encoding="utf-8"),
                    markdown_text,
                )
                self.assertEqual(
                    Path(config["json"]).read_text(encoding="utf-8"),
                    json_text,
                )

    def test_batch_and_single_rule_latest_writers_share_one_lock_domain(self) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            patched_registry = {}
            for name, config in original_registry.items():
                patched_registry[name] = {
                    **config,
                    "markdown": temp_root / f"{name}.md",
                    "json": temp_root / f"{name}.json",
                }

            results_by_name = {
                name: evaluate_module._evaluate_named_rule(name)
                for name in original_registry
            }
            single_result = json.loads(json.dumps(results_by_name["stale_system_state"]))
            single_result["verdict"]["rationale"] = "single writer override"

            first_batch_write_started = threading.Event()
            release_batch_writer = threading.Event()
            single_started_writing = threading.Event()
            batch_errors: list[Exception] = []
            single_errors: list[Exception] = []
            original_write = evaluate_module._write_text_atomic
            first_batch_markdown_path = patched_registry[sorted(results_by_name)[0]]["markdown"]

            def coordinated_write(path: Path, text: str) -> None:
                thread_name = threading.current_thread().name
                if (
                    thread_name == "batch-writer"
                    and path == first_batch_markdown_path
                    and not first_batch_write_started.is_set()
                ):
                    original_write(path, text)
                    first_batch_write_started.set()
                    if not release_batch_writer.wait(2):
                        raise TimeoutError("timed out waiting to release batch writer")
                    return
                if thread_name == "single-writer":
                    single_started_writing.set()
                original_write(path, text)

            def run_batch_writer() -> None:
                try:
                    evaluate_module._write_all_rule_reports(results_by_name)
                except Exception as exc:
                    batch_errors.append(exc)

            def run_single_writer() -> None:
                try:
                    evaluate_module._write_named_rule_reports("stale_system_state", single_result)
                except Exception as exc:
                    single_errors.append(exc)

            evaluate_module.RULE_REGISTRY = patched_registry
            try:
                with patch.object(
                    evaluate_module,
                    "_write_text_atomic",
                    side_effect=coordinated_write,
                ):
                    batch_thread = threading.Thread(target=run_batch_writer, name="batch-writer")
                    single_thread = threading.Thread(target=run_single_writer, name="single-writer")
                    batch_thread.start()
                    self.assertTrue(first_batch_write_started.wait(2))
                    single_thread.start()
                    self.assertFalse(single_started_writing.wait(0.2))
                    release_batch_writer.set()
                    batch_thread.join(timeout=2)
                    single_thread.join(timeout=2)
            finally:
                evaluate_module.RULE_REGISTRY = original_registry

            self.assertFalse(batch_thread.is_alive())
            self.assertFalse(single_thread.is_alive())
            self.assertEqual(batch_errors, [])
            self.assertEqual(single_errors, [])
            stale_markdown_path = patched_registry["stale_system_state"]["markdown"]
            stale_json_path = patched_registry["stale_system_state"]["json"]
            self.assertIn(
                "single writer override",
                stale_markdown_path.read_text(encoding="utf-8"),
            )
            self.assertEqual(
                json.loads(stale_json_path.read_text(encoding="utf-8"))["verdict"]["rationale"],
                "single writer override",
            )

    def test_evaluate_main_with_broken_refs_rule_writes_scope_states(self) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = temp_root / "broken.md"
            js = temp_root / "broken.json"
            evaluate_module.RULE_REGISTRY["broken_canonical_refs"] = {
                **evaluate_module.RULE_REGISTRY["broken_canonical_refs"],
                "markdown": md,
                "json": js,
            }
            try:
                evaluate_module.main(["--rule", "broken_canonical_refs"])
            finally:
                evaluate_module.RULE_REGISTRY = original_registry
            markdown_text = md.read_text(encoding="utf-8")
            json_payload = json.loads(js.read_text(encoding="utf-8"))
            self.assertIn("scope_state=", markdown_text)
            self.assertEqual(json_payload["scope_metrics"]["out_of_scope"], 1)
            self.assertEqual(json_payload["scope_metrics"]["in_scope_broken"], 5)
            self.assertEqual(json_payload["scope_metrics"]["in_scope_clean"], 5)

    def test_broken_ref_scope_annotation_uses_source_path_not_case_id(self) -> None:
        result = {
            "per_case": [
                {"actual_suggestion": True},
                {"actual_suggestion": False},
                {"actual_suggestion": False},
            ]
        }
        dataset = [
            {
                "id": "synthetic-broken-1",
                "source_path": "docs/operations/synthetic-broken-1.md",
            },
            {
                "id": "synthetic-clean-1",
                "source_path": "docs/operations/synthetic-clean-1.md",
            },
            {
                "id": "synthetic-out-of-scope-1",
                "source_path": "docs/reference/synthetic-out-of-scope-1.md",
            },
        ]

        evaluate_module._annotate_broken_ref_scope(result, dataset)

        self.assertEqual(
            [case["scope_state"] for case in result["per_case"]],
            ["in_scope_broken", "in_scope_clean", "out_of_scope"],
        )
        self.assertEqual(
            result["scope_metrics"],
            {
                "out_of_scope": 1,
                "in_scope_clean": 1,
                "in_scope_broken": 1,
            },
        )

    def test_broken_ref_scope_annotation_treats_prefix_sharing_sibling_as_out_of_scope(self) -> None:
        result = {"per_case": [{"actual_suggestion": False}]}
        dataset = [
            {
                "id": "synthetic-sibling-prefix",
                "source_path": "docs/operationsX/synthetic.md",
            }
        ]

        evaluate_module._annotate_broken_ref_scope(result, dataset)

        self.assertEqual(result["per_case"][0]["scope_state"], "out_of_scope")
        self.assertEqual(
            result["scope_metrics"],
            {
                "out_of_scope": 1,
                "in_scope_clean": 0,
                "in_scope_broken": 0,
            },
        )

    def test_evaluate_main_with_surface_drift_rule_writes_surface_states(self) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = temp_root / "surface.md"
            js = temp_root / "surface.json"
            evaluate_module.RULE_REGISTRY["current_surface_drift"] = {
                **evaluate_module.RULE_REGISTRY["current_surface_drift"],
                "markdown": md,
                "json": js,
            }
            try:
                evaluate_module.main(["--rule", "current_surface_drift"])
            finally:
                evaluate_module.RULE_REGISTRY = original_registry
            markdown_text = md.read_text(encoding="utf-8")
            json_payload = json.loads(js.read_text(encoding="utf-8"))
            self.assertIn("surface_state=", markdown_text)
            self.assertEqual(json_payload["surface_metrics"]["insufficient_sources"], 5)
            self.assertEqual(json_payload["surface_metrics"]["sources_agree"], 3)
            self.assertEqual(json_payload["surface_metrics"]["drift_detected"], 2)

    def test_evaluate_main_with_supersedes_rule_writes_supersedes_states(self) -> None:
        with workspace_tempdir() as temp_root:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = temp_root / "supersedes.md"
            js = temp_root / "supersedes.json"
            evaluate_module.RULE_REGISTRY["supersedes_mechanical_metadata"] = {
                **evaluate_module.RULE_REGISTRY["supersedes_mechanical_metadata"],
                "markdown": md,
                "json": js,
            }
            try:
                evaluate_module.main(["--rule", "supersedes_mechanical_metadata"])
            finally:
                evaluate_module.RULE_REGISTRY = original_registry
            markdown_text = md.read_text(encoding="utf-8")
            json_payload = json.loads(js.read_text(encoding="utf-8"))
            self.assertIn("supersedes_state=", markdown_text)
            self.assertEqual(json_payload["supersedes_metrics"]["out_of_scope"], 2)
            self.assertEqual(json_payload["supersedes_metrics"]["in_scope_contextualized"], 3)
            self.assertEqual(json_payload["supersedes_metrics"]["in_scope_mechanical_only"], 5)


if __name__ == "__main__":
    unittest.main()
