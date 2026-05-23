from __future__ import annotations

import json
from dataclasses import asdict
from typing import Iterable

from .contract import DecisionEnvelope


def _envelope_dict(envelope: DecisionEnvelope) -> dict[str, object]:
    return asdict(envelope)


def render_envelopes_json(envelopes: Iterable[DecisionEnvelope]) -> str:
    payload = {
        "state_change": "none",
        "authority": "non-authoritative; advisory decision envelope only",
        "envelopes": [_envelope_dict(envelope) for envelope in envelopes],
    }
    return json.dumps(payload, indent=2, sort_keys=True) + "\n"


def render_envelopes_markdown(envelopes: Iterable[DecisionEnvelope]) -> str:
    ordered = tuple(envelopes)
    lines = [
        "# Epistemic Guard Decision Envelope Oracle",
        "",
        "- state_change: none",
        "- authority: non-authoritative; advisory decision envelope only",
        "- advisory_pass_is_not_permission: true",
        "- registered_is_not_true: true",
        "- retrieved_is_not_relevant: true",
        "- remembered_is_not_trusted: true",
        "- silence_is_not_negative_evidence: true",
        "- permission_is_not_sufficient_evidence: true",
        "",
        "## Summary",
        "",
        f"- scenario_count: {len(ordered)}",
        f"- blocked_or_human_count: {sum(1 for item in ordered if item.blocked)}",
        f"- advisory_allowed_count: {sum(1 for item in ordered if item.action_readiness == 'advisory_report_allowed')}",
        f"- derived_experiment_allowed_count: {sum(1 for item in ordered if item.action_readiness == 'derived_experiment_allowed')}",
        "",
        "## Envelopes",
        "",
    ]
    for envelope in ordered:
        lines.extend(
            [
                f"### {envelope.scenario_id}",
                "",
                f"- intent: {envelope.intent}",
                f"- sufficiency: {envelope.sufficiency}",
                f"- action_readiness: {envelope.action_readiness}",
                f"- recommended_human_decision: {envelope.recommended_human_decision}",
                f"- approval_status: {envelope.approval_status}",
                f"- prewrite_guard_status: {envelope.prewrite_guard_status}",
                f"- state_change: {envelope.state_change}",
                f"- blockers: {', '.join(envelope.blockers) if envelope.blockers else 'none'}",
                f"- missing_evidence: {', '.join(envelope.missing_evidence) if envelope.missing_evidence else 'none'}",
                f"- stale_claims: {', '.join(envelope.stale_claims) if envelope.stale_claims else 'none'}",
                f"- conflicts: {', '.join(envelope.conflicts) if envelope.conflicts else 'none'}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"
