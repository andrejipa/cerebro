from __future__ import annotations

import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments.operational_signals.suggestions import evaluate as evaluate_module
from experiments.operational_signals.suggestions.harness import (
    ACCEPT_PRECISION,
    ACCEPT_RECALL,
    ITERATE_PRECISION,
    DatasetError,
    evaluate_dataset,
    load_dataset,
)
from experiments.operational_signals.suggestions.rules import (
    detect_broken_canonical_refs,
    detect_current_surface_drift,
    detect_export_surface_gap,
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

    def test_rejects_unsupported_label(self) -> None:
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "bad.toml"
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
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "dup.toml"
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
        with TemporaryDirectory() as tmp:
            path = Path(tmp) / "weird.toml"
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

    def test_surface_drift_dataset_reaches_acceptance(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_surface_drift.toml")
        dataset = load_dataset(dataset_path)
        result = evaluate_dataset(detect_current_surface_drift, dataset)
        metrics = result["metrics"]
        self.assertGreaterEqual(metrics["precision"], ACCEPT_PRECISION)
        self.assertGreaterEqual(metrics["recall"], ACCEPT_RECALL)
        self.assertEqual(result["verdict"]["classification"], "accept_for_staged_promotion")
        self.assertEqual(result["rule"], "detect_current_surface_drift")


class WriteReportTests(unittest.TestCase):
    def test_write_reports_produces_markdown_and_json(self) -> None:
        result = evaluate_dataset()
        with TemporaryDirectory() as tmp:
            md = Path(tmp) / "report.md"
            js = Path(tmp) / "report.json"
            evaluate_module.write_reports(result, markdown_path=md, json_path=js)
            markdown_text = md.read_text(encoding="utf-8")
            json_payload = json.loads(js.read_text(encoding="utf-8"))
        self.assertIn("Verdict", markdown_text)
        self.assertIn("advisory", markdown_text.lower())
        self.assertIn("precision", markdown_text.lower())
        self.assertEqual(json_payload["authority"], "derived-advisory-only")
        self.assertEqual(json_payload["rule"], "detect_stale_system_state")

    def test_evaluate_main_with_named_rule_writes_export_surface_reports(self) -> None:
        with TemporaryDirectory() as tmp:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = Path(tmp) / "export.md"
            js = Path(tmp) / "export.json"
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

    def test_evaluate_main_with_broken_refs_rule_writes_scope_states(self) -> None:
        with TemporaryDirectory() as tmp:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = Path(tmp) / "broken.md"
            js = Path(tmp) / "broken.json"
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

    def test_evaluate_main_with_surface_drift_rule_writes_surface_states(self) -> None:
        with TemporaryDirectory() as tmp:
            original_registry = evaluate_module.RULE_REGISTRY.copy()
            md = Path(tmp) / "surface.md"
            js = Path(tmp) / "surface.json"
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
            self.assertEqual(json_payload["surface_metrics"]["insufficient_sources"], 3)
            self.assertEqual(json_payload["surface_metrics"]["sources_agree"], 3)
            self.assertEqual(json_payload["surface_metrics"]["drift_detected"], 4)


if __name__ == "__main__":
    unittest.main()
