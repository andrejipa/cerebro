from __future__ import annotations

from pathlib import Path
import unittest


PACKAGE_ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_package_does_not_import_core_or_runtime_commands(self) -> None:
        for path in PACKAGE_ROOT.glob("*.py"):
            text = path.read_text(encoding="utf-8")
            self.assertNotIn("import core", text, path.name)
            self.assertNotIn("from core", text, path.name)
            self.assertNotIn("cli.commands.analyze", text, path.name)
            self.assertNotIn("cli.commands.validate", text, path.name)
            self.assertNotIn("cli.commands.checkpoint", text, path.name)

    def test_default_registry_path_stays_outside_cerebro_runtime_dir(self) -> None:
        registry_path = PACKAGE_ROOT / "unmet_use_cases.toml"
        self.assertNotIn(".cerebro", registry_path.parts)
