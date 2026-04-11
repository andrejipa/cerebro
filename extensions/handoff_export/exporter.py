"""Read-only handoff exporter built on top of the stable core API."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


class HandoffExportError(Exception):
    """Raised when the handoff export cannot be generated."""


def export_handoff_markdown(root: str | Path, exported_at: str | None = None) -> str:
    """Render a short human-readable handoff from the canonical state."""
    try:
        snapshot = StateStore(root).read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise HandoffExportError(str(exc)) from exc

    timestamp = exported_at or datetime.now(timezone.utc).isoformat(timespec="seconds")
    lines = [
        "# Handoff",
        "",
        f"- Exported at: {timestamp}",
        "",
        "## Objetivo",
        snapshot.checkpoint.goal or "-",
        "",
        "## Resumo",
        snapshot.checkpoint.summary or "-",
        "",
        "## Proximo passo",
        snapshot.checkpoint.next_step or "-",
        "",
        "## Restricoes",
    ]

    if snapshot.checkpoint.constraints:
        for item in snapshot.checkpoint.constraints:
            lines.append(f"- {item}")
    else:
        lines.append("- Nenhuma")

    lines.extend(
        [
            "",
            "## Sources registradas",
            f"- Quantidade: {len(snapshot.sources)}",
        ]
    )
    if snapshot.sources:
        for source in snapshot.sources:
            lines.append(f"- {source.path}")
    else:
        lines.append("- Nenhuma")

    lines.extend(
        [
            "",
            "## Estado",
            f"- Revision: {snapshot.revision}",
            f"- Updated at: {snapshot.checkpoint.updated_at or '-'}",
            f"- Last validation: {snapshot.last_validation.result}",
        ]
    )

    return "\n".join(lines) + "\n"


def write_handoff_markdown(root: str | Path, output_path: str | Path, exported_at: str | None = None) -> Path:
    """Write the rendered handoff to an explicit output file."""
    store = StateStore(root)
    markdown = export_handoff_markdown(root, exported_at=exported_at)
    target = Path(output_path)
    if not target.is_absolute():
        target = Path(root) / target
    target = target.resolve()
    _reject_runtime_output_path(store, target)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(markdown, encoding="utf-8", newline="\n")
    return target


def _reject_runtime_output_path(store: StateStore, target: Path) -> None:
    """Reject writes to runtime-owned files and directories."""
    if store.is_runtime_path(target):
        raise HandoffExportError(f"output path is reserved for runtime files: {target}")
