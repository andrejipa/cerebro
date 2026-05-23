"""Tests for experiments.drift_detection.staleness_scorer.

All tests are non-authoritative: they never write to .cerebro/ and never
call import-context. They purely exercise deterministic scoring logic.
"""
import os
import unittest

from experiments.drift_detection.staleness_scorer import (
    StalenessResult,
    classify_staleness,
    score_source,
    score_sources,
    score_staleness,
)


class TestScoreStaleness(unittest.TestCase):
    """Unit tests for the core score_staleness() formula."""

    def test_zero_zero_is_fresh(self):
        self.assertEqual(score_staleness(0, 0), 0.0)

    def test_time_maxed_no_changes(self):
        self.assertAlmostEqual(score_staleness(90, 0), 0.6, places=3)

    def test_changes_maxed_no_time(self):
        self.assertAlmostEqual(score_staleness(0, 5), 0.4, places=3)

    def test_both_maxed(self):
        self.assertAlmostEqual(score_staleness(90, 5), 1.0, places=3)

    def test_half_time_no_changes(self):
        self.assertAlmostEqual(score_staleness(45, 0), 0.3, places=3)

    def test_time_above_ceiling_is_clamped(self):
        result = score_staleness(200, 0)
        self.assertAlmostEqual(result, 0.6, places=3)

    def test_changes_above_ceiling_is_clamped(self):
        result = score_staleness(0, 100)
        self.assertAlmostEqual(result, 0.4, places=3)

    def test_both_above_ceiling_clamped_to_one(self):
        result = score_staleness(1000, 1000)
        self.assertAlmostEqual(result, 1.0, places=3)

    def test_result_is_rounded_to_three_decimal_places(self):
        result = score_staleness(1, 0)
        self.assertEqual(result, round(result, 3))

    def test_negative_days_raises_value_error(self):
        with self.assertRaises(ValueError):
            score_staleness(-1, 0)

    def test_negative_changes_raises_value_error(self):
        with self.assertRaises(ValueError):
            score_staleness(0, -1)

    def test_both_negative_raises_value_error(self):
        with self.assertRaises(ValueError):
            score_staleness(-5, -3)


class TestClassifyStaleness(unittest.TestCase):
    """Unit tests for classify_staleness()."""

    def test_zero_is_fresh(self):
        self.assertEqual(classify_staleness(0.0), "fresh")

    def test_just_below_threshold_is_fresh(self):
        self.assertEqual(classify_staleness(0.29), "fresh")

    def test_at_aging_threshold(self):
        self.assertEqual(classify_staleness(0.3), "aging")

    def test_midpoint_aging(self):
        self.assertEqual(classify_staleness(0.45), "aging")

    def test_at_stale_threshold(self):
        self.assertEqual(classify_staleness(0.6), "stale")

    def test_midpoint_stale(self):
        self.assertEqual(classify_staleness(0.7), "stale")

    def test_at_critical_threshold(self):
        self.assertEqual(classify_staleness(0.8), "critical")

    def test_one_is_critical(self):
        self.assertEqual(classify_staleness(1.0), "critical")


class TestScoreSource(unittest.TestCase):
    """Unit tests for score_source()."""

    def test_returns_staleness_result_dataclass(self):
        result = score_source("core/a.py", 30, 1)
        self.assertIsInstance(result, StalenessResult)

    def test_path_is_preserved(self):
        result = score_source("core/a.py", 30, 1)
        self.assertEqual(result.path, "core/a.py")

    def test_days_elapsed_is_preserved(self):
        result = score_source("core/a.py", 30, 1)
        self.assertEqual(result.days_elapsed, 30)

    def test_structural_changes_is_preserved(self):
        result = score_source("core/a.py", 30, 1)
        self.assertEqual(result.structural_changes, 1)

    def test_score_matches_formula(self):
        result = score_source("core/a.py", 30, 1)
        expected = score_staleness(30, 1)
        self.assertAlmostEqual(result.score, expected, places=3)

    def test_classification_matches_score(self):
        result = score_source("core/a.py", 30, 1)
        expected_cls = classify_staleness(result.score)
        self.assertEqual(result.classification, expected_cls)

    def test_frozen_dataclass_is_immutable(self):
        result = score_source("core/a.py", 30, 1)
        with self.assertRaises(Exception):
            result.score = 0.0

    def test_zero_inputs_give_fresh_classification(self):
        result = score_source("cli/main.py", 0, 0)
        self.assertEqual(result.classification, "fresh")
        self.assertEqual(result.score, 0.0)

    def test_maxed_inputs_give_critical_classification(self):
        result = score_source("extensions/x.py", 90, 5)
        self.assertEqual(result.classification, "critical")
        self.assertAlmostEqual(result.score, 1.0, places=3)


class TestScoreSources(unittest.TestCase):
    """Unit tests for score_sources()."""

    def _make_descriptor(self, path, days, changes):
        return {"path": path, "days_elapsed": days, "structural_changes": changes}

    def test_returns_list(self):
        sources = [self._make_descriptor("core/a.py", 10, 0)]
        result = score_sources(sources)
        self.assertIsInstance(result, list)

    def test_empty_list_returns_empty(self):
        self.assertEqual(score_sources([]), [])

    def test_sorted_descending_by_score(self):
        sources = [
            self._make_descriptor("core/fresh.py", 0, 0),
            self._make_descriptor("core/critical.py", 90, 5),
            self._make_descriptor("core/aging.py", 45, 0),
        ]
        results = score_sources(sources)
        scores = [r.score for r in results]
        self.assertEqual(scores, sorted(scores, reverse=True))

    def test_most_stale_comes_first(self):
        sources = [
            self._make_descriptor("core/fresh.py", 0, 0),
            self._make_descriptor("core/critical.py", 90, 5),
        ]
        results = score_sources(sources)
        self.assertEqual(results[0].path, "core/critical.py")

    def test_single_source_is_returned(self):
        sources = [self._make_descriptor("core/a.py", 30, 2)]
        results = score_sources(sources)
        self.assertEqual(len(results), 1)
        self.assertEqual(results[0].path, "core/a.py")

    def test_all_results_are_staleness_result_instances(self):
        sources = [
            self._make_descriptor("core/a.py", 10, 1),
            self._make_descriptor("cli/b.py", 50, 2),
        ]
        results = score_sources(sources)
        for r in results:
            self.assertIsInstance(r, StalenessResult)

    def test_does_not_write_to_cerebro(self):
        """score_sources must not create or modify any .cerebro/ path."""
        import tempfile, glob
        cwd_cerebro = os.path.join(os.getcwd(), ".cerebro")
        # Snapshot existing .cerebro/ contents before the call (if it exists)
        before = set(glob.glob(os.path.join(cwd_cerebro, "**", "*"), recursive=True)) if os.path.isdir(cwd_cerebro) else set()
        sources = [self._make_descriptor("core/a.py", 10, 1)]
        score_sources(sources)
        # Snapshot after the call
        after = set(glob.glob(os.path.join(cwd_cerebro, "**", "*"), recursive=True)) if os.path.isdir(cwd_cerebro) else set()
        new_files = after - before
        self.assertEqual(
            new_files,
            set(),
            f"score_sources must not write to .cerebro/; new files found: {new_files}",
        )


if __name__ == "__main__":
    unittest.main()
