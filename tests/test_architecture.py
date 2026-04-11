from __future__ import annotations

import ast
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


def extension_python_files() -> list[Path]:
    return [
        path
        for path in sorted((REPO_ROOT / "extensions").rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def parse_python(path: Path) -> ast.AST:
    return ast.parse(path.read_text(encoding="utf-8"), filename=str(path))


def string_literals_without_docstrings(tree: ast.AST) -> list[str]:
    docstring_nodes: set[ast.AST] = set()

    for node in ast.walk(tree):
        if not isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if not node.body:
            continue
        first = node.body[0]
        if isinstance(first, ast.Expr) and isinstance(first.value, ast.Constant) and isinstance(first.value.value, str):
            docstring_nodes.add(first.value)

    literals: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node not in docstring_nodes:
            literals.append(node.value)
    return literals


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

    def test_extensions_import_only_public_core_api(self) -> None:
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.ImportFrom) and node.module and node.module.startswith("core."):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports {node.module}")
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name.startswith("core."):
                            offenders.append(f"{path.relative_to(REPO_ROOT)} imports {alias.name}")

        self.assertEqual(offenders, [])

    def test_extensions_do_not_reference_runtime_path_literals(self) -> None:
        forbidden_literals = (".cerebro", "state.json", "session.local.json", "core/", "core\\")
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for literal in string_literals_without_docstrings(tree):
                if any(fragment in literal for fragment in forbidden_literals):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} contains {literal!r}")

        self.assertEqual(offenders, [])

    def test_extensions_do_not_import_json_or_use_runtime_json_calls(self) -> None:
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "json":
                            offenders.append(f"{path.relative_to(REPO_ROOT)} imports json")
                if isinstance(node, ast.ImportFrom) and node.module == "json":
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports from json")
                if isinstance(node, ast.Attribute) and isinstance(node.value, ast.Name) and node.value.id == "json":
                    if node.attr in {"load", "loads", "dump", "dumps"}:
                        offenders.append(f"{path.relative_to(REPO_ROOT)} uses json.{node.attr}")

        self.assertEqual(offenders, [])

    def test_extensions_do_not_call_internal_state_store_operations(self) -> None:
        forbidden_attributes = {
            "cerebro_dir",
            "close_session",
            "compute_sha256",
            "events_path",
            "initialize",
            "load_state",
            "logs_dir",
            "open_session",
            "prepare_sources",
            "register_sources",
            "save_state",
            "session_path",
            "state_path",
            "update_checkpoint",
            "validate_state",
        }
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} uses .{node.attr}")

        self.assertEqual(offenders, [])
