from __future__ import annotations

from dataclasses import dataclass
import json
from typing import Any, Mapping

from .baseline_lifecycle import BASELINE_LIFECYCLE_AUTHORITY, BASELINE_LIFECYCLE_SCHEMA_VERSION
from .decision_taxonomy_conformance import (
    DECISION_TAXONOMY_CONFORMANCE_AUTHORITY,
    DECISION_TAXONOMY_CONFORMANCE_SCHEMA_VERSION,
)
from .drift_policy import DRIFT_POLICY_AUTHORITY, DRIFT_POLICY_SCHEMA_VERSION
from .metacognitive_handoff import (
    METACOGNITIVE_HANDOFF_AUTHORITY,
    METACOGNITIVE_HANDOFF_SCHEMA_VERSION,
)


OPERATOR_DECISION_PACKET_SCHEMA_VERSION = "1"
OPERATOR_DECISION_PACKET_AUTHORITY = (
    "non-authoritative; advisory operator decision packet evidence only"
)

_VALID_HUMAN_DECISIONS = {
    "none",
    "acknowledge",
    "approve_baseline_refresh",
    "review_blockers",
    "adjudicate_conflict",
    "provide_missing_evidence",
}
_VALID_ACTION_READINESS = {
    "no_action",
    "observe_only",
    "propose_only",
    "advisory_report_allowed",
    "derived_experiment_allowed",
    "canonical_change_requires_trigger",
    "human_approval_required",
    "blocked",
}


@dataclass(frozen=True)
class OperatorDecisionPacket:
    recommended_human_decision: str
    action_readiness: str
    decision_summary: str
    known: tuple[str, ...]
    unknown: tuple[str, ...]
    blockers: tuple[str, ...]
    missing_evidence: tuple[str, ...]
    risk_notes: tuple[str, ...]
    source_evidence: tuple[str, ...]
    conformance_passed: bool
    source_count: int
    candidates_extracted: int
    findings_evaluated: int
    ready_count: int
    blocked_count: int
    insufficient_count: int
    drift_policy_classification: str
    drift_policy_required_human_action: str
    baseline_lifecycle_recommendation: str
    baseline_lifecycle_required_human_action: str
    state_change: str = "none"
    authority: str = OPERATOR_DECISION_PACKET_AUTHORITY
    packet_role: str = "advisory evidence-to-action packet only"

    def __post_init__(self) -> None:
        if self.state_change != "none":
            raise ValueError("operator decision packets must not change state")
        if self.authority != OPERATOR_DECISION_PACKET_AUTHORITY:
            raise ValueError(f"unsupported operator packet authority: {self.authority}")
        if self.recommended_human_decision not in _VALID_HUMAN_DECISIONS:
            raise ValueError(
                f"invalid recommended_human_decision: {self.recommended_human_decision}"
            )
        if self.action_readiness not in _VALID_ACTION_READINESS:
            raise ValueError(f"invalid action_readiness: {self.action_readiness}")
        if not self.decision_summary:
            raise ValueError("operator packet decision_summary must be non-empty")
        if self.action_readiness == "blocked" and not self.blockers:
            raise ValueError("blocked operator packets must expose blockers")
        if not self.source_evidence:
            raise ValueError("operator packets require source evidence")
        for field_name, value in (
            ("source_count", self.source_count),
            ("candidates_extracted", self.candidates_extracted),
            ("findings_evaluated", self.findings_evaluated),
            ("ready_count", self.ready_count),
            ("blocked_count", self.blocked_count),
            ("insufficient_count", self.insufficient_count),
        ):
            if value < 0:
                raise ValueError(f"{field_name} must be non-negative")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": OPERATOR_DECISION_PACKET_SCHEMA_VERSION,
            "state_change": self.state_change,
            "authority": self.authority,
            "packet_role": self.packet_role,
            "summary": {
                "recommended_human_decision": self.recommended_human_decision,
                "action_readiness": self.action_readiness,
                "decision_summary": self.decision_summary,
                "conformance_passed": self.conformance_passed,
                "source_count": self.source_count,
                "candidates_extracted": self.candidates_extracted,
                "findings_evaluated": self.findings_evaluated,
                "ready_count": self.ready_count,
                "blocked_count": self.blocked_count,
                "insufficient_count": self.insufficient_count,
                "known_count": len(self.known),
                "unknown_count": len(self.unknown),
                "blocker_count": len(self.blockers),
                "missing_evidence_count": len(self.missing_evidence),
                "risk_note_count": len(self.risk_notes),
            },
            "source_disposition": {
                "drift_policy_classification": self.drift_policy_classification,
                "drift_policy_required_human_action": self.drift_policy_required_human_action,
                "baseline_lifecycle_recommendation": self.baseline_lifecycle_recommendation,
                "baseline_lifecycle_required_human_action": (
                    self.baseline_lifecycle_required_human_action
                ),
            },
            "known": list(self.known),
            "unknown": list(self.unknown),
            "blockers": list(self.blockers),
            "missing_evidence": list(self.missing_evidence),
            "risk_notes": list(self.risk_notes),
            "source_evidence": list(self.source_evidence),
            "guardrails": {
                "registered_is_not_true": True,
                "retrieved_is_not_relevant": True,
                "remembered_is_not_trusted": True,
                "silence_is_not_negative_evidence": True,
                "operator_packet_is_not_permission": True,
                "operator_packet_is_not_memory": True,
                "operator_packet_is_not_authority": True,
                "operator_packet_is_not_runtime_gate": True,
                "operator_packet_is_not_claim_graph": True,
                "conformance_pass_is_not_permission": True,
            },
            "boundary": {
                "may_suggest": [
                    "summarize current advisory evidence",
                    "surface blockers and missing evidence",
                    "request a human decision",
                    "recommend a future trigger when evidence remains insufficient",
                ],
                "must_not_apply": [
                    "mutate state",
                    "register sources",
                    "update replay baseline",
                    "write memory automatically",
                    "act as runtime gate",
                    "create canonical claim graph",
                    "promote or demote authority",
                    "treat packet as permission",
                    "treat conformance pass as permission",
                    "hide blockers",
                    "infer negative evidence from silence",
                ],
            },
        }


