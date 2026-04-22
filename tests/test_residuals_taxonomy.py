from __future__ import annotations

from datetime import date
from pathlib import Path
import tomllib
import unittest


REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DOCS = REPO_ROOT / "docs" / "operations"

VALID_CLASSES = {
    "accepted",
    "blocked_by_architecture",
    "out_of_envelope",
    "investigating",
}

VALID_SEVERITIES = {
    "critical",
    "high",
    "medium",
    "low",
}

VALID_RISK_VECTORS = {
    "continuity",
    "auditability",
    "host_integrity",
    "data_integrity",
    "confidentiality",
}

VALID_UNBLOCK_GATES = {
    "none",
    "architecture_decision",
    "formal_resume_trigger",
    "corrective_runtime_slice",
}


class ResidualTaxonomyTests(unittest.TestCase):
    def load_residuals(self) -> dict:
        return tomllib.loads((OPERATIONS_DOCS / "residuals.toml").read_text(encoding="utf-8"))

    def test_residuals_toml_is_parseable_and_has_expected_top_level_shape(self) -> None:
        payload = self.load_residuals()

        self.assertEqual("1", payload["schema_version"])
        self.assertIn("residual", payload)
        self.assertIsInstance(payload["residual"], list)
        self.assertGreaterEqual(len(payload["residual"]), 1)

    def test_residual_entries_have_unique_ids_and_minimum_required_fields(self) -> None:
        payload = self.load_residuals()
        residuals = payload["residual"]
        ids: list[str] = []

        for entry in residuals:
            for field in (
                "id",
                "title",
                "status",
                "class",
                "severity",
                "surface",
                "risk_vector",
                "unblock_gate",
                "unblock_criterion",
                "introduced_phase",
                "last_reviewed",
                "links",
            ):
                self.assertIn(field, entry)

            self.assertIsInstance(entry["id"], str)
            self.assertTrue(entry["id"])
            ids.append(entry["id"])

            self.assertIsInstance(entry["title"], str)
            self.assertTrue(entry["title"])
            self.assertIsInstance(entry["status"], str)
            self.assertTrue(entry["status"])
            self.assertIsInstance(entry["surface"], str)
            self.assertTrue(entry["surface"])
            self.assertIsInstance(entry["unblock_criterion"], str)
            self.assertTrue(entry["unblock_criterion"])
            self.assertIsInstance(entry["introduced_phase"], str)
            self.assertTrue(entry["introduced_phase"])

            self.assertIsInstance(entry["links"], list)
            self.assertGreaterEqual(len(entry["links"]), 1)
            self.assertTrue(all(isinstance(link, str) and link for link in entry["links"]))

            date.fromisoformat(entry["last_reviewed"])

        self.assertEqual(len(ids), len(set(ids)))

    def test_residual_entries_use_closed_vocabularies(self) -> None:
        payload = self.load_residuals()

        for entry in payload["residual"]:
            self.assertIn(entry["class"], VALID_CLASSES)
            self.assertIn(entry["severity"], VALID_SEVERITIES)
            self.assertIn(entry["risk_vector"], VALID_RISK_VECTORS)
            self.assertIn(entry["unblock_gate"], VALID_UNBLOCK_GATES)


if __name__ == "__main__":
    unittest.main()
