from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any


HUMAN_DECISION_TAXONOMY_SCHEMA_VERSION = "1"
HUMAN_DECISION_TAXONOMY_AUTHORITY = (
    "non-authoritative; advisory human decision taxonomy evidence only"
)

HUMAN_DECISION_ORDER = (
    "none",
    "acknowledge",
    "approve_baseline_refresh",
    "adjudicate_conflict",
    "provide_missing_evidence",
    "review_blockers",
)

_VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "advisory_report_allowed",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class HumanDecisionTaxonomyEntry:
    decision: str
    meaning: str
    compatible_action_readiness: tuple[str, ...]
    escalation_level: str
    required_evidence: tuple[str, ...]
    allowed_next_actions: tuple[str, ...]
    forbidden_interpretations: tuple[str, ...]
    state_change: str = "none"
    authority: str = HUMAN_DECISION_TAXONOMY_AUTHORITY
    can_mutate_state: bool = False
    can_grant_permission: bool = False

    def __post_init__(self) -> None:
        if self.decision not in HUMAN_DECISION_ORDER:
            raise ValueError(f"unknown human decision: {self.decision}")
        if self.state_change != "none":
            raise ValueError("human decision taxonomy entries must not change state")
        if self.authority != HUMAN_DECISION_TAXONOMY_AUTHORITY:
            raise ValueError(f"unsupported taxonomy authority: {self.authority}")
        if self.can_mutate_state:
            raise ValueError("human decision taxonomy entries must not mutate state")
        if self.can_grant_permission:
            raise ValueError("human decision taxonomy entries must not grant permission")
        _require_non_empty(self.meaning, "meaning")
        _require_non_empty_tuple(
            self.compatible_action_readiness, "compatible_action_readiness"
        )
        _require_non_empty_tuple(self.required_evidence, "required_evidence")
        _require_non_empty_tuple(self.allowed_next_actions, "allowed_next_actions")
        _require_non_empty_tuple(
            self.forbidden_interpretations, "forbidden_interpretations"
        )
        for readiness in self.compatible_action_readiness:
            if readiness not in _VALID_ACTION_READINESS:
                raise ValueError(f"unsupported compatible action readiness: {readiness}")
        if "treat decision as permission" not in self.forbidden_interpretations:
            raise ValueError("taxonomy entries must forbid treating decisions as permission")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "meaning": self.meaning,
            "compatible_action_readiness": list(self.compatible_action_readiness),
            "escalation_level": self.escalation_level,
            "required_evidence": list(self.required_evidence),
            "allowed_next_actions": list(self.allowed_next_actions),
            "forbidden_interpretations": list(self.forbidden_interpretations),
            "state_change": self.state_change,
            "authority": self.authority,
            "can_mutate_state": self.can_mutate_state,
            "can_grant_permission": self.can_grant_permission,
        }


@dataclass(frozen=True)
class HumanDecisionInterpretation:
    decision: str
    action_readiness: str
    compatible: bool
    escalation_level: str
    allowed_next_actions: tuple[str, ...]
    required_evidence: tuple[str, ...]
    forbidden_interpretations: tuple[str, ...]
    issues: tuple[str, ...]
    state_change: str = "none"
    authority: str = HUMAN_DECISION_TAXONOMY_AUTHORITY

    def __post_init__(self) -> None:
        if self.decision not in HUMAN_DECISION_ORDER:
            raise ValueError(f"unknown human decision: {self.decision}")
        if self.action_readiness not in _VALID_ACTION_READINESS:
            raise ValueError(f"unknown action_readiness: {self.action_readiness}")
        if self.state_change != "none":
            raise ValueError("human decision interpretations must not change state")
        if self.authority != HUMAN_DECISION_TAXONOMY_AUTHORITY:
            raise ValueError(f"unsupported interpretation authority: {self.authority}")

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "action_readiness": self.action_readiness,
            "compatible": self.compatible,
            "escalation_level": self.escalation_level,
            "allowed_next_actions": list(self.allowed_next_actions),
            "required_evidence": list(self.required_evidence),
            "forbidden_interpretations": list(self.forbidden_interpretations),
            "issues": list(self.issues),
            "state_change": self.state_change,
            "authority": self.authority,
        }


