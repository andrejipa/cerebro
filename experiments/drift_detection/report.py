"""Format and write DriftReport to markdown and JSON."""
from __future__ import annotations
import json
from pathlib import Path
from .schema import DriftReport


def to_markdown(report: DriftReport) -> str:
    lines = [
        "# Cerebro Drift Detection Report",
        "",
        f"**Generated:** {report.generated_at}",
        f"**Baseline:** `{report.baseline_snapshot}`",
        f"**Scanned files:** {report.scanned_files}",
        f"**Status:** {report.summary}",
        "",
    ]
    if report.staleness_score is not None:
        lines += [
            "## Staleness",
            "",
            f"**Score:** {report.staleness_score:.3f}  "
            f"**Classification:** {report.staleness_classification}",
            "",
        ]
    if report.has_drift:
        lines += ["## Drift Entries", ""]
        for e in report.drift_entries:
            if e.kind == "modified":
                lines.append(f"- **modified** `{e.path}`")
                lines.append(f"  - baseline: `{e.baseline_hash[:12]}...`")
                lines.append(f"  - current:  `{e.current_hash[:12]}...`")
            elif e.kind == "added":
                lines.append(f"- **added** `{e.path}` (not in baseline)")
            elif e.kind == "removed":
                lines.append(f"- **removed** `{e.path}` (was in baseline)")
    else:
        lines.append("No structural drift detected since baseline snapshot.")
    lines += [
        "",
        "---",
        "*Non-authoritative. This report never modifies canonical state.*",
    ]
    return "\n".join(lines)


def write_report(report: DriftReport, out_dir: Path) -> tuple[Path, Path]:
    out_dir.mkdir(parents=True, exist_ok=True)
    md_path = out_dir / "drift_report_latest.md"
    json_path = out_dir / "drift_report_latest.json"
    md_path.write_text(to_markdown(report), encoding="utf-8")
    json_path.write_text(
        json.dumps({
            "generated_at": report.generated_at,
            "baseline_snapshot": report.baseline_snapshot,
            "scanned_files": report.scanned_files,
            "has_drift": report.has_drift,
            "summary": report.summary,
            "staleness_score": report.staleness_score,
            "staleness_classification": report.staleness_classification,
            "drift_entries": [
                {"path": e.path, "kind": e.kind,
                 "baseline_hash": e.baseline_hash, "current_hash": e.current_hash}
                for e in report.drift_entries
            ],
        }, indent=2),
        encoding="utf-8",
    )
    return md_path, json_path
