from __future__ import annotations

from .contract import BaselineMetrics, ReadinessReport


def _delta(current: int, baseline: int) -> str:
    diff = current - baseline
    sign = "+" if diff >= 0 else ""
    return f"{current} ({sign}{diff})"


def _render_baseline(lines: list[str], report: ReadinessReport, baseline: BaselineMetrics) -> None:
    lines.append("## Baseline Comparison")
    lines.append("")
    lines.append(f"- baseline_label: {baseline.label}")
    lines.append(f"- candidates_extracted: {_delta(report.candidate_count, baseline.candidates_extracted)}")
    lines.append(f"- findings_evaluated: {_delta(report.finding_count, baseline.findings_evaluated)}")
    lines.append(f"- ready_count: {_delta(report.ready_count, baseline.ready_count)}")
    lines.append(f"- blocked_count: {_delta(report.blocked_count, baseline.blocked_count)}")
    lines.append(f"- insufficient_count: {_delta(report.insufficient_count, baseline.insufficient_count)}")
    lines.append("")


def _render_risk_assessment(lines: list[str], report: ReadinessReport) -> None:
    assessment = report.risk_assessment
    if assessment is None:
        return
    lines.append("## Risk Budget Assessment")
    lines.append("")
    lines.append(f"- action_id: `{assessment.action_id}`")
    lines.append(f"- purpose: {assessment.purpose}")
    lines.append(f"- zone: `{assessment.zone}`")
    lines.append(f"- state_change: {assessment.state_change}")
    lines.append(f"- authority: {assessment.authority}")
    lines.append(f"- risk_score: {assessment.risk_score}")
    lines.append(f"- declared_gate_level: `{assessment.declared_gate_level}`")
    lines.append(f"- required_gate_level: `{assessment.required_gate_level}`")
    lines.append(f"- budget_status: `{assessment.budget_status}`")
    lines.append(f"- action_readiness: `{assessment.action_readiness}`")
    lines.append(f"- human_approval_required: {str(assessment.human_approval_required).lower()}")
    if assessment.budget_violations:
        lines.append("- budget_violations:")
        for violation in assessment.budget_violations:
            lines.append(f"  - {violation}")
    else:
        lines.append("- budget_violations: none")
    if assessment.stop_conditions:
        lines.append("- stop_conditions:")
        for condition in assessment.stop_conditions:
            lines.append(f"  - {condition}")
    else:
        lines.append("- stop_conditions: none")
    lines.append("")


def render_readiness_markdown(report: ReadinessReport) -> str:
    lines: list[str] = ["# Epistemic Readiness Report", ""]
    lines.append(f"- state_change: {report.state_change}")
    lines.append(f"- authority: {report.authority}")
    lines.append("- report_role: advisory evidence only")
    lines.append(f"- action_readiness: {report.action_readiness}")
    lines.append(f"- source_count: {len(report.source_reads)}")
    lines.append(f"- candidates_extracted: {report.candidate_count}")
    lines.append(f"- findings_evaluated: {report.finding_count}")
    lines.append(f"- ready_count: {report.ready_count}")
    lines.append(f"- blocked_count: {report.blocked_count}")
    lines.append(f"- insufficient_count: {report.insufficient_count}")
    lines.append("")
    lines.append("## Epistemic Guardrails")
    lines.append("")
    lines.append("- registered_is_not_true: true")
    lines.append("- retrieved_is_not_relevant: true")
    lines.append("- remembered_is_not_trusted: true")
    lines.append("- silence_is_not_negative_evidence: true")
    lines.append("- report_readiness_is_not_permission: true")
    lines.append("")

    lines.append("## Source Manifest")
    lines.append("")
    if not report.source_reads:
        lines.append("_no sources read_")
    for read in report.source_reads:
        lines.append(
            "- "
            f"path: `{read.relative_path}`; "
            f"role: `{read.source_role}`; "
            f"lines_read: {read.lines_read}/{read.requested_max_lines}; "
            f"bytes_read: {read.bytes_read}; "
            f"truncated: {str(read.truncated).lower()}"
        )
    lines.append("")

    if report.baseline is not None:
        _render_baseline(lines, report, report.baseline)

    _render_risk_assessment(lines, report)

    lines.append("## Findings Summary")
    lines.append("")
    if not report.evaluation.findings:
        lines.append("_no claim candidates evaluated_")
    else:
        for finding in report.evaluation.findings:
            claim = finding.claim
            lines.append(f"### {claim.claim_id}")
            lines.append("")
            lines.append(f"- claim: `{claim.subject}` `{claim.predicate}` `{claim.object}`")
            lines.append(f"- source: `{claim.source_path}:{claim.evidence_span}`")
            lines.append(f"- authority: `{finding.authority}`")
            lines.append(f"- confidence: `{finding.confidence}`")
            lines.append(f"- sufficiency: `{finding.sufficiency}`")
            lines.append(f"- conflict: `{finding.conflict}`")
            lines.append(f"- supersession: `{finding.supersession}`")
            lines.append(f"- staleness: `{finding.staleness}`")
            lines.append(f"- operational_readiness: `{finding.operational_readiness}`")
            lines.append("")

    lines.append("## Boundary")
    lines.append("")
    lines.append("- may_suggest: inspect evidence, compare reports, request human review")
    lines.append("- must_not_apply: mutate state, register sources, act as runtime gate, create canonical claim graph")
    lines.append("- next_step: use this report as advisory input only")
    return "\n".join(lines).rstrip() + "\n"
