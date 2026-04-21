"""Entry point: evaluate the tripwire ruleset against the dataset and
emit advisory-only reports in Markdown and JSON.

Running this module never mutates canonical state. Reports are written
next to this file and are classified as derived, read-only, and
advisory-only. The CLI exits non-zero only when the dataset itself is
malformed; verdicts are informative, not enforcement.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any
import argparse
import json

from . import AUTHORITY, SCHEMA_VERSION
from .harness import evaluate_dataset, load_dataset
from .rules import (
    CANONICAL_SCOPE,
    detect_broken_canonical_refs,
    detect_export_surface_gap,
    detect_stale_system_state,
)


REPORT_MD_PATH = Path(__file__).with_name("report_latest.md")
REPORT_JSON_PATH = Path(__file__).with_name("report_latest.json")
REPORT_BROKEN_REFS_MD_PATH = Path(__file__).with_name("report_broken_refs_latest.md")
REPORT_BROKEN_REFS_JSON_PATH = Path(__file__).with_name("report_broken_refs_latest.json")
REPORT_EXPORT_MD_PATH = Path(__file__).with_name("report_export_surface_latest.md")
REPORT_EXPORT_JSON_PATH = Path(__file__).with_name("report_export_surface_latest.json")

RULE_REGISTRY = {
    "broken_canonical_refs": {
        "rule": detect_broken_canonical_refs,
        "dataset": Path(__file__).with_name("dataset_broken_refs.toml"),
        "markdown": REPORT_BROKEN_REFS_MD_PATH,
        "json": REPORT_BROKEN_REFS_JSON_PATH,
    },
    "stale_system_state": {
        "rule": detect_stale_system_state,
        "dataset": Path(__file__).with_name("dataset.toml"),
        "markdown": REPORT_MD_PATH,
        "json": REPORT_JSON_PATH,
    },
    "export_surface_gap": {
        "rule": detect_export_surface_gap,
        "dataset": Path(__file__).with_name("dataset_export_surface.toml"),
        "markdown": REPORT_EXPORT_MD_PATH,
        "json": REPORT_EXPORT_JSON_PATH,
    },
}


def render_markdown(result: dict[str, Any]) -> str:
    metrics = result["metrics"]
    verdict = result["verdict"]
    lines: list[str] = []
    lines.append("# Operational Insufficiency Suggestions — Tripwire Evaluation")
    lines.append("")
    lines.append(f"- authority: `{result['authority']}`")
    lines.append(f"- schema_version: `{result['schema_version']}`")
    lines.append(f"- non_authoritative: `{str(result['non_authoritative']).lower()}`")
    lines.append(f"- read_only: `{str(result['read_only']).lower()}`")
    lines.append(f"- rule: `{result['rule']}`")
    lines.append(f"- evaluated_at: `{result['evaluated_at']}`")
    lines.append("")
    lines.append("## Metrics")
    lines.append("")
    lines.append(f"- total cases: `{metrics['total_cases']}`")
    lines.append(f"- true positives: `{metrics['tp']}`")
    lines.append(f"- false positives: `{metrics['fp']}`")
    lines.append(f"- true negatives: `{metrics['tn']}`")
    lines.append(f"- false negatives: `{metrics['fn']}`")
    lines.append(f"- precision: `{metrics['precision']:.4f}`")
    lines.append(f"- recall: `{metrics['recall']:.4f}`")
    lines.append(f"- F1: `{metrics['f1']:.4f}`")
    if metrics["confidence_checked"]:
        rate = metrics["confidence_match_rate"]
        lines.append(f"- confidence checks: `{metrics['confidence_checked']}`")
        lines.append(f"- confidence match rate: `{rate:.4f}`")
    scope_metrics = result.get("scope_metrics")
    if scope_metrics:
        lines.append(f"- out_of_scope cases: `{scope_metrics['out_of_scope']}`")
        lines.append(f"- in_scope_clean cases: `{scope_metrics['in_scope_clean']}`")
        lines.append(f"- in_scope_broken cases: `{scope_metrics['in_scope_broken']}`")
    lines.append("")
    lines.append("## Verdict")
    lines.append("")
    lines.append(f"- classification: `{verdict['classification']}`")
    lines.append(f"- rationale: {verdict['rationale']}")
    lines.append("")
    lines.append("## Per-Case Outcomes")
    lines.append("")
    for case in result["per_case"]:
        conf_expected = case["expected_confidence"] or "—"
        conf_actual = case["actual_confidence"] or "—"
        scope_state = case.get("scope_state")
        scope_suffix = f" scope_state=`{scope_state}`" if scope_state else ""
        lines.append(
            f"- `{case['id']}` label=`{case['label']}` outcome=`{case['outcome']}` "
            f"expected_suggestion=`{str(case['expected_suggestion']).lower()}` "
            f"actual_suggestion=`{str(case['actual_suggestion']).lower()}` "
            f"expected_confidence=`{conf_expected}` actual_confidence=`{conf_actual}`"
            f"{scope_suffix}"
        )
        lines.append(f"    - reason: {case['label_reason']}")
    lines.append("")
    lines.append("## Reminder")
    lines.append("")
    lines.append(
        "- Each emitted suggestion is advisory only; `human_review_required` "
        "is always `true`."
    )
    lines.append(
        "- This report is derived and non-authoritative; it must never be "
        "consumed as canonical runtime state."
    )
    return "\n".join(lines) + "\n"


def write_reports(
    result: dict[str, Any],
    *,
    markdown_path: Path = REPORT_MD_PATH,
    json_path: Path = REPORT_JSON_PATH,
) -> None:
    markdown_path.write_text(render_markdown(result), encoding="utf-8")
    json_path.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")


def _annotate_broken_ref_scope(result: dict[str, Any], dataset: list[dict[str, Any]]) -> None:
    scope_metrics = {
        "out_of_scope": 0,
        "in_scope_clean": 0,
        "in_scope_broken": 0,
    }
    scope_fragment = CANONICAL_SCOPE.as_posix()
    for case_result, case in zip(result["per_case"], dataset):
        source_artifact = Path(case["id"]).as_posix()
        if scope_fragment not in source_artifact:
            scope_state = "out_of_scope"
        elif case_result["actual_suggestion"]:
            scope_state = "in_scope_broken"
        else:
            scope_state = "in_scope_clean"
        case_result["scope_state"] = scope_state
        scope_metrics[scope_state] += 1
    result["scope_metrics"] = scope_metrics


def _evaluate_named_rule(name: str) -> dict[str, Any]:
    config = RULE_REGISTRY[name]
    dataset = load_dataset(config["dataset"])
    result = evaluate_dataset(config["rule"], dataset)
    if name == "broken_canonical_refs":
        _annotate_broken_ref_scope(result, dataset)
    write_reports(result, markdown_path=config["markdown"], json_path=config["json"])
    return result


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rule",
        choices=sorted(RULE_REGISTRY),
        help="evaluate only one named tripwire rule",
    )
    args = parser.parse_args(argv)

    if args.rule:
        result = _evaluate_named_rule(args.rule)
        payload: Any = {
            "authority": AUTHORITY,
            "schema_version": SCHEMA_VERSION,
            "rule": result["rule"],
            "metrics": result["metrics"],
            "verdict": result["verdict"],
        }
    else:
        payload = {}
        for name in sorted(RULE_REGISTRY):
            result = _evaluate_named_rule(name)
            payload[name] = {
                "rule": result["rule"],
                "metrics": result["metrics"],
                "verdict": result["verdict"],
            }
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