def build_operator_decision_packet(
    metacognitive_handoff: Mapping[str, Any],
    decision_taxonomy_conformance: Mapping[str, Any],
    drift_policy: Mapping[str, Any],
    baseline_lifecycle: Mapping[str, Any],
) -> OperatorDecisionPacket:
    handoff_payload = _validate_handoff_payload(metacognitive_handoff)
    conformance_payload = _validate_conformance_payload(decision_taxonomy_conformance)
    drift_payload = _validate_drift_policy_payload(drift_policy)
    lifecycle_payload = _validate_baseline_lifecycle_payload(baseline_lifecycle)

    handoff_summary = _mapping(handoff_payload.get("summary"), "handoff.summary")
    decision = _string_value(
        handoff_summary.get("recommended_human_decision"),
        "handoff.summary.recommended_human_decision",
    )
    readiness = _string_value(
        handoff_summary.get("action_readiness"),
        "handoff.summary.action_readiness",
    )
    conformance_summary = _mapping(conformance_payload.get("summary"), "conformance.summary")

    source_count = _int_value(handoff_summary.get("source_count"), "handoff.summary.source_count")
    candidates_extracted = _int_value(
        handoff_summary.get("candidates_extracted"),
        "handoff.summary.candidates_extracted",
    )
    findings_evaluated = _int_value(
        handoff_summary.get("findings_evaluated"),
        "handoff.summary.findings_evaluated",
    )
    ready_count = _int_value(handoff_summary.get("ready_count"), "handoff.summary.ready_count")
    blocked_count = _int_value(handoff_summary.get("blocked_count"), "handoff.summary.blocked_count")
    insufficient_count = _int_value(
        handoff_summary.get("insufficient_count"),
        "handoff.summary.insufficient_count",
    )

    known = _string_tuple(handoff_payload.get("known"), "handoff.known")
    unknown = _string_tuple(handoff_payload.get("unknown"), "handoff.unknown")
    blockers: list[str] = []
    missing_evidence = list(_string_tuple(handoff_payload.get("missing_evidence"), "handoff.missing_evidence"))
    risk_notes = list(_string_tuple(handoff_payload.get("risk_notes"), "handoff.risk_notes"))
    risk_notes.extend(_string_tuple(handoff_payload.get("conflicts"), "handoff.conflicts"))

    all_conformance_passed = _bool_value(
        conformance_summary.get("all_cases_passed"),
        "conformance.summary.all_cases_passed",
    )
    conformance_fail_count = _int_value(
        conformance_summary.get("fail_count"),
        "conformance.summary.fail_count",
    )
    pair_covered = _decision_pair_is_covered(conformance_payload, decision, readiness)
    conformance_passed = all_conformance_passed and pair_covered
    if not all_conformance_passed:
        blockers.append(
            f"decision taxonomy conformance has {conformance_fail_count} failing case(s)"
        )
        blockers.extend(_conformance_issues(conformance_payload))
    if not pair_covered:
        blockers.append(
            f"current handoff pair is not covered by taxonomy conformance: {decision}/{readiness}"
        )

    drift_classification = _string_value(drift_payload.get("classification"), "drift.classification")
    drift_required_human_action = _string_value(
        drift_payload.get("required_human_action"),
        "drift.required_human_action",
    )
    drift_readiness = _string_value(drift_payload.get("action_readiness"), "drift.action_readiness")
    drift_reasons = _string_tuple(drift_payload.get("reasons"), "drift.reasons")
    lifecycle_recommendation = _string_value(
        lifecycle_payload.get("recommendation"),
        "lifecycle.recommendation",
    )
    lifecycle_required_human_action = _string_value(
        lifecycle_payload.get("required_human_action"),
        "lifecycle.required_human_action",
    )
    lifecycle_readiness = _string_value(
        lifecycle_payload.get("action_readiness"),
        "lifecycle.action_readiness",
    )

    if readiness == "blocked":
        blockers.append(f"metacognitive handoff blocks action: {decision}")
    if drift_readiness == "blocked":
        blockers.append(f"drift policy blocks action: {drift_classification}")
    if lifecycle_readiness == "blocked":
        blockers.append(f"baseline lifecycle blocks action: {lifecycle_recommendation}")
    if drift_required_human_action != "none" and drift_required_human_action != decision:
        missing_evidence.append(
            f"drift policy requires human action: {drift_required_human_action}"
        )
    if lifecycle_required_human_action != "none" and lifecycle_required_human_action != decision:
        missing_evidence.append(
            f"baseline lifecycle requires human action: {lifecycle_required_human_action}"
        )
    if drift_classification != "no_drift":
        risk_notes.append(f"drift policy classification is {drift_classification}")
    risk_notes.extend(drift_reasons)

    final_decision, final_readiness = _select_operator_decision(
        blockers=blockers,
        handoff_decision=decision,
        handoff_readiness=readiness,
        drift_required_human_action=drift_required_human_action,
        drift_readiness=drift_readiness,
        lifecycle_required_human_action=lifecycle_required_human_action,
        lifecycle_readiness=lifecycle_readiness,
    )

    return OperatorDecisionPacket(
        recommended_human_decision=final_decision,
        action_readiness=final_readiness,
        decision_summary=_decision_summary(final_decision, final_readiness, blockers),
        known=known,
        unknown=unknown,
        blockers=tuple(_dedupe(blockers)),
        missing_evidence=tuple(_dedupe(missing_evidence)),
        risk_notes=tuple(_dedupe(risk_notes)),
        source_evidence=(
            f"metacognitive_handoff: decision={decision}; readiness={readiness}",
            (
                "decision_taxonomy_conformance: "
                f"all_cases_passed={str(all_conformance_passed).lower()}; "
                f"pair_covered={str(pair_covered).lower()}"
            ),
            (
                "drift_policy: "
                f"classification={drift_classification}; "
                f"required_human_action={drift_required_human_action}; "
                f"readiness={drift_readiness}"
            ),
            (
                "baseline_lifecycle: "
                f"recommendation={lifecycle_recommendation}; "
                f"required_human_action={lifecycle_required_human_action}; "
                f"readiness={lifecycle_readiness}"
            ),
        ),
        conformance_passed=conformance_passed,
        source_count=source_count,
        candidates_extracted=candidates_extracted,
        findings_evaluated=findings_evaluated,
        ready_count=ready_count,
        blocked_count=blocked_count,
        insufficient_count=insufficient_count,
        drift_policy_classification=drift_classification,
        drift_policy_required_human_action=drift_required_human_action,
        baseline_lifecycle_recommendation=lifecycle_recommendation,
        baseline_lifecycle_required_human_action=lifecycle_required_human_action,
    )


