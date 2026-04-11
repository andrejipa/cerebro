from __future__ import annotations

import re
import subprocess
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def tracked_files() -> list[Path]:
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    return [Path(path) for path in result.stdout.split("\0") if path]


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

    def test_gitignore_covers_non_product_roots(self) -> None:
        content = (REPO_ROOT / ".gitignore").read_text(encoding="utf-8")
        expected_entries = (
            "_backup_pre_cleanup/",
            "_legacy/",
            "_local/",
            "_sandbox/",
            "archive/",
            "biblioteca_fontes/",
            "cerebro_base/",
            "quarantine/",
        )

        missing = [entry for entry in expected_entries if entry not in content]
        self.assertEqual(missing, [])

    def test_tracked_files_do_not_include_legacy_or_local_roots(self) -> None:
        forbidden_roots = {
            "_backup_pre_cleanup",
            "_legacy",
            "_local",
            "_sandbox",
            "archive",
            "biblioteca_fontes",
            "cerebro_base",
            "quarantine",
        }
        offenders = [
            str(path)
            for path in tracked_files()
            if path.parts and path.parts[0] in forbidden_roots
        ]

        self.assertEqual(offenders, [])

    def test_tracked_files_do_not_include_heavy_or_binary_artifacts(self) -> None:
        forbidden_suffixes = {
            ".7z",
            ".db",
            ".gz",
            ".pdf",
            ".rar",
            ".sqlite",
            ".tar",
            ".xls",
            ".xlsx",
            ".zip",
        }
        max_size_bytes = 1 * 1024 * 1024
        offenders: list[str] = []

        for relative_path in tracked_files():
            suffix = relative_path.suffix.lower()
            if suffix in forbidden_suffixes:
                offenders.append(str(relative_path))
                continue

            absolute_path = REPO_ROOT / relative_path
            if absolute_path.stat().st_size > max_size_bytes:
                offenders.append(f"{relative_path} ({absolute_path.stat().st_size} bytes)")

        self.assertEqual(offenders, [])
