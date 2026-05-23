from __future__ import annotations

import hashlib
import os
from pathlib import Path
from typing import Any
import uuid

from ._file_lock import file_lock
from .analyzer import build_analysis
from .schema import ensure_allowed_output_path
from .views import render_json, render_markdown


def build_report(path: str | Path | None = None) -> dict[str, Any]:
    return build_analysis(path)


def write_report(
    *,
    registry_path: str | Path | None = None,
    markdown_path: str | Path | None = None,
    json_path: str | Path | None = None,
) -> dict[str, Any]:
    report = build_report(registry_path)
    markdown_target = ensure_allowed_output_path(markdown_path) if markdown_path else None
    json_target = ensure_allowed_output_path(json_path) if json_path else None
    markdown_text = render_markdown(report) if markdown_target else None
    json_text = render_json(report) if json_target else None
    with file_lock(
        _report_lock_path(markdown_target, json_target),
        label="operational_signals latest report",
    ):
        previous_markdown = _read_existing_text(markdown_target) if markdown_target else None
        previous_json = _read_existing_text(json_target) if json_target else None
        try:
            if markdown_target and markdown_text is not None:
                _write_text_atomic(markdown_target, markdown_text)
            if json_target and json_text is not None:
                _write_text_atomic(json_target, json_text)
        except Exception as exc:
            restore_errors: list[Exception] = []
            if markdown_target:
                try:
                    _restore_previous_text(markdown_target, previous_markdown)
                except Exception as restore_exc:
                    restore_errors.append(restore_exc)
            if json_target:
                try:
                    _restore_previous_text(json_target, previous_json)
                except Exception as restore_exc:
                    restore_errors.append(restore_exc)
            if restore_errors:
                raise ExceptionGroup(
                    "operational_signals report write failed and rollback was incomplete",
                    [exc, *restore_errors],
                )
            raise
    return report


def _report_lock_path(markdown_path: Path | None, json_path: Path | None) -> Path:
    targets = [path for path in (markdown_path, json_path) if path is not None]
    parents = {path.parent.resolve() for path in targets}
    parent = next(iter(parents), Path(__file__).resolve().parent)
    if len(parents) > 1:
        parent = Path(__file__).resolve().parent
    family_key = "operational_signals_report_latest"
    digest = hashlib.sha256(family_key.encode("utf-8")).hexdigest()[:16]
    return parent / f".{family_key}.{digest}.lock"


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