@dataclass(frozen=True)
class HumanDecisionTaxonomyReport:
    entries: tuple[HumanDecisionTaxonomyEntry, ...]
    state_change: str = "none"
    authority: str = HUMAN_DECISION_TAXONOMY_AUTHORITY
    taxonomy_role: str = "advisory handoff decision vocabulary only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("human decision taxonomy must not change state")
        if self.authority != HUMAN_DECISION_TAXONOMY_AUTHORITY:
            raise ValueError(f"unsupported taxonomy report authority: {self.authority}")
        decisions = tuple(entry.decision for entry in self.entries)
        if len(set(decisions)) != len(decisions):
            raise ValueError("human decision taxonomy decisions must be unique")
        if decisions != HUMAN_DECISION_ORDER:
            raise ValueError(
                "human decision taxonomy must contain the closed decision set in stable order"
            )
        for entry in self.entries:
            if entry.state_change != "none":
                raise ValueError("taxonomy entries must preserve state_change none")
            if entry.can_mutate_state or entry.can_grant_permission:
                raise ValueError("taxonomy entries must remain non-authoritative")

    def entry_for(self, decision: str) -> HumanDecisionTaxonomyEntry:
        for entry in self.entries:
            if entry.decision == decision:
                return entry
        raise ValueError(f"unknown human decision: {decision}")

    def interpret(self, decision: str, action_readiness: str) -> HumanDecisionInterpretation:
        entry = self.entry_for(decision)
        if action_readiness not in _VALID_ACTION_READINESS:
            raise ValueError(f"unknown action_readiness: {action_readiness}")
        compatible = action_readiness in entry.compatible_action_readiness
        issues: tuple[str, ...]
        if compatible:
            issues = ()
        else:
            issues = (
                "decision/action_readiness pair is inconsistent",
                "do not act from this pair without new evidence or human adjudication",
            )
        return HumanDecisionInterpretation(
            decision=decision,
            action_readiness=action_readiness,
            compatible=compatible,
            escalation_level=entry.escalation_level,
            allowed_next_actions=entry.allowed_next_actions,
            required_evidence=entry.required_evidence,
            forbidden_interpretations=entry.forbidden_interpretations,
            issues=issues,
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": HUMAN_DECISION_TAXONOMY_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "taxonomy_role": self.taxonomy_role,
            "summary": {
                "decision_count": len(self.entries),
                "decision_order": list(HUMAN_DECISION_ORDER),
                "all_entries_can_mutate_state": False,
                "all_entries_can_grant_permission": False,
            },
            "entries": [entry.to_dict() for entry in self.entries],
            "compatibility_matrix": {
                entry.decision: list(entry.compatible_action_readiness)
                for entry in self.entries
            },
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "human_decision_is_not_permission": True,
                "taxonomy_is_not_memory": True,
                "taxonomy_is_not_authority": True,
                "taxonomy_is_not_runtime_gate": True,
                "taxonomy_is_not_claim_graph": True,
                "compatible_pair_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "interpret a handoff decision/readiness pair",
                    "identify required evidence for a human decision",
                    "identify forbidden interpretations",
                    "recommend a future trigger when a decision needs action",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat a human decision as permission",
                    "treat a compatible pair as permission",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_human_decision_taxonomy() -> HumanDecisionTaxonomyReport:
    return HumanDecisionTaxonomyReport(
        entries=(
            HumanDecisionTaxonomyEntry(
                decision="none",
                meaning=(
                    "No human decision is requested because the advisory evidence "
                    "contains no conflict, missing evidence, drift approval, or blocker."
                ),
                compatible_action_readiness=("no_action",),
                escalation_level="none",
                required_evidence=(
                    "clean metacognitive handoff",
                    "zero active conflicts",
                    "zero insufficient findings",
                    "zero blockers",
                ),
                allowed_next_actions=(
                    "record that no human decision is currently requested",
                    "continue observation in derived layers",
                    "open a future trigger only if separate evidence appears",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "treat clean advisory evidence as canonical truth",
                    "skip future gates because no action is requested now",
                ),
            ),
            HumanDecisionTaxonomyEntry(
                decision="acknowledge",
                meaning=(
                    "A human may acknowledge advisory evidence that is visible but not "
                    "severe enough to require approval, adjudication, or blocker review."
                ),
                compatible_action_readiness=("advisory_report_allowed", "observe_only"),
                escalation_level="operator_acknowledgement",
                required_evidence=(
                    "advisory report allowed readiness",
                    "no active blocker",
                    "no authority promotion requested",
                ),
                allowed_next_actions=(
                    "record acknowledgement in a future human-facing note",
                    "keep the artifact advisory",
                    "open a separate trigger if the acknowledgement implies work",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "treat acknowledgement as approval",
                    "promote advisory evidence to authority",
                ),
            ),
            HumanDecisionTaxonomyEntry(
                decision="approve_baseline_refresh",
                meaning=(
                    "A human may approve refreshing a derived replay baseline after "
                    "material drift is visible and blockers are absent."
                ),
                compatible_action_readiness=("human_approval_required",),
                escalation_level="human_approval",
                required_evidence=(
                    "material drift or refresh candidate",
                    "no regression",
                    "no high or blocking protocol self-audit candidate",
                    "explicit human approval before any refresh",
                ),
                allowed_next_actions=(
                    "open a separate baseline-refresh trigger",
                    "prepare a derived baseline refresh audit packet",
                    "apply only the approved derived baseline refresh inside that trigger",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "refresh the baseline automatically",
                    "treat replay freshness as canonical truth",
                    "mutate canonical state",
                ),
            ),
            HumanDecisionTaxonomyEntry(
                decision="adjudicate_conflict",
                meaning=(
                    "A human must resolve or explicitly park conflicting advisory "
                    "evidence before an agent treats the affected conclusion as usable."
                ),
                compatible_action_readiness=("human_approval_required",),
                escalation_level="human_adjudication",
                required_evidence=(
                    "named conflict",
                    "conflicting source evidence",
                    "authority and freshness context for each side",
                ),
                allowed_next_actions=(
                    "request human conflict adjudication",
                    "mark conflict unresolved in advisory output",
                    "open a separate promotion or demotion trigger after adjudication",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "resolve conflict by recency alone",
                    "hide unresolved conflict behind a green summary",
                    "promote or demote authority automatically",
                ),
            ),
            HumanDecisionTaxonomyEntry(
                decision="provide_missing_evidence",
                meaning=(
                    "The agent lacks enough evidence and must seek bounded evidence "
                    "rather than infer from silence."
                ),
                compatible_action_readiness=("human_approval_required",),
                escalation_level="evidence_request",
                required_evidence=(
                    "insufficient finding or missing-evidence note",
                    "description of the missing source or fact",
                    "explicit statement that silence is not negative evidence",
                ),
                allowed_next_actions=(
                    "ask for the missing evidence",
                    "read a newly approved bounded source in a future derived run",
                    "rerun the advisory report after evidence is supplied",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "infer falsehood from absent evidence",
                    "invent a source",
                    "import or register sources automatically",
                ),
            ),
            HumanDecisionTaxonomyEntry(
                decision="review_blockers",
                meaning=(
                    "The current path is blocked by protocol risk, regression, or "
                    "another high-severity advisory signal and must stop."
                ),
                compatible_action_readiness=("blocked",),
                escalation_level="blocker_review",
                required_evidence=(
                    "blocked readiness",
                    "blocker reason",
                    "rollback or stop condition context",
                    "explicit human review before continuation",
                ),
                allowed_next_actions=(
                    "stop the current action path",
                    "inspect blocker evidence",
                    "open a corrective trigger before retrying",
                ),
                forbidden_interpretations=(
                    "treat decision as permission",
                    "continue with best effort",
                    "override blocker silently",
                    "demote canonical behavior automatically",
                ),
            ),
        )
    )


def interpret_handoff_decision(
    decision: str,
    action_readiness: str,
    taxonomy: HumanDecisionTaxonomyReport | None = None,
) -> HumanDecisionInterpretation:
    report = taxonomy if taxonomy is not None else build_human_decision_taxonomy()
    return report.interpret(decision, action_readiness)


def render_human_decision_taxonomy_json(report: HumanDecisionTaxonomyReport) -> str:
    return json.dumps(report.to_dict(), indent=2, sort_keys=True) + "\n"


def render_human_decision_taxonomy_markdown(report: HumanDecisionTaxonomyReport) -> str:
    lines = [
        "# Epistemic Readiness Human Decision Taxonomy",
        "",
        "## Boundary",
        "",
        f"- state_change: {report.state_change}",
        f"- authority: {report.authority}",
        f"- taxonomy_role: {report.taxonomy_role}",
        "- human_decision_is_not_permission: true",
        "- compatible_pair_is_not_permission: true",
        "- taxonomy_is_not_memory: true",
        "- taxonomy_is_not_authority: true",
        "- taxonomy_is_not_runtime_gate: true",
        "- taxonomy_is_not_claim_graph: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Summary",
        "",
        f"- decision_count: `{len(report.entries)}`",
        "- every entry has `can_mutate_state=false`",
        "- every entry has `can_grant_permission=false`",
        "",
        "## Decision Matrix",
        "",
        "| Decision | Compatible Readiness | Escalation |",
        "|---|---|---|",
    ]
    for entry in report.entries:
        readiness = ", ".join(f"`{item}`" for item in entry.compatible_action_readiness)
        lines.append(f"| `{entry.decision}` | {readiness} | `{entry.escalation_level}` |")
    lines.extend(["", "## Entries", ""])
    for entry in report.entries:
        lines.extend(
            [
                f"### {entry.decision}",
                "",
                f"- meaning: {entry.meaning}",
                f"- escalation_level: `{entry.escalation_level}`",
                "- can_mutate_state: `false`",
                "- can_grant_permission: `false`",
                "",
                "Required evidence:",
                "",
            ]
        )
        lines.extend(f"- {item}" for item in entry.required_evidence)
        lines.extend(["", "Allowed next actions:", ""])
        lines.extend(f"- {item}" for item in entry.allowed_next_actions)
        lines.extend(["", "Forbidden interpretations:", ""])
        lines.extend(f"- {item}" for item in entry.forbidden_interpretations)
        lines.append("")
    lines.extend(
        [
            "## Must Not Apply",
            "",
            "- mutate state",
            "- register sources",
            "- update replay baseline",
            "- write memory automatically",
            "- act as runtime gate",
            "- create canonical claim graph",
            "- promote or demote authority",
            "- treat a human decision as permission",
            "- treat a compatible pair as permission",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _require_non_empty(value: str, field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must be non-empty")


def _require_non_empty_tuple(value: tuple[str, ...], field_name: str) -> None:
    if not value:
        raise ValueError(f"{field_name} must be non-empty")
    for item in value:
        if not item:
            raise ValueError(f"{field_name} entries must be non-empty")
