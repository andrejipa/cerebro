from __future__ import annotations

import json
import tomllib
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from .contract import DecisionEnvelope
from .manifest import DecisionManifestError, evaluate_manifest_file


class PreActionGuardError(ValueError):
    """Raised when a pre-action guard manifest is malformed or unsafe."""


@dataclass(frozen=True)
class ProposedAction:
    action_id: str
    intent: str
    action_kind: str = "derived_experiment"
    proposed_by: str = "operator"
    created_at: str = ""
    expected_state_change: str = "none"
    notes: tuple[str, ...] = ()


@dataclass(frozen=True)
class PreActionGuardReport:
    proposed_action: ProposedAction
    envelope_count: int
    blocked_or_human_count: int
    advisory_allowed_count: int
    derived_experiment_allowed_count: int
    blocker_count: int
    missing_evidence_count: int
    stale_claim_count: int
    conflict_count: int
    warning_count: int
    action_readiness: str
    recommended_human_decision: str
    must_not_execute_automatically: bool
    advisory_pass_is_not_permission: bool
    state_change: str
    authority: str
    envelopes: tuple[DecisionEnvelope, ...]

    @property
    def blocked(self) -> bool:
        return self.action_readiness in {
            "blocked",
            "canonical_change_requires_trigger",
            "human_approval_required",
        }


def _required_str(table: dict[str, Any], field: str) -> str:
    value = table.get(field)
    if not isinstance(value, str) or not value:
        raise PreActionGuardError(f"missing required string field: proposed_action.{field}")
    return value


def _optional_str(table: dict[str, Any], field: str, default: str) -> str:
    value = table.get(field, default)
    if not isinstance(value, str):
        raise PreActionGuardError(f"proposed_action.{field} must be a string")
    return value


def _optional_str_tuple(table: dict[str, Any], field: str) -> tuple[str, ...]:
    value = table.get(field, [])
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise PreActionGuardError(f"proposed_action.{field} must be a list of strings")
    return tuple(value)


def _resolve_pre_action_manifest_path(path: str | Path, *, root: str | Path | None) -> Path:
    root_path = Path.cwd() if root is None else Path(root)
    resolved_root = root_path.resolve()
    candidate = Path(path)
    if not candidate.is_absolute():
        candidate = resolved_root / candidate
    resolved = candidate.resolve()

    try:
        resolved.relative_to(resolved_root)
    except ValueError as exc:
        raise PreActionGuardError("pre-action manifest path escapes root") from exc

    if any(part.casefold() == ".cerebro" for part in resolved.parts):
        raise PreActionGuardError("pre-action manifest path may not live under .cerebro")
    return resolved


def _load_proposed_action(path: Path) -> ProposedAction:
    payload = tomllib.loads(path.read_text(encoding="utf-8"))
    raw = payload.get("proposed_action")
    if not isinstance(raw, dict):
        raise PreActionGuardError("pre-action manifest requires [proposed_action]")

    expected_state_change = _optional_str(raw, "expected_state_change", "none")
    if expected_state_change != "none":
        raise PreActionGuardError("pre-action reports must declare expected_state_change = 'none'")

    return ProposedAction(
        action_id=_required_str(raw, "action_id"),
        intent=_required_str(raw, "intent"),
        action_kind=_optional_str(raw, "action_kind", "derived_experiment"),
        proposed_by=_optional_str(raw, "proposed_by", "operator"),
        created_at=_optional_str(raw, "created_at", ""),
        expected_state_change=expected_state_change,
        notes=_optional_str_tuple(raw, "notes"),
    )


def _aggregate_readiness(envelopes: tuple[DecisionEnvelope, ...]) -> str:
    readiness = {envelope.action_readiness for envelope in envelopes}
    if "canonical_change_requires_trigger" in readiness:
        return "canonical_change_requires_trigger"
    if "blocked" in readiness:
        return "blocked"
    if "human_approval_required" in readiness:
        return "human_approval_required"
    if "derived_experiment_allowed" in readiness:
        return "derived_experiment_allowed"
    if readiness == {"advisory_report_allowed"}:
        return "advisory_report_allowed"
    return "propose_only"


def _aggregate_human_decision(envelopes: tuple[DecisionEnvelope, ...]) -> str:
    decisions = {envelope.recommended_human_decision for envelope in envelopes}
    for decision in (
        "review_blockers",
        "adjudicate_conflict",
        "approve_action",
        "provide_missing_evidence",
    ):
        if decision in decisions:
            return decision
    return "none"


