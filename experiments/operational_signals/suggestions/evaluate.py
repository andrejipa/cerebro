"""Entry point: evaluate the tripwire ruleset against the dataset and
emit advisory-only reports in Markdown and JSON.

Running this module never mutates canonical state. Reports are written
next to this file and are classified as derived, read-only, and
advisory-only. The CLI exits non-zero only when the dataset itself is
malformed; verdicts are informative, not enforcement.
"""

from __future__ import annotations

import contextlib
from pathlib import Path
from typing import Any
import argparse
import json
import os
import uuid

from . import AUTHORITY, SCHEMA_VERSION
from .._file_lock import file_lock
from .harness import evaluate_dataset, load_dataset
from ..schema import ensure_allowed_output_path
from .rules import (
    CANONICAL_SCOPE,
    _is_in_canonical_scope,
    analyze_supersedes_mechanical_metadata,
    detect_broken_canonical_refs,
    detect_current_surface_drift,
    detect_export_surface_gap,
    detect_stale_system_state,
    detect_supersedes_mechanical_metadata,
    extract_current_surface_counts,
    extract_current_surface_sources,
)


REPORT_MD_PATH = Path(__file__).with_name("report_latest.md")
REPORT_JSON_PATH = Path(__file__).with_name("report_latest.json")
REPORT_BROKEN_REFS_MD_PATH = Path(__file__).with_name("report_broken_refs_latest.md")
REPORT_BROKEN_REFS_JSON_PATH = Path(__file__).with_name("report_broken_refs_latest.json")
REPORT_EXPORT_MD_PATH = Path(__file__).with_name("report_export_surface_latest.md")
REPORT_EXPORT_JSON_PATH = Path(__file__).with_name("report_export_surface_latest.json")
REPORT_SURFACE_DRIFT_MD_PATH = Path(__file__).with_name("report_surface_drift_latest.md")
REPORT_SURFACE_DRIFT_JSON_PATH = Path(__file__).with_name("report_surface_drift_latest.json")
REPORT_SUPERSEDES_MD_PATH = Path(__file__).with_name("report_supersedes_latest.md")
REPORT_SUPERSEDES_JSON_PATH = Path(__file__).with_name("report_supersedes_latest.json")

