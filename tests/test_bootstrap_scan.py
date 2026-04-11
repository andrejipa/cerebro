from __future__ import annotations

import io
import os
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.bootstrap_scan import run_bootstrap_scan, scan_bootstrap_candidates
from cli.commands.init import run_init
from core.state_store import StateStore


REPO_ROOT = Path(__file__).resolve().parents[1]


class BootstrapScanTests(unittest.TestCase):
    def test_scan_suggests_strong_entry_files_for_documented_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "controle").mkdir()
            (root / "controle" / "CONTEXTO_MESTRE.md").write_text("context", encoding="utf-8")
            (root / "docs" / "PONTO_2_PACOTE_OFICIAL").mkdir(parents=True)
            (root / "docs" / "PONTO_2_PACOTE_OFICIAL" / "00_ESTADO_ATUAL_E_CONTINUIDADE.md").write_text(
                "state",
                encoding="utf-8",
            )

            shortlist = scan_bootstrap_candidates(root)
            paths = {candidate.relative_path.as_posix() for candidate in shortlist}
            types = {candidate.relative_path.as_posix(): candidate.artifact_type for candidate in shortlist}

            self.assertIn("README.md", paths)
            self.assertIn("controle/CONTEXTO_MESTRE.md", paths)
            self.assertIn("docs/PONTO_2_PACOTE_OFICIAL/00_ESTADO_ATUAL_E_CONTINUIDADE.md", paths)
            self.assertEqual(types["README.md"], "readme")
            self.assertEqual(types["controle/CONTEXTO_MESTRE.md"], "continuidade")
            self.assertEqual(types["docs/PONTO_2_PACOTE_OFICIAL/00_ESTADO_ATUAL_E_CONTINUIDADE.md"], "canon-operacional")

    def test_scan_suggests_project_definition_for_diffuse_project(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            (root / "cerebro_base").mkdir()
            (root / "cerebro_base" / "_PROJETO.md").write_text("project", encoding="utf-8")
            (root / "src").mkdir()
            (root / "src" / "main.ts").write_text("console.log('x')", encoding="utf-8")

            shortlist = scan_bootstrap_candidates(root)
            paths = {candidate.relative_path.as_posix() for candidate in shortlist}

            self.assertIn("README.md", paths)
            self.assertIn("package.json", paths)
            self.assertIn("cerebro_base/_PROJETO.md", paths)

    def test_scan_does_not_create_runtime_when_none_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 6})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertFalse((root / ".cerebro").exists())
            self.assertIn("mode: assistive-only", output)
            self.assertIn("heuristic_basis: path-and-filename signals only", output)
            self.assertIn("state_change: none", output)
            self.assertIn("README.md", output)

    def test_scan_does_not_modify_existing_runtime_state(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            tracked = root / "tracked.txt"
            tracked.write_text("hello", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            store.validate_state()
            before_state = store.state_path.read_text(encoding="utf-8")
            before_revision = store.read_snapshot().revision
            args = type("Args", (), {"root": str(root), "limit": 6})

            run_bootstrap_scan(root, args)

            self.assertEqual(before_state, store.state_path.read_text(encoding="utf-8"))
            self.assertEqual(before_revision, store.read_snapshot().revision)

    def test_scan_skips_hidden_runtime_and_keeps_shortlist_small(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            for index in range(10):
                (root / f"Memoria - Retomada 2026-04-{index + 1:02d}.md").write_text("memory", encoding="utf-8")
            (root / ".cerebro").mkdir()
            (root / ".cerebro" / "README.md").write_text("should not appear", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 4})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertNotIn(".cerebro/README.md", output)
            self.assertLessEqual(output.count(". path:"), 4)

    def test_scan_ignores_noisy_directories_and_false_memory_signals(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "controle").mkdir()
            (root / "controle" / "CONTEXTO_MESTRE.md").write_text("context", encoding="utf-8")
            (root / "controle" / "00_ESTADO_ATUAL.md").write_text("state", encoding="utf-8")
            (root / "docs" / "20_ACERVO_TECNICO" / "05_PARECERES_E_MEMORIAIS").mkdir(parents=True)
            (root / "docs" / "20_ACERVO_TECNICO" / "05_PARECERES_E_MEMORIAIS" / "MEMORIAL_ENTRADAS.md").write_text(
                "memorial",
                encoding="utf-8",
            )
            (root / "node_modules").mkdir()
            (root / "node_modules" / "README.md").write_text("ignore", encoding="utf-8")
            (root / "livros_fontes").mkdir()
            (root / "livros_fontes" / "README.md").write_text("ignore", encoding="utf-8")

            shortlist = scan_bootstrap_candidates(root, limit=6)
            paths = [candidate.relative_path.as_posix() for candidate in shortlist]

            self.assertIn("controle/CONTEXTO_MESTRE.md", paths)
            self.assertIn("controle/00_ESTADO_ATUAL.md", paths)
            self.assertNotIn("docs/20_ACERVO_TECNICO/05_PARECERES_E_MEMORIAIS/MEMORIAL_ENTRADAS.md", paths)
            self.assertNotIn("node_modules/README.md", paths)
            self.assertNotIn("livros_fontes/README.md", paths)

    def test_scan_ignores_virtual_environment_directories(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "venv").mkdir()
            (root / "venv" / "README.md").write_text("ignore", encoding="utf-8")
            (root / "env").mkdir()
            (root / "env" / "README.md").write_text("ignore", encoding="utf-8")

            shortlist = scan_bootstrap_candidates(root, limit=6)
            paths = [candidate.relative_path.as_posix() for candidate in shortlist]

            self.assertIn("README.md", paths)
            self.assertNotIn("venv/README.md", paths)
            self.assertNotIn("env/README.md", paths)

    def test_scan_reports_total_candidates_separately_from_shortlist_limit(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "controle").mkdir()
            (root / "controle" / "CONTEXTO_MESTRE.md").write_text("context", encoding="utf-8")
            (root / "controle" / "00_ESTADO_ATUAL.md").write_text("state", encoding="utf-8")
            (root / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 2})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("candidates_found: 4", output)
            self.assertIn("shortlist_returned: 2", output)

    def test_scan_reports_total_candidates_before_family_pruning(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "package.json").write_text('{"name":"demo"}', encoding="utf-8")
            (root / "cerebro_base").mkdir()
            (root / "cerebro_base" / "_PROJETO.md").write_text("project", encoding="utf-8")
            (root / "cerebro_base" / "GDD_MVP.md").write_text("gdd", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 6})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("candidates_found: 4", output)
            self.assertIn("shortlist_returned: 3", output)

    def test_bootstrap_scan_help_and_subprocess_smoke(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")

            help_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--help"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(help_result.returncode, 0)
            self.assertIn("suggests candidate entry files", help_result.stdout)
            self.assertIn("path and filename", help_result.stdout)
            self.assertIn("signals only", help_result.stdout)
            self.assertIn("does not create or modify runtime state", help_result.stdout)
            self.assertIn("greater than zero", help_result.stdout)

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--root", str(root), "--limit", "3"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("mode: assistive-only", result.stdout)
            self.assertIn("heuristic_basis: path-and-filename signals only", result.stdout)
            self.assertIn("candidates_found: 1", result.stdout)
            self.assertIn("shortlist_returned: 1", result.stdout)
            self.assertIn("suggested_type: readme", result.stdout)
            self.assertIn("next_action:", result.stdout)
            self.assertIn("README.md", result.stdout)
            self.assertNotIn("official", result.stdout.lower())

    def test_scan_rejects_non_positive_limit_explicitly(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 0})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 1)
            self.assertIn("scan_limit_invalid", output)
            self.assertFalse((root / ".cerebro").exists())

    def test_scan_subprocess_rejects_invalid_limit_and_missing_root(self) -> None:
        invalid_limit = subprocess.run(
            [sys.executable, "-m", "cli.main", "bootstrap-scan", "--limit", "0"],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(invalid_limit.returncode, 1)
        self.assertIn("scan_limit_invalid", invalid_limit.stdout)

        missing_root = subprocess.run(
            [sys.executable, "-m", "cli.main", "bootstrap-scan", "--root", str(REPO_ROOT / "__missing__")],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
        )
        self.assertEqual(missing_root.returncode, 1)
        self.assertIn("scan_root_missing", missing_root.stdout)

    def test_scan_subprocess_rejects_root_that_is_not_a_directory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            file_path = root / "README.md"
            file_path.write_text("root readme", encoding="utf-8")

            invalid_root = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--root", str(file_path)],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )

            self.assertEqual(invalid_root.returncode, 1)
            self.assertIn("scan_root_invalid", invalid_root.stdout)

    def test_scan_subprocess_preserves_existing_runtime_byte_for_byte(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            tracked = root / "tracked.txt"
            tracked.write_text("tracked", encoding="utf-8")
            run_init(root, None)
            store = StateStore(root)
            store.register_sources(["tracked.txt"])
            store.update_checkpoint(
                {
                    "goal": "Goal",
                    "summary": "Summary",
                    "next_step": "Next",
                    "constraints": [],
                }
            )
            store.validate_state()

            before_runtime = {
                path.relative_to(root / ".cerebro").as_posix(): path.read_bytes()
                for path in sorted((root / ".cerebro").rglob("*"))
                if path.is_file()
            }
            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--limit", "4"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )

            after_runtime = {
                path.relative_to(root / ".cerebro").as_posix(): path.read_bytes()
                for path in sorted((root / ".cerebro").rglob("*"))
                if path.is_file()
            }

            self.assertEqual(result.returncode, 0)
            self.assertEqual(before_runtime, after_runtime)

    def test_scan_reports_no_strong_candidates_when_no_entry_signal_exists(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "notes").mkdir()
            (root / "notes" / "ideas.txt").write_text("free notes", encoding="utf-8")
            stream = io.StringIO()
            args = type("Args", (), {"root": str(root), "limit": 6})

            with redirect_stdout(stream):
                exit_code = run_bootstrap_scan(root, args)

            output = stream.getvalue()
            self.assertEqual(exit_code, 0)
            self.assertIn("candidates_found: 0", output)
            self.assertIn("shortlist_returned: 0", output)
            self.assertIn("no_strong_candidates:", output)

    def test_assisted_bootstrap_flow_by_subprocess(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "README.md").write_text("root readme", encoding="utf-8")
            (root / "controle").mkdir()
            (root / "controle" / "CONTEXTO_MESTRE.md").write_text("context", encoding="utf-8")
            (root / "controle" / "00_ESTADO_ATUAL.md").write_text("state", encoding="utf-8")
            (root / "tracked.txt").write_text("tracked", encoding="utf-8")

            env = os.environ.copy()
            existing_pythonpath = env.get("PYTHONPATH")
            env["PYTHONPATH"] = str(REPO_ROOT) if not existing_pythonpath else f"{REPO_ROOT}{os.pathsep}{existing_pythonpath}"

            init_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "init"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(init_result.returncode, 0)

            scan_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--limit", "4"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(scan_result.returncode, 0)
            self.assertIn("controle/CONTEXTO_MESTRE.md", scan_result.stdout)
            self.assertIn("controle/00_ESTADO_ATUAL.md", scan_result.stdout)

            import_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    "import-context",
                    "--files",
                    "README.md",
                    "controle/CONTEXTO_MESTRE.md",
                    "controle/00_ESTADO_ATUAL.md",
                ],
                cwd=root,
                env=env,
                input="y\n",
                capture_output=True,
                text=True,
            )
            self.assertEqual(import_result.returncode, 0)
            self.assertIn("sources_registered: 3", import_result.stdout)

            checkpoint_result = subprocess.run(
                [
                    sys.executable,
                    "-m",
                    "cli.main",
                    "checkpoint",
                    "--goal",
                    "Goal",
                    "--summary",
                    "Summary",
                    "--next-step",
                    "Next",
                ],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(checkpoint_result.returncode, 0)

            analyze_result = subprocess.run(
                [sys.executable, "-m", "cli.main", "analyze", "--actor", "alice"],
                cwd=root,
                env=env,
                capture_output=True,
                text=True,
            )
            self.assertEqual(analyze_result.returncode, 0)
            self.assertIn("analysis_ready", analyze_result.stdout)
            self.assertIn("validation: ok", analyze_result.stdout)
