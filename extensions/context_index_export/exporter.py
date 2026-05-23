"""Read-only context index export derived from canonical state."""

from __future__ import annotations

import hashlib
import re
from pathlib import Path, PurePosixPath

from extensions._support import (
    exported_timestamp,
    read_snapshot,
    session_file_presence,
    validation_basis_line,
    write_markdown_output,
)


class ContextIndexExportError(Exception):
    """Raised when the context index cannot be generated safely."""


def _normalized_source_path(path: str) -> str:
    """Normalize a registered source path for read-only grouping and matching."""
    return path.replace("\\", "/")


def _family_label(path: str) -> str:
    """Return the top-level family label for a registered source path."""
    normalized = PurePosixPath(_normalized_source_path(path))
    if len(normalized.parts) <= 1:
        return "(root)"
    return normalized.parts[0]


def _path_token_pattern(candidate: str) -> re.Pattern[str] | None:
    """Build an exact token matcher for path-like strings in checkpoint text."""
    normalized = candidate.strip()
    if not normalized:
        return None
    escaped = re.escape(normalized)
    return re.compile(rf"(?<![\w./-]){escaped}(?![\w./-])")


def _flatten_markdown_field(value: str) -> str:
    """Collapse multiline checkpoint text into one Markdown-safe line."""
    return re.sub(r"\s+", " ", value).strip()


def _checkpoint_anchor_reasons(
    source_path: str,
    checkpoint_text: str,
    *,
    allow_basename_match: bool,
) -> tuple[str, ...]:
    """Return compact checkpoint-derived reasons for highlighting a source path."""
    normalized_path = _normalized_source_path(source_path)
    normalized = PurePosixPath(normalized_path)
    reasons: list[str] = []

    path_pattern = _path_token_pattern(normalized_path)
    basename_pattern = _path_token_pattern(normalized.name) if allow_basename_match else None
    if normalized_path != normalized.name and path_pattern and path_pattern.search(checkpoint_text):
        reasons.append("path")
    if basename_pattern and basename_pattern.search(checkpoint_text):
        reasons.append("basename")

    return tuple(reasons)


def export_context_index_json(root: str | Path, exported_at: str | None = None) -> dict:
    """Render a structured navigation index over registered canonical sources."""
    store, snapshot = read_snapshot(root, ContextIndexExportError)

    exported_at_value = exported_timestamp(exported_at)
    if not snapshot.sources:
        raise ContextIndexExportError("context index requires at least one registered source")

    root_sha256 = hashlib.sha256(str(store.root).encode("utf-8")).hexdigest()
    primary_count = sum(1 for source in snapshot.sources if source.role == "primary")
    reference_count = sum(1 for source in snapshot.sources if source.role == "reference")

    families: dict[str, list[object]] = {}
    basename_counts: dict[str, int] = {}
    for source in snapshot.sources:
        family = _family_label(source.path)
        families.setdefault(family, []).append(source)
        basename = PurePosixPath(_normalized_source_path(source.path)).name
        basename_counts[basename] = basename_counts.get(basename, 0) + 1

    checkpoint = snapshot.checkpoint
    checkpoint_text = "\n".join(
        item.strip()
        for item in (
            checkpoint.goal,
            checkpoint.summary,
            checkpoint.next_step,
            *checkpoint.constraints,
        )
        if item.strip()
    )

    anchors: list[dict[str, object]] = []
    for source in snapshot.sources:
        basename = PurePosixPath(_normalized_source_path(source.path)).name
        reasons = _checkpoint_anchor_reasons(
            source.path,
            checkpoint_text,
            allow_basename_match=basename_counts.get(basename, 0) == 1,
        )
        if reasons:
            anchors.append(
                {
                    "path": source.path,
                    "role": source.role,
                    "reasons": list(reasons),
                }
            )

    return {
        "schema_version": "1",
        "export_kind": "context_index",
        "exported_at": exported_at_value,
        "revision": snapshot.revision,
        "root_sha256": root_sha256,
        "payload": {
            "validation": snapshot.last_validation.result,
            "validation_basis": "persisted canonical record only; exports do not rerun validate",
            "session_file": session_file_presence(store),
            "updated_at": checkpoint.updated_at,
            "registered_sources": len(snapshot.sources),
            "primary_sources": primary_count,
            "reference_sources": reference_count,
            "source_families": len(families),
            "checkpoint_anchors": len(anchors),
            "derivation": "canonical sources + canonical checkpoint only; source contents are never read",
            "checkpoint": {
                "goal": _flatten_markdown_field(checkpoint.goal),
                "summary": _flatten_markdown_field(checkpoint.summary),
                "next_step": _flatten_markdown_field(checkpoint.next_step),
                "constraints": [_flatten_markdown_field(item) for item in checkpoint.constraints],
            },
            "continuity_anchors": anchors,
            "families": [
                {
                    "family": family,
                    "count": len(sources),
                    "sources": [
                        {"path": source.path, "role": source.role}
                        for source in sorted(sources, key=lambda item: item.path)
                    ],
                }
                for family, sources in sorted(
                    families.items(),
                    key=lambda item: (item[0] != "(root)", item[0]),
                )
            ],
            "validation_details": [
                {"code": detail.code} for detail in snapshot.last_validation.details
            ],
        },
    }


