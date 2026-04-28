"""Human-readable rendering for a `DiscoveryReport`.

The output is deliberately plain Markdown with stable section headers so an
operator can paste it into a checkpoint summary or a handoff. No machine
consumer is allowed to treat this output as authoritative.
"""

from __future__ import annotations

from .discovery import DiscoveryReport


def render_markdown(report: DiscoveryReport) -> str:
    """Return a stable-shape Markdown rendering of the discovery report."""

    lines: list[str] = []
    lines.append("# Context Discovery Report")
    lines.append("")
    lines.append(f"- project_root: `{report.project_root}`")
    lines.append(f"- registered_source_count: {report.registered_source_count}")
    lines.append(f"- candidates_not_registered_count: {len(report.candidates_not_registered)}")
    lines.append(f"- drift_on_registered_sources_count: {len(report.drift_on_registered_sources)}")
    lines.append(f"- missing_registered_sources_count: {len(report.missing_registered_sources)}")
    lines.append("- state_change: none")
    lines.append("- authority: non-authoritative; advisory only")
    lines.append("")

    lines.append("## candidates_not_registered")
    lines.append("")
    if report.candidates_not_registered:
        for candidate in report.candidates_not_registered:
            lines.append(f"- `{candidate.relative_path}`")
            lines.append(f"  - role: {candidate.role}")
            lines.append(f"  - score: {candidate.score}")
            lines.append(f"  - heading: {candidate.heading or '(no heading detected)'}")
            lines.append(f"  - reasons: {', '.join(candidate.reasons)}")
    else:
        lines.append("_no new content-signalled candidates detected_")
    lines.append("")

    lines.append("## drift_on_registered_sources")
    lines.append("")
    if report.drift_on_registered_sources:
        for drift in report.drift_on_registered_sources:
            lines.append(f"- `{drift.relative_path}`")
            lines.append(f"  - registered_sha256: `{drift.registered_sha256}`")
            lines.append(f"  - current_sha256: `{drift.current_sha256}`")
            lines.append(f"  - current_heading: {drift.current_heading or '(no heading detected)'}")
    else:
        lines.append("_no drift detected across registered sources_")
    lines.append("")

    lines.append("## missing_registered_sources")
    lines.append("")
    if report.missing_registered_sources:
        for missing in report.missing_registered_sources:
            lines.append(f"- `{missing.relative_path}`")
            lines.append(f"  - registered_sha256: `{missing.registered_sha256}`")
    else:
        lines.append("_no registered source is missing from the target project_")
    lines.append("")

    if report.notes:
        lines.append("## notes")
        lines.append("")
        for note in report.notes:
            lines.append(f"- {note}")
        lines.append("")

    return "\n".join(lines)
