from __future__ import annotations

import unittest

from experiments.operational_signals.analyzer import build_analysis
from experiments.operational_signals.logger import initialize_registry, record_unmet_use_case
from experiments.operational_signals.tests._workspace_temp import workspace_tempdir


def _record(record_id: str, project: str, failure_mode: str, repeat_count: int, confidence: str):
    return {
        "id": record_id,
        "timestamp": "2026-04-20T18:00:00Z",
        "project_context": project,
        "task_description": "recover a task",
        "query_or_need": "where is the approved path",
        "surface_used": ["analyze", "status-export"],
        "failure_mode": failure_mode,
        "manual_workaround": "opened docs manually",
        "operational_cost": {
            "minutes_spent": 5 + repeat_count,
            "extra_files_opened": 2 + repeat_count,
            "manual_search_rounds": 1 + repeat_count,
        },
        "repeat_count": repeat_count,
        "evidence": ["README.md"],
        "confidence": confidence,
        "notes": "",
    }


class AnalyzerTests(unittest.TestCase):
    def test_aggregation_by_project_and_failure_mode_is_correct(self) -> None:
        with workspace_tempdir() as temp_root:
            registry_path = temp_root / "signals.toml"
            initialize_registry(registry_path)
            record_unmet_use_case(_record("uuc-1", "alpha", "CONTEXT_NOT_FOUND", 2, "high"), path=registry_path)
            record_unmet_use_case(_record("uuc-2", "alpha", "CONTEXT_NOT_FOUND", 1, "medium"), path=registry_path)
            record_unmet_use_case(_record("uuc-3", "beta", "WRONG_SOURCE_SELECTED", 3, "high"), path=registry_path)

            analysis = build_analysis(registry_path)
            self.assertEqual(analysis["totals"]["count"], 3)
            self.assertEqual(analysis["by_project_context"]["alpha"]["count"], 2)
            self.assertEqual(analysis["by_failure_mode"]["CONTEXT_NOT_FOUND"]["count"], 2)
            self.assertEqual(len(analysis["candidate_triggers"]), 2)
