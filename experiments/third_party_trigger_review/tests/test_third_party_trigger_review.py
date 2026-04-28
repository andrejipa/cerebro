from __future__ import annotations

import unittest

from experiments.third_party_trigger_review import (
    ThirdPartyTriggerReviewInput,
    check_third_party_trigger_template_conformance,
    render_review_markdown,
    review_third_party_trigger,
    summarize_trigger_reviews,
)


COMPLETE_TRIGGER = """
[third_party]
target_path = "D:\\projetos_cli\\pessoais\\rpg_caminhada"
slice_kind = "both"
dogfood_value = "Proves Cerebro can review target validation before product work."
proof_cost = "medium"
cleanup_required = true
target_cerebro_handling = "canonical_current"
allowed_target_paths = ["src/example.ts"]
forbidden_target_paths = [".cerebro/", "supabase/migrations/"]
forbidden_cerebro_paths = ["core/", "cli/", "extensions/", "tests/", ".cerebro/"]

[source_roles]
project_identity = "README.md"
current_state = "SYSTEM_STATE.md"
continuity_delta = "HANDOFF.md"
decision_ledger = "DECISIONS.md"
next_work_map = "NEXT.md"

## Rollback
git revert target patch

## Stop Conditions
Stop on schema, cloud, target .cerebro, or runtime boundary drift.
"""


TEMPLATE_CONFORMANT_TRIGGER = """
# FORMAL RESUME TRIGGER - RPG Caminhada Example Slice

status: active
created_at: 2026-04-25

## Structured Third-Party Block

```toml
[third_party]
target_path = "D:/projetos_cli/pessoais/rpg_caminhada"
slice_kind = "both"
dogfood_value = "Proves Cerebro can manage target validation without role drift."
target_product_value = "Small target improvement."
proof_cost = "medium"
cleanup_required = true
target_cerebro_handling = "canonical_current"
consecutive_target_mutating_slices_before_this = 1
max_target_writes = 3
expected_target_runtime = "local-only"

[source_roles]
project_identity = "README.md"
current_state = "docs/SYSTEM_STATE.md"
continuity_delta = "docs/HANDOFF.md"
decision_ledger = "docs/DECISIONS.md"
next_work_map = "docs/NEXT.md"
architecture_rules = "none"
validation_surface = "package.json"

[boundaries]
allowed_cerebro_paths = ["docs/operations/FORMAL_RESUME_TRIGGER_EXAMPLE.md"]
allowed_target_paths = ["D:/projetos_cli/pessoais/rpg_caminhada/src/example.ts"]
forbidden_cerebro_paths = ["core/", "cli/", "extensions/", "tests/", "core/schema.py", ".cerebro/"]
forbidden_target_paths = ["D:/projetos_cli/pessoais/rpg_caminhada/.cerebro/"]

[risk_budget]
authority_impact = "none"
runtime_impact = "target-only"
reversibility = "high"
rollback = "manual-target-revert"
gate_level = "G2"
promotion_path = "requires-consolidation"
```

## Objective

Target objective: prove one small target behavior.
Cerebro objective: prove trigger review quality.

## Why This Target

Low-risk local target.

## Source-Set Sufficiency

All source roles are present.

## Target `.cerebro/` Handling

canonical_current

## Scope

Allowed Cerebro files and target files are listed separately.

## Explicit Prohibitions

Do not touch Cerebro runtime or target `.cerebro/`.

## Proof Plan

target_typecheck and cerebro_arch_docs

## Cleanup Plan

Stop local services and preserve report evidence.

## Rollback Plan

Manual target revert.

## Stop Conditions

Stop on gate red or whitelist expansion.

## Acceptance Criteria

Focused validation passes.

## Target Report Shape

Boundary, target change, local proof, validation, cleanup.

## Reviewer Evidence

- `experiments.third_party_trigger_review`: pending before execution
- expected readiness: `ready_for_human_review`
- state_change: `none`
"""


