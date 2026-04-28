from __future__ import annotations

import unittest

from experiments.claim_extraction import FIXTURES, ClaimCandidate, SourceText, extract_candidates, render_candidates_markdown


def _normalized(candidates: list[ClaimCandidate] | tuple[ClaimCandidate, ...]) -> list[tuple[str, str, str, str, str, str, str, str, str]]:
    return sorted(candidate.normalized() for candidate in candidates)


class ClaimExtractionTests(unittest.TestCase):
    def test_all_documented_fixtures_pass_exactly(self) -> None:
        self.assertEqual(len(FIXTURES), 12)
        for fixture in FIXTURES:
            with self.subTest(fixture=fixture.id):
                actual = fixture.extract()
                expected = list(fixture.expected)
                if fixture.allow_extra:
                    for expected_candidate in expected:
                        self.assertIn(expected_candidate.normalized(), _normalized(actual))
                else:
                    self.assertEqual(_normalized(actual), _normalized(expected))

    def test_forbidden_candidates_never_emit(self) -> None:
        for fixture in FIXTURES:
            with self.subTest(fixture=fixture.id):
                emitted = {(candidate.subject, candidate.predicate, candidate.object) for candidate in fixture.extract()}
                for forbidden in fixture.forbidden:
                    self.assertNotIn(forbidden, emitted)

    def test_fixture_9_forbidden_negative_is_locked(self) -> None:
        fixture = next(case for case in FIXTURES if case.id == "F10_fixture_9_full_schema_omission_oracle")
        emitted = {(candidate.subject, candidate.predicate, candidate.object) for candidate in fixture.extract()}

        self.assertIn(("Supabase schema", "already exists", "true"), emitted)
        self.assertIn(
            ("cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md", "does not declare", "schema status"),
            emitted,
        )
        self.assertNotIn(("Supabase schema", "does not exist", "true"), emitted)
        self.assertNotIn(
            ("cerebro_base/04_DIAGNOSTICO_INICIAL_ATUAL.md", "says", "schema does not exist"),
            emitted,
        )

    def test_every_candidate_has_trace_identity_and_evidence_span(self) -> None:
        seen_ids: set[str] = set()
        for fixture in FIXTURES:
            for candidate in fixture.extract():
                self.assertTrue(candidate.claim_id)
                self.assertTrue(candidate.semantic_id)
                self.assertTrue(candidate.evidence_id)
                self.assertTrue(candidate.source_path)
                self.assertRegex(candidate.evidence_span, r"^L\d+$")
                self.assertNotIn(candidate.claim_id, seen_ids)
                seen_ids.add(candidate.claim_id)

    def test_semantic_identity_survives_line_movement_but_evidence_identity_changes(self) -> None:
        base = ClaimCandidate(
            subject="schema",
            predicate="exists",
            object="true",
            polarity="positive",
            modality="factual",
            criticality_hint="unknown",
            source_path="docs/state.md",
            evidence_span="L1",
            source_role="primary",
            authority_hint="source-local",
            extraction_basis="explicit",
        )
        moved = ClaimCandidate(
            subject=base.subject,
            predicate=base.predicate,
            object=base.object,
            polarity=base.polarity,
            modality=base.modality,
            criticality_hint=base.criticality_hint,
            source_path=base.source_path,
            evidence_span="L9",
            source_role=base.source_role,
            authority_hint=base.authority_hint,
            extraction_basis=base.extraction_basis,
        )

        self.assertEqual(base.semantic_id, moved.semantic_id)
        self.assertNotEqual(base.claim_id, moved.claim_id)
        self.assertNotEqual(base.evidence_id, moved.evidence_id)

    def test_extraction_is_deterministic(self) -> None:
        for fixture in FIXTURES:
            with self.subTest(fixture=fixture.id):
                first = fixture.extract()
                second = fixture.extract()
                self.assertEqual(first, second)

    def test_structured_and_supersession_absence_stay_unknown(self) -> None:
        for fixture in FIXTURES:
            for candidate in fixture.extract():
                if candidate.extraction_basis in {"structured_absence", "supersession_absence"}:
                    self.assertEqual(candidate.polarity, "unknown")

    def test_criticality_defaults_to_unknown_without_marker(self) -> None:
        fixture = next(case for case in FIXTURES if case.id == "F8_criticality_unknown_by_default")
        candidates = fixture.extract()

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].criticality_hint, "unknown")

    def test_render_is_advisory_and_traceable(self) -> None:
        fixture = next(case for case in FIXTURES if case.id == "F2_silence_is_not_negative")
        rendered = render_candidates_markdown(fixture.extract())

        self.assertIn("# Claim Candidates", rendered)
        self.assertIn("source: `docs/operations/DIAGNOSTIC.md:L2`", rendered)
        self.assertNotIn("does not exist", rendered)

    def test_temporal_trigger_consumption_subject_is_normalized(self) -> None:
        source = SourceText(
            "docs/operations/SYSTEM_STATE.md",
            "- Formal resume trigger consumed on 2026-04-24: `FORMAL_RESUME_TRIGGER_CEREBRO_SELF_EPISTEMIC_READINESS` — first internal epistemic-readiness report produced with a deliberately long snapshot bullet that must remain evidence only.",
        )

        candidates = extract_candidates([source])

        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0].subject, "FORMAL_RESUME_TRIGGER_CEREBRO_SELF_EPISTEMIC_READINESS")
        self.assertEqual(candidates[0].predicate, "consumed_on")
        self.assertEqual(candidates[0].object, "2026-04-24")
        self.assertEqual(candidates[0].modality, "temporal")
        self.assertNotIn("first internal epistemic-readiness report", candidates[0].subject)


if __name__ == "__main__":
    unittest.main()
