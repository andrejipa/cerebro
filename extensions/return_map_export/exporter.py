"""Read-only return map export derived from the canonical checkpoint."""

from __future__ import annotations

from pathlib import Path

from core import StateStore
from extensions._support import exported_timestamp, read_snapshot, reject_runtime_output_path, resolve_output_target


class ReturnMapExportError(Exception):
    """Raised when the return map cannot be generated safely."""


def export_return_map_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a short restart map from the canonical checkpoint."""
    store, snapshot = read_snapshot(root, ReturnMapExportError)

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    session = "active" if store.has_active_session() else "inactive"
    exported_at_value = exported_timestamp(exported_at)

    lines = [
        "# Return Map",
        "",
        f"- Exported at: {exported_at_value}",
        f"- Validation: {validation.result}",
        f"- Session: {session}",
        f"- Revision: {snapshot.revision}",
        f"- Updated at: {checkpoint.updated_at}",
        "",
        "## Point Of Return",
        f"- Goal: {checkpoint.goal}",
        f"- Summary: {checkpoint.summary}",
        f"- Next step: {checkpoint.next_step}",
        "",
        "## Constraints",
    ]

    if checkpoint.constraints:
        for item in checkpoint.constraints:
            lines.append(f"- {item}")
    else:
        lines.append("- none")

    lines.extend(
        [
            "",
            "## Sources",
            f"- Count: {len(snapshot.sources)}",
        ]
    )
    for source in snapshot.sources:
        lines.append(f"- {source.path}")

    if validation.details:
        lines.extend(
            [
                "",
                "## Validation Details",
            ]
        )
        for detail in validation.details:
            lines.append(f"- {detail.code}")

    return "\n".join(lines) + "\n"


def write_return_map_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the return map outside runtime-owned paths."""
    store = StateStore(root)
    target = resolve_output_target(root, output_path)
    reject_runtime_output_path(store, target, ReturnMapExportError)

    markdown = export_return_map_markdown(root, exported_at=exported_at)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target