def render_operator_decision_packet_json(packet: OperatorDecisionPacket) -> str:
    return json.dumps(packet.to_dict(), indent=2, sort_keys=True) + "\n"


def render_operator_decision_packet_markdown(packet: OperatorDecisionPacket) -> str:
    lines = [
        "# Epistemic Readiness Operator Decision Packet",
        "",
        "## Boundary",
        "",
        f"- state_change: {packet.state_change}",
        f"- authority: {packet.authority}",
        f"- packet_role: {packet.packet_role}",
        "- operator_packet_is_not_permission: true",
        "- operator_packet_is_not_memory: true",
        "- operator_packet_is_not_authority: true",
        "- operator_packet_is_not_runtime_gate: true",
        "- operator_packet_is_not_claim_graph: true",
        "- conformance_pass_is_not_permission: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Decision",
        "",
        f"- recommended_human_decision: `{packet.recommended_human_decision}`",
        f"- action_readiness: `{packet.action_readiness}`",
        f"- conformance_passed: `{str(packet.conformance_passed).lower()}`",
        f"- decision_summary: {packet.decision_summary}",
        "",
        "## Counts",
        "",
        f"- source_count: `{packet.source_count}`",
        f"- candidates_extracted: `{packet.candidates_extracted}`",
        f"- findings_evaluated: `{packet.findings_evaluated}`",
        f"- ready_count: `{packet.ready_count}`",
        f"- blocked_count: `{packet.blocked_count}`",
        f"- insufficient_count: `{packet.insufficient_count}`",
        "",
        "## Source Disposition",
        "",
        f"- drift_policy_classification: `{packet.drift_policy_classification}`",
        f"- drift_policy_required_human_action: `{packet.drift_policy_required_human_action}`",
        f"- baseline_lifecycle_recommendation: `{packet.baseline_lifecycle_recommendation}`",
        f"- baseline_lifecycle_required_human_action: `{packet.baseline_lifecycle_required_human_action}`",
        "",
    ]
    _append_section(lines, "Known", packet.known)
    _append_section(lines, "Unknown", packet.unknown)
    _append_section(lines, "Blockers", packet.blockers)
    _append_section(lines, "Missing Evidence", packet.missing_evidence)
    _append_section(lines, "Risk Notes", packet.risk_notes)
    _append_section(lines, "Source Evidence", packet.source_evidence)
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
            "- treat packet as permission",
            "- treat conformance pass as permission",
            "- hide blockers",
            "- infer negative evidence from silence",
            "",
        ]
    )
    return "\n".join(lines)


