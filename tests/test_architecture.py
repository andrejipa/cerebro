from __future__ import annotations

import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class ArchitectureIsolationTests(unittest.TestCase):
    def test_only_state_store_serializes_json_for_runtime(self) -> None:
        runtime_files = sorted((REPO_ROOT / "core").glob("*.py")) + sorted((REPO_ROOT / "cli").rglob("*.py"))
        offenders: list[str] = []

        for path in runtime_files:
            if path == REPO_ROOT / "core" / "state_store.py":
                continue
            content = path.read_text(encoding="utf-8")
            if "json.load(" in content or "json.dump(" in content:
                offenders.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(offenders, [])

    def test_only_state_store_declares_runtime_state_paths(self) -> None:
        runtime_files = sorted((REPO_ROOT / "core").glob("*.py")) + sorted((REPO_ROOT / "cli").rglob("*.py"))
        forbidden_patterns = (
            r"['\"]\.cerebro['\"]",
            r"['\"]session\.local\.json['\"]",
            r"['\"]state\.json['\"]",
        )
        offenders: list[str] = []

        for path in runtime_files:
            if path == REPO_ROOT / "core" / "state_store.py":
                continue
            content = path.read_text(encoding="utf-8")
            if any(re.search(pattern, content) for pattern in forbidden_patterns):
                offenders.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(offenders, [])
