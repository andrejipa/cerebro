"""Read-only dashboard shown when Cerebro opens through the context menu."""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

from core import StateStore, StateStoreError, StateValidationError


def render_open_dashboard(root: Path, *, repo_root: Path | None = None) -> str:
    resolved_root = Path(root).resolve()
    resolved_repo_root = Path(repo_root).resolve() if repo_root is not None else Path(__file__).resolve().parents[1]
    latest_iteration, tests = _read_latest_iteration(resolved_repo_root)
    critical_open, high_open = _read_weakness_counts(resolved_repo_root)
    next_item = _read_next_item(resolved_repo_root)
    project_state = _read_project_state(resolved_root)

    lines = [
        "DASHBOARD",
        f"project_root: {resolved_root}",
        f"testes: {tests}",
        f"criticos_abertos: {critical_open}",
        f"altos_abertos: {high_open}",
        f"ultima_iteracao: {latest_iteration}",
        f"proximo_item: {next_item}",
        f"estado_projeto: {project_state['state']}",
    ]
    if "revision" in project_state:
        lines.append(f"revisao: {project_state['revision']}")
        lines.append(f"validacao: {project_state['validation']}")
        lines.append(f"goal: {project_state['goal']}")
        lines.append(f"summary: {project_state['summary']}")
        lines.append(f"next_step: {project_state['next_step']}")
        lines.append(f"updated_at: {project_state['updated_at']}")
    return "\n".join(lines)


def _read_latest_iteration(repo_root: Path) -> tuple[str, str]:
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--oneline"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown", "unknown"

    if result.returncode != 0:
        return "unknown", "unknown"

    line = result.stdout.strip().splitlines()
    if not line:
        return "unknown", "unknown"

    subject = line[0].split(" ", 1)[1] if " " in line[0] else line[0]
    match = re.search(r"(\d+)\s+(?:testes|tests)\b", subject)
    tests = match.group(1) if match else "unknown"
    return subject, tests


def _read_weakness_counts(repo_root: Path) -> tuple[str, str]:
    path = repo_root / "docs" / "operations" / "WEAKNESS_REPORT.md"
    text = _read_text(path)
    if text is None:
        return "unknown", "unknown"
    return _count_open_items(text, "CRÍTICO"), _count_open_items(text, "ALTO")


def _count_open_items(text: str, heading: str) -> str:
    lines = text.splitlines()
    blocks: list[list[str]] = []
    current: list[str] = []
    in_section = False

    for line in lines:
        stripped = line.rstrip()
        if stripped == f"### {heading}":
            in_section = True
            current = []
            continue
        if in_section and stripped.startswith("### "):
            break
        if in_section and stripped.startswith("## "):
            break
        if not in_section:
            continue
        if stripped.startswith("- "):
            if current:
                blocks.append(current)
            current = [stripped]
            continue
        if current:
            current.append(stripped)

    if current:
        blocks.append(current)

    if not blocks:
        return "unknown"
    if any("Nenhum item" in " ".join(block) for block in blocks):
        return "0"
    open_items = sum(1 for block in blocks if "Status atual:" in " ".join(block))
    return str(open_items)


def _read_next_item(repo_root: Path) -> str:
    path = repo_root / "docs" / "operations" / "IMPLEMENTATION_STATUS.md"
    text = _read_text(path)
    if text is None:
        return "unknown"
    match = re.search(r"## Próxima fatia\s+.*?- Qual é: `([^`]+)`", text, flags=re.DOTALL)
    if match is None:
        return "unknown"
    return match.group(1).strip()


def _read_project_state(root: Path) -> dict[str, str]:
    store = StateStore(root)
    if not store.state_path.exists():
        return {"state": "state_absent"}
    try:
        snapshot = store.read_snapshot()
    except StateStoreError:
        return {"state": "state_unavailable"}
    except StateValidationError:
        return {"state": "state_unavailable"}

    checkpoint = snapshot.checkpoint
    return {
        "state": "initialized",
        "revision": str(snapshot.revision),
        "validation": snapshot.last_validation.result,
        "goal": checkpoint.goal,
        "summary": checkpoint.summary,
        "next_step": checkpoint.next_step,
        "updated_at": checkpoint.updated_at,
    }


def _read_text(path: Path) -> str | None:
    try:
        return path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None
