from __future__ import annotations

import unittest

from experiments.recall_eval.analysis.failure_report import build_failure_analysis


def _query(project_name: str, query_id: str, *, hit_at_3: bool, code_doc_confusion: bool = False, historical_error: bool = False) -> dict:
    return {
        "id": query_id,
        "project_name": project_name,
        "metrics": {
            "hit_at_3": hit_at_3,
            "code_doc_confusion": code_doc_confusion,
            "historical_error": historical_error,
        },
    }


class FailureReportTests(unittest.TestCase):
    def test_build_failure_analysis_keys_same_query_id_by_project_name_and_query_id(self) -> None:
        variant_results = {
            "A": {
                "projects": [
                    {
                        "name": "alpha",
                        "queries": [
                            _query("alpha", "shared-id", hit_at_3=True),
                        ],
                    },
                    {
                        "name": "beta",
                        "queries": [
                            _query("beta", "shared-id", hit_at_3=False),
                        ],
                    },
                ]
            },
            "B": {
                "projects": [
                    {
                        "name": "alpha",
                        "queries": [
                            _query("alpha", "shared-id", hit_at_3=False),
                        ],
                    },
                    {
                        "name": "beta",
                        "queries": [
                            _query("beta", "shared-id", hit_at_3=False),
                        ],
                    },
                ]
            },
            "C": {"projects": []},
            "D": {"projects": []},
        }

        failure_analysis = build_failure_analysis(variant_results)

        self.assertEqual(failure_analysis["lexical_better"], ["B:shared-id"])
        self.assertEqual(failure_analysis["embeddings_helped"], [])
        self.assertEqual(failure_analysis["embeddings_hurt"], [])
        self.assertEqual(failure_analysis["doc_beats_code"], [])
        self.assertEqual(failure_analysis["historical_pull"], [])
