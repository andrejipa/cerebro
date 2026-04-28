"""Experimental context-discovery derived track.

This package is derived, non-authoritative, opt-in, and observability-only.
It compares the canonical Cerebro state against the current target-project
filesystem and produces a human-reviewable report. It must never be treated
as canonical runtime state or as a decision gate.
"""

from .content import MAX_CONTENT_BYTES, MAX_CONTENT_LINES, read_content_head
from .discovery import (
    Candidate,
    DiscoveryReport,
    DriftRecord,
    MissingRecord,
    discover_context,
)
from .report import render_markdown

__all__ = [
    "Candidate",
    "DiscoveryReport",
    "DriftRecord",
    "MAX_CONTENT_BYTES",
    "MAX_CONTENT_LINES",
    "MissingRecord",
    "discover_context",
    "read_content_head",
    "render_markdown",
]
