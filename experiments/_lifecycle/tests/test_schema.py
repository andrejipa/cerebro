from __future__ import annotations

import unittest
from datetime import date
from pathlib import Path
from tempfile import TemporaryDirectory

from experiments._lifecycle.schema import (
    ALLOWED_STATUSES,
    LifecycleError,
    Lifecycle,
    load_lifecycle,
    overdue_active_experiments,
    review_gap,
)


VALID_LEDGER = """\
schema_version = "1"
default_review_interval_days = 90

[[experiment]]
name = "alpha"
status = "active"
started = "2026-01-01"
last_reviewed = "2026-04-01"
next_review_due = "2026-07-01"
outcome_so_far = "in progress"

[[experiment]]
name = "beta"
status = "archived"
started = "2025-10-01"
archived_on = "2026-02-01"
outcome_so_far = "measured and rejected"

[[experiment]]
name = "gamma"
status = "graduated"
started = "2025-11-01"
graduated_on = "2026-03-15"
graduated_to = "extensions/gamma_export"
outcome_so_far = "promoted to approved export"
"""


def _write_ledger(body: str, tmp: Path) -> Path:
    path = tmp / "lifecycle.toml"
    path.write_text(body, encoding="utf-8")
    return path


class LoadLifecycleTests(unittest.TestCase):
    def test_loads_valid_ledger(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_ledger(VALID_LEDGER, Path(tmp))
            lifecycle = load_lifecycle(path)
        self.assertIsInstance(lifecycle, Lifecycle)
        self.assertEqual(lifecycle.schema_version, "1")
        self.assertEqual(lifecycle.default_review_interval_days, 90)
        self.assertEqual(lifecycle.names(), ("alpha", "beta", "gamma"))

    def test_statuses_vocabulary_is_closed(self) -> None:
        self.assertEqual(ALLOWED_STATUSES, {"active", "graduated", "archived"})

    def test_real_ledger_loads(self) -> None:
        lifecycle = load_lifecycle()
        self.assertGreaterEqual(len(lifecycle.experiments), 1)
        for experiment in lifecycle.experiments:
            self.assertIn(experiment.status, ALLOWED_STATUSES)

    def test_duplicate_name_rejected(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "active"\n'
            'started = "2026-01-01"\n'
            'last_reviewed = "2026-04-01"\n'
            'next_review_due = "2026-07-01"\n'
            'outcome_so_far = "x"\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "archived"\n'
            'started = "2026-01-01"\n'
            'archived_on = "2026-02-01"\n'
            'outcome_so_far = "y"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_unknown_status_rejected(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "paused"\n'
            'started = "2026-01-01"\n'
            'outcome_so_far = "x"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_active_missing_required_field_rejected(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "active"\n'
            'started = "2026-01-01"\n'
            'last_reviewed = "2026-04-01"\n'
            'outcome_so_far = "x"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_graduated_requires_target(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "graduated"\n'
            'started = "2026-01-01"\n'
            'graduated_on = "2026-03-01"\n'
            'outcome_so_far = "x"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_next_review_due_after_last_reviewed(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "active"\n'
            'started = "2026-01-01"\n'
            'last_reviewed = "2026-04-01"\n'
            'next_review_due = "2026-03-01"\n'
            'outcome_so_far = "x"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_last_reviewed_cannot_predate_started(self) -> None:
        body = (
            'schema_version = "1"\n'
            'default_review_interval_days = 90\n\n'
            '[[experiment]]\n'
            'name = "alpha"\n'
            'status = "active"\n'
            'started = "2026-02-01"\n'
            'last_reviewed = "2026-01-15"\n'
            'next_review_due = "2026-05-01"\n'
            'outcome_so_far = "x"\n'
        )
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_schema_version_mismatch_rejected(self) -> None:
        body = 'schema_version = "2"\ndefault_review_interval_days = 90\n'
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)

    def test_out_of_range_interval_rejected(self) -> None:
        body = 'schema_version = "1"\ndefault_review_interval_days = 0\n\n'
        with TemporaryDirectory() as tmp:
            path = _write_ledger(body, Path(tmp))
            with self.assertRaises(LifecycleError):
                load_lifecycle(path)


class OverdueTests(unittest.TestCase):
    def test_overdue_detection(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_ledger(VALID_LEDGER, Path(tmp))
            lifecycle = load_lifecycle(path)
        overdue = overdue_active_experiments(lifecycle, today=date(2027, 1, 1))
        names = {exp.name for exp in overdue}
        self.assertEqual(names, {"alpha"})

    def test_not_yet_overdue(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_ledger(VALID_LEDGER, Path(tmp))
            lifecycle = load_lifecycle(path)
        overdue = overdue_active_experiments(lifecycle, today=date(2026, 4, 15))
        self.assertEqual(overdue, ())


class ReviewGapTests(unittest.TestCase):
    def test_active_has_positive_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_ledger(VALID_LEDGER, Path(tmp))
            lifecycle = load_lifecycle(path)
        alpha = lifecycle.by_name("alpha")
        assert alpha is not None
        gap = review_gap(alpha)
        assert gap is not None
        self.assertGreater(gap.days, 0)

    def test_archived_has_no_gap(self) -> None:
        with TemporaryDirectory() as tmp:
            path = _write_ledger(VALID_LEDGER, Path(tmp))
            lifecycle = load_lifecycle(path)
        beta = lifecycle.by_name("beta")
        assert beta is not None
        self.assertIsNone(review_gap(beta))


if __name__ == "__main__":
    unittest.main()
