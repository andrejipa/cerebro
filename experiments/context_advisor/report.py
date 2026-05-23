from __future__ import annotations

from .advisor import AdvisoryReport


def render_markdown(report: AdvisoryReport) -> str:
    lines: list[str] = []
    lines.append("# Context Advisor Report")
    lines.append("")
    lines.append(f"- project_root: `{report.project_root}`")
    lines.append("- audience: LLM")
    lines.append("- authority: non-authoritative; advisory evidence only")
    lines.append(f"- state_change: {report.state_change}")
    lines.append(f"- registered_source_count: {report.discovery.registered_source_count}")
    lines.append(f"- indexed_files: {report.vector_index.trace.indexed_files}")
    lines.append(f"- skipped_files: {report.vector_index.trace.skipped_files}")
    lines.append(f"- state_status: {report.vector_index.trace.state_status}")
    lines.append(f"- recommendation_count: {len(report.recommendations)}")
    lines.append("")
    lines.append("## LLM Contract")
    lines.append("")
    for rule in report.llm_contract:
        lines.append(f"- {rule}")
    lines.append("")
    lines.append("## Recommendations")
    lines.append("")
    if not report.recommendations:
        lines.append("_no advisory recommendations emitted_")
    for recommendation in report.recommendations:
        lines.append(f"### {recommendation.kind}: `{recommendation.relative_path}`")
        lines.append("")
        lines.append(f"- priority: {recommendation.priority}")
        lines.append(f"- may_suggest: {recommendation.may_suggest}")
        lines.append(f"- must_not_apply: {recommendation.must_not_apply}")
        lines.append("- reasons:")
        for reason in recommendation.reasons:
            lines.append(f"  - {reason}")
        lines.append("- vector_evidence:")
        for evidence in recommendation.evidence:
            lines.append(f"  - query: {evidence.query}")
            if evidence.hits:
                lines.append("    hits:")
                for hit in evidence.hits:
                    lines.append(f"      - `{hit.relative_path}`")
                    lines.append(f"        - score: {hit.score:.4f}")
                    lines.append(f"        - source_status: {hit.source_status}")
                    lines.append(f"        - heading: {hit.heading or '(no heading detected)'}")
            else:
                lines.append("    hits: []")
        lines.append("")
    lines.append("## Discovery Summary")
    lines.append("")
    lines.append(f"- candidates_not_registered_count: {len(report.discovery.candidates_not_registered)}")
    lines.append(f"- drift_on_registered_sources_count: {len(report.discovery.drift_on_registered_sources)}")
    lines.append(f"- missing_registered_sources_count: {len(report.discovery.missing_registered_sources)}")
    if report.discovery.notes:
        lines.append("- notes:")
        for note in report.discovery.notes:
            lines.append(f"  - {note}")
    return "\n".join(lines)
