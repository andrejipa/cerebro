"""Advisory evaluation over claim candidates.

This derived package evaluates `ClaimCandidate` inputs without creating a claim
graph or deciding canonical truth. It is local-only, read-only, and
non-authoritative.
"""

from .contract import EvaluationFinding, EvaluationReport
from .evaluator import evaluate_claims
from .render import render_evaluation_markdown

__all__ = [
    "EvaluationFinding",
    "EvaluationReport",
    "evaluate_claims",
    "render_evaluation_markdown",
]
