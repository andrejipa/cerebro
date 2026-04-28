"""Extract checkpoint text and registered source content from state.json."""
from __future__ import annotations
import json
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class CheckpointText:
    goal: str
    summary: str
    next_step: str
    updated_at: str | None

    @property
    def full_text(self) -> str:
        return " ".join(filter(None, [self.goal, self.summary, self.next_step]))


@dataclass(frozen=True)
class SourceRecord:
    path: str           # relative path as stored in state.json
    sha256: str
    role: str
    content: str | None  # None if file absent or unreadable


def load_state(state_json_path: Path) -> dict:
    """Load and return the raw state.json dict."""
    return json.loads(state_json_path.read_text(encoding="utf-8"))


def extract_checkpoint(state: dict) -> CheckpointText | None:
    """Return CheckpointText from state dict, or None if checkpoint absent."""
    cp = state.get("checkpoint")
    if not cp:
        return None
    return CheckpointText(
        goal=cp.get("goal", ""),
        summary=cp.get("summary", ""),
        next_step=cp.get("next_step", ""),
        updated_at=cp.get("updated_at"),
    )


def extract_sources(state: dict, project_root: Path) -> list[SourceRecord]:
    """Return SourceRecords, reading file content relative to project_root."""
    records = []
    for src in state.get("sources", []):
        path_str = src.get("path", "")
        sha256 = src.get("sha256", "")
        role = src.get("role", "unknown")
        content = _read_source(project_root / path_str)
        records.append(SourceRecord(path=path_str, sha256=sha256, role=role, content=content))
    return records


def _read_source(abs_path: Path) -> str | None:
    try:
        return abs_path.read_text(encoding="utf-8", errors="replace")
    except (OSError, PermissionError):
        return None
