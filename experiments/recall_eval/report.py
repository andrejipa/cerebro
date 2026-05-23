from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import uuid

from experiments.operational_signals._file_lock import file_lock


def _variant_metrics_lines(variant: str, metrics: dict) -> list[str]:
    return [
        f"### Variant {variant}",
        "",
        f"- Recall@3: `{metrics['recall_at_3']:.4f}`",
        f"- Precision@3: `{metrics['precision_at_3']:.4f}`",
        f"- Hit@3: `{metrics['hit_at_3']:.4f}`",
        f"- MRR: `{metrics['mrr']:.4f}`",
        f"- Historical error: `{metrics['historical_error_rate']:.4f}`",
        f"- Lateral doc error: `{metrics['lateral_doc_error_rate']:.4f}`",
        f"- Code/doc confusion: `{metrics['code_doc_confusion_rate']:.4f}`",
        "",
    ]


def render_markdown_report(results: dict) -> str:
    lines = [
        "# Experimental Recall Evaluation — Round 2",
        "",
        "- experimental: `true`",
        "- authority: `derived-assistive`",
        "- non-authoritative: `true`",
        "- read-only: `true`",
        "",
        "## Aggregate Metrics By Variant",
        "",
    ]
    for variant, variant_result in results["variants"].items():
        lines.extend(_variant_metrics_lines(variant, variant_result["metrics"]))

    lines.extend(["## By Project", ""])
    for variant, variant_result in results["variants"].items():
        lines.append(f"### Variant {variant}")
        lines.append("")
        for project in variant_result["projects"]:
            lines.append(f"- {project['name']}: Recall@3 `{project['metrics']['recall_at_3']:.4f}`, Precision@3 `{project['metrics']['precision_at_3']:.4f}`, Hit@3 `{project['metrics']['hit_at_3']:.4f}`, MRR `{project['metrics']['mrr']:.4f}`")
        lines.append("")

    lines.extend(["## By Scope", ""])
    for variant, variant_result in results["variants"].items():
        lines.append(f"### Variant {variant}")
        lines.append("")
        for scope_name, metrics in variant_result["by_scope"].items():
            lines.append(f"- {scope_name}: Recall@3 `{metrics['recall_at_3']:.4f}`, Precision@3 `{metrics['precision_at_3']:.4f}`, Hit@3 `{metrics['hit_at_3']:.4f}`, MRR `{metrics['mrr']:.4f}`")
        lines.append("")

    lines.extend(["## By Query Type", ""])
    for variant, variant_result in results["variants"].items():
        lines.append(f"### Variant {variant}")
        lines.append("")
        for query_type, metrics in variant_result["by_query_type"].items():
            lines.append(f"- {query_type}: Recall@3 `{metrics['recall_at_3']:.4f}`, Precision@3 `{metrics['precision_at_3']:.4f}`, Hit@3 `{metrics['hit_at_3']:.4f}`, MRR `{metrics['mrr']:.4f}`")
        lines.append("")

    lines.extend(["## Failure Analysis", ""])
    for key, values in results["failure_analysis"].items():
        lines.append(f"- {key}: `{', '.join(values) if values else 'none'}`")
    lines.append("")
    return "\n".join(lines)


def write_reports(results: dict, *, markdown_path: str | Path, json_path: str | Path) -> None:
    persisted_results = _stable_results_for_persistence(results)
    json_target = Path(json_path)
    markdown_target = Path(markdown_path)
    json_text = json.dumps(persisted_results, indent=2, ensure_ascii=False)
    markdown_text = render_markdown_report(persisted_results)
    with file_lock(_report_lock_path(markdown_target, json_target), label="recall_eval latest report"):
        previous_json = _read_existing_text(json_target)
        previous_markdown = _read_existing_text(markdown_target)
        try:
            _write_text_atomic(json_target, json_text)
            _write_text_atomic(markdown_target, markdown_text)
        except Exception as exc:
            restore_errors: list[Exception] = []
            for target, previous_text in (
                (json_target, previous_json),
                (markdown_target, previous_markdown),
            ):
                try:
                    _restore_previous_text(target, previous_text)
                except Exception as restore_exc:
                    restore_errors.append(restore_exc)
            if restore_errors:
                raise ExceptionGroup(
                    "recall_eval report write failed and rollback was incomplete",
                    [exc, *restore_errors],
                )
            raise


def _report_lock_path(markdown_path: Path, json_path: Path) -> Path:
    targets = [markdown_path, json_path]
    parents = {path.parent.resolve() for path in targets}
    parent = next(iter(parents), Path(__file__).resolve().parent)
    if len(parents) > 1:
        parent = Path(__file__).resolve().parent
    lock_key = "|".join(sorted(path.name for path in targets))
    digest = hashlib.sha256(lock_key.encode("utf-8")).hexdigest()[:16]
    return parent / f".recall_eval_report_latest.{digest}.lock"


