"""Read-only return map export derived from the canonical checkpoint."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


class ReturnMapExportError(Exception):
    """Raised when the return map cannot be generated safely."""


def export_return_map_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a short restart map from the canonical checkpoint."""
    store = StateStore(root)

    try:
        snapshot = store.read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise ReturnMapExportError(f"failed to read state snapshot: {exc}") from exc

    checkpoint = snapshot.checkpoint
    validation = snapshot.last_validation
    session = "active" if store.has_active_session() else "inactive"
    exported_at_value = exported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")

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
    root_path = Path(root).resolve()
    target = Path(output_path)
    if not target.is_absolute():
        target = root_path / target
    target = target.resolve()

    if store.is_runtime_path(target):
        raise ReturnMapExportError("refusing to write return-map output inside the runtime directory")

    markdown = export_return_map_markdown(root_path, exported_at=exported_at)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target