class ThirdPartyTriggerReviewTests(unittest.TestCase):
    def test_complete_trigger_is_ready_for_human_review(self) -> None:
        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(
                trigger_id="complete",
                trigger_text=COMPLETE_TRIGGER,
                consecutive_target_mutating_slices=1,
                target_has_cerebro=True,
            )
        )

        self.assertEqual(report.readiness, "ready_for_human_review")
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.state_change, "none")

    def test_missing_dogfood_value_blocks_review(self) -> None:
        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(
                trigger_id="missing-dogfood",
                trigger_text=COMPLETE_TRIGGER.replace("dogfood_value", "product_value"),
            )
        )

        self.assertEqual(report.readiness, "needs_missing_fields")
        self.assertIn("missing_dogfood_value", {finding.code for finding in report.findings})

    def test_target_cerebro_ambiguity_blocks_when_target_has_runtime(self) -> None:
        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(
                trigger_id="missing-target-cerebro-handling",
                trigger_text=COMPLETE_TRIGGER.replace(
                    'target_cerebro_handling = "canonical_current"\n',
                    "",
                ),
                target_has_cerebro=True,
            )
        )

        self.assertEqual(report.readiness, "blocked_target_cerebro_ambiguity")
        self.assertIn(
            "blocked_target_cerebro_ambiguity",
            {finding.code for finding in report.findings},
        )

    def test_consecutive_target_slices_require_consolidation(self) -> None:
        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(
                trigger_id="too-many-target-slices",
                trigger_text=COMPLETE_TRIGGER,
                consecutive_target_mutating_slices=3,
            )
        )

        self.assertEqual(report.readiness, "consolidation_required")
        self.assertEqual(report.consecutive_target_slice_risk, "consolidation_required")

    def test_runtime_boundary_drift_blocks(self) -> None:
        trigger = """
[third_party]
target_path = "D:\\target"
slice_kind = "both"
dogfood_value = "test"
proof_cost = "low"
cleanup_required = true
target_cerebro_handling = "blocked"
allowed_target_paths = ["core/schema.py"]

[source_roles]
project_identity = "README.md"
current_state = "SYSTEM_STATE.md"
continuity_delta = "HANDOFF.md"
decision_ledger = "DECISIONS.md"
next_work_map = "NEXT.md"

## Rollback
git revert

## Stop Conditions
Stop on failure.
"""

        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(trigger_id="runtime-drift", trigger_text=trigger)
        )

        self.assertEqual(report.readiness, "blocked_runtime_boundary")
        self.assertIn("blocked_runtime_boundary", {finding.code for finding in report.findings})

    def test_legacy_trigger_wording_extracts_target_and_prohibitions(self) -> None:
        trigger = """
# FORMAL RESUME TRIGGER - RPG Caminhada Legacy Slice

## Scope

Allowed target files under `D:\\projetos_cli\\pessoais\\rpg_caminhada\\`:

- `src/features/app/state/GameFlowContext.tsx`

## Explicit Prohibitions

- Do not modify Cerebro `core/`, `cli/`, `extensions/`, `tests/`,
  `core/schema.py`, or `.cerebro/state.json`.
- Do not modify target `.cerebro/`.

## Stop Conditions

Stop if the needed fix requires Cerebro runtime code.

## Risk Budget

```toml
rollback = "manual target revert"
```
"""

        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(trigger_id="legacy", trigger_text=trigger)
        )

        self.assertEqual(report.target_path, "D:\\projetos_cli\\pessoais\\rpg_caminhada")
        self.assertTrue(report.forbidden_paths_declared)
        self.assertNotIn("blocked_runtime_boundary", {finding.code for finding in report.findings})

    def test_render_includes_state_change_none_and_advisory_boundary(self) -> None:
        report = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(trigger_id="complete", trigger_text=COMPLETE_TRIGGER)
        )
        rendered = render_review_markdown(report)

        self.assertIn("state_change: `none`", rendered)
        self.assertIn("advisory evidence only", rendered)

    def test_retrospective_summarizes_multiple_reviews_without_authority(self) -> None:
        ready = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(trigger_id="ready", trigger_text=COMPLETE_TRIGGER)
        )
        missing = review_third_party_trigger(
            ThirdPartyTriggerReviewInput(
                trigger_id="missing-dogfood",
                trigger_text=COMPLETE_TRIGGER.replace("dogfood_value", "product_value"),
            )
        )

        retrospective = summarize_trigger_reviews((ready, missing))

        self.assertEqual(retrospective.review_count, 2)
        self.assertEqual(
            dict(retrospective.readiness_counts),
            {"needs_missing_fields": 1, "ready_for_human_review": 1},
        )
        self.assertEqual(dict(retrospective.finding_code_counts)["missing_dogfood_value"], 1)
        self.assertEqual(retrospective.blocker_total, 1)
        self.assertEqual(retrospective.state_change, "none")

    def test_template_conformance_accepts_complete_template_shape(self) -> None:
        report = check_third_party_trigger_template_conformance(
            "complete-template", TEMPLATE_CONFORMANT_TRIGGER
        )

        self.assertEqual(report.readiness, "template_conformant")
        self.assertEqual(report.blocker_count, 0)
        self.assertEqual(report.state_change, "none")

    def test_template_conformance_reports_missing_required_fields(self) -> None:
        report = check_third_party_trigger_template_conformance(
            "missing-fields",
            TEMPLATE_CONFORMANT_TRIGGER.replace(
                'dogfood_value = "Proves Cerebro can manage target validation without role drift."\n',
                "",
            ).replace('allowed_target_paths = ["D:/projetos_cli/pessoais/rpg_caminhada/src/example.ts"]\n', ""),
        )

        self.assertEqual(report.readiness, "template_needs_work")
        self.assertIn("dogfood_value", report.missing_fields)
        self.assertIn("allowed_target_paths", report.missing_fields)
        self.assertIn("missing_required_fields", {finding.code for finding in report.findings})

    def test_template_conformance_reports_invalid_enum_values(self) -> None:
        report = check_third_party_trigger_template_conformance(
            "invalid-enums",
            TEMPLATE_CONFORMANT_TRIGGER.replace('slice_kind = "both"', 'slice_kind = "target-only"')
            .replace('gate_level = "G2"', 'gate_level = "G4"'),
        )

        self.assertEqual(report.readiness, "template_needs_work")
        self.assertIn("slice_kind", report.invalid_enum_fields)
        self.assertIn("gate_level", report.invalid_enum_fields)
        self.assertIn("invalid_enum_values", {finding.code for finding in report.findings})

    def test_template_conformance_reports_missing_sections_and_reviewer_evidence(self) -> None:
        report = check_third_party_trigger_template_conformance(
            "missing-sections",
            TEMPLATE_CONFORMANT_TRIGGER.replace("## Proof Plan\n", "")
            .replace("## Reviewer Evidence\n", "")
            .replace("- state_change: `none`\n", ""),
        )

        self.assertEqual(report.readiness, "template_needs_work")
        self.assertIn("Proof Plan", report.missing_sections)
        self.assertIn("Reviewer Evidence", report.missing_sections)
        self.assertFalse(report.reviewer_evidence_present)
        self.assertIn("missing_reviewer_evidence", {finding.code for finding in report.findings})


if __name__ == "__main__":
    unittest.main()
