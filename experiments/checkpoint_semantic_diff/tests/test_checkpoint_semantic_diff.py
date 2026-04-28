"""Tests for experiments.checkpoint_semantic_diff.

Covers: extractor, scorer (tokenizer, jaccard, classify_alignment,
score_alignment), report (markdown/JSON format, non-mutation boundary).
"""
from __future__ import annotations
import json
import tempfile
import unittest
from pathlib import Path

from experiments.checkpoint_semantic_diff.extractor import (
    CheckpointText,
    SourceRecord,
    extract_checkpoint,
    extract_sources,
    load_state,
)
from experiments.checkpoint_semantic_diff.scorer import (
    SourceAlignment,
    classify_alignment,
    jaccard,
    score_alignment,
    _tokenize,
)
from experiments.checkpoint_semantic_diff.report import to_markdown, write_report


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _state(goal="", summary="", next_step="", sources=None, updated_at=None):
    cp = {"goal": goal, "summary": summary, "next_step": next_step}
    if updated_at:
        cp["updated_at"] = updated_at
    return {"checkpoint": cp, "sources": sources or []}


def _src_record(path="doc.md", role="primary", content="some content", sha256="abc"):
    return SourceRecord(path=path, sha256=sha256, role=role, content=content)


# ---------------------------------------------------------------------------
# extractor
# ---------------------------------------------------------------------------

