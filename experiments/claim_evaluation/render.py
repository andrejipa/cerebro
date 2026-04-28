from __future__ import annotations

from .contract import EvaluationReport


def render_evaluation_markdown(report: EvaluationReport) -> str:
    lines: list[str] = ["# Claim Evaluation Report", ""]
    lines.append(f"- state_change: {report.state_change}")
    lines.append(f"- authority: {report.authority}")
    lines.append(f"- findings_count: {len(report.findings)}")
    lines.append(f"- ready_count: {report.ready_count}")
    lines.append(f"- blocked_count: {report.blocked_count}")
    lines.append(f"- insufficient_count: {report.insufficient_count}")
    lines.append("- registered_is_not_true: true")
    lines.append("- retrieved_is_not_relevant: true")
    lines.append("- remembered_is_not_trusted: true")
    lines.append("- silence_is_not_negative_evidence: true")
    lines.append("")

    if not report.findings:
        lines.append("_no claim candidates evaluated_")
        return "\n".join(lines).rstrip() + "\n"

    lines.append("## Findings")
    lines.append("")
    for finding in report.findings:
        claim = finding.claim
        lines.append(f"### {claim.claim_id}")
        lines.append("")
        lines.append(f"- claim: `{claim.subject}` `{claim.predicate}` `{claim.object}`")
        lines.append(f"- polarity: `{claim.polarity}`")
        lines.append(f"- modality: `{claim.modality}`")
        lines.append(f"- source: `{claim.source_path}:{claim.evidence_span}`")
        lines.append(f"- source_role: `{claim.source_role}`")
        lines.append(f"- extraction_basis: `{claim.extraction_basis}`")
        lines.append(f"- authority: `{finding.authority}`")
        lines.append(f"- confidence: `{finding.confidence}`")
        lines.append(f"- sufficiency: `{finding.sufficiency}`")
        lines.append(f"- conflict: `{finding.conflict}`")
        lines.append(f"- supersession: `{finding.supersession}`")
        lines.append(f"- staleness: `{finding.staleness}`")
        lines.append(f"- operational_readiness: `{finding.operational_readiness}`")
        lines.append("- reasons:")
        for reason in finding.reasons:
            lines.append(f"  - {reason}")
        lines.append("")
    return "\n".join(lines).rstrip() + "\n"
