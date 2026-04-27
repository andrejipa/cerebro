from __future__ import annotations

from datetime import date
import tomllib
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OPERATIONS_DOCS = REPO_ROOT / "docs" / "operations"
REFERENCE_DOCS = REPO_ROOT / "docs" / "reference"
HANDOFF_DOCS = REPO_ROOT / "docs" / "handoffs"

LEGACY_LABELS = (
    "Orquestrador",
    "Mapeador",
    "Quebrador",
    "Organizador",
    "Comprovador",
    "Explorador de Solucoes",
    "Avaliador de Risco",
    "Guardião",
    "Executor",
    "Testador",
    "Auditor",
    "Planejador",
)

CONTEXT_MARKERS = (
    "historical",
    "historically",
    "historical record",
    "historical handoff",
    "historical round evidence",
    "closed round",
    "frozen round",
    "reference-only",
    "for reference",
    "non-canonical",
    "aliases only",
)

AUTHORITY_BOUNDARY_MARKERS = (
    "canonical authority remains",
    "canonical authority stays",
    "not current canonical",
    "not current runtime roles",
    "should not be read as new baseline authority",
    "should not be read as the current canonical role roster",
    "do not override the current role set",
    "for reference, not current canonical role authority",
    "current canonical operational names",
    "current canonical role set",
)

LEGACY_CURRENT_AUTHORITY_TOKENS = (
    "current approval gate",
    "current canonical role",
    "current runtime role",
    "official role roster",
    "official role set",
    "current baseline authority",
    "live approval boundary",
    "canonical approval gate",
)

DOC_RULES = {
    "canonical": {
        "required_markers": {
            "surface_label": (),
            "authority_boundary": (),
        },
        "forbidden_patterns": LEGACY_CURRENT_AUTHORITY_TOKENS,
        "authority_rules": {
            "label_window": 18,
            "boundary_window": 28,
            "legacy_labels_require_qualified_context": True,
        },
    },
    "active_surface": {
        "required_markers": {
            "surface_label": (
                "historical round evidence",
                "active onboarding surface",
            ),
            "authority_boundary": (
                "current canonical operational names",
                "current canonical role set",
                "should not be read as new baseline authority",
            ),
        },
        "forbidden_patterns": LEGACY_CURRENT_AUTHORITY_TOKENS,
        "authority_rules": {
            "label_window": 18,
            "boundary_window": 28,
            "legacy_labels_require_qualified_context": True,
        },
    },
    "reference": {
        "required_markers": {
            "surface_label": (
                "reference-only",
                "for reference",
                "archive-only reference material",
            ),
            "authority_boundary": (
                "canonical authority remains",
                "canonical authority stays",
                "not current canonical",
                "for reference, not current canonical role authority",
            ),
        },
        "forbidden_patterns": LEGACY_CURRENT_AUTHORITY_TOKENS,
        "authority_rules": {
            "label_window": 18,
            "boundary_window": 28,
            "legacy_labels_require_qualified_context": True,
        },
    },
    "historical": {
        "required_markers": {
            "surface_label": (
                "historical",
                "historical record",
                "historical round evidence",
                "closed round",
                "frozen round",
            ),
            "authority_boundary": (
                "non-canonical",
                "do not override the current role set",
                "not current runtime roles",
                "not current canonical",
            ),
        },
        "forbidden_patterns": LEGACY_CURRENT_AUTHORITY_TOKENS,
        "authority_rules": {
            "label_window": 18,
            "boundary_window": 28,
            "legacy_labels_require_qualified_context": True,
        },
    },
    "handoff": {
        "required_markers": {
            "surface_label": (
                "historical handoff",
                "for reference",
            ),
            "authority_boundary": (
                "non-canonical",
                "not current canonical role authority",
                "current canonical role set",
                "do not override the current role set",
                "should not be read as the current canonical role roster",
            ),
        },
        "forbidden_patterns": LEGACY_CURRENT_AUTHORITY_TOKENS,
        "authority_rules": {
            "label_window": 18,
            "boundary_window": 28,
            "legacy_labels_require_qualified_context": True,
        },
    },
}

MARKER_MESSAGES = {
    "surface_label": "missing explicit surface label near document top",
    "authority_boundary": "missing explicit authority/reference boundary near document top",
}


