"""Contract guardrails for the derived advisory layer.

These tests exist to make the fundamental invariants fail loudly: the
suggestion layer must never import the canonical runtime, must never
write inside `.cerebro/`, and every emitted suggestion must carry the
`human_review_required` flag.
"""

from __future__ import annotations

import ast
import unittest
from pathlib import Path

from experiments.operational_signals.suggestions import evaluate as evaluate_module
from experiments.operational_signals.suggestions.harness import evaluate_dataset, load_dataset
from experiments.operational_signals.suggestions.rules import (
    detect_export_surface_gap,
    detect_stale_system_state,
    detect_supersedes_mechanical_metadata,
)


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


def _python_sources() -> list[Path]:
    return [
        path
        for path in sorted(PACKAGE_ROOT.rglob("*.py"))
        if "__pycache__" not in path.parts
    ]


def _imports_in_module(path: Path) -> list[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def _non_docstring_string_literals(path: Path) -> list[str]:
    """Return every string literal that is not used as a module,
    class, or function docstring. Docstrings frequently describe the
    invariants of this layer (including `.cerebro/`), which would
    otherwise produce false positives for textual checks.
    """
    tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    docstring_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            body = getattr(node, "body", None) or []
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_node_ids.add(id(first.value))

    literals: list[str] = []
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_node_ids
        ):
            literals.append(node.value)
    return literals


class ImportBoundaryTests(unittest.TestCase):
    def test_no_module_imports_core_or_cli(self) -> None:
        forbidden_prefixes = ("core", "cli")
        for module_path in _python_sources():
            with self.subTest(module=str(module_path)):
                for imported in _imports_in_module(module_path):
                    head = imported.split(".", 1)[0]
                    self.assertNotIn(
                        head,
                        forbidden_prefixes,
                        msg=f"{module_path} imports forbidden module: {imported}",
                    )

    def test_no_module_uses_dot_cerebro_in_executable_code(self) -> None:
        """The canonical directory name is allowed to appear in docstrings
        describing the invariant, but must never appear in an executable
        string literal (a path, pattern, or value the code would actually
        use).
        """
        forbidden_fragment = "." + "cerebro"  # split so this file is self-clean
        self_path = Path(__file__).resolve()
        for module_path in _python_sources():
            if module_path.resolve() == self_path:
                continue
            with self.subTest(module=str(module_path)):
                for literal in _non_docstring_string_literals(module_path):
                    self.assertNotIn(
                        forbidden_fragment,
                        literal,
                        msg=f"{module_path} uses the canonical dir name in an executable literal",
                    )


class EmissionContractTests(unittest.TestCase):
    def test_every_emitted_suggestion_is_advisory(self) -> None:
        result = evaluate_dataset()
        emitted = [case for case in result["per_case"] if case["suggestion"] is not None]
        self.assertTrue(emitted, "dataset must produce at least one emitted suggestion")
        for case in emitted:
            suggestion = case["suggestion"]
            self.assertTrue(suggestion["human_review_required"])
            self.assertEqual(suggestion["authority"], "derived-advisory-only")
            self.assertIn(
                suggestion["suggested_failure_mode"],
                {
                    "STALE_INFORMATION",
                    "INSUFFICIENT_EXPORT_SURFACE",
                    "CONTEXT_AMBIGUOUS",
                },
            )

    def test_rule_output_is_either_none_or_a_suggestion(self) -> None:
        empty = detect_stale_system_state(source_artifact="empty", text="")
        self.assertIsNone(empty)

    def test_export_surface_rule_output_is_either_none_or_a_suggestion(self) -> None:
        empty = detect_export_surface_gap(case={"text": "", "exports_text": ""})
        self.assertIsNone(empty)

    def test_rule_registry_points_only_to_local_datasets(self) -> None:
        for config in evaluate_module.RULE_REGISTRY.values():
            dataset_path = Path(config["dataset"]).resolve()
            self.assertTrue(dataset_path.exists())
            self.assertEqual(dataset_path.parent, PACKAGE_ROOT.resolve())

    def test_export_surface_dataset_emits_advisory_suggestions_only(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_export_surface.toml")
        result = evaluate_dataset(detect_export_surface_gap, load_dataset(dataset_path))
        emitted = [case for case in result["per_case"] if case["suggestion"] is not None]
        self.assertTrue(emitted)
        for case in emitted:
            suggestion = case["suggestion"]
            self.assertTrue(suggestion["human_review_required"])
            self.assertEqual(suggestion["authority"], "derived-advisory-only")
            self.assertEqual(
                suggestion["suggested_failure_mode"], "INSUFFICIENT_EXPORT_SURFACE"
            )

    def test_supersedes_dataset_emits_advisory_suggestions_only(self) -> None:
        dataset_path = Path(evaluate_module.__file__).with_name("dataset_supersedes.toml")
        result = evaluate_dataset(
            detect_supersedes_mechanical_metadata,
            load_dataset(dataset_path),
        )
        emitted = [case for case in result["per_case"] if case["suggestion"] is not None]
        self.assertTrue(emitted)
        for case in emitted:
            suggestion = case["suggestion"]
            self.assertTrue(suggestion["human_review_required"])
            self.assertEqual(suggestion["authority"], "derived-advisory-only")
            self.assertEqual(suggestion["suggested_failure_mode"], "CONTEXT_AMBIGUOUS")


if __name__ == "__main__":
    unittest.main()
