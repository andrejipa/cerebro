"""Cross-check the lifecycle ledger against the actual `experiments/` tree.

Every folder that counts as an experiment must appear in the ledger,
and every ledger entry must correspond to an existing folder. This is
the mechanical enforcement of the lifecycle contract: adding a new
experiment without recording it, or leaving a stale entry for a removed
one, fails here.
"""

from __future__ import annotations

import unittest

from experiments._lifecycle.schema import (
    EXPERIMENTS_ROOT,
    load_lifecycle,
    tracked_experiment_dirs,
)


class LifecycleCoverageTests(unittest.TestCase):
    def test_every_experiment_folder_is_recorded(self) -> None:
        actual = set(tracked_experiment_dirs(EXPERIMENTS_ROOT))
        lifecycle = load_lifecycle()
        recorded = set(lifecycle.names())
        missing = actual - recorded
        self.assertFalse(
            missing,
            msg=(
                f"experiments/ folders without a lifecycle entry: {sorted(missing)}. "
                "Add them to experiments/lifecycle.toml with an explicit status."
            ),
        )

    def test_every_ledger_entry_points_to_existing_folder(self) -> None:
        actual = set(tracked_experiment_dirs(EXPERIMENTS_ROOT))
        lifecycle = load_lifecycle()
        recorded = set(lifecycle.names())
        orphans = recorded - actual
        self.assertFalse(
            orphans,
            msg=(
                f"lifecycle entries without a matching folder: {sorted(orphans)}. "
                "Remove the stale entry or restore the folder."
            ),
        )

    def test_infra_directories_are_excluded(self) -> None:
        actual = tracked_experiment_dirs(EXPERIMENTS_ROOT)
        self.assertNotIn("_lifecycle", actual)
        self.assertNotIn("__pycache__", actual)


if __name__ == "__main__":
    unittest.main()