def _stable_results_for_persistence(results: dict) -> dict:
    persisted = dict(results)
    if "variants" in persisted:
        persisted["variants"] = {
            variant: _stable_variant_result_for_persistence(variant_result)
            for variant, variant_result in results["variants"].items()
        }
    if "dataset_path" in persisted:
        persisted["dataset_path"] = _stable_path_reference(persisted["dataset_path"])
    if "temp_root" in persisted:
        persisted["temp_root"] = "<omitted>"
    return _sanitize_persisted_value(persisted)


def _stable_variant_result_for_persistence(variant_result: dict) -> dict:
    persisted_variant = dict(variant_result)
    if "projects" in persisted_variant:
        persisted_variant["projects"] = [
            _stable_project_report_for_persistence(project)
            for project in variant_result["projects"]
        ]
    return persisted_variant


def _stable_project_report_for_persistence(project: dict) -> dict:
    persisted_project = dict(project)
    if "root" in persisted_project:
        persisted_project["root"] = _stable_root_reference(str(persisted_project["root"]))
    return persisted_project


def _stable_path_reference(value: str) -> str:
    path = Path(value)
    if not path.parts:
        return "<omitted>"
    return Path(*path.parts[-2:]).as_posix()


def _stable_root_reference(value: str) -> str:
    path = Path(value)
    label = path.name or path.drive
    if not label:
        return "<omitted>"
    return label


_BACKTICKED_ABSOLUTE_PATH_RE = re.compile(
    r"`(?P<path>(?:[A-Za-z]:(?:\\|/)|/(?:Users|home|tmp|var|opt|etc|mnt|media|srv|Volumes)/)[^`\r\n]*)(?:`|$)"
)
_ANGLE_BRACKETED_ABSOLUTE_PATH_RE = re.compile(
    r"<(?P<path>(?:[A-Za-z]:(?:\\|/)|/(?:Users|home|tmp|var|opt|etc|mnt|media|srv|Volumes)/)[^>\r\n]*)(?:>|$)"
)
_PARENTHESIZED_ABSOLUTE_PATH_RE = re.compile(
    r"\((?P<path>(?:[A-Za-z]:(?:\\|/)|/(?:Users|home|tmp|var|opt|etc|mnt|media|srv|Volumes)/)[^\)\r\n]*)(?:\)|$)"
)
_WINDOWS_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w`\(])(?:[A-Za-z]:(?:\\|/)[^\s`\)\"']+)"
)
_UNIX_ABSOLUTE_PATH_RE = re.compile(
    r"(?<![\w`\(])(?:/(?:Users|home|tmp|var|opt|etc|mnt|media|srv|Volumes)/[^\s`\)\"']+)"
)


def _sanitize_persisted_value(value: object, *, field_name: str | None = None) -> object:
    if isinstance(value, dict):
        return {
            key: _sanitize_persisted_value(item, field_name=key)
            for key, item in value.items()
        }
    if isinstance(value, list):
        return [_sanitize_persisted_value(item) for item in value]
    if field_name == "excerpt" and isinstance(value, str):
        return _redact_absolute_paths(value)
    return value


def _redact_absolute_paths(text: str) -> str:
    redacted = _BACKTICKED_ABSOLUTE_PATH_RE.sub("`<absolute-path>`", text)
    redacted = _ANGLE_BRACKETED_ABSOLUTE_PATH_RE.sub("<absolute-path>", redacted)
    redacted = _PARENTHESIZED_ABSOLUTE_PATH_RE.sub("(<absolute-path>)", redacted)
    redacted = _WINDOWS_ABSOLUTE_PATH_RE.sub("<absolute-path>", redacted)
    redacted = _UNIX_ABSOLUTE_PATH_RE.sub("<absolute-path>", redacted)
    return redacted


def _read_existing_text(path: Path) -> str | None:
    if not path.exists():
        return None
    return path.read_text(encoding="utf-8")


def _write_text_atomic(path: Path, text: str) -> None:
    temp_path = path.with_name(f"{path.name}.{uuid.uuid4().hex}.tmp")
    try:
        temp_path.write_text(text, encoding="utf-8")
        os.replace(temp_path, path)
    finally:
        try:
            temp_path.unlink()
        except FileNotFoundError:
            pass


def _restore_previous_text(path: Path, previous_text: str | None) -> None:
    if previous_text is None:
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        return
    _write_text_atomic(path, previous_text)
