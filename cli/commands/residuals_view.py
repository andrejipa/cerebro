"""Read-only CLI view over docs/operations/residuals.toml."""

from __future__ import annotations

import json
import tomllib
from pathlib import Path

from cli.output import print_fail, print_ok, user_error
from extensions._support import exported_timestamp, reject_runtime_output_path, resolve_output_target
from core.state_store import StateStore


class ResidualsViewError(Exception):
    """Raised when the residual taxonomy view cannot be generated safely."""


def _residuals_path(root: Path) -> Path:
    path = root / "docs" / "operations" / "residuals.toml"
    if not path.is_file():
        raise ResidualsViewError(f"residual taxonomy file not found: {path}")
    return path


def load_residuals_taxonomy(root: Path) -> dict:
    path = _residuals_path(root)
    try:
        return tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as exc:
        raise ResidualsViewError(f"failed to parse residual taxonomy: {exc}") from exc


def render_residuals_json(root: Path, exported_at: str | None = None) -> dict:
    payload = load_residuals_taxonomy(root)
    residuals = payload.get("residual", [])
    counts: dict[str, int] = {"total": len(residuals)}

    for entry in residuals:
        if not isinstance(entry, dict):
            continue
        residual_class = entry.get("class")
        if isinstance(residual_class, str) and residual_class:
            counts[residual_class] = counts.get(residual_class, 0) + 1

    return {
        "schema_version": payload.get("schema_version", "1"),
        "export_kind": "residuals_view",
        "exported_at": exported_timestamp(exported_at),
        "counts": counts,
        "residuals": residuals,
    }


def render_residuals_markdown(root: Path, exported_at: str | None = None) -> str:
    view = render_residuals_json(root, exported_at=exported_at)
    lines = [
        "# Residuals View",
        "",
        f"- Exported at: {view['exported_at']}",
        f"- Total residuals: {view['counts']['total']}",
    ]
    for key in sorted(name for name in view["counts"] if name != "total"):
        lines.append(f"- {key}: {view['counts'][key]}")

    lines.extend(["", "## Residuals"])
    for entry in view["residuals"]:
        lines.append(
            f"- {entry['id']}: class={entry['class']}, severity={entry['severity']}, surface={entry['surface']}"
        )
        lines.append(f"  title: {entry['title']}")
        lines.append(f"  unblock gate: {entry['unblock_gate']}")
        lines.append(f"  last reviewed: {entry['last_reviewed']}")
    return "\n".join(lines) + "\n"


def _write_output(root: Path, output_path: str, content: str) -> Path:
    store = StateStore(root)
    target = resolve_output_target(root, output_path)
    reject_runtime_output_path(store, target, ResidualsViewError)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8", newline="\n")
    except OSError as exc:
        raise ResidualsViewError(f"failed to write output file: {target}") from exc
    return target


def run_residuals_view(root: Path, args) -> int:
    output_format = getattr(args, "format", "md")
    exported_at = getattr(args, "exported_at", None)
    output_path = getattr(args, "out", None)

    try:
        if output_format == "json":
            content = json.dumps(render_residuals_json(root, exported_at=exported_at), indent=2) + "\n"
        elif output_format == "md":
            content = render_residuals_markdown(root, exported_at=exported_at)
        else:
            raise ResidualsViewError(f"unsupported output format: {output_format}")

        if output_path:
            target = _write_output(root, output_path, content)
            print_ok(
                [
                    "residuals_view_exported: residuals view written successfully",
                    f"output: {target}",
                ]
            )
        else:
            print(content, end="")
    except ResidualsViewError as exc:
        print_fail([user_error("residuals_view_failed", str(exc))])
        return 1

    return 0
