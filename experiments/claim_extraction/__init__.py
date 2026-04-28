from __future__ import annotations

from .contract import ClaimCandidate, SourceText
from .extractor import extract_candidates
from .fixtures import FIXTURES, FixtureCase
from .render import render_candidates_markdown

__all__ = [
    "ClaimCandidate",
    "FIXTURES",
    "FixtureCase",
    "SourceText",
    "extract_candidates",
    "render_candidates_markdown",
]

