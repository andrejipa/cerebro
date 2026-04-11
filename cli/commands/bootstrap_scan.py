"""Assistive bootstrap scan for candidate entry files.

This command is intentionally outside the runtime authority path. It scans the
project tree by path and filename only, suggests a short human-reviewed
shortlist, and never mutates `.cerebro` or canonical state.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
import os
import re

from cli.output import print_fail, print_ok, user_error


DEFAULT_LIMIT = 6
MAX_SCAN_DEPTH = 5
TEXTUAL_SUFFIXES = {".adoc", ".json", ".md", ".rst", ".toml", ".txt", ".yaml", ".yml"}
IGNORED_DIR_NAMES = {
    "__pycache__",
    "archive",
    "biblioteca_fontes",
    "build",
    "coverage",
    "dados_brutos",
    "dist",
    "flash",
    "livros_fontes",
    "node_modules",
    "quarantine",
    "temp",
    "tmp",
}
PENALIZED_PART_TOKENS = {
    "acervo",
    "antigo",
    "archive",
    "backup",
    "descarte",
    "historico",
    "legacy",
    "old",
    "referencia",
    "referencias",
    "temp",
    "temporario",
}
DATE_PATTERN = re.compile(r"(20\d{2})[-_](\d{2})[-_](\d{2})")


@dataclass(frozen=True)
class BootstrapCandidate:
    relative_path: Path
    artifact_type: str
    signal_label: str
    score: int
    reasons: tuple[str, ...]
    family: str
    date_key: tuple[int, int, int] | None


def _depth(relative_path: Path) -> int:
    return len(relative_path.parts) - 1


def _extract_date_key(relative_path: Path) -> tuple[int, int, int] | None:
    match = DATE_PATTERN.search(relative_path.name)
    if not match:
        return None
    return tuple(int(part) for part in match.groups())


def _signal_label(score: int) -> str:
    if score >= 100:
        return "strong"
    if score >= 75:
        return "medium"
    return "weak"


def _family_for_type(artifact_type: str, lower_name: str) -> str:
    if "retomada" in lower_name or "memoria" in lower_name:
        return "continuity-memory"
    if artifact_type == "canon-operacional":
        return "operational-canon"
    if artifact_type == "readme":
        return "readme"
    if artifact_type == "definicao-de-projeto":
        return "project-definition"
    if artifact_type == "continuidade":
        return "continuity"
    return artifact_type


def _should_skip_dir(name: str) -> bool:
    lower_name = name.lower()
    return lower_name.startswith(".") or lower_name in IGNORED_DIR_NAMES


def _classify_candidate(relative_path: Path) -> BootstrapCandidate | None:
    lower_parts = [part.lower() for part in relative_path.parts]
    lower_name = relative_path.name.lower()
    lower_stem = relative_path.stem.lower()
    depth = _depth(relative_path)

    if relative_path.suffix.lower() not in TEXTUAL_SUFFIXES:
        return None

    scores: dict[str, int] = defaultdict(int)
    reasons: dict[str, list[str]] = defaultdict(list)

    def add(artifact_type: str, points: int, reason: str) -> None:
        scores[artifact_type] += points
        if reason not in reasons[artifact_type]:
            reasons[artifact_type].append(reason)

    if lower_name == "readme.md":
        add("readme", 95, "README naming")

    if lower_name in {"package.json", "pyproject.toml", "app.json", "cargo.toml", "go.mod"}:
        add("definicao-de-projeto", 70, "project-definition file")

    if any(token in lower_stem for token in ("entrada", "inicio", "start", "bootstrap")):
        add("continuidade", 80, "explicit bootstrap or entrypoint naming")

    if any(token in lower_stem for token in ("contexto", "continuidade", "retorno", "retomada", "memoria")):
        add("continuidade", 78, "continuity or return naming")

    if "mestre" in lower_stem:
        add("continuidade", 10, "master-context naming")

    if any(token in lower_stem for token in ("canon", "canone")):
        add("canon-operacional", 85, "explicit canon naming")

    if any(token in lower_stem for token in ("estado_atual", "vigente")):
        add("canon-operacional", 88, "explicit current-state naming")

    if "ordem" in lower_stem and any(token in lower_stem for token in ("canon", "operacional")):
        add("canon-operacional", 72, "ordering signal tied to operational canon")

    if any(token in lower_stem for token in ("projeto", "project", "gdd")):
        add("definicao-de-projeto", 72, "project-definition naming")

    if "controle" in lower_parts:
        add("continuidade", 35, "control context path")
        add("canon-operacional", 12, "control path")

    if "governanca" in lower_parts:
        add("continuidade", 20, "governance path")

    if "trabalho_vigente" in lower_parts:
        add("canon-operacional", 28, "current-work path")

    if "cerebro_base" in lower_parts:
        add("definicao-de-projeto", 25, "project-base path")

    if depth == 0:
        for artifact_type in tuple(scores):
            add(artifact_type, 22, "root-level proximity")
    elif depth == 1:
        for artifact_type in tuple(scores):
            add(artifact_type, 10, "shallow-path proximity")
    elif depth >= 4:
        for artifact_type in tuple(scores):
            add(artifact_type, -12, "deep-path penalty")

    if lower_name.startswith(("00_", "01_")):
        for artifact_type in tuple(scores):
            add(artifact_type, 6, "priority-style naming")

    if any(token in part for part in lower_parts for token in PENALIZED_PART_TOKENS):
        for artifact_type in tuple(scores):
            add(artifact_type, -35, "historical or low-priority path penalty")

    if not scores:
        return None

    artifact_type = max(scores, key=lambda key: (scores[key], key))
    score = scores[artifact_type]
    if score < 60:
        return None

    return BootstrapCandidate(
        relative_path=relative_path,
        artifact_type=artifact_type,
        signal_label=_signal_label(score),
        score=score,
        reasons=tuple(reasons[artifact_type]),
        family=_family_for_type(artifact_type, lower_name),
        date_key=_extract_date_key(relative_path),
    )


def _iter_project_files(root: Path) -> list[Path]:
    candidates: list[Path] = []
    for current_root, dirnames, filenames in os.walk(root):
        current_path = Path(current_root)
        relative_root = current_path.relative_to(root)
        depth = 0 if str(relative_root) == "." else len(relative_root.parts)

        dirnames[:] = [
            dirname
            for dirname in dirnames
            if not _should_skip_dir(dirname) and depth < MAX_SCAN_DEPTH
        ]

        if depth > MAX_SCAN_DEPTH:
            continue

        for filename in filenames:
            relative_path = (relative_root / filename) if str(relative_root) != "." else Path(filename)
            candidates.append(relative_path)
    return candidates


def scan_bootstrap_candidates(root: Path, limit: int = DEFAULT_LIMIT) -> list[BootstrapCandidate]:
    ranked: list[BootstrapCandidate] = []
    for relative_path in _iter_project_files(root):
        candidate = _classify_candidate(relative_path)
        if candidate is not None:
            ranked.append(candidate)

    ranked.sort(
        key=lambda item: (
            -item.score,
            -(int("".join(f"{part:02d}" for part in item.date_key)) if item.date_key else 0),
            _depth(item.relative_path),
            item.relative_path.as_posix().lower(),
        )
    )

    family_limits = {
        "continuity-memory": 1,
        "operational-canon": 1,
        "readme": 1,
        "project-definition": 2,
        "continuity": 2,
    }
    family_counts: dict[str, int] = defaultdict(int)
    shortlist: list[BootstrapCandidate] = []

    for candidate in ranked:
        family_limit = family_limits.get(candidate.family, 1)
        if family_counts[candidate.family] >= family_limit:
            continue
        shortlist.append(candidate)
        family_counts[candidate.family] += 1
        if len(shortlist) >= limit:
            break

    return shortlist


def run_bootstrap_scan(cwd: Path, args: object | None = None) -> int:
    root = cwd if args is None or getattr(args, "root", None) is None else Path(getattr(args, "root")).resolve()
    limit = DEFAULT_LIMIT if args is None else int(getattr(args, "limit", DEFAULT_LIMIT))

    if not root.exists():
        print_fail([user_error("scan_root_missing", f"project root does not exist: {root}")])
        return 1

    if not root.is_dir():
        print_fail([user_error("scan_root_invalid", f"project root is not a directory: {root}")])
        return 1

    shortlist = scan_bootstrap_candidates(root, limit=limit)
    lines = [
        f"scan_root: {root}",
        "mode: assistive-only",
        "state_change: none",
        f"shortlist_limit: {limit}",
        f"candidates_found: {len(shortlist)}",
        "next_action: review the shortlist and choose explicit files for `cerebro import-context --files ...`",
    ]

    for index, candidate in enumerate(shortlist, start=1):
        lines.extend(
            [
                f"{index}. path: {candidate.relative_path.as_posix()}",
                f"   type: {candidate.artifact_type}",
                f"   signal: {candidate.signal_label}",
                f"   reasons: {', '.join(candidate.reasons)}",
            ]
        )

    if not shortlist:
        lines.append("no_strong_candidates: no strong bootstrap candidates were found by path and filename signals alone")

    print_ok(lines)
    return 0