def export_context_index_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a compact navigation index over registered canonical sources."""
    store, snapshot = read_snapshot(root, ContextIndexExportError)

    exported_at_value = exported_timestamp(exported_at)
    if not snapshot.sources:
        raise ContextIndexExportError("context index requires at least one registered source")

    primary_count = sum(1 for source in snapshot.sources if source.role == "primary")
    reference_count = sum(1 for source in snapshot.sources if source.role == "reference")

    families: dict[str, list[object]] = {}
    basename_counts: dict[str, int] = {}
    for source in snapshot.sources:
        families.setdefault(_family_label(source.path), []).append(source)
        basename = PurePosixPath(_normalized_source_path(source.path)).name
        basename_counts[basename] = basename_counts.get(basename, 0) + 1

    checkpoint = snapshot.checkpoint
    checkpoint_text = "\n".join(
        item.strip()
        for item in (
            checkpoint.goal,
            checkpoint.summary,
            checkpoint.next_step,
            *checkpoint.constraints,
        )
        if item.strip()
    )

    anchors: list[tuple[object, tuple[str, ...]]] = []
    for source in snapshot.sources:
        basename = PurePosixPath(_normalized_source_path(source.path)).name
        reasons = _checkpoint_anchor_reasons(
            source.path,
            checkpoint_text,
            allow_basename_match=basename_counts.get(basename, 0) == 1,
        )
        if reasons:
            anchors.append((source, reasons))

    goal = _flatten_markdown_field(checkpoint.goal)
    summary = _flatten_markdown_field(checkpoint.summary)
    next_step = _flatten_markdown_field(checkpoint.next_step)
    constraints = tuple(_flatten_markdown_field(item) for item in checkpoint.constraints)

    lines = [
        "# Context Index",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {snapshot.last_validation.result}",
        validation_basis_line(),
        f"- Session file: {session_file_presence(store)}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {checkpoint.updated_at}",
        f"- Registered sources: {len(snapshot.sources)}",
        f"- Primary sources: {primary_count}",
        f"- Reference sources: {reference_count}",
        f"- Source families: {len(families)}",
        f"- Checkpoint anchors: {len(anchors)}",
        "- Derivation: canonical sources + canonical checkpoint only; source contents are never read",
        "",
        "## Checkpoint",
        f"- Goal: {goal}",
        f"- Summary: {summary}",
        f"- Next step: {next_step}",
        "",
        "## Constraints",
    ]

    if constraints:
        for item in constraints:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Continuity Anchors",
            "- Derivation basis: exact case-sensitive path matches or unique basename matches against canonical checkpoint text only",
        ]
    )
    if anchors:
        for source, reasons in sorted(anchors, key=lambda item: item[0].path):
            lines.append(f"- {source.path} [{source.role}] reasons: {', '.join(reasons)}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Source Families",
        ]
    )
    if families:
        sorted_families = sorted(
            families.items(),
            key=lambda item: (item[0] != "(root)", item[0]),
        )
        for family, sources in sorted_families:
            lines.append(f"### {family}")
            lines.append(f"- Count: {len(sources)}")
            for source in sorted(sources, key=lambda item: item.path):
                lines.append(f"- {source.path} [{source.role}]")
    else:
        lines.append("- none")

    if snapshot.last_validation.details:
        lines.extend(
            [
                "",
                "## Validation Details",
            ]
        )
        for detail in snapshot.last_validation.details:
            lines.append(f"- {detail.code}")

    return "\n".join(lines) + "\n"


def write_context_index_markdown(
    root: str | Path,
    output_path: str | Path,
    exported_at: str | None = None,
) -> Path:
    """Write the context index outside runtime-owned paths."""
    markdown = export_context_index_markdown(root, exported_at=exported_at)
    return write_markdown_output(root, output_path, markdown, ContextIndexExportError)