class ExtractCheckpointTests(unittest.TestCase):

    def test_extracts_all_fields(self) -> None:
        state = _state(goal="Build X", summary="Done Y", next_step="Start Z",
                       updated_at="2026-01-01T00:00:00+00:00")
        cp = extract_checkpoint(state)
        self.assertIsNotNone(cp)
        self.assertEqual(cp.goal, "Build X")
        self.assertEqual(cp.summary, "Done Y")
        self.assertEqual(cp.next_step, "Start Z")
        self.assertEqual(cp.updated_at, "2026-01-01T00:00:00+00:00")

    def test_full_text_joins_fields(self) -> None:
        cp = CheckpointText(goal="Build X", summary="Done Y",
                            next_step="Start Z", updated_at=None)
        self.assertIn("Build X", cp.full_text)
        self.assertIn("Done Y", cp.full_text)
        self.assertIn("Start Z", cp.full_text)

    def test_returns_none_when_no_checkpoint(self) -> None:
        state = {"sources": []}
        self.assertIsNone(extract_checkpoint(state))

    def test_handles_missing_fields_gracefully(self) -> None:
        state = {"checkpoint": {"goal": "only goal"}}
        cp = extract_checkpoint(state)
        self.assertIsNotNone(cp)
        self.assertEqual(cp.goal, "only goal")
        self.assertEqual(cp.summary, "")
        self.assertEqual(cp.next_step, "")

    def test_extract_sources_reads_existing_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "README.md").write_text("# Hello world", encoding="utf-8")
            state = _state(sources=[{"path": "README.md", "sha256": "x", "role": "primary"}])
            srcs = extract_sources(state, root)
            self.assertEqual(len(srcs), 1)
            self.assertEqual(srcs[0].content, "# Hello world")

    def test_extract_sources_absent_file_gives_none_content(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            state = _state(sources=[{"path": "missing.md", "sha256": "x", "role": "primary"}])
            srcs = extract_sources(state, root)
            self.assertIsNone(srcs[0].content)

    def test_load_state_parses_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / "state.json"
            p.write_text(json.dumps({"checkpoint": {"goal": "test"}}), encoding="utf-8")
            s = load_state(p)
            self.assertEqual(s["checkpoint"]["goal"], "test")


# ---------------------------------------------------------------------------
# scorer — tokenizer
# ---------------------------------------------------------------------------

class TokenizerTests(unittest.TestCase):

    def test_lowercases_tokens(self) -> None:
        tokens = _tokenize("Hello WORLD")
        self.assertIn("hello", tokens)
        self.assertIn("world", tokens)

    def test_strips_punctuation(self) -> None:
        tokens = _tokenize("fix: the bug!")
        self.assertNotIn(":", tokens)
        self.assertNotIn("!", tokens)

    def test_ignores_single_char_tokens(self) -> None:
        tokens = _tokenize("a b c word")
        self.assertNotIn("a", tokens)
        self.assertNotIn("b", tokens)
        self.assertIn("word", tokens)

    def test_empty_string_returns_empty(self) -> None:
        self.assertEqual(_tokenize(""), frozenset())

    def test_deduplicates_tokens(self) -> None:
        tokens = _tokenize("the the the")
        self.assertEqual(len(tokens), 1)


# ---------------------------------------------------------------------------
# scorer — jaccard
# ---------------------------------------------------------------------------

class JaccardTests(unittest.TestCase):

    def test_identical_sets_score_one(self) -> None:
        a = frozenset(["apple", "banana"])
        self.assertAlmostEqual(jaccard(a, a), 1.0)

    def test_disjoint_sets_score_zero(self) -> None:
        a = frozenset(["apple"])
        b = frozenset(["banana"])
        self.assertAlmostEqual(jaccard(a, b), 0.0)

    def test_partial_overlap(self) -> None:
        a = frozenset(["apple", "banana"])
        b = frozenset(["banana", "cherry"])
        # intersection=1, union=3
        self.assertAlmostEqual(jaccard(a, b), round(1 / 3, 4))

    def test_empty_sets_return_zero(self) -> None:
        self.assertAlmostEqual(jaccard(frozenset(), frozenset()), 0.0)

    def test_one_empty_set(self) -> None:
        a = frozenset(["apple"])
        self.assertAlmostEqual(jaccard(a, frozenset()), 0.0)

    def test_result_is_rounded_to_4dp(self) -> None:
        a = frozenset(["a", "b", "c"])
        b = frozenset(["b", "c", "d"])
        score = jaccard(a, b)
        self.assertEqual(score, round(score, 4))


# ---------------------------------------------------------------------------
# scorer — classify_alignment
# ---------------------------------------------------------------------------

class ClassifyAlignmentTests(unittest.TestCase):

    def test_high_at_threshold(self) -> None:
        self.assertEqual(classify_alignment(0.15), "high")

    def test_high_above_threshold(self) -> None:
        self.assertEqual(classify_alignment(0.9), "high")

    def test_medium_in_range(self) -> None:
        self.assertEqual(classify_alignment(0.1), "medium")

    def test_medium_at_lower_boundary(self) -> None:
        self.assertEqual(classify_alignment(0.04), "medium")

    def test_low_below_medium(self) -> None:
        self.assertEqual(classify_alignment(0.03), "low")

    def test_low_at_zero(self) -> None:
        self.assertEqual(classify_alignment(0.0), "low")


# ---------------------------------------------------------------------------
# scorer — score_alignment
# ---------------------------------------------------------------------------

class ScoreAlignmentTests(unittest.TestCase):

    def test_returns_list_sorted_by_score_descending(self) -> None:
        sources = [
            _src_record("low.md", content="unrelated xyz abc"),
            _src_record("high.md", content="authentication user login token system auth"),
        ]
        results = score_alignment("authentication user login system", sources)
        self.assertGreater(results[0].jaccard_score, results[1].jaccard_score)

    def test_unavailable_source_gets_zero_score(self) -> None:
        sources = [_src_record("missing.md", content=None)]
        results = score_alignment("test checkpoint", sources)
        self.assertEqual(results[0].jaccard_score, 0.0)
        self.assertEqual(results[0].alignment, "unavailable")
        self.assertFalse(results[0].source_available)

    def test_available_source_has_source_available_true(self) -> None:
        sources = [_src_record("doc.md", content="hello world")]
        results = score_alignment("hello world", sources)
        self.assertTrue(results[0].source_available)

    def test_shared_tokens_count_is_correct(self) -> None:
        cp_text = "build authentication system"
        src_content = "authentication system test"
        sources = [_src_record("doc.md", content=src_content)]
        results = score_alignment(cp_text, sources)
        # shared: {"authentication", "system"} = 2
        self.assertEqual(results[0].shared_tokens, 2)

    def test_empty_sources_returns_empty_list(self) -> None:
        results = score_alignment("some checkpoint", [])
        self.assertEqual(results, [])

    def test_checkpoint_tokens_reflect_checkpoint_text(self) -> None:
        cp_text = "hello world"
        sources = [_src_record("doc.md", content="other stuff")]
        results = score_alignment(cp_text, sources)
        # cp tokens: {"hello", "world"} = 2
        self.assertEqual(results[0].checkpoint_tokens, 2)


# ---------------------------------------------------------------------------
# report
# ---------------------------------------------------------------------------

class ReportTests(unittest.TestCase):

    def _sample_alignments(self):
        return [
            SourceAlignment(path="README.md", role="primary", jaccard_score=0.25,
                            alignment="high", shared_tokens=5, checkpoint_tokens=20,
                            source_tokens=30, source_available=True),
            SourceAlignment(path="ARCH.md", role="secondary", jaccard_score=0.01,
                            alignment="low", shared_tokens=1, checkpoint_tokens=20,
                            source_tokens=50, source_available=True),
        ]

    def test_markdown_contains_checkpoint_excerpt(self) -> None:
        md = to_markdown("Build the auth system", self._sample_alignments(), None)
        self.assertIn("Build the auth system", md)

    def test_markdown_contains_source_paths(self) -> None:
        md = to_markdown("test", self._sample_alignments(), None)
        self.assertIn("README.md", md)
        self.assertIn("ARCH.md", md)

    def test_markdown_includes_alignment_labels(self) -> None:
        md = to_markdown("test", self._sample_alignments(), None)
        self.assertIn("HIGH", md)
        self.assertIn("LOW", md)

    def test_markdown_has_non_authoritative_footer(self) -> None:
        md = to_markdown("test", self._sample_alignments(), None)
        self.assertIn("Non-authoritative", md)

    def test_write_report_creates_two_files(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            out = Path(tmp) / "reports"
            md_path, json_path = write_report("test", self._sample_alignments(), None, out)
            self.assertTrue(md_path.exists())
            self.assertTrue(json_path.exists())

    def test_json_report_has_expected_keys(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, json_path = write_report("test", self._sample_alignments(), None, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
        for key in ("generated_at", "sources_evaluated", "alignments"):
            self.assertIn(key, data)

    def test_json_alignments_match_input(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            _, json_path = write_report("test", self._sample_alignments(), None, Path(tmp))
            data = json.loads(json_path.read_text(encoding="utf-8"))
        self.assertEqual(len(data["alignments"]), 2)
        self.assertEqual(data["alignments"][0]["path"], "README.md")

    def test_report_does_not_write_to_cerebro(self) -> None:
        """Non-mutation boundary: write_report must not touch .cerebro/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            write_report("test", self._sample_alignments(), None, root / "out")
            self.assertFalse((root / ".cerebro").exists())

    def test_unavailable_source_marked_in_markdown(self) -> None:
        alignments = [
            SourceAlignment(path="gone.md", role="primary", jaccard_score=0.0,
                            alignment="unavailable", shared_tokens=0, checkpoint_tokens=5,
                            source_tokens=0, source_available=False),
        ]
        md = to_markdown("test", alignments, None)
        self.assertIn("unavailable", md.lower())


# ---------------------------------------------------------------------------
# end-to-end pipeline
# ---------------------------------------------------------------------------

class EndToEndTests(unittest.TestCase):

    def test_pipeline_with_real_state_json(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir()
            state = {
                "checkpoint": {
                    "goal": "Build authentication system",
                    "summary": "Auth module created with token validation",
                    "next_step": "Add refresh token support",
                    "updated_at": "2026-01-01T00:00:00+00:00",
                },
                "sources": [
                    {"path": "auth.md", "sha256": "abc", "role": "primary"},
                    {"path": "missing.md", "sha256": "def", "role": "secondary"},
                ],
            }
            (cerebro_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
            (root / "auth.md").write_text(
                "# Authentication\nToken-based auth. Refresh token support. System design.",
                encoding="utf-8",
            )
            from experiments.checkpoint_semantic_diff.extractor import (
                extract_checkpoint, extract_sources, load_state,
            )
            from experiments.checkpoint_semantic_diff.scorer import score_alignment
            from experiments.checkpoint_semantic_diff.report import write_report
            loaded = load_state(cerebro_dir / "state.json")
            cp = extract_checkpoint(loaded)
            sources = extract_sources(loaded, root)
            alignments = score_alignment(cp.full_text, sources)
            out = root / "reports"
            md_path, json_path = write_report(cp.full_text, alignments, cp.updated_at, out)
            self.assertTrue(md_path.exists())
            data = json.loads(json_path.read_text(encoding="utf-8"))
            self.assertEqual(data["sources_evaluated"], 2)
            # auth.md should score higher than missing.md (unavailable)
            self.assertGreater(alignments[0].jaccard_score, alignments[-1].jaccard_score)

    def test_pipeline_does_not_mutate_cerebro(self) -> None:
        """Full pipeline must not write to .cerebro/."""
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            cerebro_dir = root / ".cerebro"
            cerebro_dir.mkdir()
            state = {"checkpoint": {"goal": "test"}, "sources": []}
            (cerebro_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
            before = set(cerebro_dir.iterdir())
            from experiments.checkpoint_semantic_diff.extractor import (
                extract_checkpoint, extract_sources, load_state,
            )
            from experiments.checkpoint_semantic_diff.scorer import score_alignment
            from experiments.checkpoint_semantic_diff.report import write_report
            loaded = load_state(cerebro_dir / "state.json")
            cp = extract_checkpoint(loaded)
            sources = extract_sources(loaded, root)
            alignments = score_alignment(cp.full_text, sources)
            write_report(cp.full_text, alignments, cp.updated_at, root / "out")
            after = set(cerebro_dir.iterdir())
            self.assertEqual(before, after)


if __name__ == "__main__":
    unittest.main()