def build_pre_action_guard_report(
    proposed_action: ProposedAction,
    envelopes: Iterable[DecisionEnvelope],
) -> PreActionGuardReport:
    ordered = tuple(envelopes)
    if not ordered:
        raise PreActionGuardError("pre-action report requires at least one decision envelope")

    return PreActionGuardReport(
        proposed_action=proposed_action,
        envelope_count=len(ordered),
        blocked_or_human_count=sum(1 for envelope in ordered if envelope.blocked),
        advisory_allowed_count=sum(
            1 for envelope in ordered if envelope.action_readiness == "advisory_report_allowed"
        ),
        derived_experiment_allowed_count=sum(
            1 for envelope in ordered if envelope.action_readiness == "derived_experiment_allowed"
        ),
        blocker_count=sum(len(envelope.blockers) for envelope in ordered),
        missing_evidence_count=sum(len(envelope.missing_evidence) for envelope in ordered),
        stale_claim_count=sum(len(envelope.stale_claims) for envelope in ordered),
        conflict_count=sum(len(envelope.conflicts) for envelope in ordered),
        warning_count=sum(len(envelope.warnings) for envelope in ordered),
        action_readiness=_aggregate_readiness(ordered),
        recommended_human_decision=_aggregate_human_decision(ordered),
        must_not_execute_automatically=True,
        advisory_pass_is_not_permission=True,
        state_change="none",
        authority="non-authoritative; advisory pre-action report only",
        envelopes=ordered,
    )


def build_pre_action_guard_report_from_manifest(
    path: str | Path,
    *,
    root: str | Path | None = None,
) -> PreActionGuardReport:
    manifest_path = _resolve_pre_action_manifest_path(path, root=root)
    proposed_action = _load_proposed_action(manifest_path)
    try:
        envelopes = evaluate_manifest_file(manifest_path, root=root)
    except DecisionManifestError as exc:
        raise PreActionGuardError(str(exc)) from exc
    return build_pre_action_guard_report(proposed_action, envelopes)


def render_pre_action_guard_report_json(report: PreActionGuardReport) -> str:
    payload = asdict(report)
    payload["state_change"] = "none"
    payload["authority"] = report.authority
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_pre_action_guard_report_markdown(report: PreActionGuardReport) -> str:
    action = report.proposed_action
    lines = [
        "# Epistemic Guard Pre-Action Report",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory pre-action report only",
        "- advisory_pass_is_not_permission: true",
        "- must_not_execute_automatically: true",
        "- registered_is_not_true: true",
        "- retrieved_is_not_relevant: true",
        "- remembered_is_not_trusted: true",
        "- silence_is_not_negative_evidence: true",
        "",
        "## Proposed Action",
        "",
        f"- action_id: {action.action_id}",
        f"- intent: {action.intent}",
        f"- action_kind: {action.action_kind}",
        f"- proposed_by: {action.proposed_by}",
        f"- created_at: {action.created_at or 'not_declared'}",
        f"- expected_state_change: {action.expected_state_change}",
        "",
        "## Summary",
        "",
        f"- envelope_count: {report.envelope_count}",
        f"- blocked_or_human_count: {report.blocked_or_human_count}",
        f"- advisory_allowed_count: {report.advisory_allowed_count}",
        f"- derived_experiment_allowed_count: {report.derived_experiment_allowed_count}",
        f"- blocker_count: {report.blocker_count}",
        f"- missing_evidence_count: {report.missing_evidence_count}",
        f"- stale_claim_count: {report.stale_claim_count}",
        f"- conflict_count: {report.conflict_count}",
        f"- warning_count: {report.warning_count}",
        f"- action_readiness: {report.action_readiness}",
        f"- recommended_human_decision: {report.recommended_human_decision}",
        "",
        "## Envelopes",
        "",
    ]
    for envelope in report.envelopes:
        lines.extend(
            [
                f"### {envelope.scenario_id}",
                "",
                f"- intent: {envelope.intent}",
                f"- sufficiency: {envelope.sufficiency}",
                f"- action_readiness: {envelope.action_readiness}",
                f"- recommended_human_decision: {envelope.recommended_human_decision}",
                f"- blockers: {', '.join(envelope.blockers) if envelope.blockers else 'none'}",
                f"- missing_evidence: {', '.join(envelope.missing_evidence) if envelope.missing_evidence else 'none'}",
                f"- stale_claims: {', '.join(envelope.stale_claims) if envelope.stale_claims else 'none'}",
                f"- conflicts: {', '.join(envelope.conflicts) if envelope.conflicts else 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
