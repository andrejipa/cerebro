from __future__ import annotations

from datetime import datetime, timezone
import inspect
import unittest

from experiments.operational_signals.suggestions import rules as rules_module
from experiments.operational_signals.suggestions.rules import (
    MIN_ABSOLUTE_DRIFT,
    Suggestion,
    classify_confidence,
    detect_broken_canonical_refs,
    detect_current_surface_drift,
    detect_export_surface_gap,
    detect_stale_system_state,
    extract_current_surface_counts,
    extract_required_export_anchors,
    extract_suite_numbers_by_section,
)


FIXED_NOW = datetime(2026, 4, 20, 0, 0, 0, tzinfo=timezone.utc)


class ExtractSuiteNumbersTests(unittest.TestCase):
    def test_extracts_both_sections(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests, `0` failures

## Gate Status

- Last suite result: `550` tests, `0` failures
"""
        result = extract_suite_numbers_by_section(text)
        self.assertEqual(result, {"current_snapshot": 730, "gate_status": 550})

    def test_ignores_prose_numbers(self) -> None:
        text = """
## Current Snapshot

- posture: frozen, roughly 730 rounds logged historically

## Gate Status

- suite status: green
"""
        result = extract_suite_numbers_by_section(text)
        self.assertEqual(result, {})

    def test_first_match_wins_inside_section(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests
- Last suite result: `200` tests (historical stray)

## Gate Status

- Last suite result: `730` tests
"""
        result = extract_suite_numbers_by_section(text)
        self.assertEqual(result["current_snapshot"], 730)

    def test_rejects_non_string_input(self) -> None:
        with self.assertRaises(TypeError):
            extract_suite_numbers_by_section(b"not a string")  # type: ignore[arg-type]


class ClassifyConfidenceTests(unittest.TestCase):
    def test_thresholds(self) -> None:
        self.assertEqual(classify_confidence(5), "low")
        self.assertEqual(classify_confidence(9), "low")
        self.assertEqual(classify_confidence(10), "medium")
        self.assertEqual(classify_confidence(49), "medium")
        self.assertEqual(classify_confidence(50), "high")
        self.assertEqual(classify_confidence(999), "high")

    def test_below_minimum_raises(self) -> None:
        with self.assertRaises(ValueError):
            classify_confidence(0)
        with self.assertRaises(ValueError):
            classify_confidence(MIN_ABSOLUTE_DRIFT - 1)


class DetectBrokenCanonicalRefsTests(unittest.TestCase):
    def test_detects_broken_markdown_link_inside_docs_operations(self) -> None:
        suggestion = detect_broken_canonical_refs(
            source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
            text="See [ghost](DOES_NOT_EXIST.md).",
            now=FIXED_NOW,
        )
        self.assertIsInstance(suggestion, Suggestion)
        assert suggestion is not None
        self.assertEqual(suggestion.suggested_failure_mode, "CONTEXT_NOT_FOUND")
        self.assertEqual(suggestion.confidence, "low")
        self.assertIn(
            "broken_ref=docs/operations/DOES_NOT_EXIST.md",
            suggestion.supporting_signals,
        )
        self.assertEqual(suggestion.reason_flags, ("broken_canonical_ref_detected",))
        self.assertTrue(suggestion.human_review_required)
        self.assertEqual(suggestion.authority, "derived-advisory-only")

    def test_valid_link_is_silent(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
                text="See [state](SYSTEM_STATE.md).",
                now=FIXED_NOW,
            )
        )

    def test_external_mailto_and_fragment_only_refs_are_ignored(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
                text="""
- [external](https://example.com)
- [mail](mailto:ops@example.com)
- [fragment](#current-snapshot)
""",
                now=FIXED_NOW,
            )
        )

    def test_artifact_without_markdown_links_is_silent(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
                text="No markdown links here.",
                now=FIXED_NOW,
            )
        )

    def test_confidence_tier_follows_broken_ref_count(self) -> None:
        medium = detect_broken_canonical_refs(
            source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
            text="""
- [a](BROKEN_A.md)
- [b](BROKEN_B.md)
""",
            now=FIXED_NOW,
        )
        high = detect_broken_canonical_refs(
            source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
            text="""
- [a](BROKEN_A.md)
- [b](BROKEN_B.md)
- [c](BROKEN_C.md)
- [d](BROKEN_D.md)
""",
            now=FIXED_NOW,
        )
        assert medium is not None and high is not None
        self.assertEqual(medium.confidence, "medium")
        self.assertEqual(high.confidence, "high")

    def test_line_suffix_and_anchor_are_normalized_before_exists(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
                text="""
- [state-line](<SYSTEM_STATE.md:12>)
- [adr-anchor](<../adr/ADR-004-local-session-isolated.md#decision>)
""",
                now=FIXED_NOW,
            )
        )

    def test_slash_prefixed_windows_absolute_path_is_treated_as_absolute(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
                text="- [state-abs](</d:/projetos_cli/cerebro/docs/operations/SYSTEM_STATE.md:12>)",
                now=FIXED_NOW,
            )
        )

    def test_absolute_broken_path_emits(self) -> None:
        suggestion = detect_broken_canonical_refs(
            source_artifact="docs/operations/BROKEN_REFS_TRIPWIRE_MANUAL.md",
            text="See [ghost](D:/definitely_missing_tripwire_target/ghost.md).",
            now=FIXED_NOW,
        )
        assert suggestion is not None
        self.assertEqual(suggestion.confidence, "low")
        self.assertIn(
            "broken_ref=D:/definitely_missing_tripwire_target/ghost.md",
            suggestion.supporting_signals,
        )

    def test_out_of_scope_source_is_silent(self) -> None:
        self.assertIsNone(
            detect_broken_canonical_refs(
                source_artifact="docs/reference/out-of-scope.md",
                text="See [ghost](DOES_NOT_EXIST.md).",
                now=FIXED_NOW,
            )
        )

    def test_contract_guards_keep_rule_outside_core_and_cli(self) -> None:
        module_source = inspect.getsource(rules_module)
        rule_source = inspect.getsource(rules_module.detect_broken_canonical_refs)
        self.assertNotRegex(module_source, r"(^|\n)\s*(from|import)\s+core\b")
        self.assertNotRegex(module_source, r"(^|\n)\s*(from|import)\s+cli\b")
        self.assertNotIn("write_text(", rule_source)
        self.assertNotIn("mkdir(", rule_source)


