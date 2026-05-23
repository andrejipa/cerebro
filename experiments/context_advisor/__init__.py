"""LLM-facing context advisor derived track.

This package combines context-discovery and context-vector evidence into a
read-only advisory report for downstream agents. It is non-authoritative: it
may suggest what an LLM should inspect next, but it must never apply changes,
register sources, or mutate canonical state.
"""

from .advisor import (
    AdvisoryRecommendation,
    AdvisoryReport,
    VectorEvidence,
    advise_context,
)
from .report import render_markdown

__all__ = [
    "AdvisoryRecommendation",
    "AdvisoryReport",
    "VectorEvidence",
    "advise_context",
    "render_markdown",
]
