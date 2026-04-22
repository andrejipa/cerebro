from __future__ import annotations

import unittest

from experiments.recall_eval.scope_classifier import classify_scope, scope_filter_allows


class ScopeClassifierTests(unittest.TestCase):
    def test_scope_classifier_distinguishes_documentation_code_and_historical(self) -> None:
        self.assertEqual(classify_scope("docs/README.md")[0], "documentation")
        self.assertEqual(classify_scope("src/progression.ts")[0], "code")
        self.assertEqual(classify_scope("90_historico/backup_readme.md")[0], "historical")
        self.assertEqual(classify_scope("database/schema.sql")[0], "code")

    def test_scope_filter_allows_mixed_as_fallback(self) -> None:
        self.assertTrue(scope_filter_allows("documentation", "mixed"))
        self.assertTrue(scope_filter_allows("code", "mixed"))
        self.assertFalse(scope_filter_allows("code", "documentation"))