class DetectCurrentSurfaceDriftTests(unittest.TestCase):
    def test_drift_between_two_docs_emits_expected_confidence(self) -> None:
        case = {
            "id": "surface-001",
            "readme_text": "",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "## Current Snapshot\n\n- Last suite result: `720` tests\n",
            "phase_closure_text": "",
        }
        suggestion = detect_current_surface_drift(case=case, now=FIXED_NOW)
        self.assertIsInstance(suggestion, Suggestion)
        assert suggestion is not None
        self.assertEqual(suggestion.suggested_failure_mode, "CONTEXT_AMBIGUOUS")
        self.assertEqual(suggestion.confidence, "medium")
        self.assertEqual(suggestion.source_artifact, "surface-001")

    def test_drift_between_three_plus_docs_emits_max_pairwise_drift(self) -> None:
        case = {
            "id": "surface-002",
            "readme_text": "# README\n\n- Last suite result: `700` tests\n",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `705` tests\n",
            "opportunity_map_text": "## Current Snapshot\n\n- Last suite result: `701` tests\n",
            "phase_closure_text": "## Closure\n\n- Last suite result: `703` tests\n",
        }
        suggestion = detect_current_surface_drift(case=case, now=FIXED_NOW)
        assert suggestion is not None
        self.assertEqual(suggestion.confidence, "low")
        self.assertIn("max_pairwise_drift=5", suggestion.supporting_signals)
        self.assertEqual(
            extract_current_surface_counts(case),
            {
                "readme_text": 700,
                "system_state_text": 705,
                "opportunity_map_text": 701,
                "phase_closure_text": 703,
            },
        )

    def test_counts_that_agree_are_silent(self) -> None:
        case = {
            "id": "surface-003",
            "readme_text": "",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "phase_closure_text": "",
        }
        self.assertIsNone(detect_current_surface_drift(case=case, now=FIXED_NOW))

    def test_less_than_two_sources_is_silent(self) -> None:
        case = {
            "id": "surface-004",
            "readme_text": "",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "",
            "phase_closure_text": "",
        }
        self.assertIsNone(detect_current_surface_drift(case=case, now=FIXED_NOW))

    def test_less_than_two_extractable_counts_is_silent(self) -> None:
        case = {
            "id": "surface-005",
            "readme_text": "# README\n\nNo suite count here.\n",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "",
            "phase_closure_text": "",
        }
        self.assertIsNone(detect_current_surface_drift(case=case, now=FIXED_NOW))

    def test_drift_below_minimum_is_silent(self) -> None:
        case = {
            "id": "surface-006",
            "readme_text": "",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "## Current Snapshot\n\n- Last suite result: `727` tests\n",
            "phase_closure_text": "",
        }
        self.assertIsNone(detect_current_surface_drift(case=case, now=FIXED_NOW))

    def test_supporting_signals_include_one_line_per_source(self) -> None:
        case = {
            "id": "surface-007",
            "readme_text": "# README\n\n- Last suite result: `720` tests\n",
            "system_state_text": "## Current Snapshot\n\n- Last suite result: `730` tests\n",
            "opportunity_map_text": "## Current Snapshot\n\n- Last suite result: `725` tests\n",
            "phase_closure_text": "",
        }
        suggestion = detect_current_surface_drift(case=case, now=FIXED_NOW)
        assert suggestion is not None
        self.assertIn("readme_text_suite_count=720", suggestion.supporting_signals)
        self.assertIn("system_state_text_suite_count=730", suggestion.supporting_signals)
        self.assertIn("opportunity_map_text_suite_count=725", suggestion.supporting_signals)

    def test_contract_guards_keep_rule_outside_core_cli_and_dot_cerebro(self) -> None:
        module_source = inspect.getsource(rules_module)
        rule_source = inspect.getsource(rules_module.detect_current_surface_drift)
        self.assertNotRegex(module_source, r"(^|\n)\s*(from|import)\s+core\b")
        self.assertNotRegex(module_source, r"(^|\n)\s*(from|import)\s+cli\b")
        self.assertNotIn("write_text(", rule_source)


