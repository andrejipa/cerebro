"""CLI entry point for drift detection.

Usage:
  python -m experiments.drift_detection.cli baseline   # capture current state as baseline
  python -m experiments.drift_detection.cli detect     # compare current state to baseline
  python -m experiments.drift_detection.cli status     # print last report summary

NON-AUTHORITATIVE: this script never writes to .cerebro/, never calls
import-context, and never modifies canonical state.
"""
from __future__ import annotations
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EXPERIMENT_DIR = Path(__file__).resolve().parent
SNAPSHOT_PATH = EXPERIMENT_DIR / "baseline_snapshot.json"


def cmd_baseline() -> int:
    from .scanner import scan
    from .baseline import save_baseline
    entries = scan(REPO_ROOT)
    save_baseline(entries, SNAPSHOT_PATH)
    print(f"Baseline captured: {len(entries)} files → {SNAPSHOT_PATH.name}")
    return 0


def cmd_detect() -> int:
    from .scanner import scan
    from .baseline import load_baseline_with_meta
    from .detector import detect
    from .report import write_report

    result = load_baseline_with_meta(SNAPSHOT_PATH)
    if result is None:
        print("No baseline found. Run: python -m experiments.drift_detection.cli baseline")
        return 1

    baseline_entries, captured_at = result
    current = scan(REPO_ROOT)
    report = detect(
        baseline_entries,
        current,
        baseline_name=SNAPSHOT_PATH.name,
        baseline_captured_at=captured_at,
    )
    md_path, json_path = write_report(report, EXPERIMENT_DIR)
    print(report.summary)
    if report.staleness_score is not None:
        print(f"  staleness={report.staleness_score:.3f} ({report.staleness_classification})")
    if report.has_drift:
        for e in report.drift_entries:
            print(f"  [{e.kind}] {e.path}")
    print(f"Report: {md_path}")
    return 1 if report.has_drift else 0


def cmd_status() -> int:
    import json
    json_path = EXPERIMENT_DIR / "drift_report_latest.json"
    if not json_path.exists():
        print("No report found. Run detect first.")
        return 1
    data = json.loads(json_path.read_text(encoding="utf-8"))
    print(data["summary"])
    if data.get("staleness_score") is not None:
        print(f"Staleness: {data['staleness_score']:.3f} ({data['staleness_classification']})")
    print(f"Generated: {data['generated_at']}")
    print(f"Scanned: {data['scanned_files']} files")
    return 0


def main() -> int:
    commands = {"baseline": cmd_baseline, "detect": cmd_detect, "status": cmd_status}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        print(f"Usage: python -m experiments.drift_detection.cli [{'|'.join(commands)}]")
        return 1
    return commands[sys.argv[1]]()


if __name__ == "__main__":
    sys.exit(main())