def _select_operator_decision(
    *,
    blockers: list[str],
    handoff_decision: str,
    handoff_readiness: str,
    drift_required_human_action: str,
    drift_readiness: str,
    lifecycle_required_human_action: str,
    lifecycle_readiness: str,
) -> tuple[str, str]:
    if blockers:
        return "review_blockers", "blocked"
    if handoff_decision != "none":
        return handoff_decision, handoff_readiness
    if drift_required_human_action != "none":
        return drift_required_human_action, drift_readiness
    if lifecycle_required_human_action != "none":
        return lifecycle_required_human_action, lifecycle_readiness
    return "none", "no_action"


def _decision_summary(decision: str, readiness: str, blockers: list[str]) -> str:
    if readiness == "blocked":
        return f"Action is blocked pending human blocker review ({len(blockers)} blocker(s))."
    if readiness == "human_approval_required":
        return f"Human decision `{decision}` is required before action."
    if readiness == "advisory_report_allowed":
        return f"Operator acknowledgement `{decision}` may be requested; advisory report only."
    if readiness == "no_action":
        return "No human decision is requested by current advisory evidence; this is not permission."
    return f"Recommended readiness is `{readiness}` with decision `{decision}`; this is not permission."


def _validate_handoff_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="metacognitive_handoff",
        schema_version=METACOGNITIVE_HANDOFF_SCHEMA_VERSION,
        authority=METACOGNITIVE_HANDOFF_AUTHORITY,
    )
    summary = _mapping(result.get("summary"), "handoff.summary")
    for key in (
        "source_count",
        "candidates_extracted",
        "findings_evaluated",
        "ready_count",
        "blocked_count",
        "insufficient_count",
    ):
        _int_value(summary.get(key), f"handoff.summary.{key}")
    decision = _string_value(
        summary.get("recommended_human_decision"),
        "handoff.summary.recommended_human_decision",
    )
    readiness = _string_value(summary.get("action_readiness"), "handoff.summary.action_readiness")
    if decision not in _VALID_HUMAN_DECISIONS:
        raise ValueError(f"invalid handoff decision: {decision}")
    if readiness not in _VALID_ACTION_READINESS:
        raise ValueError(f"invalid handoff readiness: {readiness}")
    guardrails = _mapping(result.get("guardrails"), "handoff.guardrails")
    for guardrail in (
        "handoff_is_not_permission",
        "handoff_is_not_authority",
        "handoff_is_not_runtime_gate",
        "silence_is_not_negative_evidence",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"handoff guardrail missing or false: {guardrail}")
    return result


