"""Read-only template for external extensions.

Do not read runtime JSON directly.
Do not import from core internals.
Do not write inside the runtime directory.
Do not create a second source of truth.
"""

from __future__ import annotations

from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


class ExtensionError(Exception):
    """Raised when the extension cannot safely produce derived output."""


def render_extension_output(root: str | Path) -> str:
    """Render derived output from the canonical state."""
    try:
        snapshot = StateStore(root).read_snapshot()
    except (StateStoreError, StateValidationError) as exc:
        raise ExtensionError(str(exc)) from exc

    return "\n".join(
        [
            "# Extension Output",
            "",
            f"- Revision: {snapshot.revision}",
            f"- Validation: {snapshot.last_validation.result}",
        ]
    ) + "\n"


def write_extension_output(root: str | Path, output_path: str | Path) -> Path:
    """Write derived output outside runtime-owned paths."""
    store = StateStore(root)
    target = Path(output_path)
    if not target.is_absolute():
        target = Path(root) / target
    target = target.resolve()

    if store.is_runtime_path(target):
        raise ExtensionError(f"output path is reserved for runtime files: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(render_extension_output(root), encoding="utf-8", newline="\n")
    return target
