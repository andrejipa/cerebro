from __future__ import annotations

import io
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

            result = subprocess.run(
                [sys.executable, "-m", "cli.main", "bootstrap-scan", "--root", str(root), "--limit", "3"],
                cwd=REPO_ROOT,
                capture_output=True,
                text=True,
            )
            self.assertEqual(result.returncode, 0)
            self.assertIn("mode: assistive-only", result.stdout)
            self.assertIn("next_action:", result.stdout)
            self.assertIn("README.md", result.stdout)