RULE_REGISTRY = {
    "broken_canonical_refs": {
        "rule": detect_broken_canonical_refs,
        "dataset": Path(__file__).with_name("dataset_broken_refs.toml"),
        "markdown": REPORT_BROKEN_REFS_MD_PATH,
        "json": REPORT_BROKEN_REFS_JSON_PATH,
    },
    "current_surface_drift": {
        "rule": detect_current_surface_drift,
        "dataset": Path(__file__).with_name("dataset_surface_drift.toml"),
        "markdown": REPORT_SURFACE_DRIFT_MD_PATH,
        "json": REPORT_SURFACE_DRIFT_JSON_PATH,
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
    "supersedes_mechanical_metadata": {
        "rule": detect_supersedes_mechanical_metadata,
        "dataset": Path(__file__).with_name("dataset_supersedes.toml"),
        "markdown": REPORT_SUPERSEDES_MD_PATH,
        "json": REPORT_SUPERSEDES_JSON_PATH,
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
    lines.append(f"- dataset cases: `{metrics['dataset_cases']}`")
    lines.append(f"- total cases: `{metrics['total_cases']}`")
    lines.append(f"- excluded cases: `{metrics['excluded_cases']}`")
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
    surface_metrics = result.get("surface_metrics")
    if surface_metrics:
        lines.append(f"- insufficient_sources cases: `{surface_metrics['insufficient_sources']}`")
        lines.append(f"- sources_agree cases: `{surface_metrics['sources_agree']}`")
        lines.append(f"- drift_detected cases: `{surface_metrics['drift_detected']}`")
    supersedes_metrics = result.get("supersedes_metrics")
    if supersedes_metrics:
        lines.append(f"- supersedes out_of_scope cases: `{supersedes_metrics['out_of_scope']}`")
        lines.append(
            f"- supersedes in_scope_contextualized cases: "
            f"`{supersedes_metrics['in_scope_contextualized']}`"
        )
        lines.append(
            f"- supersedes in_scope_mechanical_only cases: "
            f"`{supersedes_metrics['in_scope_mechanical_only']}`"
        )
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
        surface_state = case.get("surface_state")
        surface_suffix = f" surface_state=`{surface_state}`" if surface_state else ""
        supersedes_state = case.get("supersedes_state")
        supersedes_suffix = (
            f" supersedes_state=`{supersedes_state}`" if supersedes_state else ""
        )
        lines.append(
            f"- `{case['id']}` label=`{case['label']}` outcome=`{case['outcome']}` "
            f"expected_suggestion=`{str(case['expected_suggestion']).lower()}` "
            f"actual_suggestion=`{str(case['actual_suggestion']).lower()}` "
            f"expected_confidence=`{conf_expected}` actual_confidence=`{conf_actual}`"
            f"{scope_suffix}{surface_suffix}{supersedes_suffix}"
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
    markdown_target = ensure_allowed_output_path(markdown_path)
    json_target = ensure_allowed_output_path(json_path)
    with file_lock(
        _suggestions_lock_path(markdown_target, json_target),
        label="operational_signals suggestions latest reports",
    ):
        _write_reports_unlocked(result, markdown_path=markdown_target, json_path=json_target)


def _write_reports_unlocked(
    result: dict[str, Any],
    *,
    markdown_path: Path,
    json_path: Path,
) -> None:
    markdown_text = render_markdown(result)
    json_text = json.dumps(result, indent=2) + "\n"
    previous_markdown = _read_existing_text(markdown_path)
    previous_json = _read_existing_text(json_path)
    try:
        _write_text_atomic(markdown_path, markdown_text)
        _write_text_atomic(json_path, json_text)
    except Exception as exc:
        restore_errors: list[Exception] = []
        for path, previous_text in (
            (markdown_path, previous_markdown),
            (json_path, previous_json),
        ):
            try:
                _restore_previous_text(path, previous_text)
            except Exception as restore_exc:
                restore_errors.append(restore_exc)
        if restore_errors:
            raise ExceptionGroup(
                "suggestions report write failed and rollback was incomplete",
                [exc, *restore_errors],
            )
        raise


def _read_existing_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_text_atomic(path: Path, text: str) -> None:
    temp_path = path.with_name(f".{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        with contextlib.suppress(FileNotFoundError):
            temp_path.unlink()


def _restore_previous_text(path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        with contextlib.suppress(FileNotFoundError):
            path.unlink()
        return
    _write_text_atomic(path, previous_text)


def _annotate_broken_ref_scope(result: dict[str, Any], dataset: list[dict[str, Any]]) -> None:
    scope_metrics = {
        "out_of_scope": 0,
        "in_scope_clean": 0,
        "in_scope_broken": 0,
    }
    for case_result, case in zip(result["per_case"], dataset):
        source_artifact = Path(case["source_path"]).as_posix()
        if not _is_in_canonical_scope(source_artifact):
            scope_state = "out_of_scope"
        elif case_result["actual_suggestion"]:
            scope_state = "in_scope_broken"
        else:
            scope_state = "in_scope_clean"
        case_result["scope_state"] = scope_state
        scope_metrics[scope_state] += 1
    result["scope_metrics"] = scope_metrics


def _annotate_surface_drift_states(result: dict[str, Any], dataset: list[dict[str, Any]]) -> None:
    surface_metrics = {
        "insufficient_sources": 0,
        "sources_agree": 0,
        "drift_detected": 0,
    }
    for case_result, case in zip(result["per_case"], dataset):
        sources = extract_current_surface_sources(case)
        counts = extract_current_surface_counts(case)
        if len(sources) < 2 or len(counts) < 2:
            surface_state = "insufficient_sources"
        elif case_result["actual_suggestion"]:
            surface_state = "drift_detected"
        else:
            surface_state = "sources_agree"
        case_result["surface_state"] = surface_state
        surface_metrics[surface_state] += 1
    result["surface_metrics"] = surface_metrics


def _annotate_supersedes_states(result: dict[str, Any], dataset: list[dict[str, Any]]) -> None:
    supersedes_metrics = {
        "out_of_scope": 0,
        "in_scope_contextualized": 0,
        "in_scope_mechanical_only": 0,
    }
    for case_result, case in zip(result["per_case"], dataset):
        state = analyze_supersedes_mechanical_metadata(
            source_artifact=case["source_path"],
            text=case["text"],
        ).state
        case_result["supersedes_state"] = state
        supersedes_metrics[state] += 1
    result["supersedes_metrics"] = supersedes_metrics


def _evaluate_named_rule(name: str) -> dict[str, Any]:
    config = RULE_REGISTRY[name]
    dataset = load_dataset(config["dataset"])
    result = evaluate_dataset(config["rule"], dataset)
    if name == "broken_canonical_refs":
        _annotate_broken_ref_scope(result, dataset)
    if name == "current_surface_drift":
        _annotate_surface_drift_states(result, dataset)
    if name == "supersedes_mechanical_metadata":
        _annotate_supersedes_states(result, dataset)
    return result


def _write_named_rule_reports(name: str, result: dict[str, Any]) -> None:
    config = RULE_REGISTRY[name]
    write_reports(result, markdown_path=config["markdown"], json_path=config["json"])


def _write_named_rule_reports_unlocked(name: str, result: dict[str, Any]) -> None:
    config = RULE_REGISTRY[name]
    _write_reports_unlocked(result, markdown_path=config["markdown"], json_path=config["json"])


def _write_all_rule_reports(results_by_name: dict[str, dict[str, Any]]) -> None:
    all_paths = [
        path
        for name in sorted(results_by_name)
        for path in (
            RULE_REGISTRY[name]["markdown"],
            RULE_REGISTRY[name]["json"],
        )
    ]
    previous_texts: dict[Path, str | None] = {}
    written_paths: list[Path] = []
    with file_lock(
        _suggestions_lock_path(*all_paths),
        label="operational_signals suggestions latest reports",
    ):
        try:
            for name in sorted(results_by_name):
                config = RULE_REGISTRY[name]
                markdown_path = config["markdown"]
                json_path = config["json"]
                previous_texts.setdefault(markdown_path, _read_existing_text(markdown_path))
                previous_texts.setdefault(json_path, _read_existing_text(json_path))
                _write_named_rule_reports_unlocked(name, results_by_name[name])
                written_paths.extend((markdown_path, json_path))
        except Exception as exc:
            restore_errors: list[Exception] = []
            for path in reversed(written_paths):
                try:
                    _restore_previous_text(path, previous_texts[path])
                except Exception as restore_exc:
                    restore_errors.append(restore_exc)
            if restore_errors:
                raise ExceptionGroup(
                    "suggestions batch latest write failed and rollback was incomplete",
                    [exc, *restore_errors],
                )
            raise


def _suggestions_lock_path(*paths: Path) -> Path:
    parents = {path.parent.resolve() for path in paths}
    parent = next(iter(parents), Path(__file__).resolve().parent)
    if len(parents) > 1:
        parent = Path(__file__).resolve().parent
    return parent / ".operational_signals_suggestions_latest.lock"


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
        _write_named_rule_reports(args.rule, result)
        payload: Any = {
            "authority": AUTHORITY,
            "schema_version": SCHEMA_VERSION,
            "rule": result["rule"],
            "metrics": result["metrics"],
            "verdict": result["verdict"],
        }
    else:
        payload = {}
        results_by_name = {}
        for name in sorted(RULE_REGISTRY):
            result = _evaluate_named_rule(name)
            results_by_name[name] = result
            payload[name] = {
                "rule": result["rule"],
                "metrics": result["metrics"],
                "verdict": result["verdict"],
            }
        _write_all_rule_reports(results_by_name)
    print(json.dumps(payload, indent=2))


if __name__ == "__main__":
    main()
