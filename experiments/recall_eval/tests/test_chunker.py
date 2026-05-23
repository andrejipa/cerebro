from __future__ import annotations

import unittest

from experiments.recall_eval.chunker import chunk_text


class ChunkerTests(unittest.TestCase):
    def test_chunker_is_deterministic(self) -> None:
        text = "A\n\nB\n\n" * 300
        first = chunk_text(project_name="demo", root="X:/demo", path="README.md", text=text)
        second = chunk_text(project_name="demo", root="X:/demo", path="README.md", text=text)

        self.assertEqual(first, second)
        self.assertGreater(len(first), 1)
