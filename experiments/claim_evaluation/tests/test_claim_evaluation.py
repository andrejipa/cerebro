from __future__ import annotations

import unittest

from experiments.claim_evaluation import evaluate_claims, render_evaluation_markdown
from experiments.claim_extraction import ClaimCandidate


def _claim(
    subject: str,
    predicate: str,
    object: str,
    *,
    polarity: str = "positive",
    modality: str = "factual",
    source_path: str = "source.md",
    source_role: str = "primary",
    extraction_basis: str = "explicit",
    line: str = "L1",
) -> ClaimCandidate:
    return ClaimCandidate(
        subject=subject,
        predicate=predicate,
        object=object,
        polarity=polarity,
        modality=modality,
        criticality_hint="unknown",
        source_path=source_path,
        evidence_span=line,
        source_role=source_role,
        authority_hint="source-local",
        extraction_basis=extraction_basis,
    )


class ClaimEvaluationTests(unittest.TestCase):
    def test_primary_explicit_non_conflicting_claim_can_be_ready(self) -> None:
        report = evaluate_claims([_claim("schema", "exists", "true")])

        self.assertEqual(report.ready_count, 1)
        finding = report.findings[0]
        self.assertEqual(finding.authority, "source-local")
        self.assertEqual(finding.sufficiency, "sufficient")
        self.assertEqual(finding.operational_readiness, "ready")

    def test_structured_absence_is_insufficient_not_negative(self) -> None:
        report = evaluate_claims(
            [
                _claim(
                    "diagnostic source",
                    "does not declare",
                    "schema status",
                    polarity="unknown",
                    extraction_basis="structured_absence",
                )
            ]
        )

        finding = report.findings[0]
        self.assertEqual(finding.confidence, "low")
        self.assertEqual(finding.sufficiency, "insufficient")
        self.assertEqual(finding.operational_readiness, "blocked")
        self.assertIn("insufficiency evidence, not truth", " ".join(finding.reasons))

    def test_citation_does_not_upgrade_authority(self) -> None:
        report = evaluate_claims(
            [
                _claim(
                    "next item",
                    "is",
                    "build report",
                    modality="procedural",
                    source_path="SYSTEM_STATE.md",
                    source_role="citation",
                )
            ]
        )

        finding = report.findings[0]
        self.assertEqual(finding.authority, "citation-only")
        self.assertEqual(finding.operational_readiness, "blocked")
        self.assertIn("citation does not upgrade authority", finding.reasons)

    def test_conflicting_claims_are_stale_by_conflict_and_blocked(self) -> None:
        report = evaluate_claims(
            [
                _claim("schema", "exists", "true", source_path="new.md", line="L1"),
                _claim("schema", "exists", "false", polarity="negative", source_path="old.md", line="L1"),
            ]
        )

        self.assertEqual(report.blocked_count, 2)
        self.assertEqual({finding.conflict for finding in report.findings}, {"present"})
        self.assertEqual({finding.staleness for finding in report.findings}, {"stale_by_conflict"})

    def test_supersession_absence_makes_related_source_insufficient(self) -> None:
        old_claim = _claim("Edge Functions", "need", "implementation", source_path="OLD_DIAGNOSTIC.md")
        supersession = _claim(
            "OLD_DIAGNOSTIC.md",
            "is insufficient for",
            "schema-creation decisions",
            polarity="unknown",
            modality="meta",
            source_path="OLD_DIAGNOSTIC.md",
            source_role="derived",
            extraction_basis="supersession_absence",
            line="L2",
        )

        report = evaluate_claims([old_claim, supersession])
        by_id = {finding.claim.claim_id: finding for finding in report.findings}

        self.assertEqual(by_id[old_claim.claim_id].supersession, "present")
        self.assertEqual(by_id[old_claim.claim_id].operational_readiness, "blocked")
        self.assertEqual(by_id[supersession.claim_id].sufficiency, "insufficient")

    def test_unknown_polarity_blocks_readiness(self) -> None:
        report = evaluate_claims([_claim("pilot", "remains", "waiting", polarity="unknown", modality="temporal")])

        finding = report.findings[0]
        self.assertEqual(finding.confidence, "low")
        self.assertEqual(finding.operational_readiness, "blocked")

    def test_render_exposes_epistemic_boundaries_and_state_change(self) -> None:
        report = evaluate_claims([_claim("schema", "exists", "true")])
        rendered = render_evaluation_markdown(report)

        self.assertIn("# Claim Evaluation Report", rendered)
        self.assertIn("- state_change: none", rendered)
        self.assertIn("- registered_is_not_true: true", rendered)
        self.assertIn("- retrieved_is_not_relevant: true", rendered)
        self.assertIn("- remembered_is_not_trusted: true", rendered)
        self.assertIn("- silence_is_not_negative_evidence: true", rendered)


if __name__ == "__main__":
    unittest.main()
