"""Walk-up project root detection for the cerebro CLI.

Priority (highest to lowest):
  1. Explicit --project-root argument  → source="explicit"
  2. Walk-up from cwd for .cerebro/   → source="cerebro"
  3. Walk-up from cwd for .git/       → source="git"
  4. cwd itself                       → source="cwd"

--project-root is always sovereign; walk-up never overrides an explicit value.
Walk-up stops at the filesystem root and never crosses drive boundaries.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class ResolvedRoot:
    path: Path
    source: str  # "explicit" | "cerebro" | "git" | "cwd"


def find_project_root(
    explicit: str | Path | None = None,
    *,
    start: Path | None = None,
    walk_up: bool = True,
) -> ResolvedRoot:
    """Return the resolved project root and how it was found.

    Parameters
    ----------
    explicit:
        Value of --project-root if the user passed it.  When set, returned
        immediately without any walk-up — always sovereign.
    start:
        Directory to begin the walk-up from.  Defaults to Path.cwd().
    walk_up:
        When False, skip walk-up and return the start directory directly
        (source="cwd").  Set to False for commands that create a new project
        (e.g. ``cerebro init``) so they always target the current directory.
    """
    if explicit is not None:
        return ResolvedRoot(path=Path(explicit).resolve(), source="explicit")

    origin = (start or Path.cwd()).resolve()

    if not walk_up:
        return ResolvedRoot(path=origin, source="cwd")

    # Check both markers at every level so that a nearby .git/ wins over a
    # distant .cerebro/ in a parent directory.  .cerebro/ takes priority when
    # both exist at the same level.
    current = origin
    while True:
        if (current / ".cerebro").exists():
            return ResolvedRoot(path=current, source="cerebro")
        if (current / ".git").exists():
            return ResolvedRoot(path=current, source="git")
        parent = current.parent
        if parent == current:
            break
        current = parent

    return ResolvedRoot(path=origin, source="cwd")