def _validate_conformance_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="decision_taxonomy_conformance",
        schema_version=DECISION_TAXONOMY_CONFORMANCE_SCHEMA_VERSION,
        authority=DECISION_TAXONOMY_CONFORMANCE_AUTHORITY,
    )
    summary = _mapping(result.get("summary"), "conformance.summary")
    _bool_value(summary.get("all_cases_passed"), "conformance.summary.all_cases_passed")
    _int_value(summary.get("pass_count"), "conformance.summary.pass_count")
    _int_value(summary.get("fail_count"), "conformance.summary.fail_count")
    _list_of_mappings(result.get("cases"), "conformance.cases")
    guardrails = _mapping(result.get("guardrails"), "conformance.guardrails")
    for guardrail in (
        "conformance_is_not_permission",
        "covered_pair_is_not_permission",
        "incompatible_pair_must_be_visible",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"conformance guardrail missing or false: {guardrail}")
    return result


def _validate_drift_policy_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="drift_policy",
        schema_version=DRIFT_POLICY_SCHEMA_VERSION,
        authority=DRIFT_POLICY_AUTHORITY,
    )
    for key in ("classification", "recommendation", "required_human_action", "action_readiness"):
        _string_value(result.get(key), f"drift.{key}")
    _mapping(result.get("drift"), "drift.drift")
    _mapping(result.get("regression"), "drift.regression")
    _mapping(result.get("protocol_self_audit"), "drift.protocol_self_audit")
    guardrails = _mapping(result.get("guardrails"), "drift.guardrails")
    for guardrail in (
        "drift_policy_is_not_permission",
        "drift_policy_is_not_authority",
        "baseline_refresh_is_not_automatic",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"drift guardrail missing or false: {guardrail}")
    return result


