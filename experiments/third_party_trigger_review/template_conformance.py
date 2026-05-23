from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


TemplateFindingSeverity = Literal["blocker", "warning"]

_FIELD_RE_TEMPLATE = r"{field}\s*=\s*[\"']([^\"']+)[\"']"

_REQUIRED_FIELDS = (
    "target_path",
    "slice_kind",
    "dogfood_value",
    "target_product_value",
    "proof_cost",
    "cleanup_required",
    "target_cerebro_handling",
    "consecutive_target_mutating_slices_before_this",
    "max_target_writes",
    "expected_target_runtime",
    "project_identity",
    "current_state",
    "continuity_delta",
    "decision_ledger",
    "next_work_map",
    "allowed_cerebro_paths",
    "allowed_target_paths",
    "forbidden_cerebro_paths",
    "forbidden_target_paths",
    "authority_impact",
    "runtime_impact",
    "reversibility",
    "rollback",
    "gate_level",
    "promotion_path",
)

_REQUIRED_SECTIONS = (
    "Objective",
    "Why This Target",
    "Source-Set Sufficiency",
    "Target `.cerebro/` Handling",
    "Scope",
    "Explicit Prohibitions",
    "Proof Plan",
    "Cleanup Plan",
    "Rollback Plan",
    "Stop Conditions",
    "Acceptance Criteria",
    "Target Report Shape",
    "Reviewer Evidence",
)

_ENUM_VALUES = {
    "slice_kind": {"management_proof", "target_product_work", "both"},
    "proof_cost": {"none", "low", "medium", "high", "infrastructure-heavy"},
    "target_cerebro_handling": {
        "absent",
        "legacy_external",
        "legacy_compatible",
        "legacy_incompatible",
        "canonical_current",
        "blocked",
    },
    "expected_target_runtime": {
        "none",
        "local-only",
        "local-with-services",
        "cloud-prohibited",
    },
    "authority_impact": {"none", "advisory", "canonical-prohibited"},
    "runtime_impact": {"none", "target-only", "cerebro-runtime-prohibited"},
    "reversibility": {"high", "medium", "low"},
    "rollback": {
        "git-revert",
        "manual-target-revert",
        "delete-generated-files",
        "not-reversible",
    },
    "gate_level": {"G0", "G1", "G2", "G3"},
    "promotion_path": {"none", "requires-consolidation", "requires-separate-trigger"},
}


@dataclass(frozen=True)
class ThirdPartyTriggerTemplateFinding:
    code: str
    severity: TemplateFindingSeverity
    message: str


@dataclass(frozen=True)
class ThirdPartyTriggerTemplateConformance:
    trigger_id: str
    missing_fields: tuple[str, ...]
    invalid_enum_fields: tuple[str, ...]
    missing_sections: tuple[str, ...]
    reviewer_evidence_present: bool
    state_change: str = "none"

    @property
    def findings(self) -> tuple[ThirdPartyTriggerTemplateFinding, ...]:
        findings: list[ThirdPartyTriggerTemplateFinding] = []
        if self.missing_fields:
            findings.append(
                ThirdPartyTriggerTemplateFinding(
                    code="missing_required_fields",
                    severity="blocker",
                    message=", ".join(self.missing_fields),
                )
            )
        if self.invalid_enum_fields:
            findings.append(
                ThirdPartyTriggerTemplateFinding(
                    code="invalid_enum_values",
                    severity="blocker",
                    message=", ".join(self.invalid_enum_fields),
                )
            )
        if self.missing_sections:
            findings.append(
                ThirdPartyTriggerTemplateFinding(
                    code="missing_required_sections",
                    severity="blocker",
                    message=", ".join(self.missing_sections),
                )
            )
        if not self.reviewer_evidence_present:
            findings.append(
                ThirdPartyTriggerTemplateFinding(
                    code="missing_reviewer_evidence",
                    severity="blocker",
                    message=(
                        "Reviewer Evidence must mention experiments.third_party_trigger_review, "
                        "ready_for_human_review, and state_change none."
                    ),
                )
            )
        return tuple(findings)

    @property
    def blocker_count(self) -> int:
        return sum(1 for finding in self.findings if finding.severity == "blocker")

    @property
    def readiness(self) -> str:
        return "template_conformant" if self.blocker_count == 0 else "template_needs_work"


def check_third_party_trigger_template_conformance(
    trigger_id: str, trigger_text: str
) -> ThirdPartyTriggerTemplateConformance:
    normalized = trigger_text.lower()
    missing_fields = tuple(
        field for field in _REQUIRED_FIELDS if not _has_field(normalized, field)
    )
    invalid_enum_fields = tuple(
        field
        for field, allowed_values in _ENUM_VALUES.items()
        if _has_field(normalized, field)
        and _extract_field(trigger_text, field) not in allowed_values
    )
    missing_sections = tuple(
        section for section in _REQUIRED_SECTIONS if not _has_section(trigger_text, section)
    )
    reviewer_evidence_present = (
        "experiments.third_party_trigger_review" in normalized
        and "ready_for_human_review" in normalized
        and re.search(r"state_change\s*[:=]\s*`?[\"']?none", normalized) is not None
    )

    return ThirdPartyTriggerTemplateConformance(
        trigger_id=trigger_id,
        missing_fields=missing_fields,
        invalid_enum_fields=invalid_enum_fields,
        missing_sections=missing_sections,
        reviewer_evidence_present=reviewer_evidence_present,
    )


def _has_field(normalized_text: str, field: str) -> bool:
    return re.search(rf"\b{re.escape(field)}\s*=", normalized_text) is not None


def _extract_field(text: str, field: str) -> str | None:
    match = re.search(_FIELD_RE_TEMPLATE.format(field=re.escape(field)), text)
    return match.group(1) if match else None


def _has_section(text: str, section: str) -> bool:
    return re.search(rf"^##\s+{re.escape(section)}\s*$", text, re.MULTILINE) is not None

