"""Context-discovery pipeline — read-only analysis over registered sources.

This module loads the canonical Cerebro state via the public `StateStore`
API, walks the target project (with bounded depth and safe directory
filtering), classifies candidate entry files through content signals, and
returns a `DiscoveryReport` with three sections. The pipeline never mutates
anything, never calls into `cli/`, and never produces output that the
authoritative runtime consumes.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import hashlib
import os

from core import StateStore, StateStoreError, StateValidationError

from .content import (
    TEXTUAL_SUFFIXES,
    content_role_signals,
    first_heading,
    read_content_head,
)


MAX_SCAN_DEPTH = 5
DEFAULT_CANDIDATE_LIMIT = 10
CANDIDATE_SCORE_THRESHOLD = 40

IGNORED_DIR_NAMES: frozenset[str] = frozenset(
    {
        "__pycache__",
        "archive",
        "backup",
        "biblioteca_fontes",
        "build",
        "coverage",
        "dados_brutos",
        "dist",
        "env",
        "flash",
        "legacy",
        "livros_fontes",
        "node_modules",
        "quarantine",
        "temp",
        "tmp",
        "venv",
    }
)


class ContextDiscoveryError(RuntimeError):
    """Raised when the discovery pipeline cannot read canonical state."""


@dataclass(frozen=True)
class Candidate:
    """A target-project file that looks context-worthy but is not registered."""

    relative_path: str
    role: str
    score: int
    reasons: tuple[str, ...]
    heading: str


@dataclass(frozen=True)
class DriftRecord:
    """A registered source whose content no longer matches its stored digest."""

    relative_path: str
    registered_sha256: str
    current_sha256: str
    current_heading: str


@dataclass(frozen=True)
class MissingRecord:
    """A registered source that no longer exists in the target project."""

    relative_path: str
    registered_sha256: str


@dataclass(frozen=True)
class DiscoveryReport:
    """Read-only report produced by `discover_context`."""

    project_root: str
    registered_source_count: int
    candidates_not_registered: tuple[Candidate, ...]
    drift_on_registered_sources: tuple[DriftRecord, ...]
    missing_registered_sources: tuple[MissingRecord, ...]
    notes: tuple[str, ...]


def _should_skip_dir(name: str) -> bool:
    lower = name.lower()
    return lower.startswith(".") or lower in IGNORED_DIR_NAMES


def _iter_project_relative_files(root: Path) -> list[Path]:
    relatives: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        relative_root = current_path.relative_to(root)
        depth = 0 if str(relative_root) == "." else len(relative_root.parts)
        dirnames[:] = [
            dirname for dirname in dirnames if not _should_skip_dir(dirname) and depth < MAX_SCAN_DEPTH
        ]
        if depth > MAX_SCAN_DEPTH:
            continue
        for filename in filenames:
            rel = (relative_root / filename) if str(relative_root) != "." else Path(filename)
            relatives.append(rel)
    return relatives


def _compute_sha256(path: Path) -> str | None:
    try:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(65536), b""):
                digest.update(chunk)
        return digest.hexdigest()
    except OSError:
        return None


def _classify_candidate_by_content(
    root: Path, relative_path: Path
) -> tuple[str, int, tuple[str, ...], str] | None:
    """Return `(role, score, reasons, heading)` or None if no content signal fires."""

    if relative_path.suffix.lower() not in TEXTUAL_SUFFIXES:
        return None
    absolute = root / relative_path
    head = read_content_head(absolute)
    if head is None:
        return None
    signals = content_role_signals(relative_path.suffix, head)
    if not signals:
        return None

    scores: dict[str, int] = defaultdict(int)
    reasons: dict[str, list[str]] = defaultdict(list)
    for role, points, reason in signals:
        scores[role] += points
        if reason not in reasons[role]:
            reasons[role].append(reason)

    role = max(scores, key=lambda key: (scores[key], key))
    score = scores[role]
    if score < CANDIDATE_SCORE_THRESHOLD:
        return None
    return role, score, tuple(reasons[role]), first_heading(head)


def discover_context(
    root: str | Path,
    *,
    candidate_limit: int = DEFAULT_CANDIDATE_LIMIT,
) -> DiscoveryReport:
    """Build a read-only `DiscoveryReport` for the target project at `root`."""

    if candidate_limit <= 0:
        raise ValueError(f"candidate_limit must be positive: {candidate_limit}")

    root_path = Path(root).resolve()
    if not root_path.exists() or not root_path.is_dir():
        raise ContextDiscoveryError(f"project root does not exist or is not a directory: {root_path}")

    notes: list[str] = []
    registered: list[tuple[str, str]] = []
    registered_set: set[str] = set()

    try:
        store = StateStore(root_path)
        sources = store.read_sources()
        for source in sources:
            registered.append((source.path, source.sha256))
            registered_set.add(Path(source.path).as_posix())
    except (StateStoreError, StateValidationError) as exc:
        notes.append(f"no registered sources available: {exc}")
    except FileNotFoundError:
        notes.append("no registered sources available: .cerebro/state.json is absent")

    drift: list[DriftRecord] = []
    missing: list[MissingRecord] = []
    for rel_str, sha in registered:
        abs_path = root_path / rel_str
        if not abs_path.exists():
            missing.append(MissingRecord(relative_path=Path(rel_str).as_posix(), registered_sha256=sha))
            continue
        current_sha = _compute_sha256(abs_path)
        if current_sha is None:
            notes.append(f"unable to hash registered source: {rel_str}")
            continue
        if current_sha != sha:
            head = read_content_head(abs_path) or ""
            drift.append(
                DriftRecord(
                    relative_path=Path(rel_str).as_posix(),
                    registered_sha256=sha,
                    current_sha256=current_sha,
                    current_heading=first_heading(head),
                )
            )

    candidates: list[Candidate] = []
    for rel_path in _iter_project_relative_files(root_path):
        posix = rel_path.as_posix()
        if posix in registered_set:
            continue
        classification = _classify_candidate_by_content(root_path, rel_path)
        if classification is None:
            continue
        role, score, reasons, heading = classification
        candidates.append(
            Candidate(
                relative_path=posix,
                role=role,
                score=score,
                reasons=reasons,
                heading=heading,
            )
        )

    candidates.sort(key=lambda c: (-c.score, c.relative_path))
    candidates = candidates[:candidate_limit]

    return DiscoveryReport(
        project_root=str(root_path),
        registered_source_count=len(registered),
        candidates_not_registered=tuple(candidates),
        drift_on_registered_sources=tuple(sorted(drift, key=lambda d: d.relative_path)),
        missing_registered_sources=tuple(sorted(missing, key=lambda m: m.relative_path)),
        notes=tuple(notes),
    )
