from __future__ import annotations

from pathlib import Path

from core.state_store import StateStore


def seed_registered_source(root: Path, filename: str = "tracked.txt", contents: str = "hello") -> tuple[StateStore, Path]:
    tracked = root / filename
    if not tracked.exists():
        tracked.write_text(contents, encoding="utf-8")
    store = StateStore(root)
    store.register_sources([filename])
    return store, tracked


def seed_checkpointed_runtime(
    root: Path,
    filename: str = "tracked.txt",
    contents: str = "hello",
) -> tuple[StateStore, Path]:
    store, tracked = seed_registered_source(root, filename=filename, contents=contents)
    store.update_checkpoint(
        {
            "goal": "Goal",
            "summary": "Summary",
            "next_step": "Next",
            "constraints": [],
        }
    )
    return store, tracked