def _normalized_lines(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


def _contains_any(text: str, tokens: tuple[str, ...]) -> bool:
    lowered = text.lower()
    return any(token.lower() in lowered for token in tokens)


def _section_prefix(lines: list[str], index: int) -> str:
    start = index
    while start > 0 and not lines[start].startswith("#"):
        start -= 1
    if not lines[start].startswith("#"):
        start = 0
    return " ".join(line.lower() for line in lines[start : index + 1])


def _top_window(lines: list[str], size: int) -> str:
    return " ".join(line.lower() for line in lines[:size])


def _evaluate_required_markers(
    lines: list[str],
    *,
    rule: dict[str, object],
) -> tuple[list[str], dict[str, bool]]:
    required_markers = rule["required_markers"]
    authority_rules = rule["authority_rules"]
    present_by_marker: dict[str, bool] = {}
    issues: list[str] = []

    for marker_name, markers in required_markers.items():
        if not markers:
            present_by_marker[marker_name] = True
            continue

        window = authority_rules["label_window"] if marker_name == "surface_label" else authority_rules["boundary_window"]
        present = _contains_any(_top_window(lines, window), markers)
        present_by_marker[marker_name] = present
        if not present:
            issues.append(MARKER_MESSAGES[marker_name])

    return issues, present_by_marker


def find_doc_structure_issues(text: str, *, surface_kind: str) -> list[str]:
    if surface_kind not in DOC_RULES:
        raise ValueError(f"unsupported surface_kind: {surface_kind}")

    rule = DOC_RULES[surface_kind]
    lines = _normalized_lines(text)
    lowered_lines = [line.lower() for line in lines]
    issues: list[str] = []
    marker_issues, top_markers = _evaluate_required_markers(lines, rule=rule)
    issues.extend(marker_issues)
    doc_has_context_marker = _contains_any(
        _top_window(lines, rule["authority_rules"]["label_window"]),
        CONTEXT_MARKERS,
    )
    doc_has_authority_boundary = _contains_any(
        _top_window(lines, rule["authority_rules"]["boundary_window"]),
        AUTHORITY_BOUNDARY_MARKERS,
    )

    for index, line in enumerate(lowered_lines):
        if not any(label.lower() in line for label in LEGACY_LABELS):
            continue
        section_prefix = _section_prefix(lines, index)
        section_has_context = _contains_any(section_prefix, CONTEXT_MARKERS)
        section_has_authority_boundary = _contains_any(section_prefix, AUTHORITY_BOUNDARY_MARKERS)
        doc_level_qualification = (
            top_markers["surface_label"] and top_markers["authority_boundary"] and doc_has_context_marker and doc_has_authority_boundary
        )
        section_level_qualification = section_has_context and section_has_authority_boundary
        if rule["authority_rules"]["legacy_labels_require_qualified_context"] and not (
            doc_level_qualification or section_level_qualification
        ):
            issues.append(f"legacy label lacks qualified context in its section near line {index + 1}")
        if _contains_any(line, rule["forbidden_patterns"]):
            issues.append(f"legacy label claims current authority near line {index + 1}")

    return issues


class DocumentationGovernanceStructureTests(unittest.TestCase):
    def assertNoStructuralIssues(self, path: Path, *, surface_kind: str) -> None:
        text = path.read_text(encoding="utf-8")
        issues = find_doc_structure_issues(text, surface_kind=surface_kind)
        self.assertEqual([], issues, msg=f"{path}: {issues}")

    def test_structural_context_guards_real_doc_surfaces(self) -> None:
        guarded_surfaces = {
            REFERENCE_DOCS / "INTEGRATION_SURFACE.md": "reference",
            REFERENCE_DOCS / "EXTERNAL_FRESHNESS_VERIFIER.md": "reference",
            OPERATIONS_DOCS / "REAL_OPERATION_REPORT.md": "historical",
            HANDOFF_DOCS / "HANDOFF_AGENT_TEAM_VALIDATED.md": "handoff",
            HANDOFF_DOCS / "HANDOFF_CURRENT_LAYER_CLOSED.md": "handoff",
            OPERATIONS_DOCS / "WORKSTREAM_BOARD.md": "active_surface",
        }

        for path, surface_kind in guarded_surfaces.items():
            with self.subTest(path=path.name, surface_kind=surface_kind):
                self.assertNoStructuralIssues(path, surface_kind=surface_kind)

    def test_phase_closure_is_inside_documentary_proof_perimeter(self) -> None:
        phase_closure = (OPERATIONS_DOCS / "PHASE_CLOSURE.md").read_text(encoding="utf-8")

        self.assertIn("## Data e estado final", phase_closure)
        self.assertIn("- Estado final da fase: `closed`", phase_closure)
        self.assertIn("- Suite final: `548` testes passando, `6` skips", phase_closure)
        self.assertIn("## Residual aceito explicitamente", phase_closure)
        self.assertIn("## Criterio de reabertura da proxima fase", phase_closure)
        self.assertIn("## Revalidacao Documental De Encerramento", phase_closure)

    def test_freeze_policy_contains_review_cadence_section(self) -> None:
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")

        self.assertIn("## Review Cadence", freeze_policy)
        self.assertIn("docs/operations/freeze_review.toml", freeze_policy)
        self.assertIn("mandatory_review_after_rounds", freeze_policy)
        self.assertIn("mandatory_review_after_days", freeze_policy)
        self.assertIn("trigger_count_since_review", freeze_policy)
        self.assertIn("round_count_since_review", freeze_policy)
        self.assertIn("freeze_confirmed", freeze_policy)
        self.assertIn("freeze_confirmed_with_carveout", freeze_policy)
        self.assertIn("resume_authorized", freeze_policy)
        self.assertIn("resume_pending_evidence", freeze_policy)

    def test_freeze_review_toml_has_expected_shape(self) -> None:
        freeze_review = tomllib.loads((OPERATIONS_DOCS / "freeze_review.toml").read_text(encoding="utf-8"))

        self.assertIn("review", freeze_review)
        self.assertIn("last_outcome", freeze_review)

        review = freeze_review["review"]
        self.assertIn("last_review_date", review)
        self.assertIn("mandatory_review_after_rounds", review)
        self.assertIn("mandatory_review_after_days", review)
        self.assertIn("trigger_count_since_review", review)
        self.assertIn("round_count_since_review", review)

        last_outcome = freeze_review["last_outcome"]
        self.assertIn("verdict", last_outcome)
        self.assertIn("next_review_due", last_outcome)

    def test_freeze_review_toml_values_are_coherent(self) -> None:
        freeze_review = tomllib.loads((OPERATIONS_DOCS / "freeze_review.toml").read_text(encoding="utf-8"))
        review = freeze_review["review"]
        last_outcome = freeze_review["last_outcome"]

        for field in (
            "mandatory_review_after_rounds",
            "mandatory_review_after_days",
            "trigger_count_since_review",
            "round_count_since_review",
        ):
            value = review[field]
            self.assertIsInstance(value, int, msg=f"{field} must be an integer")
            self.assertGreaterEqual(value, 0, msg=f"{field} must be non-negative")

        valid_verdicts = {
            "freeze_confirmed",
            "freeze_confirmed_with_carveout",
            "resume_authorized",
            "resume_pending_evidence",
        }
        self.assertIn(last_outcome["verdict"], valid_verdicts)

        review_date = date.fromisoformat(review["last_review_date"])
        next_review_due = date.fromisoformat(last_outcome["next_review_due"])
        self.assertGreaterEqual(next_review_due, review_date)

    def test_structural_guard_accepts_canonical_surface_without_reference_markers(self) -> None:
        text = """
# AGENT_PROTOCOL

This is the canonical protocol surface.
Current canonical role set remains the seven-role flow in `docs/operations/*`.

## Historical Alias Note

- historical note only; Guardião appears here as a legacy alias from a closed round.
"""

        self.assertEqual([], find_doc_structure_issues(text, surface_kind="canonical"))

    def test_structural_guard_accepts_semantically_correct_rephrasing(self) -> None:
        text = """
# Example Reference

Classification: `ACTIVE SURFACE`.
This page is archive-only reference material.
Canonical authority stays in `docs/operations/*`.
Older labels below are aliases from a closed round and must not be read as the live role roster.

## Archived Trace

- Guardião reviewed the archived round.
"""

        self.assertEqual([], find_doc_structure_issues(text, surface_kind="reference"))

    def test_structural_guard_rejects_words_that_claim_current_legacy_authority(self) -> None:
        text = """
# Example Reference

This page is reference-only and non-canonical.
Canonical authority remains in `docs/operations/*`.

## Archived Trace

- Guardião is the current approval gate for future rounds.
"""

        issues = find_doc_structure_issues(text, surface_kind="reference")

        self.assertTrue(any("legacy label claims current authority" in issue for issue in issues))

    def test_structural_guard_rejects_label_without_authority_boundary(self) -> None:
        text = """
# Example Board

This document is reference-only and non-canonical.

## Later Section

- Guardião permitted the slice.
"""

        issues = find_doc_structure_issues(text, surface_kind="reference")

        self.assertIn("missing explicit authority/reference boundary near document top", issues)

    def test_structural_guard_rejects_authority_boundary_without_surface_label(self) -> None:
        text = """
# Example Reference

Canonical authority remains in `docs/operations/*`.

## Archived Trace

- Guardião reviewed the archived round.
"""

        issues = find_doc_structure_issues(text, surface_kind="reference")

        self.assertIn("missing explicit surface label near document top", issues)

    def test_structural_guard_rejects_wrong_surface_label(self) -> None:
        text = """
# Example Reference

This document is historical and non-canonical.
Canonical authority remains in `docs/operations/*`.

## Archived Trace

- Guardião reviewed the archived round.
"""

        issues = find_doc_structure_issues(text, surface_kind="reference")

        self.assertIn("missing explicit surface label near document top", issues)

    def test_structural_guard_rejects_implicit_legacy_authority_without_qualification(self) -> None:
        text = """
# Example Board

This board tracks current execution state.

## Active Flow

- Guardião approved future rounds after each slice.
"""

        issues = find_doc_structure_issues(text, surface_kind="active_surface")

        self.assertIn("missing explicit surface label near document top", issues)
        self.assertIn("missing explicit authority/reference boundary near document top", issues)
        self.assertTrue(any("legacy label lacks qualified context" in issue for issue in issues))

    def test_structural_guard_accepts_historical_section_with_local_boundary_note(self) -> None:
        text = """
# Handoff

- Note: historical handoff; the approval wording below is non-canonical for current operation.
- Current canonical role set remains elsewhere.

## Decision Needed

- future sensitive actions may proceed only when Guardião explicitly returns `permitido com aprovacao humana`
"""

        self.assertEqual([], find_doc_structure_issues(text, surface_kind="handoff"))



class ObservationCenterRotationTests(unittest.TestCase):
    """Guard that the active observation center stays lean — resolved items must live in the archive."""

    def test_observation_center_has_rotation_policy(self) -> None:
        center = tomllib.loads((OPERATIONS_DOCS / "observation_center.toml").read_bytes())
        self.assertIn(
            "rotation_policy",
            center["center"],
            "observation_center.toml [center] must declare a rotation_policy",
        )

    def test_observation_center_active_file_has_no_resolved_items(self) -> None:
        center = tomllib.loads((OPERATIONS_DOCS / "observation_center.toml").read_bytes())
        resolved = [o["id"] for o in center.get("observations", []) if o.get("status") == "resolved"]
        self.assertEqual(
            [],
            resolved,
            f"observation_center.toml must not contain resolved items — rotate them to "
            f"observation_center_archive.toml. Found: {resolved}",
        )

    def test_observation_center_archive_is_non_authoritative(self) -> None:
        archive_path = OPERATIONS_DOCS / "observation_center_archive.toml"
        if not archive_path.exists():
            return
        archive = tomllib.loads(archive_path.read_bytes())
        self.assertTrue(
            archive.get("archive", {}).get("non_authoritative", False),
            "observation_center_archive.toml must declare archive.non_authoritative = true",
        )


class OperationalDocSizeLimitTests(unittest.TestCase):
    """Guard against context rot — operational docs must stay within readable limits.

    These limits exist because LLM attention degrades as context grows (context rot).
    Exceeding a limit means a docs-only reconciliation round is overdue.

    To fix a failure: rotate historical content to the corresponding _HISTORY.md file
    and move resolved observations to observation_center_archive.toml.
    """

    def _check_limit(self, filename: str, max_lines: int, rationale: str) -> None:
        path = OPERATIONS_DOCS / filename
        if not path.exists():
            return
        lines = len(path.read_text(encoding="utf-8").splitlines())
        self.assertLessEqual(
            lines,
            max_lines,
            f"{filename} has {lines} lines (limit: {max_lines}).\n"
            f"Reason: {rationale}\n"
            f"Fix: run a docs-only reconciliation round to rotate historical content.",
        )

    def test_observation_center_size(self) -> None:
        self._check_limit(
            "observation_center.toml", 150,
            "active queue only — resolved items belong in observation_center_archive.toml",
        )

    def test_system_state_size(self) -> None:
        self._check_limit(
            "SYSTEM_STATE.md", 200,
            "current snapshot only — historical sections belong in SYSTEM_STATE_HISTORY.md",
        )

    def test_opportunity_map_size(self) -> None:
        self._check_limit(
            "OPPORTUNITY_MAP.md", 400,
            "current snapshot + pinned governance sections — chronology belongs in OPPORTUNITY_MAP_HISTORY.md",
        )


if __name__ == "__main__":
    unittest.main()