class DetectStaleSystemStateTests(unittest.TestCase):
    def test_real_drift_emits_high_confidence_suggestion(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests

## Gate Status

- Last suite result: `550` tests
"""
        suggestion = detect_stale_system_state(
            source_artifact="sample.md",
            text=text,
            now=FIXED_NOW,
        )
        self.assertIsInstance(suggestion, Suggestion)
        assert suggestion is not None
        self.assertEqual(suggestion.suggested_failure_mode, "STALE_INFORMATION")
        self.assertEqual(suggestion.confidence, "high")
        self.assertIn("suite_count_drift=180", suggestion.supporting_signals)
        self.assertIn("stale_snapshot_detected", suggestion.reason_flags)
        self.assertTrue(suggestion.human_review_required)
        self.assertEqual(suggestion.authority, "derived-advisory-only")

    def test_matching_counts_produce_no_suggestion(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests

## Gate Status

- Last suite result: `730` tests
"""
        self.assertIsNone(
            detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        )

    def test_drift_below_threshold_is_silent(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `732` tests

## Gate Status

- Last suite result: `730` tests
"""
        self.assertIsNone(
            detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        )

    def test_missing_section_silences_rule(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests
"""
        self.assertIsNone(
            detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        )

    def test_reverse_drift_still_emits(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `500` tests

## Gate Status

- Last suite result: `730` tests
"""
        suggestion = detect_stale_system_state(
            source_artifact="s", text=text, now=FIXED_NOW
        )
        assert suggestion is not None
        self.assertEqual(suggestion.confidence, "high")
        self.assertIn("suite_count_drift=-230", suggestion.supporting_signals)

    def test_suggestion_id_and_timestamp_are_deterministic_with_fixed_now(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests

## Gate Status

- Last suite result: `550` tests
"""
        first = detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        second = detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        assert first is not None and second is not None
        self.assertEqual(first.id, second.id)
        self.assertEqual(first.timestamp, second.timestamp)
        self.assertIn("s-", first.id)

    def test_naive_datetime_is_treated_as_utc(self) -> None:
        text = """
## Current Snapshot

- Last suite result: `730` tests

## Gate Status

- Last suite result: `550` tests
"""
        naive_now = datetime(2026, 4, 20, 0, 0, 0)
        suggestion = detect_stale_system_state(
            source_artifact="s", text=text, now=naive_now
        )
        assert suggestion is not None
        self.assertTrue(suggestion.timestamp.endswith("Z"))

    def test_prose_only_numbers_do_not_trigger(self) -> None:
        text = """
The project currently reports 730 tests. Historically it was 550.
"""
        self.assertIsNone(
            detect_stale_system_state(source_artifact="s", text=text, now=FIXED_NOW)
        )


class ExtractRequiredExportAnchorsTests(unittest.TestCase):
    def test_extracts_bullet_items_only(self) -> None:
        text = """
## Required Export Anchors

- approved entrypoint
- current blocker
"""
        self.assertEqual(
            extract_required_export_anchors(text),
            ("approved entrypoint", "current blocker"),
        )

    def test_ignores_free_form_prose(self) -> None:
        text = """
## Required Export Anchors

approved entrypoint, current blocker
"""
        self.assertEqual(extract_required_export_anchors(text), ())


class DetectExportSurfaceGapTests(unittest.TestCase):
    def test_missing_required_anchors_emit_suggestion(self) -> None:
        case = {
            "id": "case-001",
            "text": """
## Required Export Anchors

- approved entrypoint
- next operational step
""",
            "exports_text": """
# status-export

- latest suite result: 730 tests
""",
        }
        suggestion = detect_export_surface_gap(case=case, now=FIXED_NOW)
        self.assertIsInstance(suggestion, Suggestion)
        assert suggestion is not None
        self.assertEqual(suggestion.suggested_failure_mode, "INSUFFICIENT_EXPORT_SURFACE")
        self.assertEqual(suggestion.confidence, "medium")
        self.assertIn("missing_anchor=approved entrypoint", suggestion.supporting_signals)
        self.assertIn("insufficient_surface_detected", suggestion.reason_flags)
        self.assertTrue(suggestion.human_review_required)

    def test_three_missing_anchors_emit_high_confidence(self) -> None:
        case = {
            "id": "case-002",
            "text": """
## Required Export Anchors

- approved entrypoint
- current blocker
- next step
""",
            "exports_text": "# status-export\n\n- latest suite result: 730 tests\n",
        }
        suggestion = detect_export_surface_gap(case=case, now=FIXED_NOW)
        assert suggestion is not None
        self.assertEqual(suggestion.confidence, "high")

    def test_one_anchor_present_silences_rule(self) -> None:
        case = {
            "id": "case-003",
            "text": """
## Required Export Anchors

- approved entrypoint
- current blocker
""",
            "exports_text": """
# handoff-export

- approved entrypoint: README.md
""",
        }
        self.assertIsNone(detect_export_surface_gap(case=case, now=FIXED_NOW))

    def test_missing_anchor_section_silences_rule(self) -> None:
        case = {
            "id": "case-004",
            "text": "The exports should mention the current blocker.",
            "exports_text": "# status-export\n- latest suite result: 730 tests\n",
        }
        self.assertIsNone(detect_export_surface_gap(case=case, now=FIXED_NOW))

    def test_empty_exports_text_silences_rule(self) -> None:
        case = {
            "id": "case-005",
            "text": """
## Required Export Anchors

- approved entrypoint
- current blocker
""",
            "exports_text": "",
        }
        self.assertIsNone(detect_export_surface_gap(case=case, now=FIXED_NOW))

    def test_single_anchor_is_too_weak(self) -> None:
        case = {
            "id": "case-006",
            "text": """
## Required Export Anchors

- current blocker
""",
            "exports_text": "# status-export\n- latest suite result: 730 tests\n",
        }
        self.assertIsNone(detect_export_surface_gap(case=case, now=FIXED_NOW))

    def test_export_surface_ids_are_unique_per_source_artifact(self) -> None:
        base_text = """
## Required Export Anchors

- approved entrypoint
- next operational step
"""
        exports_text = "# status-export\n- latest suite result: 730 tests\n"
        first = detect_export_surface_gap(
            case={"id": "case-a", "text": base_text, "exports_text": exports_text},
            now=FIXED_NOW,
        )
        second = detect_export_surface_gap(
            case={"id": "case-b", "text": base_text, "exports_text": exports_text},
            now=FIXED_NOW,
        )
        assert first is not None and second is not None
        self.assertNotEqual(first.id, second.id)


if __name__ == "__main__":
    unittest.main()