def _validate_baseline_lifecycle_payload(payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    result = _validate_common_payload(
        payload,
        field_name="baseline_lifecycle",
        schema_version=BASELINE_LIFECYCLE_SCHEMA_VERSION,
        authority=BASELINE_LIFECYCLE_AUTHORITY,
    )
    for key in ("recommendation", "required_human_action", "action_readiness"):
        _string_value(result.get(key), f"lifecycle.{key}")
    _mapping(result.get("drift"), "lifecycle.drift")
    _mapping(result.get("regression"), "lifecycle.regression")
    _mapping(result.get("protocol_self_audit"), "lifecycle.protocol_self_audit")
    guardrails = _mapping(result.get("guardrails"), "lifecycle.guardrails")
    for guardrail in (
        "baseline_lifecycle_is_not_permission",
        "baseline_refresh_is_not_automatic",
        "baseline_freshness_is_not_truth",
    ):
        if guardrails.get(guardrail) is not True:
            raise ValueError(f"lifecycle guardrail missing or false: {guardrail}")
    return result


def _validate_common_payload(
    payload: Mapping[str, Any] | Any,
    *,
    field_name: str,
    schema_version: str,
    authority: str,
) -> dict[str, Any]:
    result = _mapping(payload, field_name)
    if result.get("schema_version") != schema_version:
        raise ValueError(f"unsupported {field_name} schema_version: {result.get('schema_version')}")
    if result.get("state_change") != "none":
        raise ValueError(f"{field_name} must declare state_change = none")
    if result.get("authority") != authority:
        raise ValueError(f"unsupported {field_name} authority: {result.get('authority')}")
    return result


def _decision_pair_is_covered(
    conformance_payload: Mapping[str, Any],
    decision: str,
    readiness: str,
) -> bool:
    summary = _mapping(conformance_payload.get("summary"), "conformance.summary")
    covered_pairs = _list_of_mappings(summary.get("covered_pairs"), "conformance.summary.covered_pairs")
    for pair in covered_pairs:
        if (
            pair.get("recommended_human_decision") == decision
            and pair.get("action_readiness") == readiness
        ):
            return True
    return False


def _conformance_issues(conformance_payload: Mapping[str, Any]) -> list[str]:
    issues: list[str] = []
    for case in _list_of_mappings(conformance_payload.get("cases"), "conformance.cases"):
        if case.get("conformance_passed") is False:
            scenario_id = str(case.get("scenario_id", "unknown-scenario"))
            case_issues = _string_tuple(case.get("issues"), "conformance.case.issues")
            if case_issues:
                issues.extend(f"{scenario_id}: {issue}" for issue in case_issues)
            else:
                issues.append(f"{scenario_id}: conformance failed")
    return issues


def _append_section(lines: list[str], title: str, values: tuple[str, ...]) -> None:
    lines.extend([f"## {title}", ""])
    if values:
        lines.extend(f"- {value}" for value in values)
    else:
        lines.append("- none")
    lines.append("")


def _dedupe(values: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for value in values:
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def _mapping(value: Any, field_name: str) -> dict[str, Any]:
    if not isinstance(value, Mapping):
        raise ValueError(f"{field_name} must be a JSON object")
    return dict(value)


def _list_of_mappings(value: Any, field_name: str) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    result: list[dict[str, Any]] = []
    for item in value:
        if not isinstance(item, Mapping):
            raise ValueError(f"{field_name} entries must be JSON objects")
        result.append(dict(item))
    return result


def _string_tuple(value: Any, field_name: str) -> tuple[str, ...]:
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"{field_name} must be a list")
    return tuple(str(item) for item in value)


def _string_value(value: Any, field_name: str) -> str:
    if not isinstance(value, str) or not value:
        raise ValueError(f"{field_name} must be a non-empty string")
    return value


def _int_value(value: Any, field_name: str) -> int:
    if not isinstance(value, int):
        raise ValueError(f"{field_name} must be an integer")
    return value


def _bool_value(value: Any, field_name: str) -> bool:
    if not isinstance(value, bool):
        raise ValueError(f"{field_name} must be a boolean")
    return value
