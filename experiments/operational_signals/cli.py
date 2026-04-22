from __future__ import annotations

import argparse
from pathlib import Path
import sys

from .analyzer import _build_analysis_payload, build_analysis
from .logger import default_registry_path, initialize_registry, record_unmet_use_case
from .views import filter_records, render_json, render_markdown


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="operational-signals",
        description="Experimental, derived, non-authoritative operational insufficiency signals.",
    )
    parser.add_argument("--registry", default=str(default_registry_path()))
    subparsers = parser.add_subparsers(dest="command", required=True)

    log_parser = subparsers.add_parser("log", help="Record one insufficiency event.")
    log_parser.add_argument("--project-context", required=True)
    log_parser.add_argument("--task-description", required=True)
    log_parser.add_argument("--query-or-need", required=True)
    log_parser.add_argument("--surface-used", nargs="+", required=True)
    log_parser.add_argument("--failure-mode", required=True)
    log_parser.add_argument("--manual-workaround", required=True)
    log_parser.add_argument("--minutes-spent", type=int, required=True)
    log_parser.add_argument("--extra-files-opened", type=int, required=True)
    log_parser.add_argument("--manual-search-rounds", type=int, required=True)
    log_parser.add_argument("--repeat-count", type=int, required=True)
    log_parser.add_argument("--evidence", nargs="+", required=True)
    log_parser.add_argument("--confidence", required=True)
    log_parser.add_argument("--notes", default="")

    view_parser = subparsers.add_parser("view", help="View recorded signals.")
    view_parser.add_argument("--project")
    view_parser.add_argument("--failure-mode")
    view_parser.add_argument("--candidate-only", action="store_true")
    view_parser.add_argument("--format", choices=("md", "json"), default="md")

    stats_parser = subparsers.add_parser("stats", help="Show aggregate stats.")
    stats_parser.add_argument("--by", choices=("project", "failure_mode", "confidence"), default="project")
    stats_parser.add_argument("--format", choices=("md", "json"), default="json")

    report_parser = subparsers.add_parser("report", help="Show consolidated report.")
    report_parser.add_argument("--format", choices=("md", "json"), default="md")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    registry_path = Path(args.registry)

    if args.command == "log":
        initialize_registry(registry_path)
        record = record_unmet_use_case(
            {
                "project_context": args.project_context,
                "task_description": args.task_description,
                "query_or_need": args.query_or_need,
                "surface_used": list(args.surface_used),
                "failure_mode": args.failure_mode,
                "manual_workaround": args.manual_workaround,
                "operational_cost": {
                    "minutes_spent": args.minutes_spent,
                    "extra_files_opened": args.extra_files_opened,
                    "manual_search_rounds": args.manual_search_rounds,
                },
                "repeat_count": args.repeat_count,
                "evidence": list(args.evidence),
                "confidence": args.confidence,
                "notes": args.notes,
            },
            path=registry_path,
        )
        sys.stdout.write(render_json(record) + "\n")
        return 0

    analysis = build_analysis(registry_path)
    if args.command == "view":
        filtered_records = filter_records(
            analysis["records"],
            project=args.project,
            failure_mode=args.failure_mode,
            candidate_only=args.candidate_only,
        )
        payload = _build_analysis_payload(filtered_records, schema_version=analysis["schema_version"])
        output = render_markdown(payload) if args.format == "md" else render_json(payload)
        sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
        return 0

    if args.command == "stats":
        key = {
            "project": "by_project_context",
            "failure_mode": "by_failure_mode",
            "confidence": "by_confidence",
        }[args.by]
        payload = analysis[key]
        if args.format == "json":
            sys.stdout.write(render_json(payload) + "\n")
        else:
            lines = [f"# Stats by {args.by}", ""]
            for group_key, group in payload.items():
                lines.append(f"- `{group_key}`: `{group['count']}` records")
            sys.stdout.write("\n".join(lines) + "\n")
        return 0

    if args.command == "report":
        output = render_markdown(analysis) if args.format == "md" else render_json(analysis)
        sys.stdout.write(output + ("" if output.endswith("\n") else "\n"))
        return 0

    parser.error("unsupported command")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
