from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from cli.commands.residuals_view import (
    ResidualsViewError,
    render_residuals_json,
    render_residuals_markdown,
    run_residuals_view,
)


REPO_ROOT = Path(__file__).resolve().parents[1]


class ResidualsViewTests(unittest.TestCase):
    def test_render_residuals_markdown_contains_expected_fields(self) -> None:
        output = render_residuals_markdown(REPO_ROOT, exported_at="2026-04-20T12:00:00+00:00")

        self.assertIn("# Residuals View", output)
        self.assertIn("- Exported at: 2026-04-20T12:00:00+00:00", output)
        self.assertIn("- Total residuals: 3", output)
        self.assertIn("- accepted: 3", output)
        self.assertIn("## Residuals", output)
        self.assertIn("RES-SESSION-OWNERSHIP-001", output)
        self.assertIn("RES-VERIFY-BOUNDARY-001", output)
        self.assertIn("RES-APPLY-ROLLBACK-ATOMICITY-001", output)

    def test_render_residuals_json_contains_expected_shape(self) -> None:
        payload = render_residuals_json(REPO_ROOT, exported_at="2026-04-20T12:00:00+00:00")

        self.assertEqual(payload["schema_version"], "1")
        self.assertEqual(payload["export_kind"], "residuals_view")
        self.assertEqual(payload["exported_at"], "2026-04-20T12:00:00+00:00")
        self.assertEqual(payload["counts"]["total"], 3)
        self.assertEqual(payload["counts"]["accepted"], 3)
        self.assertEqual(len(payload["residuals"]), 3)

    def test_render_residuals_fails_when_taxonomy_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            root = Path(tmp_dir)
            (root / "docs" / "operations").mkdir(parents=True, exist_ok=True)

            with self.assertRaises(ResidualsViewError):
                render_residuals_markdown(root)

    def test_run_residuals_view_writes_json_to_stdout(self) -> None:
        stream = io.StringIO()

        with redirect_stdout(stream):
            exit_code = run_residuals_view(
                REPO_ROOT,
                type("Args", (), {"format": "json", "out": None, "exported_at": "2026-04-20T12:00:00+00:00"}),
            )

        output = stream.getvalue()
        self.assertEqual(exit_code, 0)
        parsed = json.loads(output)
        self.assertEqual(parsed["export_kind"], "residuals_view")
        self.assertEqual(parsed["counts"]["total"], 3)


if __name__ == "__main__":
    unittest.main()
