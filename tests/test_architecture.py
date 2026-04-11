"""Structural and documentary guardrails for the permanent runtime boundary."""

from __future__ import annotations

import ast
import re
import subprocess
import tomllib
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


def extension_package_dirs() -> list[Path]:
    return [
        path
        for path in sorted((REPO_ROOT / "extensions").iterdir())
        if path.is_dir()
        and not path.name.startswith("_")
        and "__pycache__" not in path.parts
        and (path / "__init__.py").exists()
    ]


def tracked_extension_files() -> list[Path]:
    return [path for path in tracked_files() if path.parts and path.parts[0] == "extensions"]


def tracked_extension_git_entries() -> list[tuple[str, Path]]:
    result = subprocess.run(
        ["git", "ls-files", "-s", "--", "extensions"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    entries: list[tuple[str, Path]] = []
    for line in result.stdout.splitlines():
        if not line.strip():
            continue
        metadata, path = line.split("\t", maxsplit=1)
        mode = metadata.split()[0]
        entries.append((mode, Path(path)))
    return entries


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
    def test_primary_docs_converge_on_analyze_as_standard_entrypoint(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        runtime_spec = (REPO_ROOT / "RUNTIME_SPEC.md").read_text(encoding="utf-8")
        core_contract = (REPO_ROOT / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        adr = (REPO_ROOT / "docs" / "adr" / "ADR-008-analyze-is-the-standard-entrypoint.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("start with `cerebro analyze`", readme)
        self.assertNotIn("opens a local session on `resume`", readme)
        self.assertIn("official operational entrypoint", runtime_spec)
        self.assertIn("`analyze` is the standard operational entrypoint", core_contract)
        self.assertIn("`cerebro analyze` as the permanent standard entrypoint", adr)

    def test_readme_separates_bootstrap_flow_from_daily_analyze_flow(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        bootstrap_section = readme.split("## Bootstrap Once", maxsplit=1)[1].split("## Daily Flow", maxsplit=1)[0]
        daily_section = readme.split("## Daily Flow", maxsplit=1)[1]

        self.assertIn("cerebro init", bootstrap_section)
        self.assertIn("cerebro validate", bootstrap_section)
        self.assertNotIn("cerebro analyze", bootstrap_section)
        self.assertIn("cerebro analyze", daily_section)
        self.assertIn("- start with `cerebro analyze`", daily_section)

    def test_core_contract_documents_public_read_only_session_helper(self) -> None:
        core_contract = (REPO_ROOT / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        boundaries = (REPO_ROOT / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        extension_guidelines = (REPO_ROOT / "docs" / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REPO_ROOT / "docs" / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")

        self.assertIn("has_active_session()", core_contract)
        self.assertIn("has_active_session()", boundaries)
        self.assertIn("has_active_session()", extension_guidelines)
        self.assertIn("has_active_session()", integration_surface)

    def test_external_behavior_taxonomy_is_explicit_in_docs(self) -> None:
        extension_guidelines = (REPO_ROOT / "docs" / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REPO_ROOT / "docs" / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")
        extensions_readme = (REPO_ROOT / "extensions" / "README.md").read_text(encoding="utf-8")

        expected_phrases = (
            "`export`: a read-only view or handoff of canonical state.",
            "`analysis`: a read-only transformation of canonical state into a derived report or view.",
            "`integration`: orchestration outside the runtime",
            "These shapes classify behavior, not authority.",
        )

        for phrase in expected_phrases:
            self.assertIn(phrase, extension_guidelines)

        self.assertIn("These are consumer shapes only.", integration_surface)
        self.assertIn("Allowed future `analysis` outside the runtime may:", integration_surface)
        self.assertIn("Forbidden future `analysis` may not:", integration_surface)
        self.assertIn("Allowed `analysis` stays strictly derived:", extension_guidelines)
        self.assertIn("Forbidden `analysis` crosses the boundary:", extension_guidelines)
        self.assertIn("read-only exports and derived analysis only", extensions_readme)
        self.assertIn("outside tracked extension packages", extensions_readme)
        self.assertIn("validation_export", extensions_readme)

    def test_alignment_export_remains_explicitly_blocked_in_docs(self) -> None:
        board = (REPO_ROOT / "docs" / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_ALIGNMENT_EXPORT_BLOCKED.md").read_text(
            encoding="utf-8"
        )
        reuse_map = (REPO_ROOT / "docs" / "LEGACY_REUSE_MAP.md").read_text(encoding="utf-8")

        self.assertIn("`alignment-export` is blocked as a separate front", board)
        self.assertIn("- State: blocked", handoff)
        self.assertIn("`alignment-export` remains blocked", reuse_map)

    def test_external_analysis_boundary_handoff_is_explicit_in_docs(self) -> None:
        board = (REPO_ROOT / "docs" / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_EXTERNAL_ANALYSIS_BOUNDARY.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("## External Analysis Preparation", board)
        self.assertIn("- State: stopped at the safe conceptual boundary", handoff)
        self.assertIn("no analysis module was implemented", handoff)

    def test_robustness_baseline_and_policy_are_explicit_in_docs(self) -> None:
        baseline = (REPO_ROOT / "docs" / "ROBUSTNESS_BASELINE.md").read_text(encoding="utf-8")
        boundaries = (REPO_ROOT / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        extension_guidelines = (REPO_ROOT / "docs" / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REPO_ROOT / "docs" / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")
        core_contract = (REPO_ROOT / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        runtime_spec = (REPO_ROOT / "RUNTIME_SPEC.md").read_text(encoding="utf-8")
        adr = (REPO_ROOT / "docs" / "adr" / "ADR-009-adversarial-revalidation-baseline.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("No critical or moderate failures were found", baseline)
        self.assertIn("exports do not revalidate the runtime by themselves", baseline)
        self.assertIn("Any change that expands or changes the public surface must add proportional adversarial and regression coverage", baseline)
        self.assertIn("Public-surface changes must add proportional adversarial and regression coverage.", boundaries)
        self.assertIn("add proportional adversarial and regression tests whenever an extension changes the public surface", extension_guidelines)
        self.assertIn("Any new or changed integration must add proportional adversarial and regression coverage", integration_surface)
        self.assertIn("do not open a second validation gate", core_contract)
        self.assertIn("reopen validation independently from the persisted canonical state", runtime_spec)
        self.assertIn("Adopt the adversarial revalidation baseline as a permanent evolution rule", adr)

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

    def test_extensions_do_not_use_dynamic_runtime_bypass_primitives(self) -> None:
        forbidden_calls = {
            "__import__",
            "delattr",
            "eval",
            "exec",
            "getattr",
            "globals",
            "hasattr",
            "locals",
            "setattr",
            "vars",
        }
        forbidden_literals = {"__dict__", "__getattribute__", "__setattr__", "__import__"}
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_calls:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} calls {node.func.id}")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "importlib"
                    and node.func.attr == "import_module"
                ):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} calls importlib.import_module")
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Attribute)
                    and isinstance(node.func.value, ast.Name)
                    and node.func.value.id == "object"
                    and node.func.attr == "__getattribute__"
                ):
                    offenders.append(f"{path.relative_to(REPO_ROOT)} calls object.__getattribute__")
            for literal in string_literals_without_docstrings(tree):
                if literal in forbidden_literals:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} contains {literal!r}")

        self.assertEqual(offenders, [])

    def test_extensions_do_not_spawn_processes(self) -> None:
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Import):
                    for alias in node.names:
                        if alias.name == "subprocess":
                            offenders.append(f"{path.relative_to(REPO_ROOT)} imports subprocess")
                if isinstance(node, ast.ImportFrom) and node.module == "subprocess":
                    offenders.append(f"{path.relative_to(REPO_ROOT)} imports from subprocess")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr in {"popen", "spawnl", "spawnle", "spawnlp", "spawnlpe", "spawnv", "spawnve", "spawnvp", "spawnvpe", "system"}
                    ):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} calls os.{node.func.attr}")

        self.assertEqual(offenders, [])

    def test_extensions_do_not_read_files_or_enumerate_directories_directly(self) -> None:
        forbidden_builtin_calls = {"open"}
        forbidden_attribute_calls = {"glob", "iterdir", "open", "read_bytes", "read_text", "rglob"}
        forbidden_os_calls = {"listdir", "scandir", "walk"}
        offenders: list[str] = []

        for path in extension_python_files():
            tree = parse_python(path)
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_builtin_calls:
                    offenders.append(f"{path.relative_to(REPO_ROOT)} calls {node.func.id}")
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    if node.func.attr in forbidden_attribute_calls:
                        offenders.append(f"{path.relative_to(REPO_ROOT)} calls .{node.func.attr}")
                    if (
                        isinstance(node.func.value, ast.Name)
                        and node.func.value.id == "os"
                        and node.func.attr in forbidden_os_calls
                    ):
                        offenders.append(f"{path.relative_to(REPO_ROOT)} calls os.{node.func.attr}")

        self.assertEqual(offenders, [])

    def test_extension_packages_are_listed_in_pyproject(self) -> None:
        pyproject = tomllib.loads((REPO_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
        declared = set(pyproject["tool"]["setuptools"]["packages"])
        expected = {"extensions"} | {f"extensions.{path.name}" for path in extension_package_dirs()}

        self.assertEqual(declared, {"cli", "cli.commands", "core", *sorted(expected)})

    def test_extension_packages_include_readme(self) -> None:
        missing = [
            str(path.relative_to(REPO_ROOT))
            for path in extension_package_dirs()
            if not (path / "README.md").exists()
        ]

        self.assertEqual(missing, [])

    def test_extension_readmes_describe_read_only_behavior(self) -> None:
        missing = []

        for path in extension_package_dirs():
            readme = (path / "README.md").read_text(encoding="utf-8").lower()
            if "read-only" not in readme or "does not" not in readme:
                missing.append(str(path.relative_to(REPO_ROOT)))

        self.assertEqual(missing, [])

    def test_tracked_extension_files_use_only_allowed_shapes(self) -> None:
        allowed_suffixes = {".py", ".md"}
        forbidden_suffixes = {".bat", ".cmd", ".com", ".dll", ".exe", ".ps1", ".sh", ".so"}
        offenders: list[str] = []

        for path in tracked_extension_files():
            if "__pycache__" in path.parts:
                offenders.append(str(path))
                continue
            if path.name == "README.md":
                continue
            suffix = path.suffix.lower()
            if suffix in forbidden_suffixes or suffix not in allowed_suffixes:
                offenders.append(str(path))

        self.assertEqual(offenders, [])

    def test_tracked_extension_files_do_not_start_with_non_python_shebang(self) -> None:
        offenders: list[str] = []

        for relative_path in tracked_extension_files():
            absolute_path = REPO_ROOT / relative_path
            if absolute_path.suffix.lower() != ".py":
                content = absolute_path.read_text(encoding="utf-8")
                if content.startswith("#!"):
                    offenders.append(str(relative_path))

        self.assertEqual(offenders, [])

    def test_tracked_extension_files_are_not_git_symlinks(self) -> None:
        offenders = [str(path) for mode, path in tracked_extension_git_entries() if mode == "120000"]

        self.assertEqual(offenders, [])

    def test_tracked_extension_files_are_not_git_executables(self) -> None:
        offenders = [str(path) for mode, path in tracked_extension_git_entries() if mode == "100755"]

        self.assertEqual(offenders, [])

    def test_analyze_command_remains_orchestration_only(self) -> None:
        path = REPO_ROOT / "cli" / "commands" / "analyze.py"
        tree = parse_python(path)
        forbidden_attributes = {
            "close_session",
            "compute_sha256",
            "initialize",
            "is_runtime_path",
            "load_state",
            "prepare_sources",
            "register_sources",
            "save_state",
            "update_checkpoint",
        }
        offenders: list[str] = []

        for literal in string_literals_without_docstrings(tree):
            if any(fragment in literal for fragment in (".cerebro", "state.json", "session.local.json")):
                offenders.append(f"literal {literal!r}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name == "json" or alias.name.startswith("core."):
                        offenders.append(f"import {alias.name}")
            if isinstance(node, ast.ImportFrom):
                if node.module == "json" or (node.module and node.module.startswith("core.")):
                    offenders.append(f"from {node.module}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_attributes:
                offenders.append(f"attribute .{node.attr}")

        self.assertEqual(offenders, [])
