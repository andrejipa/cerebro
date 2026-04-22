"""Structural and documentary guardrails for the permanent runtime boundary."""

from __future__ import annotations

import argparse
import ast
import re
import subprocess
import tomllib
import unittest
from pathlib import Path

import extensions.external_freshness_verifier as external_freshness_module
from cli.main import build_parser


REPO_ROOT = Path(__file__).resolve().parents[1]
REFERENCE_DOCS = REPO_ROOT / "docs" / "reference"
OPERATIONS_DOCS = REPO_ROOT / "docs" / "operations"


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


def extract_public_api_inventory_categories(
    text: str,
    start_marker: str,
    end_markers: tuple[str, ...],
) -> dict[str, set[str]]:
    start = text.index(start_marker) + len(start_marker)
    end = len(text)
    for marker in end_markers:
        position = text.find(marker, start)
        if position != -1:
            end = min(end, position)

    inventory_section = text[start:end]
    categories: dict[str, set[str]] = {}
    current_category: str | None = None

    for raw_line in inventory_section.splitlines():
        line = raw_line.rstrip()
        if line.startswith("- ") and line.endswith(":"):
            current_category = line[2:-1]
            categories[current_category] = set()
            continue
        if current_category is None:
            continue
        stripped = line.strip()
        if stripped.startswith("- `") and stripped.endswith("`"):
            categories[current_category].add(stripped[3:-1].removesuffix("()"))

    return categories


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
    def test_tracked_root_surface_is_minimal_and_docs_are_grouped(self) -> None:
        root_entries = {path.parts[0] for path in tracked_files()}
        self.assertEqual(
            root_entries,
            {
                ".codex",
                ".github",
                ".gitignore",
                "AGENTS.md",
                "README.md",
                "cli",
                "core",
                "docs",
                "experiments",
                "extensions",
                "pyproject.toml",
                "tests",
            },
        )

        docs_children = {path.name for path in (REPO_ROOT / "docs").iterdir() if path.is_dir()}
        self.assertEqual(docs_children, {"adr", "handoffs", "operations", "reference"})

    def test_repository_surface_baseline_is_explicit_and_not_open_for_style_churn(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        current_layer = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_CURRENT_LAYER_CLOSED.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("official visual baseline for human navigation", readme)
        self.assertIn("Do not reorganize it for style alone", readme)
        self.assertIn("fit one of the existing areas or stay in ignored local space", readme)
        self.assertIn("repository surface is now frozen as the official visual baseline", board)
        self.assertIn("allow repository-structure changes only for demonstrated navigation gain", board)
        self.assertIn("repository surface is stabilized as the official visual baseline", current_layer)
        self.assertIn("reopening repository organization for preference or visual taste alone", current_layer)

    def test_primary_docs_converge_on_analyze_as_standard_entrypoint(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        runtime_spec = (REFERENCE_DOCS / "RUNTIME_SPEC.md").read_text(encoding="utf-8")
        core_contract = (REFERENCE_DOCS / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        adr = (REPO_ROOT / "docs" / "adr" / "ADR-008-analyze-is-the-standard-entrypoint.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("start with `cerebro analyze`", readme)
        self.assertNotIn("opens a local session on `resume`", readme)
        self.assertIn("official operational entrypoint", runtime_spec)
        self.assertIn("`analyze` is the standard operational entrypoint", core_contract)
        self.assertIn("`cerebro analyze` as the permanent standard entrypoint", adr)

    def test_operations_baseline_is_explicit_and_infrastructure_oriented(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        operations = (OPERATIONS_DOCS / "OPERATIONS_BASELINE.md").read_text(encoding="utf-8")
        current_layer = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_CURRENT_LAYER_CLOSED.md").read_text(
            encoding="utf-8"
        )
        next_layer = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_NEXT_LAYER_DECISION.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("operational infrastructure, not an open-ended build project", readme)
        self.assertIn("Use the approved operational baseline", readme)
        self.assertIn("# Operations Baseline", operations)
        self.assertIn("## One Daily Protocol", operations)
        self.assertIn("## Mode 1: Bootstrap", operations)
        self.assertIn("## Mode 2: Continuous Work", operations)
        self.assertIn("## Mode 3: Audit / Engineering", operations)
        self.assertIn("## Minimum Execution Protocol", operations)
        self.assertIn("Treat any deviation from this flow as a protocol mismatch.", operations)
        self.assertIn(
            "This flow defines operational discipline for the round; it is not enforced by the CLI as a runtime gate.",
            operations,
        )
        self.assertIn(
            "`status-export` and the audit trail are expected closure artifacts for external rounds as part of operational discipline, not CLI enforcement",
            operations,
        )
        self.assertIn("parallel comparison is allowed only for independent approaches with an explicit join point", operations)
        self.assertIn(
            "successful prior decisions may be reused as success memory, and may slightly reinforce later scoring only as a documented heuristic",
            operations,
        )
        self.assertIn("## Do Not Tinker", operations)
        self.assertIn("current approved operational surface", operations)
        self.assertIn("## Onboarding Quick Start", operations)
        self.assertIn("The default posture is now infrastructure use, not ongoing construction.", freeze_policy)
        self.assertIn("operate it through the approved daily protocol instead", freeze_policy)
        self.assertIn("Follow-up documentation alignment updated the active onboarding surface", board)
        self.assertIn("Current canonical operational names are the seven roles defined in `AGENT_ROLES.md`", board)
        self.assertIn("operational infrastructure", current_layer)
        self.assertIn("Treat the current system as stable operational infrastructure.", next_layer)

    def test_readme_separates_bootstrap_flow_from_daily_analyze_flow(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        bootstrap_section = readme.split("## Bootstrap Once", maxsplit=1)[1].split("## Daily Flow", maxsplit=1)[0]
        daily_section = readme.split("## Daily Flow", maxsplit=1)[1]

        self.assertIn("cerebro init", bootstrap_section)
        self.assertIn("cerebro validate", bootstrap_section)
        self.assertNotIn("cerebro analyze", bootstrap_section)
        self.assertIn("cerebro analyze", daily_section)
        self.assertIn("- start with `cerebro analyze`", daily_section)
        self.assertIn("- answer first whether the work is in `cerebro` or in a `caso`", daily_section)
        self.assertIn("- submit any risky slice to the approval boundary when policy requires it", daily_section)
        self.assertIn("- execute only the approved and properly scoped slice", daily_section)
        self.assertIn("Any daily use that skips this flow is operationally invalid.", daily_section)

    def test_readme_documents_supported_install_path_and_first_source_selection(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        installer = OPERATIONS_DOCS / "install-cerebro.ps1"

        self.assertTrue(installer.exists())
        self.assertIn(r".\docs\operations\install-cerebro.ps1", readme)
        self.assertIn("Cerebro repository root", readme)
        self.assertIn("target project root", readme)
        self.assertIn("If you only read one thing, read this:", readme)
        self.assertIn("Python 3.11 or newer", readme)
        self.assertIn("creates a local `venv\\`", readme)
        self.assertIn("ignore exports and advanced operational docs until this sequence succeeds once", readme)
        self.assertIn("Read it as two steps:", readme)
        self.assertIn("cerebro analyze", readme)
        self.assertIn("the next command is `cerebro import-context --files ...`", readme)
        self.assertIn("choose a small explicit set of human-maintained files", readme)
        self.assertIn("one project-definition file", readme)
        self.assertIn("never generated files, exports, logs, caches, backups", readme)

    def test_core_contract_documents_public_read_only_session_helper(self) -> None:
        core_contract = (REFERENCE_DOCS / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        extension_guidelines = (REFERENCE_DOCS / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")

        self.assertIn("has_active_session()", core_contract)
        self.assertIn("has_active_session()", boundaries)
        self.assertIn("has_active_session()", extension_guidelines)
        self.assertIn("has_active_session()", integration_surface)
        self.assertIn("session-file presence only", core_contract)
        self.assertIn("session-file presence only", boundaries)
        self.assertIn("session-file presence only", extension_guidelines)
        self.assertIn("session-file presence only", integration_surface)

    def test_primary_docs_reject_cli_alias_proliferation(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        core_contract = (REFERENCE_DOCS / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")

        self.assertIn("do not rely on aliases or synonyms", readme)
        self.assertIn("Do not add aliases or synonyms", core_contract)
        self.assertIn("CLI command names stay canonical", boundaries)

    def test_external_behavior_taxonomy_is_explicit_in_docs(self) -> None:
        extension_guidelines = (REFERENCE_DOCS / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")
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

    def test_extension_model_and_template_block_overwriting_registered_sources(self) -> None:
        extension_model = (REFERENCE_DOCS / "EXTENSION_MODEL.md").read_text(encoding="utf-8")
        template_readme = (REPO_ROOT / "extensions" / "_template" / "README.md").read_text(encoding="utf-8")
        template_code = (REPO_ROOT / "extensions" / "_template" / "extension.py").read_text(encoding="utf-8")

        self.assertIn("overwrite registered source files through explicit output paths", extension_model)
        self.assertIn("never overwrite registered source files through output paths", template_readme)
        self.assertIn("registered source files", template_code)

    def test_agent_role_model_is_explicit_and_contract_safe(self) -> None:
        roles = (OPERATIONS_DOCS / "AGENT_ROLES.md").read_text(encoding="utf-8")

        for role in (
            "Orchestrator",
            "Planner",
            "Implementer",
            "Reviewer",
            "Verifier",
            "Researcher",
            "Documenter",
        ):
            self.assertIn(f"## {role}", roles)

        self.assertIn("No role may modify the core", roles)
        self.assertIn("No role may decide canonical context on its own.", roles)
        self.assertIn("No external tool may compete with `analyze` as the operational entrypoint.", roles)
        self.assertIn("No role may create a new source of truth.", roles)
        self.assertIn("official operational baseline", roles)
        self.assertIn("The role set is intentionally lean and composable.", roles)
        self.assertIn("Risk review remains a conditional activity inside the canonical roles.", roles)
        self.assertIn("Tool-provided nicknames, UI aliases, or auto-generated labels are never canonical role names.", roles)
        self.assertIn("Operationally, every agent must be identified by its function name from this role set only.", roles)
        self.assertIn(
            "The runtime does not assign these roles automatically; they are external functional labels applied around the canonical state.",
            roles,
        )
        self.assertIn("1. Orchestrator defines context and blocks ambiguity.", roles)
        self.assertIn("3. Planner turns that evidence into a plan-backed slice.", roles)
        self.assertIn("7. Documenter records the closure artifacts.", roles)
        self.assertIn("No agent may decide canonical context and no external tool may compete with `analyze`.", roles)
        self.assertIn("If the round does not produce structured tracing", roles)
        self.assertIn("The execution protocol lives in `docs/operations/AGENT_PROTOCOL.md`.", roles)
        self.assertIn("## Historical Compatibility Map", roles)
        self.assertIn("### Orquestrador", roles)
        self.assertIn("### Avaliador de Risco", roles)
        self.assertIn("### Guardião", roles)

    def test_agent_protocol_is_explicit_and_does_not_open_next_layer(self) -> None:
        protocol = (OPERATIONS_DOCS / "AGENT_PROTOCOL.md").read_text(encoding="utf-8")
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        next_layer_handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_NEXT_LAYER_DECISION.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("It is descriptive, not aspirational.", protocol)
        self.assertIn(
            "It does not introduce a built-in multi-agent scheduler, a second source of truth, or a new authority above the canonical state.",
            protocol,
        )
        self.assertIn("## Canonical Role Set", protocol)
        self.assertIn("## Context Gate", protocol)
        self.assertIn("Orchestrator asks: `estamos no cerebro ou em um caso?`", protocol)
        self.assertIn("If the answer is ambiguous, the round becomes `blocked-context`.", protocol)
        self.assertIn("## Minimum Operational Flow", protocol)
        self.assertIn("`READ -> ANALYZE -> PLAN -> DELEGATE -> ACT -> VERIFY -> RECORD`", protocol)
        self.assertIn("Any deviation from this sequence is a protocol mismatch.", protocol)
        self.assertIn(
            "This sequence defines operational discipline for the round; it is not enforced by the CLI as a runtime gate.",
            protocol,
        )
        self.assertIn("### READ", protocol)
        self.assertIn("### ANALYZE", protocol)
        self.assertIn("### PLAN", protocol)
        self.assertIn("### DELEGATE", protocol)
        self.assertIn("### ACT", protocol)
        self.assertIn("### VERIFY", protocol)
        self.assertIn("### RECORD", protocol)
        self.assertIn("## Scope Definition", protocol)
        self.assertIn("Before deeper analysis, the round must define scope explicitly:", protocol)
        self.assertIn("what will be analyzed now", protocol)
        self.assertIn("what is out of scope for now", protocol)
        self.assertIn("what should be analyzed later", protocol)
        self.assertIn("in what order the analysis should proceed", protocol)
        self.assertIn("## Decision Discipline", protocol)
        self.assertIn("If the evidence is weak, stop.", protocol)
        self.assertIn("If the DAG is invalid or cyclic, stop.", protocol)
        self.assertIn("If the action is blocked by approval, stop until approval is explicit.", protocol)
        self.assertIn("## Current Runtime Facts That Matter Operationally", protocol)
        self.assertIn("- `light` / `state_only`", protocol)
        self.assertIn("- `moderate` / `structured_state`", protocol)
        self.assertIn("- `heavy` / `governed_execution`", protocol)
        self.assertIn("a new `plan_updated` generation resets active approvals", protocol)
        self.assertIn("verification without pending delta is blocked", protocol)
        self.assertIn("## Success Memory And Limited Reinforcement", protocol)
        self.assertIn("success memory supports tie-breaking and prioritization", protocol)
        self.assertIn("## Parallel Delegation Rules", protocol)
        self.assertIn("Parallel delegation is a controlled optimization.", protocol)
        self.assertIn("## Consolidation Protocol", protocol)
        self.assertIn("The formal consolidation record lives in the append-only audit trail.", protocol)
        self.assertIn("## Approval, Rollback, And Verify", protocol)
        self.assertIn("## Stop Rules", protocol)
        self.assertIn("## Round States", protocol)
        self.assertIn("`awaiting-human-approval`", protocol)
        self.assertIn("Tool nicknames, UI aliases, and historical labels are non-canonical.", protocol)
        self.assertIn("## Ownership And Collision Rules", protocol)
        self.assertIn("one active editor per file at a time", protocol)
        self.assertIn("## Handoff Format", protocol)
        self.assertIn("`Papel funcional: <role>`", protocol)
        self.assertIn("## Record Requirements", protocol)
        self.assertIn("Without that record, closure is incomplete.", protocol)
        self.assertNotIn("## Debate Interno Simulado", protocol)
        self.assertNotIn("Revalidacao Adversarial", protocol)
        self.assertNotIn("## Minimum Mandatory Flow", protocol)
        self.assertIn("Follow-up documentation alignment updated the active onboarding surface", board)
        self.assertIn("The revised external protocol is now the official operational baseline", board)
        self.assertIn(
            "The external agent protocol is now explicit, but it does not open the next product layer by itself.",
            next_layer_handoff,
        )

    def test_refined_agent_team_is_operationally_validated_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        report = (OPERATIONS_DOCS / "REAL_OPERATION_REPORT.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_AGENT_TEAM_VALIDATED.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("Orquestrador opened the round by making the context explicit", board)
        self.assertIn("Quebrador found protocol drift", board)
        self.assertIn("Guardião permitted only the documentation-and-test slice needed to publish the revised protocol", board)
        self.assertIn("The revised external protocol is now the official operational baseline", board)
        self.assertIn("the official operational baseline and remains frozen", board)
        self.assertIn("Team-shape discussion remains closed until a formal role-layer trigger is documented against repeated real rounds.", board)
        self.assertIn("## Revised Operational Model Validation", report)
        self.assertIn("no mandatory explicit context gate between `cerebro` and `caso`", report)
        self.assertIn("`Avaliador de Risco` is justified as a conditional role, especially in fiscal cases like `Portal`", report)
        self.assertIn("no further permanent role is justified by this validation round", report)
        self.assertIn("- State: revised protocol baselined in a documented round", handoff)
        self.assertIn("Orquestrador made the context explicit as `cerebro`, not a live `caso`", handoff)
        self.assertIn("`Guardião` now has the explicit states `permitido`, `permitido com aprovacao humana`, and `bloqueado`", handoff)
        self.assertIn("fiscal cases like `Portal` still require explicit human approval before materially altering EFD behavior", handoff)
        self.assertIn("keep `analyze` as the only canonical operational entrypoint", handoff)

    def test_active_doc_surfaces_require_explicit_context_for_legacy_authority_language(self) -> None:
        legacy_labels = ("Orquestrador", "Comprovador", "Avaliador de Risco", "Guardião")
        clean_surfaces = {
            "README.md": (REPO_ROOT / "README.md").read_text(encoding="utf-8"),
            "docs/operations/AGENT_PROTOCOL.md": (OPERATIONS_DOCS / "AGENT_PROTOCOL.md").read_text(encoding="utf-8"),
            "docs/operations/OPERATIONS_BASELINE.md": (OPERATIONS_DOCS / "OPERATIONS_BASELINE.md").read_text(
                encoding="utf-8"
            ),
            "docs/reference/INTEGRATION_SURFACE.md": (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(
                encoding="utf-8"
            ),
            "docs/reference/EXTERNAL_FRESHNESS_VERIFIER.md": (
                REFERENCE_DOCS / "EXTERNAL_FRESHNESS_VERIFIER.md"
            ).read_text(encoding="utf-8"),
        }

        for surface_name, text in clean_surfaces.items():
            for legacy_label in legacy_labels:
                with self.subTest(surface=surface_name, legacy_label=legacy_label):
                    self.assertNotIn(legacy_label, text)

        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        self.assertIn("historical round evidence", board)
        self.assertIn("Current canonical operational names are the seven roles defined in `AGENT_ROLES.md`", board)

    def test_alignment_export_remains_explicitly_blocked_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_ALIGNMENT_EXPORT_BLOCKED.md").read_text(
            encoding="utf-8"
        )
        reuse_map = (REFERENCE_DOCS / "LEGACY_REUSE_MAP.md").read_text(encoding="utf-8")

        self.assertIn("`alignment-export` is blocked as a separate front", board)
        self.assertIn("- State: blocked", handoff)
        self.assertIn("`alignment-export` remains blocked", reuse_map)

    def test_read_only_exports_stop_handoff_is_explicit_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_READ_ONLY_EXPORTS_EXHAUSTED.md").read_text(
            encoding="utf-8"
        )
        reuse_map = (REFERENCE_DOCS / "LEGACY_REUSE_MAP.md").read_text(encoding="utf-8")

        self.assertIn("## Extensions Read-Only", board)
        self.assertIn("- State: safe limit reached", board)
        self.assertIn("- State: stopped at the current safe limit", handoff)
        self.assertIn("seven constrained read-only exports", handoff)
        self.assertIn(
            "reopen this front only if a concrete and repeated unmet use case is documented",
            handoff,
        )
        self.assertIn("current approved operational surface", handoff)
        self.assertIn("require the formal freeze-break protocol", handoff)
        self.assertIn("seven already implemented", reuse_map)
        self.assertIn("additional external analysis use cases", reuse_map)

    def test_legacy_and_integration_stop_handoffs_are_explicit_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        legacy_handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_LEGACY_LOW_RISK_EXHAUSTED.md").read_text(
            encoding="utf-8"
        )
        integration_handoff = (
            REPO_ROOT / "docs" / "handoffs" / "HANDOFF_INTEGRATION_PREPARATION_STOP.md"
        ).read_text(encoding="utf-8")

        self.assertIn("## Legacy Mining", board)
        self.assertIn("- State: low-risk slice exhausted", board)
        self.assertIn("## Integration Preparation", board)
        self.assertIn("- State: safe limit reached", board)
        self.assertIn("- State: stopped at the current low-risk limit", legacy_handoff)
        self.assertIn(
            "`handoff`, `status`, `return-map`, `impact`, `sources`, `validation`, and `context-index`",
            legacy_handoff,
        )
        self.assertIn("seven now implemented", legacy_handoff)
        self.assertIn("additional external analysis use case", legacy_handoff)
        self.assertIn("- State: stopped at the current safe limit", integration_handoff)

    def test_next_layer_transition_handoff_is_explicit_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_NEXT_LAYER_DECISION.md").read_text(
            encoding="utf-8"
        )
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")

        self.assertIn("## Next Layer Transition", board)
        self.assertIn("- State: deliberate freeze baselined", board)
        self.assertIn("break the freeze only through the formal trigger and resume protocol", board)
        self.assertIn(
            "the external-analysis boundary is documented and implemented up to the current classifier-only limit",
            board,
        )
        self.assertIn("- State: deliberate freeze approved and baselined", handoff)
        self.assertIn("Option 1: Additional Concrete External Analysis", handoff)
        self.assertIn("Option 2: Medium-Risk Graph View", handoff)
        self.assertIn("Option 3: Deliberate Freeze", handoff)
        self.assertIn("Recommended option now:", handoff)
        self.assertIn("Option 3, deliberate freeze after the first minimum external-analysis increment", handoff)
        self.assertIn("current approved operational surface", handoff)
        self.assertIn(
            "a concrete and repeated use case exists that the current approved operational surface cannot satisfy cleanly",
            handoff,
        )
        self.assertIn(
            "Record why the current approved operational surface does not satisfy it cleanly.",
            handoff,
        )
        self.assertIn("Approved Freeze Trigger", handoff)
        self.assertIn("Minimum Safe Advance Rule", handoff)
        self.assertIn(
            "no repeated unmet use case is currently documented against the current approved operational surface",
            handoff,
        )
        self.assertIn("the low-risk export slice was exhausted explicitly", handoff)
        self.assertIn(
            "One minimum read-only external-analysis classifier was implemented without contaminating the runtime, and live acquisition remains blocked.",
            handoff,
        )
        self.assertIn(
            "one narrowly defined additional external-analysis read-only increment beyond the current classifier",
            handoff,
        )
        self.assertIn("Approved pilots that remain inside the freeze:", handoff)
        self.assertIn("local automation bridge MVP as `integration` only", handoff)
        self.assertIn(
            "one narrowly defined additional external-analysis read-only increment beyond the current classifier",
            freeze_policy,
        )

    def test_current_layer_closure_handoff_is_explicit_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_CURRENT_LAYER_CLOSED.md").read_text(
            encoding="utf-8"
        )
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")

        self.assertIn("- State: deliberate freeze baselined, current layer consciously closed", board)
        self.assertIn("residual triage confirmed that no additional clearly safe block remains", board)
        self.assertIn("a final multi-role closure review closed the remaining safe external gaps", board)
        self.assertIn("- State: current layer consciously closed", handoff)
        self.assertIn("The current layer is exhausted under the active contract", handoff)
        self.assertIn("## Final Closure Validation", handoff)
        self.assertIn("Quebrador found only a last small external-safe slice", handoff)
        self.assertIn("Closure is therefore validated collectively", handoff)
        self.assertIn("future point correction", handoff)
        self.assertIn("real architecture block", handoff)
        self.assertIn("explicit next-layer decision", handoff)
        self.assertIn("Pilot Verdict", handoff)
        self.assertIn("Resume Protocol", handoff)
        self.assertIn("current approved operational surface", handoff)
        self.assertIn("additional external-analysis behavior beyond the current classifier", handoff)
        self.assertIn("local automation bridge remains the only approved integration pilot", handoff)
        self.assertIn("The project is deliberately frozen for new capability growth", freeze_policy)
        self.assertIn("The current layer is considered complete until a formal next-layer decision says otherwise.", freeze_policy)
        self.assertIn("Current classification: healthy conservatism, not excessive conservatism.", freeze_policy)
        self.assertIn("current approved operational surface", freeze_policy)
        self.assertIn(
            "a concrete and repeated use case exists that the current approved operational surface cannot satisfy cleanly",
            freeze_policy,
        )
        self.assertIn(
            "Record why the current approved operational surface does not satisfy it cleanly.",
            freeze_policy,
        )
        self.assertIn("one minimum safe increment at a time", freeze_policy)
        self.assertIn("The following do not break the freeze:", freeze_policy)
        self.assertIn("a concrete and repeated use case exists", freeze_policy)
        self.assertIn("curiosity", freeze_policy)
        self.assertIn('abstract desire to get "closer to the ideal"', freeze_policy)
        self.assertIn("A final multi-role closure review closed the last safe external gaps", readme)
        self.assertIn("current approved operational surface is complete for the current demand", readme)
        self.assertIn("runtime, the seven read-only exports, and the currently approved external helpers", readme)

    def test_phase_closure_revalidation_is_explicit_in_docs(self) -> None:
        phase_closure = (OPERATIONS_DOCS / "PHASE_CLOSURE.md").read_text(encoding="utf-8")
        opportunity_map = (OPERATIONS_DOCS / "OPPORTUNITY_MAP.md").read_text(encoding="utf-8")

        self.assertIn("- Estado final da fase: `closed`", phase_closure)
        self.assertIn("- Suite final: `548` testes passando, `6` skips", phase_closure)
        self.assertIn("## Revalidacao Documental De Encerramento", phase_closure)
        self.assertIn(
            "A revalidacao formal de encerramento agora esta coberta por guardas explicitas em `tests/test_doc_governance.py` e `tests/test_architecture.py`.",
            phase_closure,
        )
        self.assertIn(
            "`PHASE_CLOSURE.md` agora faz parte do perimetro automatizado de prova documental.",
            phase_closure,
        )
        self.assertIn("### DOC-002 — Proof Of Stop And Formal Re-Closure", opportunity_map)
        self.assertIn("- Status: `done`", opportunity_map)
        self.assertIn("documenter queue exhausted; await Formal Resume Trigger", opportunity_map)

    def test_external_analysis_boundary_handoff_is_explicit_in_docs(self) -> None:
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_EXTERNAL_ANALYSIS_BOUNDARY.md").read_text(
            encoding="utf-8"
        )
        reference_doc = (REFERENCE_DOCS / "EXTERNAL_FRESHNESS_VERIFIER.md").read_text(encoding="utf-8")
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")

        self.assertIn("## External Analysis Preparation", board)
        self.assertIn("minimum read-only external analysis classifier implemented", board)
        self.assertIn("- State: first concrete external `analysis` increment implemented as a read-only classifier; source acquisition still external", handoff)
        self.assertIn("live source acquisition, source selection, and web querying still remain outside the tracked package", handoff)
        self.assertIn("`Verificador de Atualidade Externa`", handoff)
        self.assertIn("The canonical component name is:", reference_doc)
        self.assertIn("`Verificador de Atualidade Externa`", reference_doc)
        self.assertIn("## Current Minimum Implementation", reference_doc)
        self.assertIn("The tracked minimum increment is now implemented as a read-only classifier over supplied external evidence", reference_doc)
        self.assertIn("normalizes one supplied external bundle through `Normalizador de Bundle Externo` before classification", reference_doc)
        self.assertIn("enforces `search_scope` as a technical domain allowlist over supplied source URLs", reference_doc)
        self.assertIn("collapses equivalent resource URLs into one canonical bundle source before scoring", reference_doc)
        self.assertIn("binds the derived report to the canonical snapshot revision and validation result it actually read", reference_doc)
        self.assertIn("publishes versioned serializable request/report contracts under `external_freshness_contract.v1`", reference_doc)
        self.assertIn("publishes reusable v1 fixture builders and serialized payload fixtures for integration and regression coverage", reference_doc)
        self.assertIn("public schema accessors return defensive snapshots so callers cannot mutate validation state through a shared reference", reference_doc)
        self.assertIn("emits `bundle_identity_scope=report_scoped` in the final report", reference_doc)
        self.assertIn("carries citation and provenance metadata such as normalized domain, locator, acquisition method, trace id", reference_doc)
        self.assertIn("it does not fetch URLs by itself", reference_doc)
        self.assertIn("it does not browse the internet by itself", reference_doc)
        self.assertIn("Live source acquisition remains external to this package.", reference_doc)
        self.assertIn("It is not:", reference_doc)
        self.assertIn("part of the fixed agent role set", reference_doc)
        self.assertIn("Typical position:", reference_doc)
        self.assertIn("explicit evidence review against canonical context", reference_doc)
        self.assertIn("conditional risk review (if needed)", reference_doc)
        self.assertIn("round-specific pre-execution approval boundary", reference_doc)
        self.assertIn("Legacy role labels in this flow are historical aliases only and do not expand the canonical role set.", reference_doc)
        self.assertNotIn("Comprovador", reference_doc)
        self.assertNotIn("Avaliador de Risco", reference_doc)
        self.assertNotIn("Guardião", reference_doc)
        self.assertIn("Inside this component, every external finding starts as `provavel`.", reference_doc)
        self.assertNotIn("classify external findings initially as `provavel` or `hipotese`", reference_doc)
        self.assertIn("It may never be emitted by this component as `comprovado`.", reference_doc)
        self.assertIn("Allowed `allowed_source_classes` values:", reference_doc)
        self.assertIn("`descartada` is output-only and may never appear in this input field.", reference_doc)
        self.assertIn("`search_scope` is not descriptive only.", reference_doc)
        self.assertIn("it is enforced against each supplied source URL after hostname normalization", reference_doc)
        self.assertIn("`internal_proven_items` is not free text.", reference_doc)
        self.assertIn("The standalone public request validator can only prove payload-local binding for these handles.", reference_doc)
        self.assertIn(
            "Canonical snapshot membership for `internal_proven_items` remains a runtime, snapshot-aware check performed by the verifier itself.",
            reference_doc,
        )
        self.assertIn("`canonical_context_relevant` is not a payload field in the tracked contract.", reference_doc)
        self.assertIn("`source:<registered-path>`", reference_doc)
        self.assertIn("`checkpoint.goal`", reference_doc)
        self.assertIn("`sources`: supplied external source metadata already collected outside the package", reference_doc)
        self.assertIn("`findings`: supplied claim descriptors that point to those sources", reference_doc)
        self.assertIn("both must be non-empty tuples before the component may run", reference_doc)
        self.assertIn("`time_sensitivity_context`", reference_doc)
        self.assertIn("`bundle_identity_scope`", reference_doc)
        self.assertIn("`source_date`", reference_doc)
        self.assertIn("`collected_at`", reference_doc)
        self.assertIn("`freshness_status`", reference_doc)
        self.assertIn("Required output shape:", reference_doc)
        self.assertIn("`snapshot_revision`", reference_doc)
        self.assertIn("`snapshot_validation_result`", reference_doc)
        self.assertIn("`source_aliases`", reference_doc)
        self.assertIn("`source_register[]` entries must include:", reference_doc)
        self.assertIn("`bundle_source_key`", reference_doc)
        self.assertIn("`bundle_identity_scope`", reference_doc)
        self.assertIn("`normalized_domain`", reference_doc)
        self.assertIn("`content_hash`", reference_doc)
        self.assertIn("`acquisition_method`", reference_doc)
        self.assertIn("`acquisition_trace_id`", reference_doc)
        self.assertIn("in the serialized payload, these keys are structurally required even when the source does not provide a semantic value", reference_doc)
        self.assertIn("when a semantic value is unavailable, the serialized field remains present and carries the empty-string placeholder used by the contract", reference_doc)
        self.assertIn("`claim_id`", reference_doc)
        self.assertIn("`citation_refs`", reference_doc)
        self.assertIn("`citation_refs` derived from `bundle_source_key`", reference_doc)
        self.assertIn("`claim_time_sensitivity_context`", reference_doc)
        self.assertIn("`promotion_status`", reference_doc)
        self.assertIn("Allowed `promotion_status` values:", reference_doc)
        self.assertIn("Allowed `promotion_basis` values:", reference_doc)
        self.assertIn("Allowed `conflict_type` values:", reference_doc)
        self.assertIn(
            "`autoridade_divergente` is also the fallback bucket for unresolved contradictory claims when attribution collapses to the same canonical source",
            reference_doc,
        )
        self.assertIn("Allowed `resolution_status` values:", reference_doc)
        self.assertIn("the shipping verifier currently emits only `encaminhado_ao_comprovador`", reference_doc)
        self.assertIn("Allowed `required_source_class` values:", reference_doc)
        self.assertIn("the shipping verifier currently emits only `primaria_normativa` or `primaria_tecnica` in `lacunas`", reference_doc)
        self.assertIn("Allowed `acquisition_method` values:", reference_doc)
        self.assertIn("Allowed `bundle_identity_scope` values:", reference_doc)
        self.assertIn("`downgrade_reasons`", reference_doc)
        self.assertIn("Allowed `temporal_risk` values:", reference_doc)
        self.assertIn("`source_aliases[]` entries must include:", reference_doc)
        self.assertIn("`source_register` is the normalized inventory of sources supplied for the run, not only the subset referenced by surviving claims", reference_doc)
        self.assertIn("normalized orphan sources may still appear there when they were supplied in the bundle", reference_doc)
        self.assertIn("the normalized entry may retain richer audit metadata such as `citation_locator`, `source_title`, `acquisition_query`, `acquisition_trace_id`, and `notes` from any surviving alias", reference_doc)
        self.assertIn("Markdown exports may mark source entries as `usage=referenced` or `usage=orphan` for readability", reference_doc)
        self.assertIn("Markdown `usage=referenced` must be derived from all normalized findings for the round, including findings that later become `lacunas`", reference_doc)
        self.assertIn("Markdown exports must state that `source_register.freshness_status` and `source_register.temporal_risk` are aggregated per source, while claim sections remain claim-local", reference_doc)
        self.assertIn("`baixo`", reference_doc)
        self.assertIn("`medio`", reference_doc)
        self.assertIn("`alto`", reference_doc)
        self.assertIn("`recente`", reference_doc)
        self.assertIn("`intermediaria`", reference_doc)
        self.assertIn("`possivelmente_desatualizada`", reference_doc)
        self.assertIn("missing `source_date` must reduce confidence in time-sensitive contexts", reference_doc)
        self.assertIn("older information in a high-sensitivity context must lose weight automatically", reference_doc)
        self.assertIn("conflict with a more recent trustworthy source must reduce the older item's weight automatically", reference_doc)
        self.assertIn("reject supplied source URLs outside the normalized `search_scope`", reference_doc)
        self.assertIn("reject duplicate `source_ids` inside a single finding", reference_doc)
        self.assertIn("record citation and provenance metadata when it is available from the external acquisition step", reference_doc)
        self.assertIn("keep `internal_proven_items` bound to canonical snapshot references instead of caller-defined arbitrary strings", reference_doc)
        self.assertIn("preserve the query string in the current canonical resource URL when no stronger equivalence proof exists", reference_doc)
        self.assertIn("allow query variants to collapse only when a stronger equivalence proof such as matching `content_hash` is already present", reference_doc)
        self.assertIn("keep `content_hash`-based collapse scoped to the same normalized resource family", reference_doc)
        self.assertIn("keep non-empty canonical audit fields authoritative; alias data may backfill only fields that the canonical source leaves empty", reference_doc)
        self.assertIn("## Public Contract", reference_doc)
        self.assertIn("`external_freshness_contract.v1`", reference_doc)
        self.assertIn("schemas use JSON Schema draft `2020-12`", reference_doc)
        self.assertIn("each payload carries `schema_version`", reference_doc)
        self.assertIn("contract payloads are strict and reject unsupported top-level keys", reference_doc)
        self.assertIn("`get_external_freshness_contract_schemas()` is the canonical public schema surface for integrations", reference_doc)
        self.assertIn("`get_external_freshness_contract_fixture_payloads_v1()` is the canonical public fixture-payload surface for integrations", reference_doc)
        self.assertIn("`serialize_*` and `validate_*` define the canonical programmatic wire-contract surface for integrations", reference_doc)
        self.assertIn("serialized request/report payloads keep `content_hash` structurally present as a string field", reference_doc)
        self.assertIn("the contract uses the empty-string placeholder instead of omitting the key", reference_doc)
        self.assertIn(
            "`validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` enforce minimum operational semantics beyond raw shape",
            reference_doc,
        )
        self.assertIn("`validate_external_bundle_normalization_report_payload()` is intentionally shape-only", reference_doc)
        self.assertIn("does not prove semantic coherence between `source_aliases` and `normalized_request`", reference_doc)
        self.assertIn("exported `EXTERNAL_*_SCHEMA_V1` values are compatibility snapshots only and do not define validation authority", reference_doc)
        self.assertIn("exported `build_external_*_fixture_v1()` helpers are Python convenience fixtures and do not define canonical integration payloads", reference_doc)
        self.assertIn("exported `External*` dataclasses are Python composition types and do not define canonical wire payloads", reference_doc)
        self.assertIn("exported `Verified*` dataclasses are Python composition/output types and do not define canonical wire payloads", reference_doc)
        self.assertIn("## Public API Inventory", reference_doc)
        self.assertIn("The package-root public API is intentionally grouped into four categories:", reference_doc)
        self.assertIn("`ExternalFreshnessVerifierError`", reference_doc)
        self.assertIn("`normalize_external_bundle()`", reference_doc)
        self.assertIn("`verify_external_freshness()`", reference_doc)
        self.assertIn("`render_external_freshness_markdown()`", reference_doc)
        self.assertIn("`write_external_freshness_markdown()`", reference_doc)
        self.assertIn("Markdown rendering is a derived operational summary, not a second wire contract.", reference_doc)
        self.assertIn("it must still preserve audit-critical fields such as `url`, `citation_locator`, `why_classified`, `temporal_basis`, `downgrade_reasons`, and citation chains", reference_doc)
        self.assertIn("Embedded newlines in free-text fields must be normalized to escaped `\\n`", reference_doc)
        self.assertIn("Only the canonical integration surface defines wire payload semantics for integrations.", reference_doc)
        self.assertIn("The validator split is deliberate:", reference_doc)
        self.assertIn("`validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` are not shape-only", reference_doc)
        self.assertIn("they enforce the minimum operational semantics already required by the shipping runtime", reference_doc)
        self.assertIn("source references that resolve inside the same payload", reference_doc)
        self.assertIn("`citation_refs` that resolve to known `bundle_source_key` values", reference_doc)
        self.assertIn("`citation_refs` with no duplicates and no empty trailing locator after `@`", reference_doc)
        self.assertIn("claim explanations whose `why_classified` and `temporal_basis` remain non-empty", reference_doc)
        self.assertIn(
            "report claims whose attributed `source_ids` still include at least one non-`descartada` source in `source_register`",
            reference_doc,
        )
        self.assertIn(
            "`promotion_candidate` claims whose `promotion_basis` is explicit, not `nenhuma`, and still backed by at least one attributed `primaria_normativa` source",
            reference_doc,
        )
        self.assertIn("non-promotable claims whose `promotion_basis` remains `nenhuma`", reference_doc)
        self.assertIn("`source_aliases` whose `canonical_source_id` and `canonical_resource_url` resolve to the same canonical source emitted in `source_register`", reference_doc)
        self.assertIn("`conflitos[].claim_id` values that resolve to claims emitted in `provavel` or `hipotese`", reference_doc)
        self.assertIn("the final report carries `bundle_identity_scope=report_scoped`", reference_doc)
        self.assertIn("the local validator for this package intentionally supports only the subset used by `v1`", reference_doc)
        self.assertIn("schema growth beyond that subset stays blocked until an explicit architecture decision opens it", reference_doc)
        self.assertIn("reusable request/report fixture builders and serialized payload fixtures for v1", reference_doc)
        self.assertIn(
            "Serialized fixture payloads remain contract-valid reusable samples, not a guaranteed one-to-one transcript of a single runtime emission path.",
            reference_doc,
        )
        self.assertIn(
            "older information is not discarded only because it is old, but it must be reclassified to `hipotese` when `temporal_risk` is `alto`",
            reference_doc,
        )
        self.assertIn("## Temporal Sensitivity Matrix", reference_doc)
        self.assertIn("Use the following matrix before assigning `time_sensitivity_context`:", reference_doc)
        self.assertIn("The runtime computes the top-level `time_sensitivity_context` from the highest sensitivity present across all finding items in the round.", reference_doc)
        self.assertIn("The public validator enforces the minimum externally checkable subset of that rule", reference_doc)
        self.assertIn("`alta`: laws, regulations, fiscal rules, vendor policies, pricing, security advisories, API behavior, official product documentation", reference_doc)
        self.assertIn("`media`: standards guidance, implementation guides, platform recommendations, operational documentation", reference_doc)
        self.assertIn("`baixa`: conceptual architecture, foundational references, historical records, or stable explanatory material", reference_doc)
        self.assertIn("when one present-day claim mixes recent and stale or undated sources, the temporal basis must say that the claim is mixed", reference_doc)
        self.assertIn("`temporal_risk` must be assigned as follows:", reference_doc)
        self.assertIn("## Current Threshold Windows", reference_doc)
        self.assertIn("`alta`: `recente` up to 90 days; `intermediaria` up to 365 days; after that `possivelmente_desatualizada`", reference_doc)
        self.assertIn("`media`: `recente` up to 365 days; `intermediaria` up to 1095 days; after that `possivelmente_desatualizada`", reference_doc)
        self.assertIn("`baixa`: `recente` up to 1095 days; `intermediaria` up to 3650 days; after that `possivelmente_desatualizada`", reference_doc)
        self.assertIn("## Objective Downgrade Rules", reference_doc)
        self.assertIn("Every external finding enters the component as `provavel`.", reference_doc)
        self.assertIn("It must be downgraded to `hipotese` when at least one of the following is true:", reference_doc)
        self.assertIn("the finding relies on a `possivelmente_desatualizada` source and the claim depends on present-day correctness", reference_doc)
        self.assertIn("the claim depends on normative force, but no trusted source is `primaria_normativa`", reference_doc)
        self.assertIn("the claim cannot identify at least one attributable source entry in `source_register`", reference_doc)
        self.assertIn("A finding may remain `provavel` only when all of the following are true:", reference_doc)
        self.assertIn("none of the mandatory downgrade conditions above applies", reference_doc)
        self.assertIn(
            "a more recent trustworthy source reaches an incompatible operational conclusion about the same claim and the conflict remains unresolved",
            reference_doc,
        )
        self.assertIn("A finding must be discarded instead of downgraded when:", reference_doc)
        self.assertIn("the source URL is outside the enforced `search_scope`", reference_doc)
        self.assertIn("the source date is missing in a temporally sensitive claim and the claim cannot populate the required output fields even as `hipotese`", reference_doc)
        self.assertIn("If `temporal_risk` is `alto`:", reference_doc)
        self.assertIn("the item must be reclassified as `hipotese`", reference_doc)
        self.assertIn("it comes from a clearly identified official primary normative source", reference_doc)
        self.assertIn("it comes from a clearly identified official primary normative source and also points to a canonical internal reference already available to the round", reference_doc)
        self.assertIn("Internal confirmation alone is not enough for `promotion_candidate` inside this component.", reference_doc)
        self.assertIn("A finding reclassified to `hipotese` must leave this component as `not_eligible_for_promotion`.", reference_doc)
        self.assertIn("No item may leave this component as `comprovado`.", reference_doc)
        self.assertIn("No direct decision is permitted from this component", reference_doc)
        self.assertIn("It must not read runtime JSON directly.", reference_doc)
        self.assertIn("decide whether the path should be executed", reference_doc)
        self.assertIn("mutate state", reference_doc)
        self.assertIn("create a new canonical artifact", reference_doc)
        self.assertIn("This downstream handling applies only when the component was explicitly activated for the round; it does not make the component a permanent mandatory gate.", reference_doc)
        self.assertNotIn("`confirmacao_interna_disponivel`", reference_doc)
        self.assertNotIn("`interno_vs_externo`", reference_doc)
        self.assertNotIn("usually", reference_doc)
        self.assertNotIn("rarely", reference_doc)
        self.assertNotIn("safe enough", reference_doc)
        self.assertNotIn("too weak", reference_doc)
        self.assertIn(
            "First concrete external `analysis` use case currently implemented as a minimum read-only classifier over supplied external evidence:",
            integration_surface,
        )
        self.assertIn(
            "produce structured `provavel`, `hipotese`, `conflitos`, `source_date`, `collected_at`, `freshness_status`, `time_sensitivity_context`, `source_strength`, `temporal_risk`, `promotion_status`, `resolution_status`, `source_aliases`, `bundle_source_key`, `bundle_identity_scope`, and citation/provenance metadata",
            integration_surface,
        )
        self.assertIn("normalize one supplied external bundle before classification so equivalent URLs do not inflate evidence count", integration_surface)
        self.assertIn("enforce `search_scope` as a domain allowlist over supplied source URLs", integration_surface)
        self.assertIn("bind its output to the snapshot revision and validation result it actually read", integration_surface)
        self.assertIn("publish versioned serializable request/report contracts with strict top-level payload validation", integration_surface)
        self.assertIn("treat `get_external_freshness_contract_schemas()` as the canonical integration surface for public schemas", integration_surface)
        self.assertIn("treat `get_external_freshness_contract_fixture_payloads_v1()` as the canonical integration surface for public fixture payloads", integration_surface)
        self.assertIn("treat `serialize_*` and `validate_*` as the canonical integration surface for wire payloads", integration_surface)
        self.assertIn("keep serialized `content_hash` structurally present and use the empty-string placeholder when no semantic hash is available", integration_surface)
        self.assertIn(
            "treat `validate_external_freshness_request_payload()` and `validate_external_freshness_report_payload()` as minimum operational-semantic checks, not shape-only validators",
            integration_surface,
        )
        self.assertIn("host-normalized `search_scope`", integration_surface)
        self.assertIn("non-empty claim explanations", integration_surface)
        self.assertIn("promotion basis/status coherence", integration_surface)
        self.assertIn("promotion candidates anchored by at least one `primaria_normativa` source", integration_surface)
        self.assertIn("report claims anchored by at least one non-`descartada` source", integration_surface)
        self.assertIn(
            "treat `internal_proven_items` canonicality as runtime snapshot-aware validation; the standalone request validator only proves payload-local binding between `internal_confirmation_reference` and the supplied handles",
            integration_surface,
        )
        self.assertIn("treat `validate_external_bundle_normalization_report_payload()` as structural contract validation only", integration_surface)
        self.assertIn("alias coherence remains producer/test responsibility", integration_surface)
        self.assertIn("treat exported `EXTERNAL_*_SCHEMA_V1` values as compatibility snapshots only, not validation authority", integration_surface)
        self.assertIn("treat exported `build_external_*_fixture_v1()` helpers as Python convenience fixtures, not canonical integration payloads", integration_surface)
        self.assertIn("treat exported `External*` dataclasses as Python composition helpers, not canonical wire payloads", integration_surface)
        self.assertIn("treat exported `Verified*` dataclasses as Python composition/output helpers, not canonical wire payloads", integration_surface)
        self.assertIn("return defensive public schema snapshots so callers cannot mutate later validation state through a shared reference", integration_surface)
        self.assertIn("publish reusable versioned fixture payloads for integration and regression coverage without expanding runtime authority", integration_surface)
        self.assertIn(
            "treat those fixture payloads as contract-valid reusable samples, not a guaranteed transcript of one specific verifier run",
            integration_surface,
        )
        self.assertIn("mark `bundle_identity_scope=report_scoped` explicitly so bundle keys are not treated as cross-round identifiers", integration_surface)
        self.assertIn("keep `v1` within the locally validated schema subset", integration_surface)
        self.assertIn("block schema-keyword growth until an explicit contract decision exists", integration_surface)
        self.assertIn(
            "downweight stale, undated, or temporally superseded findings automatically and reclassify them to `hipotese` when `temporal_risk` is `alto`",
            integration_surface,
        )
        self.assertIn(
            "follow a formal output schema, temporal sensitivity matrix, and objective downgrade rules instead of operator interpretation",
            integration_surface,
        )
        self.assertIn("leave live source acquisition and web querying outside the tracked package", integration_surface)
        self.assertIn("preserve query strings in canonical resource URLs unless a stronger equivalence proof is supplied", integration_surface)
        self.assertIn("collapse query variants only when stronger equivalence evidence such as matching `content_hash` is already available", integration_surface)
        self.assertIn("promote external evidence directly into runtime truth", integration_surface)
        self.assertIn("treat caller-supplied arbitrary text as canonical internal proof", integration_surface)
        self.assertIn("accept free-form `canonical_context_relevant` blobs as if they were part of the payload contract", integration_surface)
        self.assertIn("bypass the explicit downstream evidence review, conditional risk review, or pre-execution approval boundary", integration_surface)
        self.assertNotIn("stable bundle-source keys", reference_doc)
        self.assertNotIn("stable bundle keys", reference_doc)
        self.assertNotIn("across rounds, not only inside one local request", reference_doc)
        self.assertNotIn("`url` or equivalent identifier", reference_doc)

    def test_external_freshness_public_api_inventory_matches_package_exports(self) -> None:
        reference_doc = (REFERENCE_DOCS / "EXTERNAL_FRESHNESS_VERIFIER.md").read_text(encoding="utf-8")
        readme = (REPO_ROOT / "extensions" / "external_freshness_verifier" / "README.md").read_text(encoding="utf-8")
        expected_categories = {
            "Canonical integration surface": {
                "get_external_freshness_contract_schemas",
                "get_external_freshness_contract_fixture_payloads_v1",
                "serialize_external_freshness_request",
                "serialize_external_bundle_normalization_report",
                "serialize_external_freshness_report",
                "validate_external_freshness_request_payload",
                "validate_external_bundle_normalization_report_payload",
                "validate_external_freshness_report_payload",
            },
            "Compatibility snapshots and Python fixture helpers": {
                "EXTERNAL_FRESHNESS_CONTRACT_VERSION",
                "EXTERNAL_FRESHNESS_REQUEST_SCHEMA_V1",
                "EXTERNAL_BUNDLE_NORMALIZATION_REPORT_SCHEMA_V1",
                "EXTERNAL_FRESHNESS_REPORT_SCHEMA_V1",
                "build_external_freshness_request_fixture_v1",
                "build_external_bundle_normalization_report_fixture_v1",
                "build_external_freshness_report_fixture_v1",
            },
            "Python composition/output types": {
                "ExternalBundleNormalizationReport",
                "ExternalBundleSourceAlias",
                "ExternalFindingInput",
                "ExternalFreshnessReport",
                "ExternalFreshnessRequest",
                "ExternalGap",
                "ExternalSourceInput",
                "VerifiedClaim",
                "VerifiedConflict",
                "VerifiedSourceRecord",
            },
            "Operational read-only helpers": {
                "ExternalFreshnessVerifierError",
                "normalize_external_bundle",
                "verify_external_freshness",
                "render_external_freshness_markdown",
                "write_external_freshness_markdown",
            },
        }

        reference_inventory = extract_public_api_inventory_categories(
            reference_doc,
            "## Public API Inventory",
            ("## Output Contract",),
        )
        readme_inventory = extract_public_api_inventory_categories(
            readme,
            "Public API inventory at package root:",
            ("It does not:",),
        )

        self.assertEqual(reference_inventory, expected_categories)
        self.assertEqual(readme_inventory, expected_categories)
        self.assertEqual(reference_inventory, readme_inventory)
        expected_public_api = set().union(*expected_categories.values())
        self.assertEqual(expected_public_api, set(external_freshness_module.__all__))

    def test_robustness_baseline_and_policy_are_explicit_in_docs(self) -> None:
        baseline = (OPERATIONS_DOCS / "ROBUSTNESS_BASELINE.md").read_text(encoding="utf-8")
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        extension_guidelines = (REFERENCE_DOCS / "EXTENSION_GUIDELINES.md").read_text(encoding="utf-8")
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")
        core_contract = (REFERENCE_DOCS / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        runtime_spec = (REFERENCE_DOCS / "RUNTIME_SPEC.md").read_text(encoding="utf-8")
        adr = (REPO_ROOT / "docs" / "adr" / "ADR-009-adversarial-revalidation-baseline.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("No critical or moderate failures were found", baseline)
        self.assertIn("exports do not revalidate the runtime by themselves", baseline)
        self.assertIn("session-file presence only", baseline)
        self.assertIn("CLI command names remain canonical", baseline)
        self.assertIn("Any change that expands or changes the public surface must add proportional adversarial and regression coverage", baseline)
        self.assertIn("Public-surface changes must add proportional adversarial and regression coverage.", boundaries)
        self.assertIn("add proportional adversarial and regression tests whenever an extension changes the public surface", extension_guidelines)
        self.assertIn("Any new or changed integration must add proportional adversarial and regression coverage", integration_surface)
        self.assertIn("do not open a second validation gate", core_contract)
        self.assertIn("reopen validation independently from the persisted canonical state", runtime_spec)
        self.assertIn("Adopt the adversarial revalidation baseline as a permanent evolution rule", adr)

    def test_primary_docs_make_deliberate_freeze_explicit(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        core_contract = (REFERENCE_DOCS / "CORE_CONTRACT.md").read_text(encoding="utf-8")
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")

        self.assertIn("The project is deliberately frozen for new capability growth", readme)
        self.assertIn("growth beyond the current public surface requires an explicit demand and classification step", core_contract)
        self.assertIn("further capability growth stays deliberately frozen", boundaries)
        self.assertIn("minimum approved external increments were closed", boundaries)
        self.assertIn("The deliberate freeze may be broken only when", freeze_policy)
        self.assertIn(
            "Classify the proposal as `export`, `analysis`, `integration`, or the already-approved `assistive discovery` carve-out.",
            freeze_policy,
        )
        self.assertIn("current approved operational surface", freeze_policy)
        self.assertIn("core expansion or schema growth", freeze_policy)
        self.assertIn("one minimum safe external increment at a time", readme)
        self.assertIn("no additional safe autonomous capability growth remains inside the current contract", readme)
        self.assertIn("`bootstrap-scan` as assistive discovery only", freeze_policy)
        self.assertIn("does not register `sources`", freeze_policy)
        self.assertIn("Assistive Discovery Carve-Out", freeze_policy)
        self.assertIn("suggest candidates only", freeze_policy)

    def test_bootstrap_scan_docs_keep_it_assistive_only(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_NEXT_LAYER_DECISION.md").read_text(
            encoding="utf-8"
        )
        bootstrap_handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_BOOTSTRAP_SCAN_STABLE.md").read_text(
            encoding="utf-8"
        )
        current_layer_handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_CURRENT_LAYER_CLOSED.md").read_text(
            encoding="utf-8"
        )
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        reuse_map = (REFERENCE_DOCS / "LEGACY_REUSE_MAP.md").read_text(encoding="utf-8")
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")

        self.assertIn("bootstrap-scan", readme)
        self.assertIn("It is heuristic assistance, not project truth", readme)
        self.assertIn("does not create `.cerebro`", readme)
        self.assertIn("does not register `sources`", readme)
        self.assertIn("does not bypass the manual `import-context` decision", readme)
        self.assertIn("It is not a resume command, not a truth gate", readme)
        self.assertIn("Assistive bootstrap discovery such as `bootstrap-scan` may suggest candidates", boundaries)
        self.assertIn("it may not define truth, register `sources`, or bypass `import-context`", boundaries)
        self.assertIn("`bootstrap-scan` as assistive discovery only", handoff)
        self.assertIn("suggests candidates but does not decide canonical context", handoff)
        self.assertIn("stable assistive baseline", bootstrap_handoff)
        self.assertIn("it does not read file contents for classification", bootstrap_handoff)
        self.assertIn("The current layer is exhausted under the active contract", current_layer_handoff)
        self.assertIn("bootstrap or validation by heuristic when the heuristic gains authority", reuse_map)
        self.assertIn("assistive-discovery shape for initial bootstrap only", integration_surface)
        self.assertIn("suggest candidates for explicit human review", integration_surface)

    def test_runtime_lock_and_import_confirmation_are_explicit_in_primary_docs(self) -> None:
        readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
        boundaries = (REFERENCE_DOCS / "ARCHITECTURE_BOUNDARIES.md").read_text(encoding="utf-8")
        runtime_spec = (REFERENCE_DOCS / "RUNTIME_SPEC.md").read_text(encoding="utf-8")

        self.assertIn("`import-context` previews a sources diff and requires `y` confirmation", readme)
        self.assertIn("`.cerebro/runtime.lock`", readme)
        self.assertIn("transient coordination file", readme)
        self.assertIn("These persisted runtime files define business continuity", boundaries)
        self.assertIn("`.cerebro/runtime.lock`", boundaries)
        self.assertIn("does not become a second source of truth", boundaries)
        self.assertIn("runtime.lock", runtime_spec)
        self.assertIn("It is coordination only and not canonical state.", runtime_spec)

    def test_automation_bridge_docs_keep_it_external_and_non_authoritative(self) -> None:
        integration_surface = (REFERENCE_DOCS / "INTEGRATION_SURFACE.md").read_text(encoding="utf-8")
        freeze_policy = (OPERATIONS_DOCS / "FREEZE_POLICY.md").read_text(encoding="utf-8")
        board = (OPERATIONS_DOCS / "WORKSTREAM_BOARD.md").read_text(encoding="utf-8")
        handoff = (REPO_ROOT / "docs" / "handoffs" / "HANDOFF_AUTOMATION_BRIDGE_MVP.md").read_text(
            encoding="utf-8"
        )

        self.assertIn("## Automation Bridges", integration_surface)
        self.assertIn("local bridges that remain disposable and non-authoritative", integration_surface)
        self.assertIn("Disposable automation-bridge implementations should stay outside tracked product code", integration_surface)
        self.assertIn("`_local/` is the default incubation area", integration_surface)
        self.assertIn("local automation bridge MVP as `integration` only", freeze_policy)
        self.assertIn("uses disposable structured logs instead of project memory", freeze_policy)
        self.assertIn("## Automation Bridge", board)
        self.assertIn("disposable MVP initialized outside tracked product code", board)
        self.assertIn("## Architecture Options", handoff)
        self.assertIn("Option 1: Local Orquestrador With Agents SDK Plus Codex Executor Over MCP", handoff)
        self.assertIn("Option 2: Deep Integration Through Codex App Server", handoff)
        self.assertIn("Option 3: Minimal Local Orquestrador Using `codex exec`", handoff)
        self.assertIn("Recommended architecture:", handoff)
        self.assertIn("`codex exec --ephemeral --json --output-schema -o`", handoff)
        self.assertIn("does not register `sources`", handoff)
        self.assertIn("outside tracked product code during incubation", handoff)
        self.assertIn("recommend future controlled promotion", handoff)
        self.assertIn("stress-tested the bridge against invalid roots", board)
        self.assertIn("Daily-use rule for automation bridges", integration_surface)
        self.assertIn("always return to Cerebro through `checkpoint` and `analyze`", freeze_policy)
        self.assertIn("## Daily-Use Protocol", handoff)
        self.assertIn("## Non-Authority Contract", handoff)
        self.assertIn("## Operational Hygiene", handoff)
        self.assertIn("## Alert Trigger", handoff)

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
            "discard_session",
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

    def test_session_discard_command_remains_atomic_orchestration_only(self) -> None:
        path = REPO_ROOT / "cli" / "commands" / "session_discard.py"
        tree = parse_python(path)
        forbidden_attributes = {
            "close_session",
            "has_active_session",
            "load_state",
            "open_session",
            "save_state",
            "validate_state",
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

    def test_bootstrap_scan_command_remains_assistive_only(self) -> None:
        path = REPO_ROOT / "cli" / "commands" / "bootstrap_scan.py"
        tree = parse_python(path)
        offenders: list[str] = []
        forbidden_attribute_calls = {"fdopen", "open", "read", "read_bytes", "read_text", "write", "write_bytes", "write_text"}
        forbidden_name_calls = {"open", "run_import_context", "run_init"}
        forbidden_attribute_names = {"register_sources", "save_state", "update_checkpoint", "validate_state"}

        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name in {"json", "subprocess"} or alias.name.startswith("core"):
                        offenders.append(f"import {alias.name}")
                    if alias.name == "io":
                        offenders.append("import io")
            if isinstance(node, ast.ImportFrom):
                if node.module in {"json", "subprocess"} or (node.module and node.module.startswith("core")):
                    offenders.append(f"from {node.module}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_name_calls:
                offenders.append(f"calls {node.func.id}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_attribute_calls:
                    offenders.append(f"calls .{node.func.attr}")
                if node.func.attr in forbidden_attribute_names:
                    offenders.append(f"calls .{node.func.attr}")
                    offenders.append(f"attribute .{node.func.attr}")
            if isinstance(node, ast.Name) and node.id in {"StateStore", "run_import_context"}:
                offenders.append(f"name {node.id}")

        self.assertEqual(offenders, [])

    def test_doctor_command_remains_read_only(self) -> None:
        path = REPO_ROOT / "cli" / "commands" / "doctor.py"
        tree = parse_python(path)
        offenders: list[str] = []
        forbidden_name_calls = {"run_analyze", "run_validate", "run_import_context", "run_init"}
        forbidden_attribute_names = {
            "validate_state",
            "open_session",
            "save_state",
            "register_sources",
            "update_checkpoint",
            "apply_retention",
            "close_session",
        }

        for literal in string_literals_without_docstrings(tree):
            if any(fragment in literal for fragment in (".cerebro", "state.json", "session.local.json")):
                offenders.append(f"literal {literal!r}")

        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Name) and node.func.id in forbidden_name_calls:
                offenders.append(f"calls {node.func.id}")
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in forbidden_attribute_names:
                    offenders.append(f"calls .{node.func.attr}")
            if isinstance(node, ast.Attribute) and node.attr in forbidden_attribute_names:
                offenders.append(f"attribute .{node.attr}")

        self.assertEqual(offenders, [])

    def test_cli_subcommand_surface_is_canonical_and_alias_free(self) -> None:
        parser = build_parser()
        subparsers = next(
            action for action in parser._actions if isinstance(action, argparse._SubParsersAction)
        )
        expected = {
            "analyze",
            "approve",
            "apply",
            "bootstrap-scan",
            "context-index-export",
            "doctor",
            "iteration-commit",
            "init",
            "import-context",
            "checkpoint",
            "plan",
            "residuals-view",
            "resume",
            "rollback",
            "session-discard",
            "handoff-export",
            "impact-export",
            "sources-export",
            "return-map-export",
            "status-export",
            "validation-export",
            "validate",
            "verify",
            "worktree",
        }

        self.assertEqual(set(subparsers.choices), expected)
